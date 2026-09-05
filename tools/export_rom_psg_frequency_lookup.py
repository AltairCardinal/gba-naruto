#!/usr/bin/env python3
"""Export the frozen PSG frequency/noise lookup packet from the base ROM.

This packet deliberately promotes only the five byte ranges fixed by the
contract.  Initializer, SoundInfo and trampoline observations are retained as
provenance; they are not silently widened into a global runtime proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any


SCHEMA = "rom-psg-frequency-lookup-v1"
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
UNKNOWN_GAP = (0x09B4C6, 0x09B4C8)

INITIALIZER_CODE_RANGE = (0x09ACF8, 0x09ADC0)
INITIALIZER_CODE_SHA256 = (
    "b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a"
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
    actual = _bounded(rom, offset, offset + len(raw), label)
    if actual != raw:
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


def _producer_denominator(rom: bytes) -> dict[str, Any]:
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


def _initializer_provenance(rom: bytes) -> dict[str, Any]:
    producer_raw = _bounded(rom, 0x09AA56, 0x09AA5A, "initializer producer")
    if producer_raw.hex() != INITIALIZER_PRODUCER["raw_hex"]:
        raise ValueError("initializer producer changed")
    if _sha(producer_raw) != INITIALIZER_PRODUCER["bytes_sha256"]:
        raise ValueError("initializer producer hash changed")
    if _thumb_bl_target(rom, 0x09AA56) != INITIALIZER_PRODUCER["target_file_offset"]:
        raise ValueError("initializer producer target changed")
    code = _bounded(rom, *INITIALIZER_CODE_RANGE, "initializer code")
    if _sha(code) != INITIALIZER_CODE_SHA256:
        raise ValueError("initializer code semantic bytes changed")
    pool = _bounded(rom, *INITIALIZER_LITERAL_POOL_RANGE, "initializer literal pool")
    if _sha(pool) != INITIALIZER_LITERAL_POOL_SHA256:
        raise ValueError("initializer literal pool changed")
    pair = _bounded(rom, *INITIALIZER_BINDING_PAIR_RANGE, "initializer binding")
    if _sha(pair) != INITIALIZER_BINDING_PAIR_SHA256:
        raise ValueError("initializer binding pair changed")
    _expect_bytes(rom, 0x09AD74, bytes.fromhex("2348"), "initializer LDR")
    _expect_bytes(rom, 0x09AD76, bytes.fromhex("2063"), "initializer STR")
    if _u32(rom, 0x09AE04) != ROM_BASE + 0x09B494 + 1:
        raise ValueError("initializer logical SoundInfo pointer changed")
    return {
        "producer": dict(INITIALIZER_PRODUCER),
        "code_range": list(INITIALIZER_CODE_RANGE),
        "code_sha256": INITIALIZER_CODE_SHA256,
        "decoded_instruction_count": 99,
        "decoded_basic_block_count": 4,
        "block_ranges": [
            [0x09ACF8, 0x09AD3A],
            [0x09AD3A, 0x09AD8A],
            [0x09AD8A, 0x09ADB8],
            [0x09ADB8, 0x09ADC0],
        ],
        "external_call_edges": [
            {"source_file_offset": 0x09AD86, "target_file_offset": 0x09C0E0}
        ],
        "frontier_count": 0,
        "cfg_closed": True,
        "return_closed": True,
        "pc_relative_literal_count": 20,
        "literal_pool_range": list(INITIALIZER_LITERAL_POOL_RANGE),
        "literal_pool_sha256": INITIALIZER_LITERAL_POOL_SHA256,
        "binding": {
            "ldr_file_offset": 0x09AD74,
            "ldr_raw_hex": "2348",
            "literal_file_offset": 0x09AE04,
            "pointer": ROM_BASE + 0x09B494 + 1,
            "str_file_offset": 0x09AD76,
            "str_raw_hex": "2063",
            "store": "str r0,[r4,#0x30]",
            "pair_range": list(INITIALIZER_BINDING_PAIR_RANGE),
            "pair_sha256": INITIALIZER_BINDING_PAIR_SHA256,
        },
    }


def _slot_provenance(rom: bytes) -> dict[str, Any]:
    context = _bounded(rom, *SOUNDINFO_CONTEXT_RANGE, "SoundInfo context")
    if _sha(context) != SOUNDINFO_CONTEXT_SHA256:
        raise ValueError("SoundInfo slot context semantic bytes changed")
    chain = _bounded(rom, *SOUNDINFO_CHAIN_RANGE, "SoundInfo chain")
    if _sha(chain) != SOUNDINFO_CHAIN_SHA256:
        raise ValueError("SoundInfo chain semantic bytes changed")
    _expect_bytes(rom, 0x09A71A, bytes.fromhex("7949"), "SoundInfo literal load")
    _expect_bytes(rom, 0x09A71C, bytes.fromhex("0968"), "SoundInfo dereference")
    _expect_bytes(rom, 0x09A71E, bytes.fromhex("0191"), "SoundInfo stack store")
    _expect_bytes(rom, 0x09A8CC, bytes.fromhex("019b"), "SoundInfo reload")
    _expect_bytes(rom, 0x09A8CE, bytes.fromhex("1b6b"), "SoundInfo field load")
    _expect_bytes(rom, 0x09A8D0, bytes.fromhex("fff7d8fe"), "SoundInfo trampoline call")
    if _u32(rom, 0x09A900) != 0x03007FF0:
        raise ValueError("SoundInfo literal value changed")
    expected_branches = [
        {**row, "target_file_offset": 0x09A684}
        for row in DIRECT_TRAMPOLINE_BRANCHES
    ]
    actual_branches: list[dict[str, Any]] = []
    for match in _THUMB_BL_CANDIDATE.finditer(rom):
        offset = match.start()
        if offset & 1 or _thumb_bl_target(rom, offset) != 0x09A684:
            continue
        actual_branches.append(
            {
                "file_offset": offset,
                "raw_hex": rom[offset : offset + 4].hex(),
                "mnemonic": "bl",
                "target_file_offset": 0x09A684,
            }
        )
    if actual_branches != expected_branches:
        raise ValueError("trampoline direct-branch denominator changed")
    _expect_bytes(rom, 0x09A684, bytes.fromhex("1847"), "trampoline")
    if _sha(rom[0x09A684:0x09A686]) != TRAMPOLINE_SHA256:
        raise ValueError("trampoline hash changed")
    return {
        "context_range": list(SOUNDINFO_CONTEXT_RANGE),
        "context_sha256": SOUNDINFO_CONTEXT_SHA256,
        "literal_load": {
            "file_offset": 0x09A71A,
            "raw_hex": "7949",
            "literal_file_offset": 0x09A900,
            "literal_value": 0x03007FF0,
        },
        "dereference": {
            "file_offset": 0x09A71C,
            "raw_hex": "0968",
            "operation": "ldr r1,[r1]",
        },
        "stack_store": {
            "file_offset": 0x09A71E,
            "raw_hex": "0191",
            "operation": "str r1,[sp,#4]",
        },
        "stack_cell_liveness": {
            "cell": "[sp,#4]",
            "overwritten_before_reload": False,
            "sp_adjustment_until_reload": 0,
            "reload_file_offset": 0x09A8CC,
            "reload_raw_hex": "019b",
        },
        "load_and_call": {
            "load_file_offset": 0x09A8CE,
            "load_raw_hex": "1b6b",
            "field_offset": 0x30,
            "call_file_offset": 0x09A8D0,
            "call_raw_hex": "fff7d8fe",
            "trampoline_file_offset": 0x09A684,
        },
        "chain_range": list(SOUNDINFO_CHAIN_RANGE),
        "chain_sha256": SOUNDINFO_CHAIN_SHA256,
        "direct_trampoline_branch_denominator": expected_branches,
        "accepted_slot_path_callsites": [0x09A8D0],
        "trampoline": {
            "range": list(TRAMPOLINE_RANGE),
            "sha256": TRAMPOLINE_SHA256,
            "raw_hex": "1847",
            "operation": "bx r3",
            "existing_owner": {
                "id": "cfg-thumb-0752-09a684",
                "primary_class": "armv4t_cfg_reachable_thumb_code",
                "range": list(TRAMPOLINE_RANGE),
            },
            "promoted": False,
        },
    }


def _consumer_contract(rom: bytes) -> dict[str, Any]:
    first = _bounded(rom, *TARGET_CONSUMER_CODE_RANGES[0], "consumer code A")
    second = _bounded(rom, *TARGET_CONSUMER_CODE_RANGES[1], "consumer code B")
    if _sha(first + second) != TARGET_CONSUMER_CODE_SHA256:
        raise ValueError("consumer CFG semantic bytes changed")
    _expect_bytes(rom, 0x09B4BE, bytes.fromhex("0248"), "consumer noise literal load")
    _expect_bytes(rom, 0x09B52E, bytes.fromhex("f0bc02bc0847"), "consumer return")
    return {
        "root_file_offset": 0x09B494,
        "code_bytes": 154,
        "code_sha256": TARGET_CONSUMER_CODE_SHA256,
        "decoded_instruction_count": 77,
        "decoded_basic_block_count": 12,
        "code_ranges": [list(pair) for pair in TARGET_CONSUMER_CODE_RANGES],
        "block_ranges": [list(pair) for pair in TARGET_CONSUMER_BLOCK_RANGES],
        "internal_edge_count": 16,
        "external_call_edges": [],
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


def _literal_bindings(rom: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for expected in CONSUMED_LITERAL_BINDINGS:
        offset = expected["load_file_offset"]
        raw = _bounded(rom, offset, offset + 2, "consumer literal load")
        if raw.hex() != expected["load_raw_hex"]:
            raise ValueError("consumer literal load changed")
        instruction = int.from_bytes(raw, "little")
        literal = (((ROM_BASE + offset + 4) & ~3) + (instruction & 0xFF) * 4) - ROM_BASE
        if literal != expected["literal_range"][0]:
            raise ValueError("consumer literal address changed")
        pointer = _u32(rom, literal)
        if pointer != expected["pointer"]:
            raise ValueError("consumer literal pointer changed")
        occurrences = _pointer_occurrences(rom, pointer)
        if occurrences != expected["pointer_occurrences"]:
            raise ValueError("consumer literal pointer occurrence changed")
        rows.append(dict(expected))
    return rows


def analyze_noise_table(raw: bytes) -> dict[str, Any]:
    if len(raw) != 60:
        raise ValueError("noise table must contain 60 bytes")
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
            raw_range = segment.get("range") if isinstance(segment, dict) else None
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
                raise ValueError("coverage baseline has a gap or overlap inside a promotion range")
            size = right - left
            if segment.get("primary_class") == "unknown" and segment.get("primary_claim_ids") in (None, []):
                unknown_bytes += size
            else:
                overlap_bytes += size
            cursor = right
        if cursor != promotion_end:
            raise ValueError("coverage baseline does not cover a promotion range")
    if overlap_bytes or unknown_bytes != 226:
        raise ValueError("coverage baseline unknown/overlap contract changed")
    return _frozen_coverage_baseline()


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


def _build_payload_from_rom(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    promotion_ranges = [list(pair) for pair in PROMOTION_RANGES]
    bundle = b"".join(_bounded(rom, start, end, "promotion range") for start, end in PROMOTION_RANGES)
    if len(bundle) != 226 or _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion bundle identity changed")
    if _sha(_canonical(promotion_ranges)) != PROMOTION_RANGE_VECTOR_SHA256:
        raise ValueError("promotion range vector receipt identity changed")
    semantic_ranges = [dict(row) for row in SEMANTIC_RANGE_SPECS]
    if _sha(_canonical(semantic_ranges)) != SEMANTIC_RANGE_VECTOR_SHA256:
        raise ValueError("semantic range vector receipt identity changed")
    for index, (start, end) in enumerate(PROMOTION_RANGES):
        if _sha(_bounded(rom, start, end, "semantic range")) != PROMOTION_RANGE_SHA256[index]:
            raise ValueError("semantic promotion range bytes changed")
    producer = _producer_denominator(rom)
    initializer = _initializer_provenance(rom)
    slot = _slot_provenance(rom)
    consumer = _consumer_contract(rom)
    literals = _literal_bindings(rom)
    table = analyze_noise_table(_bounded(rom, 0x46475C, 0x464798, "noise table"))
    table.update({"range": [0x46475C, 0x464798], "sha256": PROMOTION_RANGE_SHA256[4]})
    lookup = {
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
    }
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "coverage_baseline": _coverage_baseline(root),
        "promotion": {
            "ranges": promotion_ranges,
            "range_count": 5,
            "byte_count": 226,
            "range_vector_sha256": PROMOTION_RANGE_VECTOR_SHA256,
            "packed_bytes_sha256": PACKED_SHA256,
            "semantic_ranges": semantic_ranges,
            "semantic_range_vector_sha256": SEMANTIC_RANGE_VECTOR_SHA256,
        },
        "producer_denominator": producer,
        "provenance": {"initializer": initializer, "soundinfo_slot": slot},
        "consumer": consumer,
        "literal_bindings": literals,
        "table": table,
        "lookup": lookup,
        "scope": dict(SCOPE),
        "limitations": [PSG_COVERAGE_LIMITATION],
    }
    return payload, bundle


def build_payload(root: Path | str) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    rom = _safe_file(repository, ROM_PATH).read_bytes()
    return _build_payload_from_rom(repository, rom)


def rebuild_from_rom(root: Path | str, rom: bytes) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    return _build_payload_from_rom(repository, rom)


def _reject_symlink_components(path: Path, root: Path | None = None) -> Path:
    requested = Path(os.path.abspath(path.expanduser()))
    scan_base = Path(requested.anchor)
    for candidate in (root, Path(tempfile.gettempdir())):
        if candidate is None:
            continue
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


def _validate_output(root: Path, output: Path | str) -> Path:
    requested = Path(output).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested, root)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("artifact output must not be repository root or ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("artifact output is not a directory")
        members = list(target.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact output directory contains a symlink")
        if any(member.is_dir() for member in members):
            raise ValueError("foreign artifact output directory")
        names = {member.relative_to(target).as_posix() for member in members if member.is_file()}
        if names:
            expected = {"manifest.json", "rom-psg-frequency-lookup.json", "rom-psg-frequency-lookup.bin"}
            if names != expected:
                raise ValueError("foreign artifact output directory")
    return target


def _file_receipts(files: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    return {
        name: {"size": len(files[name]), "sha256": _sha(files[name])}
        for name in sorted(files)
    }


def _candidate_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "candidate",
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "promotion": payload["promotion"],
        "scope": payload["scope"],
        "limitations": payload["limitations"],
        "files": _file_receipts(files),
    }


def _replace_output(target: Path, files: dict[str, bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def write_artifact(root: Path | str, output: Path | str) -> dict[str, Any]:
    repository = _validate_root(root)
    target = _validate_output(repository, output)
    payload, bundle = build_payload(repository)
    files = {
        "rom-psg-frequency-lookup.json": _canonical(payload),
        "rom-psg-frequency-lookup.bin": bundle,
    }
    files["manifest.json"] = _canonical(_candidate_manifest(payload, files))
    _replace_output(target, files)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    try:
        payload = write_artifact(args.root, args.output_dir)
    except (OSError, ValueError) as error:
        print(json.dumps({"schema": SCHEMA, "verified": False, "errors": [str(error)]}, sort_keys=True))
        return 1
    print(json.dumps(payload["promotion"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
