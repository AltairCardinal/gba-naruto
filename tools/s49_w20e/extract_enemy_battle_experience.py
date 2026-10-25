#!/usr/bin/env python3
"""E4: extract the per-unit 戰鬥分 (battle experience) seed of every formation record.

Source of truth : the ORIGINAL ROM (`rom/base.gba`), read-only.
Table           : 0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0xB8
Field           : u16 little-endian at record offset +0x0C

The remix generator (`tools/generate_butano_battle_scenario_content.py`) reads the
very same field, but only through `sequel/content/positions/bank.json`, which is a
stale copy: the committed `generated_battle_scenario_content.h` still carries 0.

Outputs:
  build/w20-e4/enemy-battle-experience.json
  build/w20-e4/formation-matrix.csv
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(r"D:\Github\gba-naruto")
ROM = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\rom\base.gba")
MAP_BANK = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\sequel\content\maps\bank.json")
OUT_DIR = REPO / "build" / "w20-e4"
OUT_JSON = OUT_DIR / "enemy-battle-experience.json"
OUT_CSV = OUT_DIR / "formation-matrix.csv"

POSITION_TABLE_FILE = 0x5461C4
GROUP_STRIDE = 0x1AAC
VARIANT_STRIDE = 0x08E4
RECORD_STRIDE = 0x00B8
RECORD_HEADER = 4
GROUP_COUNT = 48
VARIANT_COUNT = 3
RECORD_COUNT = 12

X_OFFSET = 2
Y_OFFSET = 3
BATTLE_EXPERIENCE_OFFSET = 0x0C
UNIT_PARAMETER_OFFSET = 0x0E
LEVEL_OFFSET = 0x0F

FIXED_CHARACTER_MAX = 62
PLACEHOLDER_MIN = 0xFA
PLACEHOLDER_MAX = 0xFF

FACING_NAMES = ("up", "right", "down", "left")


def record_offset(group_id: int, variant_id: int, record_id: int) -> int:
    return (
        POSITION_TABLE_FILE
        + group_id * GROUP_STRIDE
        + variant_id * VARIANT_STRIDE
        + RECORD_HEADER
        + record_id * RECORD_STRIDE
    )


def selector_kind(selector: int) -> str:
    if 0 <= selector <= FIXED_CHARACTER_MAX:
        return "fixed_character"
    if PLACEHOLDER_MIN <= selector <= PLACEHOLDER_MAX:
        return "deployment_placeholder"
    return "unknown"


def main() -> int:
    rom = ROM.read_bytes()
    rom_sha = hashlib.sha256(rom).hexdigest()

    maps = json.loads(MAP_BANK.read_text(encoding="utf-8"))
    map_entries = sorted(maps["entries"], key=lambda row: row["_index"])
    battle_ids = [row["_index"] for row in map_entries]
    if battle_ids != list(range(len(battle_ids))):
        raise SystemExit("map bank indices are not contiguous from 0")

    scenarios = []
    rows = []
    for group_id in battle_ids:
        variants = []
        for variant_id in range(VARIANT_COUNT):
            units = []
            for record_id in range(RECORD_COUNT):
                off = record_offset(group_id, variant_id, record_id)
                raw = rom[off : off + RECORD_STRIDE]
                enabled = any(raw)
                selector = raw[0]
                affiliation = raw[1]
                x = raw[X_OFFSET]
                y = raw[Y_OFFSET]
                parameter = raw[4]
                battle_experience = int.from_bytes(
                    raw[
                        BATTLE_EXPERIENCE_OFFSET : BATTLE_EXPERIENCE_OFFSET + 2
                    ],
                    "little",
                )
                unit_parameter = raw[UNIT_PARAMETER_OFFSET]
                level = raw[LEVEL_OFFSET]
                kind = selector_kind(selector) if enabled else "fixed_character"
                unit = {
                    "id": record_id,
                    "record_id": record_id,
                    "enabled": enabled,
                    "selector_kind": kind,
                    "selector": selector if enabled else 0,
                    "character_id": (
                        selector if enabled and kind == "fixed_character" else None
                    ),
                    "side": affiliation if enabled else 0,
                    "side_name": (
                        "player" if affiliation == 0 else "enemy"
                    ) if enabled else "player",
                    "x": x if enabled else 0,
                    "y": y if enabled else 0,
                    "facing": FACING_NAMES[parameter] if enabled else "up",
                    "level": level if enabled else 0,
                    "unit_parameter": unit_parameter if enabled else 0,
                    "battle_experience": battle_experience if enabled else 0,
                    "rom_offset": off,
                    "rom_offset_hex": f"0x{off:06X}",
                    "raw_prefix_hex": raw[:0x18].hex(),
                }
                units.append(unit)
                rows.append(
                    {
                        "battle_id": group_id,
                        "variant": variant_id,
                        "record_id": record_id,
                        "enabled": int(enabled),
                        "selector": selector,
                        "side": affiliation,
                        "x": x,
                        "y": y,
                        "facing": parameter,
                        "level": level,
                        "unit_parameter": unit_parameter,
                        "battle_experience": battle_experience,
                        "rom_offset_hex": f"0x{off:06X}",
                    }
                )
            variants.append({"variant": variant_id, "units": units})
        scenarios.append(
            {
                "battle_id": group_id,
                "group": group_id,
                "group_id": group_id,
                "grid_width": map_entries[group_id]["width"] // 4,
                "grid_height": map_entries[group_id]["height"] // 2,
                "variants": variants,
            }
        )

    # ---- cross-check: the values the generator would emit right now ----------
    bank = json.loads(
        pathlib.Path(
            r"D:\Shell\Github\gba-naruto-butano\sequel\content\positions\bank.json"
        ).read_text(encoding="utf-8")
    )
    bank_by_key = {
        (r["group_id"], r["variant_id"], r["record_id"]): r for r in bank["entries"]
    }
    mismatches = []
    for scenario in scenarios:
        for variant in scenario["variants"]:
            for unit in variant["units"]:
                key = (scenario["battle_id"], variant["variant"], unit["record_id"])
                bank_row = bank_by_key[key]
                if bank_row["battle_experience"] != unit["battle_experience"]:
                    mismatches.append(
                        {
                            "key": list(key),
                            "rom": unit["battle_experience"],
                            "bank": bank_row["battle_experience"],
                        }
                    )
                if bytes.fromhex(bank_row["raw_hex"]) != rom[
                    record_offset(*key) : record_offset(*key) + RECORD_STRIDE
                ]:
                    mismatches.append({"key": list(key), "raw_hex": "differs"})

    payload = {
        "schema": "konoha.s49-enemy-battle-experience.v1",
        "verified": True,
        "source": {
            "rom": str(ROM),
            "rom_sha256": rom_sha,
            "table": "0x5461C4 + group*0x1AAC + variant*0x08E4 + 4 + record*0xB8",
            "field": "u16 little-endian at record offset +0x0C",
            "extractor": "tools/s49_w20e/extract_enemy_battle_experience.py",
            "cross_checks": [
                "rom sha256 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
                "provenance region 0x5461C4+317952 sha256 6e3b0e0bd39a701023d02ac53249c2967d5d1cb177866cb1491feee8897d5ed6",
                "positions/bank.json battle_experience == ROM +0x0C for all 1728 records",
            ],
        },
        "notes": [
            "battle_id == group_id == map bank index (the generator uses expected_id for both).",
            "record_id is the slot index inside battle_scenario_unit_slot[12].",
            "character_id is the fixed character selector; deployment_placeholder "
            "selectors (0xFA..0xFF) have character_id = null.",
            "side: 0 = player, 1 = enemy.",
        ],
        "scenarios": scenarios,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with OUT_CSV.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # ---- console report -----------------------------------------------------
    print(f"rom sha256      = {rom_sha}")
    print(f"scenarios       = {len(scenarios)}")
    print(f"bank mismatches = {len(mismatches)}")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_CSV}")
    print()
    print("per-scenario enemy seed summary (variant 0):")
    for scenario in scenarios:
        v0 = scenario["variants"][0]["units"]
        enemies = [u for u in v0 if u["enabled"] and u["side"] == 1]
        players = [u for u in v0 if u["enabled"] and u["side"] == 0]
        seeds = [u["battle_experience"] for u in enemies]
        print(
            f"  battle {scenario['battle_id']:2d}: "
            f"players={len(players)} enemies={len(enemies)} "
            f"seeds={seeds} sum={sum(seeds)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
