#!/usr/bin/env python3
"""Build a ROM-provenance catalog for battle characters and actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000

UNIT_NAME_TABLE = 0x08599280
UNIT_COUNT = 63

ACTIVE_NAME_TABLE = 0x0859937C
ACTIVE_DESCRIPTION_TABLE = 0x085994D8
ACTIVE_COUNT = 87

PASSIVE_DETAIL_NAME_TABLE = 0x085A73E0
PASSIVE_DESCRIPTION_TABLE = 0x085AAEDC
PASSIVE_COUNT = 45

NINJA_TOOL_DETAIL_NAME_TABLE = 0x085A7C50
NINJA_TOOL_DESCRIPTION_TABLE = 0x085997AC
NINJA_TOOL_COUNT = 94

ACTION_IDENTITY_CONFIDENCE = {
    "runtime_visual_exact",
    "runtime_visual_ambiguous",
}
UNIT_IDENTITY_CONFIDENCE = ACTION_IDENTITY_CONFIDENCE


def _load_bank(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_action_identities(path: Path) -> list[dict[str, Any]]:
    payload = _load_bank(path)
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != ACTIVE_COUNT:
        raise ValueError("active-action identity overlay must contain 87 entries")

    result: list[dict[str, Any]] = []
    for expected_id, source in enumerate(entries):
        if source.get("action_id") != expected_id:
            raise ValueError(
                "active-action identity overlay must be ordered by contiguous action ID"
            )
        display_name = source.get("display_name")
        confidence = source.get("confidence")
        raw_hex = source.get("name_raw_hex")
        if not isinstance(display_name, str) or not display_name:
            raise ValueError(f"active-action identity {expected_id} has no display name")
        if confidence not in ACTION_IDENTITY_CONFIDENCE:
            raise ValueError(
                f"active-action identity {expected_id} has unsupported confidence"
            )
        if not isinstance(raw_hex, str) or not raw_hex:
            raise ValueError(
                f"active-action identity {expected_id} is not bound to ROM name bytes"
            )
        result.append(dict(source))
    return result


def _load_unit_identities(path: Path) -> list[dict[str, Any]]:
    payload = _load_bank(path)
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != UNIT_COUNT:
        raise ValueError("unit identity overlay must contain 63 entries")
    result: list[dict[str, Any]] = []
    for expected_id, source in enumerate(entries):
        if source.get("unit_id") != expected_id:
            raise ValueError("unit identity overlay must be ordered by contiguous unit ID")
        if not isinstance(source.get("display_name"), str) or not source["display_name"]:
            raise ValueError(f"unit identity {expected_id} has no display name")
        if source.get("confidence") not in UNIT_IDENTITY_CONFIDENCE:
            raise ValueError(f"unit identity {expected_id} has unsupported confidence")
        if not isinstance(source.get("name_raw_hex"), str) or not source["name_raw_hex"]:
            raise ValueError(f"unit identity {expected_id} is not bound to ROM name bytes")
        result.append(dict(source))
    return result


def _rom_offset(address: int, rom: bytes, *, size: int = 1) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"ROM address outside image: 0x{address:08X}")
    return offset


def _text_record(rom: bytes, table_address: int, index: int) -> dict[str, Any]:
    entry_address = table_address + index * 4
    entry_offset = _rom_offset(entry_address, rom, size=4)
    pointer = struct.unpack_from("<I", rom, entry_offset)[0]
    record: dict[str, Any] = {
        "pointer_table_address": f"0x{table_address:08X}",
        "pointer_entry_address": f"0x{entry_address:08X}",
        "pointer": None if pointer == 0 else f"0x{pointer:08X}",
        "rom_offset": None,
        "raw_hex": "",
    }
    if pointer == 0:
        return record

    offset = _rom_offset(pointer, rom)
    end_limit = min(len(rom), offset + 2048)
    end = rom.find(b"\0", offset, end_limit)
    if end < 0:
        raise ValueError(
            f"unterminated text at 0x{pointer:08X} from table 0x{table_address:08X}[{index}]"
        )
    record["rom_offset"] = offset
    record["raw_hex"] = rom[offset:end].hex()
    return record


def _nonzero_slot_ids(slots: list[dict[str, Any]]) -> list[int]:
    result: list[int] = []
    for slot in slots:
        slot_id = int(slot["id"])
        if slot_id and slot_id not in result:
            result.append(slot_id)
    return result


def _reverse_references(
    units: list[dict[str, Any]], field: str, count: int
) -> list[list[int]]:
    references = [[] for _ in range(count)]
    for unit in units:
        for action_id in unit[field]:
            if not 0 <= action_id < count:
                raise ValueError(
                    f"unit {unit['unit_id']} references out-of-range {field} ID {action_id}"
                )
            references[action_id].append(unit["unit_id"])
    return references


def _raw_bank_record(rom: bytes, entry: dict[str, Any], size: int) -> str:
    offset = int(entry["_raw_offset"])
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"bank record outside ROM: 0x{offset:X}+0x{size:X}")
    return rom[offset : offset + size].hex()


def extract_catalog(
    rom: bytes,
    units_path: Path,
    skills_path: Path,
    battle_config_path: Path,
    levels_path: Path,
    action_identities_path: Path | None = None,
    unit_identities_path: Path | None = None,
) -> dict[str, Any]:
    units_bank = _load_bank(units_path)
    legacy_skills_bank = _load_bank(skills_path)
    effect_bank = _load_bank(battle_config_path)
    passive_bank = _load_bank(levels_path)
    identities = (
        _load_action_identities(action_identities_path)
        if action_identities_path is not None
        else None
    )
    unit_identities = (
        _load_unit_identities(unit_identities_path)
        if unit_identities_path is not None
        else None
    )

    if len(units_bank["entries"]) != UNIT_COUNT:
        raise ValueError("unit bank count does not match the proven ROM name table")
    if len(legacy_skills_bank["entries"]) != NINJA_TOOL_COUNT:
        raise ValueError("legacy skills bank count does not match the ninja-tool text table")
    if len(passive_bank["entries"]) != PASSIVE_COUNT:
        raise ValueError("passive bank count does not match the passive text table")
    if len(effect_bank["entries"]) != ACTIVE_COUNT:
        raise ValueError(
            "active-action numeric template count does not match the active text table"
        )

    units: list[dict[str, Any]] = []
    for unit_id, source in enumerate(units_bank["entries"]):
        primary_ids = _nonzero_slot_ids(source["primary_slots"])
        secondary_ids = _nonzero_slot_ids(source["secondary_slots"])
        name = _text_record(rom, UNIT_NAME_TABLE, unit_id)
        display_identity = unit_identities[unit_id] if unit_identities is not None else None
        if display_identity is not None and display_identity["name_raw_hex"] != name["raw_hex"]:
            raise ValueError(f"unit identity {unit_id} does not match ROM name bytes")
        units.append(
            {
                "unit_id": unit_id,
                "name": name,
                "display_identity": display_identity,
                "active": bool(source.get("active", source.get("active_flag", 0))),
                "base_stats": {
                    "attack_power": source["template_02_base"],
                    "defense_power": source["template_03_base"],
                    "agility": source["template_04_base"],
                    "movement": source["template_05_base"],
                    "ninja_tool_capacity": source["template_06_base"],
                    "chakra_capacity": source["template_08_base"],
                    "hand_seals": source["template_0a_base"],
                    "max_hp": source["template_0e_base"],
                },
                "primary_action_ids": primary_ids,
                "secondary_passive_ids": secondary_ids,
                "primary_slots": source["primary_slots"],
                "secondary_slots": source["secondary_slots"],
                "record_rom_offset": source["rom_offset"],
                "record_raw_hex": source["raw_hex"],
            }
        )

    active_references = _reverse_references(units, "primary_action_ids", ACTIVE_COUNT)
    passive_references = _reverse_references(units, "secondary_passive_ids", PASSIVE_COUNT)

    active_actions = []
    for action_id in range(ACTIVE_COUNT):
        name = _text_record(rom, ACTIVE_NAME_TABLE, action_id)
        description = _text_record(rom, ACTIVE_DESCRIPTION_TABLE, action_id)
        numeric_template = effect_bank["entries"][action_id]
        display_identity = identities[action_id] if identities is not None else None
        if (
            display_identity is not None
            and display_identity["name_raw_hex"] != name["raw_hex"]
        ):
            raise ValueError(
                f"active-action identity {action_id} does not match ROM name bytes"
            )
        active_actions.append(
            {
                "action_id": action_id,
                "template_identity": "character_active_action",
                "name": name,
                "display_identity": display_identity,
                "description": description,
                "description_available": description["pointer"] is not None,
                "interaction_role_status": "unresolved; text availability alone does not prove menu selectability",
                "referenced_by_unit_ids": active_references[action_id],
                "numeric_template_status": "same_index_rom_table_structurally_closed; field semantics partially unresolved",
                "numeric_template": numeric_template,
            }
        )

    passives = []
    for passive_id, source in enumerate(passive_bank["entries"]):
        passives.append(
            {
                "passive_id": passive_id,
                "template_identity": "character_passive_progression_effect",
                "name": _text_record(rom, PASSIVE_DETAIL_NAME_TABLE, passive_id),
                "description": _text_record(rom, PASSIVE_DESCRIPTION_TABLE, passive_id),
                "referenced_by_unit_ids": passive_references[passive_id],
                "progression_template": source,
                "progression_template_raw_hex": _raw_bank_record(rom, source, 12),
            }
        )

    ninja_tools = []
    for action_id, source in enumerate(legacy_skills_bank["entries"]):
        ninja_tools.append(
            {
                "action_id": action_id,
                "template_identity": "ninja_tool_action_template",
                "name": _text_record(rom, NINJA_TOOL_DETAIL_NAME_TABLE, action_id),
                "description": _text_record(rom, NINJA_TOOL_DESCRIPTION_TABLE, action_id),
                "template_rom_offset": source["rom_offset"],
                "template_raw_hex": source["raw_hex"],
                "template_fields": source,
            }
        )

    return {
        "schema_version": 2,
        "identity": "battle_content_structural_catalog",
        "rom": {
            "size": len(rom),
            "sha1": hashlib.sha1(rom).hexdigest(),
            "sha256": hashlib.sha256(rom).hexdigest(),
        },
        "provenance": {
            "unit_name_table": f"0x{UNIT_NAME_TABLE:08X}",
            "active_name_table": f"0x{ACTIVE_NAME_TABLE:08X}",
            "active_description_table": f"0x{ACTIVE_DESCRIPTION_TABLE:08X}",
            "passive_name_table": f"0x{PASSIVE_DETAIL_NAME_TABLE:08X}",
            "passive_description_table": f"0x{PASSIVE_DESCRIPTION_TABLE:08X}",
            "ninja_tool_name_table": f"0x{NINJA_TOOL_DETAIL_NAME_TABLE:08X}",
            "ninja_tool_description_table": f"0x{NINJA_TOOL_DESCRIPTION_TABLE:08X}",
        },
        "legacy_paths": {
            "units_bank": str(units_path),
            "skills_bank": str(skills_path),
            "skills_bank_identity": "misnamed_ninja_tool_action_templates",
            "battle_config_bank": str(battle_config_path),
            "levels_bank": str(levels_path),
            "action_identities": (
                str(action_identities_path)
                if action_identities_path is not None
                else None
            ),
            "unit_identities": (
                str(unit_identities_path) if unit_identities_path is not None else None
            ),
        },
        "caveats": [
            "Text is preserved as raw ROM bytes; canonical Japanese transcription requires runtime-image review.",
            "Active actions map one-to-one by ID to the 87 numeric templates at 0x545458; several numeric field semantics and behavior handlers remain unresolved.",
            "Slot membership is structurally proven; ambiguous character display-name transcriptions remain candidates until second visual review.",
        ],
        "units": units,
        "active_actions": active_actions,
        "passives": passives,
        "ninja_tools": ninja_tools,
        "active_action_numeric_templates": {
            "identity": "active_action_numeric_templates",
            "entry_count": len(effect_bank["entries"]),
            "entry_size": effect_bank["entry_size"],
            "table_offset": effect_bank["table_offset"],
            "entries": effect_bank["entries"],
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--units", type=Path, default=Path("sequel/content/units/bank.json"))
    parser.add_argument("--skills", type=Path, default=Path("sequel/content/skills/bank.json"))
    parser.add_argument(
        "--battle-config", type=Path, default=Path("sequel/content/battle-config/bank.json")
    )
    parser.add_argument("--levels", type=Path, default=Path("sequel/content/levels/bank.json"))
    parser.add_argument(
        "--action-identities",
        type=Path,
        default=Path("sequel/content/battle-config/action-identities.json"),
    )
    parser.add_argument(
        "--unit-identities",
        type=Path,
        default=Path("sequel/content/units/unit-identities.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    catalog = extract_catalog(
        args.rom.read_bytes(),
        args.units,
        args.skills,
        args.battle_config,
        args.levels,
        args.action_identities,
        args.unit_identities,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)


if __name__ == "__main__":
    main()
