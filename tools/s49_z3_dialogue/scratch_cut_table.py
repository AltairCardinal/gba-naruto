"""Scratch: the reveal mask of the dialogue box interior as a cut table.

The dialogue box interior of the original is rows 103..152.  For every
capture it reports, for the top and the bottom row of that interior, where
the black mask ends on the left side and where it starts on the right side.
Those four numbers are what a renderer needs to cut the box open with a
diagonal edge.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

BOX_TOP = 103
BOX_BOTTOM = 152


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def row_mask(pixels, settled, y):
    return [x for x in range(240)
            if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24]


def side(cells):
    """(left end, right start) of the mask row, or None."""
    if not cells:
        return None
    left = None
    for x in range(0, 240):
        if x in cells:
            left = x
            break
    right = None
    for x in range(239, -1, -1):
        if x in cells:
            right = x
            break
    left_end = -1
    if left is not None and left <= 3:
        run = 0
        for x in range(240):
            if x in cells:
                run = x
            else:
                break
        left_end = run
    right_start = 240
    if right is not None and right >= 236:
        run = 239
        for x in range(239, -1, -1):
            if x not in cells:
                run = x + 1
                break
        right_start = run
    return left_end, right_start


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    settled_index = int(sys.argv[2])
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    base = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    first = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    last = int(sys.argv[6]) if len(sys.argv) > 6 else 100
    settled = load(src, settled_index, width).load()
    for index in range(first, last + 1):
        image = load(src, index, width)
        if image is None:
            break
        pixels = image.load()
        top = side(row_mask(pixels, settled, BOX_TOP))
        bottom = side(row_mask(pixels, settled, BOX_BOTTOM))
        middle = side(row_mask(pixels, settled, (BOX_TOP + BOX_BOTTOM) // 2))
        print(f"{index:04d} f={base + index:5d} "
              f"top={top} mid={middle} bottom={bottom}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
