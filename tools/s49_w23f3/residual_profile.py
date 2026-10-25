#!/usr/bin/env python3
"""Row/column profile of the residual, plus colour census of the *differing*
pixels only (which is what actually has to be explained)."""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import load_rgb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("original")
    parser.add_argument("remake")
    parser.add_argument("--top", type=int, default=14)
    parser.add_argument("--field", type=int, default=128)
    args = parser.parse_args()

    a = load_rgb(args.original)
    b = load_rgb(args.remake)
    apx, bpx = a.load(), b.load()
    width, height = a.size

    rows = Counter()
    cols = Counter()
    pairs = Counter()
    total = 0
    for y in range(args.field):
        for x in range(width):
            ca, cb = apx[x, y], bpx[x, y]
            if ca != cb:
                total += 1
                rows[y] += 1
                cols[x] += 1
                pairs[(ca, cb)] += 1
    print(f"differing pixels in field (240x{args.field}) = {total}")
    print(f"\nrow profile (non-zero rows, 8-px buckets):")
    for y in range(0, args.field, 8):
        n = sum(rows.get(yy, 0) for yy in range(y, y + 8))
        bar = "#" * (n // 40)
        print(f"  y {y:>3}-{y+7:>3}: {n:>5} {bar}")
    print(f"\ncolumn profile (8-px buckets):")
    for x in range(0, width, 8):
        n = sum(cols.get(xx, 0) for xx in range(x, x + 8))
        bar = "#" * (n // 40)
        print(f"  x {x:>3}-{x+7:>3}: {n:>5} {bar}")

    print(f"\ntop differing colour pairs (original -> remake):")
    for (ca, cb), n in pairs.most_common(args.top):
        print(f"  {str(ca):>18} -> {str(cb):>18}   x{n}")

    print(f"\ncolour census of the ORIGINAL frame (top {args.top}):")
    ca = Counter(a.getdata())
    for colour, n in ca.most_common(args.top):
        print(f"  {str(colour):>18}   x{n}")

    # bounding boxes of the distinctive colours
    print("\nbounding boxes of distinctive colours in the ORIGINAL:")
    for colour in [(231, 247, 214), (255, 0, 0), (0, 0, 0)]:
        pts = [(x, y) for y in range(height) for x in range(width)
               if apx[x, y] == colour]
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            print(f"  {colour}: n={len(pts)} bbox=({min(xs)},{min(ys)})-({max(xs)},{max(ys)})")
        else:
            print(f"  {colour}: n=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
