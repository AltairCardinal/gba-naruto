#!/usr/bin/env python3
"""Independently verify the frozen DirectSound pitch lookup packet."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


SCHEMA = "rom-directsound-pitch-lookup-v1"
VERIFY_SCHEMA = "rom-directsound-pitch-lookup-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f"
COVERAGE_TOTALS = {
    "classified_bytes": 6_121_280,
    "unknown_bytes": 170_176,
    "claim_count": 14_466,
    "segment_count": 16_577,
}
COVERAGE_BASELINE_CLAIMS_SHA256 = (
    "96c58f3627cf537f07853934a51961be66ff4dd7bdf533d5674f05e628563be7"
)
COVERAGE_BASELINE_SEGMENTS_SHA256 = (
    "84eb46911614c696216a1a4c865bfa9b2a2d1dc60a726990eec8c7a12b674276"
)
COVERAGE_BASELINE_SUMMARY_SHA256 = (
    "b9e738098cb1fd761f6373aae5daaa0791818984ddc5dc36ce9272d38e11c31d"
)
COVERAGE_BASELINE_LIMITATIONS_SHA256 = (
    "32d0f8fd66af07b2fde45434cf42b792bd5dbe348ce38c7e29026c1eb8e566ab"
)
COVERAGE_INVARIANT_TOP_SHA256 = (
    "af4304b2ac0ce0558eceb97218a4ba6881878de9c6d2fa0e24098178654fb6ca"
)
COVERAGE_POST_SEGMENTS_SHA256 = (
    "4727ba4f1f390bd174d25a31522f6474a7e318d8924a09c62a9a92535bf5e6e0"
)
COVERAGE_POST_SUMMARY_SHA256 = (
    "088c1c2bfb1afa002bddd3415efc9f6f2daee41f01a6d70a9ad777fcb0be36b4"
)
COVERAGE_POST_LIMITATIONS_SHA256 = (
    "0ac0b8e3da190b1374fbc2b8673418c11c7dff63220b172142a0a1b874bbd9e3"
)
COVERAGE_DYNAMIC_KEYS = frozenset({"claims", "segments", "summary", "limitations"})
COVERAGE_LIMITATION = (
    "The DirectSound pitch lookup artifact classifies exactly 344 frozen bytes: "
    "a 16-byte mixed Thumb/ARM high32 helper, a 92-byte bounded Thumb consumer, "
    "eight consumed pointer-literal bytes, 180 u8 scale descriptors, and twelve "
    "little-endian u32 frequencies. Its proof is limited to the target-bounded "
    "two-producer raw Thumb BL denominator, closed consumer CFG and structured "
    "return, helper interwork, literal bindings, and exhaustive u8 table-index "
    "domains; producer bytes and source-instruction membership, natural runtime "
    "reachability, global code/caller/indirect or computed/RAM consumer "
    "denominators, playback behavior, editing, writeback, relocation, and "
    "allocatable space remain unclaimed."
)

JSON_NAME = "rom-directsound-pitch-lookup.json"
BIN_NAME = "rom-directsound-pitch-lookup.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = Path("artifacts/rom-directsound-pitch-lookup-v1")
EXPORTER_PATH = Path("tools/export_rom_directsound_pitch_lookup.py")
EXPORTER_TEST_PATH = Path("tests/test_export_rom_directsound_pitch_lookup.py")
VERIFIER_PATH = Path("tools/verify_rom_directsound_pitch_lookup.py")
VERIFIER_TEST_PATH = Path("tests/test_verify_rom_directsound_pitch_lookup.py")

HELPER_RANGE = (0x099D7C, 0x099D8C)
CONSUMER_RANGE = (0x09A998, 0x09A9F4)
LITERAL_RANGE = (0x09A9F4, 0x09A9FC)
SCALE_RANGE = (0x4645C4, 0x464678)
FREQUENCY_RANGE = (0x464678, 0x4646A8)
PROMOTION_RANGES = (
    HELPER_RANGE,
    CONSUMER_RANGE,
    LITERAL_RANGE,
    SCALE_RANGE,
    FREQUENCY_RANGE,
)

HELPER_SHA256 = "1addb8be644cbaa9421a91f6cd6d91407907e9c92320f56ae49804b98fc29a81"
CONSUMER_SHA256 = "d04cce3da22f96b569d80a5fea059633e43b5daec754ffa268bf95ecbbddff40"
LITERAL_SHA256 = "c46d5afc346f36454cfdedf489cfeafc148e4f952887b63f8738339ea6fe1deb"
SCALE_SHA256 = "52e19ba195ffad7aa82ac71bf26543d912f3e3a763e40c755ce0e71b674ef9e7"
FREQUENCY_SHA256 = "6b73747d3fb29635eeda13481d08a06e5371958ee746967aa892fa5390509404"
PROMOTION_VECTOR_SHA256 = "ac877e8eec80edbdab3d1b6f3991fc8a93dfc497a66c298dc9ee0c29034431bd"
PACKED_SHA256 = "cdf62999570f66a283667ed85f535da4e04f8cbf5ea8a33ef66d1bee8ab0e850"

PRODUCERS = (
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

BLOCK_RANGES = (
    (0x09A998, 0x09A9A6),
    (0x09A9A6, 0x09A9AC),
    (0x09A9AC, 0x09A9E4),
    (0x09A9E4, 0x09A9EE),
    (0x09A9EE, 0x09A9F4),
)
CALL_EDGES = (
    {"source_file_offset": 0x09A9E0, "target_file_offset": 0x099D7C},
    {"source_file_offset": 0x09A9EA, "target_file_offset": 0x099D7C},
)
RETURN_PROOF = {
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
LIMITATIONS = [
    "This packet classifies exactly the 344 frozen bytes in its five semantic ranges: one mixed Thumb/ARM high32 helper, one bounded Thumb consumer, two consumed pointer literals, 180 scale descriptors, and twelve little-endian u32 frequencies.",
    "The two target-limited raw BL producers are provenance only because their enclosing source-instruction membership is not independently proven; their eight bytes remain outside this promotion.",
    "Natural runtime reachability, global caller/code/indirect-target completeness, business meaning beyond the exact pitch formula, editing, relocation, writeback safety, and allocatable free space remain unclaimed.",
]

COVERAGE_CLAIM_SPECS = (
    {
        "id": "directsound-pitch-high32-interwork-099d7c",
        "artifact_kind": "directsound_pitch_high32_interwork_code",
        "range": [0x099D7C, 0x099D8C],
        "primary_class": "armv4t_directsound_pitch_high32_interwork_code",
        "claim_kind": "directsound_pitch_high32_interwork_instruction_bytes",
        "mode": None,
    },
    {
        "id": "directsound-pitch-consumer-09a998",
        "artifact_kind": "directsound_pitch_consumer_code",
        "range": [0x09A998, 0x09A9F4],
        "primary_class": "armv4t_directsound_pitch_consumer_thumb_code",
        "claim_kind": "directsound_pitch_consumer_instruction_bytes",
        "mode": "thumb",
    },
    {
        "id": "directsound-pitch-literals-09a9f4",
        "artifact_kind": "directsound_pitch_table_literals",
        "range": [0x09A9F4, 0x09A9FC],
        "primary_class": "directsound_pitch_table_pointer_literals",
        "claim_kind": "directsound_pitch_consumed_literal_bytes",
        "mode": None,
    },
    {
        "id": "directsound-pitch-scale-table-4645c4",
        "artifact_kind": "directsound_pitch_scale_table",
        "range": [0x4645C4, 0x464678],
        "primary_class": "directsound_pitch_scale_descriptor_table",
        "claim_kind": "directsound_pitch_scale_descriptor_bytes",
        "mode": None,
    },
    {
        "id": "directsound-pitch-frequency-table-464678",
        "artifact_kind": "directsound_pitch_frequency_table",
        "range": [0x464678, 0x4646A8],
        "primary_class": "directsound_pitch_frequency_u32_table",
        "claim_kind": "directsound_pitch_frequency_u32_bytes",
        "mode": None,
    },
)

CONSUMER_DISASSEMBLY = (
    (0x09A998, "f0b5", "push", "{r4, r5, r6, r7, lr}"),
    (0x09A99A, "8446", "mov", "ip, r0"),
    (0x09A99C, "0906", "lsls", "r1, r1, #0x18"),
    (0x09A99E, "0e0e", "lsrs", "r6, r1, #0x18"),
    (0x09A9A0, "1706", "lsls", "r7, r2, #0x18"),
    (0x09A9A2, "b22e", "cmp", "r6, #0xb2"),
    (0x09A9A4, "02d9", "bls", "#0x809a9ac"),
    (0x09A9A6, "b226", "movs", "r6, #0xb2"),
    (0x09A9A8, "ff27", "movs", "r7, #0xff"),
    (0x09A9AA, "3f06", "lsls", "r7, r7, #0x18"),
    (0x09A9AC, "114b", "ldr", "r3, [pc, #0x44]"),
    (0x09A9AE, "f018", "adds", "r0, r6, r3"),
    (0x09A9B0, "0578", "ldrb", "r5, [r0]"),
    (0x09A9B2, "114c", "ldr", "r4, [pc, #0x44]"),
    (0x09A9B4, "0f22", "movs", "r2, #0xf"),
    (0x09A9B6, "281c", "adds", "r0, r5, #0"),
    (0x09A9B8, "1040", "ands", "r0, r2"),
    (0x09A9BA, "8000", "lsls", "r0, r0, #2"),
    (0x09A9BC, "0019", "adds", "r0, r0, r4"),
    (0x09A9BE, "2909", "lsrs", "r1, r5, #4"),
    (0x09A9C0, "0568", "ldr", "r5, [r0]"),
    (0x09A9C2, "cd40", "lsrs", "r5, r1"),
    (0x09A9C4, "701c", "adds", "r0, r6, #1"),
    (0x09A9C6, "c018", "adds", "r0, r0, r3"),
    (0x09A9C8, "0178", "ldrb", "r1, [r0]"),
    (0x09A9CA, "081c", "adds", "r0, r1, #0"),
    (0x09A9CC, "1040", "ands", "r0, r2"),
    (0x09A9CE, "8000", "lsls", "r0, r0, #2"),
    (0x09A9D0, "0019", "adds", "r0, r0, r4"),
    (0x09A9D2, "0909", "lsrs", "r1, r1, #4"),
    (0x09A9D4, "0068", "ldr", "r0, [r0]"),
    (0x09A9D6, "c840", "lsrs", "r0, r1"),
    (0x09A9D8, "6146", "mov", "r1, ip"),
    (0x09A9DA, "4c68", "ldr", "r4, [r1, #4]"),
    (0x09A9DC, "401b", "subs", "r0, r0, r5"),
    (0x09A9DE, "391c", "adds", "r1, r7, #0"),
    (0x09A9E0, "fff7ccf9", "bl", "#0x8099d7c"),
    (0x09A9E4, "011c", "adds", "r1, r0, #0"),
    (0x09A9E6, "6918", "adds", "r1, r5, r1"),
    (0x09A9E8, "201c", "adds", "r0, r4, #0"),
    (0x09A9EA, "fff7c7f9", "bl", "#0x8099d7c"),
    (0x09A9EE, "f0bc", "pop", "{r4, r5, r6, r7}"),
    (0x09A9F0, "02bc", "pop", "{r1}"),
    (0x09A9F2, "0847", "bx", "r1"),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _vector_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


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
    if start < 0 or start >= end or end > len(rom):
        raise ValueError(f"{label} range escapes ROM")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2, "Thumb halfword"), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4, "word"), "little")


def _thumb_bl_target(offset: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def independent_producer_denominator(rom: bytes) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset : offset + 2], "little")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        if _thumb_bl_target(offset, first, second) != CONSUMER_RANGE[0]:
            continue
        raw = rom[offset : offset + 4]
        matches.append(
            {
                "file_offset": offset,
                "raw_hex": raw.hex(),
                "bytes_sha256": _sha(raw),
                "target_file_offset": CONSUMER_RANGE[0],
            }
        )
    if matches != [dict(item) for item in PRODUCERS]:
        raise ValueError("target-limited producer denominator changed")
    pointer = (ROM_BASE + CONSUMER_RANGE[0] + 1).to_bytes(4, "little")
    occurrences = [
        offset
        for offset in range(len(rom) - 3)
        if rom[offset : offset + 4] == pointer
    ]
    if occurrences:
        raise ValueError("consumer Thumb pointer denominator changed")
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "target_file_offset": CONSUMER_RANGE[0],
            "matching_producer_count": len(matches),
        },
        "producers": matches,
        "thumb_pointer_occurrences": occurrences,
        "producer_source_instruction_membership_proven": False,
        "producer_bytes_promoted": False,
    }


def _engine(mode: int) -> Cs:
    engine = Cs(CS_ARCH_ARM, mode)
    engine.detail = True
    return engine


def _decode_one(engine: Cs, rom: bytes, offset: int, end: int):
    window = _bounded(rom, offset, min(offset + 4, end), "instruction window")
    decoded = list(engine.disasm(window, ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        raise ValueError(f"consumer CFG decode failed at 0x{offset:06X}")
    instruction = decoded[0]
    if instruction.size not in (2, 4) or offset + instruction.size > end:
        raise ValueError(f"consumer CFG instruction escapes at 0x{offset:06X}")
    return instruction


def _branch_target(instruction: Any) -> int:
    operands = instruction.operands
    if len(operands) != 1 or operands[0].type != arm_const.ARM_OP_IMM:
        raise ValueError("consumer CFG direct branch operand changed")
    return operands[0].imm - ROM_BASE


def independent_consumer_contract(
    rom: bytes, *, expected_sha256: str = CONSUMER_SHA256
) -> dict[str, Any]:
    start, end = CONSUMER_RANGE
    raw = _bounded(rom, start, end, "consumer")
    if _sha(raw) != expected_sha256:
        raise ValueError("consumer code identity changed")
    engine = _engine(CS_MODE_THUMB)
    pending = [start]
    seen: dict[int, Any] = {}
    byte_owner: dict[int, int] = {}
    leaders = {start}
    terminal_offsets: set[int] = set()
    calls: list[dict[str, int]] = []
    frontiers: list[dict[str, Any]] = []

    while pending:
        offset = pending.pop()
        if offset in seen:
            continue
        if not start <= offset < end or offset & 1:
            frontiers.append({"source_file_offset": None, "target_file_offset": offset})
            continue
        instruction = _decode_one(engine, rom, offset, end)
        for owned in range(offset, offset + instruction.size):
            previous = byte_owner.get(owned)
            if previous is not None and previous != offset:
                raise ValueError("consumer CFG target lands in an instruction middle")
            byte_owner[owned] = offset
        seen[offset] = instruction
        next_offset = offset + instruction.size

        if instruction.id == arm_const.ARM_INS_BL:
            target = _branch_target(instruction)
            if target != HELPER_RANGE[0]:
                raise ValueError("consumer CFG external call target changed")
            calls.append(
                {"source_file_offset": offset, "target_file_offset": target}
            )
            leaders.add(next_offset)
            terminal_offsets.add(offset)
            pending.append(next_offset)
        elif instruction.id == arm_const.ARM_INS_B:
            target = _branch_target(instruction)
            leaders.add(target)
            terminal_offsets.add(offset)
            pending.append(target)
            if instruction.cc != arm_const.ARM_CC_AL:
                leaders.add(next_offset)
                pending.append(next_offset)
        elif instruction.id == arm_const.ARM_INS_BX:
            terminal_offsets.add(offset)
            if offset != 0x09A9F2 or instruction.op_str != "r1":
                frontiers.append(
                    {"source_file_offset": offset, "register": instruction.op_str}
                )
        else:
            if next_offset >= end:
                frontiers.append(
                    {"source_file_offset": offset, "target_file_offset": next_offset}
                )
            else:
                pending.append(next_offset)

    ordered = [seen[offset] for offset in sorted(seen)]
    actual_disassembly = tuple(
        (
            instruction.address - ROM_BASE,
            instruction.bytes.hex(),
            instruction.mnemonic,
            instruction.op_str,
        )
        for instruction in ordered
    )
    if actual_disassembly != CONSUMER_DISASSEMBLY:
        raise ValueError("consumer semantic disassembly changed")
    if len(ordered) != 44 or set(byte_owner) != set(range(start, end)):
        raise ValueError("consumer CFG reachable instruction denominator changed")

    blocks: list[list[int]] = []
    instruction_by_offset = {
        instruction.address - ROM_BASE: instruction for instruction in ordered
    }
    for block_start in sorted(leaders):
        if block_start not in instruction_by_offset:
            raise ValueError("consumer CFG leader is outside reachable instructions")
        cursor = block_start
        while cursor in instruction_by_offset:
            instruction = instruction_by_offset[cursor]
            next_offset = cursor + instruction.size
            cursor = next_offset
            if instruction.address - ROM_BASE in terminal_offsets or cursor in leaders:
                break
        blocks.append([block_start, cursor])
    if tuple(map(tuple, blocks)) != BLOCK_RANGES:
        raise ValueError("consumer CFG basic-block denominator changed")
    calls.sort(key=lambda item: item["source_file_offset"])
    if tuple(calls) != CALL_EDGES:
        raise ValueError("consumer CFG call-edge denominator changed")

    if _u16(rom, start) != 0xB5F0:
        raise ValueError("consumer return proof no longer saves LR")
    if rom[0x09A9EE:end].hex() != "f0bc02bc0847":
        raise ValueError("consumer return epilogue changed")
    for offset in sorted(seen):
        if start < offset < 0x09A9EE and _u16(rom, offset) & 0xFF00 == 0xB000:
            raise ValueError("consumer return proof has an intermediate SP adjustment")
    if frontiers:
        raise ValueError(f"consumer CFG has unresolved frontier: {frontiers}")

    return {
        "root_file_offset": start,
        "code_range": [start, end],
        "code_sha256": CONSUMER_SHA256,
        "decoded_instruction_count": len(ordered),
        "decoded_basic_block_count": len(blocks),
        "block_ranges": blocks,
        "external_call_edges": calls,
        "frontier_count": len(frontiers),
        "return_proof": dict(RETURN_PROOF),
    }


def independent_literal_bindings(rom: bytes) -> list[dict[str, Any]]:
    if _sha(_bounded(rom, *LITERAL_RANGE, "literal pool")) != LITERAL_SHA256:
        raise ValueError("literal pool identity changed")
    bindings: list[dict[str, Any]] = []
    targets = {
        ROM_BASE + SCALE_RANGE[0]: SCALE_RANGE,
        ROM_BASE + FREQUENCY_RANGE[0]: FREQUENCY_RANGE,
    }
    for offset, expected_register, expected_literal in (
        (0x09A9AC, 3, 0x09A9F4),
        (0x09A9B2, 4, 0x09A9F8),
    ):
        instruction = _u16(rom, offset)
        if instruction & 0xF800 != 0x4800:
            raise ValueError("literal load is not Thumb PC-relative LDR")
        if (instruction >> 8) & 7 != expected_register:
            raise ValueError("literal load destination register changed")
        literal = (((ROM_BASE + offset + 4) & ~3) + (instruction & 0xFF) * 4) - ROM_BASE
        if literal != expected_literal:
            raise ValueError("literal PC-relative address changed")
        pointer = _u32(rom, literal)
        if pointer not in targets:
            raise ValueError("literal pointer target changed")
        bindings.append(
            {
                "load_file_offset": offset,
                "load_raw_hex": rom[offset : offset + 2].hex(),
                "literal_range": [literal, literal + 4],
                "pointer": pointer,
                "target_range": list(targets[pointer]),
            }
        )
    return bindings


def independent_helper_contract(
    rom: bytes, *, expected_sha256: str = HELPER_SHA256
) -> dict[str, Any]:
    raw = _bounded(rom, *HELPER_RANGE, "helper")
    if _sha(raw) != expected_sha256:
        raise ValueError("helper identity changed")
    thumb = list(
        _engine(CS_MODE_THUMB).disasm(
            rom[HELPER_RANGE[0] : 0x099D80], ROM_BASE + HELPER_RANGE[0]
        )
    )
    arm = list(
        _engine(CS_MODE_ARM).disasm(
            rom[0x099D80 : HELPER_RANGE[1]], ROM_BASE + 0x099D80
        )
    )
    actual = tuple(
        (
            instruction.address - ROM_BASE,
            instruction.bytes.hex(),
            instruction.mnemonic,
            instruction.op_str,
        )
        for instruction in (*thumb, *arm)
    )
    expected = (
        (0x099D7C, "00a2", "adr", "r2, #0"),
        (0x099D7E, "1047", "bx", "r2"),
        (0x099D80, "902183e0", "umull", "r2, r3, r0, r1"),
        (0x099D84, "000083e2", "add", "r0, r3, #0"),
        (0x099D88, "1eff2fe1", "bx", "lr"),
    )
    if actual != expected:
        raise ValueError("helper interwork/UMULL semantic sequence changed")
    adr_target = ((ROM_BASE + HELPER_RANGE[0] + 4) & ~3)
    if adr_target != ROM_BASE + 0x099D80:
        raise ValueError("helper interwork target changed")
    return {
        "range": list(HELPER_RANGE),
        "sha256": HELPER_SHA256,
        "thumb_range": [HELPER_RANGE[0], 0x099D80],
        "arm_range": [0x099D80, HELPER_RANGE[1]],
        "decoded_instruction_count": len(actual),
        "decoded_basic_block_count": 2,
        "frontier_count": 0,
        "state_switch": "thumb_adr_bx_to_arm",
        "operation": "unsigned_multiply_high32",
    }


def analyze_scale_descriptors(raw: bytes) -> dict[str, Any]:
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
            str(index): count
            for index, count in sorted(Counter(frequency_indices).items())
        },
        "shift_counts": {
            str(index): count for index, count in sorted(Counter(shifts).items())
        },
    }


def analyze_frequency_table(raw: bytes) -> dict[str, Any]:
    if len(raw) != FREQUENCY_RANGE[1] - FREQUENCY_RANGE[0]:
        raise ValueError("frequency table must contain 12 u32 entries")
    values = [int.from_bytes(raw[index : index + 4], "little") for index in range(0, len(raw), 4)]
    if tuple(values) != EXPECTED_FREQUENCIES:
        raise ValueError("frequency table values changed")
    return {"entry_count": len(values), "entry_size": 4, "values_u32": values}


def _frozen_coverage_baseline() -> dict[str, Any]:
    return {
        "path": COVERAGE_PATH.as_posix(),
        "schema": "rom-byte-coverage-v1",
        "sha256": COVERAGE_SHA256,
        **COVERAGE_TOTALS,
        "promotion_bytes": 344,
        "unknown_promotion_bytes": 344,
        "primary_overlap_bytes": 0,
        "all_promotion_bytes_unknown": True,
    }


def analyze_coverage_baseline(coverage: dict[str, Any]) -> dict[str, Any]:
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict) or {
        key: summary.get(key) for key in COVERAGE_TOTALS
    } != COVERAGE_TOTALS:
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
            f"coverage primary overlap: {overlap_bytes}; "
            f"unknown promotion bytes: {unknown_bytes}/{promotion_bytes}"
        )
    return _frozen_coverage_baseline()


def analyze_live_coverage(
    coverage: dict[str, Any],
    *,
    artifact_status: str,
    expected_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Accept only the exact frozen baseline or its exact five-claim projection."""

    if artifact_status not in {"candidate", "accepted"}:
        raise ValueError("coverage artifact status is invalid")
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    summary = coverage.get("summary")
    if (
        not isinstance(segments, list)
        or not isinstance(claims, list)
        or not isinstance(summary, dict)
        or not isinstance(coverage.get("limitations"), list)
    ):
        raise ValueError(
            "coverage claims, segments, summary, or limitations are absent"
        )
    invariant_top = {
        key: value for key, value in coverage.items() if key not in COVERAGE_DYNAMIC_KEYS
    }
    if _sha(_canonical(invariant_top)) != COVERAGE_INVARIANT_TOP_SHA256:
        raise ValueError("coverage invariant top-level identity changed")
    claim_ids = [
        claim.get("id") if isinstance(claim, dict) else None for claim in claims
    ]
    if any(claim_id is None for claim_id in claim_ids) or len(set(claim_ids)) != len(
        claim_ids
    ):
        raise ValueError("coverage claim IDs are missing or duplicate; IDs must be unique")
    try:
        sorted_claims = sorted(claims, key=lambda claim: (claim["range"], claim["id"]))
    except (KeyError, TypeError) as error:
        raise ValueError("coverage claim ordering fields are invalid") from error
    if claims != sorted_claims:
        raise ValueError("coverage claims are not in canonical range/ID order")

    cursor = 0
    unknown_total = 0
    classified_total = 0
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("coverage segment is not an object")
        segment_range = segment.get("range")
        if (
            not isinstance(segment_range, list)
            or len(segment_range) != 2
            or not all(isinstance(value, int) for value in segment_range)
        ):
            raise ValueError("coverage segment range changed")
        start, end = segment_range
        if start != cursor or end <= start or end > ROM_SIZE:
            raise ValueError("coverage segments do not form an exact ROM partition")
        size = end - start
        if segment.get("primary_class") == "unknown":
            unknown_total += size
        else:
            classified_total += size
        cursor = end
    if cursor != ROM_SIZE:
        raise ValueError("coverage segments do not cover the full ROM")
    if (
        summary.get("claim_count") != len(claims)
        or summary.get("segment_count") != len(segments)
        or summary.get("classified_bytes") != classified_total
        or summary.get("unknown_bytes") != unknown_total
        or summary.get("accounted_bytes") != ROM_SIZE
        or classified_total + unknown_total != ROM_SIZE
    ):
        raise ValueError("coverage summary/count/classified/unknown totals are inconsistent")
    if len(expected_claims) != len(COVERAGE_CLAIM_SPECS):
        raise ValueError("coverage expected claim denominator changed")

    states: list[str] = []
    for expected in expected_claims:
        start, end = expected["range"]
        cursor = start
        interval_states: set[str] = set()
        for segment in segments:
            segment_range = segment.get("range")
            if not isinstance(segment_range, list) or len(segment_range) != 2:
                raise ValueError("coverage segment range changed")
            segment_start, segment_end = segment_range
            if segment_end <= start:
                continue
            if segment_start >= end:
                break
            left = max(start, segment_start)
            right = min(end, segment_end)
            if left != cursor or right <= left:
                raise ValueError("coverage has a gap inside a promotion claim")
            if (
                segment.get("primary_class") == "unknown"
                and segment.get("primary_claim_ids") in (None, [])
            ):
                interval_states.add("unknown")
            elif (
                segment.get("primary_class") == expected["primary_class"]
                and segment.get("primary_claim_ids") == [expected["id"]]
            ):
                interval_states.add("owned")
            else:
                raise ValueError(
                    f"coverage owner changed for {expected['id']}: {segment}"
                )
            cursor = right
        if cursor != end or len(interval_states) != 1:
            raise ValueError(f"coverage claim is partial for {expected['id']}")
        states.append(next(iter(interval_states)))

    if len(set(states)) != 1:
        raise ValueError("coverage promotion is only partially applied")
    state = states[0]
    if state == "unknown":
        analyze_coverage_baseline(coverage)
        components = {
            "claims": (claims, COVERAGE_BASELINE_CLAIMS_SHA256),
            "segments": (segments, COVERAGE_BASELINE_SEGMENTS_SHA256),
            "summary": (summary, COVERAGE_BASELINE_SUMMARY_SHA256),
            "limitations": (
                coverage["limitations"],
                COVERAGE_BASELINE_LIMITATIONS_SHA256,
            ),
        }
        for label, (value, expected_sha) in components.items():
            if _sha(_canonical(value)) != expected_sha:
                raise ValueError(
                    f"coverage frozen baseline {label} identity changed"
                )
    elif artifact_status != "accepted":
        raise ValueError("candidate coverage is no longer the frozen unknown baseline")
    else:
        by_id = {
            claim.get("id"): claim
            for claim in claims
            if isinstance(claim, dict) and claim.get("id") is not None
        }
        for expected in expected_claims:
            if by_id.get(expected["id"]) != expected:
                raise ValueError(f"coverage claim changed for {expected['id']}")
            start, end = expected["range"]
            for claim in claims:
                if not isinstance(claim, dict) or claim.get("role") != "primary":
                    continue
                other_range = claim.get("range")
                if not isinstance(other_range, list) or len(other_range) != 2:
                    raise ValueError("coverage primary claim range changed")
                if claim.get("id") != expected["id"] and other_range[0] < end and start < other_range[1]:
                    raise ValueError(f"coverage primary overlap for {expected['id']}")
        expected_ids = {claim["id"] for claim in expected_claims}
        directsound_claims = [claim for claim in claims if claim.get("id") in expected_ids]
        non_directsound_claims = [
            claim for claim in claims if claim.get("id") not in expected_ids
        ]
        if directsound_claims != expected_claims:
            raise ValueError("coverage post DirectSound claim order or identity changed")
        components = {
            "non-DirectSound claims": (
                non_directsound_claims,
                COVERAGE_BASELINE_CLAIMS_SHA256,
            ),
            "segments": (segments, COVERAGE_POST_SEGMENTS_SHA256),
            "summary": (summary, COVERAGE_POST_SUMMARY_SHA256),
            "limitations": (
                coverage["limitations"],
                COVERAGE_POST_LIMITATIONS_SHA256,
            ),
        }
        for label, (value, expected_sha) in components.items():
            if _sha(_canonical(value)) != expected_sha:
                raise ValueError(f"coverage exact post {label} identity changed")
    return {
        "coverage_contract_verified": True,
        "promotion_bytes": 344,
        "promotion_claim_count": 5,
    }


def _coverage_baseline(root: Path) -> dict[str, Any]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    try:
        coverage = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("coverage baseline is not valid JSON") from error
    if not isinstance(coverage, dict):
        raise ValueError("coverage baseline must be an object")
    return analyze_coverage_baseline(coverage)


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    rows = (
        ("exporter", EXPORTER_PATH),
        ("exporter_test", EXPORTER_TEST_PATH),
        ("verifier", VERIFIER_PATH),
        ("verifier_test", VERIFIER_TEST_PATH),
    )
    return {
        key: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())}
        for key, path in rows
    }


def _coverage_projection(payload: dict[str, Any]) -> dict[str, Any]:
    semantic_ranges = payload.get("promotion", {}).get("semantic_ranges")
    if not isinstance(semantic_ranges, list) or len(semantic_ranges) != 5:
        raise ValueError("coverage projection semantic ranges changed")
    by_kind = {
        row.get("kind"): row for row in semantic_ranges if isinstance(row, dict)
    }
    claims = [dict(spec) for spec in COVERAGE_CLAIM_SPECS]
    expected_hashes = {
        "directsound_pitch_high32_interwork_code": HELPER_SHA256,
        "directsound_pitch_consumer_code": CONSUMER_SHA256,
        "directsound_pitch_table_literals": LITERAL_SHA256,
        "directsound_pitch_scale_table": SCALE_SHA256,
        "directsound_pitch_frequency_table": FREQUENCY_SHA256,
    }
    for spec, claim in zip(COVERAGE_CLAIM_SPECS, claims, strict=True):
        row = by_kind.get(spec["artifact_kind"])
        if (
            not isinstance(row, dict)
            or row.get("range") != spec["range"]
            or row.get("sha256") != expected_hashes[spec["artifact_kind"]]
        ):
            raise ValueError("coverage projection artifact range changed")
    return {
        "claim_count": len(claims),
        "byte_count": sum(end - start for start, end in PROMOTION_RANGES),
        "range_vector_sha256": PROMOTION_VECTOR_SHA256,
        "claim_denominator_sha256": _vector_sha(claims),
        "claims": claims,
    }


def expected_coverage_claims(
    payload: dict[str, Any],
    manifest: dict[str, Any],
    *,
    manifest_sha256: str,
) -> list[dict[str, Any]]:
    projection = _coverage_projection(payload)
    if manifest.get("coverage_projection") != projection:
        raise ValueError("coverage projection manifest changed")
    implementation = manifest.get("implementation")
    files = manifest.get("files")
    if not isinstance(implementation, dict) or not isinstance(files, dict):
        raise ValueError("coverage implementation identity is absent")
    verifier = implementation.get("verifier")
    payload_file = files.get(JSON_NAME)
    if not isinstance(verifier, dict) or not isinstance(payload_file, dict):
        raise ValueError("coverage evidence identity is absent")
    non_claims = {key: value for key, value in payload["scope"].items() if value is False}
    claims: list[dict[str, Any]] = []
    semantic_ranges = payload["promotion"]["semantic_ranges"]
    by_kind = {row["kind"]: (index, row) for index, row in enumerate(semantic_ranges)}
    for spec in COVERAGE_CLAIM_SPECS:
        index, row = by_kind[spec["artifact_kind"]]
        start, end = spec["range"]
        claims.append(
            {
                "id": spec["id"],
                "range": [start, end],
                "gba_range": [ROM_BASE + start, ROM_BASE + end],
                "role": "primary",
                "primary_class": spec["primary_class"],
                "claim_kind": spec["claim_kind"],
                "mode": spec["mode"],
                "promotion_batch": SCHEMA,
                "promoted_from_primary_class": "unknown",
                "baseline_unknown_only": True,
                "bytes_sha256": row["sha256"],
                "artifact_range_kind": spec["artifact_kind"],
                "artifact_range_index": index,
                "promotion_range_count": 5,
                "promotion_bytes": 344,
                "promotion_range_vector_sha256": PROMOTION_VECTOR_SHA256,
                "evidence_path": (ARTIFACT_RELATIVE / JSON_NAME).as_posix(),
                "evidence_sha256": payload_file["sha256"],
                "evidence_selector": f"/promotion/semantic_ranges/{index}",
                "promotion_manifest_path": (ARTIFACT_RELATIVE / MANIFEST_NAME).as_posix(),
                "promotion_manifest_sha256": manifest_sha256,
                "independent_verifier_path": verifier["path"],
                "independent_verifier_sha256": verifier["sha256"],
                "non_claims": non_claims,
                "limitations": list(LIMITATIONS),
            }
        )
    return claims


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
    for kind, (start, end), digest in specs:
        if start < previous_end or start >= end:
            raise ValueError("promotion ranges are not disjoint and ascending")
        raw = _bounded(rom, start, end, kind)
        if _sha(raw) != digest:
            raise ValueError(f"{kind} source bytes changed")
        rows.append({"kind": kind, "range": [start, end], "sha256": digest})
        previous_end = end
    return rows


def rebuild_from_rom(
    root: Path | str,
    rom: bytes,
    *,
    validate_live_baseline: bool = True,
) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    semantic_ranges = _semantic_ranges(rom)
    ranges = [item["range"] for item in semantic_ranges]
    if ranges != [list(pair) for pair in PROMOTION_RANGES]:
        raise ValueError("promotion range denominator changed")
    bundle = b"".join(rom[start:end] for start, end in PROMOTION_RANGES)
    if len(bundle) != 344 or _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion binary bundle changed")
    if _vector_sha(ranges) != PROMOTION_VECTOR_SHA256:
        raise ValueError("promotion range vector changed")

    consumer = independent_consumer_contract(rom)
    literals = independent_literal_bindings(rom)
    helper = independent_helper_contract(rom)
    scale = analyze_scale_descriptors(rom[SCALE_RANGE[0] : SCALE_RANGE[1]])
    scale.update({"range": list(SCALE_RANGE), "sha256": SCALE_SHA256})
    frequency = analyze_frequency_table(rom[FREQUENCY_RANGE[0] : FREQUENCY_RANGE[1]])
    frequency.update({"range": list(FREQUENCY_RANGE), "sha256": FREQUENCY_SHA256})

    scale_indices: set[int] = set()
    effective_keys: set[int] = set()
    clamped_keys: list[int] = []
    fine_values: set[int] = set()
    for raw_key in range(256):
        if raw_key > 178:
            key = 178
            fine_domain = (255,)
            clamped_keys.append(raw_key)
        else:
            key = raw_key
            fine_domain = range(256)
        effective_keys.add(key)
        scale_indices.update((key, key + 1))
        fine_values.update(fine_domain)
    frequency_indices = {
        descriptor & 0x0F for descriptor in rom[SCALE_RANGE[0] : SCALE_RANGE[1]]
    }
    input_domain = {
        "raw_key_u8": [0, 255],
        "effective_key": [min(effective_keys), max(effective_keys)],
        "clamped_raw_keys": [min(clamped_keys), max(clamped_keys)],
        "fine_u8": [min(fine_values), max(fine_values)],
        "clamped_fine": 255,
        "scale_access_union": [min(scale_indices), max(scale_indices)],
        "frequency_access_union": [min(frequency_indices), max(frequency_indices)],
    }
    expected_domain = {
        "raw_key_u8": [0, 255],
        "effective_key": [0, 178],
        "clamped_raw_keys": [179, 255],
        "fine_u8": [0, 255],
        "clamped_fine": 255,
        "scale_access_union": [0, 179],
        "frequency_access_union": [0, 11],
    }
    if input_domain != expected_domain:
        raise ValueError("exhaustive u8 input domain changed")

    payload = {
        "schema": SCHEMA,
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "coverage_baseline": (
            _coverage_baseline(repository)
            if validate_live_baseline
            else _frozen_coverage_baseline()
        ),
        "promotion": {
            "ranges": ranges,
            "range_count": len(ranges),
            "byte_count": len(bundle),
            "range_vector_sha256": _vector_sha(ranges),
            "packed_bytes_sha256": _sha(bundle),
            "semantic_ranges": semantic_ranges,
        },
        "producer_denominator": independent_producer_denominator(rom),
        "consumer": consumer,
        "literal_bindings": literals,
        "high32_helper": helper,
        "formula": dict(FORMULA),
        "tables": {"scale": scale, "frequency": frequency},
        "input_domain": input_domain,
        "scope": dict(SCOPE),
    }
    return payload, bundle


def rebuild_payload(
    root: Path | str, *, validate_live_baseline: bool = True
) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    rom = _safe_file(repository, ROM_PATH).read_bytes()
    return rebuild_from_rom(
        repository, rom, validate_live_baseline=validate_live_baseline
    )


def _artifact_files(root: Path, artifact_dir: Path | str) -> dict[str, bytes]:
    requested = Path(artifact_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = Path(os.path.abspath(requested))
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
            raise ValueError(f"artifact directory uses a symlink component: {cursor}")
    directory = requested.resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("artifact path is not a directory")
    members = list(directory.iterdir())
    if any(member.is_symlink() or not member.is_file() for member in members):
        raise ValueError("foreign artifact entry")
    expected = {JSON_NAME, BIN_NAME, MANIFEST_NAME}
    if {member.name for member in members} != expected:
        raise ValueError("foreign artifact file set")
    return {name: (directory / name).read_bytes() for name in expected}


def _file_receipts(files: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    return {
        name: {"size": len(files[name]), "sha256": _sha(files[name])}
        for name in sorted((JSON_NAME, BIN_NAME))
    }


def _verification_report(
    root: Path,
    *,
    status: str,
    payload: dict[str, Any],
    bundle: bytes,
) -> dict[str, Any]:
    implementation = _implementation(root)
    return {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "rom_sha256": ROM_SHA256,
        "coverage_baseline_sha256": COVERAGE_SHA256,
        "coverage_contract_verified": True,
        "promotion_bytes": len(bundle),
        "promotion_claim_count": 5,
        "promotion_range_count": len(PROMOTION_RANGES),
        "promotion_packed_sha256": _sha(bundle),
        "producer_count": len(payload["producer_denominator"]["producers"]),
        "consumer_instruction_count": payload["consumer"][
            "decoded_instruction_count"
        ],
        "consumer_block_count": payload["consumer"][
            "decoded_basic_block_count"
        ],
        "consumer_frontier_count": payload["consumer"]["frontier_count"],
        "helper_instruction_count": payload["high32_helper"][
            "decoded_instruction_count"
        ],
        "verifier_sha256": implementation["verifier"]["sha256"],
        "errors": [],
    }


def _candidate_manifest(
    payload: dict[str, Any], files: dict[str, bytes]
) -> dict[str, Any]:
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": "candidate",
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "promotion": payload["promotion"],
        "scope": payload["scope"],
        "files": _file_receipts(files),
    }


def _accepted_manifest(
    root: Path,
    payload: dict[str, Any],
    files: dict[str, bytes],
) -> dict[str, Any]:
    implementation = _implementation(root)
    report = _verification_report(
        root, status="accepted", payload=payload, bundle=files[BIN_NAME]
    )
    verification = {
        "schema": VERIFY_SCHEMA,
        "command": [
            "python3",
            VERIFIER_PATH.as_posix(),
            "--root",
            ".",
            "--artifact-dir",
            ARTIFACT_RELATIVE.as_posix(),
        ],
        "exit_code": 0,
        "verifier_sha256": implementation["verifier"]["sha256"],
        "report": report,
    }
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "promotion": payload["promotion"],
        "scope": payload["scope"],
        "limitations": list(LIMITATIONS),
        "coverage_projection": _coverage_projection(payload),
        "files": _file_receipts(files),
        "implementation": implementation,
        "producer": {
            "command": [
                "python3",
                EXPORTER_PATH.as_posix(),
                "--root",
                ".",
                "--output-dir",
                ARTIFACT_RELATIVE.as_posix(),
            ],
            "implementation": implementation,
        },
        "verification": verification,
        "verifier": verification,
    }


def _read_live_coverage(root: Path) -> tuple[bytes, dict[str, Any]]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    try:
        coverage = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("live coverage is not valid JSON") from error
    if not isinstance(coverage, dict):
        raise ValueError("live coverage must be an object")
    if raw != _canonical(coverage):
        raise ValueError("live coverage is not canonical JSON")
    return raw, coverage


def verify_artifact(root: Path | str, artifact_dir: Path | str) -> dict[str, Any]:
    repository = _validate_root(root)
    files = _artifact_files(repository, artifact_dir)
    try:
        payload = json.loads(files[JSON_NAME])
        manifest = json.loads(files[MANIFEST_NAME])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("artifact JSON is invalid") from error
    if not isinstance(payload, dict) or _canonical(payload) != files[JSON_NAME]:
        raise ValueError("payload is not canonical JSON")
    if not isinstance(manifest, dict) or _canonical(manifest) != files[MANIFEST_NAME]:
        raise ValueError("manifest is not canonical JSON")

    status = manifest.get("artifact_status")
    if status not in {"candidate", "accepted"}:
        raise ValueError("manifest artifact status is invalid")
    expected_payload, expected_bundle = rebuild_payload(
        repository, validate_live_baseline=status == "candidate"
    )
    if payload != expected_payload:
        raise ValueError("payload differs from independent reconstruction")
    if files[BIN_NAME] != expected_bundle:
        raise ValueError("binary bundle differs from frozen ROM ranges")

    if status == "candidate":
        if manifest != _candidate_manifest(expected_payload, files):
            raise ValueError("candidate manifest differs from independent reconstruction")
        raw_coverage, coverage = _read_live_coverage(repository)
        if _sha(raw_coverage) != COVERAGE_SHA256:
            raise ValueError("candidate coverage is no longer the frozen baseline")
        analyze_coverage_baseline(coverage)
    else:
        expected_manifest = _accepted_manifest(repository, expected_payload, files)
        if manifest != expected_manifest:
            raise ValueError("accepted receipt manifest differs from reconstruction")
        expected_claims = expected_coverage_claims(
            expected_payload,
            manifest,
            manifest_sha256=_sha(files[MANIFEST_NAME]),
        )
        _raw_coverage, coverage = _read_live_coverage(repository)
        analyze_live_coverage(
            coverage,
            artifact_status="accepted",
            expected_claims=expected_claims,
        )
    return _verification_report(
        repository, status=status, payload=expected_payload, bundle=expected_bundle
    )


def _accept_output_target(root: Path, output: Path | str) -> Path:
    requested = Path(output).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = Path(os.path.abspath(requested))
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
            raise ValueError(f"accept output uses a symlink component: {cursor}")
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("accept output must not be the repository root or its ancestor")
    if target.exists():
        raise ValueError("accept output already exists")
    return target


def accept_candidate(
    root: Path | str,
    candidate_dir: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    repository = _validate_root(root)
    candidate_report = verify_artifact(repository, candidate_dir)
    if candidate_report.get("artifact_status") != "candidate":
        raise ValueError("acceptance source is not a candidate")
    files = _artifact_files(repository, candidate_dir)
    payload = json.loads(files[JSON_NAME])
    accepted_manifest = _accepted_manifest(repository, payload, files)
    accepted_files = {
        JSON_NAME: files[JSON_NAME],
        BIN_NAME: files[BIN_NAME],
        MANIFEST_NAME: _canonical(accepted_manifest),
    }
    target = _accept_output_target(repository, output_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.accept-", dir=target.parent)
    )
    try:
        for name, raw in accepted_files.items():
            (temporary / name).write_bytes(raw)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return verify_artifact(repository, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    parser.add_argument("--accept-to", type=Path)
    args = parser.parse_args()
    try:
        report = (
            accept_candidate(args.root, args.artifact_dir, args.accept_to)
            if args.accept_to is not None
            else verify_artifact(args.root, args.artifact_dir)
        )
    except (OSError, ValueError) as error:
        print(
            json.dumps(
                {"schema": VERIFY_SCHEMA, "verified": False, "errors": [str(error)]},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
