#!/usr/bin/env python3
"""Dump the original's 16x16 logical buffer grid and the remake's map-space grid.

This shows the *raw* buffer coordinates (no 480 px wrap applied on the
original side) next to the map space coordinates, so the wrap segment can be
identified.

Usage::

    python tools/s49_w2/dump_grids.py --vram-dir <dir> --moment field-frame-v1
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from compare_overlay_families import (  # noqa: E402
    find_overlay_map,
    remake_entry_map,
    remake_logical_cells,
    remake_terrain,
    REMAKE_MAP_ANCHOR,
    MAP_WIDTH,
    MAP_HEIGHT,
)
from overlay_ground_truth import load_moment  # noqa: E402

SHORT = {"blank": ".", "edge": "e", "hatch": "H", "line_alt": "L",
         "band": "B", "hatch_shift": "G", "solid": "S", "mixed": "?"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--moment", default="field-frame-v1")
    ap.add_argument("--frame", default="step-25-A.state.vram-0000.bin")
    args = ap.parse_args()

    terrain = remake_terrain()
    moment = load_moment(args.moment)
    grid = moment.logical_grid()

    print(f"=== original {args.moment}: 16x16 buffer logical cells "
          f"(buffer px = col*16, map px = col*16 + 256) ===")
    print("      " + "".join(f"{c:>2}" for c in range(16)))
    for ly in range(16):
        row = "".join(SHORT.get(grid[ly][lx], "?") for lx in range(16))
        print(f"  {ly:>2}  {row}")

    path = args.vram_dir / args.frame
    vram = path.read_bytes()
    base = find_overlay_map(vram, terrain=terrain)
    entry_map = remake_entry_map(vram, base)
    cells = remake_logical_cells(entry_map, *REMAKE_MAP_ANCHOR)

    print(f"\n=== remake {args.frame}: map space logical cells "
          f"(16 px cells, map px 0..479) ===")
    for ly in range(MAP_HEIGHT // 16):
        row = ""
        for lx in range(MAP_WIDTH // 16):
            row += SHORT.get(cells.get((lx, ly), "blank"), "?")
        print(f"  {ly:>2}  {row}")

    print("\n=== terrain classes (15 battle cols x 19 rows) ===")
    for by, row in enumerate(terrain):
        print(f"  {by:>2}  " + "".join(str(v) for v in row))

    print("\n=== original buffer column -> map position ===")
    for lx in range(16):
        raw = lx * 16 + 256
        print(f"  buffer logical col {lx:>2}  map px {raw:>3}..{raw + 15:>3}  "
              f"battle col {raw // 32:>2}  map logical col "
              f"{(raw % MAP_WIDTH) // 16:>2} (raw {raw // 16})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
