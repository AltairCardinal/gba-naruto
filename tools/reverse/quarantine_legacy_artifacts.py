#!/usr/bin/env python3
"""Hide fully untracked legacy artifact roots from routine Git scans."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any


BEGIN = "# BEGIN gba-naruto legacy artifact quarantine"
END = "# END gba-naruto legacy artifact quarantine"


def _git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode("utf-8", "replace"))
    return completed.stdout


def _top_level_artifact(path: str) -> str | None:
    parts = path.split("/")
    if len(parts) < 3 or parts[0] != "artifacts":
        return None
    return "/".join(parts[:2])


def plan_quarantine(root: Path) -> dict[str, Any]:
    root = root.resolve()
    raw = _git(
        root,
        "ls-files",
        "--others",
        "-z",
        "--",
        "artifacts",
    )
    files_by_root: dict[str, list[str]] = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        relative = item.decode("utf-8", "surrogateescape")
        candidate = _top_level_artifact(relative)
        if candidate is not None:
            files_by_root.setdefault(candidate, []).append(relative)

    directories = []
    selected_files = []
    for candidate in sorted(files_by_root):
        tracked = _git(root, "ls-files", "-z", "--", candidate)
        if tracked:
            continue
        directories.append(candidate)
        selected_files.extend(files_by_root[candidate])

    byte_count = 0
    existing_files = 0
    for relative in selected_files:
        path = root / relative
        if path.is_file() and not path.is_symlink():
            byte_count += path.stat().st_size
            existing_files += 1

    return {
        "schema": "legacy-artifact-quarantine-v1",
        "root": str(root),
        "directories": directories,
        "directory_count": len(directories),
        "file_count": existing_files,
        "byte_count": byte_count,
        "patterns": [f"/{directory}/" for directory in directories],
    }


def _replace_section(text: str, patterns: list[str]) -> str:
    lines = text.splitlines()
    result = []
    inside = False
    for line in lines:
        if line == BEGIN:
            inside = True
            continue
        if line == END:
            inside = False
            continue
        if not inside:
            result.append(line)
    while result and not result[-1]:
        result.pop()
    if result:
        result.append("")
    result.extend([BEGIN, *patterns, END])
    return "\n".join(result) + "\n"


def apply_quarantine(root: Path, *, audit_path: Path) -> dict[str, Any]:
    root = root.resolve()
    plan = plan_quarantine(root)
    exclude_raw = _git(root, "rev-parse", "--git-path", "info/exclude")
    exclude = Path(exclude_raw.decode("utf-8", "surrogateescape").strip())
    if not exclude.is_absolute():
        exclude = root / exclude
    previous = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text(
        _replace_section(previous, plan["patterns"]),
        encoding="utf-8",
    )

    result = {
        **plan,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "exclude_file": str(exclude.resolve()),
        "reversible": True,
    }
    audit_path = audit_path if audit_path.is_absolute() else root / audit_path
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("build/experiments/legacy-artifact-quarantine.json"),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the reversible section to .git/info/exclude",
    )
    args = parser.parse_args()
    try:
        result = (
            apply_quarantine(args.root, audit_path=args.audit)
            if args.apply
            else plan_quarantine(args.root)
        )
    except (OSError, RuntimeError) as error:
        print(f"legacy-artifact-quarantine: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
