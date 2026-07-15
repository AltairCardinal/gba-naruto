#!/usr/bin/env python3
"""Extract the 94 skill/technique templates consumed by 0x0806D910."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TABLE_OFFSET = 0x545BE4
TABLE_END = 0x5461C4
ENTRY_SIZE = 16
ENTRY_COUNT = (TABLE_END - TABLE_OFFSET) // ENTRY_SIZE


def build_bank(rom: bytes) -> dict:
    fields = []
    for i in range(10):
        destination = 1 if i == 0 else i if i >= 2 else None
        description = (
            "Legacy column name; source +0 is copied to runtime +1 by 0x0806D910"
            if i == 0 else
            "Legacy column name; source +1 is not copied by 0x0806D910"
            if i == 1 else
            f"Copied to runtime skill structure +0x{i:02X} by 0x0806D910"
        )
        fields.append({
            "offset": i, "size": 1, "name": f"runtime_byte_{i:02x}", "type": "u8",
            "description": description, "initializer_destination": destination,
        })
    fields += [
        {"offset": i, "size": 1, "name": f"tail_byte_{i:02x}", "type": "u8",
         "description": "Not copied by the known 0x0806D910 initializer"}
        for i in range(10, 16)
    ]
    fields[10]["description"] = "Not copied by the initializer; compared by relationship-table consumer 0x0808FF7C"
    fields[10]["separate_consumer"] = "0x0808FF7C"
    fields[11]["description"] = "Not copied by the initializer; read by relationship-table consumer 0x0808FF88"
    fields[11]["separate_consumer"] = "0x0808FF88"
    semantic_names = {
        0x00: "display_animation_family",
        0x04: "attack_power",
        0x05: "distance",
        0x06: "success_rate_percent",
        0x07: "hit_count_and_line_shape",
        0x08: "range",
        0x0A: "parent_skill_id",
        0x0B: "eligible_candidate_id",
        0x0C: "eligibility_whitelist_id_0",
        0x0D: "eligibility_whitelist_id_1",
    }
    for offset, semantic in semantic_names.items():
        fields[offset]["semantic"] = semantic
    fields[0]["separate_consumers"] = ["0x08078F16", "0x080953B4"]
    fields[4]["description"] = (
        "Attack power shown by the natural technique detail panel; copied to runtime +4"
    )
    fields[5]["description"] = (
        "Technique distance shown by the natural detail panel; copied to runtime +5"
    )
    fields[6]["description"] = (
        "Success-rate percentage shown by the natural detail panel; copied to runtime +6"
    )
    fields[7]["description"] = (
        "Packed hit count and line-shape flag; skill 1 value 0x83 renders x3 and straight"
    )
    fields[8]["description"] = (
        "Technique range shown by the natural detail panel; copied to runtime +8"
    )
    fields[12]["description"] = (
        "First eligibility whitelist ID; zero means unrestricted in 0x0808FC20"
    )
    fields[12]["separate_consumer"] = "0x0808FC20"
    fields[13]["description"] = (
        "Optional second eligibility whitelist ID checked by 0x0808FC20"
    )
    fields[13]["separate_consumer"] = "0x0808FC20"
    entries = []
    for skill_id in range(ENTRY_COUNT):
        offset = TABLE_OFFSET + skill_id * ENTRY_SIZE
        raw = rom[offset:offset + ENTRY_SIZE]
        if len(raw) != ENTRY_SIZE:
            raise ValueError(f"ROM ends before skill template {skill_id}")
        entry = {
            "skill_id": skill_id, "_index": skill_id, "_raw_offset": offset,
            "rom_offset": offset, "rom_offset_hex": f"0x{offset:X}", "raw_hex": raw.hex(),
        }
        for field in fields:
            name, field_offset = field["name"], field["offset"]
            entry[name] = raw[field_offset]
            entry[f"{name}_hex"] = raw[field_offset:field_offset + 1].hex()
            semantic = field.get("semantic")
            if semantic:
                entry[semantic] = raw[field_offset]
                entry[f"{semantic}_hex"] = raw[field_offset:field_offset + 1].hex()
        entries.append(entry)
    return {
        "version": 3,
        "description": "94 skill/technique templates indexed by skill ID and initialized by Thumb 0x0806D910.",
        "table_offset": TABLE_OFFSET, "table_offset_hex": f"0x{TABLE_OFFSET:X}",
        "table_end": TABLE_END, "table_end_hex": f"0x{TABLE_END:X}",
        "entry_count": ENTRY_COUNT, "entry_size": ENTRY_SIZE,
        "verification": "runtime_verified",
        "verification_method": "Literals at 0x0806D960 and six other sites point to 0x08545BE4. A natural Naruto technique-list route ORed skill ID 1 with 0x80, hit the 0x08070906 initializer call, and copied row 0x545BF4 to EWRAM. Changing only source +4 from 6 to 7 changed the visible attack-power value from 6x3 to 7x3. Source +0 copies to runtime +1, source +1 is skipped, source +2..+9 copy to matching runtime offsets, and separate code at 0x0808FF7C/0x0808FF88 consumes source +A/+B.",
        "entry_format": {"fields": fields},
        "notes": (
            "The former 12-entry 0x546100 bank was a misbased slice beginning at physical "
            "record 81. Battle/UI consumers prove source +0 as a display/animation family, "
            "+A/+B as parent-skill to eligible-candidate relationships, and +C/+D as an "
            "optional two-ID eligibility whitelist. A natural skill-1 detail render maps "
            "+4 attack power, +5 distance, +6 success rate, packed +7 hit-count/line shape, "
            "and +8 range; +2/+3 and +9 remain unnamed."
        ),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sequel/content/skills/bank.json"))
    args = parser.parse_args()
    bank = build_bank(args.rom.read_bytes())
    args.output.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
    print(f"extracted {ENTRY_COUNT} skill templates: 0x{TABLE_OFFSET:X}..0x{TABLE_END:X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
