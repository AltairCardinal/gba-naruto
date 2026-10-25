#!/usr/bin/env python3
"""Rebuild the original's BG2 overlay layer and relate it to the screen.

The overlay layer is 32x32 tilemap entries = 256x256 px.  Screen pixel
``(sx, sy)`` shows overlay pixel ``(sx + hoffs, sy + voffs) mod 256``.

This script

* rebuilds the 256x256 overlay pixel layer from the exported ground truth
  (32 tiles, 4bpp, 32 byte stride) and the moment's tilemap,
* prints the per-16x16-logical-cell family map,
* and (optionally) checks the layer against a pair of original screenshots
  (one with BG2 off, one with BG2 on) by diffing them.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "s49_rule_probe"))

from overlay_ground_truth import (  # noqa: E402
    LOGICAL_COLS,
    LOGICAL_ROWS,
    MAP_COLS,
    load_moment,
    load_palette,
    load_tiles,
)

FAMILY_SHORT = {
    "blank": ".", "edge": "E", "hatch": "H", "line_alt": "A",
    "band": "B", "solid": "S", "hatch_shift": "h",
}


def build_layer(moment_name: str) -> tuple[list[list[tuple[int, int, int]]], int, int]:
    """The 256x256 overlay pixel layer plus its (hoff, voff) scroll."""
    moment = load_moment(moment_name)
    tiles = load_tiles()
    palette = load_palette()
    layer = [[(0, 0, 0)] * 256 for _ in range(256)]
    for index, cell in enumerate(moment.cells):
        tile = cell["tile"]
        bank = cell.get("palette_bank", 12)
        art = tiles.get(tile)
        if art is None:
            continue
        base_x = (index % MAP_COLS) * 8
        base_y = (index // MAP_COLS) * 8
        for y in range(8):
            for x in range(8):
                value = art[y][x]
                colour = palette[value] if value else (0, 0, 0)
                layer[base_y + y][base_x + x] = tuple(colour)
    registers = moment.registers
    hoffs = registers.get("bg_hoffs")
    voffs = registers.get("bg_voffs")
    if isinstance(hoffs, list):
        hoffs = hoffs[2]
    if isinstance(voffs, list):
        voffs = voffs[2]
    return layer, int(hoffs or 0), int(voffs or 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--moment", default="movegrid-frame-v1")
    ap.add_argument("--gt-dir", type=pathlib.Path, default=None)
    ap.add_argument("--off", action="store_true",
                    help="print the logical-cell family map")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"),
                    type=pathlib.Path, default=None,
                    help="two screenshots (overlay off / on) to cross-check")
    args = ap.parse_args()

    layer, hoffs, voffs = build_layer(args.moment)
    print(f"=== {args.moment}: overlay 256x256, scroll ({hoffs}, {voffs}) ===")

    moment = load_moment(args.moment)
    if args.off:
        grid = moment.logical_grid()
        print("  logical 16x16 cells (overlay space):")
        for y in range(LOGICAL_ROWS):
            print(f"    r{y:2d} " + " ".join(FAMILY_SHORT.get(f, "?") for f in grid[y]))

    if args.diff:
        before = Image.open(args.diff[0]).convert("RGB")
        after = Image.open(args.diff[1]).convert("RGB")
        bp = before.load()
        ap_ = after.load()
        changed = []
        for y in range(160):
            for x in range(240):
                if bp[x, y] != ap_[x, y]:
                    changed.append((x, y))
        print(f"\n  screen pixels changed by the overlay: {len(changed)}")
        hit = 0
        miss_blank = 0
        miss_paint = 0
        painted = 0
        for x, y in changed:
            colour = layer[(y + voffs) % 256][(x + hoffs) % 256]
            if colour == (0, 0, 0):
                miss_blank += 1
            else:
                painted += 1
        print(f"  of those, overlay paints a non-transparent pixel: {painted}")
        print(f"  overlay pixel transparent but screen changed: {miss_blank}")

        # the reverse direction: every non-blank overlay cell should show up
        blank_cells = 0
        painted_cells = 0
        for y in range(160):
            for x in range(240):
                colour = layer[(y + voffs) % 256][(x + hoffs) % 256]
                if colour == (0, 0, 0):
                    blank_cells += 1
                elif bp[x, y] != ap_[x, y]:
                    painted_cells += 1
        print(f"  screen pixels where the overlay paints but did not change: "
              f"{painted - painted_cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
