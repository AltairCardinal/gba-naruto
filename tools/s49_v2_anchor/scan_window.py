#!/usr/bin/env python3
"""Wave 9 / V2: does *any* map-space window make the remake's overlay content
match the original exactly?

The shared instrument (``tools/s49_overlay_align/compare_overlay_families.py``)
searches the remake's window origin only in ``[0, 256)``.  The original's
anchor is map px ``(256, 0)``, which that range cannot express, so this probe
widens the search to the whole map width (480 px) and prints the score of
every candidate window.

It answers one yes/no question:

    "Is the remake's overlay *content* already correct, and only its
     map-space *anchor* wrong?"

If some window yields ``original_only == 0 and remake_only == 0 and
family_mismatches == 0`` then the content is right and only the anchor has to
move.  If no window does, the content itself differs (draw range, blocked
set, ...) and the anchor is not the only defect.

Usage::

    python tools/s49_v2_anchor/scan_window.py --vram <dump.bin>
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from compare_overlay_families import (  # noqa: E402
    compare,
    find_overlay_map,
    remake_entry_map,
    remake_logical_cells,
    original_map_cells,
)

MOMENTS = ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--moments", nargs="*", default=list(MOMENTS))
    args = ap.parse_args()

    vram = args.vram.read_bytes()
    base = find_overlay_map(vram)
    print(f"overlay map at 0x{base:05X}")
    if base < 0:
        print("no overlay map in this frame")
        return 1
    entry_map = remake_entry_map(vram, base)

    for name in args.moments:
        original = original_map_cells(name)
        best = None
        rows = []
        for window_y in range(0, 256, 8):
            for window_x in range(0, 480, 8):
                cells = remake_logical_cells(entry_map, window_x, window_y)
                result = compare(original, cells)
                exact = (result["original_only"] == 0
                         and result["remake_only"] == 0
                         and result["family_mismatches"] == 0)
                score = (result["both_lit"] - result["family_mismatches"],
                         -result["residual"])
                rows.append((score, window_x, window_y, result, exact))
                if best is None or score > best[0]:
                    best = (score, window_x, window_y, result, exact)
        rows.sort(key=lambda row: row[0], reverse=True)
        print(f"=== {name}: original lit {len(original)}")
        for score, window_x, window_y, result, exact in rows[:6]:
            print(f"  window ({window_x:3d},{window_y:3d})  both {result['both_lit']:3d}"
                  f"  orig-only {result['original_only']:3d}"
                  f"  remake-only {result['remake_only']:3d}"
                  f"  mismatch {result['family_mismatches']:3d}"
                  f"  residual {result['residual']:3d}"
                  f"  exact {exact}")
        exact_windows = [row for row in rows if row[4]]
        if exact_windows:
            print(f"  EXACT windows: "
                  f"{[(row[1], row[2]) for row in exact_windows][:8]}")
        else:
            print("  NO exact window in [0,480) x [0,256)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
