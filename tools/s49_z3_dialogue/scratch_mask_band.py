"""Scratch: the reveal mask inside the dialogue box band.

For every capture it prints, for a few rows of the dialogue band, the first
and last x the black mask still covers.  A clean diagonal wipe shows up as a
boundary whose x moves one pixel per row.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


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
        for y in (100, 104, 110, 120, 130, 140, 150, 155):
            covered = [x for x in range(240)
                       if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24]
            if covered:
                parts.append(f"y{y}:{covered[0]}-{covered[-1]}")
            else:
                parts.append(f"y{y}:-")
        print(f"{index:04d} " + " ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
