#!/usr/bin/env python3
"""Compare the original's BG2 overlay buffer against the remake's terrain
derived overlay, cell by cell, at a chosen anchor.

The anchor is a map-space offset: buffer pixel (x, y) shows map pixel
(x + ox) mod 480, (y + oy) mod 304.

Usage::

    python tools/s49_y3/anchor_diff.py [--ox 256] [--oy 0]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from overlay_ground_truth import load_moment  # noqa: E402

MAP_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\generated_battle_map_content.h")
MAP_WIDTH = 480
MAP_HEIGHT = 304


def map_cells() -> list[list[int]]:
    text = MAP_HEADER.read_text(encoding="utf-8")
    body = re.search(r"battle_map_cells = \{\{(.*?)\n\}\};", text, re.S).group(1)
    values = [int(item, 16) for item in re.findall(
        r"battle_map_cell\{\s*(0x[0-9a-fA-F]+)\s*\}", body)]
    offset, width, height = 4393, 15, 19
    return [[values[offset + by * width + bx] & 15 for bx in range(width)]
            for by in range(height)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ox", type=int, default=256)
    ap.add_argument("--oy", type=int, default=0)
    ap.add_argument("--moment", default="movegrid-frame-v1")
    args = ap.parse_args()

    moment = load_moment(args.moment)
    cells = map_cells()
    print(f"moment {args.moment}  anchor ox={args.ox} oy={args.oy}")
    print("  buffer: 'S' original solid, 'X' both, '.' neither, "
          "'?' original solid but terrain walkable")
    for by in range(16):
        row = ""
        for bx in range(8):
            solid = False
            for dx in range(2):
                ly = by
                lx = bx * 2 + dx
                for ty in range(2):
                    for tx in range(2):
                        index = (ly * 2 + ty) * 32 + (lx * 2 + tx)
                        if moment.cells[index]["family"] == "solid":
                            solid = True
            map_bx = ((bx * 32 + args.ox) % MAP_WIDTH) // 32
            map_by = ((by * 16 + args.oy) % MAP_HEIGHT) // 16
            terrain_blocked = (cells[map_by][map_bx] != 0)
            if solid and terrain_blocked:
                row += "X"
            elif solid:
                row += "?"
            elif terrain_blocked:
                row += "o"
            else:
                row += "."
        print("  r%-2d %s" % (by, row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
