#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dump a screen region of two frames side by side as ASCII art.

Colour legend (GBA-15 RGB5 space, the palette the game actually uses):

    .  transparent / identical
    R  pure red      (255,0,0)
    B  marker blue   (0,107,189)
    G  grey         (57,57,57)
    K  black        (0,0,0)
    W  white        (255,255,255)
    o  olive        (173,173,49)
    g  grass green  (132,189,49)
    d  dark green   (41,66,0)
    t  teal         (0,41,41)
    T  dark teal    (0,8,8)
    ?  anything else (uppercase hex of the colour in the right column)

Usage:
    python tools/s49_w25h1/region_dump.py --original <dir> --remake <dir> \
        --orig-step step-03-A --remake-step step-07-A --box 100 20 145 50
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

KNOWN = {
    (255, 0, 0): "R",
    (0, 107, 189): "B",
    (57, 57, 57): "G",
    (0, 0, 0): "K",
    (255, 255, 255): "W",
    (173, 173, 49): "o",
    (132, 189, 49): "g",
    (41, 66, 0): "d",
    (0, 41, 41): "t",
    (0, 8, 8): "T",
    (99, 90, 57): "m",
    (181, 115, 24): "O",
    (255, 222, 148): "o",
    (33, 33, 33): "#",
    (107, 57, 90): "p",
    (115, 181, 231): "c",
    (82, 140, 173): "C",
    (198, 198, 66): "v",
    (156, 231, 66): "n",
}


def sym(color, other=None):
    if color in KNOWN:
        return KNOWN[color]
    return "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--orig-step", required=True)
    ap.add_argument("--remake-step", required=True)
    ap.add_argument("--box", nargs=4, type=int, required=True)
    args = ap.parse_args()
    x0, y0, x1, y1 = args.box
    a = Image.open(Path(args.original) / f"{args.orig_step}.png").convert("RGB")
    b = Image.open(Path(args.remake) / f"{args.remake_step}.png").convert("RGB")
    pa, pb = a.load(), b.load()
    print(f"original {args.orig_step}   remake {args.remake_step}   box={args.box}")
    print(f"{'':>{len(str(x1))}} " + "".join(str(x % 10) for x in range(x0, x1 + 1)))
    print("     " + "-" * (x1 - x0 + 1))
    for y in range(y0, y1 + 1):
        row_a = "".join(sym(pa[x, y]) for x in range(x0, x1 + 1))
        row_b = "".join(sym(pb[x, y]) for x in range(x0, x1 + 1))
        flag = "" if row_a == row_b else "  <<"
        print(f"  {y:3d} {row_a}   |{row_b}{flag}")
    print()
    print("legend: R=red B=blue G=grey K=black W=white o=olive g=grass d=darkgreen")
    print("        t=teal T=darkteal m=khaki O=orange p=magenta c=cyan C=steel")
    print("        #=darkgrey v=palegreen n=brightgreen ?=other")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
