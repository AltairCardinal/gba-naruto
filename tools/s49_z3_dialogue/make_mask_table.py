"""Generate the measured dialogue box reveal mask table.

The table is the data the ``battle_presentation_box_opening`` model encodes:
for every step of the original's dialogue box reveal, the black mask that
still covers the dialogue box, sampled at the top, the middle and the bottom
row of the dialogue box interior (rows 103, 127 and 152).

Each row is four bytes: the first mask run's start and end column and the
second mask run's start and end column.  ``end < start`` means the row has
no second run.

    python tools/s49_z3_dialogue/make_mask_table.py \
        build/s49-pairing/walk5/dense-original 0276 259 274
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

ROWS = (103, 127, 152)
WIDTH = 240


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def runs_of(cells):
    out = []
    for value in sorted(cells):
        if out and out[-1][1] == value - 1:
            out[-1][1] = value
        else:
            out.append([value, value])
    return out


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    settled_index = int(sys.argv[2])
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    last = int(sys.argv[5]) if len(sys.argv) > 5 else 100
    settled = load(src, settled_index, width).load()
    for index in range(first, last + 1):
        image = load(src, index, width)
        if image is None:
            break
        pixels = image.load()
        for y in ROWS:
            cells = {x for x in range(WIDTH)
                     if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24}
            runs = runs_of(cells)
            first_run = runs[0] if runs else (240, 0)
            second_run = runs[1] if len(runs) > 1 else (240, 0)
            print(f"    {{ {first_run[0]:3d}, {first_run[1]:3d}, "
                  f"{second_run[0]:3d}, {second_run[1]:3d} }},"
                  f"  // capture {index} row {y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
