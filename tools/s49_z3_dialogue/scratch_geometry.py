"""Scratch: per-frame geometry of the dialogue paper region.

Reports, for each frame, the pixel counts of the key colours and the
per-column top edge of the "paper" (dialogue box interior) region.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image


def classify(pixel):
    red, green, blue = pixel
    if red < 16 and green < 16 and blue < 16:
        return "black"
    if red > 200 and green > 200 and blue > 180:
        return "paper"
    return "other"


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    first = int(sys.argv[2])
    last = int(sys.argv[3])
    for index in range(first, last + 1):
        png = src / f"step-{index:04d}-in.png"
        if not png.exists():
            png = src / f"step-{index:04d}-beat.png"
        if not png.exists():
            png = src / f"step-{index:04d}-base.png"
        if not png.exists():
            continue
        with Image.open(png) as image:
            rgb = image.convert("RGB")
        width, height = rgb.size
        pixels = rgb.load()
        counts = {"black": 0, "paper": 0, "other": 0}
        columns = []
        top = None
        bottom = None
        for y in range(height):
            for x in range(width):
                kind = classify(pixels[x, y])
                counts[kind] += 1
                if kind == "paper":
                    if top is None or y < top:
                        top = y
                    if bottom is None or y > bottom:
                        bottom = y
        print(f"{index:04d} black={counts['black']:5d} paper={counts['paper']:5d} "
              f"other={counts['other']:5d} paper_y={top}..{bottom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
