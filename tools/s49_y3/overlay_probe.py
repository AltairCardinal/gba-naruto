#!/usr/bin/env python3
"""Decode the remake's overlay BG map out of a VRAM dump and compare it with
the original's four BG2 overlay moments, cell by cell.

Why this tool exists
--------------------
``tools/s49_overlay_align/compare_overlay_families.py`` locates the overlay
layer with ``find_overlay_map()``, which scans *every* 0x400 aligned window of
VRAM and keeps the one with the most entries whose tile index falls in
``1..77``.  On a GBA the BG tile graphics live in VRAM 0x00000-0x0FFFF and the
BG maps live in 0x10000-0x17FFF, so that scan happily returns a window of
*tile graphics* and decodes it as if it were a tilemap.

This tool instead requires a window whose **every** non-zero entry is a valid
overlay tile index *and* whose entries form a consistent battle cell grid
(4 entries wide x 2 entries tall per 32x16 px cell), which is what the
remake's overlay layer really looks like.

Usage::

    python tools/s49_y3/overlay_probe.py --vram <dump.bin> [--moments ...]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from overlay_ground_truth import (  # noqa: E402
    LOGICAL_COLS,
    LOGICAL_ROWS,
    MOMENTS,
    load_moment,
)

# The remake's overlay tile index layout (battle_range_ui_style.h):
#   grid 1..8, move 9..16, attack_range 17..24, cursor 53..60,
#   target 61..68, blocked 69..76.
TILE_FAMILY = {}
for _first, _last, _family in (
        (1, 8, "edge"), (9, 16, "hatch"), (17, 24, "line_alt"),
        (53, 60, "band"), (61, 68, "hatch_shift"), (69, 76, "solid")):
    for _t in range(_first, _last + 1):
        TILE_FAMILY[_t] = _family

FAMILY_SHORT = {
    "blank": ".", "edge": "E", "hatch": "H", "line_alt": "A",
    "band": "B", "hatch_shift": "g", "solid": "S", "mixed": "?",
}


def overlay_tile_family(tile: int) -> str | None:
    return TILE_FAMILY.get(tile)


def find_overlay_maps(vram: bytes) -> list[tuple[int, int]]:
    """(base, overlay_entry_count) for every plausible overlay map.

    A plausible overlay map is a 0x800 aligned window whose non-zero entries
    are all overlay tile indices and whose cells form a consistent battle cell
    grid.
    """
    results: list[tuple[int, int]] = []
    for base in range(0, len(vram) - 2048 + 1, 0x800):
        entries = struct.unpack_from("<1024H", vram, base)
        tiles = [entry & 0x3FF for entry in entries]
        non_zero = [tile for tile in tiles if tile]
        if not non_zero:
            continue
        if any(tile not in TILE_FAMILY for tile in non_zero):
            continue
        results.append((base, len(non_zero)))
    return results


def decode_logical_grid(entries: list[int]) -> list[list[str]]:
    """Rebuild the 16x16 logical family grid from a 32x32 entry grid.

    The overlay's entry grid is aligned with the battle cell grid in map space:
    a battle cell is 4 entries wide and 2 entries tall (32x16 px) and a
    logical cell is 2 entries wide and 2 entries tall (16x16 px).
    """
    grid = [["blank"] * LOGICAL_COLS for _ in range(LOGICAL_ROWS)]
    for index, tile in enumerate(entries):
        if tile == 0:
            continue
        block = None
        for first, last, family in (
                (1, 8, "edge"), (9, 16, "hatch"), (17, 24, "line_alt"),
                (53, 60, "band"), (61, 68, "hatch_shift"), (69, 76, "solid")):
            if first <= tile <= last:
                block = (first, family)
                break
        if block is None:
            continue
        first, fam = block
        pos = tile - first
        tile_x = pos % 4      # entry position inside the battle cell (0..3)
        tile_y = pos // 4     # entry position inside the battle cell (0..1)
        entry_x = index % 32
        entry_y = index // 32
        cell_x = (entry_x - tile_x) // 4
        cell_y = (entry_y - tile_y) // 2
        logical_x = cell_x * 2 + (tile_x // 2)
        logical_y = cell_y
        if not (0 <= logical_x < LOGICAL_COLS and 0 <= logical_y < LOGICAL_ROWS):
            continue
        if grid[logical_y][logical_x] not in ("blank", fam):
            grid[logical_y][logical_x] = "mixed"
        else:
            grid[logical_y][logical_x] = fam
    return grid


def compare(left: list[list[str]], right: list[list[str]],
            offset_x: int, offset_y: int) -> dict:
    original_only = 0
    remake_only = 0
    mismatch = 0
    both_lit = 0
    original_lit = 0
    remake_lit = 0
    details = []
    for y in range(LOGICAL_ROWS):
        for x in range(LOGICAL_COLS):
            other_x = x + offset_x
            other_y = y + offset_y
            a = left[y][x]
            b = "blank"
            if 0 <= other_x < LOGICAL_COLS and 0 <= other_y < LOGICAL_ROWS:
                b = right[other_y][other_x]
            a_lit = a != "blank"
            b_lit = b != "blank"
            original_lit += 1 if a_lit else 0
            remake_lit += 1 if b_lit else 0
            if a_lit and b_lit:
                both_lit += 1
                if a != b:
                    mismatch += 1
                    details.append({"x": x, "y": y, "original": a, "remake": b})
            elif a_lit:
                original_only += 1
                details.append({"x": x, "y": y, "original": a, "remake": "blank"})
            elif b_lit:
                remake_only += 1
                details.append({"x": x, "y": y, "original": "blank", "remake": b})
    return {
        "offset": [offset_x, offset_y],
        "original_lit": original_lit,
        "remake_lit": remake_lit,
        "both_lit": both_lit,
        "original_only": original_only,
        "remake_only": remake_only,
        "family_mismatches": mismatch,
        "exact": original_only == 0 and remake_only == 0 and mismatch == 0,
        "residual": original_only + remake_only + mismatch,
        "differences": details,
    }


def best_offset(left: list[list[str]], right: list[list[str]]) -> dict:
    results = []
    for offset_y in range(LOGICAL_ROWS):
        for offset_x in range(LOGICAL_COLS):
            result = compare(left, right, offset_x, offset_y)
            score = (result["both_lit"] - result["family_mismatches"],
                     -result["residual"])
            results.append((score, result))
    results.sort(key=lambda item: (-item[0][0], -item[0][1], item[1]["offset"]))
    return results[0][1]


def print_grid(grid: list[list[str]], title: str) -> None:
    print(f"  {title}")
    for y, row in enumerate(grid):
        print("   r%-2d %s" % (y, " ".join(FAMILY_SHORT.get(f, "?") for f in row)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--moments", nargs="*", default=list(MOMENTS))
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--quiet-grid", action="store_true")
    args = ap.parse_args()

    vram = args.vram.read_bytes()
    candidates = find_overlay_maps(vram)
    print(f"vram {args.vram} ({len(vram)} bytes)")
    print("overlay map candidates (base, entries): "
          + ", ".join(f"0x{base:05X}={count}" for base, count in candidates))
    if not candidates:
        print("ERR no overlay map found")
        return 2

    base, count = max(candidates, key=lambda item: item[1])
    entries = [entry & 0x3FF
               for entry in struct.unpack_from("<1024H", vram, base)]
    right = decode_logical_grid(entries)
    print(f"using overlay map at VRAM 0x{base:05X} ({count} painted entries)")
    if not args.quiet_grid:
        print_grid(right, "remake logical cells:")

    report = {"vram": str(args.vram), "overlay_map": base, "moments": {}}
    for name in args.moments:
        left = load_moment(name).logical_grid()
        best = best_offset(left, right)
        report["moments"][name] = best
        print(f"\n=== {name} ===")
        print(f"  best offset {best['offset']}  original lit {best['original_lit']}  "
              f"remake lit {best['remake_lit']}  both {best['both_lit']}")
        print(f"  original-only {best['original_only']}  remake-only {best['remake_only']}  "
              f"family mismatches {best['family_mismatches']}  "
              f"residual {best['residual']}  exact {best['exact']}")
        kinds = Counter((d["original"], d["remake"]) for d in best["differences"])
        for pair, number in kinds.most_common():
            print(f"    {pair[0]:>10} -> {pair[1]:<10} x{number}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
