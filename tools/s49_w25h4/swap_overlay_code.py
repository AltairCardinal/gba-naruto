#!/usr/bin/env python3
"""Swap the H4 overlay code in the lane between "mine" and "baseline".

The lane is a copy of the shared tree plus the H4 overlay changes, so the
baseline of the *same* lane is the shared tree's version of the two files.
Both variants are byte-copied (never rewritten with a text API) because the
files contain UTF-8 Chinese comments.

Usage:
    python tools/s49_w25h4/swap_overlay_code.py save-mine
    python tools/s49_w25h4/swap_overlay_code.py use-baseline
    python tools/s49_w25h4/swap_overlay_code.py use-mine
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
LANE = REPO / "build" / "w25-h4" / "butano-sequel"
SHARED = pathlib.Path(r"D:\Github\gba-naruto-butano\butano-sequel")
BACKUP = REPO / "build" / "w25-h4" / "code-backup"

FILES = [
    "game/src/battle_runtime_scene.cpp",
    "game/include/konoha/battle_range_ui_style.h",
]


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(src: pathlib.Path, dst: pathlib.Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("save-mine", "use-baseline", "use-mine"):
        print(__doc__)
        return 2
    mode = sys.argv[1]
    for rel in FILES:
        lane_file = LANE / rel
        if mode == "save-mine":
            copy(lane_file, BACKUP / rel)
        elif mode == "use-baseline":
            copy(SHARED / rel, lane_file)
        else:
            copy(BACKUP / rel, lane_file)
    for rel in FILES:
        print(f"{rel}: {sha(LANE / rel)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
