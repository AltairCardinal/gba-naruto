#!/usr/bin/env python3
"""Bind persistent blocker statuses to the original battle side scheduler."""

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
ACTION_80_TEMPLATE = 0x08545958
ACTION_80_RAW = bytes.fromhex("01053f02000155000302030000000000")
EFFECT_HANDLER_START = 0x0807755C
EFFECT_HANDLER_END = 0x0807758E
EFFECT_HANDLER_SHA256 = (
    "d0a95a96620619c9c2be4f4bf77f2e52c63a78eefa042eb7754db419edb0b9d7"
)
SIDE_ACTIVATION_START = 0x08075350
SIDE_ACTIVATION_END = 0x080753F4
SIDE_ACTIVATION_SHA256 = (
    "eb477d165bb683e1fec8eedd95b83564afc451dbafe2ed6baa843506e3bf5a86"
)
CONTROLLER_START = 0x080736A0
CONTROLLER_END = 0x080736E8
CONTROLLER_SHA256 = (
    "7fcc272e5763d4eee8e1059221a4dc93e694b909f3ca84b9a8ccf7381c34cfd7"
)
REACTION_STATE_SETTER = 0x0806A8C0
STATUS_FIND = 0x0806C160
STATUS_UPSERT = 0x0806C204
UNIT_ACTIVATOR = 0x0806A790
UNIT_VISUAL_REFRESH = 0x0806A80C
BLOCKER_QUERIES = (
    (0x3F, 0x0807536C, 0x0807536E),
    (0x3E, 0x0807537C, 0x0807537E),
    (0x3D, 0x0807538C, 0x0807538E),
    (0x0F, 0x0807539C, 0x0807539E),
    (0x11, 0x080753AC, 0x080753AE),
    (0x15, 0x080753BC, 0x080753BE),
)


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _range_sha256(rom: bytes, start: int, end: int) -> str:
    return hashlib.sha256(
        rom[_offset(start) : _offset(end)]
    ).hexdigest()


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


def build_command_blocker_manifest(
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
    action_raw = rom[
        _offset(ACTION_80_TEMPLATE) :
        _offset(ACTION_80_TEMPLATE) + len(ACTION_80_RAW)
    ]
    _expect(action_raw, ACTION_80_RAW, "action 80 template")
    _expect(
        _range_sha256(
            rom, EFFECT_HANDLER_START, EFFECT_HANDLER_END
        ),
        EFFECT_HANDLER_SHA256,
        "effect 0x3F handler SHA-256",
    )
    _expect(
        _range_sha256(
            rom, SIDE_ACTIVATION_START, SIDE_ACTIVATION_END
        ),
        SIDE_ACTIVATION_SHA256,
        "side activation SHA-256",
    )
    _expect(
        _range_sha256(rom, CONTROLLER_START, CONTROLLER_END),
        CONTROLLER_SHA256,
        "side transition controller SHA-256",
    )

    # Effect 0x3F first requests the restrained reaction, then—unless the
    # event's 0x1800 bypass flags are present—persists the effect as a status.
    handler_instructions = {
        0x0807755C: 0x7870,
        0x0807755E: 0x2130,
        0x08077564: 0x89F1,
        0x08077566: 0x20C0,
        0x08077568: 0x0140,
        0x0807756A: 0x4008,
        0x0807756C: 0x2800,
        0x0807756E: 0xD16E,
    }
    for address, instruction in handler_instructions.items():
        _expect(
            _u16(rom, address),
            instruction,
            f"effect handler instruction at {address:#010x}",
        )
    _expect_bl(
        rom,
        0x08077560,
        REACTION_STATE_SETTER,
        "restrained reaction state call",
    )
    _expect_bl(
        rom,
        0x0807758A,
        STATUS_UPSERT,
        "effect 0x3F status upsert call",
    )

    for status_code, load_address, callsite in BLOCKER_QUERIES:
        _expect(
            _u16(rom, load_address),
            0x2100 | status_code,
            f"blocker load for 0x{status_code:02X}",
        )
        _expect_bl(
            rom,
            callsite,
            STATUS_FIND,
            f"blocker query for 0x{status_code:02X}",
        )
        _expect(
            _u16(rom, callsite + 8),
            0x28FF,
            f"no-status sentinel check for 0x{status_code:02X}",
        )

    controller_instructions = {
        0x080736B2: 0x788A,
        0x080736B4: 0x2001,
        0x080736B6: 0x4042,
        0x080736B8: 0x708A,
        0x080736E2: 0x78A0,
    }
    for address, instruction in controller_instructions.items():
        _expect(
            _u16(rom, address),
            instruction,
            f"side transition instruction at {address:#010x}",
        )
    _expect_bl(
        rom,
        0x080736E4,
        SIDE_ACTIVATION_START,
        "side activation controller call",
    )
    _expect_bl(
        rom,
        0x080753D8,
        UNIT_ACTIVATOR,
        "eligible unit activation call",
    )
    _expect_bl(
        rom,
        0x080753DE,
        UNIT_VISUAL_REFRESH,
        "eligible unit visual refresh call",
    )

    return {
        "schema_version": 1,
        "identity": "battle_command_blocker_bindings",
        "rom": str(rom_path),
        "rom_sha256": rom_sha256,
        "action_80": {
            "action_id": 80,
            "template_address": f"0x{ACTION_80_TEMPLATE:08X}",
            "template_raw_hex": action_raw.hex(),
            "effect_code": f"0x{action_raw[2] & 0x3F:02X}",
            "success_rate_percent": action_raw[6],
            "duration_turns": action_raw[9],
            "stored_duration_ticks":
                (action_raw[9] & 0x7F) * 2,
        },
        "effect_handler": {
            "range": (
                f"0x{EFFECT_HANDLER_START:08X}.."
                f"0x{EFFECT_HANDLER_END - 1:08X}"
            ),
            "sha256": EFFECT_HANDLER_SHA256,
            "reaction_state_call": {
                "callsite": "0x08077560",
                "target": "0x0806A8C0",
                "state": "0x30",
            },
            "status_upsert_call": {
                "callsite": "0x0807758A",
                "target": "0x0806C204",
            },
            "bypass_event_flag_mask": "0x1800",
        },
        "side_activation": {
            "function": "0x08075350",
            "function_sha256": SIDE_ACTIVATION_SHA256,
            "controller_callsite": "0x080736E4",
            "controller_sha256": CONTROLLER_SHA256,
            "side_flipped_before_call": True,
            "blocker_priority": [
                f"0x{status_code:02X}"
                for status_code, _, _ in BLOCKER_QUERIES
            ],
            "status_query_target": "0x0806C160",
            "on_blocker": "skip_unit_activation",
            "on_no_blocker_for_current_side":
                "activate_unit_for_commands",
        },
        "implementation_boundary": {
            "eligibility_source": "persistent_status_store",
            "not_eligibility_source": "reaction_state_byte",
            "shared_consumers": [
                "player_unit_selection",
                "player_unit_cycle",
                "ai_unit_scheduler",
            ],
            "presentation_only_fields": ["reaction_state"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = build_command_blocker_manifest(args.rom)
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
