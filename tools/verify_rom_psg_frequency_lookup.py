#!/usr/bin/env python3
"""Independently verify and accept the frozen PSG lookup packet.

The verifier intentionally repeats the raw-ROM checks instead of importing the
exporter.  An artifact is accepted only when its bytes, receipt, ROM evidence,
and exact pre/post coverage projection agree with this contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


SCHEMA = "rom-psg-frequency-lookup-v1"
VERIFY_SCHEMA = "rom-psg-frequency-lookup-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "922e06e9b195a31ae6a8ab8c03cb06159aee7218bc4268ac56e22c729b740de6"
COVERAGE_TOTALS = {
    "classified_bytes": 6_121_624,
    "unknown_bytes": 169_832,
    "claim_count": 14_471,
    "segment_count": 16_582,
}
COVERAGE_BASELINE_CLAIMS_SHA256 = (
    "629c6d8730b1f2cd5d7f849084ec8ed62c5bb4f8ce92409fc1063a177467b734"
)
COVERAGE_BASELINE_SEGMENTS_SHA256 = (
    "4727ba4f1f390bd174d25a31522f6474a7e318d8924a09c62a9a92535bf5e6e0"
)
COVERAGE_BASELINE_SUMMARY_SHA256 = (
    "088c1c2bfb1afa002bddd3415efc9f6f2daee41f01a6d70a9ad777fcb0be36b4"
)
COVERAGE_BASELINE_LIMITATIONS_SHA256 = (
    "0ac0b8e3da190b1374fbc2b8673418c11c7dff63220b172142a0a1b874bbd9e3"
)
COVERAGE_INVARIANT_TOP_SHA256 = (
    "af4304b2ac0ce0558eceb97218a4ba6881878de9c6d2fa0e24098178654fb6ca"
)
COVERAGE_POST_SEGMENTS_SHA256 = (
    "7912231dc77663aefe52df6d99beeffafba082bb1ddba081a047c6d5187dc8dd"
)
COVERAGE_POST_SUMMARY_SHA256 = (
    "1e18399bf112fdf712a346c419415603b3b4da3dbe40cece9161e73e437de39e"
)
COVERAGE_POST_LIMITATIONS_SHA256 = (
    "ba0ceefa0cf07c11a3163aa2ebbbb7fe54b56cfd0a21598bffbd24a85eb7d3df"
)
COVERAGE_DYNAMIC_KEYS = frozenset({"claims", "segments", "summary", "limitations"})

JSON_NAME = "rom-psg-frequency-lookup.json"
BIN_NAME = "rom-psg-frequency-lookup.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = Path("artifacts/rom-psg-frequency-lookup-v1")
EXPORTER_PATH = Path("tools/export_rom_psg_frequency_lookup.py")
VERIFIER_PATH = Path("tools/verify_rom_psg_frequency_lookup.py")

PROMOTION_RANGES = (
    (0x09B494, 0x09B4C6),
    (0x09B4C8, 0x09B4CC),
    (0x09B4CC, 0x09B534),
    (0x09B534, 0x09B53C),
    (0x46475C, 0x464798),
)
PROMOTION_RANGE_SHA256 = (
    "969892b0f481afc4872493396ed034c0a696cd3c56ca07d4c0b5d68369e7365d",
    "73cbc760a9346eacd3a16553ac98763cb1a6ee27dbf7d5fa1bfafdb4ce74d9b5",
    "3c3471021d4b57c4d7708443ae8bd180d3b9919dbc049c7e10a41fecd3038e60",
    "89bce1ab76458db38f3a7d995c13f06abad02b6ab3ab8ba9ed7ecc53f913a6c0",
    "197f0679262884d48dd459dcfe690c0a41e8a73cf76cb62838119fc9cb0e7ab6",
)
PROMOTION_RANGE_VECTOR_SHA256 = (
    "5247ee79350c15d6292e52a5e1ef58bd7b7555f50a70bc157e3e936b8ffa0080"
)
PACKED_SHA256 = "e625a5fcc208a971a1ec98723f12b863a707fa9dd3ba8442f7f6d86b3099623b"
SEMANTIC_RANGE_VECTOR_SHA256 = (
    "6683ef2206af27246bc97abb750a02023ea18909611b7dbda9e1987419e515eb"
)

TARGET_CONSUMER_CODE_RANGES = (
    (0x09B494, 0x09B4C6),
    (0x09B4CC, 0x09B534),
)
TARGET_CONSUMER_BLOCK_RANGES = (
    (0x09B494, 0x09B4A8),
    (0x09B4A8, 0x09B4AC),
    (0x09B4AC, 0x09B4B0),
    (0x09B4B0, 0x09B4BC),
    (0x09B4BC, 0x09B4BE),
    (0x09B4BE, 0x09B4C6),
    (0x09B4CC, 0x09B4D0),
    (0x09B4D0, 0x09B4D8),
    (0x09B4D8, 0x09B4E4),
    (0x09B4E4, 0x09B4EA),
    (0x09B4EA, 0x09B52E),
    (0x09B52E, 0x09B534),
)
TARGET_CONSUMER_CODE_SHA256 = (
    "91ac0a7fed3e5840bf3e76dfa8484aa70ad3ec71957b35283e878444163ed9ca"
)
TARGET_CONSUMER_SEMANTIC_VECTOR_SHA256 = (
    "98258c1ad56251612ee4a62d618abcf28b25b79e93b1fc9576502085b908b0c4"
)
UNKNOWN_GAP = (0x09B4C6, 0x09B4C8)

INITIALIZER_CODE_RANGE = (0x09ACF8, 0x09ADC0)
INITIALIZER_CODE_SHA256 = (
    "b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a"
)
INITIALIZER_SEMANTIC_VECTOR_SHA256 = (
    "9bf9f1af3afdb091a18dbd236c6fffbfbb58ce8504bb7650db91109dc234fa96"
)
INITIALIZER_LITERAL_POOL_RANGE = (0x09ADC0, 0x09AE10)
INITIALIZER_LITERAL_POOL_SHA256 = (
    "5b0dd3fbbfc9f8c964f9c0f806548ccd9b72059ee6b67188c9432ac2342652b0"
)
INITIALIZER_BINDING_PAIR_RANGE = (0x09AD74, 0x09AD78)
INITIALIZER_BINDING_PAIR_SHA256 = (
    "45aee5a509e95eb1b4a273000f5f4d922f220ea3d36ff6131dbd021a351444fd"
)
INITIALIZER_PRODUCER = {
    "file_offset": 0x09AA56,
    "raw_hex": "00f04ff9",
    "bytes_sha256": (
        "3cb3a41522f6b753006d687eb512c8d607f7d4f09ea4864b2250713f1a94f71a"
    ),
    "target_file_offset": 0x09ACF8,
}
SOUNDINFO_CONTEXT_RANGE = (0x09A708, 0x09A8FE)
SOUNDINFO_CONTEXT_SHA256 = (
    "4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e"
)
SOUNDINFO_CONTEXT_SEMANTIC_VECTOR_SHA256 = (
    "9dfb2d78417b22dac468c6e2d7f066dd307f31a382b8f90ba0cf25c9f6a09e68"
)
SOUNDINFO_CHAIN_RANGE = (0x09A8C6, 0x09A8D4)
SOUNDINFO_CHAIN_SHA256 = (
    "f683daef4ff9b013ba8ca92dd7de9727094514bcc126ceadcf7e0a8e0df59734"
)
TRAMPOLINE_RANGE = (0x09A684, 0x09A686)
TRAMPOLINE_SHA256 = (
    "477db9ac7ca5efc12e37f882656b8fe5a363ffeb99b2e565a953d10c3c91ab21"
)
DIRECT_TRAMPOLINE_BRANCHES = (
    {"file_offset": 0x09A444, "raw_hex": "00f01ef9", "mnemonic": "bl"},
    {"file_offset": 0x09A50E, "raw_hex": "00f0b9f8", "mnemonic": "bl"},
    {"file_offset": 0x09A52A, "raw_hex": "00f0abf8", "mnemonic": "bl"},
    {"file_offset": 0x09A63E, "raw_hex": "00f021f8", "mnemonic": "bl"},
    {"file_offset": 0x09A6BC, "raw_hex": "fff7e2ff", "mnemonic": "bl"},
    {"file_offset": 0x09A8D0, "raw_hex": "fff7d8fe", "mnemonic": "bl"},
)
CONSUMED_LITERAL_BINDINGS = (
    {
        "load_file_offset": 0x09B4BE,
        "load_raw_hex": "0248",
        "literal_range": [0x09B4C8, 0x09B4CC],
        "pointer": 0x0846475C,
        "target_file_offset": 0x46475C,
        "target_promoted": True,
        "target_semantics_claimed": True,
        "pointer_occurrences": [0x09B4C8],
    },
    {
        "load_file_offset": 0x09B4EA,
        "load_raw_hex": "124b",
        "literal_range": [0x09B534, 0x09B538],
        "pointer": 0x084646C0,
        "target_file_offset": 0x4646C0,
        "target_promoted": False,
        "target_semantics_claimed": False,
        "pointer_occurrences": [0x09B534],
    },
    {
        "load_file_offset": 0x09B4F0,
        "load_raw_hex": "114c",
        "literal_range": [0x09B538, 0x09B53C],
        "pointer": 0x08464744,
        "target_file_offset": 0x464744,
        "target_promoted": False,
        "target_semantics_claimed": False,
        "pointer_occurrences": [0x09B538],
    },
)
SEMANTIC_RANGE_SPECS = (
    {
        "id": "psg-frequency-code-a-09b494",
        "kind": "psg_frequency_consumer_thumb_code",
        "range": [0x09B494, 0x09B4C6],
        "sha256": PROMOTION_RANGE_SHA256[0],
        "semantic_class": "armv4t_psg_frequency_lookup_thumb_code",
        "claim_kind": "psg_frequency_lookup_instruction_bytes",
        "mode": "thumb",
    },
    {
        "id": "psg-frequency-noise-literal-09b4c8",
        "kind": "psg_frequency_consumed_pointer_literal",
        "range": [0x09B4C8, 0x09B4CC],
        "sha256": PROMOTION_RANGE_SHA256[1],
        "semantic_class": "psg_frequency_lookup_consumed_pointer_literals",
        "claim_kind": "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "mode": None,
    },
    {
        "id": "psg-frequency-code-b-09b4cc",
        "kind": "psg_frequency_consumer_thumb_code",
        "range": [0x09B4CC, 0x09B534],
        "sha256": PROMOTION_RANGE_SHA256[2],
        "semantic_class": "armv4t_psg_frequency_lookup_thumb_code",
        "claim_kind": "psg_frequency_lookup_instruction_bytes",
        "mode": "thumb",
    },
    {
        "id": "psg-frequency-nonnoise-literals-09b534",
        "kind": "psg_frequency_consumed_pointer_literal",
        "range": [0x09B534, 0x09B53C],
        "sha256": PROMOTION_RANGE_SHA256[3],
        "semantic_class": "psg_frequency_lookup_consumed_pointer_literals",
        "claim_kind": "psg_frequency_lookup_consumed_pointer_literal_bytes",
        "mode": None,
    },
    {
        "id": "psg-noise-register-table-46475c",
        "kind": "psg_noise_register_descriptor_table",
        "range": [0x46475C, 0x464798],
        "sha256": PROMOTION_RANGE_SHA256[4],
        "semantic_class": "psg_noise_register_descriptor_table",
        "claim_kind": "psg_noise_register_descriptor_bytes",
        "mode": None,
    },
)
PSG_COVERAGE_LIMITATION = (
    "The PSG frequency lookup artifact classifies exactly 226 frozen bytes: "
    "154 bytes in two bounded Thumb code ranges, twelve bytes in three consumed "
    "pointer literals, and a 60-byte channel-4 noise register descriptor table. "
    "The two-byte 0x09B4C6..0x09B4C8 alignment gap remains unknown. Entry proof "
    "is limited to one fixed initializer-to-logical-SoundInfo+0x30-to-BX-r3 "
    "chain; global RAM/computed producers, writers, indirect callers, natural "
    "runtime reachability, the two non-noise target-table semantics, playback, "
    "editing, writeback, relocation, and allocatable space remain unclaimed."
)
SCOPE = {
    "target_limited_raw_branch_denominator_complete": True,
    "initializer_entry_proof_complete": True,
    "target_consumer_cfg_closed": True,
    "lookup_domain_complete_for_all_u8_inputs": True,
    "producer_source_instruction_membership_complete": False,
    "producer_bytes_promoted": False,
    "global_ram_or_computed_producer_denominator_complete": False,
    "global_writer_denominator_complete": False,
    "global_indirect_caller_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "natural_runtime_reachability_complete": False,
    "non_noise_target_table_semantics_complete": False,
    "playback_behavior_proven": False,
    "editing_relocation_writeback_safe": False,
    "allocatable_free_space_proven": False,
}
NOISE_TABLE_VALUES = bytes.fromhex(
    "d7d6d5d4c7c6c5c4b7b6b5b4a7a6a5a497969594878685847776757467666564"
    "57565554474645443736353427262524171615140706050403020100"
)
_THUMB_BL_CANDIDATE = re.compile(
    b"(?=.[\\xf0-\\xf7].[\\xf8-\\xff])", flags=re.DOTALL
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
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"{label} range escapes ROM")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2, "Thumb halfword"), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4, "ROM word"), "little")


def _expect_bytes(rom: bytes, offset: int, raw: bytes, label: str) -> None:
    if _bounded(rom, offset, offset + len(raw), label) != raw:
        raise ValueError(f"{label} semantic bytes changed")


def _thumb_bl_target(rom: bytes, offset: int) -> int:
    first = _u16(rom, offset)
    second = _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"not a Thumb BL at 0x{offset:06X}")
    displacement = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _thumb_engine() -> Cs:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    engine.detail = True
    return engine


def _code_range_end(ranges: tuple[tuple[int, int], ...], offset: int) -> int:
    for start, end in ranges:
        if start <= offset < end:
            return end
    raise ValueError(f"Thumb CFG target escapes frozen code at 0x{offset:06X}")


def _in_code(ranges: tuple[tuple[int, int], ...], offset: int) -> bool:
    return any(start <= offset < end for start, end in ranges)


def _decode_one(
    engine: Cs,
    rom: bytes,
    ranges: tuple[tuple[int, int], ...],
    offset: int,
    label: str,
):
    end = _code_range_end(ranges, offset)
    window = _bounded(rom, offset, min(offset + 4, end), f"{label} instruction")
    decoded = list(engine.disasm(window, ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        raise ValueError(f"{label} CFG decode failed at 0x{offset:06X}")
    instruction = decoded[0]
    if instruction.size not in (2, 4) or offset + instruction.size > end:
        raise ValueError(f"{label} CFG instruction escapes at 0x{offset:06X}")
    return instruction


def _direct_target(instruction: Any, label: str) -> int:
    if (
        len(instruction.operands) != 1
        or instruction.operands[0].type != arm_const.ARM_OP_IMM
    ):
        raise ValueError(f"{label} direct branch operand changed")
    return instruction.operands[0].imm - ROM_BASE


def _semantic_vector(instructions: list[Any]) -> list[list[Any]]:
    return [
        [
            instruction.address - ROM_BASE,
            instruction.size,
            instruction.mnemonic,
            instruction.op_str,
        ]
        for instruction in instructions
    ]


def _decode_linear_thumb(
    rom: bytes, start: int, end: int, label: str
) -> list[Any]:
    engine = _thumb_engine()
    ranges = ((start, end),)
    instructions: list[Any] = []
    offset = start
    while offset < end:
        instruction = _decode_one(engine, rom, ranges, offset, label)
        instructions.append(instruction)
        offset += instruction.size
    if offset != end:
        raise ValueError(f"{label} linear decode does not cover its frozen range")
    return instructions


def _decode_thumb_cfg(
    rom: bytes,
    *,
    ranges: tuple[tuple[int, int], ...],
    root: int,
    allowed_calls: tuple[tuple[int, int], ...],
    return_bx: tuple[int, str],
    label: str,
) -> tuple[list[Any], list[list[int]], list[dict[str, int]], int]:
    engine = _thumb_engine()
    pending = [root]
    seen: dict[int, Any] = {}
    byte_owner: dict[int, int] = {}
    leaders = {root}
    terminals: set[int] = set()
    calls: list[dict[str, int]] = []
    frontiers: list[dict[str, Any]] = []

    while pending:
        offset = pending.pop()
        if offset in seen:
            continue
        if offset & 1 or not _in_code(ranges, offset):
            frontiers.append({"target_file_offset": offset})
            continue
        instruction = _decode_one(engine, rom, ranges, offset, label)
        for owned in range(offset, offset + instruction.size):
            previous = byte_owner.get(owned)
            if previous is not None and previous != offset:
                raise ValueError(f"{label} CFG target lands in an instruction middle")
            byte_owner[owned] = offset
        seen[offset] = instruction
        next_offset = offset + instruction.size

        if instruction.id == arm_const.ARM_INS_B:
            target = _direct_target(instruction, label)
            terminals.add(offset)
            leaders.add(target)
            pending.append(target)
            if instruction.cc != arm_const.ARM_CC_AL:
                leaders.add(next_offset)
                pending.append(next_offset)
        elif instruction.id == arm_const.ARM_INS_BL:
            target = _direct_target(instruction, label)
            call = (offset, target)
            if call not in allowed_calls:
                raise ValueError(f"{label} external-call denominator changed")
            calls.append(
                {"source_file_offset": offset, "target_file_offset": target}
            )
            terminals.add(offset)
            leaders.add(next_offset)
            pending.append(next_offset)
        elif instruction.id == arm_const.ARM_INS_BX:
            terminals.add(offset)
            if (offset, instruction.op_str) != return_bx:
                frontiers.append(
                    {"source_file_offset": offset, "register": instruction.op_str}
                )
        elif _in_code(ranges, next_offset):
            pending.append(next_offset)
        else:
            frontiers.append(
                {"source_file_offset": offset, "target_file_offset": next_offset}
            )

    ordered = [seen[offset] for offset in sorted(seen)]
    expected_bytes = {
        offset for start, end in ranges for offset in range(start, end)
    }
    if set(byte_owner) != expected_bytes:
        raise ValueError(f"{label} reachable instruction denominator changed")
    if frontiers:
        raise ValueError(f"{label} CFG has unresolved frontier: {frontiers}")

    blocks: list[list[int]] = []
    assigned: set[int] = set()
    for block_start in sorted(leaders):
        if block_start not in seen:
            raise ValueError(f"{label} CFG leader is not reachable")
        if block_start in assigned:
            continue
        cursor = block_start
        while cursor in seen and cursor not in assigned:
            instruction = seen[cursor]
            assigned.add(cursor)
            cursor += instruction.size
            if instruction.address - ROM_BASE in terminals or cursor in leaders:
                break
        blocks.append([block_start, cursor])
    if assigned != set(seen):
        raise ValueError(f"{label} basic blocks do not own every instruction")

    internal_edges = 0
    for block_start, block_end in blocks:
        last_offset = max(offset for offset in seen if block_start <= offset < block_end)
        instruction = seen[last_offset]
        next_offset = last_offset + instruction.size
        if instruction.id == arm_const.ARM_INS_B:
            internal_edges += 1
            if instruction.cc != arm_const.ARM_CC_AL:
                internal_edges += 1
        elif instruction.id == arm_const.ARM_INS_BL:
            internal_edges += 1
        elif instruction.id != arm_const.ARM_INS_BX:
            if not _in_code(ranges, next_offset):
                raise ValueError(f"{label} block falls outside frozen code")
            internal_edges += 1
    calls.sort(key=lambda row: row["source_file_offset"])
    if tuple(
        (row["source_file_offset"], row["target_file_offset"]) for row in calls
    ) != allowed_calls:
        raise ValueError(f"{label} external-call denominator changed")
    return ordered, blocks, calls, internal_edges


def _pointer_occurrences(rom: bytes, pointer: int) -> list[int]:
    raw = pointer.to_bytes(4, "little")
    occurrences: list[int] = []
    cursor = 0
    while True:
        offset = rom.find(raw, cursor)
        if offset < 0:
            return occurrences
        occurrences.append(offset)
        cursor = offset + 1


def independent_producer_denominator(rom: bytes) -> dict[str, Any]:
    target = 0x09B494
    matches: list[dict[str, Any]] = []
    for match in _THUMB_BL_CANDIDATE.finditer(rom):
        offset = match.start()
        if offset & 1:
            continue
        if _thumb_bl_target(rom, offset) == target:
            raw = rom[offset : offset + 4]
            matches.append(
                {
                    "file_offset": offset,
                    "raw_hex": raw.hex(),
                    "bytes_sha256": _sha(raw),
                    "target_file_offset": target,
                }
            )
    if matches:
        raise ValueError("target Thumb branch producer denominator changed")
    pointer = ROM_BASE + target + 1
    occurrences = _pointer_occurrences(rom, pointer)
    if occurrences != [0x09AE04]:
        raise ValueError("Thumb pointer occurrence denominator changed")
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, ROM_SIZE],
            "target_file_offset": target,
            "matching_producer_count": len(matches),
        },
        "producers": matches,
        "thumb_pointer_target": pointer,
        "thumb_pointer_occurrences": occurrences,
        "producer_source_instruction_membership_proven": False,
        "producer_bytes_promoted": False,
    }


def independent_initializer_provenance(
    rom: bytes, *, expected_sha256: str = INITIALIZER_CODE_SHA256
) -> dict[str, Any]:
    producer_raw = _bounded(rom, 0x09AA56, 0x09AA5A, "initializer producer")
    if (
        producer_raw.hex() != INITIALIZER_PRODUCER["raw_hex"]
        or _sha(producer_raw) != INITIALIZER_PRODUCER["bytes_sha256"]
    ):
        raise ValueError("initializer producer changed")
    if _thumb_bl_target(rom, 0x09AA56) != 0x09ACF8:
        raise ValueError("initializer producer target changed")
    code = _bounded(rom, *INITIALIZER_CODE_RANGE, "initializer code")
    code_sha256 = _sha(code)
    if code_sha256 != expected_sha256:
        raise ValueError("initializer code identity hash changed")
    pool = _bounded(rom, *INITIALIZER_LITERAL_POOL_RANGE, "initializer pool")
    if _sha(pool) != INITIALIZER_LITERAL_POOL_SHA256:
        raise ValueError("initializer literal pool changed")

    instructions, blocks, calls, internal_edges = _decode_thumb_cfg(
        rom,
        ranges=(INITIALIZER_CODE_RANGE,),
        root=INITIALIZER_CODE_RANGE[0],
        allowed_calls=((0x09AD86, 0x09C0E0),),
        return_bx=(0x09ADBE, "r0"),
        label="initializer",
    )
    if _sha(_canonical(_semantic_vector(instructions))) != (
        INITIALIZER_SEMANTIC_VECTOR_SHA256
    ):
        raise ValueError("initializer semantic disassembly changed")
    expected_blocks = [
        [0x09ACF8, 0x09AD3A],
        [0x09AD3A, 0x09AD8A],
        [0x09AD8A, 0x09ADB8],
        [0x09ADB8, 0x09ADC0],
    ]
    if len(instructions) != 99 or blocks != expected_blocks or internal_edges != 4:
        raise ValueError("initializer CFG block/instruction denominator changed")

    literal_offsets: list[int] = []
    for instruction in instructions:
        offset = instruction.address - ROM_BASE
        if instruction.size != 2:
            continue
        halfword = _u16(rom, offset)
        if halfword & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
        if not INITIALIZER_LITERAL_POOL_RANGE[0] <= literal < (
            INITIALIZER_LITERAL_POOL_RANGE[1]
        ):
            raise ValueError("initializer PC-relative literal escapes frozen pool")
        literal_offsets.append(literal)
    if len(literal_offsets) != 20 or len(set(literal_offsets)) != 20:
        raise ValueError("initializer PC-relative literal denominator changed")

    if rom[0x09ACF8:0x09ACFC].hex() != "70b581b0":
        raise ValueError("initializer entry stack/LR proof changed")
    if rom[0x09ADB8:0x09ADC0].hex() != "01b070bc01bc0047":
        raise ValueError("initializer structured return proof changed")
    _expect_bytes(rom, 0x09AD74, bytes.fromhex("2348"), "initializer LDR")
    _expect_bytes(rom, 0x09AD76, bytes.fromhex("2063"), "initializer STR")
    if _u32(rom, 0x09AE04) != ROM_BASE + 0x09B495:
        raise ValueError("initializer SoundInfo pointer changed")
    return {
        "producer": dict(INITIALIZER_PRODUCER),
        "code_range": list(INITIALIZER_CODE_RANGE),
        "code_sha256": code_sha256,
        "decoded_instruction_count": len(instructions),
        "decoded_basic_block_count": len(blocks),
        "block_ranges": blocks,
        "external_call_edges": calls,
        "frontier_count": 0,
        "cfg_closed": True,
        "return_closed": True,
        "pc_relative_literal_count": len(literal_offsets),
        "literal_pool_range": list(INITIALIZER_LITERAL_POOL_RANGE),
        "literal_pool_sha256": INITIALIZER_LITERAL_POOL_SHA256,
        "binding": {
            "ldr_file_offset": 0x09AD74,
            "ldr_raw_hex": "2348",
            "literal_file_offset": 0x09AE04,
            "pointer": ROM_BASE + 0x09B495,
            "str_file_offset": 0x09AD76,
            "str_raw_hex": "2063",
            "store": "str r0,[r4,#0x30]",
            "pair_range": list(INITIALIZER_BINDING_PAIR_RANGE),
            "pair_sha256": INITIALIZER_BINDING_PAIR_SHA256,
        },
    }


def independent_slot_consumer_provenance(
    rom: bytes, *, expected_sha256: str = SOUNDINFO_CONTEXT_SHA256
) -> dict[str, Any]:
    context = _bounded(rom, *SOUNDINFO_CONTEXT_RANGE, "SoundInfo context")
    context_sha256 = _sha(context)
    if context_sha256 != expected_sha256:
        raise ValueError("SoundInfo slot context identity hash changed")
    instructions = _decode_linear_thumb(
        rom, *SOUNDINFO_CONTEXT_RANGE, "SoundInfo context"
    )
    if len(instructions) != 245 or _sha(
        _canonical(_semantic_vector(instructions))
    ) != SOUNDINFO_CONTEXT_SEMANTIC_VECTOR_SHA256:
        raise ValueError("SoundInfo slot provenance semantic disassembly changed")

    for instruction in instructions:
        offset = instruction.address - ROM_BASE
        if not 0x09A720 <= offset < 0x09A8CC or instruction.size != 2:
            continue
        halfword = _u16(rom, offset)
        if (
            halfword & 0xFF00 == 0xB000
            or halfword & 0xFE00 in (0xB400, 0xBC00)
        ):
            raise ValueError("SoundInfo stack pointer changes before slot reload")
        if halfword & 0xF800 == 0x9000 and halfword & 0xFF == 1:
            raise ValueError("SoundInfo [sp,#4] cell is overwritten before reload")

    for offset, raw, label in (
        (0x09A71A, "7949", "SoundInfo literal load"),
        (0x09A71C, "0968", "SoundInfo dereference"),
        (0x09A71E, "0191", "SoundInfo stack store"),
        (0x09A8CC, "019b", "SoundInfo reload"),
        (0x09A8CE, "1b6b", "SoundInfo field load"),
        (0x09A8D0, "fff7d8fe", "SoundInfo trampoline call"),
    ):
        _expect_bytes(rom, offset, bytes.fromhex(raw), label)
    literal_load = _u16(rom, 0x09A71A)
    literal_offset = ((0x09A71A + 4) & ~3) + (literal_load & 0xFF) * 4
    if literal_offset != 0x09A900 or _u32(rom, literal_offset) != 0x03007FF0:
        raise ValueError("SoundInfo literal value changed")
    expected_branches = [
        {**row, "target_file_offset": 0x09A684}
        for row in DIRECT_TRAMPOLINE_BRANCHES
    ]
    branches: list[dict[str, Any]] = []
    for match in _THUMB_BL_CANDIDATE.finditer(rom):
        offset = match.start()
        if offset & 1 or _thumb_bl_target(rom, offset) != 0x09A684:
            continue
        branches.append(
            {
                "file_offset": offset,
                "raw_hex": rom[offset : offset + 4].hex(),
                "mnemonic": "bl",
                "target_file_offset": 0x09A684,
            }
        )
    if branches != expected_branches:
        raise ValueError("trampoline direct-branch denominator changed")
    if _thumb_bl_target(rom, 0x09A8D0) != 0x09A684:
        raise ValueError("SoundInfo accepted slot call target changed")
    _expect_bytes(rom, 0x09A684, bytes.fromhex("1847"), "trampoline")
    if _sha(rom[0x09A684:0x09A686]) != TRAMPOLINE_SHA256:
        raise ValueError("trampoline provenance changed")
    chain_sha256 = _sha(_bounded(rom, *SOUNDINFO_CHAIN_RANGE, "SoundInfo chain"))
    if chain_sha256 != SOUNDINFO_CHAIN_SHA256:
        raise ValueError("SoundInfo chain provenance changed")
    return {
        "context_range": list(SOUNDINFO_CONTEXT_RANGE),
        "context_sha256": context_sha256,
        "literal_load": {"file_offset": 0x09A71A, "raw_hex": "7949", "literal_file_offset": 0x09A900, "literal_value": 0x03007FF0},
        "dereference": {"file_offset": 0x09A71C, "raw_hex": "0968", "operation": "ldr r1,[r1]"},
        "stack_store": {"file_offset": 0x09A71E, "raw_hex": "0191", "operation": "str r1,[sp,#4]"},
        "stack_cell_liveness": {"cell": "[sp,#4]", "overwritten_before_reload": False, "sp_adjustment_until_reload": 0, "reload_file_offset": 0x09A8CC, "reload_raw_hex": "019b"},
        "load_and_call": {"load_file_offset": 0x09A8CE, "load_raw_hex": "1b6b", "field_offset": 0x30, "call_file_offset": 0x09A8D0, "call_raw_hex": "fff7d8fe", "trampoline_file_offset": 0x09A684},
        "chain_range": list(SOUNDINFO_CHAIN_RANGE),
        "chain_sha256": chain_sha256,
        "direct_trampoline_branch_denominator": branches,
        "accepted_slot_path_callsites": [0x09A8D0],
        "trampoline": {
            "range": list(TRAMPOLINE_RANGE),
            "sha256": TRAMPOLINE_SHA256,
            "raw_hex": "1847",
            "operation": "bx r3",
            "existing_owner": {"id": "cfg-thumb-0752-09a684", "primary_class": "armv4t_cfg_reachable_thumb_code", "range": list(TRAMPOLINE_RANGE)},
            "promoted": False,
        },
    }


def independent_consumer_contract(
    rom: bytes, *, expected_sha256: str = TARGET_CONSUMER_CODE_SHA256
) -> dict[str, Any]:
    raw = _bounded(
        rom, *TARGET_CONSUMER_CODE_RANGES[0], "consumer code A"
    ) + _bounded(rom, *TARGET_CONSUMER_CODE_RANGES[1], "consumer code B")
    code_sha256 = _sha(raw)
    if code_sha256 != expected_sha256:
        raise ValueError("consumer code identity hash changed")
    instructions, blocks, calls, internal_edges = _decode_thumb_cfg(
        rom,
        ranges=TARGET_CONSUMER_CODE_RANGES,
        root=TARGET_CONSUMER_CODE_RANGES[0][0],
        allowed_calls=(),
        return_bx=(0x09B532, "r1"),
        label="consumer",
    )
    if _sha(_canonical(_semantic_vector(instructions))) != (
        TARGET_CONSUMER_SEMANTIC_VECTOR_SHA256
    ):
        raise ValueError("consumer semantic disassembly changed")
    expected_blocks = [list(pair) for pair in TARGET_CONSUMER_BLOCK_RANGES]
    if (
        len(instructions) != 77
        or blocks != expected_blocks
        or calls
        or internal_edges != 16
    ):
        raise ValueError("consumer CFG block/edge denominator changed")

    entry = _u16(rom, 0x09B494)
    if entry != 0xB5F0 or not entry & 0x0100:
        raise ValueError("consumer return proof no longer saves LR")
    _expect_bytes(rom, 0x09B4BE, bytes.fromhex("0248"), "consumer literal")
    _expect_bytes(rom, 0x09B52E, bytes.fromhex("f0bc02bc0847"), "consumer return")
    for instruction in instructions:
        offset = instruction.address - ROM_BASE
        if offset >= 0x09B52E or instruction.size != 2:
            continue
        if _u16(rom, offset) & 0xFF00 == 0xB000:
            raise ValueError("consumer return proof has an intermediate SP adjustment")
    return {
        "root_file_offset": 0x09B494,
        "code_bytes": len(raw),
        "code_sha256": code_sha256,
        "decoded_instruction_count": len(instructions),
        "decoded_basic_block_count": len(blocks),
        "code_ranges": [list(pair) for pair in TARGET_CONSUMER_CODE_RANGES],
        "block_ranges": blocks,
        "internal_edge_count": internal_edges,
        "external_call_edges": calls,
        "frontier_count": 0,
        "structured_return_count": 1,
        "return_proof": {
            "epilogue_range": [0x09B52E, 0x09B534],
            "epilogue_raw_hex": "f0bc02bc0847",
            "saved_lr_at_entry": True,
            "stack_adjustment_between_entry_and_epilogue": 0,
            "restored_lr_register": "r1",
            "return_instruction": "bx r1",
        },
        "unclassified_unknown_ranges": [list(UNKNOWN_GAP)],
    }


def independent_literal_bindings(rom: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for expected in CONSUMED_LITERAL_BINDINGS:
        offset = expected["load_file_offset"]
        raw = _bounded(rom, offset, offset + 2, "consumer literal")
        if raw.hex() != expected["load_raw_hex"]:
            raise ValueError("literal load semantic bytes changed")
        instruction = int.from_bytes(raw, "little")
        literal = (((ROM_BASE + offset + 4) & ~3) + (instruction & 0xFF) * 4) - ROM_BASE
        if literal != expected["literal_range"][0]:
            raise ValueError("literal pointer address changed")
        if _u32(rom, literal) != expected["pointer"]:
            raise ValueError("literal pointer value changed")
        if _pointer_occurrences(rom, expected["pointer"]) != expected["pointer_occurrences"]:
            raise ValueError("literal pointer occurrence denominator changed")
        rows.append(dict(expected))
    return rows


def analyze_noise_table(raw: bytes) -> dict[str, Any]:
    if len(raw) != 60:
        raise ValueError("noise table length changed")
    if raw != NOISE_TABLE_VALUES:
        raise ValueError("noise table bytes changed")
    values = list(raw)
    if len(set(values)) != 60:
        raise ValueError("noise table entries are not unique")
    return {
        "entry_count": 60,
        "entry_size": 1,
        "unique_entry_count": 60,
        "values_u8": values,
        "sha256": PROMOTION_RANGE_SHA256[4],
        "reachable_index_domain": [0, 59],
        "every_table_entry_reachable": True,
        "edge_indices": {"20": 0, "21": 0, "22": 1, "79": 58, "80": 59, "255": 59},
    }


def lookup_index(type_value: int, key: int) -> int | None:
    selected_type = type_value & 0xFF
    selected_key = key & 0xFF
    if selected_type != 4:
        return None
    return 0 if selected_key <= 20 else min((selected_key - 21) & 0xFF, 59)


def _frozen_coverage_baseline() -> dict[str, Any]:
    return {
        "path": COVERAGE_PATH.as_posix(),
        "schema": "rom-byte-coverage-v1",
        "sha256": COVERAGE_SHA256,
        **COVERAGE_TOTALS,
        "promotion_bytes": 226,
        "unknown_promotion_bytes": 226,
        "primary_overlap_bytes": 0,
        "all_promotion_bytes_unknown": True,
    }


def analyze_coverage_baseline(coverage: dict[str, Any]) -> dict[str, Any]:
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict) or {key: summary.get(key) for key in COVERAGE_TOTALS} != COVERAGE_TOTALS:
        raise ValueError("coverage baseline totals changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list):
        raise ValueError("coverage baseline segments are absent")
    unknown = 0
    overlap = 0
    for start, end in PROMOTION_RANGES:
        cursor = start
        for segment in segments:
            raw_range = segment.get("range") if isinstance(segment, dict) else None
            if not isinstance(raw_range, list) or len(raw_range) != 2 or not all(isinstance(v, int) for v in raw_range):
                raise ValueError("coverage baseline contains an invalid segment range")
            left_bound, right_bound = raw_range
            if right_bound <= start:
                continue
            if left_bound >= end:
                break
            left = max(start, left_bound)
            right = min(end, right_bound)
            if left != cursor or right <= left:
                raise ValueError("coverage baseline has a gap or overlap inside a promotion range")
            if segment.get("primary_class") == "unknown" and segment.get("primary_claim_ids") in (None, []):
                unknown += right - left
            else:
                overlap += right - left
            cursor = right
        if cursor != end:
            raise ValueError("coverage baseline does not cover a promotion range")
    if unknown != 226 or overlap:
        raise ValueError("coverage baseline unknown/overlap contract changed")
    return _frozen_coverage_baseline()


def _read_live_coverage(root: Path) -> tuple[bytes, dict[str, Any]]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    try:
        coverage = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("live coverage is not valid JSON") from error
    if not isinstance(coverage, dict) or raw != _canonical(coverage):
        raise ValueError("live coverage is not canonical JSON")
    return raw, coverage


def _coverage_projection(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("promotion", {}).get("semantic_ranges")
    if not isinstance(rows, list) or rows != [dict(row) for row in SEMANTIC_RANGE_SPECS]:
        raise ValueError("coverage projection semantic range identity changed")
    claims = [
        {
            "id": row["id"],
            "artifact_kind": row["kind"],
            "range": list(row["range"]),
            "primary_class": row["semantic_class"],
            "claim_kind": row["claim_kind"],
            "mode": row["mode"],
        }
        for row in rows
    ]
    return {
        "claim_count": 5,
        "byte_count": 226,
        "range_vector_sha256": PROMOTION_RANGE_VECTOR_SHA256,
        "semantic_range_vector_sha256": SEMANTIC_RANGE_VECTOR_SHA256,
        "claim_denominator_sha256": _vector_sha(claims),
        "claims": claims,
    }


def _implementation(root: Path) -> dict[str, Any]:
    return {
        "exporter": {"path": EXPORTER_PATH.as_posix(), "sha256": _sha(_safe_file(root, EXPORTER_PATH).read_bytes())},
        "verifier": {"path": VERIFIER_PATH.as_posix(), "sha256": _sha(_safe_file(root, VERIFIER_PATH).read_bytes())},
    }


def _file_receipts(files: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    return {name: {"size": len(files[name]), "sha256": _sha(files[name])} for name in sorted(files)}


def expected_coverage_claims(
    payload: dict[str, Any], manifest: dict[str, Any], *, manifest_sha256: str
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
    for index, row in enumerate(payload["promotion"]["semantic_ranges"]):
        start, end = row["range"]
        claims.append(
            {
                "id": row["id"],
                "range": [start, end],
                "gba_range": [ROM_BASE + start, ROM_BASE + end],
                "role": "primary",
                "primary_class": row["semantic_class"],
                "claim_kind": row["claim_kind"],
                "mode": row["mode"],
                "promotion_batch": SCHEMA,
                "promoted_from_primary_class": "unknown",
                "baseline_unknown_only": True,
                "bytes_sha256": row["sha256"],
                "artifact_range_kind": row["kind"],
                "artifact_range_index": index,
                "promotion_range_count": 5,
                "promotion_bytes": 226,
                "promotion_range_vector_sha256": PROMOTION_RANGE_VECTOR_SHA256,
                "evidence_path": (ARTIFACT_RELATIVE / JSON_NAME).as_posix(),
                "evidence_sha256": payload_file["sha256"],
                "evidence_selector": f"/promotion/semantic_ranges/{index}",
                "promotion_manifest_path": (ARTIFACT_RELATIVE / MANIFEST_NAME).as_posix(),
                "promotion_manifest_sha256": manifest_sha256,
                "independent_verifier_path": verifier["path"],
                "independent_verifier_sha256": verifier["sha256"],
                "non_claims": non_claims,
                "limitations": list(payload["limitations"]),
            }
        )
    return claims


def _build_payload(repository: Path, rom: bytes, *, validate_live_baseline: bool) -> tuple[dict[str, Any], bytes]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    ranges = [list(pair) for pair in PROMOTION_RANGES]
    bundle = b"".join(_bounded(rom, start, end, "promotion range") for start, end in PROMOTION_RANGES)
    if len(bundle) != 226 or _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion binary bundle changed")
    if _sha(_canonical(ranges)) != PROMOTION_RANGE_VECTOR_SHA256:
        raise ValueError("promotion range vector receipt identity changed")
    semantic_ranges = [dict(row) for row in SEMANTIC_RANGE_SPECS]
    if _sha(_canonical(semantic_ranges)) != SEMANTIC_RANGE_VECTOR_SHA256:
        raise ValueError("semantic range vector receipt identity changed")
    for index, (start, end) in enumerate(PROMOTION_RANGES):
        if _sha(_bounded(rom, start, end, "semantic range")) != PROMOTION_RANGE_SHA256[index]:
            raise ValueError("semantic promotion range bytes changed")
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "coverage_baseline": _coverage_baseline(repository) if validate_live_baseline else _frozen_coverage_baseline(),
        "promotion": {
            "ranges": ranges,
            "range_count": 5,
            "byte_count": 226,
            "range_vector_sha256": PROMOTION_RANGE_VECTOR_SHA256,
            "packed_bytes_sha256": PACKED_SHA256,
            "semantic_ranges": semantic_ranges,
            "semantic_range_vector_sha256": SEMANTIC_RANGE_VECTOR_SHA256,
        },
        "producer_denominator": independent_producer_denominator(rom),
        "provenance": {
            "initializer": independent_initializer_provenance(rom),
            "soundinfo_slot": independent_slot_consumer_provenance(rom),
        },
        "consumer": independent_consumer_contract(rom),
        "literal_bindings": independent_literal_bindings(rom),
        "table": dict(analyze_noise_table(_bounded(rom, 0x46475C, 0x464798, "noise table")), range=[0x46475C, 0x464798]),
        "lookup": {
            "type_input_width": "u8",
            "key_input_width": "u8",
            "type_selector": 4,
            "index_formula": "0 if key<=20 else min(u8(key-21),59)",
            "type_input_truncated_before_dispatch": True,
            "key_input_truncated_before_index": True,
            "enumerated_type_domain": [0, 255],
            "enumerated_key_domain": [0, 255],
            "reachable_index_domain": [0, 59],
            "reachable_index_count": 60,
            "every_table_entry_reachable": all(lookup_index(4, key) is not None for key in range(256)),
            "edge_indices": {"20": 0, "21": 0, "22": 1, "79": 58, "80": 59, "255": 59},
        },
        "scope": dict(SCOPE),
        "limitations": [PSG_COVERAGE_LIMITATION],
    }
    return payload, bundle


def _coverage_baseline(root: Path) -> dict[str, Any]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    try:
        coverage = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("coverage baseline is not valid JSON") from error
    if not isinstance(coverage, dict) or raw != _canonical(coverage):
        raise ValueError("coverage baseline is not canonical JSON")
    return analyze_coverage_baseline(coverage)


def rebuild_from_rom(
    root: Path | str, rom: bytes, *, validate_live_baseline: bool = True
) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    return _build_payload(repository, rom, validate_live_baseline=validate_live_baseline)


def rebuild_payload(
    root: Path | str, *, validate_live_baseline: bool = True
) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    return rebuild_from_rom(
        repository,
        _safe_file(repository, ROM_PATH).read_bytes(),
        validate_live_baseline=validate_live_baseline,
    )


def _artifact_files(root: Path, artifact_dir: Path | str) -> dict[str, bytes]:
    requested = Path(artifact_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = Path(os.path.abspath(requested))
    scan_base = Path(requested.anchor)
    for candidate in (root, Path(tempfile.gettempdir())):
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
    expected = {JSON_NAME, BIN_NAME, MANIFEST_NAME}
    if any(member.is_symlink() or not member.is_file() for member in members):
        raise ValueError("foreign artifact entry")
    if {member.name for member in members} != expected:
        raise ValueError("foreign artifact file set")
    return {name: (directory / name).read_bytes() for name in expected}


def _candidate_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": "candidate",
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "promotion": payload["promotion"],
        "scope": payload["scope"],
        "limitations": payload["limitations"],
        "files": _file_receipts(files),
    }


def _verification_report(root: Path, *, status: str, payload: dict[str, Any], bundle: bytes) -> dict[str, Any]:
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
        "promotion_range_count": 5,
        "promotion_packed_sha256": _sha(bundle),
        "producer_count": 0,
        "consumer_instruction_count": payload["consumer"]["decoded_instruction_count"],
        "consumer_block_count": payload["consumer"]["decoded_basic_block_count"],
        "consumer_frontier_count": payload["consumer"]["frontier_count"],
        "verifier_sha256": implementation["verifier"]["sha256"],
        "errors": [],
    }


def _accepted_manifest(root: Path, payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    implementation = _implementation(root)
    report = _verification_report(root, status="accepted", payload=payload, bundle=files[BIN_NAME])
    verification = {
        "schema": VERIFY_SCHEMA,
        "command": ["python3", VERIFIER_PATH.as_posix(), "--root", ".", "--artifact-dir", ARTIFACT_RELATIVE.as_posix()],
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
        "limitations": list(payload["limitations"]),
        "coverage_projection": _coverage_projection(payload),
        "files": _file_receipts(files),
        "implementation": implementation,
        "producer": {
            "command": ["python3", EXPORTER_PATH.as_posix(), "--root", ".", "--output-dir", ARTIFACT_RELATIVE.as_posix()],
            "implementation": implementation,
        },
        "verification": verification,
        "verifier": verification,
    }


def _check_partition(coverage: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    summary = coverage.get("summary")
    if not isinstance(segments, list) or not isinstance(claims, list) or not isinstance(summary, dict) or not isinstance(coverage.get("limitations"), list):
        raise ValueError("coverage claims, segments, summary, or limitations are absent")
    cursor = 0
    classified = 0
    unknown = 0
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("coverage segment is not an object")
        raw_range = segment.get("range")
        if not isinstance(raw_range, list) or len(raw_range) != 2 or not all(isinstance(value, int) for value in raw_range):
            raise ValueError("coverage segment range changed")
        start, end = raw_range
        if start != cursor or end <= start or end > ROM_SIZE:
            raise ValueError("coverage segments do not form an exact ROM partition")
        if segment.get("primary_class") == "unknown":
            unknown += end - start
        else:
            classified += end - start
        cursor = end
    if cursor != ROM_SIZE:
        raise ValueError("coverage segments do not cover the full ROM")
    if summary.get("claim_count") != len(claims) or summary.get("segment_count") != len(segments) or summary.get("classified_bytes") != classified or summary.get("unknown_bytes") != unknown or summary.get("accounted_bytes") != ROM_SIZE or classified + unknown != ROM_SIZE:
        raise ValueError("coverage summary/count/classified/unknown totals are inconsistent")
    return segments, claims, summary


def analyze_live_coverage(
    coverage: dict[str, Any], *, artifact_status: str, expected_claims: list[dict[str, Any]]
) -> dict[str, Any]:
    if artifact_status not in {"candidate", "accepted"}:
        raise ValueError("coverage artifact status is invalid")
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    invariant_top = {key: value for key, value in coverage.items() if key not in COVERAGE_DYNAMIC_KEYS}
    if _sha(_canonical(invariant_top)) != COVERAGE_INVARIANT_TOP_SHA256:
        raise ValueError("coverage invariant top-level identity changed")
    segments, claims, summary = _check_partition(coverage)
    ids = [claim.get("id") if isinstance(claim, dict) else None for claim in claims]
    if any(value is None for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("coverage claim IDs are missing or duplicate; IDs must be unique")
    try:
        if claims != sorted(claims, key=lambda claim: (claim["range"], claim["id"])):
            raise ValueError("coverage claims are not in canonical range/ID order")
    except (KeyError, TypeError) as error:
        raise ValueError("coverage claim ordering fields are invalid") from error
    if len(expected_claims) != 5:
        raise ValueError("coverage expected claim denominator changed")

    states: list[str] = []
    for expected in expected_claims:
        start, end = expected.get("range", [None, None])
        cursor = start
        seen: set[str] = set()
        for segment in segments:
            left_bound, right_bound = segment["range"]
            if right_bound <= start:
                continue
            if left_bound >= end:
                break
            left = max(start, left_bound)
            right = min(end, right_bound)
            if left != cursor or right <= left:
                raise ValueError("coverage has a gap inside a promotion claim")
            if segment.get("primary_class") == "unknown" and segment.get("primary_claim_ids") in (None, []):
                seen.add("unknown")
            elif segment.get("primary_class") == expected.get("primary_class") and segment.get("primary_claim_ids") == [expected.get("id")]:
                seen.add("owned")
            else:
                raise ValueError(f"coverage owner changed for {expected.get('id')}")
            cursor = right
        if cursor != end or len(seen) != 1:
            raise ValueError(f"coverage claim is partial for {expected.get('id')}")
        states.append(next(iter(seen)))
    if len(set(states)) != 1:
        raise ValueError("coverage promotion is only partially applied")

    if states[0] == "unknown":
        analyze_coverage_baseline(coverage)
        components = {
            "claims": (claims, COVERAGE_BASELINE_CLAIMS_SHA256),
            "segments": (segments, COVERAGE_BASELINE_SEGMENTS_SHA256),
            "summary": (summary, COVERAGE_BASELINE_SUMMARY_SHA256),
            "limitations": (coverage["limitations"], COVERAGE_BASELINE_LIMITATIONS_SHA256),
        }
        for label, (value, expected_sha) in components.items():
            if _sha(_canonical(value)) != expected_sha:
                raise ValueError(f"coverage frozen baseline {label} identity changed")
    else:
        if artifact_status != "accepted":
            raise ValueError("candidate coverage is no longer the frozen unknown baseline")
        expected_ids = {claim["id"] for claim in expected_claims}
        by_id = {claim.get("id"): claim for claim in claims if isinstance(claim, dict)}
        for expected in expected_claims:
            if by_id.get(expected["id"]) != expected:
                raise ValueError(f"coverage claim changed for {expected['id']}")
        projected_claims = [claim for claim in claims if claim.get("id") in expected_ids]
        if projected_claims != expected_claims:
            raise ValueError("coverage post PSG claim order or identity changed")
        non_psg = [claim for claim in claims if claim.get("id") not in expected_ids]
        components = {
            "non-PSG claims": (non_psg, COVERAGE_BASELINE_CLAIMS_SHA256),
            "segments": (segments, COVERAGE_POST_SEGMENTS_SHA256),
            "summary": (summary, COVERAGE_POST_SUMMARY_SHA256),
            "limitations": (coverage["limitations"], COVERAGE_POST_LIMITATIONS_SHA256),
        }
        for label, (value, expected_sha) in components.items():
            if _sha(_canonical(value)) != expected_sha:
                raise ValueError(f"coverage exact post {label} identity changed")
    return {"coverage_contract_verified": True, "promotion_bytes": 226, "promotion_claim_count": 5}


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
    expected_payload, expected_bundle = rebuild_payload(repository, validate_live_baseline=status == "candidate")
    if payload != expected_payload:
        raise ValueError("payload differs from independent reconstruction")
    if files[BIN_NAME] != expected_bundle:
        raise ValueError("binary bundle differs from frozen ROM ranges")
    receipt_files = {JSON_NAME: files[JSON_NAME], BIN_NAME: files[BIN_NAME]}
    if status == "candidate":
        if manifest != _candidate_manifest(expected_payload, receipt_files):
            raise ValueError("candidate manifest differs from independent reconstruction")
        raw, coverage = _read_live_coverage(repository)
        if _sha(raw) != COVERAGE_SHA256:
            raise ValueError("candidate coverage is no longer the frozen baseline")
        analyze_coverage_baseline(coverage)
    else:
        expected_manifest = _accepted_manifest(repository, expected_payload, receipt_files)
        if manifest != expected_manifest:
            raise ValueError("accepted receipt manifest differs from reconstruction")
        expected_claims = expected_coverage_claims(expected_payload, manifest, manifest_sha256=_sha(files[MANIFEST_NAME]))
        _, coverage = _read_live_coverage(repository)
        analyze_live_coverage(coverage, artifact_status="accepted", expected_claims=expected_claims)
    return _verification_report(repository, status=status, payload=expected_payload, bundle=expected_bundle)


def _accept_output_target(root: Path, output: Path | str) -> Path:
    requested = Path(output).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = Path(os.path.abspath(requested))
    scan_base = Path(requested.anchor)
    for candidate in (root, Path(tempfile.gettempdir())):
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
        raise ValueError("accept output must not be repository root or ancestor")
    if target.exists():
        raise ValueError("accept output already exists")
    return target


def accept_candidate(root: Path | str, candidate_dir: Path | str, output_dir: Path | str) -> dict[str, Any]:
    repository = _validate_root(root)
    candidate_report = verify_artifact(repository, candidate_dir)
    if candidate_report.get("artifact_status") != "candidate":
        raise ValueError("acceptance source is not a candidate")
    files = _artifact_files(repository, candidate_dir)
    payload = json.loads(files[JSON_NAME])
    receipt_files = {JSON_NAME: files[JSON_NAME], BIN_NAME: files[BIN_NAME]}
    accepted_manifest = _accepted_manifest(repository, payload, receipt_files)
    accepted_files = {
        JSON_NAME: files[JSON_NAME],
        BIN_NAME: files[BIN_NAME],
        MANIFEST_NAME: _canonical(accepted_manifest),
    }
    target = _accept_output_target(repository, output_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.accept-", dir=target.parent))
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
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    parser.add_argument("--accept-to", type=Path)
    args = parser.parse_args()
    try:
        report = accept_candidate(args.root, args.artifact_dir, args.accept_to) if args.accept_to is not None else verify_artifact(args.root, args.artifact_dir)
    except (OSError, ValueError) as error:
        print(json.dumps({"schema": VERIFY_SCHEMA, "verified": False, "errors": [str(error)]}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
