#!/usr/bin/env python3
"""Export the frozen u8-indexed two-u16 lookup overlay from the base ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


SCHEMA = "rom-u8-indexed-u16-pair-lookup-v1"
VERIFY_SCHEMA = "rom-u8-indexed-u16-pair-lookup-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
JSON_NAME = "rom-u8-indexed-u16-pair-lookup.json"
BIN_NAME = "rom-u8-indexed-u16-pair-lookup.bin"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
_FIXED_ROM_SHA256 = ROM_SHA256
COVERAGE_SHA256 = "4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd"
LOGICAL_START = 0x59F560
LOGICAL_END = 0x59F960
LOGICAL_CELL_COUNT = 256
LOGICAL_CELL_SIZE = 4
LOGICAL_SIZE = LOGICAL_END - LOGICAL_START
LOGICAL_SHA256 = "adaa3da39ee951908263186ab1587a95f827b3041b4a59055da9fb54eb7cdf53"
PRIMARY_START = 0x59F560
PRIMARY_END = 0x59F5F0
PRIMARY_CELL_COUNT = 36
PRIMARY_SIZE = PRIMARY_END - PRIMARY_START
PRIMARY_SHA256 = "36799e6ed48b1bb9dfb3b6ed607e114ef6477174ce57f57ad352b8cab0441f60"
OVERLAP_START = 0x59F5F0
OVERLAP_END = 0x59F960
OVERLAP_CELL_COUNT = 220
OVERLAP_SIZE = OVERLAP_END - OVERLAP_START
OVERLAP_SHA256 = "8e709ff34aa30c2d5f1639513fee9cfabd54e88e726112f5d49e3253549306f1"

BASE_LITERAL = ROM_BASE + LOGICAL_START
BASE_LITERAL_RAW = bytes.fromhex("60f55908")
BASE_LITERAL_OCCURRENCES = (0x08078094, 0x080898D8, 0x08093C6C)
BASE_LITERAL_VECTOR_SHA256 = "937c38eacbcca9c6a7736b083b84e1f90b5bffe495674b0add9aaa17a98c189f"

OWNER_DIR = Path("artifacts/rom-selector-direct-source-records-v1")
OWNER_MANIFEST = OWNER_DIR / "manifest.json"
OWNER_PAYLOAD = OWNER_DIR / "rom-selector-direct-source-records.json"
OWNER_BUNDLE = OWNER_DIR / "rom-selector-direct-source-records.bin"
OWNER_VERIFIER = Path("tools/verify_rom_selector_direct_source_records.py")
OWNER_MANIFEST_SHA256 = "094dbb593b2b8e09849ea795f4a09155598936cd3a1bc0b36e2eda6a413cf789"
OWNER_PAYLOAD_SHA256 = "adc03bd5e29e956c208698fedc733e305ea87e519e17dfa405ff813939149430"
OWNER_BUNDLE_SHA256 = "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56"
OWNER_VERIFIER_SHA256 = "510835b5d104f0009df09e3c8200beaefcb4f01836c40db7d3b1c11b475052d1"
OWNER_RECORD_START = 0x59F5F0
OWNER_RECORD_SIZE = 20
OWNER_RECORD_COUNT = 46
OWNER_OVERLAP_RECORD_COUNT = 44

CONSUMER1_ENTRY = 0x08077C90
CONSUMER1_CODE_RANGE = (0x08077C90, 0x08077F50)
CONSUMER1_CODE_SHA256 = "1e37801a1bf2d34a111cba85799becd9aca715d1dd3c099d7264d48f934c36c5"
CONSUMER1_LITERAL_LOAD = 0x08077F34
CONSUMER1_LITERAL_ADDRESS = 0x08078094
CONSUMER1_LITERAL_HALFWORD = 0x4957
CONSUMER1_SCALE = 0x08077DBC
CONSUMER1_SCALE_HALFWORD = 0x0089
CONSUMER1_SCALE_MOV_HALFWORD = 0x468A
CONSUMER1_CALLERS = (0x080795D4, 0x08086B90)
CONSUMER1_CALLER_VECTOR_SHA256 = "8967e640d0928fc3030bd9f015c1cffe179acd68acc3e5c5714d2b2806932739"

CONSUMER2_ENTRY = 0x0808983C
CONSUMER2_CODE_RANGE = (0x0808983C, 0x08089884)
CONSUMER2_CODE_SHA256 = "b9297ade6bd50f62c7463652557b8bceb07929b1bf16fc1224b3c313eaa96370"
CONSUMER2_LITERAL_LOAD = 0x08089868
CONSUMER2_LITERAL_ADDRESS = 0x080898D8
CONSUMER2_LITERAL_HALFWORD = 0x481B
CONSUMER2_CALLERS = (0x08089464, 0x08089920)
CONSUMER2_CALLER_VECTOR_SHA256 = "cc2aabc1beebb68903bbc66fbbaff20481bd3dc1e0daf3d233adb3df2283cb9b"
CONSUMER2_BRANCH_RANGE = (0x080898E0, 0x08089924)
CONSUMER2_BRANCH_SHA256 = "783075b6bbf6b265e1b118840b77c179443859882cf947cabbbd9736a016431d"

CONSUMER3_ENTRY = 0x08093818
CONSUMER3_CODE_RANGE = (0x08093818, 0x08093A46)
CONSUMER3_CODE_SHA256 = "a3a3dbc5fdcec880e9a09697e91c50698e45e89e6f5995f7993b1d1f5fc957c4"
CONSUMER3_LITERAL_LOAD = 0x08093A26
CONSUMER3_LITERAL_ADDRESS = 0x08093C6C
CONSUMER3_LITERAL_HALFWORD = 0x4A91
CONSUMER3_CALLERS = (0x08095E68,)
CONSUMER3_CALLER_VECTOR_SHA256 = "fc75ad710d8e65f72d256001890f7d347a353cc2c6430873f8d3ab6f3d82feff"
CONSUMER3_POST_CMP_RANGE = (0x08093A7C, 0x08093A80)
CONSUMER3_POST_CMP_SHA256 = "bec0fbed2b5b6391e92632de75c2a10a451ed1afabe914de91a3ea0b26ad19d1"
ENCLOSING_FUNCTION_THUMB_ENTRIES = (CONSUMER1_ENTRY | 1, CONSUMER2_ENTRY | 1, CONSUMER3_ENTRY | 1)

NON_CLAIM_FIELDS = (
    "independent_physical_bank",
    "physical_22_or_63_entry_table",
    "natural_gameplay_all_256_indices",
    "computed_or_indirect_calls_exhausted",
    "business_field_semantics",
    "selector_primary_owners_0_to_43_revoked",
    "editing_relocation_writeback_safety",
    "cross_owner_cell_62_bug_or_natural_must",
    "consumer_completeness",
    "natural_reachability_all_256",
    "safe_relocation_or_editability",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _addr(value: int) -> str:
    return f"0x{value:08X}"


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


def _safe_dir(root: Path, relative: Path) -> Path:
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
    if not resolved.is_dir():
        raise ValueError(f"repository input is not a directory: {relative}")
    return resolved


def _implementation_identities(root: Path) -> dict[str, dict[str, str]]:
    paths = {
        "exporter": Path("tools/export_rom_u8_indexed_u16_pair_lookup.py"),
        "verifier": Path("tools/verify_rom_u8_indexed_u16_pair_lookup.py"),
        "tests": Path("tests/test_export_rom_u8_indexed_u16_pair_lookup.py"),
    }
    return {
        role: {"path": relative.as_posix(), "sha256": _sha(_safe_file(root, relative).read_bytes())}
        for role, relative in paths.items()
    }


def _file_offset(gba: int) -> int:
    if not ROM_BASE <= gba < ROM_BASE + ROM_SIZE:
        raise ValueError(f"GBA address is outside mapped ROM: {_addr(gba)}")
    return gba - ROM_BASE


def _u16(rom: bytes, gba: int) -> int:
    offset = _file_offset(gba)
    if offset + 2 > len(rom):
        raise ValueError("Thumb halfword escapes ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _u32(rom: bytes, gba: int) -> int:
    offset = _file_offset(gba)
    if offset + 4 > len(rom):
        raise ValueError("literal word escapes ROM")
    return int.from_bytes(rom[offset : offset + 4], "little")


def _slice_gba(rom: bytes, start: int, end: int, expected: str, label: str) -> dict[str, Any]:
    start_offset = _file_offset(start)
    end_offset = _file_offset(end)
    if end_offset < start_offset or end_offset > len(rom):
        raise ValueError(f"{label} range escapes ROM")
    raw = rom[start_offset:end_offset]
    actual = _sha(raw)
    if actual != expected:
        raise ValueError(f"{label} source changed")
    return {
        "range": [start_offset, end_offset],
        "gba_range": [_addr(start), _addr(end)],
        "size": len(raw),
        "sha256": actual,
        "raw_hex": raw.hex(),
    }


def _expect16(rom: bytes, gba: int, expected: int, label: str) -> int:
    actual = _u16(rom, gba)
    if actual != expected:
        raise ValueError(f"{label} changed: expected 0x{expected:04X}, got 0x{actual:04X}")
    return actual


def _decode_ldr_literal(rom: bytes, gba: int, expected_halfword: int, expected_literal: int, label: str) -> dict[str, Any]:
    instruction = _expect16(rom, gba, expected_halfword, label)
    if instruction & 0xF800 != 0x4800:
        raise ValueError(f"{label} is not a Thumb PC-relative LDR")
    literal = ((gba + 4) & ~3) + (instruction & 0xFF) * 4
    value = _u32(rom, literal)
    if literal != expected_literal or value != BASE_LITERAL:
        raise ValueError(f"{label} resolution changed")
    return {
        "gba_address": gba,
        "file_offset": _file_offset(gba),
        "halfword": instruction,
        "raw_hex": rom[_file_offset(gba) : _file_offset(gba) + 2].hex(),
        "register": (instruction >> 8) & 7,
        "literal_gba_address": literal,
        "literal_file_offset": _file_offset(literal),
        "literal_value": value,
        "literal_raw_hex": BASE_LITERAL_RAW.hex(),
    }


def _decode_thumb_bl(rom: bytes, gba: int) -> int:
    first = _u16(rom, gba)
    second = _u16(rom, gba + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("not a Thumb BL")
    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    imm11 = second & 0x07FF
    i1 = j1 ^ 1 ^ sign
    i2 = j2 ^ 1 ^ sign
    immediate = (sign << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if sign:
        immediate -= 1 << 25
    return gba + 4 + immediate


def _scan_bl_sites(rom: bytes, targets: set[int]) -> dict[int, list[int]]:
    result = {target: [] for target in targets}
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset : offset + 2], "little")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        gba = ROM_BASE + offset
        target = _decode_thumb_bl(rom, gba)
        if target in result:
            result[target].append(gba)
    return result


def _scan_literal_occurrences(rom: bytes) -> list[int]:
    return [
        ROM_BASE + offset
        for offset in range(0, len(rom) - 3)
        if rom[offset : offset + 4] == BASE_LITERAL_RAW
    ]


def _scan_exact_thumb_entry_occurrences(rom: bytes) -> dict[int, list[int]]:
    occurrences = {entry: [] for entry in ENCLOSING_FUNCTION_THUMB_ENTRIES}
    for offset in range(0, len(rom) - 3):
        value = int.from_bytes(rom[offset : offset + 4], "little")
        if value in occurrences:
            occurrences[value].append(ROM_BASE + offset)
    return occurrences


def _owner_contract(root: Path, rom: bytes) -> dict[str, Any]:
    manifest_path = _safe_file(root, OWNER_MANIFEST)
    payload_path = _safe_file(root, OWNER_PAYLOAD)
    bundle_path = _safe_file(root, OWNER_BUNDLE)
    verifier_path = _safe_file(root, OWNER_VERIFIER)
    for path, expected, label in (
        (manifest_path, OWNER_MANIFEST_SHA256, "owner manifest"),
        (payload_path, OWNER_PAYLOAD_SHA256, "owner payload"),
        (bundle_path, OWNER_BUNDLE_SHA256, "owner bundle"),
        (verifier_path, OWNER_VERIFIER_SHA256, "owner verifier"),
    ):
        if _sha(path.read_bytes()) != expected:
            raise ValueError(f"{label} changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_schema") != "rom-selector-direct-source-records-v1":
        raise ValueError("owner artifact schema changed")
    if payload.get("schema") != "rom-selector-direct-source-records-v1":
        raise ValueError("owner payload schema changed")
    if payload.get("rom", {}).get("sha256") != _FIXED_ROM_SHA256:
        raise ValueError("owner ROM identity changed")
    if bundle_path.read_bytes() != rom[OWNER_RECORD_START : OWNER_RECORD_START + OWNER_RECORD_COUNT * OWNER_RECORD_SIZE]:
        raise ValueError("owner bundle bytes changed")
    records = payload.get("source_table", {}).get("records")
    if not isinstance(records, list) or len(records) != OWNER_RECORD_COUNT:
        raise ValueError("owner source record denominator changed")
    owner_ids: list[str] = []
    owner_source_ids: list[int] = []
    owner_ranges: list[list[int]] = []
    owner_bytes_sha256: list[str] = []
    for index in range(OWNER_OVERLAP_RECORD_COUNT):
        start = OWNER_RECORD_START + index * OWNER_RECORD_SIZE
        end = start + OWNER_RECORD_SIZE
        raw = rom[start:end]
        row = records[index]
        if (
            row.get("source_id") != index
            or row.get("range") != [start, end]
            or row.get("raw_sha256") not in (None, _sha(raw))
            or row.get("sha256") not in (None, _sha(raw))
        ):
            raise ValueError("owner source record identity changed")
        owner_ids.append(f"selector-direct-source-record-{index:02d}-{start:06x}")
        owner_source_ids.append(index)
        owner_ranges.append([start, end])
        owner_bytes_sha256.append(_sha(raw))
    return {
        "owner_artifact_manifest": OWNER_MANIFEST.as_posix(),
        "owner_manifest_sha256": OWNER_MANIFEST_SHA256,
        "owner_payload": OWNER_PAYLOAD.as_posix(),
        "owner_payload_sha256": OWNER_PAYLOAD_SHA256,
        "owner_bundle": OWNER_BUNDLE.as_posix(),
        "owner_bundle_sha256": OWNER_BUNDLE_SHA256,
        "owner_verifier": OWNER_VERIFIER.as_posix(),
        "owner_verifier_sha256": OWNER_VERIFIER_SHA256,
        "owner_primary_class": "selector_direct_source_record",
        "owner_claim_kind": "selector_direct_source_record_bytes",
        "owner_source_ids": owner_source_ids,
        "owner_claim_ids": owner_ids,
        "owner_ranges": owner_ranges,
        "owner_bytes_sha256": owner_bytes_sha256,
    }


def _coverage_projection(root: Path, rom: bytes, owner: dict[str, Any]) -> dict[str, Any]:
    coverage_path = _safe_file(root, COVERAGE_PATH)
    coverage_raw = coverage_path.read_bytes()
    if _sha(coverage_raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    coverage = json.loads(coverage_raw.decode("utf-8"))
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    if coverage.get("base_rom", {}).get("sha256") != _FIXED_ROM_SHA256 or coverage.get("base_rom", {}).get("size") != ROM_SIZE:
        raise ValueError("coverage baseline ROM identity changed")
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("coverage baseline segments/claims missing")
    relevant = [
        segment
        for segment in segments
        if segment.get("range", [0, 0])[0] < OVERLAP_END
        and segment.get("range", [0, 0])[1] >= PRIMARY_START
    ]
    if len(relevant) != OWNER_OVERLAP_RECORD_COUNT + 1:
        raise ValueError("coverage projection segment denominator changed")
    unknown = relevant[0]
    if unknown.get("range") != [0x59EAE0, OVERLAP_START] or unknown.get("primary_claim_ids") != [] or unknown.get("secondary_claim_ids") != [] or unknown.get("primary_class") != "unknown":
        raise ValueError("coverage current-unknown projection changed")
    claim_by_id = {claim.get("id"): claim for claim in claims}
    for index, claim_id in enumerate(owner["owner_claim_ids"]):
        expected_range = [OVERLAP_START + index * OWNER_RECORD_SIZE, OVERLAP_START + (index + 1) * OWNER_RECORD_SIZE]
        segment = relevant[index + 1]
        if segment.get("range") != expected_range or segment.get("primary_claim_ids") != [claim_id] or segment.get("secondary_claim_ids") != [] or segment.get("primary_class") != owner["owner_primary_class"]:
            raise ValueError("coverage existing-owner partition changed")
        claim = claim_by_id.get(claim_id)
        if not isinstance(claim, dict):
            raise ValueError("coverage existing-owner claim missing")
        raw = rom[expected_range[0] : expected_range[1]]
        if (
            claim.get("range") != expected_range
            or claim.get("role") != "primary"
            or claim.get("claim_kind") != owner["owner_claim_kind"]
            or claim.get("primary_class") != owner["owner_primary_class"]
            or claim.get("bytes_sha256") != _sha(raw)
            or claim.get("promotion_manifest_path") != owner["owner_artifact_manifest"]
            or claim.get("promotion_manifest_sha256") != owner["owner_manifest_sha256"]
            or claim.get("baseline_unknown_only") is not True
        ):
            raise ValueError("coverage existing-owner claim changed")
    projection = {
        "baseline": {
            "path": COVERAGE_PATH.as_posix(),
            "sha256": COVERAGE_SHA256,
            "schema": coverage.get("schema"),
        },
        "current_unknown": {
            "range": [PRIMARY_START, PRIMARY_END],
            "gba_range": [_addr(ROM_BASE + PRIMARY_START), _addr(ROM_BASE + PRIMARY_END)],
            "cell_range": [0, PRIMARY_CELL_COUNT],
            "cell_count": PRIMARY_CELL_COUNT,
            "size": PRIMARY_SIZE,
            "sha256": _sha(rom[PRIMARY_START:PRIMARY_END]),
            "primary_class": "u8_indexed_u16_pair_lookup",
            "claim_kind": "u8_indexed_u16_pair_lookup_bytes",
            "promoted_from_primary_class": "unknown",
            "allocatable": False,
        },
        "existing_owner_overlap": {
            "range": [OVERLAP_START, OVERLAP_END],
            "gba_range": [_addr(ROM_BASE + OVERLAP_START), _addr(ROM_BASE + OVERLAP_END)],
            "cell_range": [PRIMARY_CELL_COUNT, LOGICAL_CELL_COUNT],
            "cell_count": OVERLAP_CELL_COUNT,
            "size": OVERLAP_SIZE,
            "sha256": _sha(rom[OVERLAP_START:OVERLAP_END]),
            "role": "provenance_only",
            "reclassifies_existing_owner": False,
            **owner,
        },
    }
    return projection


def _consumer_contract(rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    occurrences = _scan_literal_occurrences(rom)
    if occurrences != list(BASE_LITERAL_OCCURRENCES):
        raise ValueError("base literal full-ROM denominator changed")
    vector = b"".join(rom[_file_offset(address) : _file_offset(address) + 4] for address in occurrences)
    if _sha(vector) != BASE_LITERAL_VECTOR_SHA256:
        raise ValueError("base literal occurrence vector changed")
    caller_map = _scan_bl_sites(rom, {CONSUMER1_ENTRY, CONSUMER2_ENTRY, CONSUMER3_ENTRY})
    expected_callers = {
        CONSUMER1_ENTRY: list(CONSUMER1_CALLERS),
        CONSUMER2_ENTRY: list(CONSUMER2_CALLERS),
        CONSUMER3_ENTRY: list(CONSUMER3_CALLERS),
    }
    if caller_map != expected_callers:
        raise ValueError("direct BL caller denominator changed")
    enclosing_entry_occurrences = _scan_exact_thumb_entry_occurrences(rom)
    if any(enclosing_entry_occurrences.values()):
        raise ValueError("enclosing function Thumb entry literal denominator changed")

    xrefs = []
    specs = (
        (CONSUMER1_ENTRY, CONSUMER1_CODE_RANGE, CONSUMER1_CODE_SHA256, CONSUMER1_LITERAL_LOAD, CONSUMER1_LITERAL_ADDRESS, CONSUMER1_LITERAL_HALFWORD, "third_argument", CONSUMER1_SCALE, (CONSUMER1_SCALE_HALFWORD, CONSUMER1_SCALE_MOV_HALFWORD), CONSUMER1_CALLERS, CONSUMER1_CALLER_VECTOR_SHA256),
        (CONSUMER2_ENTRY, CONSUMER2_CODE_RANGE, CONSUMER2_CODE_SHA256, CONSUMER2_LITERAL_LOAD, CONSUMER2_LITERAL_ADDRESS, CONSUMER2_LITERAL_HALFWORD, "first_argument", None, (), CONSUMER2_CALLERS, CONSUMER2_CALLER_VECTOR_SHA256),
        (CONSUMER3_ENTRY, CONSUMER3_CODE_RANGE, CONSUMER3_CODE_SHA256, CONSUMER3_LITERAL_LOAD, CONSUMER3_LITERAL_ADDRESS, CONSUMER3_LITERAL_HALFWORD, "dynamic_object_first_byte", None, (), CONSUMER3_CALLERS, CONSUMER3_CALLER_VECTOR_SHA256),
    )
    for entry, code_range, code_sha, literal_load, literal_address, literal_halfword, index_source, scale, scale_halfwords, callers, caller_sha in specs:
        code = _slice_gba(rom, *code_range, code_sha, f"consumer {_addr(entry)} code window")
        load = _decode_ldr_literal(rom, literal_load, literal_halfword, literal_address, f"consumer {_addr(entry)} base LDR")
        caller_raw = b"".join(rom[_file_offset(site) : _file_offset(site) + 4] for site in callers)
        if _sha(caller_raw) != caller_sha:
            raise ValueError(f"consumer {_addr(entry)} caller encodings changed")
        item: dict[str, Any] = {
            "function_entry": entry,
            "function_entry_hex": _addr(entry),
            "code_window": code,
            "base_literal_load": load,
            "index_argument": {
                "source": index_source,
                "width": "u8",
                "index_scale_bytes": 4,
            },
            "index_scale_bytes": 4,
            "formula": "u16(multiplier_u16*(count-1)+addend_u16)",
            "arithmetic_expression": "multiplier_u16*(count-1)+addend_u16",
            "direct_bl_callers": list(callers),
            "direct_bl_caller_raw_vector_sha256": caller_sha,
            "enclosing_function_thumb_pointer_literals": [],
            "index_guard_before_load": False,
            "result": {"width": "u16", "truncation_gba": [], "truncation_halfwords": []},
        }
        if scale is not None:
            _expect16(rom, scale, scale_halfwords[0], f"consumer {_addr(entry)} index shift")
            _expect16(rom, scale + 2, scale_halfwords[1], f"consumer {_addr(entry)} index scale move")
            _expect16(rom, 0x08077F3A, 0x8802, "consumer 0x08077C90 multiplier load")
            _expect16(rom, 0x08077F3E, 0x7858, "consumer 0x08077C90 count load")
            _expect16(rom, 0x08077F40, 0x3801, "consumer 0x08077C90 count decrement")
            _expect16(rom, 0x08077F42, 0x3102, "consumer 0x08077C90 addend offset")
            _expect16(rom, 0x08077F44, 0x4451, "consumer 0x08077C90 scaled add")
            _expect16(rom, 0x08077F46, 0x4350, "consumer 0x08077C90 multiply")
            _expect16(rom, 0x08077F48, 0x8809, "consumer 0x08077C90 addend load")
            _expect16(rom, 0x08077F4A, 0x1840, "consumer 0x08077C90 final add")
            _expect16(rom, 0x08077F4C, 0x0400, "consumer 0x08077C90 final u16 truncation load")
            _expect16(rom, 0x08077F4E, 0x0C05, "consumer 0x08077C90 final u16 truncation")
            _expect16(rom, 0x08077CA4, 0x0612, "consumer 0x08077C90 third-argument truncation")
            _expect16(rom, 0x08077CA6, 0x0E12, "consumer 0x08077C90 third-argument u8")
            item["index_argument"]["truncation_halfwords"] = [0x0612, 0x0E12]
            item["table_load"] = {"gba_address": 0x08077F3A, "offset": 0, "width": "u16", "halfword": 0x8802}
            item["count_argument"] = {"source": "object_byte_1", "width": "u8", "decrement": 1}
            item["result"] = {"width": "u16", "truncation_gba": [0x08077F4C, 0x08077F4E], "truncation_halfwords": [0x0400, 0x0C05]}
        elif entry == CONSUMER2_ENTRY:
            for gba, halfword, label in (
                (0x08089842, 0x0600, "consumer 0x0808983C first-argument truncation"),
                (0x08089844, 0x0E03, "consumer 0x0808983C first-argument u8"),
                (0x08089846, 0x0409, "consumer 0x0808983C count truncation"),
                (0x08089848, 0x0C0C, "consumer 0x0808983C count u16"),
                (0x0808984A, 0x0412, "consumer 0x0808983C third-argument truncation"),
                (0x0808984C, 0x0C15, "consumer 0x0808983C third-argument u16"),
                (0x08089852, 0x2C31, "consumer 0x0808983C count guard"),
                (0x0808986A, 0x0099, "consumer 0x0808983C index shift"),
                (0x0808986C, 0x180A, "consumer 0x0808983C base add"),
                (0x08089870, 0x8813, "consumer 0x0808983C multiplier load"),
                (0x08089872, 0x1E62, "consumer 0x0808983C count decrement"),
                (0x08089874, 0x3002, "consumer 0x0808983C addend offset"),
                (0x08089876, 0x1809, "consumer 0x0808983C scaled add"),
                (0x08089878, 0x1C18, "consumer 0x0808983C multiplier copy"),
                (0x0808987A, 0x4350, "consumer 0x0808983C multiply"),
                (0x0808987C, 0x8809, "consumer 0x0808983C addend load"),
                (0x0808987E, 0x1840, "consumer 0x0808983C final add"),
                (0x08089880, 0x0400, "consumer 0x0808983C final u16 truncation load"),
                (0x08089882, 0x0C01, "consumer 0x0808983C final u16 truncation"),
            ):
                _expect16(rom, gba, halfword, label)
            branch = _slice_gba(rom, *CONSUMER2_BRANCH_RANGE, CONSUMER2_BRANCH_SHA256, "consumer 0x0808983C branch domain")
            for gba, halfword in ((0x080898EC, 0x2800), (0x080898EE, 0xD00D), (0x080898F0, 0x2815), (0x080898F2, 0xD903), (0x080898F4, 0x281D), (0x080898F6, 0xD001), (0x080898F8, 0x283E), (0x080898FA, 0xD107)):
                _expect16(rom, gba, halfword, "consumer 0x0808983C branch-domain instruction")
            if _conditional_branch_target(rom, 0x080898EE) != 0x0808990C or _conditional_branch_target(rom, 0x080898F2) != 0x080898FC or _conditional_branch_target(rom, 0x080898F6) != 0x080898FC or _conditional_branch_target(rom, 0x080898FA) != 0x0808990C:
                raise ValueError("consumer 0x0808983C branch targets changed")
            call_target = _decode_thumb_bl(rom, 0x08089920)
            if call_target != CONSUMER2_ENTRY:
                raise ValueError("consumer 0x08089920 load path changed")
            item.update(
                {
                    "table_load": {"gba_address": 0x08089870, "offset": 0, "width": "u16", "halfword": 0x8813},
                    "count_guard": {"immediate": 0x31, "relation": "count<=0x31"},
                    "branch_domain": {"inclusive_ranges": [[0, 21]], "singleton_values": [29, 62]},
                    "all_branch_classes_reach_load": True,
                    "branch_load_callsite": 0x08089920,
                    "index_argument": {"source": "first_argument", "width": "u8", "truncation_halfwords": [0x0600, 0x0E03], "index_scale_bytes": 4},
                    "count_argument": {"source": "second_argument", "width": "u16", "truncation_halfwords": [0x0409, 0x0C0C]},
                    "result": {"width": "u16", "truncation_gba": [0x08089880, 0x08089882], "truncation_halfwords": [0x0400, 0x0C01]},
                }
            )
        else:
            _expect16(rom, 0x08093824, 0x0600, "consumer 0x08093818 first-argument truncation")
            _expect16(rom, 0x08093826, 0x0E00, "consumer 0x08093818 first-argument u8")
            _expect16(rom, 0x08093836, 0x7801, "consumer 0x08093818 dynamic-object first byte")
            for gba, halfword, label in (
                (0x08093A2A, 0x7819, "consumer 0x08093818 index load"),
                (0x08093A2C, 0x0089, "consumer 0x08093818 index shift"),
                (0x08093A2E, 0x1888, "consumer 0x08093818 base add"),
                (0x08093A30, 0x8803, "consumer 0x08093818 multiplier load"),
                (0x08093A34, 0x7868, "consumer 0x08093818 count load"),
                (0x08093A36, 0x3801, "consumer 0x08093818 count decrement"),
                (0x08093A38, 0x3202, "consumer 0x08093818 addend offset"),
                (0x08093A3A, 0x1889, "consumer 0x08093818 scaled add"),
                (0x08093A3C, 0x4358, "consumer 0x08093818 multiply"),
                (0x08093A3E, 0x8809, "consumer 0x08093818 addend load"),
                (0x08093A40, 0x1840, "consumer 0x08093818 final add"),
                (0x08093A42, 0x0400, "consumer 0x08093818 final u16 truncation load"),
                (0x08093A44, 0x0C05, "consumer 0x08093818 final u16 truncation"),
                (0x08093A7C, 0x7818, "consumer 0x08093818 post-load byte")
            ):
                _expect16(rom, gba, halfword, label)
            post = _slice_gba(rom, *CONSUMER3_POST_CMP_RANGE, CONSUMER3_POST_CMP_SHA256, "consumer 0x08093818 post-load comparison")
            _expect16(rom, 0x08093A7E, 0x2803, "consumer 0x08093818 post-load cmp #3")
            item.update(
                {
                    "table_load": {"gba_address": 0x08093A30, "offset": 0, "width": "u16", "halfword": 0x8803},
                    "index_argument": {"source": "dynamic_object_first_byte", "width": "u8", "truncation_halfwords": [0x7819], "index_scale_bytes": 4},
                    "count_argument": {"source": "dynamic_object_byte_1", "width": "u8", "decrement": 1},
                    "post_load_cmp": {"gba_address": 0x08093A7E, "immediate": 3, "position": "after_load", "window": post},
                    "result": {"width": "u16", "truncation_gba": [0x08093A42, 0x08093A44], "truncation_halfwords": [0x0400, 0x0C05]},
                }
            )
        xrefs.append(item)
    base = {
        "value": BASE_LITERAL,
        "raw_hex": BASE_LITERAL_RAW.hex(),
        "occurrences": list(occurrences),
        "occurrence_count": len(occurrences),
        "vector_sha256": BASE_LITERAL_VECTOR_SHA256,
        "xrefs": [item["base_literal_load"] for item in xrefs],
        "enclosing_function_thumb_entry_occurrences": [
            {"entry": entry, "entry_hex": _addr(entry), "occurrences": enclosing_entry_occurrences[entry]}
            for entry in ENCLOSING_FUNCTION_THUMB_ENTRIES
        ],
    }
    return base, xrefs


def _conditional_branch_target(rom: bytes, gba: int) -> int:
    instruction = _u16(rom, gba)
    if instruction & 0xF000 != 0xD000:
        raise ValueError("expected Thumb conditional branch")
    immediate = instruction & 0xFF
    if immediate & 0x80:
        immediate -= 0x100
    return gba + 4 + immediate * 2


def _cells(rom: bytes) -> list[dict[str, Any]]:
    raw_table = rom[LOGICAL_START:LOGICAL_END]
    if len(raw_table) != LOGICAL_SIZE or _sha(raw_table) != LOGICAL_SHA256:
        raise ValueError("logical lookup view identity changed")
    cells = []
    for index in range(LOGICAL_CELL_COUNT):
        start = LOGICAL_START + index * LOGICAL_CELL_SIZE
        end = start + LOGICAL_CELL_SIZE
        raw = rom[start:end]
        if len(raw) != LOGICAL_CELL_SIZE:
            raise ValueError("logical cell escapes ROM")
        cells.append(
            {
                "index": index,
                "range": [start, end],
                "gba_range": [_addr(ROM_BASE + start), _addr(ROM_BASE + end)],
                "size": LOGICAL_CELL_SIZE,
                "raw_hex": raw.hex(),
                "raw_sha256": _sha(raw),
                "multiplier_u16": int.from_bytes(raw[:2], "little"),
                "addend_u16": int.from_bytes(raw[2:], "little"),
                "formula": "multiplier_u16*(count-1)+addend_u16",
            }
        )
    return cells


def _expected_payload(root: Path, rom: bytes, *, validate_coverage: bool) -> tuple[dict[str, Any], bytes]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("ROM identity changed")
    cells = _cells(rom)
    owner = _owner_contract(root, rom)
    if validate_coverage:
        projection = _coverage_projection(root, rom, owner)
    else:
        projection = _fixed_projection(rom, owner)
    base, consumers = _consumer_contract(rom)
    implementation = _implementation_identities(root)
    non_claims = {field: False for field in NON_CLAIM_FIELDS}
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": _FIXED_ROM_SHA256},
        "coverage_baseline": {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256, "verifier_does_not_require_future_file": True},
        "logical_view": {
            "range": [LOGICAL_START, LOGICAL_END],
            "gba_range": [_addr(ROM_BASE + LOGICAL_START), _addr(ROM_BASE + LOGICAL_END)],
            "cell_count": LOGICAL_CELL_COUNT,
            "cell_size": LOGICAL_CELL_SIZE,
            "size": LOGICAL_SIZE,
            "sha256": LOGICAL_SHA256,
            "index_width": "u8",
            "pair_encoding": ["little_endian_u16", "little_endian_u16"],
            "formula": "multiplier_u16*(count-1)+addend_u16",
            "cells": cells,
        },
        "coverage_projection": projection,
        "base_literal": base,
        "consumers": consumers,
        "scope": {
            "logical_view_complete": True,
            "current_unknown_primary_projection_only": True,
            "existing_owner_overlap_is_provenance_only": True,
            "allocatable": False,
            "revokes_existing_selector_owners": False,
            "reclassifies_existing_owner_overlap": False,
            "non_claims": non_claims,
        },
        "non_claims": non_claims,
        "implementation": implementation,
    }
    return payload, rom[LOGICAL_START:LOGICAL_END]


def _fixed_projection(rom: bytes, owner: dict[str, Any]) -> dict[str, Any]:
    return {
        "baseline": {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256, "schema": "rom-byte-coverage-v1"},
        "current_unknown": {
            "range": [PRIMARY_START, PRIMARY_END],
            "gba_range": [_addr(ROM_BASE + PRIMARY_START), _addr(ROM_BASE + PRIMARY_END)],
            "cell_range": [0, PRIMARY_CELL_COUNT],
            "cell_count": PRIMARY_CELL_COUNT,
            "size": PRIMARY_SIZE,
            "sha256": _sha(rom[PRIMARY_START:PRIMARY_END]),
            "primary_class": "u8_indexed_u16_pair_lookup",
            "claim_kind": "u8_indexed_u16_pair_lookup_bytes",
            "promoted_from_primary_class": "unknown",
            "allocatable": False,
        },
        "existing_owner_overlap": {
            "range": [OVERLAP_START, OVERLAP_END],
            "gba_range": [_addr(ROM_BASE + OVERLAP_START), _addr(ROM_BASE + OVERLAP_END)],
            "cell_range": [PRIMARY_CELL_COUNT, LOGICAL_CELL_COUNT],
            "cell_count": OVERLAP_CELL_COUNT,
            "size": OVERLAP_SIZE,
            "sha256": _sha(rom[OVERLAP_START:OVERLAP_END]),
            "role": "provenance_only",
            "reclassifies_existing_owner": False,
            **owner,
        },
    }


def build_payload(root: Path) -> tuple[dict[str, Any], bytes]:
    root = _validate_root(root)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    return _expected_payload(root, rom, validate_coverage=True)


def rebuild_from_rom(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    root = _validate_root(root)
    return _expected_payload(root, rom, validate_coverage=True)


def _validate_output_path(root: Path, output_dir: Path) -> Path:
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    if requested.is_symlink():
        raise ValueError("output directory uses a symlink")
    absolute = requested.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var")}:
            raise ValueError("output directory path uses a symlink")
    if requested.exists() and not requested.is_dir():
        raise ValueError("output directory is not a directory")
    if requested.exists() and any(requested.iterdir()):
        raise ValueError("output directory is non-empty")
    if absolute == root or absolute in root.parents:
        raise ValueError("output directory is repository root or ancestor")
    return absolute


def _run_independent_verifier(root: Path, artifact_dir: Path) -> tuple[int, dict[str, Any], list[str]]:
    verifier_relative = Path("tools/verify_rom_u8_indexed_u16_pair_lookup.py")
    verifier = _safe_file(root, verifier_relative)
    command = [
        sys.executable,
        str(verifier),
        "--root",
        str(root),
        "--artifact-dir",
        str(artifact_dir),
    ]
    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    output_lines = completed.stdout.strip().splitlines()
    report: dict[str, Any]
    if output_lines:
        try:
            parsed = json.loads(output_lines[-1])
        except json.JSONDecodeError:
            parsed = None
        report = parsed if isinstance(parsed, dict) else {"verified": False, "errors": ["verifier output was not JSON"]}
    else:
        report = {"verified": False, "errors": [completed.stderr.strip() or "verifier produced no report"]}
    if completed.returncode != 0 or report.get("verified") is not True:
        detail = report.get("errors") or [completed.stderr.strip() or "independent verifier rejected candidate"]
        raise RuntimeError(f"independent verifier failed (exit {completed.returncode}): {detail}")
    return completed.returncode, report, command


def _canonical_verifier_command(root: Path, artifact_dir: Path) -> list[str]:
    root = root.resolve(strict=True)
    artifact = Path(artifact_dir).absolute().resolve(strict=False)
    try:
        artifact_arg = artifact.relative_to(root).as_posix()
    except ValueError:
        artifact_arg = str(artifact)
    return [
        "python3",
        "tools/verify_rom_u8_indexed_u16_pair_lookup.py",
        "--root",
        ".",
        "--artifact-dir",
        artifact_arg,
    ]


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = _validate_root(root)
    output = _validate_output_path(root, output_dir)
    payload, bundle = build_payload(root)
    implementation = payload["implementation"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{SCHEMA}-", dir=output.parent))
    try:
        payload_raw = _canonical(payload)
        binary = bytes(bundle)
        json_sha256 = _sha(payload_raw)
        bin_sha256 = _sha(binary)
        (temporary / JSON_NAME).write_bytes(payload_raw)
        (temporary / BIN_NAME).write_bytes(binary)
        manifest = {
            "schema": PROMOTION_SCHEMA,
            "artifact_schema": SCHEMA,
            "artifact_status": "candidate",
            "files": {JSON_NAME: json_sha256, BIN_NAME: bin_sha256},
            "rom": payload["rom"],
            "coverage_baseline": payload["coverage_baseline"],
            "implementation": implementation,
            "producer": {
                "command": ["python3", "tools/export_rom_u8_indexed_u16_pair_lookup.py", "--root", str(root), "--output-dir", str(output)],
                **implementation,
            },
            "scope": payload["scope"],
            "non_claims": payload["non_claims"],
        }
        (temporary / "manifest.json").write_bytes(_canonical(manifest))
        exit_code, receipt, _actual_verifier_command = _run_independent_verifier(root, temporary)
        verifier_command = _canonical_verifier_command(root, output)
        manifest.update(
            {
                "artifact_status": "accepted",
                "verifier": {"command": verifier_command, "exit_code": exit_code, "report": receipt},
                "verification": receipt,
            }
        )
        (temporary / "manifest.json").write_bytes(_canonical(manifest))
        os.replace(temporary, output)
    except BaseException:
        if temporary.exists():
            for path in temporary.iterdir():
                path.unlink()
            temporary.rmdir()
        raise
    return {
        "schema": SCHEMA,
        "artifact_dir": str(output),
        "files": {JSON_NAME: json_sha256, BIN_NAME: bin_sha256},
        "manifest_sha256": _sha((output / "manifest.json").read_bytes()),
        "verification": receipt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output-dir", "--out-dir", dest="output_dir", type=Path, required=True)
    args = parser.parse_args()
    result = export_artifact(args.root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
