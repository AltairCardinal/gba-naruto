#!/usr/bin/env python3
"""Swap the H4 lane's graphics/ between the 8bpp and the 4bpp asset sets.

The 4bpp asset set is the **149** file set in build/w24-g2/assets-4bpp-full/
(F1's original hand-over only had 100 files; the extra 49 are the
battle_XX_map_chunks.json manifests).

Usage:
    python tools/s49_w25h4/swap_assets.py diff
    python tools/s49_w25h4/swap_assets.py to-4bpp
    python tools/s49_w25h4/swap_assets.py to-8bpp
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
LANE = REPO / "build" / "w25-h4" / "butano-sequel" / "graphics"
FOURBPP = REPO / "build" / "w24-g2" / "assets-4bpp-full"
EIGHTBPP_BACKUP = REPO / "build" / "w25-h4" / "assets-8bpp-backup"


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "diff"
    files = sorted(p for p in FOURBPP.rglob("*") if p.is_file())
    print(f"4bpp asset set: {len(files)} files")

    if mode == "diff":
        already = sum(
            1 for p in files
            if (LANE / p.relative_to(FOURBPP)).exists()
            and sha(LANE / p.relative_to(FOURBPP)) == sha(p))
        print(f"already 4bpp in the lane: {already}/{len(files)}")
        return 0

    if mode == "to-4bpp":
        changed = 0
        for p in files:
            rel = p.relative_to(FOURBPP)
            dst = LANE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() and sha(dst) == sha(p):
                continue
            backup = EIGHTBPP_BACKUP / rel
            if dst.exists() and not backup.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(dst, backup)
            shutil.copyfile(p, dst)
            changed += 1
        print(f"copied {changed} files to 4bpp")
        return 0

    if mode == "to-8bpp":
        changed = 0
        for p in sorted(x for x in EIGHTBPP_BACKUP.rglob("*") if x.is_file()):
            rel = p.relative_to(EIGHTBPP_BACKUP)
            dst = LANE / rel
            if dst.exists() and sha(dst) == sha(p):
                continue
            shutil.copyfile(p, dst)
            changed += 1
        print(f"restored {changed} files to 8bpp")
        return 0

    print("unknown mode")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
