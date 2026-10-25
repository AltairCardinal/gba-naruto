#!/usr/bin/env python3
"""Print the original's overlay and the remake's overlay side by side, in map
space logical cells.

Usage::

    python tools/s49_y3/side_by_side.py --vram <dump.bin> --window-x 224 --window-y 0
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

from compare_overlay_families import (  # noqa: E402
    find_overlay_map,
    remake_entry_map,
    remake_logical_cells,
    original_map_cells,
)

SHORT = {
    "blank": ".", "edge": "E", "hatch": "H", "line_alt": "A",
    "band": "B", "hatch_shift": "g", "solid": "S", "mixed": "?",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--window-x", type=int, default=224)
    ap.add_argument("--window-y", type=int, default=0)
    ap.add_argument("--moment", default="movegrid-frame-v1")
    args = ap.parse_args()

    vram = args.vram.read_bytes()
    base = find_overlay_map(vram)
    entry_map = remake_entry_map(vram, base)
    remake = remake_logical_cells(entry_map, args.window_x, args.window_y)
    original = original_map_cells(args.moment)

    lxs = sorted({key[0] for key in set(original) | set(remake)})
    lys = sorted({key[1] for key in set(original) | set(remake)})
    print(f"original {args.moment} (left)   vs   remake (right)   "
          f"window ({args.window_x}, {args.window_y})")
    print("map logical columns " + " ".join(f"{lx:<4d}" for lx in lxs))
    for ly in lys:
        left = " ".join(f"{SHORT.get(original.get((lx, ly), 'blank')):<4s}"
                        for lx in lxs)
        right = " ".join(f"{SHORT.get(remake.get((lx, ly), 'blank')):<4s}"
                         for lx in lxs)
        print(f"ly{ly:<3d} {left}   |  {right}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
