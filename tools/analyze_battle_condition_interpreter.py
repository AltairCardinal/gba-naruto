#!/usr/bin/env python3
"""Extract the original battle condition record layout and outcome precedence."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
INTERPRETER = 0x080777FC
INTERPRETER_END = 0x08077C1C
INTERPRETER_SHA256 = "d3d27daffc790de8896f7d2194ae110f8e839e7095c95b2f708dacbe527e152e"
RECORD_BASE = 0x08594758
BATTLE_COUNT = 47
BATTLE_STRIDE = 0xCC
VARIANT_COUNT = 3
VARIANT_STRIDE = 0x44
HEADER_SIZE = 4
GROUP_SIZE = 0x20
PREDICATES_PER_GROUP = 4
PREDICATE_STRIDE = 8
JUMP_TABLE = 0x08077878
JUMP_TABLE_SHA256 = "3365c0bb46f11c4cb369b1f8c1d1a9f614907f20e3cd7ce9889d389c1d7348f7"
RECORDS_SHA256 = "0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4"
RECORD_END = RECORD_BASE + BATTLE_COUNT * BATTLE_STRIDE
CALLER = 0x0807305C
CALLER_END = 0x080731D0
CALLER_SHA256 = "6d2208001cebc68f565fd30aaf1a0068549f0cb7c675faedc9c346cec6cc2240"
PRESENTATION_FUNCTION = 0x08072EDC
OBJECT_ALLOCATOR = 0x08081024
OBJECT_ALLOCATOR_END = 0x08081084
OBJECT_ALLOCATOR_SHA256 = "c2d9429855e9a91fabf5783581a0466a88a63f209dded259c359aef7e5ba73e8"
OBJECT_FREE = 0x08081084
OBJECT_FREE_END = 0x080810AC
OBJECT_FREE_SHA256 = "55e75115a5e31ff9d2c0dac24fd38848bb051599702c5d3618574155de884bee"
TYPE_9_COUNTER_WRITER = 0x08081984
TYPE_9_COUNTER_WRITER_END = 0x080819D2
TYPE_9_COUNTER_WRITER_SHA256 = "ff87581daed02b45790ab554bca7d6fe54693a771f84cddfae2f2b4c84c11686"
DISPATCH_TARGETS = [
    0x0807789C,
    0x08077904,
    0x08077924,
    0x08077994,
    0x080779B4,
    0x080779D4,
    0x080779EC,
    0x08077A78,
    0x08077AFC,
]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _offset(address: int) -> int:
    return address - ROM_BASE


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _parse_predicate(rom: bytes, offset: int) -> dict[str, Any]:
    condition_type, arg0, arg1, reserved, script = struct.unpack_from(
        "<BBBBI", rom, offset
    )
    _expect(reserved, 0, f"condition reserved byte at 0x{offset:06X}")
    return {
        "type": condition_type,
        "arg0": arg0,
        "arg1": arg1,
        "script": f"0x{script:08X}",
    }


def _parse_variant(rom: bytes, battle_id: int, variant: int) -> dict[str, Any]:
    address = RECORD_BASE + battle_id * BATTLE_STRIDE + variant * VARIANT_STRIDE
    offset = _offset(address)
    header = list(rom[offset : offset + HEADER_SIZE])

    def group(group_offset: int) -> list[dict[str, Any]]:
        return [
            _parse_predicate(
                rom,
                offset + group_offset + index * PREDICATE_STRIDE,
            )
            for index in range(PREDICATES_PER_GROUP)
        ]

    return {
        "address": f"0x{address:08X}",
        "header": header,
        "win": group(HEADER_SIZE),
        "lose": group(HEADER_SIZE + GROUP_SIZE),
    }


def build_condition_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    interpreter = rom[_offset(INTERPRETER) : _offset(INTERPRETER_END)]
    _expect(_sha256(interpreter), INTERPRETER_SHA256, "condition interpreter SHA-256")
    caller = rom[_offset(CALLER) : _offset(CALLER_END)]
    _expect(_sha256(caller), CALLER_SHA256, "condition caller SHA-256")
    jump_table = rom[_offset(JUMP_TABLE) : _offset(JUMP_TABLE) + 9 * 4]
    _expect(_sha256(jump_table), JUMP_TABLE_SHA256, "condition jump table SHA-256")
    dispatch = list(struct.unpack("<9I", jump_table))
    _expect(dispatch, DISPATCH_TARGETS, "condition dispatch targets")
    records_start = _offset(RECORD_BASE)
    records = rom[records_start : records_start + BATTLE_COUNT * BATTLE_STRIDE]
    _expect(_sha256(records), RECORDS_SHA256, "condition record bank SHA-256")
    object_allocator = rom[
        _offset(OBJECT_ALLOCATOR) : _offset(OBJECT_ALLOCATOR_END)
    ]
    _expect(
        _sha256(object_allocator),
        OBJECT_ALLOCATOR_SHA256,
        "battlefield object allocator SHA-256",
    )
    object_free = rom[_offset(OBJECT_FREE) : _offset(OBJECT_FREE_END)]
    _expect(
        _sha256(object_free),
        OBJECT_FREE_SHA256,
        "battlefield object free SHA-256",
    )
    type_9_counter_writer = rom[
        _offset(TYPE_9_COUNTER_WRITER) : _offset(TYPE_9_COUNTER_WRITER_END)
    ]
    _expect(
        _sha256(type_9_counter_writer),
        TYPE_9_COUNTER_WRITER_SHA256,
        "type-9 resolved-object counter writer SHA-256",
    )

    # The interpreter constructs base + battle_id*0xCC + variant*0x44 and visits
    # two groups of four 8-byte predicates. These literal checks keep the parser
    # tied to the actual controller rather than inferred sample addresses.
    _expect(_u32(rom, 0x0807786C), 0x02026804, "battle control literal")
    _expect(_u32(rom, 0x08077870), RECORD_BASE, "condition record base literal")
    _expect(_u32(rom, 0x08077920), 0x0202680C, "type-2 round index literal")
    _expect(_u32(rom, 0x080779E8), 0x02026604, "type-6 object table literal")
    _expect(_u32(rom, 0x08077A70), 0x0202680C, "type-7 round index literal")
    _expect(_u32(rom, 0x08077A74), 0x020240C0, "type-7 unit pool literal")
    _expect(_u32(rom, 0x08077AF4), 0x0202680C, "type-8 round index literal")
    _expect(_u32(rom, 0x08077AF8), 0x020240C0, "type-8 unit pool literal")
    _expect(_u32(rom, 0x08077BF0), 0x0202680C, "type-9 round index literal")

    # Validate the ordered win/loss first-match comparison and result codes.
    precedence = rom[_offset(0x08077B54) : _offset(0x08077BB6)]
    _expect(
        _sha256(precedence),
        "1b8f5184ce6889ec7eae007400d20d9e56228340ecb0002b60372528c384e546",
        "outcome precedence SHA-256",
    )
    returns = rom[_offset(0x08077BE6) : _offset(0x08077C1C)]
    _expect(
        _sha256(returns),
        "a646a09009fafddae7a6b3cbac239758f131fc694884d5816f05aca598b419e8",
        "outcome return block SHA-256",
    )

    all_variants = [
        _parse_variant(rom, battle_id, variant)
        for battle_id in range(BATTLE_COUNT)
        for variant in range(VARIANT_COUNT)
    ]
    observed_types = sorted(
        {
            predicate["type"]
            for variant in all_variants
            for group_name in ("win", "lose")
            for predicate in variant[group_name]
            if predicate["type"]
        }
    )
    _expect(
        observed_types,
        [1, 2, 3, 6, 7, 8, 9],
        "condition types used by record bank",
    )
    type_usage = Counter(
        predicate["type"]
        for variant in all_variants
        for group_name in ("win", "lose")
        for predicate in variant[group_name]
        if predicate["type"]
    )

    return {
        "schema_version": 1,
        "identity": "battle_condition_interpreter_and_ordered_outcome_precedence",
        "interpreter": f"0x{INTERPRETER:08X}",
        "caller": f"0x{CALLER:08X}",
        "presentation_function": f"0x{PRESENTATION_FUNCTION:08X}",
        "result_to_presentation_id": {"1": 1, "2": 2, "5": 3},
        "result_5_ends_battle": True,
        "record_base": f"0x{RECORD_BASE:08X}",
        "record_end": f"0x{RECORD_END:08X}",
        "battle_count": BATTLE_COUNT,
        "battle_stride": BATTLE_STRIDE,
        "variant_count": VARIANT_COUNT,
        "variant_stride": VARIANT_STRIDE,
        "header_size": HEADER_SIZE,
        "predicates_per_group": PREDICATES_PER_GROUP,
        "predicate_stride": PREDICATE_STRIDE,
        "dispatch_types": list(range(1, 10)),
        "dispatch_targets": [f"0x{target:08X}" for target in dispatch],
        "observed_record_types": observed_types,
        "record_type_usage": {
            str(condition_type): type_usage[condition_type]
            for condition_type in observed_types
        },
        "closed_semantics": {
            "type_1": "no_valid_unit_for_affiliation",
            "type_2": "round_limit_reached_at_round_boundary",
            "type_3": "no_valid_unit_for_character_and_affiliation",
            "type_6": "indexed_battlefield_object_slot_is_inactive",
            "type_7": "round_limit_selected_side_current_hp_sum_greater_than_opponent",
            "type_8": "round_limit_selected_side_valid_unit_count_greater_than_opponent",
            "type_9": "round_limit_selected_side_resolved_object_counter_greater_than_opponent",
        },
        "operational_addresses": {
            "round_limit": "0x0202680A",
            "round_index": "0x0202680C",
            "battlefield_object_table": "0x02026604",
            "battlefield_object_stride": 0x10,
            "battlefield_object_count": 32,
            "resolved_object_side_counter_base": "0x02026BC0",
            "unit_pool": "0x020240C0",
            "unit_stride": 0x1D4,
            "current_hp_offset": 0x0C,
        },
        "battlefield_object_lifecycle": {
            "allocate": f"0x{OBJECT_ALLOCATOR:08X}",
            "free": f"0x{OBJECT_FREE:08X}",
            "type_9_counter_writer": f"0x{TYPE_9_COUNTER_WRITER:08X}",
            "active_type_offset": 0,
            "x_offset": 1,
            "y_offset": 2,
            "behavior_offset": 6,
            "counter_writer_behavior": 9,
            "counter_increment": 1,
            "counter_side_source": "resolving_unit_affiliation_bit",
        },
        "outcome_precedence": {
            "neither_matches": 0,
            "only_win_matches": 1,
            "only_loss_matches": 2,
            "lower_first_match_index_wins": True,
            "same_first_match_index": 5,
        },
        "samples": {
            "battle_9_variant_0": _parse_variant(rom, 9, 0),
            "battle_15_variant_0": _parse_variant(rom, 15, 0),
            "battle_44_variant_0": _parse_variant(rom, 44, 0),
        },
        "conclusion": (
            "Each battle has three fixed condition variants. Every variant evaluates "
            "four ordered win predicates and four ordered loss predicates. When both "
            "groups match, the lower first-match slot wins; equal slots return result 5."
        ),
        "boundary": (
            "The record layout, type dispatch inventory, operational predicates for "
            "every record-used type, and ordered result arbitration are statically closed. "
            "The type-6 battlefield-object slot lifecycle and the type-9 behavior-9 "
            "resolution counter writer are also statically bound. The visible gameplay "
            "labels for object behaviors, the unused dispatch handlers 4 and 5, and "
            "runtime controls still require separate bindings. Result 5 is closed as a "
            "distinct presentation-ID 3 path that ends the battle, without assigning an "
            "unproven display label."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-condition-interpreter-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_condition_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
