#!/usr/bin/env python3
"""Extract the code-referenced per-character growth table.

Thumb function ``0x0806D964`` computes the ordinary record address as
``0x08545068 + character_id * 0x10``.  Character IDs 57 and 58 are special:
they reuse records 8 and 15 respectively.  The physical table still occupies
63 records and ends exactly where the next known table starts at 0x545458.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any


TABLE_OFFSET = 0x545068
ENTRY_SIZE = 0x10
ENTRY_COUNT = 63
TABLE_END = TABLE_OFFSET + ENTRY_SIZE * ENTRY_COUNT
NEXT_TABLE_OFFSET = 0x545458

# Physical storage order.  Names describe the proven destination in the
# runtime template, not still-unproved player-facing labels.
FIELDS = (
    ("template_0e_growth", 0x0E),
    ("template_08_growth", 0x08),
    ("template_02_growth", 0x02),
    ("template_03_growth", 0x03),
    ("template_04_growth", 0x04),
    ("template_05_growth", 0x05),
    ("template_06_growth", 0x06),
    ("unused_0e", None),
)

SPECIAL_GROWTH_RECORDS = {57: 8, 58: 15}
PLAYER_LABELS = {
    0x00: "max_hp",
    0x02: "chakra_capacity",
    0x04: "attack_power",
    0x06: "defense_power",
    0x08: "agility",
    0x0A: "movement",
    0x0C: "ninja_tool_capacity",
}


def extract_entries(rom: bytes) -> list[dict[str, Any]]:
    if len(rom) < TABLE_END:
        raise ValueError(f"ROM ends before growth table end 0x{TABLE_END:X}")
    entries = []
    for character_id in range(ENTRY_COUNT):
        offset = TABLE_OFFSET + character_id * ENTRY_SIZE
        raw = rom[offset : offset + ENTRY_SIZE]
        values = struct.unpack("<8H", raw)
        entry: dict[str, Any] = {
            "character_id": character_id,
            "_index": character_id,
            "_raw_offset": offset,
            "rom_offset": offset,
            "rom_offset_hex": f"0x{offset:X}",
            "raw_hex": raw.hex(),
        }
        for (name, _target), value in zip(FIELDS, values):
            entry[name] = value
            entry[f"{name}_hex"] = struct.pack("<H", value).hex()
        aliases = [source for source, target in SPECIAL_GROWTH_RECORDS.items() if target == character_id]
        if aliases:
            entry["also_used_by_character_ids"] = aliases
        entries.append(entry)
    return entries


def build_bank(rom: bytes) -> dict[str, Any]:
    fields = []
    for index, (name, target) in enumerate(FIELDS):
        description = "Not read by the known 0x0806D964 growth path"
        if target is not None:
            description = (
                f"Added to runtime template +0x{target:02X} as "
                "value * (level - 1) / 100"
            )
        field = {
                "offset": index * 2,
                "size": 2,
                "name": name,
                "type": "u16",
                "description": description,
            }
        if index * 2 in PLAYER_LABELS:
            field["player_label"] = PLAYER_LABELS[index * 2]
        fields.append(field)
    return {
        "version": 2,
        "description": "Per-character level-growth records consumed by Thumb function 0x0806D964.",
        "table_offset": TABLE_OFFSET,
        "table_offset_hex": f"0x{TABLE_OFFSET:X}",
        "table_end": TABLE_END,
        "table_end_hex": f"0x{TABLE_END:X}",
        "entry_count": ENTRY_COUNT,
        "entry_size": ENTRY_SIZE,
        "verification": "runtime_verified",
        "verification_method": (
            "0x0806D98A computes character_id<<4 and adds literal 0x08545068; "
            "0x0806D9C0..0x0806DA4C consumes seven u16 fields and writes template fields. "
            "A controlled two-factor first-battle probe changed character 1 record +4 "
            "from 100 to 200 and changed only runtime template/battle-slot +2 from 15 to 16."
        ),
        "address_formula": "0x545068 + character_id * 0x10",
        "special_growth_record_aliases": {str(k): v for k, v in SPECIAL_GROWTH_RECORDS.items()},
        "entry_format": {"fields": fields},
        "notes": (
            "Fields are growth increments per 100 levels, applied with integer division to "
            "level-1. IDs 57 and 58 use physical records 8 and 15 at runtime. "
            "A same-boundary character overview screenshot/EWRAM dump identifies the visible "
            "statistics. Renderer 0x08089B82..0x08089C9A pairs its chakra label with template "
            "+08 and its ninja-tool label with template +06, identifying growth +02 as chakra "
            "capacity and growth +0C as ninja-tool capacity."
        ),
        "entries": extract_entries(rom),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("sequel/content/character-stats/bank.json")
    )
    args = parser.parse_args()
    bank = build_bank(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
    print(f"extracted {ENTRY_COUNT} growth records: 0x{TABLE_OFFSET:X}..0x{TABLE_END:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
