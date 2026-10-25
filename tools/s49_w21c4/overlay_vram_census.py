#!/usr/bin/env python3
"""Wave 21 / C4 -- VRAM overlay census (no emulator run).

Reads the savestates directly (``tools/s49_pairing/savestate.py`` ->
``tools/s49_victory_capture/s49_state.py``) and decodes the **overlay layer**:

* **original**: the overlay is BG2 -- 4bpp, palette bank 12, char base block 0,
  screen base block 2 -- so its tilemap sits at VRAM ``0x06001000`` and the
  family of every 16x16 logical cell is read from the tile indices with the
  vocabulary of ``tools/s49_rule_probe/overlay_ground_truth.py``.
* **remake**: the overlay has its own BG map, located by signature
  (``tools/s49_overlay_align/compare_overlay_families.find_overlay_map``).

Usage
-----
    python tools/s49_w21c4/overlay_vram_census.py \
        --original build/s49-package-w18/work/s49-report/capture-original \
        --remake  build/w20-e3/capture-remake \
        --out     build/w21-c4/overlay-vram-census.json
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

from s49_rule_probe.overlay_ground_truth import TILE_FAMILY, tile_family  # noqa: E402
from s49_overlay_align.compare_overlay_families import (  # noqa: E402
    find_overlay_map, remake_entry_map, remake_logical_cells, remake_terrain,
)

VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
ORIGINAL_BG2_TILEMAP = 0x06001000


def load_vram(path: pathlib.Path) -> bytes:
    from s49_pairing import savestate  # noqa: WPS433
    state = savestate.load(path)
    return state.read_memory(VRAM_BASE, VRAM_LENGTH)


def original_families(vram: bytes) -> dict:
    """The original's BG2 overlay as a family census."""
    import struct
    entries = struct.unpack_from("<1024H", vram, ORIGINAL_BG2_TILEMAP - VRAM_BASE)
    cells = Counter()
    lit = 0
    for entry in entries:
        tile = entry & 0x3FF
        family = tile_family(tile)
        cells[family] += 1
        if family != "blank":
            lit += 1
    return {"lit_entries": lit, "families": dict(cells)}


def remake_families(vram: bytes, terrain) -> dict:
    base = find_overlay_map(vram, terrain=terrain)
    if base < 0:
        return {"overlay_map": -1, "lit_entries": 0, "families": {}}
    entry_map = remake_entry_map(vram, base)
    cells = remake_logical_cells(entry_map)
    counter = Counter(cells.values())
    return {"overlay_map": base, "lit_entries": len(cells),
            "families": dict(counter)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--original", type=pathlib.Path, required=True)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    terrain = remake_terrain()
    document = {"schema": "konoha.s49-overlay-vram-census.v1", "original": {}, "remake": {}}

    for name in sorted(os.listdir(args.original)):
        if not name.endswith(".ss9"):
            continue
        try:
            vram = load_vram(args.original / name)
        except Exception as error:  # noqa: BLE001
            document["original"][name] = {"error": str(error)}
            continue
        document["original"][name] = original_families(vram)

    for name in sorted(os.listdir(args.remake)):
        if not name.endswith(".ss9"):
            continue
        try:
            vram = load_vram(args.remake / name)
        except Exception as error:  # noqa: BLE001
            document["remake"][name] = {"error": str(error)}
            continue
        document["remake"][name] = remake_families(vram, terrain)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=1)
        print(f"wrote {args.out}")
    for side in ("original", "remake"):
        print("=" * 90)
        print(side)
        for name, row in document[side].items():
            if "error" in row:
                print(f"  {name:22s} ERROR {row['error'][:60]}")
            elif side == "original":
                print(f"  {name:22s} lit={row['lit_entries']:5d} {row['families']}")
            else:
                print(f"  {name:22s} map=0x{row['overlay_map']:05x} lit={row['lit_entries']:5d} "
                      f"{row['families']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
