"""Scratch: exact-colour census of a frame region."""
from __future__ import annotations

import collections
import pathlib
import sys

from PIL import Image


def main() -> int:
    png = pathlib.Path(sys.argv[1])
    top = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    bottom = int(sys.argv[3]) if len(sys.argv) > 3 else 160
    left = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    right = int(sys.argv[5]) if len(sys.argv) > 5 else 240
    with Image.open(png) as image:
        rgb = image.convert("RGB")
    pixels = rgb.load()
    census = collections.Counter()
    for y in range(top, bottom):
        for x in range(left, right):
            census[pixels[x, y]] += 1
    for color, count in census.most_common(12):
        print(f"{color} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
