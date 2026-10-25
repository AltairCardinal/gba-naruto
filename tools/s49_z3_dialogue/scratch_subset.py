"""Scratch: are the reveal frames a subset of the settled scene?

For every capture it counts the pixels that differ from the settled capture
and reports how many of the differing pixels are *black* in the settled
capture.  A pure black overlay makes the reveal a strict subset of the
settled scene: every non black settled pixel must already be on screen.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageChops


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
    settled = load(src, settled_index)
    settled_pixels = settled.load()
    for index in range(first, last + 1):
        image = load(src, index)
        if image is None:
            continue
        pixels = image.load()
        differ = 0
        differ_black = 0
        differ_other = 0
        missing = 0
        for y in range(image.height):
            for x in range(image.width):
                if pixels[x, y] != settled_pixels[x, y]:
                    differ += 1
                    if max(settled_pixels[x, y]) < 24:
                        differ_black += 1
                    else:
                        differ_other += 1
                elif max(settled_pixels[x, y]) < 24:
                    missing += 1
        print(f"{index:04d} differ={differ:6d} differ_black={differ_black:6d} "
              f"differ_other={differ_other:6d} settled_black_hidden={missing:6d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
