"""Generate the measured dialogue box reveal cut table.

The table is the data the ``battle_presentation_box_opening`` model encodes:
for every step of the original's dialogue box reveal, where the black shard
that still covers the dialogue box starts and ends, at the top, the middle
and the bottom row of the dialogue box interior (rows 103, 127 and 152).

    python tools/s49_z3_dialogue/make_cut_table.py \
        build/s49-pairing/walk5/dense-original 0276 259 274
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

BOX_TOP = 103
BOX_MIDDLE = 127
BOX_BOTTOM = 152
WIDTH = 240


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def cuts(pixels, settled, y):
    """(left cut, right cut) of the black mask on one row.

    ``left cut`` is the last column of the mask run that touches the left
    edge (239 when the whole row is covered, -1 when there is no such run),
    ``right cut`` is the first column of the mask run that touches the right
    edge (0 when the whole row is covered, 240 when there is no such run).
    """
    cells = {x for x in range(WIDTH)
             if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24}
    if not cells:
        return -1, WIDTH
    left = -1
    if cells:
        lowest = min(cells)
        run = lowest
        for x in range(lowest, WIDTH):
            if x in cells:
                run = x
            else:
                break
        left = run
    right = WIDTH
    if cells:
        highest = max(cells)
        run = highest
        for x in range(highest, -1, -1):
            if x not in cells:
                run = x + 1
                break
        right = run
    return left, right


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    settled_index = int(sys.argv[2])
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    last = int(sys.argv[5]) if len(sys.argv) > 5 else 100
    settled = load(src, settled_index, width).load()
    print("    {")
    for index in range(first, last + 1):
        image = load(src, index, width)
        if image is None:
            break
        pixels = image.load()
        top = cuts(pixels, settled, BOX_TOP)
        middle = cuts(pixels, settled, BOX_MIDDLE)
        bottom = cuts(pixels, settled, BOX_BOTTOM)
        print(f"    {{ {index:4d}, {top[0]:4d}, {top[1]:4d}, "
              f"{middle[0]:4d}, {middle[1]:4d}, "
              f"{bottom[0]:4d}, {bottom[1]:4d} }},")
    print("    };")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
