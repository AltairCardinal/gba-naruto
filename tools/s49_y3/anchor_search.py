#!/usr/bin/env python3
"""Brute-force the geometric anchor between the original's BG2 overlay and the
remake's battle-14 terrain.

The original's overlay buffer is 256x256 px (map space).  This tool turns its
``solid`` (blocked) pixels into a per-row bitmask and searches every 8 px
offset for the shift of the remake's terrain-derived blocked mask that best
explains it.

Usage::

    python tools/s49_y3/anchor_search.py
"""

from __future__ import annotations

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


def original_solid_rows(moment_name: str) -> list[int]:
    moment = load_moment(moment_name)
    rows = []
    for y in range(32):
        mask = 0
        for x in range(32):
            if moment.cells[y * 32 + x]["family"] == "solid":
                mask |= 0xFF << (x * 8)
        rows.extend([mask] * 8)   # one 8 px tilemap row = 8 px rows
    return rows


def map_blocked_rows(classes: tuple[int, ...]) -> list[int]:
    text = MAP_HEADER.read_text(encoding="utf-8")
    body = re.search(r"battle_map_cells = \{\{(.*?)\n\}\};", text, re.S).group(1)
    values = [int(item, 16) for item in re.findall(
        r"battle_map_cell\{\s*(0x[0-9a-fA-F]+)\s*\}", body)]
    offset, width, height = 4393, 15, 19
    blocked = set()
    for by in range(height):
        for bx in range(width):
            if (values[offset + by * width + bx] & 15) in classes:
                blocked.add((bx, by))
    rows = []
    for py in range(height * 16):
        by = py // 16
        mask = 0
        for bx in range(width):
            if (bx, by) in blocked:
                mask |= 0xFFFFFFFF << (bx * 32)
        rows.append(mask)
    return rows


def score(original: list[int], terrain: list[int], ox: int, oy: int,
          wrap: bool) -> int:
    total = 0
    height = len(terrain)
    width = 480
    for y in range(256):
        if wrap:
            sy = (y + oy) % height
            shifted = ((terrain[sy] >> ox) | (terrain[sy] << (width - ox))) \
                & ((1 << 256) - 1)
        else:
            sy = y + oy
            if sy >= height:
                break
            shifted = (terrain[sy] >> ox) & ((1 << 256) - 1)
        total += bin(original[y] & shifted).count("1")
    return total


def main() -> int:
    for moment in ("movegrid-frame-v1", "field-frame-v1"):
        original = original_solid_rows(moment)
        total = sum(bin(row).count("1") for row in original)
        print(f"=== {moment}: original solid px = {total}")
        for classes in ((15,), (15, 7), (15, 7, 1), (15, 7, 1, 3)):
            terrain = map_blocked_rows(classes)
            for wrap in (False, True):
                results = []
                for oy in range(0, 304, 8):
                    for ox in range(0, 480, 8):
                        results.append((score(original, terrain, ox, oy, wrap),
                                        ox, oy))
                results.sort(reverse=True)
                text = ", ".join(
                    f"overlap={o} at ({x},{y})" for o, x, y in results[:3])
                print(f"  classes={classes} wrap={wrap}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
