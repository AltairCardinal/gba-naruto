"""Scratch: stack the dialogue band of a frame range into one strip.

Usage: python scratch_stack.py <src-dir> <first> <last> <out.png> [band-top] [band-bottom]
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    first = int(sys.argv[2])
    last = int(sys.argv[3])
    out = pathlib.Path(sys.argv[4])
    top = int(sys.argv[5]) if len(sys.argv) > 5 else 96
    bottom = int(sys.argv[6]) if len(sys.argv) > 6 else 160
    strips = []
    for index in range(first, last + 1):
        png = src / f"step-{index:04d}-in.png"
        if not png.exists():
            png = src / f"step-{index:04d}-beat.png"
        if not png.exists():
            png = src / f"step-{index:04d}-base.png"
        if not png.exists():
            continue
        with Image.open(png) as image:
            strip = image.convert("RGB").crop((0, top, 240, bottom))
        strips.append((index, strip))
    if not strips:
        print("no frames")
        return 1
    width = 240
    height = strips[0][1].height
    sheet = Image.new("RGB", (width, height * len(strips)), (255, 0, 255))
    for row, (index, strip) in enumerate(strips):
        sheet.paste(strip, (0, row * height))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"{out} frames={len(strips)} first={strips[0][0]} last={strips[-1][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
