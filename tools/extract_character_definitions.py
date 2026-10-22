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
NEXT_GROWTH_TABLE_FILE = 0x545068
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
                "active_flag": raw[0],
                "active_flag_hex": raw[0:1].hex(),
                "template_02_base": raw[1],
                "template_02_base_hex": raw[1:2].hex(),
                "template_03_base": raw[2],
                "template_03_base_hex": raw[2:3].hex(),
                "template_04_base": raw[3],
                "template_04_base_hex": raw[3:4].hex(),
                "template_05_base": raw[4],
                "template_05_base_hex": raw[4:5].hex(),
                "template_06_base": raw[5],
                "template_06_base_hex": raw[5:6].hex(),
                "ninja_tool_capacity_base": raw[5],
                "ninja_tool_capacity_base_hex": raw[5:6].hex(),
                "template_08_base": raw[6],
                "template_08_base_hex": raw[6:7].hex(),
                "chakra_capacity_base": raw[6],
                "chakra_capacity_base_hex": raw[6:7].hex(),
                "reserved_07": raw[7],
                "reserved_07_hex": raw[7:8].hex(),
                "template_0a_base": int.from_bytes(raw[8:10], "little"),
                "template_0a_base_hex": raw[8:10].hex(),
                "template_0e_base": int.from_bytes(raw[10:12], "little"),
                "template_0e_base_hex": raw[10:12].hex(),
                "primary_slots_raw_hex": raw[0x0C:0x48].hex(),
                "secondary_slots_raw_hex": raw[0x48:0xA8].hex(),
                "filtered_candidate_ids_hex": raw[0xA8:0xB1].hex(),
                "tail_raw_hex": raw[0xB1:0xB4].hex(),
                "primary_slots": [
                    {"slot": i, "id": raw[0x0C + i * 4],
                     "initial_state": raw[0x0D + i * 4],
                     "unlock_level": raw[0x0E + i * 4],
                     "reserved": raw[0x0F + i * 4]}
                    for i in range(15)
                ],
                "secondary_slots": [
                    {"slot": i, "id": raw[0x48 + i * 4],
                     "initial_state": raw[0x49 + i * 4],
                     "unlock_level": raw[0x4A + i * 4],
                     "reserved": raw[0x4B + i * 4]}
                    for i in range(24)
                ],
                "raw_hex": raw.hex(),
                "active": any(raw),
            }
        )

    return {
        "version": 3,
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
                "Base-value destinations and the two four-byte slot arrays are proven by "
                "0x0806D4A0/0x0806D964. The character overview renderer at 0x08089AE0 "
                "provides the player-facing stat names."
            ),
            "fields": [
                {"name": "active_flag", "type": "u8", "offset": 0, "size": 1},
                {"name": "template_02_base", "type": "u8", "offset": 1, "size": 1},
                {"name": "template_03_base", "type": "u8", "offset": 2, "size": 1},
                {"name": "template_04_base", "type": "u8", "offset": 3, "size": 1},
                {"name": "template_05_base", "type": "u8", "offset": 4, "size": 1},
                {"name": "template_06_base", "type": "u8", "offset": 5, "size": 1},
                {"name": "template_08_base", "type": "u8", "offset": 6, "size": 1},
                {"name": "reserved_07", "type": "u8", "offset": 7, "size": 1},
                {"name": "template_0a_base", "type": "u16", "offset": 8, "size": 2},
                {"name": "template_0e_base", "type": "u16", "offset": 10, "size": 2},
                {"name": "primary_slots_raw_hex", "type": "bytes", "offset": 12, "size": 60},
                {"name": "secondary_slots_raw_hex", "type": "bytes", "offset": 72, "size": 96},
                {"name": "filtered_candidate_ids_hex", "type": "bytes", "offset": 168, "size": 9},
                {"name": "tail_raw_hex", "type": "bytes", "offset": 177, "size": 3},
                {"name": "raw_hex", "type": "bytes", "offset": 0, "size": CHARACTER_DEFINITION_STRIDE},
            ],
        },
        "player_visible_semantics": {
            "template_02": "attack_power",
            "template_03": "defense_power",
            "template_04": "agility",
            "template_05": "movement",
            "template_06": "ninja_tool_capacity",
            "template_08": "chakra_capacity",
            "template_0a": "hand_seals",
            "template_0e": "max_hp",
            "template_10": "experience",
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
            "the record. Runtime evidence connects character_id=1 to ROM record "
            "0x5424D0, proves template-to-battle-slot copying, and shows byte "
            "0x5424D1 changes runtime template payload byte +1. A same-boundary character "
            "overview screenshot and EWRAM dump correlate the visible statistics. The same "
            "page's renderer at 0x08089B82..0x08089C9A draws labels in the order max HP, "
            "chakra, attack, defense, agility, movement, ninja tools while reading template "
            "+0E,+08,+02,+03,+04,+05,+06, proving +08 chakra and +06 ninja-tool capacity."
        ),
        "entries": entries,
        "verification": "runtime_verified",
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
