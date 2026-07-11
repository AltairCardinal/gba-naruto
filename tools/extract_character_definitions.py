#!/usr/bin/env python3
"""Extract the ROM-backed character definition table into the units bank.

The table identity is established in ``notes/character-definition-source-20260711.md``:
``0x0806D4A0`` indexes ``0x0854241C + character_id * 0xB4`` while creating
WRAM character templates.  JSON is written to stdout by default; ``--bank``
atomically replaces a bank file.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


CHARACTER_DEFINITIONS_FILE = 0x54241C
CHARACTER_DEFINITION_STRIDE = 0x00B4
CHARACTER_DEFINITION_COUNT = 63
CHARACTER_DEFINITIONS_END = (
    CHARACTER_DEFINITIONS_FILE
    + CHARACTER_DEFINITION_COUNT * CHARACTER_DEFINITION_STRIDE
)
NEXT_GROWTH_TABLE_FILE = 0x54507A
POST_TABLE_GAP_SIZE = NEXT_GROWTH_TABLE_FILE - CHARACTER_DEFINITIONS_END

WRAM_TEMPLATE_POOL = 0x02022E34
WRAM_TEMPLATE_STRIDE = 0x00BC
WRAM_TEMPLATE_COUNT = 24
WRAM_UNIT_ARRAY = 0x020240C0
WRAM_UNIT_STRIDE = 0x01D4


def record_offset(character_id: int) -> int:
    """Return the file offset of one character definition record."""
    return CHARACTER_DEFINITIONS_FILE + character_id * CHARACTER_DEFINITION_STRIDE


def extract_character_definitions(rom: bytes) -> dict[str, Any]:
    """Parse all character definition records losslessly from the baseline ROM."""
    if len(rom) < NEXT_GROWTH_TABLE_FILE:
        raise ValueError(
            "ROM too small for character definitions: "
            f"need 0x{NEXT_GROWTH_TABLE_FILE:X}, got 0x{len(rom):X}"
        )

    post_table_gap = rom[CHARACTER_DEFINITIONS_END:NEXT_GROWTH_TABLE_FILE]

    entries: list[dict[str, Any]] = []
    for character_id in range(CHARACTER_DEFINITION_COUNT):
        offset = record_offset(character_id)
        raw = rom[offset:offset + CHARACTER_DEFINITION_STRIDE]
        entries.append(
            {
                "id": f"character_{character_id:02d}",
                "character_id": character_id,
                "_index": character_id,
                "_raw_offset": offset,
                "rom_offset": offset,
                "rom_offset_hex": f"0x{offset:06X}",
                "field_00": raw[0],
                "field_00_hex": raw[0:1].hex(),
                "field_01": raw[1],
                "field_01_hex": raw[1:2].hex(),
                "field_02": raw[2],
                "field_02_hex": raw[2:3].hex(),
                "field_03": raw[3],
                "field_03_hex": raw[3:4].hex(),
                "raw_hex": raw.hex(),
                "active": any(raw),
            }
        )

    return {
        "version": 2,
        "description": (
            "ROM-backed character definition records. This replaces the legacy "
            "0x53F298 units identity, whose character-ID interpretation was disproven."
        ),
        "table_offset": CHARACTER_DEFINITIONS_FILE,
        "table_offset_hex": f"0x{CHARACTER_DEFINITIONS_FILE:06X}",
        "entry_size": CHARACTER_DEFINITION_STRIDE,
        "entry_count": CHARACTER_DEFINITION_COUNT,
        "entry_format": {
            "description": (
                "Lossless 0xB4 character definition records indexed by character_id. "
                "Only the first four bytes are exposed as conservative raw fields; "
                "remaining bytes are retained in raw_hex until field semantics are proven."
            ),
            "fields": [
                {"name": "field_00", "type": "u8", "offset": 0, "size": 1},
                {"name": "field_01", "type": "u8", "offset": 1, "size": 1},
                {"name": "field_02", "type": "u8", "offset": 2, "size": 1},
                {"name": "field_03", "type": "u8", "offset": 3, "size": 1},
                {"name": "raw_hex", "type": "bytes", "offset": 0, "size": CHARACTER_DEFINITION_STRIDE},
            ],
        },
        "format": {
            "address_formula": "0x54241C + character_id*0xB4",
            "character_id_range": "0..62",
            "record_stride": CHARACTER_DEFINITION_STRIDE,
            "table_end": CHARACTER_DEFINITIONS_END,
            "table_end_hex": f"0x{CHARACTER_DEFINITIONS_END:06X}",
            "next_growth_table": NEXT_GROWTH_TABLE_FILE,
            "next_growth_table_hex": f"0x{NEXT_GROWTH_TABLE_FILE:06X}",
            "post_table_gap_size": POST_TABLE_GAP_SIZE,
            "post_table_gap_hex": post_table_gap.hex(),
            "post_table_zero_prefix": len(post_table_gap) - len(post_table_gap.lstrip(b"\x00")),
        },
        "wram_template_pool": {
            "address": f"0x{WRAM_TEMPLATE_POOL:08X}",
            "slots": WRAM_TEMPLATE_COUNT,
            "stride": WRAM_TEMPLATE_STRIDE,
        },
        "wram_unit_array": {
            "address": f"0x{WRAM_UNIT_ARRAY:08X}",
            "stride": WRAM_UNIT_STRIDE,
        },
        "notes": (
            "Character_id is the table index used by code, not a byte read from "
            "the record. Runtime evidence still needs to connect a successful "
            "battle-slot sample back to this ROM source before upgrading to "
            "runtime_verified."
        ),
        "entries": entries,
        "verification": "code_verified",
        "evidence": "notes/character-definition-source-20260711.md",
        "extraction": {
            "tool": "tools/extract_character_definitions.py",
            "extracted_count": CHARACTER_DEFINITION_COUNT,
            "rom_offset": CHARACTER_DEFINITIONS_FILE,
            "rom_offset_hex": f"0x{CHARACTER_DEFINITIONS_FILE:06X}",
        },
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

    bank = extract_character_definitions(args.rom.read_bytes())
    if args.bank:
        write_json_atomic(args.bank, bank)
        print(f"wrote {len(bank['entries'])} records to {args.bank}")
    else:
        json.dump(bank, __import__("sys").stdout, ensure_ascii=False, indent=2)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
