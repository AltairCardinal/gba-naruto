#!/usr/bin/env python3
"""Bind the 24-slot passive query and its 45 progression rows to ROM bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
QUERY_START = 0x0806DDA4
QUERY_END = 0x0806DE16
QUERY_SHA256 = (
    "1a129adf0d5d492f5cbd8531c9bd2b6e49934b56879b2163ee9971f6ccc04681"
)
TABLE_ADDRESS = 0x085459C8
TABLE_COUNT = 45
TABLE_ENTRY_SIZE = 12
TABLE_SHA256 = (
    "4746ef6114975d356d893267d1bd78e5e7c49a0cc705b8c721acaf7d1664aafd"
)


def _offset(address: int) -> int:
    return address - ROM_BASE


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _record(rom: bytes, passive_id: int) -> dict[str, int | str]:
    offset = _offset(TABLE_ADDRESS) + passive_id * TABLE_ENTRY_SIZE
    raw = rom[offset : offset + TABLE_ENTRY_SIZE]
    (
        target_type,
        reserved1,
        base_a,
        base_b,
        per_level_a,
        per_level_b,
        reserved_a,
    ) = struct.unpack("<BBHHHHH", raw)
    return {
        "passive_id": passive_id,
        "target_type": target_type,
        "reserved1": reserved1,
        "base_a": base_a,
        "base_b": base_b,
        "per_level_a": per_level_a,
        "per_level_b": per_level_b,
        "reserved_a": reserved_a,
        "raw_hex": raw.hex(),
    }


def build_passive_query_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    query = rom[_offset(QUERY_START) : _offset(QUERY_END)]
    table = rom[
        _offset(TABLE_ADDRESS) :
        _offset(TABLE_ADDRESS) + TABLE_COUNT * TABLE_ENTRY_SIZE
    ]
    _expect(hashlib.sha256(query).hexdigest(), QUERY_SHA256, "query SHA-256")
    _expect(hashlib.sha256(table).hexdigest(), TABLE_SHA256, "table SHA-256")

    # Bind each part of the contract to the concrete Thumb sequence, rather
    # than treating a hash match alone as a semantic proof.
    instructions = {
        0x0806DDB0: 0x0090,  # slot index * 4
        0x0806DDB6: 0x3150,  # secondary-slot base +0x50
        0x0806DDB8: 0x7809,  # passive ID
        0x0806DDBA: 0x3051,  # stored level +0x51
        0x0806DDBC: 0x7800,
        0x0806DDBE: 0x3801,  # stored_level - 1
        0x0806DDC4: 0x2900,  # reject passive ID 0
        0x0806DDC8: 0x2BFE,  # stored level 0 -> wrapped 0xFF
        0x0806DDCC: 0x2BFF,  # stored level 0xFF -> wrapped 0xFE
        0x0806DDD0: 0x0048,  # passive ID * 2
        0x0806DDD2: 0x1840,  # passive ID * 3
        0x0806DDD4: 0x0080,  # passive ID * 12
        0x0806DDDA: 0x7808,  # target type
        0x0806DDE0: 0x88C8,  # per-level A at +6
        0x0806DDE8: 0x884D,  # base A at +2
        0x0806DDEE: 0x8908,  # per-level B at +8
        0x0806DDF6: 0x8889,  # base B at +4
        0x0806DE0A: 0x2A17,  # inclusive last slot 23
        0x0806DE0E: 0x20FF,  # not-found return
    }
    for address, expected in instructions.items():
        _expect(_u16(rom, address), expected, f"instruction at {_hex(address)}")
    _expect(_u32(rom, 0x0806DE00), TABLE_ADDRESS, "table literal")

    return {
        "schema_version": 1,
        "identity": "battle_passive_query",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "query_function": {
            "start": _hex(QUERY_START),
            "end_inclusive": _hex(QUERY_END - 1),
            "size": len(query),
            "sha256": hashlib.sha256(query).hexdigest(),
        },
        "progression_table": {
            "address": _hex(TABLE_ADDRESS),
            "entry_count": TABLE_COUNT,
            "entry_size": TABLE_ENTRY_SIZE,
            "sha256": hashlib.sha256(table).hexdigest(),
        },
        "slot_layout": {
            "count": 24,
            "base_offset": "0x50",
            "stride": 4,
            "passive_id_offset": 0,
            "stored_level_offset": 1,
        },
        "query_contract": {
            "inactive_passive_ids": [0],
            "inactive_stored_levels": [0, 255],
            "selection": "first_active_slot_with_matching_target_type",
            "return_value": "slot_index_or_0xFF",
            "value_a": "base_a + per_level_a * (stored_level - 1)",
            "value_b": "base_b + per_level_b * (stored_level - 1)",
        },
        "records": [_record(rom, passive_id) for passive_id in range(TABLE_COUNT)],
        "boundary": (
            "All 45 progression rows and the generic lookup are code-verified. "
            "Only consumers independently bound to a target type may assign gameplay meaning."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_passive_query_manifest(args.rom)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
