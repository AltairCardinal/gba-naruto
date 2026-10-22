#!/usr/bin/env python3
"""Independently verify the frozen u8-indexed u8-triplet lookup candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


SCHEMA = "rom-u8-indexed-u8-triplet-lookup-v1"
VERIFY_SCHEMA = "rom-u8-indexed-u8-triplet-lookup-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
JSON_NAME = "rom-u8-indexed-u8-triplet-lookup.json"
BIN_NAME = "rom-u8-indexed-u8-triplet-lookup.bin"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
EXPERIMENT_ROOT = Path("build/experiments/active/rom-u8-indexed-u8-triplet-lookup")
ARTIFACT_RELATIVE = Path("artifacts/rom-u8-indexed-u8-triplet-lookup-v1")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SIZE = 23_020_449
COVERAGE_SHA256 = "5432e12ff0aa9bd2722f7e18e169ac0d82d67f6a1afd4601a8d0011e502eba89"
COVERAGE_BASELINE_CLAIMS_SHA256 = "764c56f124572bcf0a88a5a8b7fab7fd519c83f01b51d280abe71e6e148d1bac"
COVERAGE_BASELINE_SEGMENTS_SHA256 = "7912231dc77663aefe52df6d99beeffafba082bb1ddba081a047c6d5187dc8dd"
COVERAGE_BASELINE_SUMMARY_SHA256 = "1e18399bf112fdf712a346c419415603b3b4da3dbe40cece9161e73e437de39e"
COVERAGE_BASELINE_LIMITATIONS_SHA256 = "ba0ceefa0cf07c11a3163aa2ebbbb7fe54b56cfd0a21598bffbd24a85eb7d3df"
COVERAGE_INVARIANT_TOP_SHA256 = "af4304b2ac0ce0558eceb97218a4ba6881878de9c6d2fa0e24098178654fb6ca"
COVERAGE_POST_SEGMENTS_SHA256 = "66800eb89254d07e1eeba23d7b14ecc763bfcd888f13072560d777400759b31d"
COVERAGE_POST_SUMMARY_SHA256 = "3aaa7f345d1b49a9db140c55e7dfdc3aecc6a54a1ed346bbed5af9ab84135018"
COVERAGE_POST_LIMITATIONS_SHA256 = "768236648c3f6eb45677715fb62eda7cec6b5c3bedec79a76e1767dc1950f656"
COVERAGE_DYNAMIC_KEYS = {"claims", "segments", "summary", "limitations"}
COVERAGE_LIMITATION = (
    "The u8-indexed u8-triplet lookup artifact classifies exactly 19 "
    "current-unknown bytes: one consumed four-byte pointer literal and one "
    "fifteen-byte five-by-three raw u8 record table. The 272 consumer code "
    "bytes retain their existing generic CFG owners and are provenance only; "
    "four literal pools and the right-hand diagnostic range remain unknown. "
    "The frozen static r5=0..4 and 3*i field-load binding does not prove a "
    "newly closed CFG, return epilogue, natural runtime reachability, business "
    "field semantics, editing, relocation, or allocatable space."
)

TABLE_START = 0x53DFB0
TABLE_END = 0x53DFBF
TABLE_SHA256 = "d9f09635484acda7178a3c3661cacb5857338798c5dd87058fe5c7d8a17c3ef3"
TABLE_RAW_HEX = "09080a09050b0c0c0d10101110ff12"
TABLE_RECORD_COUNT = 5
TABLE_RECORD_SIZE = 3
TABLE_INDEX_DOMAIN = [0, 4]
TABLE_FIELD_OFFSETS = [0, 1, 2]
RIGHT_UNKNOWN_RANGE = [0x53DFBF, 0x53E000]
RIGHT_UNKNOWN_SHA256 = "3649f772a191366cf911ca8eb6b9e28e902a79e4a19607a5ac340cd64d818849"

POINTER_START = 0x075C0C
POINTER_END = 0x075C10
POINTER_RAW = bytes.fromhex("b0df5308")
POINTER_VALUE = 0x0853DFB0
POINTER_SHA256 = "94ed1b299bbef8b78e0b6e7e6afab5cec9dada3516e48cf04e104ccdd689262e"
POINTER_OCCURRENCES = [POINTER_START]
POINTER_OCCURRENCE_VECTOR_SHA256 = "ce055d1c77a9bf59940c7f367a1c66973425d7a2c7c95782150fc261f9af159a"

CONSUMER_ROOT = 0x075BD2
CONSUMER_END = 0x075D10
CONSUMER_ENVELOPE_SHA256 = "00ad2e10053d53e5d4f96d28fc2f327a4bf6d143ad44718ff84195d246263d6b"
CODE_RANGES = [
    [0x075BD2, 0x075BFE],
    [0x075C10, 0x075C5E],
    [0x075C68, 0x075C98],
    [0x075CA4, 0x075CB6],
    [0x075CBC, 0x075D10],
]
CODE_RANGE_SHA256 = [
    "78d7f801e92e99be865b441e4255c2e094c26c0e706edce9832151a8e1ae1c80",
    "ddb47ef7f74fbfeba0ce22c798b33e745233aad5468ddc904687c702799ded8d",
    "a49efe8fb40580dcd7a47fac9493b674a65c41feb3fcdc164d2a715847440394",
    "e6c57fcfbca9954be08edd2044b0d2d680d880d76443603c6186b3ee82a34357",
    "a1efd81c3f82b685a916eb70c2985c6bcef4d3674eeed39423d058787aa61be3",
]
CODE_RANGE_HEX = [
    "00250d4c49460e78680042191119031c09788e4200d08be0601c10180178ff290dd04a46507888420fd081e0",
    "49464878802874d9912872d804aa5819a11c40180078107005a90120087001220c920025079885426bd2094e4a4651190a78802010400c1c00280dd12078089a511909785246034bf7f700fe0ae0",
    "7f20104051460a4af7f74efe0949e1229200881800788c4602280fd1c821490061440548604400880a88801808802de0",
    "012809d10348604400783178401830701ee0",
    "052819d120787f210140081c0e380006000e022810d9081c1c380006000e02280ad9081c1f380006000e052804d9cb204000604428180170681c0006050e079a95429dd307e0681c0006050e042d00d865e700e0",
]
CODE_BYTE_SIZE = 272
CODE_SHA256 = "203f476edad477eb359e84d625ca079f2a7aba161e5f2a2266c83cc31f3e6529"
BLOCK_RANGES = [
    [0x075BD2, 0x075BDA], [0x075BDA, 0x075BE8], [0x075BE8, 0x075BEA],
    [0x075BEA, 0x075BF4], [0x075BF4, 0x075BFC], [0x075BFC, 0x075BFE],
    [0x075C10, 0x075C18], [0x075C18, 0x075C1C], [0x075C1C, 0x075C3A],
    [0x075C3A, 0x075C3C], [0x075C3C, 0x075C4C], [0x075C4C, 0x075C5C],
    [0x075C5C, 0x075C5E], [0x075C68, 0x075C74], [0x075C74, 0x075C84],
    [0x075C84, 0x075C98], [0x075CA4, 0x075CA8], [0x075CA8, 0x075CB6],
    [0x075CBC, 0x075CC0], [0x075CC0, 0x075CD2], [0x075CD2, 0x075CDE],
    [0x075CDE, 0x075CEA], [0x075CEA, 0x075CF4], [0x075CF4, 0x075D00],
    [0x075D00, 0x075D02], [0x075D02, 0x075D0C], [0x075D0C, 0x075D0E],
    [0x075D0E, 0x075D10],
]
BLOCK_VECTOR_SHA256 = "91225206f466857eae0f8e6d6718b1c7020dcd824344793cf2e8ba79944afe5d"
INSTRUCTION_COUNT = 134
BLOCK_COUNT = 28
FRONTIER_COUNT = 0
SEMANTIC_VECTOR_SHA256 = "08d4f11aafdc6f1a6dc020c4f4f6a637d0a2507f1ad8464bf1aa1f28d2026b4c"
POOL_RANGES = [
    [0x075BFE, 0x075C10], [0x075C5E, 0x075C68],
    [0x075C98, 0x075CA4], [0x075CB6, 0x075CBC],
]
PROMOTION_RANGES = [[POINTER_START, POINTER_END], [TABLE_START, TABLE_END]]
PROMOTION_RANGE_VECTOR_SHA256 = "99af22b0af2f42931bb29c3cbe187ff8836b1f651504eea40a45eb5be108d87f"
PROMOTION_PACKED_SHA256 = "4439669abd06a2c350f23e705c750821694c15e2f92a083bc00c89ab7506dcc6"

EXPECTED_HALFWORDS = {
    0x075BD2: 0x2500, 0x075BD4: 0x4C0D, 0x075BD8: 0x780E,
    0x075BDA: 0x0068, 0x075BDC: 0x1942, 0x075BDE: 0x1911,
    0x075BE0: 0x1C03, 0x075BE2: 0x7809, 0x075BEA: 0x1C60,
    0x075BEC: 0x1810, 0x075BEE: 0x7801, 0x075BF0: 0x29FF,
    0x075BF2: 0xD00D, 0x075BF6: 0x7850, 0x075BF8: 0x4288,
    0x075BFA: 0xD00F, 0x075C10: 0x4649, 0x075C12: 0x7848,
    0x075C14: 0x2880, 0x075C16: 0xD974, 0x075C18: 0x2891,
    0x075C1A: 0xD872, 0x075C1E: 0x1958, 0x075C20: 0x1CA1,
    0x075C22: 0x1840, 0x075C24: 0x7800, 0x075C58: 0xF7F7,
    0x075C5A: 0xFE00, 0x075C70: 0xF7F7, 0x075C72: 0xFE4E,
    0x075D02: 0x1C68, 0x075D04: 0x0600, 0x075D06: 0x0E05,
    0x075D08: 0x2D04, 0x075D0A: 0xD800, 0x075D0C: 0xE765,
    0x075D0E: 0xE000,
}
CFG_OWNER_CLAIMS = {
    "cfg-thumb-0371-075abc": ([0x075ABC, 0x075BFE], "armv4t_cfg_reachable_thumb_code"),
    "cfg-thumb-0372-075c10": ([0x075C10, 0x075C5E], "armv4t_cfg_reachable_thumb_code"),
    "cfg-thumb-0373-075c68": ([0x075C68, 0x075C98], "armv4t_cfg_reachable_thumb_code"),
    "cfg-thumb-0374-075ca4": ([0x075CA4, 0x075CB6], "armv4t_cfg_reachable_thumb_code"),
    "cfg-thumb-0375-075cbc": ([0x075CBC, 0x075D5C], "armv4t_cfg_reachable_thumb_code"),
}
NON_CLAIMS = {
    "complete_80_byte_object": False,
    "natural_runtime_reachability_complete": False,
    "business_field_semantics_complete": False,
    "all_consumers_and_producers_exhausted": False,
    "computed_ram_or_indirect_consumers_exhausted": False,
    "cutscene_id_relationship": False,
    "right_gap_structure_or_padding": False,
    "editing_writeback_relocation_safety": False,
    "free_or_allocatable_space": False,
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _validate_root(root: Path) -> Path:
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
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var"), Path("/private/tmp")}:
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    paths = {
        "exporter": Path("tools/export_rom_u8_indexed_u8_triplet_lookup.py"),
        "verifier": Path("tools/verify_rom_u8_indexed_u8_triplet_lookup.py"),
        "exporter_tests": Path("tests/test_export_rom_u8_indexed_u8_triplet_lookup.py"),
        "verifier_tests": Path("tests/test_verify_rom_u8_indexed_u8_triplet_lookup.py"),
    }
    return {
        role: {"path": relative.as_posix(), "sha256": _sha(_safe_file(root, relative).read_bytes())}
        for role, relative in paths.items()
    }


def _slice(raw: bytes, start: int, end: int, expected: str, label: str) -> bytes:
    if start < 0 or end < start or end > len(raw):
        raise ValueError(f"{label} range escapes ROM")
    value = raw[start:end]
    if _sha(value) != expected:
        raise ValueError(f"{label} bytes changed")
    return value


def _u16(raw: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(raw):
        raise ValueError("Thumb halfword escapes ROM")
    return int.from_bytes(raw[offset : offset + 2], "little")


def _u32(raw: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(raw):
        raise ValueError("literal word escapes ROM")
    return int.from_bytes(raw[offset : offset + 4], "little")


def _expect16(raw: bytes, offset: int, expected: int, label: str) -> int:
    actual = _u16(raw, offset)
    if actual != expected:
        raise ValueError(f"{label} changed: expected 0x{expected:04X}, got 0x{actual:04X}")
    return actual


def _scan_pointer_occurrences(raw: bytes) -> list[int]:
    return [offset for offset in range(len(raw) - 3) if raw[offset : offset + 4] == POINTER_RAW]


def _decode_ldr_literal(raw: bytes) -> dict[str, Any]:
    if POINTER_VALUE != ROM_BASE + TABLE_START:
        raise ValueError("consumer pointer no longer binds the exact table start")
    instruction = _expect16(raw, 0x075BD4, 0x4C0D, "consumer pointer LDR")
    if instruction & 0xF800 != 0x4800:
        raise ValueError("consumer pointer instruction is not a Thumb PC-relative LDR")
    literal_offset = ((0x075BD4 + 4) & ~3) + (instruction & 0xFF) * 4
    if literal_offset != POINTER_START or _u32(raw, literal_offset) != POINTER_VALUE:
        raise ValueError("consumer pointer LDR resolution changed")
    return {
        "file_offset": 0x075BD4,
        "gba_address": _addr(0x075BD4),
        "halfword": instruction,
        "raw_hex": raw[0x075BD4 : 0x075BD6].hex(),
        "literal_file_offset": literal_offset,
        "literal_gba_address": _addr(literal_offset),
        "literal_value": POINTER_VALUE,
        "literal_raw_hex": POINTER_RAW.hex(),
    }


def _branch_target(offset: int, halfword: int) -> int:
    if halfword & 0xF800 == 0xE000:
        immediate = halfword & 0x07FF
        if immediate & 0x0400:
            immediate -= 0x0800
        return offset + 4 + immediate * 2
    if halfword & 0xF000 == 0xD000 and (halfword & 0x0F00) != 0x0F00:
        immediate = halfword & 0xFF
        if immediate & 0x80:
            immediate -= 0x100
        return offset + 4 + immediate * 2
    raise ValueError(f"unsupported branch at 0x{offset:06X}")


def _decode_thumb_bl(raw: bytes, offset: int) -> int:
    first = _u16(raw, offset)
    second = _u16(raw, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"expected Thumb BL at 0x{offset:06X}")
    sign = (first >> 10) & 1
    i1 = ((second >> 13) & 1) ^ 1 ^ sign
    i2 = ((second >> 11) & 1) ^ 1 ^ sign
    immediate = (sign << 24) | (i1 << 23) | (i2 << 22) | ((first & 0x03FF) << 12) | ((second & 0x07FF) << 1)
    if sign:
        immediate -= 1 << 25
    return offset + 4 + immediate


def _instruction_vector(raw: bytes) -> list[list[Any]]:
    vector: list[list[Any]] = []
    for start, end in CODE_RANGES:
        offset = start
        while offset < end:
            first = _u16(raw, offset)
            size = 4 if first & 0xF800 == 0xF000 and offset + 4 <= end and _u16(raw, offset + 2) & 0xF800 == 0xF800 else 2
            vector.append([offset, size, raw[offset : offset + size].hex()])
            offset += size
    return vector


def _validate_code(raw: bytes) -> tuple[dict[str, Any], list[list[int]]]:
    code_bytes = bytearray()
    ranges = []
    for (start, end), expected_sha, expected_hex in zip(CODE_RANGES, CODE_RANGE_SHA256, CODE_RANGE_HEX):
        value = _slice(raw, start, end, expected_sha, f"consumer code range 0x{start:06X}")
        if value.hex() != expected_hex:
            raise ValueError(f"consumer semantic bytes changed at 0x{start:06X}")
        code_bytes.extend(value)
        ranges.append({"file_range": [start, end], "gba_range": [_addr(start), _addr(end)], "byte_size": len(value), "sha256": _sha(value)})
    if len(code_bytes) != CODE_BYTE_SIZE or _sha(bytes(code_bytes)) != CODE_SHA256:
        raise ValueError("consumer code union changed")
    vector = _instruction_vector(raw)
    if len(vector) != INSTRUCTION_COUNT or _sha(_compact(vector)) != SEMANTIC_VECTOR_SHA256:
        raise ValueError("consumer semantic instruction vector changed")
    for offset, expected in EXPECTED_HALFWORDS.items():
        _expect16(raw, offset, expected, f"consumer semantic instruction 0x{offset:06X}")
    if _branch_target(0x075D0C, _u16(raw, 0x075D0C)) != 0x075BDA:
        raise ValueError("consumer index back-edge changed")
    if _branch_target(0x075D0A, _u16(raw, 0x075D0A)) != 0x075D0E:
        raise ValueError("consumer index exit branch changed")
    if _branch_target(0x075D0E, _u16(raw, 0x075D0E)) != 0x075D12:
        raise ValueError("consumer structured return target changed")
    external = []
    for callsite, target in ((0x075C58, 0x06D85C), (0x075C70, 0x06D910)):
        if _decode_thumb_bl(raw, callsite) != target:
            raise ValueError(f"consumer external call target changed at 0x{callsite:06X}")
        external.append([callsite, target])
    if _sha(_compact(BLOCK_RANGES)) != BLOCK_VECTOR_SHA256:
        raise ValueError("consumer block vector constant changed")
    return {
        "root_file_offset": CONSUMER_ROOT,
        "root_gba_address": _addr(CONSUMER_ROOT),
        "mode": "thumb",
        "envelope": {"file_range": [CONSUMER_ROOT, CONSUMER_END], "gba_range": [_addr(CONSUMER_ROOT), _addr(CONSUMER_END)], "byte_size": CONSUMER_END - CONSUMER_ROOT, "sha256": _sha(_slice(raw, CONSUMER_ROOT, CONSUMER_END, CONSUMER_ENVELOPE_SHA256, "consumer envelope"))},
        "code_ranges": ranges,
        "code_byte_size": CODE_BYTE_SIZE,
        "code_sha256": CODE_SHA256,
        "block_ranges": BLOCK_RANGES,
        "block_count": BLOCK_COUNT,
        "instruction_count": INSTRUCTION_COUNT,
        "frontier_count": FRONTIER_COUNT,
        "block_vector_sha256": BLOCK_VECTOR_SHA256,
        "semantic_instruction_vector_sha256": SEMANTIC_VECTOR_SHA256,
        "excluded_pool_ranges": POOL_RANGES,
    }, external


def _range_unknown(coverage: dict[str, Any], start: int, end: int) -> bool:
    cursor = start
    segments = sorted(coverage.get("segments", []), key=lambda item: item.get("range", [0, 0])[0])
    while cursor < end:
        matching = [s for s in segments if s.get("range", [0, 0])[0] <= cursor < s.get("range", [0, 0])[1]]
        if len(matching) != 1:
            return False
        segment = matching[0]
        if segment.get("primary_class") != "unknown" or segment.get("primary_claim_ids") != [] or segment.get("secondary_claim_ids") != []:
            return False
        cursor = min(end, segment["range"][1])
    return cursor == end


def _frozen_coverage_baseline() -> dict[str, Any]:
    return {
        "path": COVERAGE_PATH.as_posix(),
        "schema": "rom-byte-coverage-v1",
        "size": COVERAGE_SIZE,
        "sha256": COVERAGE_SHA256,
        "current_unknown_only": True,
        "existing_cfg_owner_reused": True,
        "expected_delta": {
            "classified": 19,
            "unknown": -19,
            "claims": 2,
            "segments": 2,
        },
    }


def _coverage_contract(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if len(raw) != COVERAGE_SIZE or _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    coverage = json.loads(raw.decode("utf-8"))
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    if coverage.get("base_rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
        raise ValueError("coverage baseline ROM identity changed")
    summary = coverage.get("summary", {})
    expected_summary = {
        "classified_bytes": 6_121_850,
        "unknown_bytes": 169_606,
        "claim_count": 14_476,
        "segment_count": 16_589,
    }
    if {key: summary.get(key) for key in expected_summary} != expected_summary:
        raise ValueError("coverage baseline summary changed")
    for start, end in PROMOTION_RANGES + [RIGHT_UNKNOWN_RANGE] + POOL_RANGES:
        if not _range_unknown(coverage, start, end):
            raise ValueError(f"coverage range is not current unknown: 0x{start:06X}-0x{end:06X}")
    claims = {claim.get("id"): claim for claim in coverage.get("claims", [])}
    for claim_id, (expected_range, expected_class) in CFG_OWNER_CLAIMS.items():
        claim = claims.get(claim_id)
        if not isinstance(claim, dict) or claim.get("range") != expected_range or claim.get("role") != "primary" or claim.get("primary_class") != expected_class:
            raise ValueError(f"existing CFG owner changed: {claim_id}")
    return _frozen_coverage_baseline()


def _read_live_coverage(root: Path) -> tuple[bytes, dict[str, Any]]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    try:
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("live coverage is not valid JSON") from error
    if not isinstance(coverage, dict) or raw != _canonical(coverage):
        raise ValueError("live coverage is not canonical JSON")
    return raw, coverage


def _check_coverage_partition(
    coverage: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    summary = coverage.get("summary")
    limitations = coverage.get("limitations")
    if (
        not isinstance(segments, list)
        or not isinstance(claims, list)
        or not isinstance(summary, dict)
        or not isinstance(limitations, list)
    ):
        raise ValueError("coverage claims, segments, summary, or limitations are absent")
    cursor = 0
    classified = 0
    unknown = 0
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("coverage segment is not an object")
        interval = segment.get("range")
        if (
            not isinstance(interval, list)
            or len(interval) != 2
            or not all(isinstance(value, int) for value in interval)
        ):
            raise ValueError("coverage segment range changed")
        start, end = interval
        if start != cursor or end <= start or end > ROM_SIZE:
            raise ValueError("coverage segments do not form an exact ROM partition")
        if segment.get("primary_class") == "unknown":
            unknown += end - start
        else:
            classified += end - start
        cursor = end
    if cursor != ROM_SIZE:
        raise ValueError("coverage segments do not cover the full ROM")
    if (
        summary.get("claim_count") != len(claims)
        or summary.get("segment_count") != len(segments)
        or summary.get("classified_bytes") != classified
        or summary.get("unknown_bytes") != unknown
        or summary.get("accounted_bytes") != ROM_SIZE
        or classified + unknown != ROM_SIZE
    ):
        raise ValueError("coverage summary/count/classified/unknown totals are inconsistent")
    return segments, claims, summary


def _table_contract(raw: bytes) -> dict[str, Any]:
    table = _slice(raw, TABLE_START, TABLE_END, TABLE_SHA256, "triplet table")
    if table.hex() != TABLE_RAW_HEX:
        raise ValueError("triplet table bytes changed")
    records = []
    for index in range(TABLE_RECORD_COUNT):
        start = TABLE_START + index * TABLE_RECORD_SIZE
        row = raw[start : start + TABLE_RECORD_SIZE]
        records.append({"index": index, "file_range": [start, start + TABLE_RECORD_SIZE], "gba_range": [_addr(start), _addr(start + TABLE_RECORD_SIZE)], "byte_size": TABLE_RECORD_SIZE, "raw_hex": row.hex(), "sha256": _sha(row), "fields_u8": list(row)})
    right = _slice(raw, RIGHT_UNKNOWN_RANGE[0], RIGHT_UNKNOWN_RANGE[1], RIGHT_UNKNOWN_SHA256, "right diagnostic range")
    return {"file_range": [TABLE_START, TABLE_END], "gba_range": [_addr(TABLE_START), _addr(TABLE_END)], "byte_size": len(table), "byte_sha256": _sha(table), "raw_hex": table.hex(), "record_count": TABLE_RECORD_COUNT, "record_size": TABLE_RECORD_SIZE, "index_domain": TABLE_INDEX_DOMAIN, "stride_bytes": TABLE_RECORD_SIZE, "field_offsets": TABLE_FIELD_OFFSETS, "records": records, "right_unknown_range": RIGHT_UNKNOWN_RANGE, "right_unknown_gba_range": [_addr(RIGHT_UNKNOWN_RANGE[0]), _addr(RIGHT_UNKNOWN_RANGE[1])], "right_unknown_sha256": _sha(right)}


def _pointer_contract(raw: bytes) -> dict[str, Any]:
    literal = _slice(raw, POINTER_START, POINTER_END, POINTER_SHA256, "triplet pointer literal")
    if literal != POINTER_RAW:
        raise ValueError("triplet pointer literal bytes changed")
    occurrences = _scan_pointer_occurrences(raw)
    if occurrences != POINTER_OCCURRENCES:
        raise ValueError("triplet pointer occurrence denominator changed")
    compact = _compact(occurrences)
    if _sha(compact) != POINTER_OCCURRENCE_VECTOR_SHA256:
        raise ValueError("triplet pointer occurrence vector changed")
    load = _decode_ldr_literal(raw)
    return {"literal_file_range": [POINTER_START, POINTER_END], "literal_gba_range": [_addr(POINTER_START), _addr(POINTER_END)], "raw_hex": literal.hex(), "value": int.from_bytes(literal, "little"), "sha256": _sha(literal), "full_rom_occurrences": occurrences, "occurrence_count": len(occurrences), "occurrence_vector_sha256": _sha(compact), "load_instruction": load, "raw_occurrence_vector_sha256": _sha(b"".join(raw[offset : offset + 4] for offset in occurrences))}


def _promotion(raw: bytes) -> tuple[dict[str, Any], bytes]:
    packed = raw[POINTER_START:POINTER_END] + raw[TABLE_START:TABLE_END]
    if _sha(_compact(PROMOTION_RANGES)) != PROMOTION_RANGE_VECTOR_SHA256 or _sha(packed) != PROMOTION_PACKED_SHA256:
        raise ValueError("promotion input identity changed")
    claims = [
        {"id": "fixed-consumer-triplet-pointer-literal", "claim_kind": "fixed_consumer_triplet_pointer_literal_bytes", "primary_class": "fixed_consumer_triplet_pointer_literal", "range": [POINTER_START, POINTER_END], "byte_size": POINTER_END - POINTER_START, "sha256": _sha(raw[POINTER_START:POINTER_END]), "promoted_from_primary_class": "unknown"},
        {"id": "fixed-consumer-triplet-records", "claim_kind": "fixed_consumer_triplet_record_bytes", "primary_class": "fixed_consumer_triplet_table", "range": [TABLE_START, TABLE_END], "byte_size": TABLE_END - TABLE_START, "sha256": _sha(raw[TABLE_START:TABLE_END]), "promoted_from_primary_class": "unknown"},
    ]
    return {"range_order": "file_offset_ascending", "ranges": PROMOTION_RANGES, "byte_size": len(packed), "range_vector_sha256": PROMOTION_RANGE_VECTOR_SHA256, "packed_sha256": PROMOTION_PACKED_SHA256, "claims": claims}, packed


def _expected_payload(
    root: Path,
    raw: bytes,
    *,
    validate_live_baseline: bool,
) -> tuple[dict[str, Any], bytes]:
    if len(raw) != ROM_SIZE or _sha(raw) != ROM_SHA256:
        raise ValueError("ROM identity changed")
    coverage = (
        _coverage_contract(root)
        if validate_live_baseline
        else _frozen_coverage_baseline()
    )
    table = _table_contract(raw)
    pointer = _pointer_contract(raw)
    consumer, external_calls = _validate_code(raw)
    promotion, packed = _promotion(raw)
    scope = {"table_records_complete": True, "static_index_formula_complete": True, "pointer_occurrence_denominator_complete": True, "consumer_code_is_existing_cfg_provenance": True, "promotion_current_unknown_only": True, "natural_runtime_reachability_complete": False, "business_field_semantics_complete": False, "complete_80_byte_object": False, "right_gap_claimed": False, "literal_pools_claimed": False, "code_repromoted": False}
    coverage_projection = {"baseline": coverage, "promoted_ranges": PROMOTION_RANGES, "promoted_byte_size": 19, "expected_delta": {"classified": 19, "unknown": -19, "claims": 2, "segments": 2}, "current_unknown_only": True, "code_repromotion": False, "literal_pools_claimed": False, "right_gap_claimed": False}
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(raw), "sha256": ROM_SHA256},
        "coverage_baseline": coverage,
        "coverage_projection": coverage_projection,
        "table": table,
        "pointer_binding": pointer,
        "consumer": consumer,
        "index_formula": {"index_register": "r5", "initial_value": 0, "expression": "2*i+i", "stride_bytes": 3, "index_domain": [0, 4], "field_offsets": [0, 1, 2], "field_width": "u8", "literal_load": {"file_offset": 0x075BD4, "halfword": 0x4C0D, "literal_file_offset": POINTER_START}, "increment_u8_truncation": [0x075D02, 0x075D04, 0x075D06], "bound_compare": {"file_offset": 0x075D08, "immediate": 4}, "back_edge": [0x075D0C, 0x075BDA], "wildcard_field1_value": 0xFF, "wildcard_range": {"lower_exclusive": 0x80, "upper_inclusive": 0x91}},
        "external_calls": external_calls,
        "structured_return_target": 0x075D12,
        "excluded_ranges": {"literal_pools": POOL_RANGES, "right_unknown": RIGHT_UNKNOWN_RANGE},
        "promotion": promotion,
        "scope": scope,
        "non_claims": NON_CLAIMS,
        "limitations": ["Only the four-byte consumed pointer literal and fifteen table bytes are candidate promotion ranges.", "The 272 consumer code bytes remain owned by the existing generic CFG and are provenance only.", "Literal pools and the right-hand diagnostic range remain unknown.", "The index domain is a static bounded-loop fact, not natural runtime coverage.", "No business, cutscene, PSG, editing, relocation, writeback, or free-space semantics are claimed."],
        "implementation": _implementation(root),
    }
    return payload, packed


def rebuild_from_rom(
    root: Path,
    rom: bytes,
    *,
    validate_live_baseline: bool = True,
) -> tuple[dict[str, Any], bytes]:
    return _expected_payload(
        _validate_root(root),
        rom,
        validate_live_baseline=validate_live_baseline,
    )


def rebuild_payload(
    root: Path,
    *,
    validate_live_baseline: bool = True,
) -> tuple[dict[str, Any], bytes]:
    root = _validate_root(root)
    return rebuild_from_rom(
        root,
        _safe_file(root, ROM_PATH).read_bytes(),
        validate_live_baseline=validate_live_baseline,
    )


def verify_payload(root: Path, payload: dict[str, Any], bundle: bytes) -> dict[str, Any]:
    root = _validate_root(root)
    expected, expected_bundle = rebuild_payload(root)
    if payload != expected:
        raise ValueError("payload differs from independent reconstruction")
    if bundle != expected_bundle:
        raise ValueError("bundle differs from independent reconstruction")
    return _report(root, expected, _sha(_canonical(payload)), _sha(bundle))


def _artifact_path(root: Path, artifact_dir: Path) -> Path:
    requested = Path(artifact_dir).expanduser()
    if not requested.is_absolute():
        if ".." in requested.parts:
            raise ValueError("artifact path uses parent traversal")
        requested = root / requested
    if requested.is_symlink():
        raise ValueError("artifact directory uses a symlink")
    cursor = Path(requested.absolute().anchor)
    for part in requested.absolute().parts[1:]:
        cursor /= part
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var"), Path("/private/tmp")}:
            raise ValueError("artifact path uses a symlink")
    resolved = requested.resolve(strict=True)
    experiment = (root / EXPERIMENT_ROOT).resolve(strict=False)
    official = (root / ARTIFACT_RELATIVE).resolve(strict=False)
    try:
        resolved.relative_to(experiment)
        allowed = True
    except ValueError:
        allowed = resolved == official
    if not allowed:
        raise ValueError("artifact must stay under the triplet experiment directory or exact official path")
    if not resolved.is_dir():
        raise ValueError("artifact path is not a directory")
    return resolved


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"artifact member is not a regular file: {name}")
    return path


def _report(
    root: Path,
    payload: dict[str, Any],
    payload_sha: str,
    bundle_sha: str,
    *,
    status: str = "candidate",
) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("artifact status is not reportable")
    return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": status, "verified": True, "errors": [], "rom_sha256": ROM_SHA256, "coverage_baseline_sha256": payload["coverage_baseline"]["sha256"], "promotion_claim_count": len(payload["promotion"]["claims"]), "promotion_range_count": len(payload["promotion"]["ranges"]), "promotion_bytes": payload["promotion"]["byte_size"], "promotion_range_vector_sha256": payload["promotion"]["range_vector_sha256"], "promotion_packed_sha256": payload["promotion"]["packed_sha256"], "consumer_instruction_count": payload["consumer"]["instruction_count"], "consumer_block_count": payload["consumer"]["block_count"], "consumer_frontier_count": payload["consumer"]["frontier_count"], "table_record_count": payload["table"]["record_count"], "json_sha256": payload_sha, "bin_sha256": bundle_sha, "verifier_sha256": _implementation(root)["verifier"]["sha256"]}


def _verifier_command(root: Path, artifact: Path) -> list[str]:
    try:
        artifact_arg = artifact.resolve(strict=False).relative_to(root.resolve(strict=True)).as_posix()
    except ValueError:
        artifact_arg = str(artifact.resolve(strict=False))
    return ["python3", "-I", "-S", "tools/verify_rom_u8_indexed_u8_triplet_lookup.py", "--root", ".", "--artifact-dir", artifact_arg]


def _coverage_projection(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("promotion", {}).get("claims")
    expected_rows = [
        {
            "id": "fixed-consumer-triplet-pointer-literal",
            "range": [POINTER_START, POINTER_END],
            "primary_class": "fixed_consumer_triplet_pointer_literal",
            "claim_kind": "fixed_consumer_triplet_pointer_literal_bytes",
        },
        {
            "id": "fixed-consumer-triplet-records",
            "range": [TABLE_START, TABLE_END],
            "primary_class": "fixed_consumer_triplet_table",
            "claim_kind": "fixed_consumer_triplet_record_bytes",
        },
    ]
    if not isinstance(rows, list):
        raise ValueError("coverage promotion claims are absent")
    projected = [
        {
            "id": row.get("id"),
            "range": row.get("range"),
            "primary_class": row.get("primary_class"),
            "claim_kind": row.get("claim_kind"),
        }
        for row in rows
    ]
    if projected != expected_rows:
        raise ValueError("coverage promotion claim denominator changed")
    return {
        "claim_count": 2,
        "byte_count": 19,
        "range_vector_sha256": PROMOTION_RANGE_VECTOR_SHA256,
        "packed_bytes_sha256": PROMOTION_PACKED_SHA256,
        "claims": expected_rows,
        "claim_denominator_sha256": _sha(_canonical(expected_rows)),
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
    rows = payload["promotion"]["claims"]
    non_claims = dict(payload["non_claims"])
    claims: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        start, end = row["range"]
        claims.append(
            {
                "id": row["id"],
                "range": [start, end],
                "gba_range": [ROM_BASE + start, ROM_BASE + end],
                "role": "primary",
                "primary_class": row["primary_class"],
                "claim_kind": row["claim_kind"],
                "promotion_batch": SCHEMA,
                "promoted_from_primary_class": "unknown",
                "baseline_unknown_only": True,
                "bytes_sha256": row["sha256"],
                "artifact_range_index": index,
                "promotion_range_count": 2,
                "promotion_bytes": 19,
                "promotion_range_vector_sha256": PROMOTION_RANGE_VECTOR_SHA256,
                "evidence_path": (ARTIFACT_RELATIVE / JSON_NAME).as_posix(),
                "evidence_sha256": payload_file["sha256"],
                "evidence_selector": f"/promotion/claims/{index}",
                "promotion_manifest_path": (
                    ARTIFACT_RELATIVE / "manifest.json"
                ).as_posix(),
                "promotion_manifest_sha256": manifest_sha256,
                "independent_verifier_path": verifier["path"],
                "independent_verifier_sha256": verifier["sha256"],
                "non_claims": non_claims,
                "limitations": [COVERAGE_LIMITATION],
            }
        )
    return claims


def analyze_live_coverage(
    coverage: dict[str, Any],
    *,
    artifact_status: str,
    expected_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    if artifact_status not in {"candidate", "accepted"}:
        raise ValueError("coverage artifact status is invalid")
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    invariant_top = {
        key: value for key, value in coverage.items() if key not in COVERAGE_DYNAMIC_KEYS
    }
    if _sha(_canonical(invariant_top)) != COVERAGE_INVARIANT_TOP_SHA256:
        raise ValueError("coverage invariant top-level identity changed")
    segments, claims, summary = _check_coverage_partition(coverage)
    ids = [claim.get("id") if isinstance(claim, dict) else None for claim in claims]
    if any(value is None for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("coverage claim IDs are missing or duplicate")
    try:
        if claims != sorted(claims, key=lambda claim: (claim["range"], claim["id"])):
            raise ValueError("coverage claims are not in canonical range/ID order")
    except (KeyError, TypeError) as error:
        raise ValueError("coverage claim ordering fields are invalid") from error
    if len(expected_claims) != 2:
        raise ValueError("coverage expected claim denominator changed")

    states: list[str] = []
    for expected in expected_claims:
        start, end = expected["range"]
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
            if (
                segment.get("primary_class") == "unknown"
                and segment.get("primary_claim_ids") in (None, [])
            ):
                seen.add("unknown")
            elif (
                segment.get("primary_class") == expected["primary_class"]
                and segment.get("primary_claim_ids") == [expected["id"]]
            ):
                seen.add("owned")
            else:
                raise ValueError(f"coverage owner changed for {expected['id']}")
            cursor = right
        if cursor != end or len(seen) != 1:
            raise ValueError(f"coverage claim is partial for {expected['id']}")
        states.append(next(iter(seen)))
    if len(set(states)) != 1:
        raise ValueError("coverage promotion is only partially applied")

    if states[0] == "unknown":
        components = {
            "claims": (claims, COVERAGE_BASELINE_CLAIMS_SHA256),
            "segments": (segments, COVERAGE_BASELINE_SEGMENTS_SHA256),
            "summary": (summary, COVERAGE_BASELINE_SUMMARY_SHA256),
            "limitations": (
                coverage["limitations"],
                COVERAGE_BASELINE_LIMITATIONS_SHA256,
            ),
        }
    else:
        if artifact_status != "accepted":
            raise ValueError("candidate coverage is no longer the frozen baseline")
        expected_ids = {claim["id"] for claim in expected_claims}
        by_id = {claim.get("id"): claim for claim in claims if isinstance(claim, dict)}
        for expected in expected_claims:
            if by_id.get(expected["id"]) != expected:
                raise ValueError(f"coverage claim changed for {expected['id']}")
        projected = [claim for claim in claims if claim.get("id") in expected_ids]
        if projected != expected_claims:
            raise ValueError("coverage post triplet claim order or identity changed")
        non_triplet = [claim for claim in claims if claim.get("id") not in expected_ids]
        components = {
            "non-triplet claims": (
                non_triplet,
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
            raise ValueError(f"coverage exact {label} identity changed")
    return {
        "coverage_contract_verified": True,
        "promotion_bytes": 19,
        "promotion_claim_count": 2,
    }


def _expected_manifest(
    root: Path,
    artifact: Path,
    payload: dict[str, Any],
    payload_raw: bytes,
    bundle: bytes,
    *,
    status: str,
) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("artifact status is not verifiable")
    manifest = {"schema": PROMOTION_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": status, "files": {JSON_NAME: {"sha256": _sha(payload_raw), "size": len(payload_raw)}, BIN_NAME: {"sha256": _sha(bundle), "size": len(bundle)}}, "rom": payload["rom"], "coverage_baseline": payload["coverage_baseline"], "promotion": payload["promotion"], "scope": payload["scope"], "non_claims": payload["non_claims"], "implementation": payload["implementation"], "reproduction_command": _verifier_command(root, artifact)}
    if status == "accepted":
        manifest["coverage_projection"] = _coverage_projection(payload)
        report = _report(root, payload, _sha(payload_raw), _sha(bundle), status="accepted")
        verification = {
            "schema": VERIFY_SCHEMA,
            "command": _verifier_command(root, artifact),
            "exit_code": 0,
            "verifier_sha256": _implementation(root)["verifier"]["sha256"],
            "report": report,
        }
        manifest["verification"] = verification
        manifest["verifier"] = verification
    return manifest


def _safe_report_path(
    root: Path,
    value: Path,
    artifacts: tuple[Path, ...] = (),
) -> Path:
    requested = Path(value).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    absolute = requested.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var"), Path("/private/tmp")}:
            raise ValueError("report path uses a symlink")
    try:
        absolute.relative_to((root / EXPERIMENT_ROOT).resolve(strict=False))
    except ValueError as error:
        raise ValueError("report path must stay under the triplet experiment directory") from error
    if absolute.exists() and (absolute.is_symlink() or not absolute.is_file()):
        raise ValueError("report path is not a regular file")
    for artifact in artifacts:
        artifact = artifact.resolve(strict=False)
        resolved_output = absolute.resolve(strict=False)
        if resolved_output == artifact or artifact in resolved_output.parents:
            raise ValueError("report path must not overwrite or enter the artifact directory")
    return absolute


def _check_existing_report(root: Path, path: Path, expected: dict[str, Any]) -> None:
    report_path = _safe_report_path(root, path)
    raw = report_path.read_bytes()
    actual = json.loads(raw.decode("utf-8"))
    if raw != _canonical(actual) or actual != expected:
        raise ValueError("existing verifier report differs from independent reconstruction")


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    status = "unknown"
    try:
        root = _validate_root(root)
        artifact = _artifact_path(root, artifact_dir)
        members = list(artifact.iterdir())
        if {item.name for item in members} != {"manifest.json", JSON_NAME, BIN_NAME} or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("artifact file denominator changed")
        manifest_path = _artifact_file(artifact, "manifest.json")
        manifest_raw = manifest_path.read_bytes()
        manifest = json.loads(manifest_raw.decode("utf-8"))
        if not isinstance(manifest, dict) or manifest_raw != _canonical(manifest):
            raise ValueError("artifact manifest is not canonical JSON")
        status = manifest.get("artifact_status")
        if status not in {"candidate", "accepted"}:
            raise ValueError("artifact status is not verifiable")
        expected, expected_bundle = rebuild_payload(
            root,
            validate_live_baseline=status == "candidate",
        )
        payload_path = _artifact_file(artifact, JSON_NAME)
        bundle_path = _artifact_file(artifact, BIN_NAME)
        payload_raw = payload_path.read_bytes()
        bundle = bundle_path.read_bytes()
        if payload_raw != _canonical(expected):
            raise ValueError("artifact payload differs from independent reconstruction")
        if bundle != expected_bundle:
            raise ValueError("artifact bundle differs from independent reconstruction")
        if manifest != _expected_manifest(
            root,
            artifact,
            expected,
            payload_raw,
            bundle,
            status=status,
        ):
            raise ValueError("artifact manifest differs from independent reconstruction")
        if status == "accepted":
            expected_claims = expected_coverage_claims(
                expected,
                manifest,
                manifest_sha256=_sha(manifest_raw),
            )
            _, coverage = _read_live_coverage(root)
            analyze_live_coverage(
                coverage,
                artifact_status="accepted",
                expected_claims=expected_claims,
            )
        return _report(root, expected, _sha(payload_raw), _sha(bundle), status=status)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": status, "verified": False, "errors": [str(error)]}


def _accept_output_path(root: Path, output_dir: Path) -> Path:
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        if ".." in requested.parts:
            raise ValueError("accept output uses parent traversal")
        requested = root / requested
    absolute = Path(os.path.abspath(requested))
    try:
        relative = absolute.relative_to(root)
    except ValueError as error:
        raise ValueError("accept output must stay inside the repository") from error
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("accept output uses a symlink component")
    experiment = (root / EXPERIMENT_ROOT).resolve(strict=False)
    official = (root / ARTIFACT_RELATIVE).resolve(strict=False)
    target = absolute.resolve(strict=False)
    try:
        target.relative_to(experiment)
        allowed = True
    except ValueError:
        allowed = target == official
    if not allowed:
        raise ValueError("accepted output must stay in the triplet experiment or exact official path")
    if target.exists():
        raise ValueError("accepted output already exists")
    return target


def accept_candidate(root: Path, candidate_dir: Path, output_dir: Path) -> dict[str, Any]:
    repository = _validate_root(root)
    candidate = _artifact_path(repository, candidate_dir)
    report = verify_artifact(repository, candidate)
    if report.get("verified") is not True or report.get("artifact_status") != "candidate":
        raise ValueError("acceptance source is not a verified candidate")
    payload_raw = _artifact_file(candidate, JSON_NAME).read_bytes()
    bundle = _artifact_file(candidate, BIN_NAME).read_bytes()
    payload = json.loads(payload_raw.decode("utf-8"))
    target = _accept_output_path(repository, output_dir)
    files = {
        JSON_NAME: payload_raw,
        BIN_NAME: bundle,
        "manifest.json": _canonical(
            _expected_manifest(
                repository,
                target,
                payload,
                payload_raw,
                bundle,
                status="accepted",
            )
        ),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.accept-", dir=target.parent))
    published = False
    try:
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        os.replace(temporary, target)
        published = True
        accepted = verify_artifact(repository, target)
        if accepted.get("verified") is not True or accepted.get("artifact_status") != "accepted":
            raise ValueError("accepted artifact failed independent reconstruction")
        command = _verifier_command(repository, target)
        completed = subprocess.run(
            command,
            cwd=str(repository),
            capture_output=True,
            text=True,
            check=False,
        )
        lines = completed.stdout.strip().splitlines()
        try:
            isolated = json.loads(lines[-1]) if lines else None
        except json.JSONDecodeError as error:
            raise ValueError("isolated accepted verifier output is not JSON") from error
        if (
            completed.returncode != 0
            or not isinstance(isolated, dict)
            or isolated != accepted
        ):
            detail = completed.stderr.strip() or isolated or "no verifier report"
            raise ValueError(
                f"isolated accepted verifier failed (exit {completed.returncode}): {detail}"
            )
        return accepted
    except BaseException:
        if published and target.exists():
            shutil.rmtree(target)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--accept-to", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    output: Path | None = None
    try:
        root = _validate_root(args.root)
        source = _artifact_path(root, args.artifact_dir)
        target = _accept_output_path(root, args.accept_to) if args.accept_to is not None else None
        if args.output is not None:
            protected = (source,) if target is None else (source, target)
            output = _safe_report_path(root, args.output, protected)
        report = (
            verify_artifact(root, source)
            if target is None
            else accept_candidate(root, source, target)
        )
        if args.report is not None and report.get("verified") is True:
            _check_existing_report(root, args.report, report)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        report = {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": "unknown", "verified": False, "errors": [str(error)]}
    if output is not None:
        try:
            _atomic_write(output, _canonical(report))
        except (OSError, ValueError) as error:
            report = {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": "unknown", "verified": False, "errors": [str(error)]}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if report.get("verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
