#!/usr/bin/env python3
"""Export the frozen DirectSound pitch lookup closure from the base ROM.

The exporter intentionally keeps the claim narrow: it validates the fixed ROM,
decodes the two small code fragments and their literals, analyzes the two tables,
and writes a deterministic candidate bundle.  It does not infer callers,
runtime reachability, or editability.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any


SCHEMA = "rom-directsound-pitch-lookup-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f"
COVERAGE_TOTALS = {
    "classified_bytes": 6_121_280,
    "unknown_bytes": 170_176,
    "claim_count": 14_466,
    "segment_count": 16_577,
}

JSON_NAME = "rom-directsound-pitch-lookup.json"
BIN_NAME = "rom-directsound-pitch-lookup.bin"

HELPER_RANGE = (0x099D7C, 0x099D8C)
CONSUMER_RANGE = (0x09A998, 0x09A9F4)
LITERAL_RANGE = (0x09A9F4, 0x09A9FC)
SCALE_RANGE = (0x4645C4, 0x464678)
FREQUENCY_RANGE = (0x464678, 0x4646A8)

HELPER_SHA256 = "1addb8be644cbaa9421a91f6cd6d91407907e9c92320f56ae49804b98fc29a81"
CONSUMER_SHA256 = "d04cce3da22f96b569d80a5fea059633e43b5daec754ffa268bf95ecbbddff40"
LITERAL_SHA256 = "c46d5afc346f36454cfdedf489cfeafc148e4f952887b63f8738339ea6fe1deb"
SCALE_SHA256 = "52e19ba195ffad7aa82ac71bf26543d912f3e3a763e40c755ce0e71b674ef9e7"
FREQUENCY_SHA256 = "6b73747d3fb29635eeda13481d08a06e5371958ee746967aa892fa5390509404"

PROMOTION_RANGES = (
    HELPER_RANGE,
    CONSUMER_RANGE,
    LITERAL_RANGE,
    SCALE_RANGE,
    FREQUENCY_RANGE,
)
PROMOTION_VECTOR_SHA256 = "ac877e8eec80edbdab3d1b6f3991fc8a93dfc497a66c298dc9ee0c29034431bd"
PACKED_SHA256 = "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850"

PRODUCER_SPECS = (
    {
        "file_offset": 0x09A654,
        "raw_hex": "00f0a0f9",
        "bytes_sha256": "3bafe4212ed9d14d56bccd395ff9c325fbe5a4a6f14f0d34b081b0cb74a6ff74",
        "target_file_offset": 0x09A998,
    },
    {
        "file_offset": 0x09A8DC,
        "raw_hex": "00f05cf8",
        "bytes_sha256": "5fc2d693651559bb36bd2b8ea97a263e5b7546576569baeab382e37a6a924eb7",
        "target_file_offset": 0x09A998,
    },
)

EXPECTED_BLOCK_RANGES = (
    (0x09A998, 0x09A9A6),
    (0x09A9A6, 0x09A9AC),
    (0x09A9AC, 0x09A9E4),
    (0x09A9E4, 0x09A9EE),
    (0x09A9EE, 0x09A9F4),
)
EXPECTED_CALL_EDGES = (
    {"source_file_offset": 0x09A9E0, "target_file_offset": 0x099D7C},
    {"source_file_offset": 0x09A9EA, "target_file_offset": 0x099D7C},
)
EXPECTED_LITERAL_BINDINGS = (
    {
        "load_file_offset": 0x09A9AC,
        "load_raw_hex": "114b",
        "literal_range": [0x09A9F4, 0x09A9F8],
        "pointer": 0x084645C4,
        "target_range": list(SCALE_RANGE),
    },
    {
        "load_file_offset": 0x09A9B2,
        "load_raw_hex": "114c",
        "literal_range": [0x09A9F8, 0x09A9FC],
        "pointer": 0x08464678,
        "target_range": list(FREQUENCY_RANGE),
    },
)
EXPECTED_RETURN_PROOF = {
    "saved_lr_at_entry": True,
    "stack_adjustment_between_entry_and_epilogue": 0,
    "epilogue_range": [0x09A9EE, 0x09A9F4],
    "epilogue_raw_hex": "f0bc02bc0847",
    "restored_lr_register": "r1",
    "return_instruction": "bx r1",
}
EXPECTED_FREQUENCIES = (
    0x80000000,
    0x879C7C97,
    0x8FACD61E,
    0x9837F052,
    0xA14517CC,
    0xAADC0848,
    0xB504F334,
    0xBFC886BB,
    0xCB2FF52A,
    0xD744FCCB,
    0xE411F03A,
    0xF1A1BF39,
)

FORMULA = {
    "base_pitch": "freq[descriptor&15]>>(descriptor>>4)",
    "interpolation": "u32(p0+high32(u32(p1-p0),fine<<24))",
    "step": "high32(load_u32(input_r0+4),interpolated)",
}

SCOPE = {
    "target_limited_raw_bl_denominator_complete": True,
    "consumer_cfg_closed": True,
    "helper_interwork_closed": True,
    "table_index_domain_complete_for_all_u8_inputs": True,
    "producer_source_instruction_membership_complete": False,
    "producer_bytes_promoted": False,
    "natural_runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "editing_relocation_writeback_safe": False,
    "allocatable_free_space_proven": False,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _vector_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _validate_root(root: Path | str) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    return resolved


def _safe_file(root: Path, relative: Path) -> Path:
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


def _bounded(rom: bytes, start: int, end: int, label: str) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"{label} range escapes ROM")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2, "Thumb halfword"), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4, "little-endian word"), "little")


def _expect_u16(rom: bytes, offset: int, expected: int, label: str) -> int:
    actual = _u16(rom, offset)
    if actual != expected:
        raise ValueError(f"{label} changed: expected 0x{expected:04X}, got 0x{actual:04X}")
    return actual


def _slice_with_hash(rom: bytes, start: int, end: int, expected: str, label: str) -> bytes:
    raw = _bounded(rom, start, end, label)
    actual = _sha(raw)
    if actual != expected:
        raise ValueError(f"{label} bytes changed")
    return raw


def _is_thumb_bl(first: int, second: int) -> bool:
    return first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def _thumb_bl_target(rom: bytes, offset: int) -> int:
    first = _u16(rom, offset)
    second = _u16(rom, offset + 2)
    if not _is_thumb_bl(first, second):
        raise ValueError(f"not a Thumb BL at 0x{offset:06X}")
    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    imm11 = second & 0x07FF
    i1 = j1 ^ 1 ^ sign
    i2 = j2 ^ 1 ^ sign
    displacement = (sign << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if sign:
        displacement -= 1 << 25
    return offset + 4 + displacement


def _scan_producers(rom: bytes) -> dict[str, Any]:
    target = CONSUMER_RANGE[0]
    matches: list[int] = []
    for offset in range(0, len(rom) - 3, 2):
        first = _u16(rom, offset)
        second = _u16(rom, offset + 2)
        if _is_thumb_bl(first, second) and _thumb_bl_target(rom, offset) == target:
            matches.append(offset)
    producers = []
    for offset in matches:
        raw = _bounded(rom, offset, offset + 4, "producer")
        producers.append(
            {
                "file_offset": offset,
                "raw_hex": raw.hex(),
                "bytes_sha256": _sha(raw),
                "target_file_offset": target,
            }
        )
    expected_producers = [dict(spec) for spec in PRODUCER_SPECS]
    if producers != expected_producers:
        raise ValueError("target-limited raw Thumb BL denominator changed")

    thumb_pointer = (ROM_BASE + target + 1).to_bytes(4, "little")
    occurrences = [
        offset
        for offset in range(0, len(rom) - len(thumb_pointer) + 1)
        if rom[offset : offset + len(thumb_pointer)] == thumb_pointer
    ]
    if occurrences:
        raise ValueError("exact Thumb pointer occurrence for consumer target")
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "target_file_offset": target,
            "matching_producer_count": len(producers),
        },
        "producers": producers,
        "thumb_pointer_occurrences": occurrences,
        "producer_source_instruction_membership_proven": False,
        "producer_bytes_promoted": False,
    }


def _decode_thumb_consumer(rom: bytes) -> tuple[list[dict[str, Any]], list[list[int]], list[dict[str, int]], dict[str, Any]]:
    start, end = CONSUMER_RANGE
    instructions: list[dict[str, Any]] = []
    offset = start
    while offset < end:
        first = _u16(rom, offset)
        if first & 0xF800 == 0xF000:
            if offset + 4 > end:
                raise ValueError("consumer wide Thumb instruction escapes code range")
            second = _u16(rom, offset + 2)
            if not _is_thumb_bl(first, second):
                raise ValueError(f"unsupported wide Thumb instruction at 0x{offset:06X}")
            target = _thumb_bl_target(rom, offset)
            instructions.append(
                {
                    "file_offset": offset,
                    "size": 4,
                    "kind": "bl",
                    "target_file_offset": target,
                    "raw_hex": rom[offset : offset + 4].hex(),
                }
            )
            offset += 4
            continue
        if first & 0xF000 == 0xD000 and (first & 0x0F00) != 0x0F00:
            displacement = first & 0xFF
            if displacement & 0x80:
                displacement -= 0x100
            target = offset + 4 + displacement * 2
            instructions.append(
                {
                    "file_offset": offset,
                    "size": 2,
                    "kind": "conditional_branch",
                    "target_file_offset": target,
                    "raw_hex": rom[offset : offset + 2].hex(),
                }
            )
        elif first & 0xF800 == 0xE000:
            displacement = first & 0x7FF
            if displacement & 0x400:
                displacement -= 0x800
            target = offset + 4 + displacement * 2
            instructions.append(
                {
                    "file_offset": offset,
                    "size": 2,
                    "kind": "branch",
                    "target_file_offset": target,
                    "raw_hex": rom[offset : offset + 2].hex(),
                }
            )
        elif first & 0xFF87 == 0x4700:
            register = (first >> 3) & 0xF
            instructions.append(
                {
                    "file_offset": offset,
                    "size": 2,
                    "kind": "bx",
                    "register": register,
                    "raw_hex": rom[offset : offset + 2].hex(),
                }
            )
        else:
            instructions.append(
                {
                    "file_offset": offset,
                    "size": 2,
                    "kind": "linear",
                    "raw_hex": rom[offset : offset + 2].hex(),
                }
            )
        offset += 2

    if offset != end or len(instructions) != 44:
        raise ValueError("consumer instruction denominator changed")
    by_offset = {item["file_offset"]: item for item in instructions}
    starts = {start}
    calls: list[dict[str, int]] = []
    for instruction in instructions:
        address = instruction["file_offset"]
        next_offset = address + instruction["size"]
        if instruction["kind"] == "conditional_branch":
            starts.update((instruction["target_file_offset"], next_offset))
        elif instruction["kind"] == "branch":
            starts.add(instruction["target_file_offset"])
            if instruction["target_file_offset"] != next_offset:
                starts.add(next_offset)
        elif instruction["kind"] == "bl":
            if instruction["target_file_offset"] != HELPER_RANGE[0]:
                raise ValueError("consumer external call target changed")
            starts.add(next_offset)
            calls.append(
                {
                    "source_file_offset": address,
                    "target_file_offset": instruction["target_file_offset"],
                }
            )
    starts = {value for value in starts if start <= value < end}
    blocks: list[list[int]] = []
    assigned: set[int] = set()
    for block_start in sorted(starts):
        if block_start in assigned:
            continue
        cursor = block_start
        while cursor in by_offset and cursor not in assigned:
            instruction = by_offset[cursor]
            assigned.add(cursor)
            next_offset = cursor + instruction["size"]
            if instruction["kind"] in {"conditional_branch", "branch", "bl", "bx"}:
                cursor = next_offset
                break
            if next_offset in starts:
                cursor = next_offset
                break
            cursor = next_offset
        if cursor <= block_start:
            raise ValueError("consumer block construction made no progress")
        blocks.append([block_start, cursor])
    if assigned != set(by_offset) or tuple(map(tuple, blocks)) != EXPECTED_BLOCK_RANGES:
        raise ValueError("consumer basic-block denominator changed")
    if tuple(calls) != EXPECTED_CALL_EDGES:
        raise ValueError("consumer external-call denominator changed")

    entry = _expect_u16(rom, start, 0xB5F0, "consumer entry push")
    if not entry & 0x0100:
        raise ValueError("consumer entry push does not save LR")
    epilogue_start = EXPECTED_RETURN_PROOF["epilogue_range"][0]
    epilogue_raw = _bounded(rom, epilogue_start, end, "consumer epilogue")
    if epilogue_raw.hex() != EXPECTED_RETURN_PROOF["epilogue_raw_hex"]:
        raise ValueError("consumer structured return changed")
    if _u16(rom, epilogue_start) != 0xBCF0 or _u16(rom, epilogue_start + 2) != 0xBC02:
        raise ValueError("consumer epilogue POP sequence changed")
    if _u16(rom, epilogue_start + 4) != 0x4708:
        raise ValueError("consumer epilogue BX r1 changed")
    if (0xBC02 >> 0) & 0xFF != 0x02:
        raise ValueError("consumer LR restore register changed")
    stack_adjustments = [
        item
        for item in instructions
        if item["file_offset"] < epilogue_start
        and _u16(rom, item["file_offset"]) & 0xFF00 == 0xB000
    ]
    if stack_adjustments:
        raise ValueError("consumer has an SP adjustment before structured return")
    return_proof = {
        "saved_lr_at_entry": True,
        "stack_adjustment_between_entry_and_epilogue": 0,
        "epilogue_range": [epilogue_start, end],
        "epilogue_raw_hex": epilogue_raw.hex(),
        "restored_lr_register": "r1",
        "return_instruction": "bx r1",
    }
    if return_proof != EXPECTED_RETURN_PROOF:
        raise ValueError("consumer return proof denominator changed")
    return instructions, blocks, calls, return_proof


def _literal_bindings(rom: bytes) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for offset, expected_register, expected_literal_offset in (
        (0x09A9AC, 3, 0x09A9F4),
        (0x09A9B2, 4, 0x09A9F8),
    ):
        instruction = _u16(rom, offset)
        if instruction & 0xF800 != 0x4800:
            raise ValueError(f"literal load at 0x{offset:06X} is not Thumb PC-relative LDR")
        register = (instruction >> 8) & 7
        if register != expected_register:
            raise ValueError("consumer literal destination register changed")
        literal_address = ((ROM_BASE + offset + 4) & ~3) + (instruction & 0xFF) * 4
        literal_offset = literal_address - ROM_BASE
        if literal_offset != expected_literal_offset:
            raise ValueError("consumer PC-relative literal target changed")
        if not LITERAL_RANGE[0] <= literal_offset or literal_offset + 4 > LITERAL_RANGE[1]:
            raise ValueError("consumer literal escapes literal range")
        pointer = _u32(rom, literal_offset)
        targets = {
            ROM_BASE + SCALE_RANGE[0]: SCALE_RANGE,
            ROM_BASE + FREQUENCY_RANGE[0]: FREQUENCY_RANGE,
        }
        if pointer not in targets:
            raise ValueError("consumer literal pointer target changed")
        bindings.append(
            {
                "load_file_offset": offset,
                "load_raw_hex": rom[offset : offset + 2].hex(),
                "literal_range": [literal_offset, literal_offset + 4],
                "pointer": pointer,
                "target_range": list(targets[pointer]),
            }
        )
    if tuple(bindings) != EXPECTED_LITERAL_BINDINGS:
        raise ValueError("consumer literal binding denominator changed")
    if any(item["literal_range"][0] < CONSUMER_RANGE[1] for item in bindings):
        raise ValueError("literal bytes were decoded as consumer instructions")
    return bindings


def _decode_helper(rom: bytes) -> dict[str, Any]:
    start, thumb_end = 0x099D7C, 0x099D80
    end = HELPER_RANGE[1]
    _expect_u16(rom, start, 0xA200, "helper Thumb ADR")
    _expect_u16(rom, start + 2, 0x4710, "helper Thumb BX r2")
    adr_target = ((ROM_BASE + start + 4) & ~3) + ((0xA200 & 0xFF) * 4)
    if adr_target != ROM_BASE + thumb_end:
        raise ValueError("helper Thumb ADR/BX state switch changed")
    words = [_u32(rom, offset) for offset in (thumb_end, thumb_end + 4, thumb_end + 8)]
    if words != [0xE0832190, 0xE2830000, 0xE12FFF1E]:
        raise ValueError("helper ARM UMULL/MOV/BX-LR body changed")
    if _sha(_bounded(rom, *HELPER_RANGE, "helper")) != HELPER_SHA256:
        raise ValueError("helper bytes changed")
    return {
        "range": list(HELPER_RANGE),
        "sha256": HELPER_SHA256,
        "thumb_range": [start, thumb_end],
        "arm_range": [thumb_end, end],
        "decoded_instruction_count": 5,
        "decoded_basic_block_count": 2,
        "frontier_count": 0,
        "state_switch": "thumb_adr_bx_to_arm",
        "operation": "unsigned_multiply_high32",
    }


def analyze_scale_descriptors(raw: bytes) -> dict[str, Any]:
    """Validate and summarize the 180 descriptor bytes.

    The low nibble selects one of the twelve frequency entries; rejecting an
    out-of-domain value here keeps table analysis fail-closed even when called
    independently of :func:`build_payload`.
    """

    if len(raw) != SCALE_RANGE[1] - SCALE_RANGE[0]:
        raise ValueError("scale descriptor table must contain 180 bytes")
    frequency_indices: list[int] = []
    shifts: list[int] = []
    for index, descriptor in enumerate(raw):
        frequency_index = descriptor & 0x0F
        shift = descriptor >> 4
        if frequency_index >= len(EXPECTED_FREQUENCIES):
            raise ValueError(
                f"frequency index {frequency_index} at descriptor {index} is outside [0, 11]"
            )
        if shift > 14:
            raise ValueError(f"scale shift {shift} at descriptor {index} is outside [0, 14]")
        frequency_indices.append(frequency_index)
        shifts.append(shift)
    frequency_domain = sorted(set(frequency_indices))
    shift_domain = sorted(set(shifts))
    if frequency_domain != list(range(12)):
        raise ValueError("scale frequency index domain is incomplete")
    if shift_domain != list(range(15)):
        raise ValueError("scale shift domain is incomplete")
    return {
        "descriptor_count": len(raw),
        "key_index_domain": [0, len(raw) - 1],
        "frequency_index_domain": [frequency_domain[0], frequency_domain[-1]],
        "shift_domain": [shift_domain[0], shift_domain[-1]],
        "frequency_index_counts": {
            str(index): count for index, count in sorted(Counter(frequency_indices).items())
        },
        "shift_counts": {str(index): count for index, count in sorted(Counter(shifts).items())},
    }


def _analyze_frequency_table(raw: bytes) -> dict[str, Any]:
    if len(raw) != FREQUENCY_RANGE[1] - FREQUENCY_RANGE[0]:
        raise ValueError("frequency table must contain 12 u32 entries")
    values = [int.from_bytes(raw[index : index + 4], "little") for index in range(0, len(raw), 4)]
    if tuple(values) != EXPECTED_FREQUENCIES:
        raise ValueError("frequency table values changed")
    return {"entry_count": len(values), "entry_size": 4, "values_u32": values}


def _semantic_ranges(rom: bytes) -> list[dict[str, Any]]:
    specs = (
        ("directsound_pitch_high32_interwork_code", HELPER_RANGE, HELPER_SHA256),
        ("directsound_pitch_consumer_code", CONSUMER_RANGE, CONSUMER_SHA256),
        ("directsound_pitch_table_literals", LITERAL_RANGE, LITERAL_SHA256),
        ("directsound_pitch_scale_table", SCALE_RANGE, SCALE_SHA256),
        ("directsound_pitch_frequency_table", FREQUENCY_RANGE, FREQUENCY_SHA256),
    )
    rows: list[dict[str, Any]] = []
    previous_end = -1
    for kind, (start, end), expected in specs:
        if start < previous_end or start >= end:
            raise ValueError("promotion ranges are not disjoint and ascending")
        raw = _slice_with_hash(rom, start, end, expected, kind)
        rows.append({"kind": kind, "range": [start, end], "sha256": _sha(raw)})
        previous_end = end
    return rows


def analyze_coverage_baseline(coverage: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless every byte promoted by this packet is still unknown."""

    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("coverage baseline summary is absent")
    if {key: summary.get(key) for key in COVERAGE_TOTALS} != COVERAGE_TOTALS:
        raise ValueError("coverage baseline totals changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list):
        raise ValueError("coverage baseline segments are absent")

    unknown_bytes = 0
    overlap_bytes = 0
    for promotion_start, promotion_end in PROMOTION_RANGES:
        cursor = promotion_start
        for segment in segments:
            raw_range = segment.get("range")
            if (
                not isinstance(raw_range, list)
                or len(raw_range) != 2
                or not all(isinstance(value, int) for value in raw_range)
            ):
                raise ValueError("coverage baseline contains an invalid segment range")
            segment_start, segment_end = raw_range
            if segment_end <= promotion_start:
                continue
            if segment_start >= promotion_end:
                break
            left = max(promotion_start, segment_start)
            right = min(promotion_end, segment_end)
            if left != cursor or right <= left:
                raise ValueError("coverage baseline has a gap inside a promotion range")
            size = right - left
            if (
                segment.get("primary_class") == "unknown"
                and segment.get("primary_claim_ids") in (None, [])
            ):
                unknown_bytes += size
            else:
                overlap_bytes += size
            cursor = right
        if cursor != promotion_end:
            raise ValueError("coverage baseline does not cover a promotion range")

    promotion_bytes = sum(end - start for start, end in PROMOTION_RANGES)
    if overlap_bytes or unknown_bytes != promotion_bytes:
        raise ValueError(
            f"coverage primary overlap: {overlap_bytes} bytes; "
            f"unknown promotion bytes: {unknown_bytes}/{promotion_bytes}"
        )
    return {
        "path": COVERAGE_PATH.as_posix(),
        "schema": "rom-byte-coverage-v1",
        "sha256": COVERAGE_SHA256,
        **COVERAGE_TOTALS,
        "promotion_bytes": promotion_bytes,
        "unknown_promotion_bytes": unknown_bytes,
        "primary_overlap_bytes": overlap_bytes,
        "all_promotion_bytes_unknown": True,
    }


def _coverage_baseline(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    try:
        coverage = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("coverage baseline is not valid JSON") from error
    if not isinstance(coverage, dict):
        raise ValueError("coverage baseline must be a JSON object")
    return analyze_coverage_baseline(coverage)


def _build_payload_from_rom(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    semantic_ranges = _semantic_ranges(rom)
    promotion_ranges = [item["range"] for item in semantic_ranges]
    if promotion_ranges != [list(pair) for pair in PROMOTION_RANGES]:
        raise ValueError("promotion range denominator changed")
    bundle = b"".join(_bounded(rom, start, end, "promotion") for start, end in PROMOTION_RANGES)
    if len(bundle) != 344 or _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion packed bytes changed")
    if _vector_sha(promotion_ranges) != PROMOTION_VECTOR_SHA256:
        raise ValueError("promotion range vector changed")

    producer_denominator = _scan_producers(rom)
    _slice_with_hash(rom, *CONSUMER_RANGE, CONSUMER_SHA256, "consumer")
    _slice_with_hash(rom, *LITERAL_RANGE, LITERAL_SHA256, "literal")
    _slice_with_hash(rom, *SCALE_RANGE, SCALE_SHA256, "scale")
    _slice_with_hash(rom, *FREQUENCY_RANGE, FREQUENCY_SHA256, "frequency")
    instructions, blocks, calls, return_proof = _decode_thumb_consumer(rom)
    literal_bindings = _literal_bindings(rom)
    helper = _decode_helper(rom)

    scale = analyze_scale_descriptors(_bounded(rom, *SCALE_RANGE, "scale"))
    scale.update({"range": list(SCALE_RANGE), "sha256": SCALE_SHA256})
    frequency = _analyze_frequency_table(_bounded(rom, *FREQUENCY_RANGE, "frequency"))
    frequency.update({"range": list(FREQUENCY_RANGE), "sha256": FREQUENCY_SHA256})

    consumer = {
        "root_file_offset": CONSUMER_RANGE[0],
        "code_range": list(CONSUMER_RANGE),
        "code_sha256": CONSUMER_SHA256,
        "decoded_instruction_count": len(instructions),
        "decoded_basic_block_count": len(blocks),
        "block_ranges": blocks,
        "external_call_edges": calls,
        "frontier_count": 0,
        "return_proof": return_proof,
    }
    input_domain = {
        "raw_key_u8": [0, 255],
        "effective_key": [0, scale["descriptor_count"] - 2],
        "clamped_raw_keys": [scale["descriptor_count"] - 1, 255],
        "fine_u8": [0, 255],
        "clamped_fine": 255,
        "scale_access_union": [0, scale["descriptor_count"] - 1],
        "frequency_access_union": list(scale["frequency_index_domain"]),
    }
    if input_domain != {
        "raw_key_u8": [0, 255],
        "effective_key": [0, 178],
        "clamped_raw_keys": [179, 255],
        "fine_u8": [0, 255],
        "clamped_fine": 255,
        "scale_access_union": [0, 179],
        "frequency_access_union": [0, 11],
    }:
        raise ValueError("u8 table access domain changed")
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "coverage_baseline": _coverage_baseline(root),
        "promotion": {
            "ranges": promotion_ranges,
            "range_count": len(promotion_ranges),
            "byte_count": sum(end - start for start, end in PROMOTION_RANGES),
            "range_vector_sha256": _vector_sha(promotion_ranges),
            "packed_bytes_sha256": _sha(bundle),
            "semantic_ranges": semantic_ranges,
        },
        "producer_denominator": producer_denominator,
        "consumer": consumer,
        "literal_bindings": literal_bindings,
        "high32_helper": helper,
        "formula": dict(FORMULA),
        "tables": {"scale": scale, "frequency": frequency},
        "input_domain": input_domain,
        "scope": dict(SCOPE),
    }
    return payload, bundle


def build_payload(root: Path | str) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    rom = _safe_file(repository, ROM_PATH).read_bytes()
    return _build_payload_from_rom(repository, rom)


def rebuild_from_rom(root: Path | str, rom: bytes) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    return _build_payload_from_rom(repository, rom)


def _reject_symlink_components(path: Path, root: Path) -> Path:
    requested = Path(os.path.abspath(path.expanduser()))
    temp_root = Path(tempfile.gettempdir())
    scan_base = Path(requested.anchor)
    for candidate in (root, temp_root):
        candidate = Path(os.path.abspath(candidate))
        if requested == candidate or candidate in requested.parents:
            scan_base = candidate
            break
    cursor = scan_base
    for part in requested.relative_to(scan_base).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"artifact output uses a symlink component: {cursor}")
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested, root)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("artifact output must not be the repository root or its ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("artifact output is not a directory")
        members = list(target.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact output directory contains a symlink")
        if any(member.is_dir() for member in members):
            raise ValueError("foreign artifact output directory")
        files = {member.relative_to(target).as_posix() for member in members if member.is_file()}
        if files not in (set(), {JSON_NAME, BIN_NAME, "manifest.json"}):
            raise ValueError("foreign artifact output directory")
        if files:
            try:
                payload = json.loads((target / JSON_NAME).read_text(encoding="utf-8"))
                manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("foreign artifact schema") from error
            if (
                not isinstance(payload, dict)
                or payload.get("schema") != SCHEMA
                or not isinstance(manifest, dict)
                or manifest.get("schema") != "git-artifact-promotion-v1"
                or manifest.get("artifact_schema") != SCHEMA
                or manifest.get("artifact_status") not in {"candidate", "accepted"}
            ):
                raise ValueError("foreign artifact schema")
    return target


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "candidate",
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "promotion": payload["promotion"],
        "scope": payload["scope"],
        "files": {
            name: {"size": len(content), "sha256": _sha(content)}
            for name, content in sorted(files.items())
        },
    }


def _replace_output(target: Path, files: dict[str, bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup: Path | None = None
    backup_container: Path | None = None
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        if target.exists():
            legacy_backup = target.with_name(f".{target.name}.old-{os.getpid()}")
            if legacy_backup.exists():
                raise ValueError(f"artifact backup collision: {legacy_backup}")
            backup_container = Path(
                tempfile.mkdtemp(prefix=f".{target.name}.old-", dir=target.parent)
            )
            backup = backup_container / "previous"
            os.replace(target, backup)
        os.replace(temporary, target)
        if backup_container is not None and backup_container.exists():
            shutil.rmtree(backup_container)
    except BaseException:
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup_container is not None and backup_container.exists() and target.exists():
            shutil.rmtree(backup_container)


def write_artifact(root: Path | str, output: Path | str) -> dict[str, Any]:
    repository = _validate_root(root)
    target = _validate_output(repository, Path(output))
    payload, bundle = build_payload(repository)
    payload_raw = _canonical(payload)
    files = {JSON_NAME: payload_raw, BIN_NAME: bundle}
    files["manifest.json"] = _canonical(_manifest(payload, files))
    _replace_output(target, files)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    payload = write_artifact(args.root, args.output_dir)
    print(json.dumps(payload["promotion"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
