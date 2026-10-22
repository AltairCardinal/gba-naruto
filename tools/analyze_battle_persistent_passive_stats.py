#!/usr/bin/env python3
"""Bind persistent passive stat modifiers to the original stat loader."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ORIGINAL_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
FUNCTION_START = 0x0806D964
FUNCTION_END = 0x0806DDA4
FUNCTION_SHA256 = (
    "9cbcf9e7a568f31c837e2aa7acdb3ed265ccde914044746dd99eaa498a9c2a2c"
)
PERCENTAGE_PASS_START = 0x0806DAE6
PERCENTAGE_PASS_END = 0x0806DC1A
PERCENTAGE_PASS_SHA256 = (
    "8f9a658a9355a07995f8fc0f701c399695d6a889acf349f0a51aea2d22068768"
)
FLAT_PASS_START = 0x0806DC1A
FLAT_PASS_END = 0x0806DD96
FLAT_PASS_SHA256 = (
    "6e29782b34cf169955b8da7e1b2d55c9a653fa8df7c88560929fd92c15539542"
)
PASSIVE_DEFINITION_TABLE = 0x085459C8
FLAT_JUMP_TABLE_POINTER = 0x0806DC78
FLAT_JUMP_TABLE = 0x0806DC7C
FLAT_JUMP_TABLE_ENTRIES = (
    0x0806DCA4,
    0x0806DD86,
    0x0806DCC8,
    0x0806DCE8,
    0x0806DD08,
    0x0806DD86,
    0x0806DD28,
    0x0806DD86,
    0x0806DD48,
    0x0806DD68,
)
FLAT_JUMP_TABLE_SHA256 = (
    "987d6c826346bdb3bbd698c8e274d7fe0c7c6724b30094906384d0c2d7947d2b"
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


def _expect_halfwords(
    rom: bytes,
    expected: dict[int, int],
    label: str,
) -> None:
    for address, instruction in expected.items():
        _expect(
            _u16(rom, address),
            instruction,
            f"{label} instruction at 0x{address:08X}",
        )


def build_persistent_passive_stat_manifest(
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
    _expect(
        _range_sha256(rom, FUNCTION_START, FUNCTION_END),
        FUNCTION_SHA256,
        "character stat loader SHA-256",
    )
    _expect(
        _range_sha256(
            rom,
            PERCENTAGE_PASS_START,
            PERCENTAGE_PASS_END,
        ),
        PERCENTAGE_PASS_SHA256,
        "percentage passive pass SHA-256",
    )
    _expect(
        _range_sha256(rom, FLAT_PASS_START, FLAT_PASS_END),
        FLAT_PASS_SHA256,
        "flat passive pass SHA-256",
    )

    # Both loops index exactly 24 four-byte unit slots. The passive ID is
    # unit+0x50+4*i, and the stored level is the following byte.
    for start in (PERCENTAGE_PASS_START, 0x0806DC1E):
        _expect_halfwords(
            rom,
            {
                start: 0x4641,
                start + 2: 0x0088,
                start + 4: 0x1830,
                start + 8: 0x3150,
                start + 10: 0x7809,
                start + 12: 0x3051,
                start + 14: 0x7800,
                start + 16: 0x3801,
            },
            "secondary passive slot iteration",
        )
    _expect_halfwords(
        rom,
        {
            0x0806DAFC: 0x2900,
            0x0806DB02: 0x2DFE,
            0x0806DB08: 0x2DFF,
            0x0806DC34: 0x2900,
            0x0806DC3A: 0x2DFE,
            0x0806DC40: 0x2DFF,
            0x0806DC14: 0x2817,
            0x0806DD90: 0x2817,
        },
        "secondary passive activity and count gates",
    )

    # Both passes load the same 45x12-byte definition table. The arithmetic
    # around each literal computes id*12 and then base_a + per_level_a*(L-1).
    _expect(
        _u32(rom, 0x0806DB44),
        PASSIVE_DEFINITION_TABLE,
        "percentage-pass passive definition table",
    )
    _expect(
        _u32(rom, 0x0806DC74),
        PASSIVE_DEFINITION_TABLE,
        "flat-pass passive definition table",
    )
    _expect_halfwords(
        rom,
        {
            0x0806DB0E: 0x0048,
            0x0806DB10: 0x1840,
            0x0806DB12: 0x0080,
            0x0806DB18: 0x88D8,
            0x0806DB1C: 0x436A,
            0x0806DB20: 0x8859,
            0x0806DB22: 0x1840,
            0x0806DC46: 0x0048,
            0x0806DC48: 0x1840,
            0x0806DC4A: 0x0080,
            0x0806DC50: 0x88D8,
            0x0806DC54: 0x436A,
            0x0806DC58: 0x8859,
            0x0806DC5A: 0x1840,
        },
        "passive definition value calculation",
    )

    # The percentage pass has four explicit dispatch targets. Field loads and
    # clamps below bind their otherwise numeric target types to runtime stats.
    _expect_halfwords(
        rom,
        {
            0x0806DB28: 0x7818,
            0x0806DB2A: 0x2806,
            0x0806DB32: 0x2802,
            0x0806DB48: 0x2808,
            0x0806DB4C: 0x280B,
            0x0806DB52: 0x89F4,
            0x0806DB84: 0x78F4,
            0x0806DB96: 0x2863,
            0x0806DBB2: 0x7934,
            0x0806DBC4: 0x2863,
            0x0806DBE0: 0x8974,
            0x0806DBF2: 0x2800,
            0x0806DBF6: 0x1E60,
        },
        "percentage passive target handlers",
    )
    _expect(_u32(rom, 0x0806DB80), 999, "max HP percentage cap")

    jump_table_raw = rom[
        _offset(FLAT_JUMP_TABLE) :
        _offset(FLAT_JUMP_TABLE) + 4 * len(FLAT_JUMP_TABLE_ENTRIES)
    ]
    _expect(
        hashlib.sha256(jump_table_raw).hexdigest(),
        FLAT_JUMP_TABLE_SHA256,
        "flat passive jump table SHA-256",
    )
    jump_table_entries = struct.unpack(
        "<10I",
        jump_table_raw,
    )
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
    _expect_halfwords(
        rom,
        {
            0x0806DCA4: 0x89F1,
            0x0806DCC8: 0x7A31,
            0x0806DCCC: 0x2809,
            0x0806DCE8: 0x78B1,
            0x0806DCEC: 0x2863,
            0x0806DD08: 0x78F1,
            0x0806DD0C: 0x2863,
            0x0806DD28: 0x7931,
            0x0806DD2C: 0x2863,
            0x0806DD48: 0x7971,
            0x0806DD4C: 0x2809,
            0x0806DD68: 0x79B1,
            0x0806DD6C: 0x2863,
        },
        "flat passive target handlers",
    )
    _expect(_u32(rom, 0x0806DCC4), 999, "max HP flat cap")

    percentage_targets = {
        "2": {
            "field": "max_hp",
            "operation": "increase_percent",
            "cap": 999,
        },
        "6": {
            "field": "defense",
            "operation": "increase_percent",
            "cap": 99,
        },
        "8": {
            "field": "agility",
            "operation": "increase_percent",
            "cap": 99,
        },
        "11": {
            "field": "hand_seals",
            "operation": "reduce_percent",
            "minimum": 1,
        },
    }
    flat_targets = {
        "1": {
            "field": "max_hp",
            "operation": "add",
            "cap": 999,
        },
        "2": {"operation": "no_op"},
        "3": {
            "field": "chakra_capacity",
            "operation": "add",
            "cap": 9,
        },
        "4": {
            "field": "attack",
            "operation": "add",
            "cap": 99,
        },
        "5": {
            "field": "defense",
            "operation": "add",
            "cap": 99,
        },
        "6": {"operation": "no_op"},
        "7": {
            "field": "agility",
            "operation": "add",
            "cap": 99,
        },
        "8": {"operation": "no_op"},
        "9": {
            "field": "movement",
            "operation": "add",
            "cap": 9,
        },
        "10": {
            "field": "ninja_tool_capacity",
            "operation": "add",
            "cap": 99,
        },
    }
    return {
        "schema_version": 1,
        "identity": "battle_persistent_passive_stat_bindings",
        "rom": str(rom_path),
        "rom_sha256": rom_sha256,
        "function": {
            "range": "0x0806D964..0x0806DDA3",
            "sha256": FUNCTION_SHA256,
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
        "pass_order": [
            "percentage_and_reduction",
            "flat_addition",
        ],
        "passes": {
            "percentage_and_reduction": {
                "range": "0x0806DAE6..0x0806DC19",
                "sha256": PERCENTAGE_PASS_SHA256,
                "targets": percentage_targets,
            },
            "flat_addition": {
                "range": "0x0806DC1A..0x0806DD95",
                "sha256": FLAT_PASS_SHA256,
                "jump_table": f"0x{FLAT_JUMP_TABLE:08X}",
                "jump_table_sha256": FLAT_JUMP_TABLE_SHA256,
                "jump_table_entries": [
                    f"0x{entry:08X}"
                    for entry in jump_table_entries
                ],
                "targets": flat_targets,
            },
        },
        "boundary": (
            "Targets 1-11 are consumed directly inside the character stat "
            "loader rather than through the generic passive query at "
            "0x0806DDA4. Target 10 raises the byte-valued capacity stat up "
            "to 99; this manifest does not infer the separate equipment "
            "slot or per-tool capacity-allocation rules."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_persistent_passive_stat_manifest(args.rom)
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
