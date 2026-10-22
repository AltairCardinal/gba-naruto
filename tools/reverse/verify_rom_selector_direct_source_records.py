#!/usr/bin/env python3
"""Independently verify the fixed selector direct-source record table."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCHEMA = "rom-selector-direct-source-records-v1"
VERIFY_SCHEMA = "rom-selector-direct-source-records-verification-v1"
ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_START = 0x59F5F0
SOURCE_COUNT = 46
SOURCE_RECORD_SIZE = 20
SOURCE_END = 0x59F988
SOURCE_SHA256 = "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56"
SOURCE_VECTOR_SHA256 = "065fca6237d166557a03cf30ddd309f695b825f5c850356a3c736e396d9478db"
NAME_SLOT_VECTOR_SHA256 = "d429cca720c928593b80289794395d0c6d266268af5da567bbe76a22c5b65ba2"
SORTED_SLOT_VECTOR_SHA256 = "42aaddfc56e36df6be859279c4a64aff4ae006e416895817c200d733eeae64a2"
ROW_RANGE_VECTOR_SHA256 = "a4fb31202d48f65f839217585495c2dc40d29cc63b25ff7a3d5594673056e608"
EXPECTED_NAME_SLOTS = (
    1, 2, 3, 7, 44, 43, 4, 5, 6, 45, 8, 9, 10, 46, 11, 12, 13, 47,
    48, 30, 51, 52, 14, 15, 16, 17, 18, 19, 22, 23, 24, 29, 61, 20,
    21, 31, 49, 56, 50, 25, 26, 27, 28, 53, 54, 62,
)
UPSTREAM_DIR = Path("artifacts/rom-selector-text-bindings-v1")
UPSTREAM_MANIFEST = UPSTREAM_DIR / "manifest.json"
UPSTREAM_PAYLOAD = UPSTREAM_DIR / "selector-text-bindings.json"
UPSTREAM_BUNDLE = UPSTREAM_DIR / "selector-text-bytes.bin"
UPSTREAM_VERIFIER = Path("tools/verify_rom_selector_text_bindings.py")
UPSTREAM_MANIFEST_SHA256 = "05cd987a60990ca6b2d3ee187eae963fd6ac8728ef9b42b92d6b37b5dc4bc031"
UPSTREAM_PAYLOAD_SHA256 = "8737d04de14949cbbbb9215c892a7776476c4230eb1e2b0c2abbbbe4440ce2eb"
UPSTREAM_VERIFIER_SHA256 = "a68a0d1e036be241bbac84538d5a082c7e76e2c6331ffa1d12cd384dc79e2f18"
UPSTREAM_BUNDLE_SHA256 = "1bc1df2046811a0399226edc53895b3c3359779d9407a6555dc0e7810d11e869"
EXPECTED_UPSTREAM_REPORT = {
    "artifact_schema": "rom-selector-text-bindings-v1",
    "errors": [],
    "rom_sha256": ROM_SHA256,
    "schema": "rom-selector-text-bindings-verification-v1",
    "summary": {
        "classified_bytes": 816,
        "classified_range_count": 86,
        "config_bytes": 164,
        "config_list_count": 3,
        "config_pointer_bytes": 12,
        "config_pointer_slot_count": 3,
        "config_record_count": 38,
        "config_terminator_count": 3,
        "configured_physical_slot_count": 55,
        "configured_referenced_slot_count": 38,
        "configured_text_consumed_bytes": 316,
        "configured_text_unclassified_suffix_bytes": 368,
        "configured_unreferenced_slot_bytes": 306,
        "direct_source_record_bytes": 920,
        "direct_source_record_count": 46,
        "direct_text_candidate_slot_count": 46,
        "direct_text_consumed_bytes": 324,
        "direct_text_unclassified_suffix_bytes": 550,
        "packed_bytes": 816,
        "parse_failure_count": 0,
        "range_overlap_bytes": 0,
    },
    "verified": True,
}
ENUMERATOR_RANGE = (0x0808A6AC, 0x0808A700)
ENUMERATOR_SHA256 = "68e8b80905466def5f6c4cae6fb6977336c129e7560577a77f6acac7222ca665"
LIFECYCLE_RANGE = (0x0808B58C, 0x0808B65A)
LIFECYCLE_SHA256 = "3b6050a3df82957c8804b86a06eb6c5b5efb8a7eca3da082dc999f74b78c7637"
MENU_RANGE = (0x0808B2C8, 0x0808B580)
MENU_SHA256 = "fe12c74a937dae0e60f0ba1e566788cd4dc842596d168632c9c45809f88dd07e"
DIRECT_CONSUMER_RANGE = (0x0808AFE0, 0x0808B07C)
DIRECT_CONSUMER_SHA256 = "9ec877cbef2c9aa100a825509cd41be605e3d20ff0304279572d7986c1865ac4"
BRIDGE_RANGE = (0x08066758, 0x08066790)
BRIDGE_SHA256 = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
PARSER_RANGE = (0x0806626C, 0x08066736)
PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
FORMULA_ONE_RANGE = (0x0808B2D8, 0x0808B2E8)
FORMULA_ONE_SHA256 = "8d2d98f0da6fc90d2a878f2b837278984e84488da64a42b9df0a5e223d6ea68f"
FORMULA_TWO_RANGE = (0x0808B500, 0x0808B512)
FORMULA_TWO_SHA256 = "ddf9b3c5235cb884b51b7c6cc772c81de8ceef3b8f5fcc5a49eef19b6be818ab"
STRIDE_FORMULA_RANGE = (0x0808B02C, 0x0808B03A)
STRIDE_FORMULA_SHA256 = "bf1139185eb281b29c5b4adce7b182e6f7af8213d0c40f34ff680663e0d958be"
DIRECT_BRIDGE_CALLSITES = (
    0x0808B010,
    0x0808B028,
    0x0808B044,
    0x0808B054,
    0x0808B062,
    0x0808B076,
)
BRIDGE_PARSER_CALLSITE = 0x0806678A
PAYLOAD_NAME = "rom-selector-direct-source-records.json"
BUNDLE_NAME = "rom-selector-direct-source-records.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
IMPLEMENTATION_PATHS = {
    "exporter": Path("tools/export_rom_selector_direct_source_records.py"),
    "verifier": Path("tools/verify_rom_selector_direct_source_records.py"),
    "test": Path("tests/test_export_rom_selector_direct_source_records.py"),
}
SCOPE = {
    "fixed_46_source_record_denominator_complete": True,
    "byte_2_to_19_semantics_proven": False,
    "complete_63_slot_text_table": False,
    "natural_gameplay_all_rows_reached": False,
    "unicode_decoding_complete": False,
    "editing_or_writeback_safety_proven": False,
    "allocatable_space_claimed": False,
}
LIMITATIONS = [
    "Only the fixed 46×20-byte direct source records at 0x59F5F0..0x59F988 are classified.",
    "The source row bytes at offsets 2..19 have no semantic field claim in this artifact.",
    "This does not expand to the 63-slot direct text table or include 0x59F988 and adjacent profile data.",
    "Natural gameplay reachability, Unicode decoding, editing/writeback safety, and allocatable space are not claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vector_hash(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":")).encode("ascii"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _file_offset(gba: int) -> int:
    if gba < ROM_BASE:
        raise ValueError("GBA address precedes ROM base")
    return gba - ROM_BASE


def _bounded(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError("ROM slice escapes input")
    return rom[start:end]


def _word16(rom: bytes, gba: int) -> int:
    offset = _file_offset(gba)
    return int.from_bytes(_bounded(rom, offset, offset + 2), "little")


def _word32(rom: bytes, gba: int) -> int:
    offset = _file_offset(gba)
    return int.from_bytes(_bounded(rom, offset, offset + 4), "little")


def _thumb_bl(rom: bytes, gba: int) -> int:
    first = _word16(rom, gba)
    second = _word16(rom, gba + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("Thumb BL encoding changed")
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & 0x400000:
        delta -= 0x800000
    return gba + 4 + delta


def _literal(gba: int, instruction: int, register: int) -> int:
    if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != register:
        raise ValueError("literal load encoding changed")
    return ((gba + 4) & ~3) + (instruction & 0xFF) * 4


def _raw_bl_sites(rom: bytes, target: int) -> list[int]:
    result = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset:offset + 2], "little")
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            gba = ROM_BASE + offset
            if _thumb_bl(rom, gba) == target:
                result.append(gba)
    return result


def _raw_bl_sites_in_range(
    rom: bytes, target: int, gba_start: int, gba_end: int
) -> list[int]:
    result = []
    for gba in range(gba_start, gba_end - 3, 2):
        first = _word16(rom, gba)
        second = _word16(rom, gba + 2)
        if (
            first & 0xF800 == 0xF000
            and second & 0xF800 == 0xF800
            and _thumb_bl(rom, gba) == target
        ):
            result.append(gba)
    return result


def _decode_stride_formula(rom: bytes) -> dict[str, Any]:
    addresses = tuple(range(STRIDE_FORMULA_RANGE[0], STRIDE_FORMULA_RANGE[1], 2))
    instructions = tuple(_word16(rom, gba) for gba in addresses)
    if instructions[0] != 0x7871:
        raise ValueError("direct record stride source load changed")

    first_shift = instructions[1]
    if first_shift & 0xF800 != 0x0000 or (first_shift >> 6) & 0x1F != 2 or (first_shift >> 3) & 7 != 1 or first_shift & 7 != 0:
        raise ValueError("direct record stride first shift changed")
    first_add = instructions[2]
    if first_add & 0xFE00 != 0x1800 or (first_add >> 6) & 7 != 1 or (first_add >> 3) & 7 != 0 or first_add & 7 != 0:
        raise ValueError("direct record stride first add changed")
    second_shift = instructions[3]
    if second_shift & 0xF800 != 0x0000 or (second_shift >> 6) & 0x1F != 2 or (second_shift >> 3) & 7 != 0 or second_shift & 7 != 0:
        raise ValueError("direct record stride second shift changed")
    subtract = instructions[4]
    if subtract & 0xFE00 != 0x1A00 or (subtract >> 6) & 7 != 1 or (subtract >> 3) & 7 != 0 or subtract & 7 != 0:
        raise ValueError("direct record stride subtract changed")
    literal_address = _literal(addresses[5], instructions[5], 1)
    if literal_address != 0x0808B084 or _word32(rom, literal_address) != 0x085A5AB8:
        raise ValueError("direct record stride table-base literal changed")
    final_add = instructions[6]
    if final_add & 0xFE00 != 0x1800 or (final_add >> 6) & 7 != 1 or (final_add >> 3) & 7 != 0 or final_add & 7 != 0:
        raise ValueError("direct record stride base add changed")

    coefficients = [1]
    coefficients.append(coefficients[-1] << 2)
    coefficients.append(coefficients[-1] + 1)
    coefficients.append(coefficients[-1] << 2)
    coefficients.append(coefficients[-1] - 1)
    if coefficients[-1] != 19:
        raise ValueError("direct record stride derivation changed")
    return {
        "coefficients": coefficients,
        "instruction_halfwords": [f"0x{instruction:04X}" for instruction in instructions],
        "literal_address": literal_address,
        "literal_value": _word32(rom, literal_address),
    }


def _safe_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
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


def _safe_dir(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
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
    if not resolved.is_dir():
        raise ValueError(f"repository input is not a directory: {relative}")
    return resolved


def _slice_evidence(rom: bytes, gba_start: int, gba_end: int, expected: str, label: str) -> dict[str, Any]:
    start = _file_offset(gba_start)
    end = _file_offset(gba_end)
    raw = _bounded(rom, start, end)
    if _sha(raw) != expected:
        raise ValueError(f"{label} source changed")
    return {"range": [start, end], "gba_range": [f"0x{gba_start:08X}", f"0x{gba_end:08X}"], "size": len(raw), "sha256": expected, "raw_hex": raw.hex()}


def _word_evidence(rom: bytes, gba: int, size: int, expected_value: int, label: str) -> dict[str, Any]:
    start = _file_offset(gba)
    raw = _bounded(rom, start, start + size)
    value = int.from_bytes(raw, "little")
    if value != expected_value:
        raise ValueError(f"{label} changed")
    return {"range": [start, start + size], "gba_range": [f"0x{gba:08X}", f"0x{gba + size:08X}"], "size": size, "sha256": _sha(raw), "raw_hex": raw.hex(), "value": value}


def _validate_upstream_files(root: Path) -> dict[str, Any]:
    def read_bound(relative: Path, expected: str) -> bytes:
        raw = _safe_file(root, relative).read_bytes()
        if _sha(raw) != expected:
            raise ValueError(f"bound upstream source changed: {relative}")
        return raw

    manifest = json.loads(read_bound(UPSTREAM_MANIFEST, UPSTREAM_MANIFEST_SHA256))
    payload = json.loads(read_bound(UPSTREAM_PAYLOAD, UPSTREAM_PAYLOAD_SHA256))
    bundle = read_bound(UPSTREAM_BUNDLE, UPSTREAM_BUNDLE_SHA256)
    read_bound(UPSTREAM_VERIFIER, UPSTREAM_VERIFIER_SHA256)
    if (
        manifest.get("artifact_schema") != "rom-selector-text-bindings-v1"
        or manifest.get("files", {}).get(UPSTREAM_PAYLOAD.name) != UPSTREAM_PAYLOAD_SHA256
        or manifest.get("files", {}).get(UPSTREAM_BUNDLE.name) != UPSTREAM_BUNDLE_SHA256
        or payload.get("schema") != "rom-selector-text-bindings-v1"
        or _sha(bundle) != UPSTREAM_BUNDLE_SHA256
    ):
        raise ValueError("upstream selector source contract changed")
    return payload


def _run_upstream_verifier(root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(_safe_file(root, UPSTREAM_VERIFIER)), "--root", str(root), "--artifact-dir", str(_safe_dir(root, UPSTREAM_DIR))],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("upstream verifier returned invalid JSON") from error
    if completed.returncode != 0 or report != EXPECTED_UPSTREAM_REPORT:
        raise ValueError(f"upstream verifier exact success contract changed: {report}")
    return report


def _legacy_rows(payload: dict[str, Any], rom: bytes) -> None:
    table = payload.get("direct_source_table")
    if not isinstance(table, dict) or table.get("record_vector_sha256") != SOURCE_VECTOR_SHA256:
        raise ValueError("upstream record_vector_sha256 changed")
    rows = table.get("records")
    if not isinstance(rows, list) or len(rows) != SOURCE_COUNT:
        raise ValueError("upstream direct source row denominator changed")
    vector = []
    slots = []
    for source_id, legacy in enumerate(rows):
        start = SOURCE_START + source_id * SOURCE_RECORD_SIZE
        raw = _bounded(rom, start, start + SOURCE_RECORD_SIZE)
        if legacy.get("source_id") != source_id or legacy.get("name_slot") != raw[1] or legacy.get("range") != [start, start + SOURCE_RECORD_SIZE] or legacy.get("sha256") != _sha(raw):
            raise ValueError("upstream direct source row identity changed")
        vector.append([source_id, start, raw[0], raw[1]])
        slots.append(raw[1])
    if _vector_hash(vector) != SOURCE_VECTOR_SHA256 or tuple(slots) != EXPECTED_NAME_SLOTS:
        raise ValueError("upstream direct source row vector changed")


def _source_records(rom: bytes) -> list[dict[str, Any]]:
    if _sha(_bounded(rom, SOURCE_START, SOURCE_END)) != SOURCE_SHA256:
        raise ValueError("selector direct source table changed")
    rows = []
    vector = []
    slots = []
    ranges = []
    for source_id in range(SOURCE_COUNT):
        start = SOURCE_START + source_id * SOURCE_RECORD_SIZE
        end = start + SOURCE_RECORD_SIZE
        raw = _bounded(rom, start, end)
        if raw[0] != source_id:
            raise ValueError("selector direct source_id identity changed")
        slot = raw[1]
        vector.append([source_id, start, raw[0], slot])
        slots.append(slot)
        ranges.append([start, end])
        rows.append({"source_id": source_id, "name_slot_id": slot, "range": [start, end], "gba_range": [_gba(start), _gba(end)], "size": SOURCE_RECORD_SIZE, "raw_hex": raw.hex(), "raw_sha256": _sha(raw), "packed_range": [source_id * SOURCE_RECORD_SIZE, (source_id + 1) * SOURCE_RECORD_SIZE]})
    if tuple(slots) != EXPECTED_NAME_SLOTS or len(set(slots)) != SOURCE_COUNT or set(slots) != set(range(1, 32)) | set(range(43, 55)) | {56, 61, 62} or _vector_hash(vector) != SOURCE_VECTOR_SHA256 or _vector_hash(slots) != NAME_SLOT_VECTOR_SHA256 or _vector_hash(sorted(slots)) != SORTED_SLOT_VECTOR_SHA256 or _vector_hash(ranges) != ROW_RANGE_VECTOR_SHA256:
        raise ValueError("selector direct source slot/domain vector changed")
    return rows


def _producer_evidence(rom: bytes) -> dict[str, Any]:
    enumerator = _slice_evidence(rom, *ENUMERATOR_RANGE, ENUMERATOR_SHA256, "enumerator")
    lifecycle = _slice_evidence(rom, *LIFECYCLE_RANGE, LIFECYCLE_SHA256, "lifecycle")
    menu = _slice_evidence(rom, *MENU_RANGE, MENU_SHA256, "menu selector")
    if _literal(0x0808A6B0, _word16(rom, 0x0808A6B0), 6) != 0x0808A700 or _word32(rom, 0x0808A700) != ROM_BASE + SOURCE_START or _word16(rom, 0x0808A6BC) != 0x7870 or _word16(rom, 0x0808A6F0) != 0x3614 or _word16(rom, 0x0808A6F6) != 0x282D or _word16(rom, 0x0808A6F8) != 0xDDE0:
        raise ValueError("enumerator producer contract changed")
    if _thumb_bl(rom, 0x0808B5FE) != 0x0808A6AC or _thumb_bl(rom, 0x0808B640) != 0x0808B2C8 or _word32(rom, 0x0808B44C) != ROM_BASE + SOURCE_START or _word32(rom, 0x0808B57C) != ROM_BASE + SOURCE_START:
        raise ValueError("selector lifecycle/menu contract changed")
    formula_one = _slice_evidence(rom, *FORMULA_ONE_RANGE, FORMULA_ONE_SHA256, "menu formula one")
    formula_two = _slice_evidence(rom, *FORMULA_TWO_RANGE, FORMULA_TWO_SHA256, "menu formula two")
    return {
        "enumerator": enumerator,
        "lifecycle": lifecycle,
        "menu": menu,
        "literal_word_0x0808A700": _word_evidence(rom, 0x0808A700, 4, ROM_BASE + SOURCE_START, "enumerator source literal"),
        "literal_word_0x0808B44C": _word_evidence(rom, 0x0808B44C, 4, ROM_BASE + SOURCE_START, "menu first literal"),
        "literal_word_0x0808B57C": _word_evidence(rom, 0x0808B57C, 4, ROM_BASE + SOURCE_START, "menu second literal"),
        "enumerator_loop": {"cmp_offset": 0x0808A6F6, "cmp_raw_hex": _bounded(rom, _file_offset(0x0808A6F6), _file_offset(0x0808A6F6) + 2).hex(), "cmp_immediate": 0x2D, "bhi_offset": 0x0808A6F8, "bhi_raw_hex": _bounded(rom, _file_offset(0x0808A6F8), _file_offset(0x0808A6F8) + 2).hex(), "bhi_target": 0x0808A6AC, "upper_inclusive": 45},
        "callsites": [0x0808B5FE, 0x0808B640],
        "callsite_targets": {"0x0808B5FE": 0x0808A6AC, "0x0808B640": 0x0808B2C8},
        "formula_windows": {"0x0808B2D8": formula_one, "0x0808B500": formula_two},
    }


def _consumer_evidence(rom: bytes) -> dict[str, Any]:
    direct = _slice_evidence(rom, *DIRECT_CONSUMER_RANGE, DIRECT_CONSUMER_SHA256, "direct consumer")
    bridge = _slice_evidence(rom, *BRIDGE_RANGE, BRIDGE_SHA256, "renderer bridge")
    parser = _slice_evidence(rom, *PARSER_RANGE, PARSER_SHA256, "renderer parser")
    stride = _slice_evidence(rom, *STRIDE_FORMULA_RANGE, STRIDE_FORMULA_SHA256, "direct index formula")
    if _word32(rom, 0x0808B084) != 0x085A5AB8 or _thumb_bl(rom, 0x0808B420) != 0x0808AFE0 or _thumb_bl(rom, 0x0808B51A) != 0x0808AFE0:
        raise ValueError("direct consumer key contract changed")
    callsites = _raw_bl_sites(rom, 0x0808AFE0)
    if callsites != [0x0808B420, 0x0808B51A]:
        raise ValueError("direct consumer BL denominator changed")
    stride_derivation = _decode_stride_formula(rom)
    bridge_callsites = _raw_bl_sites_in_range(
        rom, BRIDGE_RANGE[0], DIRECT_CONSUMER_RANGE[0], DIRECT_CONSUMER_RANGE[1]
    )
    if bridge_callsites != list(DIRECT_BRIDGE_CALLSITES):
        raise ValueError("direct consumer bridge callsite denominator changed")
    bridge_parser_target = _thumb_bl(rom, BRIDGE_PARSER_CALLSITE)
    if bridge_parser_target != PARSER_RANGE[0]:
        raise ValueError("renderer bridge parser callsite changed")
    return {
        "direct_consumer": direct,
        "bridge": bridge,
        "parser": parser,
        "stride_formula": stride,
        "record_stride_bytes": stride_derivation["coefficients"][-1],
        "record_stride_derivation": stride_derivation,
        "literal_word_0x080B084": _word_evidence(rom, 0x0808B084, 4, 0x085A5AB8, "direct table literal"),
        "direct_consumer_callsites": callsites,
        "direct_consumer_callsite_raw_hex": {f"0x{site:08X}": _bounded(rom, _file_offset(site), _file_offset(site) + 4).hex() for site in callsites},
        "bridge_callsites": bridge_callsites,
        "bridge_callsite_raw_hex": {f"0x{site:08X}": _bounded(rom, _file_offset(site), _file_offset(site) + 4).hex() for site in bridge_callsites},
        "bridge_target": BRIDGE_RANGE[0],
        "bridge_parser_callsite": BRIDGE_PARSER_CALLSITE,
        "bridge_parser_callsite_raw_hex": _bounded(rom, _file_offset(BRIDGE_PARSER_CALLSITE), _file_offset(BRIDGE_PARSER_CALLSITE) + 4).hex(),
        "bridge_parser_target": bridge_parser_target,
        "parser_range": [_file_offset(PARSER_RANGE[0]), _file_offset(PARSER_RANGE[1])],
    }


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    return {label: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for label, path in IMPLEMENTATION_PATHS.items()}


def rebuild_from_rom(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")
    upstream = _validate_upstream_files(root)
    verifier_report = _run_upstream_verifier(root)
    _legacy_rows(upstream, rom)
    rows = _source_records(rom)
    producer = _producer_evidence(rom)
    consumer = _consumer_evidence(rom)
    bundle = b"".join(bytes.fromhex(row["raw_hex"]) for row in rows)
    if _sha(bundle) != SOURCE_SHA256:
        raise ValueError("packed source record bundle changed")
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "source_table": {"range": [SOURCE_START, SOURCE_END], "gba_range": [_gba(SOURCE_START), _gba(SOURCE_END)], "record_count": SOURCE_COUNT, "record_size": SOURCE_RECORD_SIZE, "size": SOURCE_END - SOURCE_START, "sha256": SOURCE_SHA256, "record_vector_sha256": SOURCE_VECTOR_SHA256, "name_slot_vector_sha256": NAME_SLOT_VECTOR_SHA256, "sorted_slot_vector_sha256": SORTED_SLOT_VECTOR_SHA256, "row_range_vector_sha256": ROW_RANGE_VECTOR_SHA256, "name_slot_ids": list(EXPECTED_NAME_SLOTS), "name_slot_domain": sorted(EXPECTED_NAME_SLOTS), "records": rows},
        "producer_evidence": producer,
        "consumer_evidence": consumer,
        "upstream": {"artifact_schema": "rom-selector-text-bindings-v1", "manifest": {"path": UPSTREAM_MANIFEST.as_posix(), "sha256": UPSTREAM_MANIFEST_SHA256}, "payload": {"path": UPSTREAM_PAYLOAD.as_posix(), "sha256": UPSTREAM_PAYLOAD_SHA256}, "bundle": {"path": UPSTREAM_BUNDLE.as_posix(), "sha256": UPSTREAM_BUNDLE_SHA256}, "verifier": {"path": UPSTREAM_VERIFIER.as_posix(), "sha256": UPSTREAM_VERIFIER_SHA256}, "verifier_report": verifier_report, "legacy_rows_crosschecked_from_rom": True, "legacy_record_vector_sha256": SOURCE_VECTOR_SHA256},
        "summary": {"record_count": SOURCE_COUNT, "record_bytes": SOURCE_END - SOURCE_START, "range_overlap_bytes": 0, "bundle_sha256": SOURCE_SHA256},
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": SOURCE_SHA256}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
    }
    return payload, bundle


def rebuild_payload(root: Path) -> tuple[dict[str, Any], bytes]:
    root = root.resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    return rebuild_from_rom(root, rom)


def _expected_report(payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "verified": True, "record_count": SOURCE_COUNT, "record_bytes": SOURCE_END - SOURCE_START, "bundle_sha256": SOURCE_SHA256, "record_vector_sha256": SOURCE_VECTOR_SHA256, "errors": []}


def _promotion_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA, "artifact_status": "accepted", "files": {name: _sha(raw) for name, raw in sorted(files.items())}, "rom": payload["rom"], "upstream": payload["upstream"], "scope": SCOPE, "producer": {"command": ["python3", IMPLEMENTATION_PATHS["exporter"].as_posix(), "--root", ".", "--output-dir", f"artifacts/{SCHEMA}"], **payload["implementation"]}, "verification": {"command": ["python3", IMPLEMENTATION_PATHS["verifier"].as_posix(), "--root", ".", "--artifact-dir", f"artifacts/{SCHEMA}"], "schema": VERIFY_SCHEMA, "verifier_sha256": payload["implementation"]["verifier"]["sha256"], "exit_code": 0, "report": _expected_report(payload)}}


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"artifact member is not a regular file: {name}")
    return path


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        requested = artifact_dir.expanduser()
        if not requested.is_absolute():
            requested = root / requested
        requested = _reject_symlink_components(requested)
        artifact = requested.resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("artifact path is not a directory")
        members = list(artifact.iterdir())
        if {item.name for item in members} != EXPECTED_FILES or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("artifact file denominator changed")
        expected_payload, expected_bundle = rebuild_payload(root)
        expected_payload_raw = _canonical(expected_payload)
        actual_payload_raw = _artifact_file(artifact, PAYLOAD_NAME).read_bytes()
        actual_bundle = _artifact_file(artifact, BUNDLE_NAME).read_bytes()
        if actual_payload_raw != expected_payload_raw:
            raise ValueError("artifact payload differs from independent reconstruction")
        if actual_bundle != expected_bundle:
            raise ValueError("artifact bundle differs from independent reconstruction")
        manifest_path = _artifact_file(artifact, "manifest.json")
        actual_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_manifest = _promotion_manifest(expected_payload, {PAYLOAD_NAME: expected_payload_raw, BUNDLE_NAME: expected_bundle})
        if actual_manifest != expected_manifest:
            raise ValueError("artifact manifest differs from independent reconstruction")
        return _expected_report(expected_payload)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "verified": False, "errors": [str(error)]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
