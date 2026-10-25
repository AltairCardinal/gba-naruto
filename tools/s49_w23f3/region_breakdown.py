#!/usr/bin/env python3
"""Sub-region breakdown of a frame pair's residual."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--regions", default="")
    args = parser.parse_args()
    a = load_rgb(args.a)
    b = load_rgb(args.b)
    if args.regions:
        regions = []
        for item in args.regions.split(";"):
            name, coords = item.split(":")
            regions.append((name, tuple(int(v) for v in coords.split(","))))
    else:
        regions = [
            ("top-strip  y0-8", (0, 0, 240, 8)),
            ("forest     y8-48", (0, 8, 240, 48)),
            ("grass      y48-95", (0, 48, 240, 95)),
            ("gap        y95-98", (0, 95, 240, 98)),
            ("box-top    y98-128", (0, 98, 240, 128)),
            ("field      y0-128", (0, 0, 240, 128)),
            ("below      y128-160", (0, 128, 240, 160)),
            ("full       y0-160", (0, 0, 240, 160)),
        ]
    total = 0
    for name, box in regions:
        count, _ = diff_mask(a, b, box)
        area = (box[2] - box[0]) * (box[3] - box[1])
        print(f"  {name:<20} {count:>7} / {area:>6} px  ({100*count/area:5.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
