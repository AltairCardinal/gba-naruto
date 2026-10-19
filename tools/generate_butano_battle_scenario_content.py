#!/usr/bin/env python3
"""Generate fixed-capacity Butano battle map and formation content."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FIXED_CHARACTER_MAX = 62
PLACEHOLDER_MIN = 0xFA
PLACEHOLDER_MAX = 0xFF
VARIANT_COUNT = 3
RECORD_COUNT = 12
FACING_NAMES = ("up", "right", "down", "left")
PRIMARY_ACTION_COUNT = 15
SECONDARY_ACTION_COUNT = 24
NINJA_TOOL_COUNT = 9
ACTIVE_ACTION_MAX = 86
SECONDARY_ACTION_MAX = 23
NINJA_TOOL_MAX = 93
CHARACTER_LEVEL_MAX = 50


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _selector_kind(selector: int) -> str:
    if 0 <= selector <= FIXED_CHARACTER_MAX:
        return "fixed_character"
    if PLACEHOLDER_MIN <= selector <= PLACEHOLDER_MAX:
        return "deployment_placeholder"
    raise ValueError(f"unsupported selector {selector}")


def _validated_action_slots(
    row: dict[str, Any],
    field: str,
    count: int,
    maximum_action: int,
    key: tuple[int, int, int],
) -> list[dict[str, int]]:
    slots = row.get(field)
    if not isinstance(slots, list) or len(slots) != count:
        raise ValueError(
            f"invalid {field} for formation record {key}"
        )
    result: list[dict[str, int]] = []
    for slot in slots:
        values = {
            "action": slot.get("action"),
            "state": slot.get("state"),
            "unlock_level": slot.get("unlock_level"),
            "reserved": slot.get("reserved"),
        }
        if (
            not all(isinstance(value, int) for value in values.values())
            or not all(0 <= value <= 0xFF for value in values.values())
            or values["action"] > maximum_action
        ):
            raise ValueError(
                f"invalid {field} for formation record {key}"
            )
        result.append(values)
    return result


def _runtime_config(
    row: dict[str, Any],
    selector_kind: str,
    enabled: bool,
    key: tuple[int, int, int],
) -> dict[str, Any]:
    if not enabled:
        return {
            "embedded_character_config": False,
            "level": 1,
            "unit_parameter": 0,
            "primary_action_slots": [],
            "secondary_action_slots": [],
            "equipped_tools": [],
        }

    level = row.get("level")
    unit_parameter = row.get("unit_parameter")
    primary_slots = _validated_action_slots(
        row,
        "primary_action_slots",
        PRIMARY_ACTION_COUNT,
        ACTIVE_ACTION_MAX,
        key,
    )
    secondary_slots = _validated_action_slots(
        row,
        "secondary_action_slots",
        SECONDARY_ACTION_COUNT,
        SECONDARY_ACTION_MAX,
        key,
    )
    tools = row.get("equipped_tools")
    if (
        not isinstance(level, int)
        or not 1 <= level <= CHARACTER_LEVEL_MAX
        or not isinstance(unit_parameter, int)
        or not 0 <= unit_parameter <= 0xFF
        or not isinstance(tools, list)
        or len(tools) != NINJA_TOOL_COUNT
        or not all(
            isinstance(tool, int) and 0 <= tool <= NINJA_TOOL_MAX
            for tool in tools
        )
    ):
        raise ValueError(
            f"invalid runtime configuration for formation record {key}"
        )
    return {
        "embedded_character_config":
            selector_kind == "fixed_character",
        "level": level,
        "unit_parameter": unit_parameter,
        "primary_action_slots": primary_slots,
        "secondary_action_slots": secondary_slots,
        "equipped_tools": tools,
    }


def load_scenario_content(root: Path) -> list[dict[str, Any]]:
    maps = _load_json(root / "sequel/content/maps/bank.json")
    positions = _load_json(root / "sequel/content/positions/bank.json")
    map_entries = sorted(maps["entries"], key=lambda row: row["_index"])
    if maps.get("entry_count") != len(map_entries):
        raise ValueError("map entry count does not match entries")

    indexed_positions: dict[tuple[int, int, int], dict[str, Any]] = {}
    for row in positions["entries"]:
        key = (row["group_id"], row["variant_id"], row["record_id"])
        if key in indexed_positions:
            raise ValueError(f"duplicate formation record {key}")
        indexed_positions[key] = row

    scenarios: list[dict[str, Any]] = []
    for expected_id, map_row in enumerate(map_entries):
        if map_row["_index"] != expected_id:
            raise ValueError(f"non-contiguous map index {map_row['_index']}")
        width = map_row["width"]
        height = map_row["height"]
        if width <= 0 or height <= 0 or width % 4 or height % 2:
            raise ValueError(f"invalid map dimensions for battle {expected_id}")
        grid_width = width // 4
        grid_height = height // 2
        variants = []
        for variant_id in range(VARIANT_COUNT):
            records = []
            for record_id in range(RECORD_COUNT):
                key = (expected_id, variant_id, record_id)
                if key not in indexed_positions:
                    raise ValueError(f"missing formation record {key}")
                row = indexed_positions[key]
                enabled = bool(row["active"])
                selector = row["selector"]
                selector_kind = (
                    _selector_kind(selector) if enabled else "fixed_character"
                )
                side = row["affiliation"]
                x = row["x"]
                y = row["y"]
                parameter = row["parameter"]
                battle_experience = row.get("battle_experience")
                if battle_experience is None:
                    raw_hex = row.get("raw_hex", "")
                    if len(raw_hex) < 28:
                        raise ValueError(
                            f"missing battle experience for formation record {key}"
                        )
                    battle_experience = int.from_bytes(
                        bytes.fromhex(raw_hex)[0x0C:0x0E], "little"
                    )
                if enabled:
                    if side not in (0, 1):
                        raise ValueError(f"invalid side for formation record {key}")
                    if not 0 <= x < grid_width or not 0 <= y < grid_height:
                        raise ValueError(f"out-of-bounds coordinate for formation record {key}")
                    if not 0 <= parameter < len(FACING_NAMES):
                        raise ValueError(f"invalid facing for formation record {key}")
                    if not 0 <= battle_experience <= 0xFFFF:
                        raise ValueError(
                            f"invalid battle experience for formation record {key}"
                        )
                records.append(
                    {
                        "enabled": enabled,
                        "selector_kind": selector_kind,
                        "selector": selector if enabled else 0,
                        "side": side if enabled else 0,
                        "x": x if enabled else 0,
                        "y": y if enabled else 0,
                        "facing": parameter if enabled else 0,
                        "battle_experience": (
                            battle_experience if enabled else 0
                        ),
                        "runtime_config": _runtime_config(
                            row,
                            selector_kind,
                            enabled,
                            key,
                        ),
                    }
                )
            variants.append(records)
        scenarios.append(
            {
                "battle_id": expected_id,
                "grid_width": grid_width,
                "grid_height": grid_height,
                "map_flags": map_row["flags"],
                "variants": variants,
            }
        )
    return scenarios


def _action_slot_cpp(row: dict[str, int]) -> str:
    return (
        "action_slot_definition{ "
        f"{row['action']}, {row['state']}, "
        f"{row['unlock_level']}, {row['reserved']} }}"
    )


def _runtime_config_cpp(config: dict[str, Any]) -> str:
    if not config["embedded_character_config"]:
        return "battle_scenario_unit_runtime_config{}"
    embedded = (
        "true"
        if config["embedded_character_config"]
        else "false"
    )
    primary = ", ".join(
        _action_slot_cpp(slot)
        for slot in config["primary_action_slots"]
    )
    secondary = ", ".join(
        _action_slot_cpp(slot)
        for slot in config["secondary_action_slots"]
    )
    tools = ", ".join(str(tool) for tool in config["equipped_tools"])
    return "".join(
        [
            "battle_scenario_unit_runtime_config{ ",
            f"{embedded}, {config['level']}, ",
            f"{config['unit_parameter']}, ",
            "std::array<action_slot_definition, 15>{{ ",
            primary,
            " }}, ",
            "std::array<action_slot_definition, 24>{{ ",
            secondary,
            " }}, ",
            "std::array<ninja_tool_id, ",
            "battle_ninja_tool_slot_capacity>{{ ",
            tools,
            " }} }",
        ]
    )


def _slot_cpp(row: dict[str, Any]) -> str:
    kind = f"scenario_selector_kind::{row['selector_kind']}"
    side = "battle_side::player" if row["side"] == 0 else "battle_side::enemy"
    facing = f"battle_facing::{FACING_NAMES[row['facing']]}"
    enabled = "true" if row["enabled"] else "false"
    return (
        "battle_scenario_unit_slot{ "
        f"{enabled}, {kind}, {row['selector']}, {side}, "
        f"grid_point{{ {row['x']}, {row['y']} }}, {facing}, "
        f"{row['battle_experience']}, "
        f"{_runtime_config_cpp(row['runtime_config'])} }}"
    )


def generate_header(scenarios: list[dict[str, Any]]) -> str:
    rendered_scenarios = []
    for scenario in scenarios:
        rendered_variants = []
        for records in scenario["variants"]:
            rendered_slots = ",\n                    ".join(
                _slot_cpp(row) for row in records
            )
            rendered_variants.append(
                "std::array<battle_scenario_unit_slot, 12>{{\n"
                f"                    {rendered_slots}\n"
                "                }}"
            )
        variants = ",\n            ".join(rendered_variants)
        rendered_scenarios.append(
            "battle_scenario_definition{\n"
            f"        {scenario['battle_id']}, {scenario['grid_width']}, "
            f"{scenario['grid_height']}, {scenario['map_flags']}U,\n"
            "        std::array<std::array<battle_scenario_unit_slot, 12>, 3>{{\n"
            f"            {variants}\n"
            "        }}\n"
            "    }"
        )
    body = ",\n    ".join(rendered_scenarios)
    return f"""// Generated by tools/generate_butano_battle_scenario_content.py. Do not edit.
#ifndef KONOHA_GENERATED_BATTLE_SCENARIO_CONTENT_H
#define KONOHA_GENERATED_BATTLE_SCENARIO_CONTENT_H

#include "konoha/battle_scenario_content.h"

#include <array>

namespace konoha
{{

inline constexpr std::array<battle_scenario_definition, {len(scenarios)}>
        battle_scenario_definitions = {{{{
    {body}
}}}};

}}

#endif
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "butano-sequel/game/include/konoha/generated_battle_scenario_content.h"
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    scenarios = load_scenario_content(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_header(scenarios), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
