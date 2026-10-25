#!/usr/bin/env python3
"""Decode the original's 32 overlay tiles and learn the variant rule.

The tile graphics come from the remake's own generated header
(``generated_battle_movegrid_overlay_content.h``), which carries the ROM's
1024 bytes of 4bpp overlay tiles (32 tiles x 8 rows x 4 bytes).

The variant rule is learned from the exported ground truth: for every logical
16x16 cell of the four moments, the four 8x8 quadrant tiles are known, and so
are the families of the neighbouring cells.  The script prints, per family,
which quadrant tile each cell used and how that correlates with the
neighbourhood.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "s49_rule_probe"))

from overlay_ground_truth import (  # noqa: E402
    LOGICAL_COLS,
    LOGICAL_ROWS,
    MAP_COLS,
    MOMENTS,
    load_moment,
)

REMAKE_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\generated_battle_movegrid_overlay_content.h"
)

FAMILY_OF = {}
for _t in (256, 257, 282, 283, 284, 285, 286, 287):
    FAMILY_OF[_t] = "blank"
for _t in range(258, 262):
    FAMILY_OF[_t] = "edge"
for _t in range(262, 266):
    FAMILY_OF[_t] = "hatch"
for _t in range(266, 270):
    FAMILY_OF[_t] = "line_alt"
for _t in range(270, 274):
    FAMILY_OF[_t] = "band"
for _t in range(274, 278):
    FAMILY_OF[_t] = "hatch_shift"
for _t in range(278, 282):
    FAMILY_OF[_t] = "solid"

QUADRANT_ORDER = ((0, 0), (1, 0), (0, 1), (1, 1))  # tl, tr, bl, br


def load_tile_bytes() -> bytes:
    text = REMAKE_HEADER.read_text(encoding="utf-8")
    body = text.split("battle_movegrid_overlay_tile_data = {{", 1)[1]
    body = body.split("}};", 1)[0]
    return bytes(int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]{2}", body))


def decode_tile(raw: bytes, index: int) -> list[list[int]]:
    base = (index - 256) * 32
    rows = []
    for y in range(8):
        start = base + y * 4
        row = []
        for byte in raw[start:start + 4]:
            row.append(byte & 0x0F)
            row.append((byte >> 4) & 0x0F)
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tiles", action="store_true")
    args = ap.parse_args()

    raw = load_tile_bytes()
    print(f"tile data: {len(raw)} bytes")

    if args.tiles:
        for index in range(256, 288):
            art = decode_tile(raw, index)
            family = FAMILY_OF.get(index, "?")
            colours = sorted({v for row in art for v in row})
            print(f"\n--- tile {index}  family {family}  colours {colours} ---")
            for y, row in enumerate(art):
                print("    " + "".join(
                    "." if v == 0 else str(v) for v in row))

    # ---- variant rule -----------------------------------------------------
    print("\n=== variant usage per family (quadrant tile -> count) ===")
    usage: dict[str, Counter] = defaultdict(Counter)
    quad_usage: dict[str, Counter] = defaultdict(Counter)
    for name in MOMENTS:
        moment = load_moment(name)
        for ly in range(LOGICAL_ROWS):
            for lx in range(LOGICAL_COLS):
                quads = moment.quadrants(lx, ly)
                family = moment.cell_family(lx, ly)
                tiles = tuple(q[3] for q in quads)
                usage[family][tiles] += 1
                for (qx, qy), (_tx, _ty, _fam, tile) in zip(QUADRANT_ORDER, quads):
                    quad_usage[family][(qx, qy, tile)] += 1

    for family in sorted(usage):
        print(f"\n  {family}:")
        for tiles, count in usage[family].most_common():
            print(f"    tiles {tiles}  x{count}")
        print(f"    per quadrant:")
        for quadrant in QUADRANT_ORDER:
            entries = {tile: c for (qx, qy, tile), c in quad_usage[family].items()
                       if (qx, qy) == quadrant}
            print(f"      {quadrant}: " + ", ".join(
                f"tile{t}={c}" for t, c in sorted(entries.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
