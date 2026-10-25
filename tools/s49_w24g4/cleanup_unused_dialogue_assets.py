#!/usr/bin/env python3
"""Wave 24 / G4 task 3 -- safe deletion of the zero-reference
scenario_41_postbattle_dialogue_* assets.

Safety contract (in this order, every step must pass before the next runs):

  1. VERIFY   re-scan the CURRENT product tree; every target stem must have
              zero references outside its own sidecar, and the set of
              unreferenced stems must match the manifest exactly.
  2. BACKUP   copy every target file (byte-for-byte) into
              build/w24-g4/backup/ preserving the relative path, and write a
              sha256 ledger.
  3. DELETE   remove only the files listed in the manifest, only under the
              expected graphics directory.
  4. ROLLBACK `--rollback` restores every backed-up file from the ledger and
              re-verifies the sha256 of each restored file.

The script NEVER touches files outside the manifest and never deletes without
a matching backup.  Run with `--apply` to actually delete; the default is a
dry run.

Usage:
    python tools/s49_w24g4/cleanup_unused_dialogue_assets.py            # dry run
    python tools/s49_w24g4/cleanup_unused_dialogue_assets.py --apply    # delete
    python tools/s49_w24g4/cleanup_unused_dialogue_assets.py --rollback  # undo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys

REMIX = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")
GRAPHICS = REMIX / "graphics"
BUILD = pathlib.Path(r"D:\Github\gba-naruto\build\w24-g4")
BACKUP = BUILD / "backup"
MANIFEST = BUILD / "dialogue-asset-cleanup-manifest.json"
LEDGER = BACKUP / "backup-ledger.json"

TEXT_SUFFIXES = {
    ".cpp", ".h", ".hpp", ".c", ".py", ".lua", ".json", ".txt", ".md", ".cmake",
    ".mk", ".make", ".yml", ".yaml", ".toml", ".sh", ".ps1", ".cfg", ".ini",
}
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "build", "obj",
    ".cache", ".idea",
}


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_unreferenced() -> tuple[set[str], set[str]]:
    """Return (unreferenced_stems, referenced_stems) for the current tree."""
    assets = sorted(
        p for p in GRAPHICS.glob("scenario_41_postbattle_dialogue_*")
        if p.suffix in (".bmp", ".json")
    )
    stems = sorted({p.stem for p in assets})
    corpus = []
    for path in REMIX.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            corpus.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    unreferenced: set[str] = set()
    referenced: set[str] = set()
    for stem in stems:
        pattern = re.compile(re.escape(stem))
        hit = False
        for path, text in corpus:
            if path.parent == GRAPHICS:
                continue
            if pattern.search(text):
                hit = True
                break
        (referenced if hit else unreferenced).add(stem)
    return unreferenced, referenced


def verify(manifest: dict) -> tuple[bool, list[str]]:
    """Confirm the tree still matches the manifest exactly."""
    problems: list[str] = []
    unreferenced, referenced = scan_unreferenced()
    want_unref = set(manifest["files_stems"]) if "files_stems" in manifest else set()
    if not want_unref:
        want_unref = {pathlib.Path(f["path"]).stem for f in manifest["files"]}
    if unreferenced != want_unref:
        problems.append(
            "unreferenced stem set changed: "
            f"new={sorted(unreferenced - want_unref)} "
            f"gone={sorted(want_unref - unreferenced)}"
        )
    for entry in manifest["files"]:
        path = REMIX / entry["path"]
        if not path.is_file():
            problems.append(f"missing: {entry['path']}")
            continue
        digest = sha256(path)
        if digest != entry["sha256"]:
            problems.append(f"sha256 mismatch: {entry['path']}")
    return (not problems), problems


def do_backup(manifest: dict) -> pathlib.Path:
    BACKUP.mkdir(parents=True, exist_ok=True)
    ledger = []
    for entry in manifest["files"]:
        src = REMIX / entry["path"]
        dst = BACKUP / entry["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        digest = sha256(dst)
        if digest != entry["sha256"]:
            raise SystemExit(f"backup verification failed for {entry['path']}")
        ledger.append(
            {
                "path": entry["path"],
                "backup": str(dst.relative_to(BACKUP)).replace("\\", "/"),
                "bytes": dst.stat().st_size,
                "sha256": digest,
            }
        )
    LEDGER.write_text(
        json.dumps(
            {"schema": "konoha.s49-dialogue-asset-backup-ledger.v1", "files": ledger},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return LEDGER


def do_delete(manifest: dict) -> None:
    for entry in manifest["files"]:
        path = REMIX / entry["path"]
        if path.resolve().parent != GRAPHICS.resolve():
            raise SystemExit(f"refusing to delete outside graphics dir: {path}")
        if sha256(path) != entry["sha256"]:
            raise SystemExit(f"refusing to delete (sha256 changed): {path}")
        path.unlink()
        print(f"deleted {entry['path']}")


def do_rollback() -> None:
    if not LEDGER.is_file():
        raise SystemExit(f"no backup ledger at {LEDGER}")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    for entry in ledger["files"]:
        src = BACKUP / entry["backup"]
        dst = REMIX / entry["path"]
        if not src.is_file():
            raise SystemExit(f"backup missing for {entry['path']}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        digest = sha256(dst)
        if digest != entry["sha256"]:
            raise SystemExit(f"rollback verification failed for {entry['path']}")
        print(f"restored {entry['path']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually delete")
    ap.add_argument("--rollback", action="store_true", help="restore from backup")
    args = ap.parse_args()

    if args.rollback:
        do_rollback()
        print("rollback complete")
        return 0

    if not MANIFEST.is_file():
        raise SystemExit(
            f"manifest missing: {MANIFEST} "
            "(run tools/s49_w24g4/scan_unused_dialogue_assets.py first)"
        )
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    ok, problems = verify(manifest)
    if not ok:
        print("VERIFY FAILED -- nothing was deleted:")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print(f"VERIFY OK: {len(manifest['files'])} files still match the manifest")

    ledger = do_backup(manifest)
    print(f"BACKUP OK: {ledger}")

    if not args.apply:
        print("DRY RUN -- pass --apply to delete the backed-up files")
        return 0

    do_delete(manifest)
    print(f"deleted {len(manifest['files'])} files; rollback with --rollback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
