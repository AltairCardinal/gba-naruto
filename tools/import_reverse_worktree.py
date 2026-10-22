#!/usr/bin/env python3
"""Mirror the reverse-engineering worktree's deliverables into the viewer repo.

The results viewer lives in this repository, but the reverse-engineering work
happens in a sibling worktree.  Everything the viewer shows has to exist here,
so this imports the three kinds of deliverables that live only there:

  * ``artifacts/<family>/``  -- a family that has no copy here yet
  * ``notes/**/*.md``        -- investigation notes, mirrored to ``notes/reverse/``
  * ``tools/*.py``           -- analysis tools, mirrored to ``tools/reverse/``

Every file is pinned by SHA-256.  When the family's own manifest lists a file
with a hash, that hash is checked and a mismatch aborts the import; files the
manifest does not pin are copied and their hash is recorded in the receipt, so
the next run can verify them.

The importer is idempotent: a family that is already present is verified, not
overwritten, and the receipt records what was checked.

Usage:
    python3 tools/import_reverse_worktree.py [--root .] [--source <worktree>]
    python3 tools/import_reverse_worktree.py --root . --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = "../gba-naruto-reverse"
NOTES_PREFIX = "notes/reverse"
TOOLS_PREFIX = "tools/reverse"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _head_commit(source: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _manifest_pins(manifest: dict[str, Any]) -> dict[str, str]:
    """SHA-256 pins declared by the family's own manifest."""
    pins: dict[str, str] = {}
    files = manifest.get("files")
    if isinstance(files, dict):
        for name, info in files.items():
            if isinstance(info, dict) and isinstance(info.get("sha256"), str):
                pins[name] = info["sha256"]
    return pins


def _copy_verified(source: Path, target: Path, expected: str | None) -> str:
    """Copy one file, checking the pin when there is one."""
    digest = _sha256(source)
    if expected and digest != expected:
        raise ValueError(
            f"{source.name}: sha256 mismatch "
            f"(manifest {expected[:12]}, file {digest[:12]})")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return digest


def import_artifacts(root: Path, source: Path, dry_run: bool,
                     only: set[str] | None = None) -> dict[str, Any]:
    src_root = source / "artifacts"
    dst_root = root / "artifacts"
    result: dict[str, Any] = {"imported": [], "verified": [], "skipped": []}
    if not src_root.is_dir():
        return result
    for family_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
        family = family_dir.name
        if only and family not in only:
            continue
        manifest_path = family_dir / "manifest.json"
        dst_dir = dst_root / family
        pins: dict[str, str] = {}
        manifest: dict[str, Any] = {}
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            pins = _manifest_pins(manifest)
        if dst_dir.is_dir():
            # Already imported: verify the pinned files instead of copying.
            bad = []
            for name, expected in pins.items():
                target = dst_dir / name
                if not target.is_file() or _sha256(target) != expected:
                    bad.append(name)
            result["verified" if not bad else "skipped"].append(
                {"family": family, "files": len(pins),
                 "mismatched": bad})
            continue
        if dry_run:
            result["imported"].append({"family": family, "files": len(pins),
                                       "planned": True})
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for path in sorted(family_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(family_dir)
            _copy_verified(path, dst_dir / rel, pins.get(rel.as_posix()))
            copied += 1
        result["imported"].append({
            "family": family,
            "files": copied,
            "pinned": len(pins),
            "unpinned": copied - len(pins),
            "has_manifest": manifest_path.is_file(),
        })
    return result


def _flatten(rel: Path) -> str:
    """A collision-free flat name for a file that lives deeper than one level."""
    return "__".join(rel.parts)


def _local_names(root: Path, folder: str, suffix: str) -> dict[str, Path]:
    """Every file already present locally under ``folder``, by base name."""
    out: dict[str, Path] = {}
    for path in (root / folder).rglob(f"*{suffix}"):
        out[path.name] = path
    return out


def import_notes(root: Path, source: Path, dry_run: bool) -> dict[str, Any]:
    src_root = source / "notes"
    dst_root = root / NOTES_PREFIX
    result: dict[str, Any] = {"imported": [], "identical": [],
                               "divergent": []}
    if not src_root.is_dir():
        return result
    local = _local_names(root, "notes", ".md")
    for path in sorted(src_root.rglob("*.md")):
        rel = path.relative_to(src_root)
        target = dst_root / _flatten(rel)
        if target.is_file():
            result["identical"].append(target.relative_to(root).as_posix())
            continue
        # A note that already exists here is not copied: the two branches
        # diverged, and the local copy is the one this site is built from --
        # it carries the corrections the reverse branch has not taken yet.
        # The divergence is recorded rather than silently dropped.
        existing = local.get(path.name)
        if existing is not None:
            if existing.read_bytes() == path.read_bytes():
                result["identical"].append(rel.as_posix())
            else:
                result["divergent"].append({
                    "source": rel.as_posix(),
                    "local": existing.relative_to(root).as_posix(),
                    "local_sha256": _sha256(existing),
                    "source_sha256": _sha256(path),
                })
            continue
        if dry_run:
            result["imported"].append(target.relative_to(root).as_posix())
            continue
        digest = _copy_verified(path, target, None)
        result["imported"].append({
            "path": target.relative_to(root).as_posix(),
            "source": rel.as_posix(),
            "sha256": digest,
        })
    # A few investigation notes live in the reverse tree's docs/ directory.
    docs_root = source / "docs"
    if docs_root.is_dir():
        for path in sorted(docs_root.glob("*.md")):
            target = dst_root / _flatten(Path("docs") / path.name)
            if target.is_file():
                result["identical"].append(target.relative_to(root).as_posix())
                continue
            existing = local.get(path.name)
            if existing is not None:
                result["divergent"].append({
                    "source": (Path("docs") / path.name).as_posix(),
                    "local": existing.relative_to(root).as_posix(),
                    "local_sha256": _sha256(existing),
                    "source_sha256": _sha256(path),
                })
                continue
            if dry_run:
                result["imported"].append(target.relative_to(root).as_posix())
                continue
            digest = _copy_verified(path, target, None)
            result["imported"].append({
                "path": target.relative_to(root).as_posix(),
                "source": (Path("docs") / path.name).as_posix(),
                "sha256": digest,
            })
    return result


def import_tools(root: Path, source: Path, dry_run: bool) -> dict[str, Any]:
    src_root = source / "tools"
    dst_root = root / TOOLS_PREFIX
    result: dict[str, Any] = {"imported": [], "identical": [],
                               "divergent": []}
    if not src_root.is_dir():
        return result
    local = _local_names(root, "tools", ".py")
    for path in sorted(src_root.rglob("*.py")):
        rel = path.relative_to(src_root)
        target = dst_root / _flatten(rel)
        if target.is_file():
            result["identical"].append(target.relative_to(root).as_posix())
            continue
        # Same rule as for the notes: a tool that exists here is not replaced.
        # The viewer's own copy is the one the site is built with, and the
        # reverse branch's older revisions of the same file are recorded.
        existing = local.get(path.name)
        if existing is not None:
            if existing.read_bytes() == path.read_bytes():
                result["identical"].append(rel.as_posix())
            else:
                result["divergent"].append({
                    "source": rel.as_posix(),
                    "local": existing.relative_to(root).as_posix(),
                    "local_sha256": _sha256(existing),
                    "source_sha256": _sha256(path),
                })
            continue
        if dry_run:
            result["imported"].append(target.relative_to(root).as_posix())
            continue
        digest = _copy_verified(path, target, None)
        result["imported"].append({
            "path": target.relative_to(root).as_posix(),
            "source": rel.as_posix(),
            "sha256": digest,
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source", type=Path, action="append", default=None,
                        help="source worktree; repeatable.  The first one is "
                             f"also the source of the notes and tools "
                             f"(default {DEFAULT_SOURCE})")
    parser.add_argument("--families", type=str, default=None,
                        help="comma separated family names to import; with "
                             "this flag only the artifacts are imported")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--receipt", type=Path,
                        default=Path("build/viewer-data/reverse-import.json"))
    args = parser.parse_args()

    root = args.root.resolve()
    sources = [p.resolve() for p in (args.source or [Path(DEFAULT_SOURCE)])]
    missing = [s for s in sources if not s.is_dir()]
    if missing:
        for s in missing:
            print(f"source worktree not found: {s}")
        return 2
    only = (set(n.strip() for n in args.families.split(",") if n.strip())
            if args.families else None)

    artifacts: dict[str, Any] = {"imported": [], "verified": [], "skipped": []}
    for source in sources:
        part = import_artifacts(root, source, args.dry_run, only)
        for key in artifacts:
            artifacts[key].extend(part[key])

    # Notes and tools come from the first source only: the other tree is the
    # remake workstream, whose notes are not reverse-engineering findings.
    notes = import_notes(root, sources[0], args.dry_run)
    tools = import_tools(root, sources[0], args.dry_run)

    receipt = {
        "schema": "viewer-reverse-import-v1",
        "source": str(sources[0]),
        "sources": [str(s) for s in sources],
        "source_commit": _head_commit(sources[0]),
        "family_filter": sorted(only) if only else None,
        "dry_run": args.dry_run,
        "artifacts": artifacts,
        "notes": notes,
        "tools": tools,
        "totals": {
            "families_imported": len(artifacts["imported"]),
            "families_verified": len(artifacts["verified"]),
            "notes_imported": len(notes["imported"]),
            "notes_identical": len(notes["identical"]),
            "notes_divergent": len(notes["divergent"]),
            "tools_imported": len(tools["imported"]),
            "tools_identical": len(tools["identical"]),
            "tools_divergent": len(tools["divergent"]),
        },
    }
    if not args.dry_run:
        receipt_path = args.receipt
        if not receipt_path.is_absolute():
            receipt_path = root / receipt_path
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    totals = receipt["totals"]
    print(f"source={sources[0]} commit={receipt['source_commit'][:7]}")
    if len(sources) > 1:
        print("also imported artifacts from: "
              + ", ".join(str(s) for s in sources[1:]))
    print(f"families imported={totals['families_imported']} "
          f"verified={totals['families_verified']}")
    print(f"notes imported={totals['notes_imported']} "
          f"identical={totals['notes_identical']} "
          f"divergent={totals['notes_divergent']}")
    print(f"tools imported={totals['tools_imported']} "
          f"identical={totals['tools_identical']} "
          f"divergent={totals['tools_divergent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
