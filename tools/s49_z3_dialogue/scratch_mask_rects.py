"""Scratch: the reveal mask of the dialogue band as merged rectangles.

The mask of a capture is the set of pixels that are black on screen but not
black in the settled capture.  The runs of a row are merged vertically into
rectangles, which is the shape a renderer can draw as black boxes over the
dialogue box.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

BAND_TOP = 96
BAND_BOTTOM = 160


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def runs(values):
    out = []
    for value in values:
        if out and out[-1][1] == value - 1:
            out[-1][1] = value
        else:
            out.append([value, value])
    return out


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
        row_runs = []
        for y in range(BAND_TOP, BAND_BOTTOM):
            covered = [x for x in range(240)
                       if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24]
            row_runs.append(runs(covered))
        # Merge the runs vertically: a rectangle survives while the next row
        # has a run with the same left and right.
        rectangles = []
        for y, row in enumerate(row_runs):
            for low, high in row:
                for rectangle in rectangles:
                    if (rectangle[1] == y - 1 and rectangle[2] == low
                            and rectangle[3] == high):
                        rectangle[1] = y
                        break
                else:
                    rectangles.append([y, y, low, high])
        parts = [f"({a},{b},{c},{d})" for a, b, c, d in rectangles]
        print(f"{index:04d} f={base + index:5d} n={len(rectangles):3d} "
              + " ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
