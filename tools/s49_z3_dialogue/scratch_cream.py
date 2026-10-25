"""Scratch: exact geometry of the dialogue box interior colour.

For each frame it prints the bounding box of the exact cream colour and the
per-column top / bottom edge of that colour, so the growth shape of the
dialogue box can be read off directly.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

CREAM = (231, 247, 214)


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
        pixels = rgb.load()
        width, height = rgb.size
        cols = {}
        for y in range(height):
            for x in range(width):
                if pixels[x, y] == CREAM:
                    lo, hi = cols.get(x, (y, y))
                    cols[x] = (min(lo, y), max(hi, y))
        if not cols:
            print(f"{index:04d} cream=0")
            continue
        xs = sorted(cols)
        top = min(lo for lo, _ in cols.values())
        bottom = max(hi for _, hi in cols.values())
        # The top edge sampled every 8 columns, as a compact shape read-out.
        edge = []
        for x in range(0, width, 8):
            if x in cols:
                edge.append(f"{x}:{cols[x][0]}-{cols[x][1]}")
            else:
                edge.append(f"{x}:--")
        print(f"{index:04d} n={len(cols):3d} x={xs[0]}..{xs[-1]} y={top}..{bottom}")
        print("      " + " ".join(edge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
