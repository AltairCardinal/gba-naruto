#!/usr/bin/env python3
"""Bind status 0x0E's linked-unit recursion inside the battle effect resolver."""

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
SHARED_RESOLVER = 0x08076A30
SHARED_RESOLVER_END = 0x08076CDE
SHARED_RESOLVER_SHA256 = (
    "98c04b5f751e85af362a139387cecfe749f0832a57f70cb1210a04055b7266f1"
)
STATUS_LOOKUP = 0x0806C160
STATUS_CODE = 0x0E
LOOKUP_CALLSITE = 0x08076B48
RECURSIVE_CALLSITE = 0x08076B6C


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


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


def build_status_linked_resolution_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    resolver = rom[_offset(SHARED_RESOLVER) : _offset(SHARED_RESOLVER_END)]
    _expect(
        hashlib.sha256(resolver).hexdigest(),
        SHARED_RESOLVER_SHA256,
        "shared resolver SHA-256",
    )
    _expect_bl(rom, LOOKUP_CALLSITE, STATUS_LOOKUP, "status 0x0E lookup call")
    _expect_bl(
        rom,
        RECURSIVE_CALLSITE,
        SHARED_RESOLVER,
        "status 0x0E recursive resolver call",
    )

    # The branch is skipped for action type 0x1F. Otherwise the target unit's
    # status 0x0E record is located, record byte +4 is loaded as another unit
    # slot, and the resolver is called recursively with the same event values.
    _expect_halfwords(
        rom,
        {
            0x08076B40: 0x281F,  # CMP r0, #0x1F
            0x08076B44: 0x1C38,  # ADDS r0, r7, #0 (primary target slot)
            0x08076B46: 0x210E,  # MOVS r1, #0x0E
            0x08076B54: 0x00C8,  # LSLS r0, r1, #3 (record index * 8)
            0x08076B56: 0x4440,  # ADD r0, r8 (primary target unit)
            0x08076B58: 0x30D8,  # ADDS r0, #0xD8 (active bank + record +4)
            0x08076B5A: 0x7801,  # LDRB r1, [r0] (linked unit slot)
            0x08076B5C: 0x9400,  # extra argument 0 = 0
            0x08076B5E: 0x9401,  # extra argument 1 = 0
            0x08076B60: 0x9402,  # extra argument 2 = 0
            0x08076B62: 0x2001,  # MOVS r0, #1
            0x08076B64: 0x9003,  # extra argument 3 = 1 (recursion guard)
            0x08076B66: 0x4648,  # MOV r0, r9 (original source)
            0x08076B68: 0x9A04,  # LDR r2, [sp, #0x10] (same action type)
            0x08076B6A: 0x9B05,  # LDR r3, [sp, #0x14] (same amount)
            0x08076B70: 0x4641,  # MOV r1, r8 (return to primary target)
            0x08076B72: 0x8988,  # LDRH r0, [r1, #0x0C] (primary target HP)
        },
    )

    return {
        "schema_version": 1,
        "identity": "battle_status_0x0e_linked_unit_recursive_resolution",
        "shared_resolver": f"0x{SHARED_RESOLVER:08X}",
        "shared_resolver_end": f"0x{SHARED_RESOLVER_END:08X}",
        "shared_resolver_sha256": SHARED_RESOLVER_SHA256,
        "status_code": f"0x{STATUS_CODE:02X}",
        "lookup_callsite": f"0x{LOOKUP_CALLSITE:08X}",
        "recursive_callsite": f"0x{RECURSIVE_CALLSITE:08X}",
        "linked_target_record_offset": 4,
        "recursive_arguments": {
            "source": "original_source",
            "target": "active_status_record_plus_4_unit_slot",
            "action_type": "same_as_primary",
            "amount": "same_as_primary",
            "extra_arguments": [0, 0, 0, 1],
        },
        "recursion_guard_extra_argument_index": 3,
        "primary_target_still_resolves": True,
        "skipped_action_type": "0x1F",
        "operational_semantics": (
            "linked_target_recursive_resolution_before_primary_target_damage"
        ),
        "visible_gameplay_name": None,
        "conclusion": (
            "For action types other than 0x1F, status 0x0E recursively resolves "
            "the same source, action type, and amount against the unit slot stored "
            "in status-record byte +4, then continues resolving the primary target. "
            "This is ordered propagation, not target redirection."
        ),
        "boundary": (
            "The linked-resolution data flow and recursion guard are statically "
            "closed. The visible gameplay name, status producer, natural runtime "
            "presentation, and interactions with death or removed-status events "
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
            "notes/battle-status-linked-resolution-bindings-20260723.json"
        ),
    )
    args = parser.parse_args()
    result = build_status_linked_resolution_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
