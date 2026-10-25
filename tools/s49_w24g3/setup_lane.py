#!/usr/bin/env python3
"""W24-G3: build a *self contained* lane copy.

The wave-24 lane that the parent handed over keeps `graphics/` and `audio/`
as **symlinks into the shared tree**, so editing a lane asset edits the
shared tree (which is forbidden).  This script makes a lane whose `graphics/`
is a real directory, so that the settlement assets can be patched safely.

Usage:
  python tools/s49_w24g3/setup_lane.py --lane build/w24-g3/butano-sequel
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARED = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="build/w24-g3/butano-sequel")
    args = ap.parse_args()

    lane = Path(args.lane)
    if not lane.is_absolute():
        lane = REPO / lane

    if lane.exists():
        print("lane exists, removing:", lane)
        shutil.rmtree(lane)

    lane.mkdir(parents=True)

    shutil.copy2(SHARED / "Makefile", lane / "Makefile")
    shutil.copytree(SHARED / "src", lane / "src")
    shutil.copytree(SHARED / "game", lane / "game")
    shutil.copytree(SHARED / "graphics", lane / "graphics")
    # audio is not touched by this stream: a link is enough.
    try:
        (lane / "audio").symlink_to(SHARED / "audio", target_is_directory=True)
    except OSError:
        shutil.copytree(SHARED / "audio", lane / "audio")

    files = sum(1 for p in (lane / "graphics").rglob("*") if p.is_file())
    print("lane:", lane)
    print("graphics files:", files)
    print("src:", [p.name for p in (lane / "src").iterdir()])
    print("is symlink:", (lane / "graphics").is_symlink())


if __name__ == "__main__":
    main()
