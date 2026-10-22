#!/usr/bin/env python3
"""Independently verify the frozen positions auxiliary dispatch artifact."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "rom-positions-aux-dispatch-v1"
VERIFY_SCHEMA = "rom-positions-aux-dispatch-verification-v1"
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_RELATIVE = Path("rom/base.gba")
POSITIONS_RELATIVE = Path("sequel/content/positions/bank.json")
POSITIONS_SHA256 = "1e9d2822e486c6e79c9ad4f1545915fa378505dd1b58e840f939fd1032fd55e9"

BASE = 0x5461C4
GROUP_COUNT = 48
GROUP_STRIDE = 0x1AAC
VARIANT_COUNT = 3
VARIANT_STRIDE = 0x08E4
CANDIDATE_OFFSET = 0x08A4
CANDIDATE_END_OFFSET = 0x08E4
TABLE_COUNT = 144
BYTES_PER_TABLE = 0x40
CELL_COUNT = 16
CELL_STRIDE = 4
TOTAL_CELLS = 2304
TOTAL_BYTES = 9216

FUNCTION_RANGE = (0x06E810, 0x06E958)
FUNCTION_SHA256 = "bd30b1fd844bd3258666af5dfd739ef42401a1cfcabe680cd09055a6ec4785fd"
PREFIX_RANGE = (0x06E810, 0x06E850)
PREFIX_SHA256 = "558e09e265ea5802d8df4d6fc416bfe55e6717f9231381d2a7554d6362f8a722"
LITERALS_RANGE = (0x06E850, 0x06E864)
LITERALS_SHA256 = "39160eebab586c626c4b80c8eee9a57136ebb69808729311836b6b36919adc17"
DISPATCH_RANGE = (0x06E83A, 0x06E850)
DISPATCH_SHA256 = "c74238ef0b90b5f251a3bf71e9cf471a187efaa32836f8e83dc292a45f142e1d"
JUMP_LITERAL_RANGE = (0x06E864, 0x06E868)
JUMP_LITERAL_SHA256 = "e4fe803292766caeeed6856a18dafdeb481e3fb798997e76370e5fdb2b562ad5"
JUMP_TABLE_RANGE = (0x06E868, 0x06E884)
JUMP_TABLE_SHA256 = "2e7c3a263cf6d6410dd741d4e2439fabbc106ccca78c781bab8cd95ad998cd5d"
HANDLER_RANGE = (0x06E884, 0x06E950)
HANDLER_SHA256 = "a8c75fe5b7499a2d234bddfbbbf0ee72d99b8691c5264542f376afed8cb3a253"
CLOSURE_RANGE = (0x06E884, 0x06E958)
CLOSURE_SHA256 = "1084c91ec581ecb495bd6d42d61acffcced7663d86158a01974ab8e9b79a8460"
LOOP_RANGE = (0x06E944, 0x06E950)
LOOP_SHA256 = "d76e7e938f8292873e4551dc8f4d5133fd67aaad687ada05cecf6d43b61b28b8"

LITERAL_VALUES = {
    "wram_context": 0x02026804,
    "group_stride": GROUP_STRIDE,
    "variant_stride": VARIANT_STRIDE,
    "positions_base": 0x085461C4,
    "candidate_offset": CANDIDATE_OFFSET,
}
EXPECTED_JUMP_TARGETS = [
    0x0806E884,
    0x0806E884,
    0x0806E898,
    0x0806E8C8,
    0x0806E8E4,
    0x0806E8F8,
    0x0806E90C,
]
EXPECTED_BYTE1_READS = [
    0x06E886,
    0x06E898,
    0x06E8AA,
    0x06E8C8,
    0x06E8D8,
    0x06E8E6,
    0x06E8FA,
    0x06E90E,
    0x06E926,
]
EXPECTED_BYTE2_READS = [
    0x06E88A,
    0x06E8DC,
    0x06E8EA,
    0x06E8FE,
    0x06E916,
    0x06E92A,
    0x06E938,
]
EXPECTED_BYTE3_READS = [
    0x06E88C,
    0x06E8DE,
    0x06E8EC,
    0x06E900,
    0x06E918,
    0x06E92C,
    0x06E93A,
]
NON_CLAIM_FIELDS = (
    "runtime_group_bound_claimed",
    "runtime_variant_bound_claimed",
    "all_variants_naturally_reachable_claimed",
    "all_cells_naturally_reached_claimed",
    "all_tags_naturally_reached_claimed",
    "tag_business_semantics_claimed",
    "byte1_common_semantics_claimed",
    "byte2_common_semantics_claimed",
    "byte3_common_semantics_claimed",
    "byte3_padding_claimed",
    "byte3_reserved_claimed",
    "byte3_globally_unused_claimed",
    "free_space_claimed",
    "allocatable_space_claimed",
    "editing_safety_claimed",
    "writeback_or_relocation_safety_claimed",
    "abi_stability_claimed",
    "next_variant_headers_claimed",
    "final_post_candidate_gap_claimed",
    "existing_position_record_extension_claimed",
    "exhaustive_positions_aux_consumers_claimed",
)
PAYLOAD_NAME = "rom-positions-aux-dispatch.json"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME}


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _compact_hash(value: Any) -> str:
    return _digest(json.dumps(value, separators=(",", ":")).encode("ascii"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _bounded(data: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(data):
        raise ValueError("independent positions auxiliary slice escapes input")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4), "little")


def _root_directory(root: Path) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    return resolved


def _root_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
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


def _artifact_path(path: Path) -> Path:
    requested = Path(path).expanduser()
    cursor = Path(requested.anchor)
    for part in requested.absolute().parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            if cursor not in {Path("/var"), Path("/tmp")}:
                raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    return requested.resolve(strict=True)


def _expect(data: bytes, offset: int, halfword: int, label: str) -> None:
    if _u16(data, offset) != halfword:
        raise ValueError(f"independent {label} instruction changed")


def _literal_load(data: bytes, offset: int, label: str) -> tuple[int, int]:
    halfword = _u16(data, offset)
    if halfword & 0xF800 != 0x4800:
        raise ValueError(f"independent {label} literal load changed")
    return (halfword >> 8) & 7, ((offset + 4) & ~3) + ((halfword & 0xFF) << 2)


def _ldrb(data: bytes, offset: int, label: str) -> tuple[int, int, int]:
    halfword = _u16(data, offset)
    if halfword & 0xF800 != 0x7800:
        raise ValueError(f"independent {label} LDRB changed")
    return (halfword >> 3) & 7, (halfword >> 6) & 0x1F, halfword & 7


def independent_consumer_contract(data: bytes) -> dict[str, Any]:
    """Decode the consumer from raw bytes without relying on another module."""

    if len(data) != ROM_SIZE:
        raise ValueError("independent consumer requires the complete ROM")
    literal_specs = (
        (0x06E816, 2, 0x06E850, LITERAL_VALUES["wram_context"], "WRAM context"),
        (0x06E81A, 0, 0x06E854, LITERAL_VALUES["group_stride"], "group stride"),
        (0x06E822, 0, 0x06E858, LITERAL_VALUES["variant_stride"], "variant stride"),
        (0x06E826, 1, 0x06E85C, LITERAL_VALUES["positions_base"], "positions base"),
        (0x06E82E, 1, 0x06E860, LITERAL_VALUES["candidate_offset"], "candidate offset"),
        (0x06E848, 1, 0x06E864, 0x0806E868, "jump-table literal"),
    )
    locations = {}
    for instruction, register, literal, value, label in literal_specs:
        actual_register, actual_literal = _literal_load(data, instruction, label)
        if actual_register != register or actual_literal != literal:
            raise ValueError(f"independent {label} literal address changed")
        if _u32(data, literal) != value:
            raise ValueError(f"independent {label} literal value changed")
        locations[label] = literal

    for offset, halfword, label in (
        (0x06E818, 0x7851, "group byte load"),
        (0x06E820, 0x7891, "variant byte load"),
        (0x06E81C, 0x1C0B, "group move"),
        (0x06E81E, 0x4343, "group multiply"),
        (0x06E824, 0x4348, "variant multiply"),
        (0x06E828, 0x1840, "variant addition"),
        (0x06E82A, 0x181B, "group addition"),
        (0x06E82C, 0x00B0, "index base addition"),
        (0x06E830, 0x1840, "candidate addition"),
        (0x06E832, 0x181C, "cell address formation"),
        (0x06E814, 0x2600, "index initialization"),
        (0x06E836, 0x7820, "byte-zero load"),
        (0x06E83A, 0x7820, "dispatch byte-zero load"),
        (0x06E83C, 0x3801, "selector decrement"),
        (0x06E840, 0x2806, "selector bound"),
        (0x06E842, 0xD900, "unsigned selector branch"),
        (0x06E844, 0xE07F, "default selector branch"),
        (0x06E846, 0x0080, "index times four"),
        (0x06E84A, 0x1840, "dispatch table addition"),
        (0x06E84C, 0x6800, "dispatch table load"),
        (0x06E84E, 0x4687, "dispatch indirect jump"),
        (0x06E944, 0x1C75, "loop increment"),
        (0x06E946, 0x0628, "loop truncation left"),
        (0x06E948, 0x0E06, "loop truncation right"),
        (0x06E94A, 0x2E0F, "loop bound"),
        (0x06E94C, 0xD800, "loop stop branch"),
        (0x06E94E, 0xE762, "loop back branch"),
    ):
        _expect(data, offset, halfword, label)

    actual_reads = {1: [], 2: [], 3: []}
    actual_halfwords = {1: [], 2: [], 3: []}
    for offset in range(HANDLER_RANGE[0], HANDLER_RANGE[1], 2):
        halfword = _u16(data, offset)
        if halfword & 0xF800 != 0x7800:
            continue
        base, immediate, _register = _ldrb(data, offset, "handler")
        if base == 4 and immediate in actual_reads:
            actual_reads[immediate].append(offset)
            actual_halfwords[immediate].append(halfword)
    expected = {1: EXPECTED_BYTE1_READS, 2: EXPECTED_BYTE2_READS, 3: EXPECTED_BYTE3_READS}
    allowed = {1: {0x7860, 0x7862}, 2: {0x78A1}, 3: {0x78E2}}
    for byte in (1, 2, 3):
        if actual_reads[byte] != expected[byte] or any(value not in allowed[byte] for value in actual_halfwords[byte]):
            raise ValueError(f"independent handler byte {byte} read footprint changed")
    jumps = [_u32(data, 0x06E868 + index * 4) for index in range(7)]
    if jumps != EXPECTED_JUMP_TARGETS:
        raise ValueError("independent jump table changed")

    def evidence(bounds: tuple[int, int], expected_hash: str, label: str) -> dict[str, Any]:
        start, end = bounds
        if _digest(_bounded(data, start, end)) != expected_hash:
            raise ValueError(f"independent {label} evidence changed")
        return {"range": [start, end], "gba_range": [_gba(start), _gba(end)], "sha256": expected_hash}

    return {
        "function": evidence(FUNCTION_RANGE, FUNCTION_SHA256, "consumer function"),
        "prefix": evidence(PREFIX_RANGE, PREFIX_SHA256, "address-builder prefix"),
        "literal_words": evidence(LITERALS_RANGE, LITERALS_SHA256, "literal words"),
        "dispatch_proof": evidence(DISPATCH_RANGE, DISPATCH_SHA256, "dispatch proof"),
        "jump_table_literal": evidence(JUMP_LITERAL_RANGE, JUMP_LITERAL_SHA256, "jump-table literal"),
        "jump_table": evidence(JUMP_TABLE_RANGE, JUMP_TABLE_SHA256, "jump table"),
        "handler": evidence(HANDLER_RANGE, HANDLER_SHA256, "handler body"),
        "closure": evidence(CLOSURE_RANGE, CLOSURE_SHA256, "handler closure"),
        "loop": evidence(LOOP_RANGE, LOOP_SHA256, "loop update/check"),
        "literal_values": dict(LITERAL_VALUES),
        "literal_locations": locations,
        "address_equation": {
            "group_source": LITERAL_VALUES["wram_context"] + 1,
            "variant_source": LITERAL_VALUES["wram_context"] + 2,
            "base": LITERAL_VALUES["positions_base"],
            "group_stride": GROUP_STRIDE,
            "variant_stride": VARIANT_STRIDE,
            "cell_stride": CELL_STRIDE,
            "candidate_offset": CANDIDATE_OFFSET,
            "scan_count": CELL_COUNT,
            "formula": "r4 = base + group*group_stride + variant*variant_stride + index*cell_stride + candidate_offset",
        },
        "scan": {
            "index_initial_value": 0,
            "index_increment_instruction_offset": 0x06E944,
            "u8_truncation_instruction_offsets": [0x06E946, 0x06E948],
            "last_index": 15,
            "scan_count": CELL_COUNT,
            "cell_stride": CELL_STRIDE,
        },
        "dispatch": {
            "selector_load_instruction_offsets": [0x06E83A],
            "selector_byte_offset": 0,
            "subtract_one_instruction_offset": 0x06E83C,
            "accepted_selector_values": list(range(1, 8)),
            "compare_immediate": 6,
            "compare_instruction_offset": 0x06E840,
            "jump_table_literal_offset": 0x06E864,
            "jump_table_address": 0x0806E868,
            "jump_targets": list(EXPECTED_JUMP_TARGETS),
            "slot_count": 7,
            "distinct_target_count": len(set(EXPECTED_JUMP_TARGETS)),
        },
        "read_footprint": {
            "byte0": {"role": "dispatch selector", "instruction_offsets": [0x06E83A], "common_business_semantics_claimed": False},
            "byte1": {"role": "handler-dependent raw operand", "instruction_offsets": list(EXPECTED_BYTE1_READS), "instruction_halfwords": [0x7860, 0x7862], "common_business_semantics_claimed": False},
            "byte2": {"role": "handler-dependent raw operand", "instruction_offsets": list(EXPECTED_BYTE2_READS), "instruction_halfwords": [0x78A1], "common_business_semantics_claimed": False},
            "byte3": {"role": "handler-dependent raw operand", "instruction_offsets": list(EXPECTED_BYTE3_READS), "instruction_halfwords": [0x78E2], "common_business_semantics_claimed": False},
            "statement": "byte0 selects dispatch; bytes1/2/3 are consumed by selected handlers as raw operands with no single common business meaning",
        },
    }


def _load_bank(root: Path) -> tuple[dict[str, Any], bytes]:
    path = _root_file(root, POSITIONS_RELATIVE)
    raw = path.read_bytes()
    if _digest(raw) != POSITIONS_SHA256:
        raise ValueError("positions bank identity changed")
    bank = json.loads(raw.decode("utf-8"))
    fmt = bank.get("format", {})
    if bank.get("table_offset") != BASE or bank.get("entry_size") != 0xB8 or fmt.get("group_count") != GROUP_COUNT or fmt.get("variant_count") != VARIANT_COUNT or len(bank.get("entries", [])) != 1728:
        raise ValueError("positions bank structure changed")
    return bank, raw


def _rebuild_tables(rom: bytes, bank: dict[str, Any]) -> tuple[list[dict[str, Any]], list[list[int]], bytes, list[str]]:
    entries = bank["entries"]
    tables: list[dict[str, Any]] = []
    ranges: list[list[int]] = []
    packed = bytearray()
    hashes: list[str] = []
    for ordinal in range(TABLE_COUNT):
        group, variant = divmod(ordinal, VARIANT_COUNT)
        base = BASE + group * GROUP_STRIDE + variant * VARIANT_STRIDE
        start, end = base + CANDIDATE_OFFSET, base + CANDIDATE_END_OFFSET
        raw_table = _bounded(rom, start, end)
        owner_entries = entries[ordinal * 12 : ordinal * 12 + 12]
        left_range = [base + 4, base + CANDIDATE_OFFSET]
        if len(owner_entries) != 12 or owner_entries[0].get("rom_offset") != left_range[0] or owner_entries[-1].get("rom_offset") + 0xB8 != left_range[1]:
            raise ValueError(f"left owner boundary changed at ordinal {ordinal}")
        if ordinal < TABLE_COUNT - 1:
            next_group, next_variant = divmod(ordinal + 1, VARIANT_COUNT)
            next_base = BASE + next_group * GROUP_STRIDE + next_variant * VARIANT_STRIDE
            header = [end, end + 4]
            right_range = [next_base + 4, next_base + CANDIDATE_OFFSET]
            right_entries = entries[(ordinal + 1) * 12 : (ordinal + 1) * 12 + 12]
            if header[1] != right_range[0] or len(right_entries) != 12 or right_entries[0].get("rom_offset") != right_range[0] or right_entries[-1].get("rom_offset") + 0xB8 != right_range[1]:
                raise ValueError(f"right owner boundary changed at ordinal {ordinal}")
            right_owner = {"id": f"bank-positions-{ordinal + 1:03d}", "range": right_range}
            final_boundary = None
        else:
            header = None
            right_owner = None
            final_boundary = {
                "range": [end, 0x596D5C],
                "size": 0xB58,
                "next_owner": {"id": "character-battle-visual-descriptor_table-596d5c", "range": [0x596D5C, 0x59903C]},
            }
        cells = []
        for index in range(CELL_COUNT):
            cell_start = start + index * CELL_STRIDE
            cell = _bounded(rom, cell_start, cell_start + CELL_STRIDE)
            cells.append({
                "index": index,
                "range": [cell_start, cell_start + CELL_STRIDE],
                "gba_range": [_gba(cell_start), _gba(cell_start + CELL_STRIDE)],
                "raw_hex": cell.hex(),
                "byte0_dispatch_selector": cell[0],
                "byte1_raw_handler_operand": cell[1],
                "byte2_raw_handler_operand": cell[2],
                "byte3_raw_handler_operand": cell[3],
            })
        row = {
            "ordinal": ordinal,
            "group": group,
            "variant": variant,
            "base": base,
            "range": [start, end],
            "gba_range": [_gba(start), _gba(end)],
            "sha256": _digest(raw_table),
            "left_owner": {"id": f"bank-positions-{ordinal:03d}", "range": left_range},
            "next_header_range": header,
            "right_positions_owner": right_owner,
            "right_owner_adjacent": False,
            "final_post_candidate_boundary": final_boundary,
            "cells": cells,
        }
        tables.append(row)
        ranges.append([start, end])
        hashes.append(row["sha256"])
        packed.extend(raw_table)
    return tables, ranges, bytes(packed), hashes


def _distribution(tables: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, int]]:
    arrays = []
    for index in range(4):
        key = "byte0_dispatch_selector" if index == 0 else f"byte{index}_raw_handler_operand"
        arrays.append([cell[key] for table in tables for cell in table["cells"]])
    zero0 = arrays[0].count(0)
    counter0 = Counter(arrays[0])
    result = {
        "byte0": {
            "zero_count": zero0,
            "nonzero_count": TOTAL_CELLS - zero0,
            "dispatch_tag_counts": {str(value): counter0[value] for value in range(1, 8) if counter0[value]},
            "out_of_table_nonzero_counts": {str(value): counter0[value] for value in sorted(counter0) if value > 7},
        }
    }
    for index in (1, 2, 3):
        zero = arrays[index].count(0)
        result[f"byte{index}"] = {"zero_count": zero, "nonzero_count": TOTAL_CELLS - zero}
    counts = {
        "nonzero_bytes": sum(value != 0 for array in arrays for value in array),
        "nonzero_tables": sum(any(bytes.fromhex(cell["raw_hex"]) != b"\0\0\0\0" for cell in table["cells"]) for table in tables),
    }
    return result, counts


def _expected_non_claims() -> dict[str, bool]:
    return {field: False for field in NON_CLAIM_FIELDS}


def _implementation_hashes(root: Path) -> dict[str, dict[str, str]]:
    paths = {
        "exporter": Path("tools/export_rom_positions_aux_dispatch.py"),
        "verifier": Path("tools/verify_rom_positions_aux_dispatch.py"),
        "test": Path("tests/test_export_rom_positions_aux_dispatch.py"),
    }
    return {label: {"path": path.as_posix(), "sha256": _digest(_root_file(root, path).read_bytes())} for label, path in paths.items()}


def _validate_payload(root: Path, payload: dict[str, Any], rom: bytes, bank: dict[str, Any], decoded: dict[str, Any]) -> dict[str, Any]:
    tables, ranges, packed, hashes = _rebuild_tables(rom, bank)
    range_hash = _compact_hash(ranges)
    packed_hash = _digest(packed)
    vector_hash = _compact_hash(hashes)
    distributions, counts = _distribution(tables)
    expected_summary = {
        "table_count": TABLE_COUNT,
        "cell_count": TOTAL_CELLS,
        "byte_count": TOTAL_BYTES,
        "bytes_per_table": BYTES_PER_TABLE,
        "cells_per_table": CELL_COUNT,
        "cell_stride": CELL_STRIDE,
        "nonzero_byte_count": counts["nonzero_bytes"],
        "nonzero_table_count": counts["nonzero_tables"],
    }
    expected_upstream = {
        "path": POSITIONS_RELATIVE.as_posix(),
        "sha256": POSITIONS_SHA256,
        "table_offset": BASE,
        "entry_size": 0xB8,
        "entry_count": 1728,
        "group_count": GROUP_COUNT,
        "group_stride": GROUP_STRIDE,
        "variant_count": VARIANT_COUNT,
        "variant_stride": VARIANT_STRIDE,
        "records_per_variant": 12,
    }
    non_claims = _expected_non_claims()
    expected_scope = {
        "read_footprint": ["byte0_dispatch_selector", "byte1_raw_handler_operand", "byte2_raw_handler_operand", "byte3_raw_handler_operand"],
        "conclusion": "The fixed canonical positions denominator has 144 associated 16x4-byte structural cell tables; byte0 selects the frozen dispatch and bytes1/2/3 are consumed in handler-dependent ways without a single proven common business meaning.",
        **non_claims,
    }
    expected = {
        "schema": SCHEMA,
        "rom": {"path": "rom/base.gba", "size": ROM_SIZE, "sha256": ROM_SHA256},
        "upstream_positions": expected_upstream,
        "consumer": decoded,
        "range_denominator": ranges,
        "range_list_sha256": range_hash,
        "packed_range_bytes_sha256": packed_hash,
        "per_range_sha256_vector": hashes,
        "per_range_sha256_vector_sha256": vector_hash,
        "tables": tables,
        "byte_distributions": distributions,
        "byte_counts": counts,
        "summary": expected_summary,
        "scope": expected_scope,
        "non_claims": non_claims,
        "upstream_positions_file_sha256": POSITIONS_SHA256,
    }
    for key, expected_value in expected.items():
        if key == "implementation":
            continue
        if payload.get(key) != expected_value:
            raise ValueError(f"payload {key} does not match independent reconstruction")
    implementation = _implementation_hashes(root)
    if payload.get("implementation") != implementation:
        raise ValueError("payload implementation identity changed")
    return {"summary": expected_summary, "range_list_sha256": range_hash, "packed_range_bytes_sha256": packed_hash, "per_range_sha256_vector_sha256": vector_hash, "non_claims": non_claims, "scope": expected_scope, "consumer": decoded}


def _base_report(errors: list[str]) -> dict[str, Any]:
    non_claims = _expected_non_claims()
    return {
        "schema": VERIFY_SCHEMA,
        "artifact_schema": SCHEMA,
        "verified": not errors,
        "errors": list(errors),
        "summary": {
            "table_count": TABLE_COUNT,
            "cell_count": TOTAL_CELLS,
            "byte_count": TOTAL_BYTES,
            "bytes_per_table": BYTES_PER_TABLE,
            "cells_per_table": CELL_COUNT,
            "cell_stride": CELL_STRIDE,
        },
        "non_claims": non_claims,
        "scope": non_claims,
    }


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    report = _base_report(errors)
    try:
        root = _root_directory(Path(root))
        artifact = _artifact_path(Path(artifact_dir))
        if not artifact.is_dir():
            raise ValueError("artifact directory is not a directory")
        members = list(artifact.rglob("*"))
        if any(item.is_symlink() for item in members):
            raise ValueError("artifact directory uses a symlink")
        actual = {item.relative_to(artifact).as_posix() for item in members if item.is_file()}
        if actual != EXPECTED_FILES:
            raise ValueError("artifact exact file set changed")
        manifest_path = artifact / "manifest.json"
        payload_path = artifact / PAYLOAD_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != f"{SCHEMA}-artifact-manifest-v1" or manifest.get("artifact_schema") != SCHEMA:
            raise ValueError("manifest schema changed")
        payload_raw = payload_path.read_bytes()
        payload_hash = _digest(payload_raw)
        if manifest.get("files") != {PAYLOAD_NAME: payload_hash} or manifest.get("payload") != {"filename": PAYLOAD_NAME, "sha256": payload_hash} or manifest.get("file_set") != sorted(EXPECTED_FILES):
            raise ValueError("manifest payload identity changed")
        rom_path = _root_file(root, ROM_RELATIVE)
        rom = rom_path.read_bytes()
        if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256:
            raise ValueError("ROM identity changed")
        bank, _bank_raw = _load_bank(root)
        decoded = independent_consumer_contract(rom)
        result = _validate_payload(root, payload, rom, bank, decoded)
        if manifest.get("rom") != payload["rom"] or manifest.get("producer") != payload["implementation"] or manifest.get("summary") != payload["summary"] or manifest.get("denominator") != {
            "range_list_sha256": payload["range_list_sha256"],
            "packed_range_bytes_sha256": payload["packed_range_bytes_sha256"],
            "per_range_sha256_vector_sha256": payload["per_range_sha256_vector_sha256"],
        }:
            raise ValueError("manifest binding changed")
        if manifest.get("verification", {}).get("schema") != VERIFY_SCHEMA or manifest.get("verification", {}).get("verifier_sha256") != payload["implementation"]["verifier"]["sha256"]:
            raise ValueError("manifest verifier binding changed")
        report.update(result)
        report["verified"] = True
    except Exception as error:
        errors.append(str(error))
        report["verified"] = False
        report["errors"] = errors
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args(argv)
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] is True and report["errors"] == [] else 1


if __name__ == "__main__":
    raise SystemExit(main())
