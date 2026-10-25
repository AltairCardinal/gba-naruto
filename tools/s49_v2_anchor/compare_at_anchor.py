#!/usr/bin/env python3
"""Wave 9 / V2: compare the remake's overlay with the original's **at the
original's map-space anchor**, without searching for a window.

Why this tool exists
--------------------
The shared instrument (``tools/s49_overlay_align/compare_overlay_families.py``)
relabels the remake's overlay buffer with a *camera relative* window and
searches that window in ``[0, 256)``.  The original's anchor is map pixel
``(256, 0)`` - which that search range cannot even express (256 == 0 mod 256,
but the map is 480 px wide, so the two are different places).

This tool therefore does what the shared instrument cannot:

* the remake's buffer pixel ``p`` is labelled with the map pixel
  ``(p + 256) mod 480`` (horizontally) and ``p`` (vertically) -  the same
  convention as ``battle_map_overlay_map_x`` / ``_map_y`` in the remake;
* the original's side keeps the shared instrument's anchor convention;
* the two are compared per 16x16 logical cell.

It is a *diagnostic*:  it reports what the numbers look like once the
instrument can address the original's anchor.  Getting to
``both 192 / original-only 0 / remake-only 0 / mismatches 0`` additionally
requires the product side to draw the content at that anchor (the wiring
list is in ``notes/s49-fidelity/V2-camera-anchor.md`` section 6).

Usage::

    python tools/s49_v2_anchor/compare_at_anchor.py --vram <dump.bin>
    python tools/s49_v2_anchor/compare_at_anchor.py --vram-dir <dir>
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from compare_overlay_families import (  # noqa: E402
    ORIGINAL_MAP_ANCHOR,
    compare,
    find_overlay_map,
    remake_entry_map,
    original_map_cells,
)
from overlay_ground_truth import MOMENTS  # noqa: E402

ANCHOR_X, ANCHOR_Y = ORIGINAL_MAP_ANCHOR
MAP_WIDTH = 480
MAP_HEIGHT = 304
LOGICAL = 16


def remake_cells_at_anchor(entry_map: list[list[int]]) -> dict[tuple[int, int], str]:
    """The remake's overlay as map space logical cells, at the fixed anchor."""
    from compare_overlay_families import remake_family

    cells: dict[tuple[int, int], str] = {}
    for row in range(32):
        map_px_y = (row * 8 + ANCHOR_Y) % MAP_HEIGHT
        for column in range(32):
            tile = entry_map[row][column]
            if tile == 0:
                continue
            family, _tx, _ty = remake_family(tile)
            if family == "blank":
                continue
            map_px_x = (column * 8 + ANCHOR_X) % MAP_WIDTH
            key = (map_px_x // 16, map_px_y // 16)
            if cells.get(key, family) != family:
                cells[key] = "mixed"
            else:
                cells[key] = family
    return cells


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, default=None)
    ap.add_argument("--vram-dir", type=pathlib.Path, default=None)
    ap.add_argument("--moments", nargs="*", default=list(MOMENTS))
    args = ap.parse_args()

    dumps: list[pathlib.Path] = []
    if args.vram:
        dumps.append(args.vram)
    if args.vram_dir:
        dumps.extend(sorted(args.vram_dir.glob("*.vram-*.bin")))
    if not dumps:
        print("ERR --vram or --vram-dir is required")
        return 2

    originals = {name: original_map_cells(name) for name in args.moments}
    for path in dumps:
        vram = path.read_bytes()
        base = find_overlay_map(vram)
        if base < 0:
            print(f"{path.name}: no overlay map (the overlay is not displayed)")
            continue
        cells = remake_cells_at_anchor(remake_entry_map(vram, base))
        for name in args.moments:
            result = compare(originals[name], cells)
            print(f"{path.name}  {name}:  both {result['both_lit']:3d}"
                  f"  original-only {result['original_only']:3d}"
                  f"  remake-only {result['remake_only']:3d}"
                  f"  mismatches {result['family_mismatches']:3d}"
                  f"  residual {result['residual']:3d}"
                  f"  exact {result['exact']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
