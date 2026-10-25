#!/usr/bin/env python3
"""Measure the original's overlay lattice (the `edge` grid lines).

The overlay layer is rebuilt from the exported ground truth (32 tiles, 4bpp,
32 byte stride) and the moment's tilemap.  This script then reports, for the
whole 256x256 layer:

* which rows/columns carry the `edge` line colour (palette index 1),
* which rows/columns carry a `solid` (grey dither) pixel,
* the exact pixel positions of the lattice lines.

The lattice spacing is what tells us the original's *battle cell* size.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "s49_rule_probe"))

from overlay_ground_truth import load_moment, load_palette, load_tiles  # noqa: E402


def build_layer(moment_name: str):
    moment = load_moment(moment_name)
    tiles = load_tiles()
    palette = load_palette()
    layer = [[0] * 256 for _ in range(256)]
    for index, cell in enumerate(moment.cells):
        art = tiles.get(cell["tile"])
        if art is None:
            continue
        base_x = (index % 32) * 8
        base_y = (index // 32) * 8
        for y in range(8):
            for x in range(8):
                layer[base_y + y][base_x + x] = art[y][x]
    return layer, palette


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--moment", default="movegrid-frame-v1")
    args = ap.parse_args()

    layer, palette = build_layer(args.moment)
    edge_rgb = palette[1]
    solid_rgb = palette[10]

    print(f"=== {args.moment} ===")
    print(f"  edge colour {edge_rgb}, solid colour {solid_rgb}")

    # lattice lines: pixels whose colour is exactly the edge colour
    vertical: dict[int, int] = {}
    horizontal: dict[int, int] = {}
    for x in range(256):
        count = sum(1 for y in range(256) if layer[y][x] == 1)
        if count:
            vertical[x] = count
    for y in range(256):
        count = sum(1 for x in range(256) if layer[y][x] == 1)
        if count:
            horizontal[y] = count
    print(f"  columns carrying the edge line: {sorted(vertical)}")
    print(f"  rows    carrying the edge line: {sorted(horizontal)}")

    # where does the solid (grey dither) region start/end per column?
    solid_cols = []
    for x in range(256):
        ys = [y for y in range(256) if layer[y][x] in (10, 11)]
        if ys:
            solid_cols.append((x, min(ys), max(ys)))
    if solid_cols:
        print(f"  solid region spans px x {solid_cols[0][0]}..{solid_cols[-1][0]}")
        print(f"  first column {solid_cols[0]}")
        print(f"  last  column {solid_cols[-1]}")

    # the top wall: rows 3..5 are solid across the whole width
    for y in range(0, 12):
        kinds = sorted({layer[y][x] for x in range(256)})
        print(f"  row {y:>3}: colour indices present {kinds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
