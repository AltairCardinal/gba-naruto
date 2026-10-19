#!/usr/bin/env python3
"""Bind original-ROM player resolution and AI two-component action building."""

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

from tools.thumb_branch import iter_thumb_direct_branches


ROM_BASE = 0x08000000
ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
TABLE_ADDRESS = 0x0853DFB0
TABLE_LITERAL_ADDRESS = 0x08075C0C
TABLE_BYTES = bytes.fromhex(
    "09 08 0A 09 05 0B 0C 0C 0D 10 10 11 10 FF 12 00"
)
ACTIVE_ACTION_TABLE_ADDRESS = 0x08545458
ACTION_RECORD_SIZE = 0x10
FORCED_FOLLOW_ACTION_ID = 9
COMBINATION_FLAG_MASK = 0x1800
OPTIONAL_FOLLOW_MASK = 0x0800
FORCED_FOLLOW_MASK = 0x1000

EVIDENCE_RANGES = {
    "pair_builder_prefix": (
        0x08075B58,
        0x08075D12,
        "6d863a3e7462225fa4dba24af9ffedd5237f8bf875bf12226c8d464c9ab65b64",
    ),
    "recipe_match_branch": (
        0x08075BD0,
        0x08075C34,
        "1d00ebc972e9ce6fdf2d71ea34e0aa8f0007422071bef610bb3f317007d2809b",
    ),
    "generic_pair_builder": (
        0x08075D10,
        0x08075DF8,
        "6ff74d87a0fff0c93d00c21b250c2381cccb2ea188b14962ec6dd34ef960e1e8",
    ),
    "ai_component_enumerator": (
        0x08082354,
        0x08082596,
        "bf084a305073bee7e041ca059519a377eb0a8b01ed3f083fee758fcdbd0665a0",
    ),
    "ai_candidate_enumerator": (
        0x08083040,
        0x0808326E,
        "a4aaf575a838b3975ae31290dcc24990ad5a56452adaf30662c549295af22aff",
    ),
    "ai_planner": (
        0x080851F8,
        0x080855FE,
        "d94ce211153c95b9d6065691179a6887b149c443be27311c8baaf679c8d85b95",
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _offset(address: int) -> int:
    return address - ROM_BASE


def _slice(rom: bytes, start: int, end: int) -> bytes:
    return rom[_offset(start) : _offset(end)]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _direct_call_target(
    rom: bytes,
    start: int,
    end: int,
    callsite: int,
) -> int:
    matches = [
        branch.target
        for branch in iter_thumb_direct_branches(
            rom,
            rom_base=ROM_BASE,
            start=start,
            end=end,
        )
        if branch.address == callsite and branch.mnemonic == "bl"
    ]
    _expect(len(matches), 1, f"direct call at 0x{callsite:08X}")
    return matches[0]


def analyze_battle_action_combinations(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    _expect(_sha256(rom), ROM_SHA256, "ROM SHA-256")

    table = _slice(
        rom,
        TABLE_ADDRESS,
        TABLE_ADDRESS + len(TABLE_BYTES),
    )
    _expect(table, TABLE_BYTES, "combination table")
    _expect(
        _u32(rom, TABLE_LITERAL_ADDRESS),
        TABLE_ADDRESS,
        "combination table literal",
    )

    ranges: dict[str, dict[str, Any]] = {}
    for name, (start, end, expected_sha) in EVIDENCE_RANGES.items():
        digest = _sha256(_slice(rom, start, end))
        _expect(digest, expected_sha, f"{name} bytes")
        ranges[name] = {
            "start": f"0x{start:08X}",
            "end": f"0x{end:08X}",
            "sha256": digest,
        }

    for address, expected in {
        0x08075BCC: 0x2802,  # cmp component_count, #2
        0x08075C14: 0x2880,  # encoded tool must be > 0x80
        0x08075C18: 0x2891,  # encoded tool must be <= 0x91
        0x08075C2E: 0x2201,  # matched output count = 1
        0x08075C30: 0x920C,  # store matched output count
        0x08075D10: 0x2505,  # recipe sentinel/fallback selector
        0x08075D16: 0x9807,  # reload original component count
        0x08075D18: 0x900C,  # preserve original count
    }.items():
        _expect(
            _u16(rom, address),
            expected,
            f"instruction at 0x{address:08X}",
        )

    recipes = []
    for offset in range(0, 15, 3):
        first, second, result = table[offset : offset + 3]
        recipes.append(
            {
                "first_action_id": first,
                "second_action_id": (
                    "ninja_tool_1_through_17"
                    if second == 0xFF
                    else second
                ),
                "result_action_id": result,
            }
        )

    action_template_address = (
        ACTIVE_ACTION_TABLE_ADDRESS
        + FORCED_FOLLOW_ACTION_ID * ACTION_RECORD_SIZE
    )
    action_template_halfword = _u16(
        rom,
        action_template_address + 2,
    )
    _expect(
        action_template_halfword,
        0x1008,
        "action 9 effect/target-flags halfword",
    )
    for address, expected in {
        0x08082498: 0x8821,  # load selected action effect/flags
        0x0808249A: 0x26C0,  # begin 0x1800 mask construction
        0x0808249C: 0x0176,
        0x080824A0: 0x4008,  # selected & 0x1800
        0x080824A2: 0x2800,  # any combination flag?
        0x080824EE: 0x8820,  # reload selected action effect/flags
        0x080824F0: 0x2280,  # begin 0x1000 mask construction
        0x080824F2: 0x0152,
        0x080824F6: 0x4008,  # selected & 0x1000
        0x080824F8: 0x2800,  # forced second component?
        0x080824FA: 0xD000,  # optional path skips forced loop
        0x080824FC: 0xE749,  # loop back to component enumeration
        0x080824FE: 0xE006,  # return one component first
        0x080831BC: 0x73E2,  # store returned component count
    }.items():
        _expect(
            _u16(rom, address),
            expected,
            f"AI combination instruction at 0x{address:08X}",
        )

    planner_call = _direct_call_target(
        rom,
        0x080851F8,
        0x080855FE,
        0x080855C6,
    )
    _expect(
        planner_call,
        0x08083040,
        "planner candidate-enumerator call",
    )
    candidate_call = _direct_call_target(
        rom,
        0x08083040,
        0x0808326E,
        0x080831B6,
    )
    _expect(
        candidate_call,
        0x08082354,
        "candidate component-enumerator call",
    )
    follow_catalog_call = _direct_call_target(
        rom,
        0x08082354,
        0x08082596,
        0x080824D8,
    )
    _expect(
        follow_catalog_call,
        0x0806FDA4,
        "second-component catalog call",
    )
    follow_filter_call = _direct_call_target(
        rom,
        0x08082354,
        0x08082596,
        0x080824E4,
    )
    _expect(
        follow_filter_call,
        0x08082280,
        "second-component catalog filter call",
    )

    optional_follow_action_ids = []
    forced_follow_action_ids = []
    for action_id in range(87):
        template_halfword = _u16(
            rom,
            ACTIVE_ACTION_TABLE_ADDRESS
            + action_id * ACTION_RECORD_SIZE
            + 2,
        )
        flags = template_halfword & COMBINATION_FLAG_MASK
        if flags & FORCED_FOLLOW_MASK:
            forced_follow_action_ids.append(action_id)
        elif flags & OPTIONAL_FOLLOW_MASK:
            optional_follow_action_ids.append(action_id)

    _expect(
        optional_follow_action_ids,
        [12, 16],
        "optional-follow action IDs",
    )
    _expect(
        forced_follow_action_ids,
        [9, 14, 25, 29],
        "forced-follow action IDs",
    )

    return {
        "schema_version": 1,
        "identity": "battle_action_combination_builder_binding",
        "rom": str(rom_path),
        "rom_sha256": ROM_SHA256,
        "builder_address": "0x08075B58",
        "table_address": f"0x{TABLE_ADDRESS:08X}",
        "table_literal_address": (
            f"0x{TABLE_LITERAL_ADDRESS:08X}"
        ),
        "table_sha256": _sha256(table),
        "component_count_gate": 2,
        "recipes": recipes,
        "encoded_ninja_tool_range": ["0x81", "0x91"],
        "matched_recipe_behavior": (
            "replace two selected components with one derived action"
        ),
        "unmatched_pair_behavior": (
            "preserve both selected components and initialize both action events"
        ),
        "component_initializers": {
            "active_action": "0x0806D85C",
            "ninja_tool": "0x0806D910",
        },
        "ai_forced_follow": {
            "action_id": FORCED_FOLLOW_ACTION_ID,
            "action_template_address": (
                f"0x{action_template_address:08X}"
            ),
            "action_template_halfword": (
                f"0x{action_template_halfword:04X}"
            ),
            "combination_flag_mask": "0x1800",
            "forced_second_component_mask": "0x1000",
            "planner_to_candidate_enumerator_call": {
                "callsite": "0x080855C6",
                "target": f"0x{planner_call:08X}",
            },
            "candidate_to_component_enumerator_call": {
                "callsite": "0x080831B6",
                "target": f"0x{candidate_call:08X}",
            },
            "second_component_catalog_call": {
                "callsite": "0x080824D8",
                "target": f"0x{follow_catalog_call:08X}",
            },
            "second_component_filter_call": {
                "callsite": "0x080824E4",
                "target": f"0x{follow_filter_call:08X}",
            },
            "behavior": (
                "The enemy planner reaches the shared component enumerator. "
                "Action 9 carries the forced-follow flag, so the enumerator "
                "builds and filters a second action/tool catalog and loops "
                "until a second component is selected before returning the "
                "candidate component count."
            ),
        },
        "ai_combination_policies": {
            "optional_follow_action_ids":
                optional_follow_action_ids,
            "forced_follow_action_ids":
                forced_follow_action_ids,
            "combination_flag_mask":
                f"0x{COMBINATION_FLAG_MASK:04X}",
            "optional_follow_mask":
                f"0x{OPTIONAL_FOLLOW_MASK:04X}",
            "forced_follow_mask":
                f"0x{FORCED_FOLLOW_MASK:04X}",
            "optional_behavior": (
                "return the single-component candidate first, "
                "then retain the follow cursor so later calls "
                "enumerate two-component candidates"
            ),
            "forced_behavior": (
                "skip the single-component candidate and loop "
                "immediately until a second component is selected"
            ),
        },
        "evidence_ranges": ranges,
        "boundary": (
            "This binds the ordered two-component builder, five replacement "
            "recipes, encoded tool wildcard, unmatched two-event fallback, "
            "and the enemy planner's forced-follow path for action 9. It does "
            "not by itself identify menu prompt text or prove every optional "
            "first-component policy."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = analyze_battle_action_combinations(args.rom)
    text = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
