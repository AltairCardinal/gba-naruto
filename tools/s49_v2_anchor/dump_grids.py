#!/usr/bin/env python3
"""Wave 9 / V2: dump the original's and the remake's overlay at 8 px
granularity, next to the battle-14 terrain.

Answers one question per run:

    "What exactly is in each side's overlay buffer, and where does it sit in
     map space?"

Usage::

    python tools/s49_v2_anchor/dump_grids.py --vram <dump.bin>
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from compare_overlay_families import (  # noqa: E402
    find_overlay_map,
    remake_entry_map,
    remake_family,
    remake_terrain,
)
from overlay_ground_truth import load_moment  # noqa: E402

SHORT = {
    "blank": ".",
    "edge": "E",
    "hatch": "H",
    "line_alt": "A",
    "band": "B",
    "hatch_shift": "h",
    "solid": "S",
    "other": "?",
}


def original_8px(name: str) -> list[list[str]]:
    moment = load_moment(name)
    return [[moment.cells[y * 32 + x]["family"] for x in range(32)]
            for y in range(32)]


def remake_8px(vram: bytes) -> list[list[str]] | None:
    base = find_overlay_map(vram)
    if base < 0:
        return None
    entry_map = remake_entry_map(vram, base)
    return [[remake_family(entry_map[y][x])[0] for x in range(32)]
            for y in range(32)]


def show(title: str, grid: list[list[str]]) -> None:
    print(f"--- {title} (8 px entries, 32 x 32)")
    for y, row in enumerate(grid):
        print(f"  r{y:2d} " + "".join(SHORT.get(f, "?") for f in row))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--moment", default="field-frame-v1")
    args = ap.parse_args()

    terrain = remake_terrain()
    print("--- terrain (15 battle cols x 19 rows)")
    for y, row in enumerate(terrain):
        print(f"  r{y:2d} " + "".join(str(v) for v in row))

    show(f"original {args.moment}", original_8px(args.moment))

    remake = remake_8px(args.vram.read_bytes())
    if remake is None:
        print("--- remake: no overlay map in this frame")
    else:
        show("remake", remake)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
