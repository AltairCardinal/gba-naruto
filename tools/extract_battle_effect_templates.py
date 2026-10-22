#!/usr/bin/env python3
"""Extract 87 active-action numeric templates consumed by 0x0806D85C."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TABLE_OFFSET = 0x545458
ENTRY_COUNT = 87
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
    semantic_names = {
        0x00: "cost_kind",
        0x01: "display_animation_family",
        0x02: "effect_type_and_flags",
        0x03: "target_policy_and_flags",
        0x04: "potency",
        0x05: "hit_count",
        0x06: "success_rate_percent",
        0x07: "distance_and_line_flags",
        0x08: "area_range_and_shape_flags",
        0x09: "duration_turns",
        0x0A: "resource_cost_low_byte",
        0x0B: "resource_cost_high_byte",
    }
    for offset, semantic in semantic_names.items():
        fields[offset]["semantic"] = semantic
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
            semantic = field.get("semantic")
            if semantic:
                entry[semantic] = value
                entry[f"{semantic}_hex"] = raw[start:start + size].hex()
        entry["effect_code"] = raw[2] & 0x3F
        entry["effect_flags"] = raw[2] & 0xC0
        entry["target_policy"] = raw[3] & 0x07
        entry["target_flags"] = raw[3] & 0xF8
        entry["resource_cost_u16"] = int.from_bytes(raw[10:12], "little")
        entry["resource_cost_value"] = entry["resource_cost_u16"]
        entries.append(entry)
    return {
        "version": 3,
        "description": "Active-action numeric templates indexed by action ID and consumed by Thumb 0x0806D85C.",
        "table_offset": TABLE_OFFSET, "table_offset_hex": f"0x{TABLE_OFFSET:X}",
        "entry_count": ENTRY_COUNT, "entry_size": ENTRY_SIZE,
        "verification": "runtime_verified",
        "verification_method": "0x0806D866 computes 0x08545458 + effect_id*16 and copies 16 bytes. A controlled effect-2 level-2 A/B changed +0x0E growth 1 to 2 and changed only the type-4 destination byte +7 from 4 to 5.",
        "entry_format": {
            "fields": fields,
            "derived_fields": {
                "effect_code": "byte_02 & 0x3F",
                "effect_flags": "byte_02 & 0xC0",
                "target_policy": "byte_03 & 0x07",
                "target_flags": "byte_03 & 0xF8",
                "resource_cost_u16": "little-endian u16 at +0x0A",
            },
        },
        "notes": "Rows 0..86 align one-to-one with the active-action text and character primary-slot IDs. Runtime +0 is the cost kind, +1 is the presentation family, +2/+3 pack effect and target policy independently, and +A/+B form the scalar resource cost. Unresolved flag bits retain neutral names.",
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sequel/content/battle-config/bank.json"))
    args = parser.parse_args()
    bank = build_bank(args.rom.read_bytes())
    args.output.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
    print(f"extracted {ENTRY_COUNT} active-action templates at 0x{TABLE_OFFSET:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
