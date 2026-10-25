#!/usr/bin/env python3
"""W20-E2: cross-check E4's ROM forensics against the remake's data chain.

Chain under test:

    ROM formation record (+0x0C, u16 LE)
      -> reverse line ``sequel/content/positions/bank.json`` (``battle_experience``)
      -> generated header ``generated_battle_scenario_content.h``
        (``battle_scenario_unit_slot`` field #7)

Answers two questions:
  1. does the generated header already carry the ROM seed values?
  2. does the E4 extraction agree with the reverse line's bank.json?
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

REPO = pathlib.Path(r"D:\Github\gba-naruto")
REMAKE = pathlib.Path(r"D:\Shell\gba-naruto-butano")
E4_JSON = REPO / "build/w20-e4/enemy-battle-experience.json"
POSITIONS = REMAKE / "sequel/content/positions/bank.json"
HEADER = REMAKE / "butano-sequel/game/include/konoha/generated_battle_scenario_content.h"

SCENARIO_HEAD = re.compile(
    r"battle_scenario_definition\{\s*\n\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)U,"
)
INNER_ARRAY = "std::array<battle_scenario_unit_slot, 12>{{"
SLOT_RE = re.compile(
    r"battle_scenario_unit_slot\{\s*"
    r"(true|false),\s*scenario_selector_kind::(\w+),\s*(\d+),\s*"
    r"battle_side::(\w+),\s*grid_point\{\s*(\d+),\s*(\d+)\s*\},\s*"
    r"battle_facing::(\w+),\s*(\d+),"
)


def load_header_slots(path: pathlib.Path) -> dict[tuple[int, int, int], int]:
    """Parse (battle_id, variant, record) -> battle_experience from the header."""
    text = path.read_text(encoding="utf-8")
    out: dict[tuple[int, int, int], int] = {}
    for head in SCENARIO_HEAD.finditer(text):
        battle_id = int(head.group(1))
        region = text[head.end():]
        # the three variant arrays, in order
        starts = []
        cursor = 0
        for _ in range(3):
            index = region.find(INNER_ARRAY, cursor)
            if index < 0:
                break
            starts.append(index)
            cursor = index + len(INNER_ARRAY)
        for variant_index, start in enumerate(starts):
            end = (
                starts[variant_index + 1]
                if variant_index + 1 < len(starts)
                else region.find("\n        }}", start)
            )
            chunk = region[start:end]
            for record_index, slot in enumerate(SLOT_RE.finditer(chunk)):
                out[(battle_id, variant_index, record_index)] = int(slot.group(8))
    return out


def main() -> int:
    header_slots = load_header_slots(HEADER)
    positions = json.loads(POSITIONS.read_text(encoding="utf-8"))
    pos_map = {
        (r["group_id"], r["variant_id"], r["record_id"]): r.get("battle_experience")
        for r in positions["entries"]
    }

    print("=" * 78)
    print("A. generated header  vs  reverse-line positions/bank.json")
    print("=" * 78)
    missing = [k for k in pos_map if k not in header_slots]
    mismatch = [
        (k, pos_map[k], header_slots[k])
        for k in sorted(pos_map)
        if k in header_slots and header_slots[k] != pos_map[k]
    ]
    print(f"  bank.json records      : {len(pos_map)}")
    print(f"  header records parsed  : {len(header_slots)}")
    print(f"  missing in header      : {len(missing)} {missing[:6]}")
    print(f"  value mismatches       : {len(mismatch)}")
    for key, bank_value, header_value in mismatch[:15]:
        print(f"    {key}: bank={bank_value} header={header_value}")

    print()
    print("=" * 78)
    print("B. battle 14 — every variant, every record")
    print("=" * 78)
    for variant in range(3):
        for record in range(12):
            key = (14, variant, record)
            bank_value = pos_map.get(key)
            header_value = header_slots.get(key)
            if bank_value:
                flag = "OK " if bank_value == header_value else "DIFF"
                print(
                    f"  {flag} v{variant} rec{record:2d}: "
                    f"bank={bank_value:5d} header={header_value}"
                )

    print()
    print("=" * 78)
    print("C. E4 extraction  vs  reverse-line bank.json")
    print("=" * 78)
    e4 = pathlib.Path(E4_JSON)
    if not e4.is_file():
        print("  E4 JSON not found:", e4)
        return 0
    document = json.loads(e4.read_text(encoding="utf-8"))
    print("  schema  :", document.get("schema"))
    print("  verified:", document.get("verified"))
    print("  source  :", json.dumps(document.get("source"), ensure_ascii=False))
    scenarios = document.get("scenarios") or []
    print("  scenarios:", len(scenarios))
    agree = 0
    disagree = []
    for scenario in scenarios:
        battle_id = scenario.get("battle_id", scenario.get("group_id"))
        variant_id = scenario.get("variant_id", scenario.get("variant"))
        for unit in scenario.get("units", scenario.get("enemies", [])):
            record = unit.get("record_id", unit.get("record"))
            rom_value = unit.get("battle_experience")
            key = (battle_id, variant_id, record)
            bank_value = pos_map.get(key)
            if bank_value == rom_value:
                agree += 1
            else:
                disagree.append((key, rom_value, bank_value))
    print(f"  units compared        : {agree + len(disagree)}")
    print(f"  agree with bank.json  : {agree}")
    print(f"  disagree              : {len(disagree)}")
    for item in disagree[:15]:
        print("   ", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
