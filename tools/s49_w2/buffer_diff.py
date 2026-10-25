#!/usr/bin/env python3
"""Compare the original's and the remake's overlay **buffer**, cell for cell.

The original's BG2 overlay is a 256x256 px buffer (32x32 tilemap entries) and
the remake's is a 256x256 px buffer too.  Comparing them in *buffer* space
avoids every question about how a buffer cell maps back to a map cell (the
original's buffer tail is not a map column at all).

Both sides are reduced to a 16x16 grid of 16x16 px logical cells; a logical
cell's family is the family that contributes most of its four 8x8 entries
(the same rule the original's ground truth loader uses).

Usage::

    python tools/s49_w2/buffer_diff.py --vram-dir <dir> --moment field-frame-v1
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
    remake_terrain,
    REMAKE_TILE_RANGES,
)
from overlay_ground_truth import load_moment  # noqa: E402

SHORT = {"blank": ".", "edge": "e", "hatch": "H", "line_alt": "L",
         "band": "B", "hatch_shift": "G", "solid": "S"}
PRIORITY = {"solid": 6, "hatch": 5, "band": 4, "line_alt": 3,
            "edge": 2, "hatch_shift": 2, "blank": 0}


def remake_tile_family(tile: int) -> str:
    for first, last, family in REMAKE_TILE_RANGES:
        if first <= tile <= last:
            return family
    return "blank"


def logical_grid_from_entries(entries: list[list[int]]) -> list[list[str]]:
    grid = []
    for ly in range(16):
        row = []
        for lx in range(16):
            counts: dict[str, int] = {}
            for ty in range(2):
                for tx in range(2):
                    fam = remake_tile_family(entries[ly * 2 + ty][lx * 2 + tx])
                    counts[fam] = counts.get(fam, 0) + 1
            best = max(counts.items(),
                       key=lambda kv: (kv[1], PRIORITY.get(kv[0], 1)))
            row.append(best[0])
        grid.append(row)
    return grid


def original_grid(moment_name: str) -> list[list[str]]:
    return load_moment(moment_name).logical_grid()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--moment", default="field-frame-v1")
    ap.add_argument("--frame", default=None)
    args = ap.parse_args()

    terrain = remake_terrain()
    orig = original_grid(args.moment)

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    best = None
    for path in dumps:
        vram = path.read_bytes()
        base = find_overlay_map(vram, terrain=terrain)
        if base < 0:
            continue
        grid = logical_grid_from_entries(remake_entry_map(vram, base))
        lit = sum(1 for row in grid for f in row if f != "blank")
        same = sum(1 for ly in range(16) for lx in range(16)
                   if grid[ly][lx] == orig[ly][lx])
        key = (same, -abs(lit - 192))
        if best is None or key > best[0]:
            best = (key, path, grid)
    assert best is not None
    if args.frame:
        vram = (args.vram_dir / args.frame).read_bytes()
        base = find_overlay_map(vram, terrain=terrain)
        best = (None, args.vram_dir / args.frame,
                logical_grid_from_entries(remake_entry_map(vram, base)))
    grid = best[2]

    print(f"=== original {args.moment} (buffer) ===")
    for ly in range(16):
        print(f"  {ly:>2} " + "".join(SHORT.get(orig[ly][lx], "?")
                                      for lx in range(16)))
    print(f"\n=== remake {best[1].name} (buffer) ===")
    for ly in range(16):
        print(f"  {ly:>2} " + "".join(SHORT.get(grid[ly][lx], "?")
                                      for lx in range(16)))

    print("\n=== difference map (X = different) ===")
    for ly in range(16):
        cells = []
        for lx in range(16):
            a, b = orig[ly][lx], grid[ly][lx]
            cells.append("." if a == b else
                         ("X" if (a == "blank") != (b == "blank") else "x"))
        print(f"  {ly:>2} " + "".join(cells))

    only_o = only_r = mism = both = 0
    for ly in range(16):
        for lx in range(16):
            a, b = orig[ly][lx], grid[ly][lx]
            if a != "blank" and b != "blank":
                both += 1
                if a != b:
                    mism += 1
            elif a != "blank":
                only_o += 1
            elif b != "blank":
                only_r += 1
    print(f"\nbuffer-space: both {both}  original-only {only_o}  "
          f"remake-only {only_r}  mismatches {mism}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
