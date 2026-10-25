#!/usr/bin/env python3
"""W20-E2: locate the original ROM that matches the generator provenance hash.

The generator's provenance block pins the formation table at ROM 0x5461C4 with
length 317952 and sha256 6e3b0e0b...  We search candidate ROMs for that slice.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

OFFSET = 0x5461C4
LENGTH = 317952
WANT = "6e3b0e0bd39a701023d02ac53249c2967d5d1cb177866cb1491feee8897d5ed6"

CANDIDATE_DIRS = [
    Path(r"D:\Shell\Github\gba-naruto-butano\rom"),
    Path(r"D:\Shell\Github\gba-naruto-butano"),
    Path(r"D:\Shell\gba-naruto-reverse"),
    Path(r"D:\Github\gba-naruto\build"),
]


def sha256_slice(path: Path) -> tuple[str | None, str]:
    data = path.read_bytes()
    whole = hashlib.sha256(data).hexdigest()
    if len(data) < OFFSET + LENGTH:
        return None, whole
    return hashlib.sha256(data[OFFSET:OFFSET + LENGTH]).hexdigest(), whole


def main() -> int:
    seen: set[Path] = set()
    for d in CANDIDATE_DIRS:
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*.gba")):
            if path in seen:
                continue
            seen.add(path)
            try:
                slice_hash, whole = sha256_slice(path)
            except OSError as exc:  # pragma: no cover - diagnostics only
                print(f"SKIP {path}: {exc}")
                continue
            mark = ""
            if slice_hash == WANT:
                mark = "  <<< FORMATION TABLE MATCH"
            print(f"{path}\n    size={path.stat().st_size} whole={whole[:16]}\n    slice@{OFFSET:#x}={slice_hash}{mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
