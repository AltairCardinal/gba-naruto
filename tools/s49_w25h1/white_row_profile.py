#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Row profile of remake-only bright pixels inside the field area.

The remake draws several ASCII text widgets ("S DEPLOY", "UNIT", "THIS PLAYER",
"AOK BEAK").  Each one is pure white on black.  This tool lists, per paired
frame, the rows where the remake has white pixels that the original does not
have -- i.e. exactly the rows where the remake draws something the original
does not.

Usage:
    python tools/s49_w25h1/white_row_profile.py --original <dir> --remake <dir>
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

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

WHITE = (255, 255, 255)


def white_rows(path: Path):
    img = Image.open(path).convert("RGB")
    p = img.load()
    out = {}
    for y in range(0, 128):
        n = sum(1 for x in range(0, 240) if p[x, y] == WHITE)
        if n:
            out[y] = n
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    od = Path(args.original)
    rd = Path(args.remake)
    for o, r in PAIRS:
        ro = white_rows(od / f"{o}.png")
        rr = white_rows(rd / f"{r}.png")
        only_r = {y: v for y, v in rr.items() if y not in ro}
        only_o = {y: v for y, v in ro.items() if y not in rr}
        tot = sum(only_r.values())
        print(
            f"{o:>13} vs {r:<12} remake-only white = {tot:5d} px  "
            f"rows: "
            + ", ".join(f"y{y}={v}" for y, v in sorted(only_r.items()))[:200]
        )
        if only_o:
            print(
                f"{'':>13} {'':<12} original-only white = {sum(only_o.values()):5d} px  "
                + ", ".join(f"y{y}={v}" for y, v in sorted(only_o.items()))[:150]
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
