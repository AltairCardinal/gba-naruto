#!/usr/bin/env python3
"""Extract ROM-backed battle formation positions into a content bank.

The address formula is statically proven in ``notes/positions-rom-source-20260710.md``.
By default JSON is written to stdout; ``--bank`` atomically replaces a bank file.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


POSITION_TABLE_FILE = 0x5461C4
GROUP_STRIDE = 0x1AAC
VARIANT_STRIDE = 0x08E4
RECORD_STRIDE = 0x00B8
RECORD_HEADER = 4
X_OFFSET = 2
Y_OFFSET = 3

# Three variants exactly fill a group: 3 * 0x8E4 == 0x1AAC.
GROUP_COUNT = 48
VARIANT_COUNT = 3
RECORD_COUNT = 12

WRAM_UNIT_ARRAY = 0x020240C0
WRAM_FIRST_USABLE_UNIT = 0x02024294
UNIT_STRIDE = 0x01D4


def record_offset(group_id: int, variant_id: int, record_id: int) -> int:
    """Return the file offset of one unique formation record."""
    return (
        POSITION_TABLE_FILE
        + group_id * GROUP_STRIDE
        + variant_id * VARIANT_STRIDE
        + RECORD_HEADER
        + record_id * RECORD_STRIDE
    )


def extract_positions(rom: bytes) -> dict[str, Any]:
    """Parse the complete 48 x 3 x 12 formation matrix from a baseline ROM."""
    last_end = record_offset(GROUP_COUNT - 1, VARIANT_COUNT - 1, RECORD_COUNT - 1) + RECORD_STRIDE
    if len(rom) < last_end:
        raise ValueError(
            f"ROM too small for positions matrix: need 0x{last_end:X}, got 0x{len(rom):X}"
        )

    entries: list[dict[str, Any]] = []
    for group_id in range(GROUP_COUNT):
        for variant_id in range(VARIANT_COUNT):
            for record_id in range(RECORD_COUNT):
                offset = record_offset(group_id, variant_id, record_id)
                raw = rom[offset : offset + RECORD_STRIDE]
                entries.append(
                    {
                        "id": f"g{group_id:02d}_v{variant_id}_r{record_id:02d}",
                        "_index": len(entries),
                        "_raw_offset": offset,
                        "group_id": group_id,
                        "variant_id": variant_id,
                        "record_id": record_id,
                        "rom_offset": offset,
                        "rom_offset_hex": f"0x{offset:06X}",
                        "selector": raw[0],
                        "affiliation": raw[1],
                        "x": raw[X_OFFSET],
                        "y": raw[Y_OFFSET],
                        "parameter": raw[4],
                        "aux_u32": int.from_bytes(raw[8:12], "little"),
                        "raw_hex": raw.hex(),
                        "active": any(raw),
                    }
                )

    return {
        "version": 2,
        "description": "ROM-backed battle formation and initial unit positions.",
        "table_offset": POSITION_TABLE_FILE,
        "table_offset_hex": f"0x{POSITION_TABLE_FILE:06X}",
        "entry_size": RECORD_STRIDE,
        "entry_count": len(entries),
        "entry_format": {
            "fields": [
                {"name": "group_id", "type": "u8"},
                {"name": "variant_id", "type": "u8"},
                {"name": "record_id", "type": "u8"},
                {"name": "selector", "type": "u8", "offset": 0, "size": 1},
                {"name": "affiliation", "type": "u8", "offset": 1, "size": 1},
                {"name": "x", "type": "u8", "offset": X_OFFSET, "size": 1},
                {"name": "y", "type": "u8", "offset": Y_OFFSET, "size": 1},
                {"name": "parameter", "type": "u8", "offset": 4, "size": 1},
                {"name": "aux_u32", "type": "u32", "offset": 8, "size": 4},
                {"name": "raw_hex", "type": "bytes"},
            ]
        },
        "format": {
            "address_formula": (
                "0x5461C4 + group_id*0x1AAC + variant_id*0x08E4 "
                "+ 4 + record_id*0xB8"
            ),
            "group_count": GROUP_COUNT,
            "group_stride": GROUP_STRIDE,
            "variant_count": VARIANT_COUNT,
            "variant_stride": VARIANT_STRIDE,
            "records_per_variant": RECORD_COUNT,
            "record_stride": RECORD_STRIDE,
            "fields": {
                "selector": {"offset": 0, "size": 1},
                "affiliation": {"offset": 1, "size": 1},
                "x": {"offset": X_OFFSET, "size": 1},
                "y": {"offset": Y_OFFSET, "size": 1},
                "parameter": {"offset": 4, "size": 1},
                "aux_u32": {"offset": 8, "size": 4},
            },
        },
        "wram_unit_array": {
            "address": f"0x{WRAM_UNIT_ARRAY:08X}",
            "first_usable_slot": f"0x{WRAM_FIRST_USABLE_UNIT:08X}",
            "stride": UNIT_STRIDE,
            "coordinate_fields": {
                "current_x": 0xC4,
                "current_y": 0xC5,
                "initial_or_target_x": 0xC7,
                "initial_or_target_y": 0xC8,
            },
        },
        "notes": (
            "Static consumer trace proves record +2/+3 feed unit x/y. The exact names "
            "of group_id, variant_id, selector, affiliation, parameter and aux_u32 remain "
            "provisional pending runtime traces. Zero records are retained for stable editing."
        ),
        "entries": entries,
        "verification": "static_verified",
        "evidence": "notes/positions-rom-source-20260710.md",
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON without leaving a partially replaced content bank."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="Baseline GBA ROM")
    parser.add_argument("--bank", type=Path, help="Optional bank.json destination")
    args = parser.parse_args()

    bank = extract_positions(args.rom.read_bytes())
    if args.bank:
        write_json_atomic(args.bank, bank)
        print(f"wrote {len(bank['entries'])} records to {args.bank}")
    else:
        json.dump(bank, __import__("sys").stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
