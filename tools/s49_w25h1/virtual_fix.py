#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offline "virtual fix" measurement for the S49 intro frames.

For a chosen set of regions the remake frame is patched with the *original's*
pixels inside those regions and the residual is recomputed.  That is the upper
bound of what a product fix for that cause can achieve: it assumes the remake
ends up drawing exactly what the original draws there.

This is NOT a product change -- it is a measurement that bounds the payoff of
the wiring proposals in notes/s49-fidelity/W25-H1-intro.md §4.

Usage:
    python tools/s49_w25h1/virtual_fix.py --original <dir> --remake <dir> \
        [--sets A,A+C,A+B+C]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

FIELD = (0, 0, 240, 128)
FULL = (0, 0, 240, 160)

PAIRS = [
    ("step-00-base", "step-24-A"),
    ("step-01-A", "step-05-A"),
    ("step-02-A", "step-06-A"),
    ("step-03-A", "step-07-A"),
    ("step-04-A", "step-08-A"),
    ("step-05-A", "step-09-A"),
    ("step-06-A", "step-10-A"),
    ("step-07-A", "step-11-A"),
    ("step-08-A", "step-12-A"),
    ("step-09-A", "step-13-A"),
    ("step-10-A", "step-14-A"),
    ("step-11-A", "step-22-A"),
]

# A: the remake-only deployment text overlay
A = [(0, 0, 80, 16), (0, 16, 45, 26), (0, 116, 100, 128)]
# B: the three unit sprite boxes
B = [(100, 42, 140, 92), (2, 14, 48, 92), (200, 12, 234, 70)]
# C: the two map markers
C = [(108, 25, 128, 36), (128, 34, 140, 45)]

SETS = {"A": A, "B": B, "C": C}


def residual(a: Image.Image, b: Image.Image, area) -> int:
    x0, y0, x1, y1 = area
    pa, pb = a.load(), b.load()
    n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pa[x, y] != pb[x, y]:
                n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--sets", default="A,C,A+C,A+B+C")
    args = ap.parse_args()
    od = Path(args.original)
    rd = Path(args.remake)

    combos = []
    for name in args.sets.split(","):
        name = name.strip()
        if not name:
            continue
        regions = []
        for part in name.split("+"):
            regions.extend(SETS[part])
        combos.append((name, regions))

    totals = {name: [0, 0] for name, _ in combos}
    base = [0, 0]
    print(f"{'pair':<28}{'base field':>11}" + "".join(f"{n:>12}" for n, _ in combos))
    for o, r in PAIRS:
        a = Image.open(od / f"{o}.png").convert("RGB")
        b0 = Image.open(rd / f"{r}.png").convert("RGB")
        bf = residual(a, b0, FIELD)
        base[0] += bf
        base[1] += residual(a, b0, FULL)
        cells = []
        for name, regions in combos:
            b = b0.copy()
            pb, pa = b.load(), a.load()
            for x0, y0, x1, y1 in regions:
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        pb[x, y] = pa[x, y]
            f = residual(a, b, FIELD)
            totals[name][0] += f
            totals[name][1] += residual(a, b, FULL)
            cells.append(f"{f:>12}")
        print(f"{o + ' vs ' + r:<28}{bf:>11}" + "".join(cells))
    print(
        f"{'TOTAL field':<28}{base[0]:>11}"
        + "".join(f"{totals[n][0]:>12}" for n, _ in combos)
    )
    print(
        f"{'TOTAL full':<28}{base[1]:>11}"
        + "".join(f"{totals[n][1]:>12}" for n, _ in combos)
    )
    print()
    for name, _ in combos:
        print(
            f"  fix {name:<6} field {base[0]} -> {totals[name][0]} "
            f"(-{base[0] - totals[name][0]})   "
            f"full {base[1]} -> {totals[name][1]} "
            f"(-{base[1] - totals[name][1]})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
