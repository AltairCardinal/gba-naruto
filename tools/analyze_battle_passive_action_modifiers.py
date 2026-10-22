#!/usr/bin/env python3
"""Bind persistent passive modifiers to original runtime action definitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
ORIGINAL_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
FUNCTION_START = 0x0806D6B8
FUNCTION_END = 0x0806D856
FUNCTION_SHA256 = (
    "eb6688fd7b16927475ffe10c3a833326e0792ea13c8595de9a642722324182ff"
)
PERCENTAGE_PASS_START = 0x0806D6C0
PERCENTAGE_PASS_END = 0x0806D75E
PERCENTAGE_PASS_SHA256 = (
    "60d7c5e123dc9f1ff1ecd2fa1b7f9ec13288263ea8f6cee7204c529febac090c"
)
FLAT_PASS_START = 0x0806D75E
FLAT_PASS_END = 0x0806D850
FLAT_PASS_SHA256 = (
    "2627a331461dcb7a69d23ff10739f1842034b612f125a9e9ebb92f305467ae94"
)
ACTIVE_INITIALIZER_START = 0x0806D85C
ACTIVE_INITIALIZER_END = 0x0806D910
ACTIVE_INITIALIZER_SHA256 = (
    "dd78df15b6599a2bc73fd04e5b04f8a58cb8d761f7d7ae3a0460a5daae9daa7f"
)
TOOL_INITIALIZER_START = 0x0806D910
TOOL_INITIALIZER_END = 0x0806D95E
TOOL_INITIALIZER_SHA256 = (
    "032c35e2fa3295e906a741e1f58a5351417686fd17826d7849af7c1959138268"
)
ACTIVE_MODIFIER_CALLSITE = 0x0806D906
TOOL_MODIFIER_CALLSITE = 0x0806D954
PASSIVE_DEFINITION_TABLE = 0x085459C8
FLAT_JUMP_TABLE_POINTER = 0x0806D7B4
FLAT_JUMP_TABLE = 0x0806D7B8
FLAT_JUMP_TABLE_ENTRIES = (
    0x0806D7D4,
    0x0806D846,
    0x0806D7F2,
    0x0806D846,
    0x0806D7FC,
    0x0806D820,
    0x0806D832,
)
FLAT_JUMP_TABLE_SHA256 = (
    "96d0da6fa4d9f53c7a9ea90ffe142314317fa5258f5dfa5dd80036308b86ddd2"
)


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _range_sha256(rom: bytes, start: int, end: int) -> str:
    return hashlib.sha256(rom[_offset(start) : _offset(end)]).hexdigest()


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _expect_range_sha256(
    rom: bytes,
    start: int,
    end: int,
    expected: str,
    label: str,
) -> None:
    _expect(_range_sha256(rom, start, end), expected, f"{label} SHA-256")


def _expect_bl(
    rom: bytes,
    callsite: int,
    target: int,
    label: str,
) -> None:
    actual = decode_thumb_bl(
        callsite,
        _u16(rom, callsite),
        _u16(rom, callsite + 2),
    )
    _expect(actual, target, label)


def build_passive_action_modifier_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    rom_sha256 = hashlib.sha256(rom).hexdigest()
    _expect(
        rom_sha256,
        ORIGINAL_ROM_SHA256,
        "original ROM SHA-256",
    )
    _expect_range_sha256(
        rom,
        FUNCTION_START,
        FUNCTION_END,
        FUNCTION_SHA256,
        "passive action modifier",
    )
    _expect_range_sha256(
        rom,
        PERCENTAGE_PASS_START,
        PERCENTAGE_PASS_END,
        PERCENTAGE_PASS_SHA256,
        "percentage pass",
    )
    _expect_range_sha256(
        rom,
        FLAT_PASS_START,
        FLAT_PASS_END,
        FLAT_PASS_SHA256,
        "flat-addition pass",
    )
    _expect_range_sha256(
        rom,
        ACTIVE_INITIALIZER_START,
        ACTIVE_INITIALIZER_END,
        ACTIVE_INITIALIZER_SHA256,
        "active-action initializer",
    )
    _expect_range_sha256(
        rom,
        TOOL_INITIALIZER_START,
        TOOL_INITIALIZER_END,
        TOOL_INITIALIZER_SHA256,
        "ninja-tool initializer",
    )

    # Both passes consume the same 24 four-byte passive slots and definition
    # table. The full function/pass hashes keep these structural bindings
    # fail-closed, while the literals bind the table rather than only its
    # surrounding control flow.
    _expect(
        _u32(rom, 0x0806D708),
        PASSIVE_DEFINITION_TABLE,
        "percentage-pass passive definition table",
    )
    _expect(
        _u32(rom, 0x0806D7B0),
        PASSIVE_DEFINITION_TABLE,
        "flat-pass passive definition table",
    )

    jump_table_raw = rom[
        _offset(FLAT_JUMP_TABLE) :
        _offset(FLAT_JUMP_TABLE) + 4 * len(FLAT_JUMP_TABLE_ENTRIES)
    ]
    _expect(
        hashlib.sha256(jump_table_raw).hexdigest(),
        FLAT_JUMP_TABLE_SHA256,
        "flat passive jump table SHA-256",
    )
    jump_table_entries = struct.unpack("<7I", jump_table_raw)
    _expect(
        jump_table_entries,
        FLAT_JUMP_TABLE_ENTRIES,
        "flat passive jump table entries",
    )
    _expect(
        _u32(rom, FLAT_JUMP_TABLE_POINTER),
        FLAT_JUMP_TABLE,
        "flat passive jump table pointer",
    )

    _expect_bl(
        rom,
        ACTIVE_MODIFIER_CALLSITE,
        FUNCTION_START,
        "active-action passive modifier call",
    )
    _expect_bl(
        rom,
        TOOL_MODIFIER_CALLSITE,
        FUNCTION_START,
        "ninja-tool passive modifier call",
    )
    _expect(_u32(rom, 0x0806D858), 999, "success-rate comparison cap")

    physical_predicate = (
        "(header_0_1 == 0x0102 and effect_code != 0x21) "
        "or effect_code == 0x0A"
    )
    percentage_targets = {
        "14": {
            "field": "potency",
            "operation": "increase_percent",
            "predicate": physical_predicate,
            "cap": 99,
        },
        "16": {
            "field": "potency",
            "operation": "increase_percent",
            "predicate": "header_0_1 == 0x0101",
            "cap": 99,
        },
    }
    flat_targets = {
        "13": {
            "field": "potency",
            "operation": "add",
            "predicate": physical_predicate,
            "cap": 99,
        },
        "14": {"operation": "no_op"},
        "15": {
            "field": "potency",
            "operation": "add",
            "predicate": "header_0_1 == 0x0101",
            "cap": 99,
        },
        "16": {"operation": "no_op"},
        "17": {
            "field": "potency",
            "operation": "add",
            "predicate": "header_0_1 == 0x0105",
            "cap": 99,
        },
        "18": {
            "field": "potency",
            "operation": "add",
            "predicate": "effect_code == 0x1A",
            "storage": "u8",
            "explicit_cap": None,
        },
        "19": {
            "field": "success_rate_percent",
            "operation": "add",
            "predicate": "all_runtime_actions",
            "storage": "u8",
            "comparison_cap_before_store": 999,
        },
    }
    return {
        "schema_version": 1,
        "identity": "battle_passive_action_modifier_bindings",
        "rom": str(rom_path),
        "rom_sha256": rom_sha256,
        "function": {
            "range": "0x0806D6B8..0x0806D855",
            "sha256": FUNCTION_SHA256,
        },
        "initializers": {
            "active_action": {
                "function": "0x0806D85C",
                "passive_modifier_callsite": "0x0806D906",
                "order":
                    "action_level_growth_then_passive_modifiers",
            },
            "ninja_tool": {
                "function": "0x0806D910",
                "passive_modifier_callsite": "0x0806D954",
                "order": "template_then_passive_modifiers",
            },
        },
        "secondary_slots": {
            "count": 24,
            "stride": 4,
            "passive_id_offset": "unit+0x50",
            "stored_level_offset": "unit+0x51",
            "inactive_passive_id": 0,
            "inactive_stored_levels": [0, 255],
        },
        "definition_table": {
            "address": f"0x{PASSIVE_DEFINITION_TABLE:08X}",
            "record_size": 12,
            "target_type_offset": 0,
            "base_a_offset": 2,
            "per_level_a_offset": 6,
        },
        "value_formula":
            "base_a + per_level_a * (stored_level - 1)",
        "runtime_action_fields": {
            "header_0_1": "+0 u16",
            "effect_code": "+2 low 6 bits",
            "potency": "+4 u8",
            "success_rate_percent": "+6 u8",
        },
        "pass_order": ["percentage", "flat_addition"],
        "passes": {
            "percentage": {
                "range": "0x0806D6C0..0x0806D75D",
                "sha256": PERCENTAGE_PASS_SHA256,
                "targets": percentage_targets,
            },
            "flat_addition": {
                "range": "0x0806D75E..0x0806D84F",
                "sha256": FLAT_PASS_SHA256,
                "jump_table": f"0x{FLAT_JUMP_TABLE:08X}",
                "jump_table_sha256": FLAT_JUMP_TABLE_SHA256,
                "jump_table_entries": [
                    f"0x{entry:08X}" for entry in jump_table_entries
                ],
                "targets": flat_targets,
            },
        },
        "boundary": (
            "Targets 13-19 modify a per-command runtime action copy after "
            "active-action level growth or ninja-tool template loading. "
            "This manifest binds numeric predicates and does not assign "
            "unverified player-facing passive names."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_passive_action_modifier_manifest(args.rom)
    payload = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
