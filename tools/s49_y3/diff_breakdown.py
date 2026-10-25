#!/usr/bin/env python3
"""Categorise the remaining per-cell differences between the original's
overlay and the remake's overlay, in map space.

Every differing cell is attributed to one of

* ``extent``   -- the remake paints lattice rows the original leaves blank
  (the original draws its lattice for map rows 1..12 only);
* ``blocked``  -- the original paints the cell as blocked (grey dither)
  because its terrain class is not "plain", while the remake paints it as
  walkable ground;
* ``highlight``-- the reachable / attack / cursor highlight differs;
* ``anchor``   -- the cell is only lit on one side because the two overlays
  cover different map regions.

Usage::

    python tools/s49_y3/diff_breakdown.py --vram <dump.bin> --window-x 224 --window-y 0
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

from compare_overlay_families import (  # noqa: E402
    find_overlay_map,
    remake_entry_map,
    remake_logical_cells,
    remake_terrain,
    original_map_cells,
)

# The original draws its lattice for these map rows only (measured: its
# buffer rows 3..25 of the 8x8 tilemap are the only non-blank ones).
ORIGINAL_DRAWN_ROWS = range(1, 13)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--window-x", type=int, default=224)
    ap.add_argument("--window-y", type=int, default=0)
    ap.add_argument("--moment", default="movegrid-frame-v1")
    args = ap.parse_args()

    vram = args.vram.read_bytes()
    base = find_overlay_map(vram)
    entry_map = remake_entry_map(vram, base)
    remake = remake_logical_cells(entry_map, args.window_x, args.window_y)
    original = original_map_cells(args.moment)
    terrain = remake_terrain()
    blocked = {(bx, by)
               for by, row in enumerate(terrain)
               for bx, value in enumerate(row) if value != 0}

    counts = Counter()
    detail = []
    for key in sorted(set(original) | set(remake)):
        a = original.get(key, "blank")
        b = remake.get(key, "blank")
        if a == b:
            continue
        lx, ly = key
        map_by = ly
        map_bx = lx // 2
        if a == "blank":
            reason = ("extent" if map_by not in ORIGINAL_DRAWN_ROWS
                      else "remake_extra")
        elif b == "blank":
            reason = "original_only"
        else:
            if (map_bx, map_by) in blocked and b != "solid":
                reason = "blocked"
            elif a == "solid" and b != "solid":
                reason = "blocked"
            else:
                reason = "highlight"
        counts[reason] += 1
        detail.append((lx, ly, a, b, reason))

    total = sum(counts.values())
    print(f"moment {args.moment}  window ({args.window_x}, {args.window_y})  "
          f"differing cells: {total}")
    for reason, number in counts.most_common():
        print(f"  {reason:<10} {number}")
    print()
    print("  lx  ly  original -> remake   reason")
    for lx, ly, a, b, reason in detail[:40]:
        print(f"  {lx:3d} {ly:3d}  {a:<10} -> {b:<10} {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
