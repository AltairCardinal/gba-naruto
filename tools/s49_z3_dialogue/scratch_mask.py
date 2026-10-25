"""Scratch: the geometry of the original's black reveal mask.

The mask of a capture is the set of pixels that are black on screen but not
black in the settled capture: the scene underneath is already complete, the
mask is what is being carved away.  For every capture it prints, per row, the
first and last x that the mask covers.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image


def load(src: pathlib.Path, index: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:04d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    settled_index = int(sys.argv[2])
    first = int(sys.argv[3])
    last = int(sys.argv[4])
    settled = load(src, settled_index).load()
    for index in range(first, last + 1):
        image = load(src, index)
        if image is None:
            continue
        pixels = image.load()
        rows = []
        for y in range(image.height):
            covered = [x for x in range(image.width)
                       if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24]
            if covered:
                rows.append((y, covered[0], covered[-1], len(covered)))
        if not rows:
            print(f"{index:04d} mask=empty")
            continue
        sample = " ".join(f"{y}:{a}-{b}" for y, a, b, _ in rows[::12])
        print(f"{index:04d} mask_rows={len(rows):3d} "
              f"total={sum(count for _, _, _, count in rows):6d} {sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
