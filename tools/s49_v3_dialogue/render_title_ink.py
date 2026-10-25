"""Scratch: render the original's title ink as ASCII art.

Answers one question: what exactly does the original's 「開始」 title look
like, and how far does its ink reach?

Only the darkest grey (the brush stroke) is drawn, so the background cannot
contribute.  The output is the region of the screen the title covers.

Usage:
    python tools/s49_v3_dialogue/render_title_ink.py <original-frames-dir>
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

STROKE = (33, 33, 33)
REGION = (30, 20, 235, 135)


def main() -> int:
    directory = pathlib.Path(sys.argv[1])
    best = None
    for path in sorted(directory.glob("*.png")):
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            pixels = list(rgb.getdata())
        hits = sum(1 for pixel in pixels if pixel == STROKE)
        if best is None or hits > best[0]:
            best = (hits, path, rgb)
    if best is None:
        print("no stroke found")
        return 1
    hits, path, rgb = best
    print(f"frame: {path.name}  stroke pixels: {hits}")
    crop = rgb.crop(REGION)
    width, height = crop.size
    pixels = list(crop.getdata())
    for y in range(height):
        row = "".join(
            "#" if pixels[y * width + x] == STROKE else "." for x in range(width))
        if "#" in row:
            print(f"{REGION[1] + y:>3} {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
