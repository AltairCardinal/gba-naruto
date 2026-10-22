#!/usr/bin/env python3
"""Bind the original battle event high-bit follow-up status handler."""

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
EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
ACTIVE_ACTION_TABLE = 0x08545458
ACTIVE_ACTION_COUNT = 87
NINJA_TOOL_TABLE = 0x08545BE4
NINJA_TOOL_COUNT = 94
RECORD_SIZE = 16
HANDLER_START = 0x080768D8
HANDLER_END = 0x08076A26
HANDLER_SHA256 = (
    "eea2a918515d8c367ac0f464c5a33092cd1da83963708282e93dba020bef84b4"
)
QUEUE_GATE_START = 0x0807764E
QUEUE_GATE_END = 0x08077670
QUEUE_GATE_SHA256 = (
    "8c0638a3f11746e5ec72fed04f9edfc1635c20ef17e7de5f777b91ee46c92f14"
)
STATUS_UPSERT = 0x0806C204
REACTION_STATE_SETTER = 0x0806A8C0
QUEUE_CALLSITE = 0x0807766C


def _slice(rom: bytes, start: int, end: int) -> bytes:
    return rom[start - ROM_BASE : end - ROM_BASE]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _branch_targets(rom: bytes, start: int, end: int) -> dict[int, int]:
    return {
        branch.address: branch.target
        for branch in iter_thumb_direct_branches(rom, rom_base=ROM_BASE)
        if start <= branch.address < end and branch.mnemonic == "bl"
    }


def _flagged_ids(
    rom: bytes, address: int, count: int, flag: int
) -> list[int]:
    result: list[int] = []
    offset = address - ROM_BASE
    for index in range(count):
        effect_type = rom[offset + index * RECORD_SIZE + 2]
        if effect_type & 0xC0 == flag:
            result.append(index)
    return result


def build_effect_flag_followup_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    _expect(
        hashlib.sha256(rom).hexdigest(),
        EXPECTED_ROM_SHA256,
        "ROM SHA-256",
    )

    handler = _slice(rom, HANDLER_START, HANDLER_END)
    queue_gate = _slice(rom, QUEUE_GATE_START, QUEUE_GATE_END)
    _expect(
        hashlib.sha256(handler).hexdigest(),
        HANDLER_SHA256,
        "follow-up handler SHA-256",
    )
    _expect(
        hashlib.sha256(queue_gate).hexdigest(),
        QUEUE_GATE_SHA256,
        "queue gate SHA-256",
    )

    handler_branches = _branch_targets(rom, HANDLER_START, HANDLER_END)
    _expect(
        {
            address: target
            for address, target in handler_branches.items()
            if target == STATUS_UPSERT
        },
        {
            0x0807690A: STATUS_UPSERT,
            0x08076960: STATUS_UPSERT,
            0x080769A4: STATUS_UPSERT,
            0x080769E8: STATUS_UPSERT,
        },
        "status upsert callsites",
    )
    _expect(
        handler_branches.get(0x08076940),
        REACTION_STATE_SETTER,
        "reaction-state setter callsite",
    )
    queue_branches = _branch_targets(
        rom, QUEUE_GATE_START, QUEUE_GATE_END
    )
    _expect(
        queue_branches.get(QUEUE_CALLSITE),
        HANDLER_START,
        "queue follow-up callsite",
    )

    # Queue gate:
    #   sp+0x18 must be nonzero;
    #   (event+0x0E & 0x0700) must equal 0x0200;
    # then target, potency, packed effect type and source are passed to
    # the helper. These checks keep the semantic manifest tied to the
    # exact original instructions rather than only to table names.
    _expect(_u16(rom, 0x0807764E), 0x9C06, "effective-hit load")
    _expect(_u16(rom, 0x08077650), 0x2C00, "effective-hit compare")
    _expect(_u16(rom, 0x08077654), 0x89F0, "packed event load")
    _expect(_u16(rom, 0x08077656), 0x21E0, "target-policy mask base")
    _expect(_u16(rom, 0x08077658), 0x00C9, "target-policy mask shift")
    _expect(_u16(rom, 0x0807765A), 0x4001, "target-policy mask apply")
    _expect(_u16(rom, 0x0807765C), 0x2080, "target-policy expected base")
    _expect(_u16(rom, 0x0807765E), 0x0080, "target-policy expected shift")

    # Helper constants and arguments:
    # flag 0x80 -> 0x3F, duration 1, value 0, reaction state 0x30.
    # flag 0x40 -> 0x1F/0x21/0x23, duration 3, value 10.
    for address, expected in {
        0x080768F2: 0x2080,
        0x08076904: 0x213F,
        0x08076906: 0x1C3A,
        0x08076908: 0x2301,
        0x0807693E: 0x2130,
        0x08076944: 0x2040,
        0x0807694E: 0x200A,
        0x0807695A: 0x211F,
        0x0807695E: 0x2303,
        0x08076992: 0x200A,
        0x0807699E: 0x2121,
        0x080769A2: 0x2303,
        0x080769D6: 0x200A,
        0x080769E2: 0x2123,
        0x080769E6: 0x2303,
    }.items():
        _expect(_u16(rom, address), expected, f"opcode 0x{address:08X}")

    active_0x80 = _flagged_ids(
        rom, ACTIVE_ACTION_TABLE, ACTIVE_ACTION_COUNT, 0x80
    )
    ninja_0x40 = _flagged_ids(
        rom, NINJA_TOOL_TABLE, NINJA_TOOL_COUNT, 0x40
    )
    _expect(active_0x80, [8, 10, 60], "active flag 0x80 producers")
    _expect(
        ninja_0x40,
        [11, 12, 13, 25, 26, 27, 43, 44, 45, 70, 71, 72],
        "ninja-tool flag 0x40 producers",
    )

    return {
        "schema_version": 1,
        "identity": "battle_effect_high_bit_followup_status_handler",
        "rom_sha256": EXPECTED_ROM_SHA256,
        "handler": f"0x{HANDLER_START:08X}",
        "handler_end": f"0x{HANDLER_END:08X}",
        "handler_sha256": HANDLER_SHA256,
        "queue_gate": (
            f"0x{QUEUE_GATE_START:08X}..0x{QUEUE_GATE_END:08X}"
        ),
        "queue_gate_sha256": QUEUE_GATE_SHA256,
        "queue_callsite": f"0x{QUEUE_CALLSITE:08X}",
        "requires_effective_hit": True,
        "target_policy_gate": "0x0200",
        "post_handler_gate": (
            f"0x{QUEUE_GATE_START:08X}..0x{QUEUE_CALLSITE:08X}"
        ),
        "applies_after_lethal_resolution": True,
        "status_parameter_mapping": {
            "raw_parameter_1": "queued_event_potency",
            "raw_parameter_4": "queued_event_source_unit",
            "duration": "handler_constant",
            "value_u16": "handler_constant",
        },
        "followups": {
            "0x80": {
                "status_codes": ["0x3F"],
                "duration_turns": 1,
                "value_u16": 0,
                "reaction_state": "0x30",
            },
            "0x40": {
                "status_codes": ["0x1F", "0x21", "0x23"],
                "duration_turns": 3,
                "value_u16": 10,
                "reaction_state": None,
            },
        },
        "active_action_producers": {
            "0x80": active_0x80,
        },
        "ninja_tool_producers": {
            "0x40": ninja_0x40,
        },
        "conclusion": (
            "After an effective opponent-target event, packed effect bit "
            "0x80 creates one-turn status 0x3F and sets reaction state 0x30; "
            "bit 0x40 creates three-turn 10-percent attack, defense and "
            "agility reductions 0x1F/0x21/0x23. The post-handler gate checks "
            "only effective-hit and target-policy state before calling the "
            "follow-up helper, so a lethal effect also receives follow-ups."
        ),
        "boundary": (
            "The helper, queue gate, status records, constants and all table "
            "producers are closed. The lethal ordering is bound to the full "
            "post-handler gate hash and its exact branch/call opcodes; no "
            "HP/active-unit load or branch exists between the effective-hit "
            "load at 0x0807764E and helper call at 0x0807766C. Per-status "
            "labels and dedicated animation timing remain presentation-layer "
            "work."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "notes/battle-effect-flag-followups-20260726.json"
        ),
    )
    args = parser.parse_args()
    result = build_effect_flag_followup_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
