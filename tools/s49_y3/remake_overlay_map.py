#!/usr/bin/env python3
"""Decode the remake's overlay BG map and express it in map coordinates.

The remake's overlay buffer is a 256x256 px map-space window whose origin is
``window_x = 240 + camera.x()`` / ``window_y = 248 + camera.y()`` (see
``battle_runtime_scene.cpp``).  This tool decodes the buffer out of a VRAM
dump, guesses its map anchor by aligning the buffer's ``solid`` (blocked)
pixels with the terrain's blocked cells, and prints the result as a per
battle-cell family map.

Usage::

    python tools/s49_y3/remake_overlay_map.py --vram <dump.bin>
"""

from __future__ import annotations

import argparse
import pathlib
import re
import struct
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

FAMILIES = (
    (1, 8, "edge"), (9, 16, "hatch"), (17, 24, "line_alt"),
    (53, 60, "band"), (61, 68, "hatch_shift"), (69, 76, "solid"),
)
FAMILY_SHORT = {
    "blank": ".", "edge": "E", "hatch": "H", "line_alt": "A",
    "band": "B", "hatch_shift": "g", "solid": "S", "mixed": "?",
}


def find_overlay_map(vram: bytes) -> int:
    best = (-1, -1)
    for base in range(0, len(vram) - 2048 + 1, 0x800):
        entries = struct.unpack_from("<1024H", vram, base)
        tiles = [entry & 0x3FF for entry in entries]
        non_zero = [tile for tile in tiles if tile]
        if not non_zero:
            continue
        if any(not any(first <= tile <= last
                       for first, last, _family in FAMILIES)
               for tile in non_zero):
            continue
        if len(non_zero) > best[0]:
            best = (len(non_zero), base)
    return best[1]


def map_cells() -> list[list[int]]:
    text = MAP_HEADER.read_text(encoding="utf-8")
    body = re.search(r"battle_map_cells = \{\{(.*?)\n\}\};", text, re.S).group(1)
    values = [int(item, 16) for item in re.findall(
        r"battle_map_cell\{\s*(0x[0-9a-fA-F]+)\s*\}", body)]
    offset, width, height = 4393, 15, 19
    return [[values[offset + by * width + bx] & 15 for bx in range(width)]
            for by in range(height)]


def decode_entries(entries: list[int]) -> list[list[str]]:
    """16x16 logical family grid from the 32x32 entry grid."""
    grid = [["blank"] * 16 for _ in range(16)]
    for index, tile in enumerate(entries):
        if tile == 0:
            continue
        block = None
        for first, last, family in FAMILIES:
            if first <= tile <= last:
                block = (first, family)
                break
        if block is None:
            continue
        first, family = block
        position = tile - first
        tile_x = position % 4
        tile_y = position // 4
        entry_x = index % 32
        entry_y = index // 32
        cell_x = (entry_x - tile_x) // 4
        cell_y = (entry_y - tile_y) // 2
        logical_x = cell_x * 2 + tile_x // 2
        logical_y = cell_y
        if not (0 <= logical_x < 16 and 0 <= logical_y < 16):
            continue
        if grid[logical_y][logical_x] not in ("blank", family):
            grid[logical_y][logical_x] = "mixed"
        else:
            grid[logical_y][logical_x] = family
    return grid


def best_anchor(grid: list[list[str]], cells: list[list[int]]) -> tuple[int, int]:
    """Find the map offset that explains the buffer's solid cells best."""
    blocked = {(bx, by)
               for by, row in enumerate(cells)
               for bx, value in enumerate(row) if value != 0}
    best = (-1, 0, 0)
    for oy in range(0, MAP_HEIGHT, 16):
        for ox in range(0, MAP_WIDTH, 32):
            score = 0
            wrong = 0
            for by in range(16):
                for bx in range(8):
                    map_bx = ((bx * 32 + ox) % MAP_WIDTH) // 32
                    map_by = ((by * 16 + oy) % MAP_HEIGHT) // 16
                    terrain_blocked = (map_bx, map_by) in blocked
                    family = grid[by][bx * 2]
                    solid = family == "solid"
                    if solid and terrain_blocked:
                        score += 1
                    elif solid != terrain_blocked:
                        wrong += 1
            metric = score * 2 - wrong
            if metric > best[0]:
                best = (metric, ox, oy)
    return best[1], best[2]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--ox", type=int, default=None)
    ap.add_argument("--oy", type=int, default=None)
    ap.add_argument("--moment", default="movegrid-frame-v1")
    args = ap.parse_args()

    vram = args.vram.read_bytes()
    base = find_overlay_map(vram)
    print(f"vram {args.vram}  overlay map at 0x{base:05X}")
    entries = [entry & 0x3FF
               for entry in struct.unpack_from("<1024H", vram, base)]
    grid = decode_entries(entries)
    cells = map_cells()
    ox, oy = (args.ox, args.oy) if args.ox is not None else best_anchor(grid, cells)
    print(f"map anchor: buffer px (0,0) = map px ({ox}, {oy})")
    print("remake buffer, per battle cell (2 logical cols each):")
    for by in range(16):
        row = ""
        for bx in range(8):
            left = grid[by][bx * 2][:2]
            right = grid[by][bx * 2 + 1][:2]
            pair = left[0] if left[0] == right[0] else "%s/%s" % (left[0], right[0])
            row += ("%-6s" % pair)[:6]
        print("  r%-2d %s" % (by, row))
    print()
    print("original", args.moment, "for comparison:")
    moment = load_moment(args.moment)
    original = moment.logical_grid()
    for by in range(16):
        row = ""
        for bx in range(8):
            pair = original[by][bx * 2]
            row += ("%-6s" % pair[:6])[:6]
        print("  r%-2d %s" % (by, row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
