"""Scratch: measure the ink extent of the recovered title art.

Answers one question: does the 「始」 art really need four sprite pieces, and
does each piece carry ink?

The art is the recovered PNG of the original's glyph.  The measure reports the
ink bounding box of each glyph and the ink per quadrant, so the pieces that
carry no ink at all are visible.

Usage:
    python tools/s49_v3_dialogue/measure_title_art.py [<art-dir>]
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ART = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    pathlib.Path(r"D:\Github\gba-naruto\tools\s49_opening_title")


def main() -> int:
    for name in ("kai", "shi"):
        path = ART / f"{name}.png"
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            width, height = rgba.size
            pixels = list(rgba.getdata())
        hits = [(index % width, index // width)
                for index, pixel in enumerate(pixels)
                if pixel[3] != 0]
        xs = [x for x, _ in hits]
        ys = [y for _, y in hits]
        print(f"{name}.png {width}x{height} ink={len(hits)}")
        if not hits:
            print("  no ink")
            continue
        print(f"  ink bbox: x {min(xs)}..{max(xs)}  y {min(ys)}..{max(ys)}")
        quadrants = {
            "top-left  64x64": (0, 0, 64, 64),
            "right   32x64": (64, 0, 96, 64),
            "bottom  64x32": (0, 64, 64, 96),
            "corner  32x32": (64, 64, 96, 96),
        }
        for label, (x0, y0, x1, y1) in quadrants.items():
            count = sum(1 for x, y in hits
                        if x0 <= x < x1 and y0 <= y < y1)
            print(f"  {label}: ink={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
