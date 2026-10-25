"""W3: measure the original's *full screen* dialogue reveal mask.

Z3 measured only the dialogue band (rows 96..160) because that is the part
the dialogue box owns.  The reveal is an entry transition: the black mask
covers the whole screen, including the forest, and it is carved away by
straight diagonal edges.

This probe answers one question per run:

    what does the full screen mask look like on every capture of the dense
    walk, and how many rectangles does it decompose into?

The mask of a capture is the set of pixels that are black on screen but not
black in the settled capture, exactly like Z3's scratch_mask_rects.py, only
over the whole 240x160 screen.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from PIL import Image

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
BLACK_LEVEL = 24


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def row_runs(pixels, settled, y):
    covered = [x for x in range(SCREEN_WIDTH)
               if max(pixels[x, y]) < BLACK_LEVEL
               and max(settled[x, y]) >= BLACK_LEVEL]
    runs = []
    for value in covered:
        if runs and runs[-1][1] == value - 1:
            runs[-1][1] = value
        else:
            runs.append([value, value])
    return runs


def merge_rectangles(rows):
    """Merge the per row runs into rectangles.

    A rectangle survives while the next row has a run with the same left and
    right edge.  The order of the rectangles is the order of their first
    pixel, so the list is stable and reproducible.
    """
    rectangles = []
    for y, row in enumerate(rows):
        for low, high in row:
            for rectangle in rectangles:
                if (rectangle[1] == y - 1 and rectangle[2] == low
                        and rectangle[3] == high):
                    rectangle[1] = y
                    break
            else:
                rectangles.append([y, y, low, high])
    return rectangles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--settled", type=int, default=276)
    parser.add_argument("--first", type=int, default=255)
    parser.add_argument("--last", type=int, default=275)
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    src = pathlib.Path(args.src)
    settled_image = load(src, args.settled, args.width)
    if settled_image is None:
        print("no settled capture", file=sys.stderr)
        return 1
    settled = settled_image.load()

    report = []
    for index in range(args.first, args.last + 1):
        image = load(src, index, args.width)
        if image is None:
            break
        pixels = image.load()
        rows = [row_runs(pixels, settled, y) for y in range(SCREEN_HEIGHT)]
        rectangles = merge_rectangles(rows)
        covered = sum(high - low + 1
                      for row in rows for low, high in row)
        entry = {
            "capture": index,
            "mask_pixels": covered,
            "mask_per_cent": covered * 100 // (SCREEN_WIDTH * SCREEN_HEIGHT),
            "rectangle_count": len(rectangles),
            "rectangles": rectangles,
        }
        report.append(entry)
        print(f"{index:04d} px={covered:6d} "
              f"({entry['mask_per_cent']:3d}%) rects={len(rectangles):3d} "
              f"runs/row={max((len(r) for r in rows), default=0)}")
        for y0, y1, x0, x1 in rectangles:
            print(f"      ({y0},{y1}) x[{x0}..{x1}] "
                  f"w={x1 - x0 + 1} h={y1 - y0 + 1}")

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
