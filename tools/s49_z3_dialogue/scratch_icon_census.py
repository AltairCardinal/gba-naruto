"""Scratch: census the advance icon region of a few original frames."""
from __future__ import annotations

import collections
import pathlib
import sys

from PIL import Image


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    for raw in sys.argv[2:]:
        index = int(raw)
        png = src / f"step-{index:04d}-in.png"
        if not png.exists():
            png = src / f"step-{index:04d}-beat.png"
        with Image.open(png) as handle:
            rgb = handle.convert("RGB")
        pixels = rgb.load()
        census = collections.Counter()
        for y in range(130, 160):
            for x in range(240):
                census[pixels[x, y]] += 1
        print(index, census.most_common(6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
