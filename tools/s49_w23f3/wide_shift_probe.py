#!/usr/bin/env python3
"""Wide shift probe (PIL only): is the remake's frame just the original's frame
seen from a different camera, or a different scene altogether?"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import load_rgb  # noqa: E402


def count_diff(a: Image.Image, patch: Image.Image) -> int:
    diff = ImageChops.difference(a, patch)
    r, g, b = diff.split()
    merged = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return sum(merged.histogram()[1:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--box", default="0,0,240,128")
    parser.add_argument("--max-dx", type=int, default=240)
    parser.add_argument("--max-dy", type=int, default=120)
    args = parser.parse_args()
    x0, y0, x1, y1 = (int(v) for v in args.box.split(","))
    a = load_rgb(args.a).crop((x0, y0, x1, y1))
    b = load_rgb(args.b)
    area = (x1 - x0) * (y1 - y0)
    best = []
    for dy in range(-args.max_dy, args.max_dy + 1):
        sy0, sy1 = y0 + dy, y1 + dy
        if sy0 < 0 or sy1 > b.size[1]:
            continue
        for dx in range(-args.max_dx, args.max_dx + 1):
            sx0, sx1 = x0 + dx, x1 + dx
            if sx0 < 0 or sx1 > b.size[0]:
                continue
            best.append((count_diff(a, b.crop((sx0, sy0, sx1, sy1))), dx, dy))
    best.sort()
    for total, dx, dy in best[:10]:
        print(f"  dx={dx:+5d} dy={dy:+5d}   {total:>7} px  ({100*total/area:5.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
