#!/usr/bin/env python3
"""Generate fixed-capacity Butano content for original battle scripts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


NO_INDEX = 0xFFFF
SUPPORTED_OPCODES = {
    0x00,
    0x01,
    0x02,
    0x03,
    0x04,
    0x07,
    0x08,
    0x0F,
    0x11,
    0x12,
    0x17,
    0x20,
    0x32,
    0x33,
    0x34,
    0x35,
    0x36,
    0x37,
    0x38,
    0x39,
}


def _number(value: str | int) -> int:
    return int(value, 16) if isinstance(value, str) else value


def _opcode(record: dict[str, Any]) -> int:
    value = _number(record["opcode"])
    if value not in SUPPORTED_OPCODES:
        raise ValueError(
            f"unsupported presentation opcode 0x{value:02X} "
            f"at {record.get('address', 'unknown')}"
        )
    return value


def _operands(record: dict[str, Any]) -> list[int]:
    if "operand_hex" in record:
        values = list(bytes.fromhex(record["operand_hex"]))
    elif _opcode(record) == 0x20:
        values = [record["parameter"]]
    elif _opcode(record) == 0x33:
        values = [record["selector"]]
    else:
        values = []
    if len(values) > 4:
        raise ValueError(
            f"presentation operands exceed four bytes at {record['address']}"
        )
    return values + [0] * (4 - len(values))


def _text(
    record: dict[str, Any],
    text_bytes: list[int],
) -> tuple[int, int]:
    encoded = bytes.fromhex(record.get("encoded_text_hex", ""))
    if len(encoded) > 255:
        raise ValueError(
            f"presentation text exceeds 255 bytes at {record['address']}"
        )
    offset = len(text_bytes)
    if offset + len(encoded) > 0xFFFF:
        raise ValueError("presentation text bank exceeds 65535 bytes")
    text_bytes.extend(encoded)
    return offset, len(encoded)


def _target(
    record: dict[str, Any],
    key: str,
    address_to_index: dict[int, int],
) -> int:
    value = record.get(key)
    if value is None:
        return NO_INDEX
    address = _number(value)
    if address not in address_to_index:
        raise ValueError(
            f"{key} {value} is outside the battle selector graph"
        )
    return address_to_index[address]


def normalize_battle_presentation_manifest(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported battle presentation schema")
    battles = manifest.get("battles", [])
    if len(battles) != 47:
        raise ValueError("unexpected battle presentation definition count")

    definitions: list[dict[str, int]] = []
    selector_instructions: list[dict[str, Any]] = []
    selector_dispatch_cases: list[dict[str, int]] = []
    cases: list[dict[str, int]] = []
    commands: list[dict[str, Any]] = []
    text_bytes: list[int] = []
    presentation_text_byte_count = 0

    for expected_battle_id, battle in enumerate(battles):
        if battle.get("battle_id") != expected_battle_id:
            raise ValueError("non-contiguous battle presentation definitions")
        nodes = battle.get("selector_nodes", [])
        if len(nodes) > 255:
            raise ValueError("battle selector program exceeds 255 instructions")
        selector_offset = len(selector_instructions)
        address_to_index = {
            _number(node["address"]): selector_offset + index
            for index, node in enumerate(nodes)
        }
        root = battle.get("selector_root")
        root_index = (
            _target(
                {"selector_root": root},
                "selector_root",
                address_to_index,
            )
            if root is not None
            else NO_INDEX
        )

        for node in nodes:
            opcode = _opcode(node)
            text_offset, text_length = _text(node, text_bytes)
            dispatch_offset = len(selector_dispatch_cases)
            dispatch = node.get("cases", []) if opcode == 0x32 else []
            if len(dispatch) > 255:
                raise ValueError("selector dispatch exceeds 255 cases")
            for entry in dispatch:
                selector_dispatch_cases.append(
                    {
                        "selector": entry["selector"],
                        "instruction_index": _target(
                            {"target": entry["target"]},
                            "target",
                            address_to_index,
                        ),
                    }
                )
            selector_instructions.append(
                {
                    "source_address": _number(node["address"]),
                    "opcode": opcode,
                    "operands": _operands(node),
                    "fallthrough_index": _target(
                        node, "fallthrough", address_to_index
                    ),
                    "branch_index": _target(
                        node, "branch_target", address_to_index
                    ),
                    "dispatch_offset": dispatch_offset,
                    "dispatch_count": len(dispatch),
                    "text_offset": text_offset,
                    "text_length": text_length,
                }
            )

        case_offset = len(cases)
        battle_cases = battle.get("presentation_cases", [])
        if len(battle_cases) > 255:
            raise ValueError("battle presentation exceeds 255 cases")
        for case in battle_cases:
            if not case.get("payload_complete"):
                raise ValueError(
                    f"incomplete presentation payload at {case['target']}"
                )
            command_offset = len(commands)
            case_commands = case.get("commands", [])
            if not case_commands or len(case_commands) > 255:
                raise ValueError(
                    f"invalid presentation command count at {case['target']}"
                )
            for command in case_commands:
                opcode = _opcode(command)
                if opcode not in {
                    0x00, 0x01, 0x02, 0x03, 0x04, 0x08,
                    0x0F, 0x11, 0x12, 0x17, 0x20,
                }:
                    raise ValueError(
                        "unsupported presentation opcode "
                        f"0x{opcode:02X} in case payload"
                    )
                text_offset, text_length = _text(command, text_bytes)
                presentation_text_byte_count += text_length
                commands.append(
                    {
                        "source_address": _number(command["address"]),
                        "opcode": opcode,
                        "operands": _operands(command),
                        "text_offset": text_offset,
                        "text_length": text_length,
                    }
                )
            cases.append(
                {
                    "source_address": _number(case["target"]),
                    "command_offset": command_offset,
                    "command_count": len(case_commands),
                    "selector": case["selector"],
                }
            )
        definitions.append(
            {
                "battle_id": expected_battle_id,
                "selector_root_instruction": root_index,
                "selector_instruction_offset": selector_offset,
                "selector_instruction_count": len(nodes),
                "case_offset": case_offset,
                "case_count": len(battle_cases),
            }
        )

    for label, values in (
        ("selector instructions", selector_instructions),
        ("selector dispatch cases", selector_dispatch_cases),
        ("presentation cases", cases),
        ("presentation commands", commands),
    ):
        if len(values) > NO_INDEX:
            raise ValueError(f"{label} exceed 65535 records")
    return {
        "manifest": manifest,
        "definitions": definitions,
        "selector_instructions": selector_instructions,
        "selector_dispatch_cases": selector_dispatch_cases,
        "cases": cases,
        "commands": commands,
        "text_bytes": text_bytes,
        "presentation_text_byte_count": presentation_text_byte_count,
    }


def load_battle_presentation_content(root: Path) -> dict[str, Any]:
    path = root / "sequel/content/battle-presentation-scripts/bank.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return normalize_battle_presentation_manifest(manifest)


def _array(values: list[int]) -> str:
    return ", ".join(str(value) for value in values)


def _opcode_name(value: int) -> str:
    return (
        "static_cast<battle_presentation_script_opcode>"
        f"(0x{value:02X})"
    )


def generate_header(content: dict[str, Any]) -> str:
    definitions = [
        "battle_presentation_definition{ "
        f"{row['battle_id']}, "
        f"{row['selector_root_instruction']}, "
        f"{row['selector_instruction_offset']}, "
        f"{row['selector_instruction_count']}, "
        f"{row['case_offset']}, {row['case_count']} }}"
        for row in content["definitions"]
    ]
    dispatch = [
        "battle_presentation_selector_dispatch_case{ "
        f"{row['selector']}, {row['instruction_index']} }}"
        for row in content["selector_dispatch_cases"]
    ]
    instructions = [
        "battle_presentation_selector_instruction{ "
        f"0x{row['source_address']:08X}U, "
        f"{_opcode_name(row['opcode'])}, "
        "std::array<std::uint8_t, 4>{{ "
        f"{_array(row['operands'])} }}}}, "
        f"{row['fallthrough_index']}, {row['branch_index']}, "
        f"{row['dispatch_offset']}, {row['dispatch_count']}, "
        f"{row['text_offset']}, {row['text_length']} }}"
        for row in content["selector_instructions"]
    ]
    cases = [
        "battle_presentation_case{ "
        f"0x{row['source_address']:08X}U, "
        f"{row['command_offset']}, {row['command_count']}, "
        f"{row['selector']} }}"
        for row in content["cases"]
    ]
    commands = [
        "battle_presentation_command{ "
        f"0x{row['source_address']:08X}U, "
        f"{_opcode_name(row['opcode'])}, "
        "std::array<std::uint8_t, 4>{{ "
        f"{_array(row['operands'])} }}}}, "
        f"{row['text_offset']}, {row['text_length']} }}"
        for row in content["commands"]
    ]
    text_values = [
        f"0x{value:02X}" for value in content["text_bytes"]
    ]
    return f"""// Generated by tools/generate_butano_battle_presentation_content.py. Do not edit.
#ifndef KONOHA_GENERATED_BATTLE_PRESENTATION_CONTENT_H
#define KONOHA_GENERATED_BATTLE_PRESENTATION_CONTENT_H

#include "konoha/battle_presentation_content.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{{

inline constexpr std::array<battle_presentation_definition, {len(definitions)}>
        battle_presentation_definitions = {{{{
    {",\n    ".join(definitions)}
}}}};

inline constexpr std::array<battle_presentation_selector_dispatch_case, {len(dispatch)}>
        battle_presentation_selector_dispatch_cases = {{{{
    {",\n    ".join(dispatch)}
}}}};

inline constexpr std::array<battle_presentation_selector_instruction, {len(instructions)}>
        battle_presentation_selector_instructions = {{{{
    {",\n    ".join(instructions)}
}}}};

inline constexpr std::array<battle_presentation_case, {len(cases)}>
        battle_presentation_cases = {{{{
    {",\n    ".join(cases)}
}}}};

inline constexpr std::array<battle_presentation_command, {len(commands)}>
        battle_presentation_commands = {{{{
    {",\n    ".join(commands)}
}}}};

inline constexpr std::array<std::uint8_t, {len(text_values)}>
        battle_presentation_text = {{{{
    {", ".join(text_values)}
}}}};

[[nodiscard]] inline constexpr const battle_presentation_definition*
battle_presentation_definition_for(int battle_id)
{{
    return battle_id >= 0 &&
                   battle_id <
                           static_cast<int>(
                                   battle_presentation_definitions.size()) ?
            &battle_presentation_definitions[
                    static_cast<std::size_t>(battle_id)] :
            nullptr;
}}

[[nodiscard]] inline constexpr const battle_presentation_case*
battle_presentation_case_for(
        const battle_presentation_definition& definition,
        std::uint8_t selector)
{{
    const battle_presentation_case* fallback = nullptr;
    for(std::size_t index = 0;
            index < definition.case_count; ++index)
    {{
        const battle_presentation_case& value =
                battle_presentation_cases[
                        definition.case_offset + index];
        if(! fallback)
        {{
            fallback = &value;
        }}
        if(value.selector == selector)
        {{
            return &value;
        }}
    }}
    return fallback;
}}

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
            "butano-sequel/game/include/konoha/"
            "generated_battle_presentation_content.h"
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    content = load_battle_presentation_content(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_header(content), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
