#!/usr/bin/env python3
"""Export the frozen physical battle-condition record table."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from typing import Any


SCHEMA = "rom-battle-condition-records-v1"
JSON_NAME = "battle-condition-records.json"
BIN_NAME = "battle-condition-records.bin"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

TABLE_START = 0x00594758
TABLE_END = 0x00596CCC
TABLE_GBA_START = ROM_BASE + TABLE_START
TABLE_GBA_END = ROM_BASE + TABLE_END
TABLE_SIZE = TABLE_END - TABLE_START
TABLE_SHA256 = "0d6e137011aa4e97c5b5d165f1939b7fb0b33235b9b20fceb1566b485dc35bf4"
BATTLE_COUNT = 47
BATTLE_STRIDE = 0xCC
VARIANTS_PER_BATTLE = 3
VARIANT_STRIDE = 0x44
VARIANT_COUNT = BATTLE_COUNT * VARIANTS_PER_BATTLE
GROUP_COUNT = 2
SLOTS_PER_GROUP = 4
GROUP_STRIDE = 0x20
PREFIX_SIZE = 4
PREDICATE_STRIDE = 8
PREDICATE_SLOT_COUNT = VARIANT_COUNT * GROUP_COUNT * SLOTS_PER_GROUP

PREFIX_RANGE_SHA256 = "1e2e792bf9c4fd75afe20481e55ca3ba7ea0374b88db95e7dad918b52f8bdd2d"
PREFIX_BYTES_SHA256 = "45ca80c7d87e05305a9677c54c552161834f1829c298b0d2078924e0947d950c"
PREDICATE_PAYLOAD_RANGE_SHA256 = "240541fbf33b129c71076b7dbbed0fa12c5e4e58cc4d0df91dd406b96e22c958"
PREDICATE_PAYLOAD_BYTES_SHA256 = "f429071eb67753a70d01e5ea056a1853646598cda81866adaa82630c13f17f7e"
PREDICATE_SLOT_RANGE_SHA256 = "c9156961326d3ea4e7ba99f85c1860c3c6bfe587edbe79cda6fd5a5b541d7f6a"
PREDICATE_SLOT_BYTES_SHA256 = "f429071eb67753a70d01e5ea056a1853646598cda81866adaa82630c13f17f7e"

INTERPRETER_START = 0x0777FC
INTERPRETER_END = 0x077C1C
INTERPRETER_SHA256 = "d3d27daffc790de8896f7d2194ae110f8e839e7095c95b2f708dacbe527e152e"
CORE_SLICE_START = 0x07781C
CORE_SLICE_END = 0x07786A
CORE_SLICE_SHA256 = "459ff8159f6db352869fc58aaa5862820ecaa5aa4d209cbd8df9e0656d91cc2a"
CALLER_START = 0x07305C
CALLER_END = 0x0731D0
CALLER_SHA256 = "6d2208001cebc68f565fd30aaf1a0068549f0cb7c675faedc9c346cec6cc2240"
DISPATCH_START = 0x077878
DISPATCH_END = 0x07789C
DISPATCH_SHA256 = "3365c0bb46f11c4cb369b1f8c1d1a9f614907f20e3cd7ce9889d389c1d7348f7"
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
TABLE_CONTROL_LITERAL_OFFSET = 0x07786C
TABLE_BASE_LITERAL_OFFSET = 0x077870
JUMP_TABLE_POINTER_OFFSET = 0x077874
TABLE_CONTROL_LITERAL = 0x02026804

NON_CLAIM_FIELDS = (
    "all_battle_ids_naturally_reached_claimed",
    "all_variant_indices_naturally_reached_claimed",
    "all_predicate_slots_naturally_evaluated_claimed",
    "all_condition_consumers_exhausted_claimed",
    "computed_or_ram_consumers_exhausted_claimed",
    "prefix_field_semantics_claimed",
    "prefix_padding_or_reserved_claimed",
    "byte3_field_semantics_claimed",
    "payload_word_business_semantics_claimed",
    "handlers_4_5_naturally_used_claimed",
    "battlefield_object_visible_behavior_names_claimed",
    "all_battle_conditions_semantically_named_claimed",
    "complete_objective_engine_claimed",
    "positions_condition_business_relation_claimed",
    "existing_primary_owner_reclassification_claimed",
    "right_gap_structure_claimed",
    "right_gap_padding_claimed",
    "runtime_trigger_coverage_claimed",
    "editing_safety_claimed",
    "writeback_safety_claimed",
    "relocation_safety_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _compact(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _u16(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("Thumb halfword escapes the ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _u32(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError("literal word escapes the ROM")
    return int.from_bytes(rom[offset : offset + 4], "little")


def _expect_halfword(rom: bytes, offset: int, expected: int, label: str) -> int:
    actual = _u16(rom, offset)
    if actual != expected:
        raise ValueError(f"{label} changed: expected 0x{expected:04X}, got 0x{actual:04X}")
    return actual


def _validate_root(root: Path) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    return resolved


def _safe_input(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _implementation_identities(root: Path) -> dict[str, dict[str, str]]:
    paths = {
        "exporter": Path("tools/export_rom_battle_condition_records.py"),
        "verifier": Path("tools/verify_rom_battle_condition_records.py"),
        "tests": Path("tests/test_export_rom_battle_condition_records.py"),
    }
    result: dict[str, dict[str, str]] = {}
    for role, relative in paths.items():
        path = _safe_input(root, relative)
        result[role] = {"path": relative.as_posix(), "sha256": _sha(path.read_bytes())}
    return result


def _decode_ldr_literal(
    rom: bytes,
    offset: int,
    expected_halfword: int,
    expected_register: int,
    expected_literal_offset: int,
    expected_value: int,
    label: str,
) -> dict[str, int]:
    instruction = _expect_halfword(rom, offset, expected_halfword, label)
    if instruction & 0xF800 != 0x4800:
        raise ValueError(f"{label} is not a Thumb PC-relative LDR")
    register = (instruction >> 8) & 7
    immediate = (instruction & 0xFF) * 4
    literal_address = ((ROM_BASE + offset + 4) & ~3) + immediate
    literal_offset = literal_address - ROM_BASE
    value = _u32(rom, literal_offset)
    if register != expected_register:
        raise ValueError(f"{label} destination register changed")
    if literal_offset != expected_literal_offset or value != expected_value:
        raise ValueError(f"{label} literal resolution changed")
    return {
        "file_offset": offset,
        "gba_address": ROM_BASE + offset,
        "halfword": instruction,
        "literal_file_offset": literal_offset,
        "literal_gba_address": literal_address,
        "literal_word_le": value,
    }


def _branch_target(offset: int, halfword: int, conditional: bool) -> int:
    if conditional:
        if halfword & 0xF000 != 0xD000:
            raise ValueError("expected Thumb conditional branch")
        immediate = halfword & 0xFF
        if immediate & 0x80:
            immediate -= 0x100
    else:
        if halfword & 0xF800 != 0xE000:
            raise ValueError("expected Thumb unconditional branch")
        immediate = halfword & 0x7FF
        if immediate & 0x400:
            immediate -= 0x800
    return offset + 4 + immediate * 2


def _raw_instruction(rom: bytes, offset: int, halfword: int, label: str) -> dict[str, Any]:
    actual = _expect_halfword(rom, offset, halfword, label)
    return {
        "file_offset": offset,
        "gba_address": ROM_BASE + offset,
        "halfword": actual,
        "raw_hex": rom[offset : offset + 2].hex(),
    }


def decode_consumer_contract(rom: bytes) -> dict[str, Any]:
    """Decode the frozen raw Thumb consumer and loop evidence."""
    if len(rom) != ROM_SIZE:
        raise ValueError("consumer decoder requires the complete ROM")
    table = rom[TABLE_START:TABLE_END]
    if len(table) != TABLE_SIZE or _sha(table) != TABLE_SHA256:
        raise ValueError("battle condition table identity changed")

    interpreter = rom[INTERPRETER_START:INTERPRETER_END]
    core_slice = rom[CORE_SLICE_START:CORE_SLICE_END]
    caller = rom[CALLER_START:CALLER_END]
    if _sha(interpreter) != INTERPRETER_SHA256:
        raise ValueError("condition interpreter identity changed")
    if _sha(core_slice) != CORE_SLICE_SHA256:
        raise ValueError("core selector slice identity changed")
    if _sha(caller) != CALLER_SHA256:
        raise ValueError("condition caller identity changed")

    control_load = _decode_ldr_literal(
        rom, 0x07781C, 0x4A13, 2, TABLE_CONTROL_LITERAL_OFFSET, TABLE_CONTROL_LITERAL, "battle control LDR"
    )
    _expect_halfword(rom, 0x07781E, 0x7851, "battle ID LDRB")
    _expect_halfword(rom, 0x077820, 0x20CC, "battle stride MOVS")
    _expect_halfword(rom, 0x077822, 0x1C0B, "battle stride ADDS")
    _expect_halfword(rom, 0x077824, 0x4343, "battle stride MULS")
    _expect_halfword(rom, 0x077826, 0x7891, "variant LDRB")
    _expect_halfword(rom, 0x077828, 0x0108, "variant LSLS")
    _expect_halfword(rom, 0x07782A, 0x1840, "variant ADDS")
    _expect_halfword(rom, 0x07782C, 0x0080, "variant LSLS by two")
    table_load = _decode_ldr_literal(
        rom, 0x07782E, 0x4910, 1, TABLE_BASE_LITERAL_OFFSET, TABLE_GBA_START, "table base LDR"
    )
    _expect_halfword(rom, 0x077830, 0x1840, "variant/table ADDS")
    _expect_halfword(rom, 0x077840, 0x0149, "group index LSLS")
    _expect_halfword(rom, 0x07784C, 0x3004, "prefix skip ADDS")
    _expect_halfword(rom, 0x077852, 0x00F9, "predicate stride LSLS")
    _expect_halfword(rom, 0x077856, 0x7828, "condition type LDRB")
    _expect_halfword(rom, 0x077858, 0x3801, "condition type SUBS")
    _expect_halfword(rom, 0x07785A, 0x2808, "condition type CMP")
    _expect_halfword(rom, 0x07783C, 0x2700, "slot initialization")

    slot_loop_offsets = list(range(0x077B3A, 0x077B46, 2))
    slot_loop_halfwords = [0x1C78, 0x0600, 0x0E07, 0x2F03, 0xD800, 0xE681]
    slot_raw = [
        _raw_instruction(rom, offset, expected, "slot loop instruction")
        for offset, expected in zip(slot_loop_offsets, slot_loop_halfwords)
    ]
    slot_exit = _branch_target(slot_loop_offsets[4], slot_loop_halfwords[4], True)
    slot_back = _branch_target(slot_loop_offsets[5], slot_loop_halfwords[5], False)
    if slot_exit != 0x077B46 or slot_back != 0x07784A:
        raise ValueError("slot loop branch target changed")

    group_loop_offsets = list(range(0x077B46, 0x077B54, 2))
    group_loop_halfwords = [0x4649, 0x0608, 0x0E00, 0x4684, 0x2801, 0xD800, 0xE673]
    group_raw = [
        _raw_instruction(rom, offset, expected, "group loop instruction")
        for offset, expected in zip(group_loop_offsets, group_loop_halfwords)
    ]
    group_exit = _branch_target(group_loop_offsets[5], group_loop_halfwords[5], True)
    group_back = _branch_target(group_loop_offsets[6], group_loop_halfwords[6], False)
    if group_exit != 0x077B54 or group_back != 0x07783C:
        raise ValueError("group loop branch target changed")

    literal_bytes = rom[TABLE_CONTROL_LITERAL_OFFSET : TABLE_BASE_LITERAL_OFFSET + 4]
    if literal_bytes != bytes.fromhex("0468020258475908"):
        raise ValueError("battle-control/table-base literal bytes changed")
    jump_pointer = _u32(rom, JUMP_TABLE_POINTER_OFFSET)
    if jump_pointer != 0x08077878:
        raise ValueError("dispatch table pointer literal changed")
    dispatch_bytes = rom[DISPATCH_START:DISPATCH_END]
    if _sha(dispatch_bytes) != DISPATCH_SHA256:
        raise ValueError("dispatch table identity changed")
    dispatch = list(struct.unpack("<9I", dispatch_bytes))
    if dispatch != DISPATCH_TARGETS:
        raise ValueError("dispatch targets changed")

    required_offsets = [
        0x07781C,
        0x07781E,
        0x077820,
        0x077822,
        0x077824,
        0x077826,
        0x077828,
        0x07782A,
        0x07782C,
        0x07782E,
        0x077830,
        0x07783C,
        0x077840,
        0x07784C,
        0x077852,
        0x077856,
        0x077858,
        0x07785A,
    ]
    required_halfwords = [
        0x4A13,
        0x7851,
        0x20CC,
        0x1C0B,
        0x4343,
        0x7891,
        0x0108,
        0x1840,
        0x0080,
        0x4910,
        0x1840,
        0x2700,
        0x0149,
        0x3004,
        0x00F9,
        0x7828,
        0x3801,
        0x2808,
    ]
    raw_instructions = [
        _raw_instruction(rom, offset, halfword, "core consumer instruction")
        for offset, halfword in zip(required_offsets, required_halfwords)
    ]
    raw_instructions.extend(slot_raw)
    raw_instructions.extend(group_raw)
    raw_instructions.sort(key=lambda row: row["file_offset"])
    return {
        "interpreter": {
            "file_range": [INTERPRETER_START, INTERPRETER_END],
            "gba_range": [ROM_BASE + INTERPRETER_START, ROM_BASE + INTERPRETER_END],
            "byte_size": INTERPRETER_END - INTERPRETER_START,
            "sha256": _sha(interpreter),
        },
        "core_selector_slice": {
            "file_range": [CORE_SLICE_START, CORE_SLICE_END],
            "gba_range": [ROM_BASE + CORE_SLICE_START, ROM_BASE + CORE_SLICE_END],
            "byte_size": CORE_SLICE_END - CORE_SLICE_START,
            "sha256": _sha(core_slice),
        },
        "caller": {
            "file_range": [CALLER_START, CALLER_END],
            "gba_range": [ROM_BASE + CALLER_START, ROM_BASE + CALLER_END],
            "byte_size": CALLER_END - CALLER_START,
            "sha256": _sha(caller),
        },
        "literals": {
            "file_range": [TABLE_CONTROL_LITERAL_OFFSET, TABLE_BASE_LITERAL_OFFSET + 4],
            "gba_range": [ROM_BASE + TABLE_CONTROL_LITERAL_OFFSET, ROM_BASE + TABLE_BASE_LITERAL_OFFSET + 4],
            "raw_hex": literal_bytes.hex(),
            "words_le": [TABLE_CONTROL_LITERAL, TABLE_GBA_START],
            "battle_control": control_load,
            "table_base": table_load,
        },
        "dispatch": {
            "pointer_file_offset": JUMP_TABLE_POINTER_OFFSET,
            "pointer_gba_address": ROM_BASE + JUMP_TABLE_POINTER_OFFSET,
            "pointer_word_le": jump_pointer,
            "file_range": [DISPATCH_START, DISPATCH_END],
            "gba_range": [ROM_BASE + DISPATCH_START, ROM_BASE + DISPATCH_END],
            "byte_size": DISPATCH_END - DISPATCH_START,
            "sha256": _sha(dispatch_bytes),
            "types": list(range(1, 10)),
            "targets": dispatch,
            "raw_words_le": dispatch,
        },
        "formula": {
            "table_base_gba_address": TABLE_GBA_START,
            "battle_control_gba_address": TABLE_CONTROL_LITERAL,
            "battle_id_load_offset": 1,
            "battle_stride": BATTLE_STRIDE,
            "variant_index_load_offset": 2,
            "variant_stride": VARIANT_STRIDE,
            "group_stride": GROUP_STRIDE,
            "prefix_size": PREFIX_SIZE,
            "predicate_stride": PREDICATE_STRIDE,
            "slots_per_group": SLOTS_PER_GROUP,
            "group_count": GROUP_COUNT,
            "address_expression": "table_base + battle_id * 0xCC + variant_index * 0x44 + group_index * 0x20 + 0x04 + slot_index * 0x08",
        },
        "raw_instructions": raw_instructions,
        "loops": {
            "slot": {
                "file_range": [0x077B3A, 0x077B46],
                "gba_range": [ROM_BASE + 0x077B3A, ROM_BASE + 0x077B46],
                "halfwords": slot_loop_halfwords,
                "compare_immediate": 3,
                "count": 4,
                "conditional_exit_file_offset": slot_exit,
                "back_edge_file_offset": slot_back,
            },
            "group": {
                "file_range": [0x077B46, 0x077B54],
                "gba_range": [ROM_BASE + 0x077B46, ROM_BASE + 0x077B54],
                "halfwords": group_loop_halfwords,
                "compare_immediate": 1,
                "count": 2,
                "conditional_exit_file_offset": group_exit,
                "back_edge_file_offset": group_back,
            },
        },
    }


def _range_hash(ranges: list[list[int]]) -> str:
    return _sha(_compact(ranges))


def _variant_offsets() -> list[tuple[int, int, int]]:
    return [
        (battle_id, variant_index, TABLE_START + battle_id * BATTLE_STRIDE + variant_index * VARIANT_STRIDE)
        for battle_id in range(BATTLE_COUNT)
        for variant_index in range(VARIANTS_PER_BATTLE)
    ]


def _record_row(rom: bytes, battle_id: int, variant_index: int, start: int) -> dict[str, Any]:
    prefix = rom[start : start + PREFIX_SIZE]
    groups: dict[str, dict[str, Any]] = {}
    for name, group_offset in (("win", PREFIX_SIZE), ("lose", PREFIX_SIZE + GROUP_STRIDE)):
        group_start = start + group_offset
        predicates = []
        for slot_index in range(SLOTS_PER_GROUP):
            slot_start = group_start + slot_index * PREDICATE_STRIDE
            raw = rom[slot_start : slot_start + PREDICATE_STRIDE]
            if len(raw) != PREDICATE_STRIDE:
                raise ValueError("predicate slot escapes the complete table")
            condition_type, arg0, arg1, byte3_raw, payload_word = struct.unpack("<BBBBI", raw)
            predicates.append(
                {
                    "slot_index": slot_index,
                    "file_range": [slot_start, slot_start + PREDICATE_STRIDE],
                    "gba_range": [ROM_BASE + slot_start, ROM_BASE + slot_start + PREDICATE_STRIDE],
                    "address": ROM_BASE + slot_start,
                    "raw_hex": raw.hex(),
                    "condition_type": condition_type,
                    "arg0": arg0,
                    "arg1": arg1,
                    "byte3_raw": byte3_raw,
                    "payload_word_le_raw": payload_word,
                }
            )
        groups[name] = {
            "file_range": [group_start, group_start + GROUP_STRIDE],
            "gba_range": [ROM_BASE + group_start, ROM_BASE + group_start + GROUP_STRIDE],
            "predicates": predicates,
        }
    return {
        "battle_id": battle_id,
        "variant_index": variant_index,
        "file_range": [start, start + VARIANT_STRIDE],
        "gba_range": [ROM_BASE + start, ROM_BASE + start + VARIANT_STRIDE],
        "address": ROM_BASE + start,
        "prefix_file_range": [start, start + PREFIX_SIZE],
        "prefix_gba_range": [ROM_BASE + start, ROM_BASE + start + PREFIX_SIZE],
        "prefix_bytes": list(prefix),
        "prefix_bytes_hex": prefix.hex(),
        "win": groups["win"],
        "lose": groups["lose"],
    }


def build_payload(root: Path) -> dict[str, Any]:
    root = _validate_root(root)
    rom_path = _safe_input(root, ROM_PATH)
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity changed")
    table = rom[TABLE_START:TABLE_END]
    if len(table) != TABLE_SIZE or _sha(table) != TABLE_SHA256:
        raise ValueError("battle condition table identity changed")

    offsets = _variant_offsets()
    variants = [_record_row(rom, battle_id, variant_index, start) for battle_id, variant_index, start in offsets]
    prefix_ranges = [[start, start + PREFIX_SIZE] for _, _, start in offsets]
    payload_ranges = [[start + PREFIX_SIZE, start + VARIANT_STRIDE] for _, _, start in offsets]
    slot_ranges = [
        [start + group_offset + slot * PREDICATE_STRIDE, start + group_offset + (slot + 1) * PREDICATE_STRIDE]
        for _, _, start in offsets
        for group_offset in (PREFIX_SIZE, PREFIX_SIZE + GROUP_STRIDE)
        for slot in range(SLOTS_PER_GROUP)
    ]
    denominator_hashes = {
        "prefix_ranges_json_sha256": _range_hash(prefix_ranges),
        "prefix_bytes_sha256": _sha(b"".join(rom[a:b] for a, b in prefix_ranges)),
        "predicate_payload_ranges_json_sha256": _range_hash(payload_ranges),
        "predicate_payload_bytes_sha256": _sha(b"".join(rom[a:b] for a, b in payload_ranges)),
        "predicate_slot_ranges_json_sha256": _range_hash(slot_ranges),
        "predicate_slot_bytes_sha256": _sha(b"".join(rom[a:b] for a, b in slot_ranges)),
    }
    expected_denominators = {
        "prefix_ranges_json_sha256": PREFIX_RANGE_SHA256,
        "prefix_bytes_sha256": PREFIX_BYTES_SHA256,
        "predicate_payload_ranges_json_sha256": PREDICATE_PAYLOAD_RANGE_SHA256,
        "predicate_payload_bytes_sha256": PREDICATE_PAYLOAD_BYTES_SHA256,
        "predicate_slot_ranges_json_sha256": PREDICATE_SLOT_RANGE_SHA256,
        "predicate_slot_bytes_sha256": PREDICATE_SLOT_BYTES_SHA256,
    }
    if denominator_hashes != expected_denominators:
        raise ValueError("battle condition denominator identity changed")

    predicates = [
        row
        for variant in variants
        for group_name in ("win", "lose")
        for row in variant[group_name]["predicates"]
    ]
    prefix_frequency = Counter(variant["prefix_bytes_hex"] for variant in variants)
    type_counts = Counter(str(row["condition_type"]) for row in predicates)
    prefix_nonzero = sum(byte != 0 for variant in variants for byte in variant["prefix_bytes"])
    payload_nonzero = [row["payload_word_le_raw"] for row in predicates if row["payload_word_le_raw"] != 0]
    if any(row["byte3_raw"] != 0 for row in predicates):
        raise ValueError("predicate byte3_raw value identity changed")
    if dict(prefix_frequency) != {"00000000": 122, "0f000000": 6, "14000000": 3, "0a000000": 2, "ff000000": 8}:
        raise ValueError("prefix frequency identity changed")
    if dict(type_counts) != {"0": 898, "1": 155, "2": 11, "3": 18, "6": 8, "7": 16, "8": 16, "9": 6}:
        raise ValueError("condition type count identity changed")
    if prefix_nonzero != 19 or len(payload_nonzero) != 230 or len(set(payload_nonzero)) != 219:
        raise ValueError("battle condition value statistics changed")

    consumer = decode_consumer_contract(rom)
    non_claims = {field: False for field in NON_CLAIM_FIELDS}
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _sha(rom)},
        "table": {
            "file_range": [TABLE_START, TABLE_END],
            "gba_range": [TABLE_GBA_START, TABLE_GBA_END],
            "byte_size": TABLE_SIZE,
            "byte_sha256": _sha(table),
            "battle_count": BATTLE_COUNT,
            "battle_stride": BATTLE_STRIDE,
            "variants_per_battle": VARIANTS_PER_BATTLE,
            "variant_stride": VARIANT_STRIDE,
            "variant_count": VARIANT_COUNT,
            "predicate_slot_count": PREDICATE_SLOT_COUNT,
            "denominator_hashes": denominator_hashes,
        },
        "consumer": consumer,
        "variants": variants,
        "statistics": {
            "prefix_frequency_map": dict(prefix_frequency),
            "prefix_nonzero_byte_count": prefix_nonzero,
            "condition_type_counts": dict(type_counts),
            "byte3_raw_zero_count": sum(row["byte3_raw"] == 0 for row in predicates),
            "payload_word_le_raw_nonzero_count": len(payload_nonzero),
            "payload_word_le_raw_nonzero_distinct_count": len(set(payload_nonzero)),
        },
        "scope": {
            "complete_physical_table": True,
            "raw_interpreter_bound_layout": True,
            "coverage_classification_performed": False,
            "non_claims": non_claims,
        },
        "non_claims": non_claims,
        "implementation": _implementation_identities(root),
    }


def _validate_output_path(root: Path, output_dir: Path) -> Path:
    requested = Path(output_dir).expanduser()
    if requested.is_symlink():
        raise ValueError("output directory uses a symlink")
    absolute = requested.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var")}:
            raise ValueError("output directory path uses a symlink")
    resolved = absolute.resolve()
    if resolved == root:
        raise ValueError("output directory cannot be the repository root")
    if resolved in root.parents:
        raise ValueError("output directory cannot be an ancestor of repository root")
    if requested.exists() and not requested.is_dir():
        raise ValueError("output directory is not a directory")
    if requested.exists() and any(requested.iterdir()):
        raise ValueError("output directory is non-empty or contains foreign files")
    return absolute


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = _validate_root(root)
    output = _validate_output_path(root, output_dir)
    payload = build_payload(root)
    binary = _safe_input(root, ROM_PATH).read_bytes()[TABLE_START:TABLE_END]
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{SCHEMA}-", dir=parent))
    try:
        (temporary / JSON_NAME).write_bytes(_canonical(payload))
        (temporary / BIN_NAME).write_bytes(binary)
        os.replace(temporary, output)
    except Exception:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()
        raise
    return {
        "schema": SCHEMA,
        "files": {
            JSON_NAME: _sha((output / JSON_NAME).read_bytes()),
            BIN_NAME: _sha((output / BIN_NAME).read_bytes()),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--out-dir", "--output-dir", dest="out_dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_artifact(args.root, args.out_dir), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
