#!/usr/bin/env python3
"""Where does the original's overlay buffer sit in the map space?

Answers one question: for the original's 16x16 logical buffer, is there a
map-space labelling under which the original's ``solid`` cells are exactly
the map cells whose terrain class is not plain?

The candidates are (ox, oy) anchors with the map wrap (mod 480) applied or
not, and the terrain is decoded from the remake's generated map content with
the same rule the product uses (``raw & 15``).

Usage::

    python tools/s49_w2/anchor_solve.py --moment field-frame-v1
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from compare_overlay_families import remake_terrain, MAP_WIDTH, MAP_HEIGHT  # noqa: E402
from overlay_ground_truth import load_moment  # noqa: E402


def blocked_set(terrain):
    return {(bx, by)
            for by, row in enumerate(terrain)
            for bx, value in enumerate(row) if value != 0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--moment", default="field-frame-v1")
    args = ap.parse_args()

    terrain = remake_terrain()
    print(f"terrain {len(terrain[0])} x {len(terrain)} battle cells")
    for by, row in enumerate(terrain):
        print(f"  {by:>2}  " + " ".join(f"{v:>2}" for v in row))

    grid = load_moment(args.moment).logical_grid()
    solid = [(lx, ly) for ly in range(16) for lx in range(16)
             if grid[ly][lx] == "solid"]
    lit = [(lx, ly) for ly in range(16) for lx in range(16)
           if grid[ly][lx] != "blank"]
    print(f"\noriginal {args.moment}: {len(lit)} lit cells, {len(solid)} solid")

    blocked = blocked_set(terrain)
    # A battle cell is 32 px wide x 16 px tall = 2 logical columns x 1 row.
    # The original's buffer is a 16 x 16 *logical* cell grid.
    best = []
    for wrap in (False, True):
        for ox in range(0, MAP_WIDTH):
            for oy in range(0, MAP_HEIGHT, 16):
                on = 0
                off = 0
                for lx, ly in solid:
                    map_px = lx * 16 + ox
                    if wrap:
                        map_px %= MAP_WIDTH
                    bx = map_px // 32
                    by = ly + oy // 16
                    if bx >= len(terrain[0]) or by >= len(terrain):
                        off += 1
                        continue
                    if (bx, by) in blocked:
                        on += 1
                    else:
                        off += 1
                best.append((on, -off, ox, oy, wrap))
    best.sort(reverse=True)
    print("\ntop anchors (on_blocked, -off_blocked, ox, oy, wrap):")
    for row in best[:12]:
        print("  ", row)

    # The reverse direction: for the best anchor, which blocked cells are
    # *not* painted solid by the original (within the buffer's rows)?
    on, _, ox, oy, wrap = best[0]
    covered = set()
    for lx, ly in solid:
        map_px = lx * 16 + ox
        if wrap:
            map_px %= MAP_WIDTH
        covered.add((map_px // 32, ly + oy // 16))
    print(f"\nblocked cells in rows {oy // 16}..{oy // 16 + 11}: "
          f"{len({(bx, by) for bx, by in blocked if oy // 16 <= by <= oy // 16 + 11})}")
    missing = sorted({(bx, by) for bx, by in blocked
                      if oy // 16 <= by <= oy // 16 + 11} - covered)
    print(f"blocked but NOT solid in the original: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
