#!/usr/bin/env python3
"""Scan the original ROM's battle formation matrix for the per-unit
``battle_experience`` seed (record offset +0x0C).

The original's settlement screen row 2 is 「戰鬥分」.  The shared tree's
``tools/extract_positions.py`` proves the formation matrix layout::

    0x5461C4 + group_id*0x1AAC + variant_id*0x08E4 + 4 + record_id*0x0B8

and that ``battle_experience`` is the u16 at record offset ``+0x0C``.

This tool answers one question:

    *Which (battle, variant, slot) formation records carry a non-zero
    ``battle_experience``, and what are the values?*

Usage::

    python tools/s49_w20e2/e2_scan_formation_exp.py <rom>
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

POSITION_TABLE_FILE = 0x5461C4
GROUP_STRIDE = 0x1AAC
VARIANT_STRIDE = 0x08E4
RECORD_STRIDE = 0x00B8
RECORD_HEADER = 4
X_OFFSET = 2
Y_OFFSET = 3
BATTLE_EXPERIENCE_OFFSET = 0x0C
UNIT_PARAMETER_OFFSET = 0x0E
LEVEL_OFFSET = 0x0F
GROUP_COUNT = 48
VARIANT_COUNT = 3
RECORD_COUNT = 12


def record_offset(group_id: int, variant_id: int, record_id: int) -> int:
    return (
        POSITION_TABLE_FILE
        + group_id * GROUP_STRIDE
        + variant_id * VARIANT_STRIDE
        + RECORD_HEADER
        + record_id * RECORD_STRIDE
    )


def main() -> int:
    rom_path = pathlib.Path(sys.argv[1])
    rom = rom_path.read_bytes()
    print(f"rom        : {rom_path}")
    print(f"rom sha256 : {hashlib.sha256(rom).hexdigest()}")
    print(f"rom bytes  : {len(rom)}")
    print()

    hits: list[tuple[int, int, int, int, int, int, int, int]] = []
    for group in range(GROUP_COUNT):
        for variant in range(VARIANT_COUNT):
            for record in range(RECORD_COUNT):
                off = record_offset(group, variant, record)
                raw = rom[off:off + RECORD_STRIDE]
                selector = raw[0]
                side = raw[1]
                x = raw[X_OFFSET]
                y = raw[Y_OFFSET]
                exp = int.from_bytes(
                    raw[BATTLE_EXPERIENCE_OFFSET:
                        BATTLE_EXPERIENCE_OFFSET + 2], "little")
                level = raw[LEVEL_OFFSET]
                if exp == 0:
                    continue
                hits.append((group, variant, record, selector, side, x, y, exp))
                print(
                    f"group={group:>2} variant={variant} record={record:>2} "
                    f"selector={selector:>3} side={side} "
                    f"pos=({x},{y}) level={level} battle_exp={exp}"
                )
    print()
    print(f"non-zero battle_experience records: {len(hits)}")
    values = sorted({hit[7] for hit in hits})
    print(f"distinct values: {values}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
