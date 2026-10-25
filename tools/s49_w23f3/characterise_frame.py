#!/usr/bin/env python3
"""Characterise a frame pair: brightness, colour census, coarse ASCII map."""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import load_rgb  # noqa: E402

CHARS = " .:-=+*#%@"


def ascii_map(image: Image.Image, cols: int = 60, rows: int = 30) -> str:
    width, height = image.size
    out = []
    for ry in range(rows):
        y0 = ry * height // rows
        y1 = max(y0 + 1, (ry + 1) * height // rows)
        line = []
        for rx in range(cols):
            x0 = rx * width // cols
            x1 = max(x0 + 1, (rx + 1) * width // cols)
            total = 0
            count = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    r, g, b = image.getpixel((x, y))
                    total += (r * 30 + g * 59 + b * 11) // 100
                    count += 1
            line.append(CHARS[min(len(CHARS) - 1, total * len(CHARS) // 256)])
        out.append("".join(line))
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    ia = load_rgb(args.a)
    ib = load_rgb(args.b)
    for tag, image in (("A", ia), ("B", ib)):
        counts = Counter(image.getdata())
        bright = sum(1 for c in counts for _ in ())  # placeholder
        px = image.load()
        lum = [sum(px[x, y]) / 3 for y in range(image.size[1])
               for x in range(image.size[0])]
        print(f"--- {tag} {args.a if tag=='A' else args.b}  size={image.size}")
        print(f"    mean lum = {sum(lum)/len(lum):.1f}   min={min(lum):.0f} "
              f"max={max(lum):.0f}   unique colours = {len(counts)}")
        for colour, n in counts.most_common(args.top):
            print(f"      {colour}  x{n}")
    print()
    print("=== A ===")
    print(ascii_map(ia))
    print()
    print("=== B ===")
    print(ascii_map(ib))
    return 0


if __name__ == "__main__":
    sys.exit(main())
