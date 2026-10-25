#!/usr/bin/env python3
"""The overlay instrument's two conventions, side by side, on the same VRAM.

Why this tool exists
--------------------
Wave 10 / U4 changed ``compare_overlay_families.py`` from a *searched
window* convention to the original's *measured anchor*:

* **old (wave <= 9)**: the buffer pixel ``p`` was labelled with the map pixel
  ``p + 256 * ceil_div(window_x - p, 256)`` and ``window`` was searched in
  ``[0, 256)``.  That range cannot even express the original's anchor
  (map px 256 on a 480 px wide map), and reporting the *best* of the search
  flatters the remake.
* **new (wave 10 / U4)**: the buffer pixel ``p`` holds the map pixel
  ``((p + 256) mod 480, p)`` -- the anchor is a measured constant
  (17984 / 17984 px against the battle-14 terrain at ``(256, 0)``).

This tool answers exactly one question: **does changing the convention move
the numbers?**  It runs both conventions on the same dump and prints both.

Usage::

    python tools/s49_overlay_align/compare_conventions.py \
        --vram <dump.bin> --out build/s49-overlay/conventions.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from compare_overlay_families import (  # noqa: E402
    MAP_HEIGHT,
    MAP_WIDTH,
    REMAKE_MAP_ANCHOR,
    compare,
    find_overlay_map,
    remake_entry_map,
    remake_family,
    remake_terrain,
    original_map_cells,
)
from overlay_ground_truth import MOMENTS  # noqa: E402


def ceil_div(value: int, divisor: int) -> int:
    quotient = value // divisor
    remainder = value % divisor
    return quotient + 1 if remainder > 0 else quotient


def old_window_cells(entry_map, window_x: int, window_y: int):
    """The wave <= 9 convention: a camera derived window, wrapped every 256 px."""
    cells: dict[tuple[int, int], str] = {}
    for row in range(32):
        map_px_y = row * 8 + 256 * ceil_div(window_y - row * 8, 256)
        for column in range(32):
            tile = entry_map[row][column]
            if tile == 0:
                continue
            family, _tx, _ty = remake_family(tile)
            if family == "blank":
                continue
            map_px_x = (column * 8
                        + 256 * ceil_div(window_x - column * 8, 256))
            key = (map_px_x // 16, map_px_y // 16)
            if cells.get(key, family) != family:
                cells[key] = "mixed"
            else:
                cells[key] = family
    return cells


def old_best_window(entry_map, terrain):
    """The wave <= 9 search: the best window in [0, 256) x [0, 256)."""
    blocked = {(bx, by)
               for by, row in enumerate(terrain)
               for bx, value in enumerate(row) if value != 0}
    best = None
    for window_y in range(0, 256, 8):
        for window_x in range(0, 256, 8):
            cells = old_window_cells(entry_map, window_x, window_y)
            contained = wrong = 0
            for (lx, ly), family in cells.items():
                if family != "solid":
                    continue
                if (lx // 2, ly) in blocked:
                    contained += 1
                else:
                    wrong += 1
            score = (contained - wrong, contained)
            if best is None or score > best[0]:
                best = (score, window_x, window_y, cells)
    return best[1], best[2], best[3]


def anchored_cells(entry_map, anchor_x: int, anchor_y: int):
    """The wave 10 convention: the buffer pixel holds the map pixel."""
    cells: dict[tuple[int, int], str] = {}
    for row in range(32):
        map_px_y = (row * 8 + anchor_y) % MAP_HEIGHT
        for column in range(32):
            tile = entry_map[row][column]
            if tile == 0:
                continue
            family, _tx, _ty = remake_family(tile)
            if family == "blank":
                continue
            map_px_x = (column * 8 + anchor_x) % MAP_WIDTH
            key = (map_px_x // 16, map_px_y // 16)
            if cells.get(key, family) != family:
                cells[key] = "mixed"
            else:
                cells[key] = family
    return cells


def summarize(result: dict) -> dict:
    return {key: result[key] for key in
            ("original_lit", "remake_lit", "both_lit", "original_only",
             "remake_only", "family_mismatches", "residual", "exact")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vram", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    parser.add_argument("--moments", nargs="*", default=list(MOMENTS))
    args = parser.parse_args()

    terrain = remake_terrain()
    vram = args.vram.read_bytes()
    base = find_overlay_map(vram)
    if base < 0:
        print("ERR no overlay map in the dump")
        return 2
    entry_map = remake_entry_map(vram, base)

    old_x, old_y, old = old_best_window(entry_map, terrain)
    new = anchored_cells(entry_map, REMAKE_MAP_ANCHOR[0], REMAKE_MAP_ANCHOR[1])

    document = {
        "schema": "konoha.s49-overlay.conventions.v1",
        "dump": args.vram.name,
        "overlay_map": base,
        "old_convention": {
            "name": "window-search (wave <= 9)",
            "window": [old_x, old_y],
            "search_range": "[0, 256) x [0, 256)",
        },
        "new_convention": {
            "name": "fixed map-space anchor (wave 10 / U4)",
            "anchor": list(REMAKE_MAP_ANCHOR),
            "rule": "buffer px p holds map px ((p + 256) mod 480, p)",
        },
        "moments": {},
    }
    for name in args.moments:
        original = original_map_cells(name)
        old_result = compare(original, old)
        new_result = compare(original, new)
        document["moments"][name] = {
            "old_window": summarize(old_result),
            "new_anchor": summarize(new_result),
            "delta": {
                "both_lit": new_result["both_lit"] - old_result["both_lit"],
                "original_only": (new_result["original_only"]
                                  - old_result["original_only"]),
                "remake_only": (new_result["remake_only"]
                                - old_result["remake_only"]),
                "family_mismatches": (new_result["family_mismatches"]
                                      - old_result["family_mismatches"]),
                "residual": new_result["residual"] - old_result["residual"],
            },
        }

    for name in args.moments:
        row = document["moments"][name]
        old_result = row["old_window"]
        new_result = row["new_anchor"]
        print(f"=== {name}")
        print(f"  old window  ({old_x}, {old_y}): both {old_result['both_lit']:3d} "
              f"orig-only {old_result['original_only']:3d} "
              f"remake-only {old_result['remake_only']:3d} "
              f"mismatch {old_result['family_mismatches']:3d} "
              f"residual {old_result['residual']:3d}")
        print(f"  new anchor  {REMAKE_MAP_ANCHOR}: both {new_result['both_lit']:3d} "
              f"orig-only {new_result['original_only']:3d} "
              f"remake-only {new_result['remake_only']:3d} "
              f"mismatch {new_result['family_mismatches']:3d} "
              f"residual {new_result['residual']:3d}")
        print(f"  delta      : residual {row['delta']['residual']:+d}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(document, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
