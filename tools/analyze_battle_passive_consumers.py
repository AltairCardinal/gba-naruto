#!/usr/bin/env python3
"""Inventory every direct passive query and bind proven consumer formulas."""

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

from tools.thumb_branch import find_thumb_branches


ROM_BASE = 0x08000000
PASSIVE_QUERY = 0x0806DDA4
HP_RESTORATION_START = 0x08077C1C
HP_RESTORATION_END = 0x08077C54
HP_RESTORATION_SHA256 = (
    "4e8b5f365ae591a3ae8580863dcdef4554bcee9e29f7379c0c3d3b48efbdb507"
)
BATTLE_EXPERIENCE_START = 0x08089064
BATTLE_EXPERIENCE_END = 0x080890F0
BATTLE_EXPERIENCE_SHA256 = (
    "03f7940fd622b6c1b97c54b710c97006c2dd2a804b5e276dc8c916ed0f95900c"
)
TERRAIN_CONFIGURATION_START = 0x08069DB8
TERRAIN_CONFIGURATION_END = 0x08069E44
TERRAIN_CONFIGURATION_SHA256 = (
    "415a0f9cb1ab184f6b40d257a82905abb4201c7a2d8723621624ecbf2bf786fb"
)
TERRAIN_SEARCH_START = 0x080698B4
TERRAIN_SEARCH_END = 0x08069D1C
TERRAIN_SEARCH_SHA256 = (
    "143a7223550ccd44c69615b39e76fc2f96e7ba4ec62671a9ff6de62adaa844aa"
)
EXPECTED_CALLS = (
    (0x08069DD0, 0x1A, "terrain_traversal_configuration"),
    (0x08069DF0, 0x1B, "terrain_traversal_configuration"),
    (0x08069E0A, 0x1C, "terrain_traversal_configuration"),
    (0x0806DFCC, 0x1D, "side_start_trigger"),
    (0x0806E032, 0x1E, "side_start_trigger"),
    (0x0806E0AC, 0x1F, "side_start_trigger"),
    (0x0806E118, 0x20, "side_start_trigger"),
    (0x0807613A, 0x0C, "per_hit_modifier"),
    (0x0807618C, 0x19, "per_hit_modifier"),
    (0x0807629C, 0x16, "battlefield_event_gate"),
    (0x080762C0, 0x17, "battlefield_event_gate"),
    (0x080762E4, 0x18, "battlefield_event_gate"),
    (0x0807689E, 0x1F, "effect_0x0e_marker_override"),
    (0x08077C34, 0x14, "hp_restoration_bonus"),
    (0x080890C2, 0x15, "battle_experience_bonus"),
)


def _offset(address: int) -> int:
    return address - ROM_BASE


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, _offset(address))[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(
            f"{label} mismatch: expected {expected!r}, got {actual!r}"
        )


def _hex(address: int) -> str:
    return f"0x{address:08X}"


def _slice_sha256(rom: bytes, start: int, end: int) -> str:
    return hashlib.sha256(rom[_offset(start) : _offset(end)]).hexdigest()


def _target_type_before_call(rom: bytes, callsite: int) -> int:
    instruction = _u16(rom, callsite - 4)
    if instruction & 0xFF00 != 0x2100:
        raise ValueError(
            f"callsite {_hex(callsite)} does not load an immediate target type into r1"
        )
    return instruction & 0xFF


def build_passive_consumer_manifest(
    rom_path: Path | str,
) -> dict[str, Any]:
    rom_path = Path(rom_path)
    rom = rom_path.read_bytes()
    branches = find_thumb_branches(
        rom, PASSIVE_QUERY, rom_base=ROM_BASE
    )
    actual_calls = tuple(
        (branch.address, _target_type_before_call(rom, branch.address))
        for branch in branches
    )
    expected_calls = tuple(
        (callsite, target_type)
        for callsite, target_type, _ in EXPECTED_CALLS
    )
    _expect(actual_calls, expected_calls, "direct passive query inventory")

    hp_sha256 = _slice_sha256(
        rom, HP_RESTORATION_START, HP_RESTORATION_END
    )
    _expect(
        hp_sha256,
        HP_RESTORATION_SHA256,
        "HP restoration consumer SHA-256",
    )
    _expect(_u16(rom, 0x08077C22), 0x89E0, "maximum HP load")
    _expect(_u16(rom, 0x08077C24), 0x2105, "one-fifth divisor")
    _expect(_u16(rom, 0x08077C30), 0x2114, "restoration target type")
    _expect(_u16(rom, 0x08077C42), 0x8800, "passive value A load")
    _expect(_u16(rom, 0x08077C44), 0x1828, "restoration bonus add")

    experience_sha256 = _slice_sha256(
        rom, BATTLE_EXPERIENCE_START, BATTLE_EXPERIENCE_END
    )
    _expect(
        experience_sha256,
        BATTLE_EXPERIENCE_SHA256,
        "battle experience consumer SHA-256",
    )
    _expect(_u16(rom, 0x08089092), 0x7810, "unit character ID load")
    _expect(_u16(rom, 0x080890AA), 0x8800, "carried experience load")
    _expect(_u16(rom, 0x080890BE), 0x2115, "experience target type")
    _expect(_u16(rom, 0x080890D0), 0x8800, "experience value A load")
    _expect(_u16(rom, 0x080890D2), 0x4360, "experience multiply")
    _expect(_u16(rom, 0x080890D4), 0x2164, "percentage divisor")
    _expect(_u16(rom, 0x080890DA), 0x1820, "experience bonus add")

    terrain_configuration_sha256 = _slice_sha256(
        rom, TERRAIN_CONFIGURATION_START, TERRAIN_CONFIGURATION_END
    )
    _expect(
        terrain_configuration_sha256,
        TERRAIN_CONFIGURATION_SHA256,
        "terrain traversal configuration SHA-256",
    )
    terrain_search_sha256 = _slice_sha256(
        rom, TERRAIN_SEARCH_START, TERRAIN_SEARCH_END
    )
    _expect(
        terrain_search_sha256,
        TERRAIN_SEARCH_SHA256,
        "terrain traversal search SHA-256",
    )
    for address, expected in {
        0x08069DA4: 0x03005E28,
        0x08069DA8: 0x03005E29,
        0x08069DAC: 0x03005E2A,
        0x08069DB0: 0x03005E2B,
        0x08069DB4: 0x0201BE2A,
        0x08069908: 0x03005E29,
        0x08069924: 0x03005E2B,
        0x08069950: 0x03005E2A,
        0x08069CF8: 0x03005E29,
        0x08069CFC: 0x03005E2A,
        0x08069D00: 0x03005E2B,
    }.items():
        _expect(
            _u32(rom, address),
            expected,
            f"terrain traversal literal at {_hex(address)}",
        )
    for address, expected in {
        0x080698FC: 0x2401,
        0x0806991E: 0x2304,
        0x0806993A: 0x2402,
        0x08069C98: 0x2001,
        0x08069CAA: 0x9C03,
        0x08069CBA: 0x2004,
    }.items():
        _expect(
            _u16(rom, address),
            expected,
            f"terrain traversal opcode at {_hex(address)}",
        )

    consumed_types = {target_type for _, target_type in actual_calls}
    return {
        "schema_version": 1,
        "identity": "battle_passive_consumers",
        "rom": str(rom_path),
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "query_address": _hex(PASSIVE_QUERY),
        "direct_call_count": len(actual_calls),
        "direct_calls": [
            {
                "callsite": _hex(callsite),
                "target_type": target_type,
                "context": context,
            }
            for callsite, target_type, context in EXPECTED_CALLS
        ],
        "consumed_target_types": sorted(consumed_types),
        "unconsumed_target_types": [
            target_type
            for target_type in range(1, 0x21)
            if target_type not in consumed_types
        ],
        "verified_consumers": {
            "hp_restoration_bonus": {
                "function": (
                    f"{_hex(HP_RESTORATION_START)}.."
                    f"{_hex(HP_RESTORATION_END - 1)}"
                ),
                "sha256": hp_sha256,
                "target_type": 0x14,
                "formula": "floor(max_hp / 5) + value_a",
            },
            "battle_experience_bonus": {
                "function": (
                    f"{_hex(BATTLE_EXPERIENCE_START)}.."
                    f"{_hex(BATTLE_EXPERIENCE_END - 1)}"
                ),
                "sha256": experience_sha256,
                "target_type": 0x15,
                "formula": (
                    "battle_experience + "
                    "floor(battle_experience * value_a / 100)"
                ),
            },
            "terrain_traversal_limits": {
                "configuration_function": (
                    f"{_hex(TERRAIN_CONFIGURATION_START)}.."
                    f"{_hex(TERRAIN_CONFIGURATION_END - 1)}"
                ),
                "configuration_sha256": terrain_configuration_sha256,
                "search_function": (
                    f"{_hex(TERRAIN_SEARCH_START)}.."
                    f"{_hex(TERRAIN_SEARCH_END - 1)}"
                ),
                "search_sha256": terrain_search_sha256,
                "target_to_terrain_class": {
                    "26": 1,
                    "27": 7,
                    "28": 3,
                },
                "limit_formula": (
                    "base_a + per_level_a * (stored_level - 1)"
                ),
                "consumption": (
                    "one matching terrain tile per path step, including "
                    "the starting tile; recursive return restores the limit"
                ),
                "blocked_class": 15,
            },
        },
        "boundary": (
            "The inventory proves direct requested target types. Only the two "
            "formula-bound consumers in verified_consumers are assigned gameplay "
            "semantics here; the remaining contexts require their own data-flow "
            "and runtime evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build_passive_consumer_manifest(args.rom)
    text = json.dumps(
        result, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
