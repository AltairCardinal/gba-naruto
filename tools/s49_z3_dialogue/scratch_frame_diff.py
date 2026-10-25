"""Scratch: what changes between two captures of the original walk."""
from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageChops


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    first = int(sys.argv[2])
    last = int(sys.argv[3])
    width = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    base = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    previous = None
    for index in range(first, last + 1):
        png = None
        for suffix in ("in", "beat", "base"):
            candidate = src / f"step-{index:0{width}d}-{suffix}.png"
            if candidate.exists():
                png = candidate
                break
        if png is None:
            continue
        with Image.open(png) as handle:
            image = handle.convert("RGB")
        if previous is None:
            previous = image
            print(f"{index:04d} (first)")
            continue
        delta = ImageChops.difference(previous, image)
        red, green, blue = delta.split()
        mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        pixels = mask.load()
        rows = {}
        for y in range(image.height):
            for x in range(image.width):
                if pixels[x, y]:
                    key = y // 8
                    entry = rows.setdefault(key, [y * 8, y * 8 + 7, x, x, 0])
                    entry[0] = min(entry[0], y)
                    entry[1] = max(entry[1], y)
                    entry[2] = min(entry[2], x)
                    entry[3] = max(entry[3], x)
                    entry[4] += 1
        parts = [f"y{a}-{b} x{c}..{d} ({n}px)"
                 for a, b, c, d, n in sorted(rows.values())]
        print(f"{index:04d} changed={sum(entry[4] for entry in rows.values()):5d} "
              + " ".join(parts))
        previous = image
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
