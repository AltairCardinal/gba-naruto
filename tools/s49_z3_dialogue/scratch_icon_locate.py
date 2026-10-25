"""Scratch: locate the advance icon: which colour, which rows, which frames."""
from __future__ import annotations

import collections
import pathlib
import sys

from PIL import Image


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    first = int(sys.argv[2])
    last = int(sys.argv[3])
    for index in range(first, last + 1):
        png = src / f"step-{index:04d}-in.png"
        if not png.exists():
            png = src / f"step-{index:04d}-beat.png"
        if not png.exists():
            continue
        with Image.open(png) as handle:
            rgb = handle.convert("RGB")
        pixels = rgb.load()
        counts = collections.Counter()
        for y in range(136, 160):
            for x in range(180, 240):
                counts[pixels[x, y]] += 1
        dark = sum(count for color, count in counts.items()
                   if max(color) < 160)
        print(f"{index:04d} dark={dark:4d} "
              + " ".join(f"{color}x{count}"
                         for color, count in counts.most_common(4)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
