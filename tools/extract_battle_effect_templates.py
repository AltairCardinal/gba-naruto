#!/usr/bin/env python3
"""Extract 32 battle skill/effect templates consumed by 0x0806D85C."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TABLE_OFFSET = 0x545458
ENTRY_COUNT = 32
ENTRY_SIZE = 16


def build_bank(rom: bytes) -> dict:
    fields = [
        {"offset": i, "size": 1, "name": f"byte_{i:02x}", "type": "u8",
         "description": "Copied verbatim to the runtime effect structure"}
        for i in range(14)
    ]
    fields[12] = {
        "offset": 12, "size": 1, "name": "growth_target_type", "type": "u8",
        "description": "1..6 applies level growth to runtime byte +4..+9; 7 applies no growth",
    }
    fields.append({
        "offset": 14, "size": 2, "name": "per_level_growth", "type": "u16",
        "description": "Added as value * (level - 1) to the byte selected by growth_target_type",
    })
    entries = []
    for index in range(ENTRY_COUNT):
        offset = TABLE_OFFSET + index * ENTRY_SIZE
        raw = rom[offset:offset + ENTRY_SIZE]
        if len(raw) != ENTRY_SIZE:
            raise ValueError(f"ROM ends before effect template {index}")
        entry = {
            "effect_id": index, "_index": index, "_raw_offset": offset,
            "rom_offset": offset, "rom_offset_hex": f"0x{offset:X}", "raw_hex": raw.hex(),
        }
        for field in fields:
            start, size, name = field["offset"], field["size"], field["name"]
            value = int.from_bytes(raw[start:start + size], "little")
            entry[name] = value
            entry[f"{name}_hex"] = raw[start:start + size].hex()
        entries.append(entry)
    return {
        "version": 2,
        "description": "Battle skill/effect templates indexed by effect ID and consumed by Thumb 0x0806D85C.",
        "table_offset": TABLE_OFFSET, "table_offset_hex": f"0x{TABLE_OFFSET:X}",
        "entry_count": ENTRY_COUNT, "entry_size": ENTRY_SIZE,
        "verification": "runtime_verified",
        "verification_method": "0x0806D866 computes 0x08545458 + effect_id*16 and copies 16 bytes. A controlled effect-2 level-2 A/B changed +0x0E growth 1 to 2 and changed only the type-4 destination byte +7 from 4 to 5.",
        "entry_format": {"fields": fields},
        "notes": "Former u16 config/value/flag names were disproved; byte-level names are intentionally conservative.",
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sequel/content/battle-config/bank.json"))
    args = parser.parse_args()
    bank = build_bank(args.rom.read_bytes())
    args.output.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
    print(f"extracted {ENTRY_COUNT} effect templates at 0x{TABLE_OFFSET:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
