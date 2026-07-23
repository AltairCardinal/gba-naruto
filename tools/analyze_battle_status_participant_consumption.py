#!/usr/bin/env python3
"""Bind status 0x0D consumption at the original battle resolver queue."""

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
RESOLVER_QUEUE = 0x08076CE0
RESOLVER_QUEUE_END = 0x08077760
RESOLVER_QUEUE_SHA256 = (
    "f5675aded5a37132820b79ff5cddd7fcc9a83290ae56098604fe41d49eb3b579"
)
STATUS_LOOKUP = 0x0806C160
STATUS_REMOVE = 0x0806C1A4
STATUS_CODE = 0x0D
LOOKUP_CALLSITES = {"source": 0x08076DC4, "target": 0x08076DDC}
REMOVE_CALLSITES = {"source": 0x08076DD4, "target": 0x08076DEC}
REACTION_EVENT_CODES = [0x04, 0x09, 0x0A, 0x10, 0x16, 0x19]
TARGET_STATE_AND_MASK_ADDRESS = 0x08076E60
TARGET_STATE_AND_MASK = 0xFFFFFEFF


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _expect_halfwords(rom: bytes, expected: dict[int, int]) -> None:
    for address, halfword in expected.items():
        _expect(_u16(rom, address), halfword, f"halfword at 0x{address:08X}")


def _expect_bl(rom: bytes, callsite: int, target: int, label: str) -> None:
    actual = decode_thumb_bl(
        callsite,
        _u16(rom, callsite),
        _u16(rom, callsite + 2),
    )
    _expect(actual, target, label)


def _format_address(address: int) -> str:
    return f"0x{address:08X}"


def _format_code(code: int) -> str:
    return f"0x{code:02X}"


def build_status_participant_consumption_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    resolver_queue = rom[_offset(RESOLVER_QUEUE) : _offset(RESOLVER_QUEUE_END)]
    _expect(
        hashlib.sha256(resolver_queue).hexdigest(),
        RESOLVER_QUEUE_SHA256,
        "resolver queue SHA-256",
    )
    for role, callsite in LOOKUP_CALLSITES.items():
        _expect_bl(rom, callsite, STATUS_LOOKUP, f"{role} status lookup")
    for role, callsite in REMOVE_CALLSITES.items():
        _expect_bl(rom, callsite, STATUS_REMOVE, f"{role} status removal")

    # The event type is masked to its low six bits. The six known reaction
    # codes branch around the entire status-0x0D consumption block.
    _expect_halfwords(
        rom,
        {
            0x08076DA2: 0x89F0,  # LDRH r0, [r6, #0x0E]
            0x08076DA4: 0x213F,  # MOVS r1, #0x3F
            0x08076DA6: 0x4001,  # ANDS r1, r0
            0x08076DA8: 0x2904,
            0x08076DAC: 0x2909,
            0x08076DB0: 0x290A,
            0x08076DB4: 0x2910,
            0x08076DB8: 0x2916,
            0x08076DBC: 0x2919,
            0x08076DC0: 0x1C18,  # source unit slot from event byte +0
            0x08076DC2: 0x210D,
            0x08076DD0: 0x7830,  # source unit slot
            0x08076DD2: 0x2200,  # removal mode 0
            0x08076DD8: 0x7870,  # target unit slot from event byte +1
            0x08076DDA: 0x210D,
            0x08076DE8: 0x7870,  # target unit slot
            0x08076DEA: 0x2200,  # removal mode 0
            0x08076DF0: 0x1C3A,  # target unit pointer
            0x08076DF2: 0x32C0,  # target unit state word +0xC0
            0x08076DF4: 0x6810,
            0x08076DF8: 0x4008,
            0x08076DFA: 0x6010,
        },
    )
    _expect(
        _u32(rom, TARGET_STATE_AND_MASK_ADDRESS),
        TARGET_STATE_AND_MASK,
        "target unit state AND-mask literal",
    )

    return {
        "schema_version": 1,
        "identity": "battle_status_0x0d_participant_consumption",
        "resolver_queue": _format_address(RESOLVER_QUEUE),
        "resolver_queue_end": _format_address(RESOLVER_QUEUE_END),
        "resolver_queue_sha256": RESOLVER_QUEUE_SHA256,
        "status_code": _format_code(STATUS_CODE),
        "lookup_callsites": {
            role: _format_address(callsite)
            for role, callsite in LOOKUP_CALLSITES.items()
        },
        "remove_callsites": {
            role: _format_address(callsite)
            for role, callsite in REMOVE_CALLSITES.items()
        },
        "removal_mode": 0,
        "skipped_event_type_low_6_values": [
            _format_code(code) for code in REACTION_EVENT_CODES
        ],
        "skipped_family": "known_reaction_event_codes",
        "target_unit_state_word_offset": 0xC0,
        "target_unit_state_and_mask": f"0x{TARGET_STATE_AND_MASK:08X}",
        "target_unit_state_cleared_bits": (
            f"0x{((~TARGET_STATE_AND_MASK) & 0xFFFFFFFF):08X}"
        ),
        "operational_semantics": (
            "consume_status_0x0d_from_source_and_target_before_non_reaction_event;_"
            "target_consumption_also_clears_unit_state_bit_0x100"
        ),
        "visible_gameplay_name": None,
        "conclusion": (
            "Before resolving an event whose low-six-bit type is not one of the "
            "six known reaction codes, the queue directly consumes status 0x0D "
            "from both source and target using removal mode 0. Target consumption "
            "also clears bit 0x100 in the target unit state word."
        ),
        "boundary": (
            "The event-family gate, participant order, direct-consumption mode, and "
            "target state-bit mutation are statically closed. The visible gameplay "
            "name, producer parameters, and semantic name of unit-state bit 0x100 "
            "remain unresolved."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "notes/battle-status-participant-consumption-bindings-20260723.json"
        ),
    )
    args = parser.parse_args()
    result = build_status_participant_consumption_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
