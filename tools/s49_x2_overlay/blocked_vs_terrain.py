#!/usr/bin/env python3
"""X2: the original's blocked (solid) region vs the remake's terrain.

The original's BG2 overlay buffer is 256x256 px and is anchored in map space
at map pixel (256, 0): buffer pixel ``p`` holds the map pixel
``(p + 256) mod 480``.  The buffer therefore covers

* map px 256..479  -> battle cells 8..14
* map px 0..31     -> battle cell 0 (the wrap tail)

and **nothing else** -- battle cells 1..7 are not in the buffer at all.

This tool prints, per battle row, how many of the 8 BG2 entries of each
covered battle cell carry the ``solid`` tile, next to the remake's terrain
class of the same cell.  The two must agree, otherwise the overlay's blocked
family and the map's terrain tell different stories.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

import compare_overlay_families as shared  # noqa: E402
from overlay_ground_truth import load_moment  # noqa: E402

BATTLE_CELL_W = 32
BATTLE_CELL_H = 16
MAP_W = 480
MAP_H = 304
ANCHOR = 256


def buffer_col_of_map_px(map_px: int) -> int:
    """The buffer entry column that holds the given map pixel."""
    return ((map_px - ANCHOR) % MAP_W) // 8


def main() -> int:
    terrain = shared.remake_terrain()
    moments = ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1")

    for name in moments:
        moment = load_moment(name)
        solid = [[moment.cells[r * 32 + c]["family"] == "solid"
                  for c in range(32)] for r in range(32)]
        print(f"=== {name}: solid entries (of 8) per covered battle cell")
        covered = [0] + list(range(8, 15))
        header = "  row  " + " ".join(f"c{bx:<2d}" for bx in covered)
        print(header + "   | terrain class")
        for by in range(13):
            row0 = by * 2
            row1 = by * 2 + 1
            if row1 >= 32:
                break
            counts = []
            classes = []
            for bx in covered:
                buf0 = buffer_col_of_map_px(bx * BATTLE_CELL_W)
                cols = [(buf0 + i) % 32 for i in range(4)]
                counts.append(sum(1 for c in cols
                                  for r in (row0, row1) if solid[r][c]))
                classes.append(terrain[by][bx] if by < len(terrain) else -1)
            print(f"  r{by:<3d} " + " ".join(f"{c:<3d}" for c in counts)
                  + "   | " + " ".join(f"{c:<2d}" for c in classes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
