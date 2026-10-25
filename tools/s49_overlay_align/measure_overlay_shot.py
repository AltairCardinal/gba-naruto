#!/usr/bin/env python3
"""Measure the overlay geometry in an original-game screenshot.

The original's overlay (BG2) paints with its own 16-colour bank-12 palette.
This script classifies the screenshot's pixels against that palette and
reports, per palette role, the bounding box and the 16x16 logical-cell
footprint it occupies on screen.
"""

from __future__ import annotations

import argparse
import pathlib
from collections import defaultdict

from PIL import Image

# bank 12 of the original's overlay (from bg2-palette.json)
PALETTE = {
    (0, 0, 0): "blank",
    (66, 107, 140): "edge",
    (24, 206, 255): "hatch",
    (8, 107, 173): "hatch_secondary",
    (255, 57, 0): "line_alt",
    (165, 41, 0): "line_alt_secondary",
    (255, 189, 0): "band",
    (148, 107, 0): "band_secondary",
    (173, 255, 0): "hatch_shift",
    (82, 132, 0): "hatch_shift_secondary",
    (74, 74, 74): "solid",
    (33, 33, 33): "solid_secondary",
}

FAMILY = {
    "edge": "edge",
    "hatch": "hatch",
    "hatch_secondary": "hatch",
    "line_alt": "line_alt",
    "line_alt_secondary": "line_alt",
    "band": "band",
    "band_secondary": "band",
    "hatch_shift": "hatch_shift",
    "hatch_shift_secondary": "hatch_shift",
    "solid": "solid",
    "solid_secondary": "solid",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", type=pathlib.Path)
    ap.add_argument("--cell", type=int, default=16)
    args = ap.parse_args()

    image = Image.open(args.image).convert("RGB")
    width, height = image.size
    pixels = image.load()
    hits: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for y in range(height):
        for x in range(width):
            role = PALETTE.get(pixels[x, y])
            if role:
                hits[role].append((x, y))

    print(f"{args.image}: {width}x{height}")
    for role in sorted(hits):
        points = hits[role]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        cells = {(p[0] // args.cell, p[1] // args.cell) for p in points}
        print(f"  {role:<20} px={len(points):>6}  "
              f"bbox=({min(xs)},{min(ys)})-({max(xs)},{max(ys)})  "
              f"{args.cell}px cells={len(cells)}")

    # the cyan (move range) footprint, per 16 px cell
    cyan = hits.get("hatch", []) + hits.get("hatch_secondary", [])
    if cyan:
        cells = sorted({(p[0] // args.cell, p[1] // args.cell) for p in cyan})
        print(f"\n  hatch cells ({args.cell}px grid), screen space:")
        min_y = min(c[1] for c in cells)
        max_y = max(c[1] for c in cells)
        min_x = min(c[0] for c in cells)
        max_x = max(c[0] for c in cells)
        for cy in range(min_y, max_y + 1):
            row = "".join(
                "X" if (cx, cy) in set(cells) else "." for cx in range(min_x, max_x + 1))
            print(f"    y{cy:>3} x{min_x:>3}..{max_x:<3} {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
