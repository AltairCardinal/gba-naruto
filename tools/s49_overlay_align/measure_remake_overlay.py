#!/usr/bin/env python3
"""Locate the remake's battle overlay layer inside its captured frames.

The remake paints the overlay with the original's bank-12 palette, so the
overlay's own colours (slate lattice 66/107/140, cyan 226-ish, orange, yellow)
identify the overlay pixels.  This script reports, per frame, how many overlay
pixels there are and where the 1 px lattice lines sit -- the lattice spacing
gives the battle cell size and the line positions give the overlay's screen
anchor.
"""

from __future__ import annotations

import argparse
import pathlib
from collections import Counter

from PIL import Image

# the original's bank-12 colours, as the remake renders them (8 bit)
EDGE = (66, 107, 140)
MOVE = (24, 206, 255)
ATTACK = (255, 57, 0)
CURSOR = (255, 189, 0)
TARGET = (173, 255, 0)
BLOCKED = (74, 74, 74)


def classify(pixel):
    r, g, b = pixel
    if abs(r - EDGE[0]) <= 6 and abs(g - EDGE[1]) <= 6 and abs(b - EDGE[2]) <= 6:
        return "edge"
    if abs(r - MOVE[0]) <= 8 and abs(g - MOVE[1]) <= 8 and abs(b - MOVE[2]) <= 8:
        return "move"
    if r > 200 and 30 < g < 110 and b < 60:
        return "attack"
    if r > 200 and 150 < g < 220 and b < 80:
        return "cursor"
    if g > 200 and r > 120 and b < 80:
        return "target"
    if abs(r - BLOCKED[0]) <= 6 and abs(g - BLOCKED[1]) <= 6 and abs(b - BLOCKED[2]) <= 6:
        return "blocked"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("frames", nargs="+", type=pathlib.Path)
    args = ap.parse_args()

    for path in args.frames:
        image = Image.open(path).convert("RGB")
        pixels = image.load()
        width, height = image.size
        hits = Counter()
        edge_x = Counter()
        edge_y = Counter()
        for y in range(height):
            for x in range(width):
                role = classify(pixels[x, y])
                if role:
                    hits[role] += 1
                    if role == "edge":
                        edge_x[x] += 1
                        edge_y[y] += 1
        if not hits:
            print(f"{path.name}: no overlay pixels")
            continue
        print(f"{path.name}: {dict(hits)}")
        columns = sorted(x for x, n in edge_x.items() if n >= 8)
        rows = sorted(y for y, n in edge_y.items() if n >= 8)
        print(f"   lattice columns (>=8 px tall): {columns}")
        print(f"   lattice rows    (>=8 px wide): {rows}")
        if len(columns) > 1:
            print(f"   column spacing: "
                  f"{[columns[i + 1] - columns[i] for i in range(len(columns) - 1)]}")
        if len(rows) > 1:
            print(f"   row spacing:    "
                  f"{[rows[i + 1] - rows[i] for i in range(len(rows) - 1)]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
