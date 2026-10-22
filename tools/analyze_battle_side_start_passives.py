#!/usr/bin/env python3
"""Bind the original ROM's side-start passive family and shared latch."""

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

from tools.analyze_battle_passive_query import (
    build_passive_query_manifest,
)
from tools.thumb_branch import decode_thumb_bl


ROM_BASE = 0x08000000
SIDE_START = 0x0806DF88
SIDE_START_END = 0x0806E1B0
SIDE_START_SHA256 = (
    "7fa07a63ea37b827f52bdd22790811d13ecacd16beec92ba037d375bd95417d0"
)
CONTROLLER_START = 0x08073680
CONTROLLER_END = 0x080736E8
CONTROLLER_SHA256 = (
    "2d063388a9f616cd6d0d3a8acfe1494a8182949b81aa3f4590fdc0604be1847d"
)
STATUS_UPSERT = 0x0806C204


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


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


def _hash_range(rom: bytes, start: int, end: int) -> str:
    return hashlib.sha256(
        rom[_offset(start) : _offset(end)]
    ).hexdigest()


def _passive_id_for_target(
    passive_manifest: dict[str, Any],
    target_type: int,
) -> int:
    matches = [
        row["passive_id"]
        for row in passive_manifest["records"]
        if row["target_type"] == target_type
    ]
    _expect(len(matches), 1, f"passive row count for {target_type:#x}")
    return int(matches[0])


def build_side_start_passive_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    _expect(
        _hash_range(rom, SIDE_START, SIDE_START_END),
        SIDE_START_SHA256,
        "side-start function SHA-256",
    )
    _expect(
        _hash_range(rom, CONTROLLER_START, CONTROLLER_END),
        CONTROLLER_SHA256,
        "controller call sequence SHA-256",
    )

    # The controller finishes side-end work, flips the side bit, then invokes
    # the side-start family before continuing into the next-side setup.
    controller_instructions = {
        0x080736B2: 0x788A,  # current side byte
        0x080736B4: 0x2001,
        0x080736B6: 0x4042,  # xor 1
        0x080736B8: 0x708A,  # store flipped side
        0x080736DC: 0x78A0,  # load new side
        0x080736E2: 0x78A0,  # same side passed onward
    }
    for address, expected in controller_instructions.items():
        _expect(
            _u16(rom, address),
            expected,
            f"controller instruction at {address:#010x}",
        )
    _expect_bl(
        rom,
        0x080736DE,
        SIDE_START,
        "side-start controller call",
    )

    query_calls = {
        0x1D: 0x0806DFCC,
        0x1E: 0x0806E032,
        0x1F: 0x0806E0AC,
        0x20: 0x0806E118,
    }
    for target_type, callsite in query_calls.items():
        _expect(
            _u16(rom, callsite - 4),
            0x2100 | target_type,
            f"target load for {target_type:#x}",
        )
        _expect_bl(
            rom,
            callsite,
            0x0806DDA4,
            f"passive query for {target_type:#x}",
        )

    instructions = {
        0x0806DFDA: 0x30BE,  # shared latch
        0x0806DFE4: 0x89A0,  # current HP
        0x0806DFE6: 0x2809,  # <= 9
        0x0806DFF8: 0x8810,  # value A u16
        0x0806DFFA: 0x89A1,  # current HP
        0x0806DFFE: 0x81A0,  # write HP
        0x0806E000: 0x89E1,  # max HP
        0x0806E008: 0xD900,  # clamp branch
        0x0806E00C: 0x7A20,  # max chakra
        0x0806E00E: 0x71E0,  # current chakra
        0x0806E040: 0x30BE,  # same latch for 0x1E
        0x0806E04A: 0x89A0,
        0x0806E04C: 0x2809,
        0x0806E05E: 0x7810,  # value A low byte
        0x0806E06C: 0x2305,  # raw duration 5
        0x0806E074: 0x8848,  # value B u16
        0x0806E0BA: 0x30BE,  # same latch for 0x1F
        0x0806E0C4: 0x89E0,  # max HP
        0x0806E0C6: 0x89A1,  # current HP
        0x0806E0C8: 0x0880,  # floor(max HP / 4)
        0x0806E0DC: 0x7810,  # value A low byte
        0x0806E0EA: 0x2303,  # raw duration 3
        0x0806E126: 0x30BE,  # same latch for 0x20
        0x0806E134: 0x280B,  # battle ID 11
        0x0806E150: 0x211E,  # attack-up status
        0x0806E154: 0x2300,  # raw duration 0
        0x0806E16A: 0x2122,  # agility-up status
        0x0806E16E: 0x2300,  # raw duration 0
        0x0806E190: 0x2000,  # clear latch
        0x0806E192: 0x7028,
    }
    for address, expected in instructions.items():
        _expect(
            _u16(rom, address),
            expected,
            f"side-start instruction at {address:#010x}",
        )
    for callsite in (
        0x0806E06E,
        0x0806E0EC,
        0x0806E156,
        0x0806E170,
    ):
        _expect_bl(
            rom,
            callsite,
            STATUS_UPSERT,
            f"status upsert at {callsite:#010x}",
        )

    passive_manifest = build_passive_query_manifest(rom_path)
    passive_ids = {
        target_type: _passive_id_for_target(
            passive_manifest, target_type
        )
        for target_type in query_calls
    }
    return {
        "schema_version": 1,
        "identity": "battle_side_start_passive_consumers",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "function": {
            "start": f"0x{SIDE_START:08X}",
            "end_inclusive": f"0x{SIDE_START_END - 1:08X}",
            "sha256": SIDE_START_SHA256,
        },
        "controller": {
            "callsite": "0x080736DE",
            "side_flip_before_call": True,
            "side_start_before_next_side_setup": True,
            "sha256": CONTROLLER_SHA256,
        },
        "query_priority": ["0x1D", "0x1E", "0x1F", "0x20"],
        "shared_latch": {
            "unit_offset": "0xBE",
            "set_after_trigger": True,
            "retrigger_while_below_threshold": False,
            "rearm_after_condition_clears": True,
        },
        "families": {
            "0x1D": {
                "passive_id": passive_ids[0x1D],
                "trigger": "current_hp <= 9",
                "effects": [
                    "hp += value_a, clamped to max_hp",
                    "current_chakra = max_chakra",
                ],
                "raw_duration": None,
                "implementation_status": "closed",
            },
            "0x1E": {
                "passive_id": passive_ids[0x1E],
                "trigger": "current_hp <= 9",
                "status_code": "0x1E",
                "status_value": "value_a low byte",
                "raw_duration": 5,
                "healing": "value_b",
                "implementation_status": "closed",
            },
            "0x1F": {
                "passive_id": passive_ids[0x1F],
                "trigger": "current_hp <= floor(max_hp / 4)",
                "status_code": "0x1E",
                "status_value": "value_a low byte",
                "raw_duration": 3,
                "implementation_status": "closed",
            },
            "0x20": {
                "passive_id": passive_ids[0x20],
                "battle_id_gate": 11,
                "status_codes": ["0x1E", "0x22"],
                "raw_duration": 0,
                "implementation_status": "withheld_pending_semantics",
            },
        },
        "boundary": (
            "Types 0x1D through 0x1F have closed trigger, value, status, "
            "duration, and latch behavior. Type 0x20 is battle-11 gated and "
            "its mechanical writes are known, but its user-facing semantics "
            "and scenario ordering remain withheld rather than guessed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        default=Path("rom/base.gba"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_side_start_passive_manifest(args.rom)
    text = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if(args.output):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
