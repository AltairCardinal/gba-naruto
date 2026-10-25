"""The reveal segment's per frame residual on both sides.

For every capture of the segment it counts the pixels that differ from the
settled capture of the same side: that is the residual the dialogue box
reveal still carries on that frame.  The original settles at the capture
whose dialogue signature is the empty box (0.805); the remake settles at the
capture whose line is complete.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageChops


def load(src: pathlib.Path, index: int, width: int = 4):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def residual(src: pathlib.Path, index: int, settled, width: int = 4) -> int:
    image = load(src, index, width)
    if image is None:
        return -1
    delta = ImageChops.difference(image, settled)
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(mask.histogram()[1:])


def main() -> int:
    root = pathlib.Path(sys.argv[1])
    original = root / "walk5" / "dense-original"
    remake = root / "walk5" / "dense-remake"
    original_settled = load(original, 276)
    remake_settled = load(remake, 333)
    print("original (settled 0276):")
    for index in range(255, 278):
        print(f"  {index:04d} residual={residual(original, index, original_settled):6d}")
    print("remake (settled 0333):")
    for index in range(318, 340):
        print(f"  {index:04d} residual={residual(remake, index, remake_settled):6d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
