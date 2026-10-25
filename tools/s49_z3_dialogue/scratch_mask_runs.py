"""Scratch: the reveal mask of the dialogue band as compact segments.

For every capture it prints the black mask inside the dialogue band as a
list of ``row -> covered x range`` runs, so the reveal can be encoded as a
small table.
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
        parts = []
        for y in range(BAND_TOP, BAND_BOTTOM):
            covered = [x for x in range(240)
                       if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24]
            if not covered:
                continue
            for low, high in runs(covered):
                parts.append(f"({y},{low},{high})")
        print(f"{index:04d} f={base + index:5d} n={len(parts):3d} "
              + " ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
