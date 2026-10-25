#!/usr/bin/env python3
"""2-D shift probe: how well does remake frame B fit original frame A after a
translation of B?  Used to separate "camera is elsewhere" from "camera is the
same but the pixels are different"."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import load_rgb  # noqa: E402


def probe(a_path, b_path, box, max_dx=48, max_dy=24, step=1):
    a = load_rgb(a_path)
    b = load_rgb(b_path)
    apx, bpx = a.load(), b.load()
    x0, y0, x1, y1 = box
    width, height = a.size
    rows = []
    for dy in range(-max_dy, max_dy + 1, step):
        for dx in range(-max_dx, max_dx + 1, step):
            total = 0
            for y in range(y0, y1):
                sy = y + dy
                if sy < 0 or sy >= height:
                    total += (x1 - x0)
                    continue
                for x in range(x0, x1):
                    sx = x + dx
                    if sx < 0 or sx >= width:
                        total += 1
                        continue
                    if apx[x, y] != bpx[sx, sy]:
                        total += 1
            rows.append((total, dx, dy))
    rows.sort()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--box", default="0,0,240,128")
    parser.add_argument("--max-dx", type=int, default=48)
    parser.add_argument("--max-dy", type=int, default=24)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    box = tuple(int(v) for v in args.box.split(","))
    rows = probe(args.a, args.b, box, args.max_dx, args.max_dy)
    print(f"box={box}  best 8 shifts:")
    for total, dx, dy in rows[:args.top]:
        print(f"  dx={dx:+4d} dy={dy:+4d}   {total:>7} px")
    print(f"  (unshifted baseline would be at dx=0 dy=0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
