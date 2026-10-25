#!/usr/bin/env python3
"""Read the remake's generated battle map content (battle 14) and print it.

The remake's battle map is a grid of 16-bit attribute cells
(``battle_map_cell.raw_attributes``).  The low nibble is the terrain class
(``battle_map_content.h``), and a cell whose terrain class is
``battle_map_fully_closed`` (15) is impassable (``cost == 0``).
"""

from __future__ import annotations

import pathlib
import re

REMAKE_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\generated_battle_map_content.h"
)

FULLY_CLOSED = 15


def load_definitions(text: str) -> list[tuple[int, int, int, int, int]]:
    """[(battle_id, width, height, cell_offset, cell_count), ...]"""
    out = []
    for match in re.finditer(
            r"battle_map_definition\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}",
            text):
        out.append(tuple(int(value) for value in match.groups()))
    return out


def load_cells(text: str) -> list[int]:
    body = text.split("battle_map_cells = {{", 1)[1]
    body = body.split("}};", 1)[0]
    return [int(value, 0) for value in re.findall(r"0x[0-9A-Fa-f]+|\d+", body)]


def main() -> int:
    text = REMAKE_HEADER.read_text(encoding="utf-8")
    definitions = load_definitions(text)
    cells = load_cells(text)
    print(f"definitions: {len(definitions)}   cells: {len(cells)}")
    for definition in definitions:
        if definition[0] != 14:
            continue
        _battle, width, height, offset, count = definition
        print(f"battle 14: {width} x {height}  offset {offset} count {count}")
        print()
        for y in range(height):
            row = []
            for x in range(width):
                raw = cells[offset + y * width + x]
                terrain = raw & FULLY_CLOSED
                row.append(
                    "#" if terrain == FULLY_CLOSED else
                    ("." if terrain == 0 else str(terrain % 10)))
            print(f"  r{y:2d} " + " ".join(row))
        print()
        print("  terrain histogram:")
        hist = {}
        for y in range(height):
            for x in range(width):
                terrain = cells[offset + y * width + x] & FULLY_CLOSED
                hist[terrain] = hist.get(terrain, 0) + 1
        for terrain in sorted(hist):
            print(f"    terrain {terrain:>2}: {hist[terrain]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
