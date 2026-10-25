#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Attribute the field-area residual of the S49 intro frames to regions.

For every (original, remake) pair it computes the field residual with a set of
candidate regions "explained away": inside a masked rectangle the original's
pixels are assumed to be reproduced by the remake, so those pixels no longer
count.  The difference between the raw residual and the masked residual is the
cost of that cause.

Usage:
    python tools/s49_w25h1/attribute_regions.py --original <dir> --remake <dir>
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

FIELD = (0, 0, 240, 128)

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

REGIONS = {
    # the remake-only deployment header widgets
    "deploy_hdr": (0, 0, 80, 16),
    "unit_line": (0, 16, 45, 26),
    "this_player": (0, 116, 100, 128),
    # the two map markers
    "marker_left": (108, 25, 128, 36),
    "marker_right": (128, 34, 140, 45),
    # the big unit sprites
    "konohamaru": (100, 42, 140, 92),
    "unit_right": (200, 12, 234, 70),
    "unit_left": (2, 14, 48, 92),
}


def diff_map(a: Image.Image, b: Image.Image):
    pa, pb = a.load(), b.load()
    x0, y0, x1, y1 = FIELD
    s = set()
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pa[x, y] != pb[x, y]:
                s.add((x, y))
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--remake", required=True)
    args = ap.parse_args()
    od = Path(args.original)
    rd = Path(args.remake)

    names = list(REGIONS)
    totals = {n: 0 for n in names}
    grand = 0
    print(
        f"{'pair':<28}{'total':>7}" + "".join(f"{n:>13}" for n in names)
    )
    for o, r in PAIRS:
        a = Image.open(od / f"{o}.png").convert("RGB")
        b = Image.open(rd / f"{r}.png").convert("RGB")
        dm = diff_map(a, b)
        grand += len(dm)
        cells = []
        for n in names:
            x0, y0, x1, y1 = REGIONS[n]
            inside = sum(
                1 for x, y in dm if x0 <= x <= x1 and y0 <= y <= y1
            )
            totals[n] += inside
            cells.append(f"{inside:>13}")
        print(f"{o + ' vs ' + r:<28}{len(dm):>7}" + "".join(cells))
    print(f"{'TOTAL':<28}{grand:>7}" + "".join(f"{totals[n]:>13}" for n in names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
