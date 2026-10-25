#!/usr/bin/env python3
"""X2: side-by-side map-space grids of the original and the remake.

Read-only reuse of ``tools/s49_overlay_align/compare_overlay_families.py``.

The original's buffer logical column ``lx`` holds the map pixel
``(256 + lx * 16) mod 480`` (the 480 px wrap is what the original's own
anchor evidence measured, ``tools/s49_y3/anchor_search.py``: 17984 / 17984
px at (256, 0) with wrap).  The shared instrument does **not** wrap the
original side, which is where its 24 "original missing" / 24 "painted too
much" cells come from.

Usage::

    python tools/s49_x2_overlay/dump_grids.py \
        --vram-dir build/s49-package/evidence/overlay/vram
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

import compare_overlay_families as shared  # noqa: E402
from overlay_ground_truth import LOGICAL_COLS, LOGICAL_ROWS  # noqa: E402

SHORT = {
    "blank": ".", "edge": "E", "hatch": "H", "line_alt": "A",
    "band": "B", "hatch_shift": "h", "solid": "S", "mixed": "?",
}


def original_cells_wrapped(name: str) -> dict[tuple[int, int], str]:
    moment = shared.load_moment(name)
    grid = moment.logical_grid()
    anchor_x, anchor_y = shared.ORIGINAL_MAP_ANCHOR
    cells: dict[tuple[int, int], str] = {}
    for ly in range(LOGICAL_ROWS):
        for lx in range(LOGICAL_COLS):
            family = grid[ly][lx]
            if family == "blank":
                continue
            map_lx = ((anchor_x + lx * 16) % shared.MAP_WIDTH) // 16
            map_ly = ((anchor_y + ly * 16) % shared.MAP_HEIGHT) // 16
            cells[(map_lx, map_ly)] = family
    return cells


def render(cells: dict[tuple[int, int], str],
           width: int = 30, height: int = 19) -> list[str]:
    lines = []
    for ly in range(height):
        row = "".join(SHORT.get(cells.get((lx, ly), "blank"), "?")
                      for lx in range(width))
        lines.append(f"  r{ly:2d} {row}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--frame", default=None,
                    help="the remake frame to compare (default: best per moment)")
    args = ap.parse_args()

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    terrain = shared.remake_terrain()

    remake_by_frame: dict[str, dict[tuple[int, int], str]] = {}
    for path in dumps:
        vram = path.read_bytes()
        base = shared.find_overlay_map(vram, terrain=terrain)
        if base < 0:
            remake_by_frame[path.name] = {}
            continue
        entry_map = shared.remake_entry_map(vram, base)
        _ax, _ay, cells = shared.best_window(entry_map, terrain)
        remake_by_frame[path.name] = cells

    for name in shared.MOMENTS:
        original = original_cells_wrapped(name)
        if args.frame:
            remake = remake_by_frame.get(args.frame, {})
            frame_name = args.frame
        else:
            frame_name = None
            best = None
            for path in dumps:
                cells = remake_by_frame[path.name]
                result = shared.compare(original, cells)
                key = (result["both_lit"] - result["family_mismatches"],
                       -result["residual"])
                if best is None or key > best[0]:
                    best = (key, path.name, result)
            if best is None:
                continue
            frame_name = best[1]
            remake = remake_by_frame[frame_name]

        print("=" * 78)
        print(f"{name}   remake frame: {frame_name}")
        print("-" * 78)
        print("  ORIGINAL (map space, wrapped)")
        for line in render(original):
            print(line)
        print("  REMAKE")
        for line in render(remake):
            print(line)
        print("  DIFF (x = mismatch, o = original only, r = remake only)")
        for ly in range(19):
            row = ""
            for lx in range(30):
                a = original.get((lx, ly), "blank")
                b = remake.get((lx, ly), "blank")
                if a == b:
                    row += "."
                elif a == "blank":
                    row += "r"
                elif b == "blank":
                    row += "o"
                else:
                    row += "x"
            print(f"  r{ly:2d} {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
