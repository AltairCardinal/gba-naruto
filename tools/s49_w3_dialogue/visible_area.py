"""W3: the visible area of the original's entry transition, per capture.

The visible area is the number of pixels that are not black on screen.  It is
the quantity the black field's star model has to reproduce (Z2 measured it
per level and stored it in battle_black_field_star::visible_pixels).

This probe compares the measured areas against that table so the extra
levels the original has after the star's own fade-in become visible.
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

BLACK_LEVEL = 24


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--first", type=int, default=250)
    parser.add_argument("--last", type=int, default=280)
    parser.add_argument("--width", type=int, default=4)
    args = parser.parse_args()

    src = pathlib.Path(args.src)
    for index in range(args.first, args.last + 1):
        image = load(src, index, args.width)
        if image is None:
            break
        pixels = image.load()
        visible = 0
        for y in range(160):
            for x in range(240):
                if max(pixels[x, y]) >= BLACK_LEVEL:
                    visible += 1
        print(f"capture {index:04d} visible={visible:6d} "
              f"({visible * 100 // (240 * 160):3d}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
