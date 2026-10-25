#!/usr/bin/env python3
"""Scan every candidate map space window of the remake's overlay buffer and
report the best comparison per original moment.

Usage::

    python tools/s49_y3/window_scan.py --vram <dump.bin> [--moments ...]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

from compare_overlay_families import (  # noqa: E402
    compare,
    find_overlay_map,
    remake_entry_map,
    remake_logical_cells,
    remake_terrain,
    original_map_cells,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--moments", nargs="*",
                    default=["field-frame-v1", "movegrid-frame-v1",
                             "grid16-frame-v1", "banner-frame-v1"])
    args = ap.parse_args()

    vram = args.vram.read_bytes()
    base = find_overlay_map(vram)
    print(f"overlay map at 0x{base:05X}")
    entry_map = remake_entry_map(vram, base)
    originals = {name: original_map_cells(name) for name in args.moments}

    for name, original in originals.items():
        best = None
        for window_y in range(0, 256, 8):
            for window_x in range(0, 256, 8):
                cells = remake_logical_cells(entry_map, window_x, window_y)
                result = compare(original, cells)
                score = (result["both_lit"] - result["family_mismatches"],
                         -result["residual"])
                if best is None or score > best[0]:
                    best = (score, window_x, window_y, result)
        _score, window_x, window_y, result = best
        print(f"=== {name}: window ({window_x}, {window_y})  "
              f"both {result['both_lit']}  orig-only {result['original_only']}  "
              f"remake-only {result['remake_only']}  "
              f"mismatch {result['family_mismatches']}  "
              f"remake lit {result['remake_lit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
