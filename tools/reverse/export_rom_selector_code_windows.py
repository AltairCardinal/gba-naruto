#!/usr/bin/env python3
"""Export the frozen selector-code source-window promotion artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


SCHEMA = "rom-selector-code-windows-v1"
VERIFY_SCHEMA = "rom-selector-code-windows-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_BASELINE_SHA256 = "d441f702add65e36dce291cfa6e6235e3ee7156cbb7b259ad47255848a581049"
COVERAGE_CLASSIFIED_BYTES = 6_091_909
COVERAGE_UNKNOWN_BYTES = 199_547
COVERAGE_BASELINE_SIZE = 21_057_965

TEXT_DIR = Path("artifacts/rom-selector-text-bindings-v1")
TEXT_MANIFEST = TEXT_DIR / "manifest.json"
TEXT_PAYLOAD = TEXT_DIR / "selector-text-bindings.json"
TEXT_BUNDLE = TEXT_DIR / "selector-text-bytes.bin"
TEXT_VERIFIER = Path("tools/verify_rom_selector_text_bindings.py")
TEXT_MANIFEST_SHA256 = "05cd987a60990ca6b2d3ee187eae963fd6ac8728ef9b42b92d6b37b5dc4bc031"
TEXT_PAYLOAD_SHA256 = "8737d04de14949cbbbb9215c892a7776476c4230eb1e2b0c2abbbbe4440ce2eb"
TEXT_BUNDLE_SHA256 = "1bc1df2046811a0399226edc53895b3c3359779d9407a6555dc0e7810d11e869"
TEXT_VERIFIER_SHA256 = "a68a0d1e036be241bbac84538d5a082c7e76e2c6331ffa1d12cd384dc79e2f18"
DIRECT_DIR = Path("artifacts/rom-selector-direct-source-records-v1")
DIRECT_MANIFEST = DIRECT_DIR / "manifest.json"
DIRECT_PAYLOAD = DIRECT_DIR / "rom-selector-direct-source-records.json"
DIRECT_BUNDLE = DIRECT_DIR / "rom-selector-direct-source-records.bin"
DIRECT_VERIFIER = Path("tools/verify_rom_selector_direct_source_records.py")
DIRECT_MANIFEST_SHA256 = "094dbb593b2b8e09849ea795f4a09155598936cd3a1bc0b36e2eda6a413cf789"
DIRECT_PAYLOAD_SHA256 = "adc03bd5e29e956c208698fedc733e305ea87e519e17dfa405ff813939149430"
DIRECT_BUNDLE_SHA256 = "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56"
DIRECT_VERIFIER_SHA256 = "510835b5d104f0009df09e3c8200beaefcb4f01836c40db7d3b1c11b475052d1"

SOURCE_START = 0x59F5F0
SOURCE_END = 0x59F988
SOURCE_COUNT = 46
SOURCE_RECORD_SIZE = 20
SOURCE_SHA256 = "a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56"
SOURCE_VECTOR_SHA256 = "065fca6237d166557a03cf30ddd309f695b825f5c850356a3c736e396d9478db"
EXPECTED_NAME_SLOTS = (
    1, 2, 3, 7, 44, 43, 4, 5, 6, 45, 8, 9, 10, 46, 11, 12, 13, 47,
    48, 30, 51, 52, 14, 15, 16, 17, 18, 19, 22, 23, 24, 29, 61, 20,
    21, 31, 49, 56, 50, 25, 26, 27, 28, 53, 54, 62,
)
NAME_SLOT_VECTOR_SHA256 = "d429cca720c928593b80289794395d0c6d266268af5da567bbe76a22c5b65ba2"
SORTED_SLOT_VECTOR_SHA256 = "42aaddfc56e36df6be859279c4a64aff4ae006e416895817c200d733eeae64a2"

PAYLOAD_NAME = "rom-selector-code-windows.json"
FULL_BUNDLE_NAME = "rom-selector-code-windows.bin"
PROMOTION_BUNDLE_NAME = "rom-selector-code-windows-promotion.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, FULL_BUNDLE_NAME, PROMOTION_BUNDLE_NAME}
IMPLEMENTATION_PATHS = {
    "exporter": Path("tools/export_rom_selector_code_windows.py"),
    "verifier": Path("tools/verify_rom_selector_code_windows.py"),
    "test": Path("tests/test_export_rom_selector_code_windows.py"),
}

WINDOW_SPECS = (
    ("renderer-parser", "decoded_semantics", "renderer_parser", 0x06626C, 0x066736, "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be", (("rom-selector-text-bindings-v1", "consumer_evidence.decoded_semantics.renderer_parser"), ("rom-selector-direct-source-records-v1", "consumer_evidence.parser"))),
    ("renderer-bridge", "decoded_semantics", "renderer_bridge", 0x066758, 0x066790, "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c", (("rom-selector-text-bindings-v1", "consumer_evidence.decoded_semantics.renderer_bridge"), ("rom-selector-direct-source-records-v1", "consumer_evidence.bridge"))),
    ("enumerator", "direct_producer", "enumerator", 0x08A6AC, 0x08A700, "68e8b80905466def5f6c4cae6fb6977336c129e7560577a77f6acac7222ca665", (("rom-selector-text-bindings-v1", "consumer_evidence.direct_producer.enumerator"), ("rom-selector-direct-source-records-v1", "producer_evidence.enumerator"))),
    ("direct-text-consumer", "decoded_semantics", "direct_text_consumer", 0x08AFE0, 0x08B07C, "9ec877cbef2c9aa100a825509cd41be605e3d20ff0304279572d7986c1865ac4", (("rom-selector-text-bindings-v1", "consumer_evidence.decoded_semantics.direct_text_consumer"), ("rom-selector-direct-source-records-v1", "consumer_evidence.direct_consumer"))),
    ("menu-selector", "direct_producer", "menu_selector", 0x08B2C8, 0x08B580, "fe12c74a937dae0e60f0ba1e566788cd4dc842596d168632c9c45809f88dd07e", (("rom-selector-text-bindings-v1", "consumer_evidence.direct_producer.menu_selector"), ("rom-selector-direct-source-records-v1", "producer_evidence.menu"))),
    ("lifecycle", "direct_producer", "lifecycle", 0x08B58C, 0x08B65A, "3b6050a3df82957c8804b86a06eb6c5b5efb8a7eca3da082dc999f74b78c7637", (("rom-selector-text-bindings-v1", "consumer_evidence.direct_producer.lifecycle"), ("rom-selector-direct-source-records-v1", "producer_evidence.lifecycle"))),
    ("three-way-mapper", "three_way_selector", "mapper", 0x08CC80, 0x08CCB4, "b496c1d67e0c22493935c1e458ca8da74e6f692543b9a879add659b9be967f3f", (("rom-selector-text-bindings-v1", "consumer_evidence.decoded_semantics.three_way_selector.mapper"),)),
    ("configured-text-consumer", "decoded_semantics", "configured_text_consumer", 0x08CD5A, 0x08CDF8, "f36813ab1237d74d65213b8ee0f696f9506f5cd85c4ab4691cddd6fd5d9da73a", (("rom-selector-text-bindings-v1", "consumer_evidence.decoded_semantics.configured_text_consumer"),)),
    ("three-way-producer", "three_way_selector", "producer", 0x097C6C, 0x097C98, "7ee4104e63d0210a67f6fba866585df11a5f8018e3660d5f378d7958ac6ec57d", (("rom-selector-text-bindings-v1", "consumer_evidence.decoded_semantics.three_way_selector.producer"),)),
    ("copy-parser", "decoded_semantics", "copy_parser", 0x09C4DC, 0x09C528, "e6fec731464677978f23752f6d0e920ba2ad91f2ff09baf18d0f65383d6508c5", (("rom-selector-text-bindings-v1", "consumer_evidence.decoded_semantics.copy_parser"),)),
)
EXPECTED_SOURCE_RANGE_HASH = "c45e828631f019ea506b0b24a0efeb16ed8508377277bc27936e8a8932fa8d43"
EXPECTED_FULL_BUNDLE_SHA256 = "4c1d5865350a66b57db7b483f68c6bf97e9c88fcd5372f021358d4ad8c917523"
EXPECTED_PROMOTION_RANGE_HASH = "1a1e50479424dbd441bc81adeca3c7d9075dc1a8ca13869e94693a71e702563e"
EXPECTED_PROMOTION_BUNDLE_SHA256 = "2207f28f0e2635b7cff09660d4440d5f8c926017583d210b748a34ac2639672b"
EXPECTED_PROMOTION_RANGES = (
    (0x0663A6, 0x0663B4), (0x0663EE, 0x0663F4), (0x066408, 0x06640C),
    (0x066420, 0x066424), (0x066438, 0x06643C), (0x0664EC, 0x0664F8),
    (0x066526, 0x066530), (0x0666CC, 0x0666F8), (0x08A6AC, 0x08A700),
    (0x08AFE0, 0x08B07C), (0x08B2C8, 0x08B2EA), (0x08B356, 0x08B580),
    (0x08B58C, 0x08B5C2), (0x08B5E6, 0x08B640), (0x08B64E, 0x08B65A),
    (0x08CD5A, 0x08CDF8), (0x097C96, 0x097C98), (0x09C4FC, 0x09C504),
    (0x09C526, 0x09C528),
)
SCOPE = {
    "primary_class": "consumer_code_slice", "claim_kind": "consumer_code_slice", "baseline_unknown_only": True,
    "instruction_only_claimed": False, "runtime_reachability_claimed": False, "safe_editing": False, "allocatable": False,
    "promotion_batch": SCHEMA, "existing_primary_bytes_preserved": 1502, "bridge_window_promotion_count": 0, "mapper_window_promotion_count": 0,
}
LIMITATIONS = [
    "The artifact freezes ten complete selector source windows and promotes only their current-unknown intersections.",
    "The 1,502 bytes already carrying a primary coverage claim remain outside promotion; no byte is re-claimed.",
    "The result is not a claim that all bytes are instructions, that natural gameplay reaches every path, or that global callers are exhaustive.",
    "Safe editing, relocation, allocatable/free-space status, and new field semantics are not claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _vector_hash(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":")).encode("ascii"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _bounded(data: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(data):
        raise ValueError("selector-code ROM slice escapes input")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4), "little")


def _thumb_bl(data: bytes, offset: int) -> int:
    first, second = _u16(data, offset), _u16(data, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("selector-code BL encoding changed")
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & 0x400000:
        delta -= 0x800000
    return offset + 4 + delta


def _bl_sites_to(data: bytes, target: int) -> list[int]:
    result = []
    for offset in range(0, len(data) - 3, 2):
        first, second = _u16(data, offset), _u16(data, offset + 2)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800 and _thumb_bl(data, offset) == target:
            result.append(offset)
    return result


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    root = root.resolve(strict=True)
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
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    root = root.resolve(strict=True)
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
    if any(member.is_symlink() for member in resolved.rglob("*")):
        raise ValueError(f"repository input directory contains a symlink: {relative}")
    return resolved


def _exact_artifact_files(root: Path, relative: Path, expected: set[str]) -> Path:
    directory = _safe_dir(root, relative)
    actual = {
        item.relative_to(directory).as_posix() for item in directory.rglob("*")
    }
    if actual != expected:
        raise ValueError(f"{relative} exact file set changed")
    return directory


def _read_json(root: Path, path: Path, expected: str) -> dict[str, Any]:
    raw = _safe_file(root, path).read_bytes()
    if _sha(raw) != expected:
        raise ValueError(f"bound source changed: {path}")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"bound JSON is not an object: {path}")
    return value


def _expected_upstream_reports() -> tuple[dict[str, Any], dict[str, Any]]:
    text = {
        "artifact_schema": "rom-selector-text-bindings-v1", "errors": [], "rom_sha256": ROM_SHA256,
        "schema": "rom-selector-text-bindings-verification-v1", "summary": {
            "classified_bytes": 816, "classified_range_count": 86, "config_bytes": 164, "config_list_count": 3,
            "config_pointer_bytes": 12, "config_pointer_slot_count": 3, "config_record_count": 38, "config_terminator_count": 3,
            "configured_physical_slot_count": 55, "configured_referenced_slot_count": 38, "configured_text_consumed_bytes": 316,
            "configured_text_unclassified_suffix_bytes": 368, "configured_unreferenced_slot_bytes": 306, "direct_source_record_bytes": 920,
            "direct_source_record_count": 46, "direct_text_candidate_slot_count": 46, "direct_text_consumed_bytes": 324,
            "direct_text_unclassified_suffix_bytes": 550, "packed_bytes": 816, "parse_failure_count": 0, "range_overlap_bytes": 0,
        }, "verified": True,
    }
    direct = {
        "artifact_schema": "rom-selector-direct-source-records-v1", "bundle_sha256": SOURCE_SHA256, "errors": [], "record_bytes": 920,
        "record_count": 46, "record_vector_sha256": SOURCE_VECTOR_SHA256, "schema": "rom-selector-direct-source-records-verification-v1", "verified": True,
    }
    return text, direct


def _validate_upstream(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _exact_artifact_files(root, TEXT_DIR, {"manifest.json", TEXT_PAYLOAD.name, TEXT_BUNDLE.name})
    _exact_artifact_files(root, DIRECT_DIR, {"manifest.json", DIRECT_PAYLOAD.name, DIRECT_BUNDLE.name})
    text_manifest, text_payload = _read_json(root, TEXT_MANIFEST, TEXT_MANIFEST_SHA256), _read_json(root, TEXT_PAYLOAD, TEXT_PAYLOAD_SHA256)
    direct_manifest, direct_payload = _read_json(root, DIRECT_MANIFEST, DIRECT_MANIFEST_SHA256), _read_json(root, DIRECT_PAYLOAD, DIRECT_PAYLOAD_SHA256)
    if _sha(_safe_file(root, TEXT_BUNDLE).read_bytes()) != TEXT_BUNDLE_SHA256 or _sha(_safe_file(root, DIRECT_BUNDLE).read_bytes()) != DIRECT_BUNDLE_SHA256:
        raise ValueError("bound selector upstream bundle changed")
    if _sha(_safe_file(root, TEXT_VERIFIER).read_bytes()) != TEXT_VERIFIER_SHA256 or _sha(_safe_file(root, DIRECT_VERIFIER).read_bytes()) != DIRECT_VERIFIER_SHA256:
        raise ValueError("bound selector upstream verifier changed")
    if (
        text_manifest.get("artifact_schema") != "rom-selector-text-bindings-v1" or text_manifest.get("artifact_status", "accepted") != "accepted" or text_manifest.get("files") != {TEXT_PAYLOAD.name: TEXT_PAYLOAD_SHA256, TEXT_BUNDLE.name: TEXT_BUNDLE_SHA256}
        or direct_manifest.get("artifact_schema") != "rom-selector-direct-source-records-v1" or direct_manifest.get("artifact_status") != "accepted" or direct_manifest.get("files") != {DIRECT_PAYLOAD.name: DIRECT_PAYLOAD_SHA256, DIRECT_BUNDLE.name: DIRECT_BUNDLE_SHA256}
        or text_payload.get("schema") != "rom-selector-text-bindings-v1" or direct_payload.get("schema") != "rom-selector-direct-source-records-v1"
    ):
        raise ValueError("upstream selector artifact contract changed")
    text_report, direct_report = _expected_upstream_reports()
    return text_payload, direct_payload, {"text": text_report, "direct": direct_report}


def _path_value(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise ValueError(f"upstream selector path missing: {path}")
        current = current[part]
    return current


def _selector_entry(payload: dict[str, Any], artifact: str, path: str, start: int, end: int, expected: str, rom: bytes) -> dict[str, Any]:
    evidence = _path_value(payload, path)
    if not isinstance(evidence, dict) or evidence.get("range") != [start, end] or evidence.get("sha256") != expected:
        raise ValueError(f"upstream selector evidence changed: {path}")
    raw = _bounded(rom, start, end)
    if _sha(raw) != expected or evidence.get("gba_range") != [_gba(start), _gba(end)]:
        raise ValueError(f"upstream selector window changed: {path}")
    if "size" in evidence and evidence["size"] != end - start:
        raise ValueError(f"upstream selector size changed: {path}")
    if "raw_hex" in evidence and evidence["raw_hex"] != raw.hex():
        raise ValueError(f"upstream selector bytes changed: {path}")
    return {"artifact_schema": artifact, "path": path, "range": [start, end], "gba_range": [_gba(start), _gba(end)], "size": end - start, "sha256": expected}


def _validate_source_domain(rom: bytes, text_payload: dict[str, Any], direct_payload: dict[str, Any]) -> dict[str, Any]:
    if _sha(_bounded(rom, SOURCE_START, SOURCE_END)) != SOURCE_SHA256:
        raise ValueError("selector source table changed")
    vector, slots = [], []
    for source_id in range(SOURCE_COUNT):
        start = SOURCE_START + source_id * SOURCE_RECORD_SIZE
        row = _bounded(rom, start, start + SOURCE_RECORD_SIZE)
        if row[0] != source_id:
            raise ValueError("selector domain source id changed")
        vector.append([source_id, start, row[0], row[1]])
        slots.append(row[1])
    if _vector_hash(vector) != SOURCE_VECTOR_SHA256 or tuple(slots) != EXPECTED_NAME_SLOTS or _vector_hash(slots) != NAME_SLOT_VECTOR_SHA256 or _vector_hash(sorted(slots)) != SORTED_SLOT_VECTOR_SHA256:
        raise ValueError("selector domain slot vector changed")
    rows = direct_payload.get("source_table", {}).get("records")
    if not isinstance(rows, list) or len(rows) != SOURCE_COUNT:
        raise ValueError("upstream direct selector domain count changed")
    for source_id, row in enumerate(rows):
        start = SOURCE_START + source_id * SOURCE_RECORD_SIZE
        if row.get("source_id") != source_id or row.get("name_slot_id", row.get("name_slot")) != slots[source_id] or row.get("range") != [start, start + SOURCE_RECORD_SIZE]:
            raise ValueError("upstream direct selector domain changed")
    producer = text_payload.get("consumer_evidence", {}).get("direct_producer", {})
    if producer.get("source_record_count") != 46 or producer.get("source_record_size") != 20 or producer.get("name_slot_domain") != sorted(EXPECTED_NAME_SLOTS):
        raise ValueError("upstream selector domain changed")
    selector = text_payload.get("consumer_evidence", {}).get("decoded_semantics", {}).get("three_way_selector", {})
    if selector.get("output_domain") != [0, 1, 2]:
        raise ValueError("selector output domain changed")
    return {"source_record_count": 46, "source_record_size": 20, "name_slot_domain": sorted(EXPECTED_NAME_SLOTS), "output_domain": [0, 1, 2]}


def _validate_selector_semantics(root: Path, rom: bytes) -> None:
    del root
    if tuple(_u16(rom, offset) for offset in range(0x08B02C, 0x08B03A, 2)) != (0x7871, 0x0088, 0x1840, 0x0080, 0x1A40, 0x4913, 0x1840) or _u32(rom, 0x08B084) != ROM_BASE + 0x5A5AB8:
        raise ValueError("selector stride semantic contract changed")
    mapper = (0xB500, 0x0400, 0x1400, 0x2801, 0xDD11, 0x2808, 0xDD0D, 0x2817, 0xDD0D, 0x281E, 0xDC01, 0x2002, 0xE00A, 0x2832, 0xDD07, 0x2833, 0xD003, 0x2834, 0xD003, 0x2835, 0xD101, 0x2001, 0xE000, 0x2000, 0xBC02, 0x4708)
    if tuple(_u16(rom, 0x08CC80 + 2 * index) for index in range(26)) != mapper or _u16(rom, 0x097C82) != 0x7520 or _thumb_bl(rom, 0x097C7E) != 0x08CC80:
        raise ValueError("selector output domain semantic contract changed")
    if _thumb_bl(rom, 0x06678A) != 0x06626C or _thumb_bl(rom, 0x08CD94) != 0x09C4DC:
        raise ValueError("selector parser boundary semantic contract changed")
    bridge_sites = [0x08B010, 0x08B028, 0x08B044, 0x08B054, 0x08B062, 0x08B076]
    if any(_thumb_bl(rom, site) != 0x066758 for site in bridge_sites):
        raise ValueError("selector BL callsite semantic contract changed")
    direct_sites = [0x08B420, 0x08B51A]
    if any(_thumb_bl(rom, site) != 0x08AFE0 for site in direct_sites):
        raise ValueError("selector direct BL callsite semantic contract changed")
    if _bl_sites_to(rom, 0x08AFE0) != direct_sites:
        raise ValueError("selector direct BL denominator changed")


def _validate_direct_upstream_semantics(text_payload: dict[str, Any], direct_payload: dict[str, Any]) -> None:
    consumer_evidence = direct_payload.get("consumer_evidence", {})
    consumer = consumer_evidence.get("direct_consumer", {})
    if consumer_evidence.get("direct_consumer_callsites") != [0x0808B420, 0x0808B51A] or consumer_evidence.get("record_stride_bytes") != 19:
        raise ValueError("upstream direct consumer selector changed")
    text_consumer = text_payload.get("consumer_evidence", {}).get("decoded_semantics", {}).get("direct_text_consumer", {})
    if text_consumer.get("record_stride") != 19 or text_consumer.get("renderer_bridge_target") != "0x08066758":
        raise ValueError("upstream direct consumer selector changed")
    mapper = text_payload.get("consumer_evidence", {}).get("decoded_semantics", {}).get("three_way_selector", {})
    if mapper.get("output_domain") != [0, 1, 2] or mapper.get("mapper_call_offset") != 621694 or mapper.get("output_store_offset") != 621698:
        raise ValueError("upstream selector mapper contract changed")


def _make_windows(rom: bytes, text_payload: dict[str, Any], direct_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], bytes]:
    windows, parts, cursor = [], [], 0
    for ident, kind, role, start, end, expected, selectors in WINDOW_SPECS:
        raw = _bounded(rom, start, end)
        if _sha(raw) != expected:
            raise ValueError(f"selector source window changed: {ident}")
        evidence = [_selector_entry(text_payload if artifact == "rom-selector-text-bindings-v1" else direct_payload, artifact, path, start, end, expected, rom) for artifact, path in selectors]
        windows.append({"id": ident, "source_kind": kind, "role": role, "range": [start, end], "gba_range": [_gba(start), _gba(end)], "size": end - start, "raw_sha256": _sha(raw), "packed_range": [cursor, cursor + len(raw)], "packed_sha256": _sha(raw), "selector_evidence": evidence, "provenance": {"rom": {"path": ROM_PATH.as_posix(), "range": [start, end], "sha256": _sha(raw)}, "upstream_selector_paths": [item["artifact_schema"] + ":" + item["path"] for item in evidence]}})
        parts.append(raw)
        cursor += len(raw)
    bundle = b"".join(parts)
    if len(bundle) != 2754 or _sha(bundle) != EXPECTED_FULL_BUNDLE_SHA256 or _vector_hash([list(spec[3:5]) for spec in WINDOW_SPECS]) != EXPECTED_SOURCE_RANGE_HASH:
        raise ValueError("selector full source bundle or range denominator changed")
    return windows, bundle


def _batch_claim_is_valid(claim: dict[str, Any], rom: bytes) -> bool:
    value = claim.get("range")
    if (
        not isinstance(value, list)
        or len(value) != 2
        or tuple(value) not in EXPECTED_PROMOTION_RANGES
    ):
        return False
    start, end = value
    return (
        claim.get("role") == "primary"
        and claim.get("primary_class") == "consumer_code_slice"
        and claim.get("claim_kind") == "consumer_code_slice"
        and claim.get("promotion_batch") == SCHEMA
        and claim.get("promoted_from_primary_class") == "unknown"
        and claim.get("baseline_unknown_only") is True
        and claim.get("instruction_only_claimed") is False
        and claim.get("runtime_reachability_claimed") is False
        and claim.get("safe_editing") is False
        and claim.get("allocatable") is False
        and claim.get("bytes_sha256") == _sha(_bounded(rom, start, end))
    )


def _load_coverage(
    root: Path, rom: bytes, windows: list[dict[str, Any]]
) -> tuple[list[tuple[int, int]], int]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    coverage = json.loads(raw.decode("utf-8"))
    if coverage.get("schema") != "rom-byte-coverage-v1" or coverage.get("base_rom") != {"path": ROM_PATH.as_posix(), "sha256": ROM_SHA256, "size": ROM_SIZE}:
        raise ValueError("coverage ROM identity changed")
    if coverage.get("domain") != [0, ROM_SIZE] or coverage.get("state_inventory_complete") is not True:
        raise ValueError("coverage domain/state inventory changed")
    claims = coverage.get("claims")
    if not isinstance(claims, list):
        raise ValueError("coverage claims missing")
    claims_by_id: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("id"), str):
            raise ValueError("coverage claim shape changed")
        if claim["id"] in claims_by_id:
            raise ValueError("coverage claim IDs are not unique")
        claims_by_id[claim["id"]] = claim
    batch_claims = [claim for claim in claims if claim.get("promotion_batch") == SCHEMA]
    batch_claim_ids = {claim["id"] for claim in batch_claims}
    if batch_claims:
        if (
            not all(_batch_claim_is_valid(claim, rom) for claim in batch_claims)
            or sorted(tuple(claim["range"]) for claim in batch_claims)
            != list(EXPECTED_PROMOTION_RANGES)
        ):
            raise ValueError("coverage selector batch claim denominator changed")
    summary = coverage.get("summary", {})
    segments = coverage.get("segments")
    if not isinstance(segments, list):
        raise ValueError("coverage segments missing")
    consumer_code_slice_bytes = 0
    consumer_code_slice_claim_count = 0
    for claim in claims:
        if claim.get("claim_kind") != "consumer_code_slice":
            continue
        claim_range = claim.get("range")
        if (
            not isinstance(claim_range, list)
            or len(claim_range) != 2
            or not all(isinstance(value, int) for value in claim_range)
            or not 0 <= claim_range[0] < claim_range[1] <= ROM_SIZE
        ):
            raise ValueError("coverage consumer code claim range changed")
        consumer_code_slice_bytes += claim_range[1] - claim_range[0]
        consumer_code_slice_claim_count += 1
    previous = classified = unknown = 0
    owned_batch_claim_ids: set[str] = set()
    for segment in segments:
        start, end = segment.get("range", [None, None])
        if start != previous or not isinstance(start, int) or not isinstance(end, int) or not start < end:
            raise ValueError("coverage segment partition changed")
        if segment.get("primary_class") == "unknown":
            if segment.get("primary_claim_ids") not in ([], None):
                raise ValueError("coverage unknown segment has primary claims")
            unknown += end - start
        else:
            primary_ids = segment.get("primary_claim_ids")
            if not isinstance(primary_ids, list) or not primary_ids:
                raise ValueError("coverage classified segment lacks primary claims")
            if any(claim_id not in claims_by_id for claim_id in primary_ids):
                raise ValueError("coverage segment references a missing primary claim")
            for claim_id in primary_ids:
                claim = claims_by_id[claim_id]
                claim_range = claim.get("range")
                if (
                    claim.get("role") != "primary"
                    or claim.get("primary_class") != segment.get("primary_class")
                    or not isinstance(claim_range, list)
                    or len(claim_range) != 2
                    or not all(isinstance(value, int) for value in claim_range)
                    or not claim_range[0] <= start < end <= claim_range[1]
                ):
                    raise ValueError("coverage segment primary claim ownership changed")
                if claim_id in batch_claim_ids:
                    owned_batch_claim_ids.add(claim_id)
            classified += end - start
        previous = end
    if (
        previous != ROM_SIZE
        or summary.get("accounted_bytes") != ROM_SIZE
        or summary.get("classified_bytes") != classified
        or summary.get("unknown_bytes") != unknown
        or summary.get("claim_count") != len(claims)
        or summary.get("segment_count") != len(segments)
        or summary.get("consumer_code_slice_bytes")
        != consumer_code_slice_bytes
        or summary.get("consumer_code_slice_claim_count")
        != consumer_code_slice_claim_count
    ):
        raise ValueError("coverage byte totals changed")
    if owned_batch_claim_ids != batch_claim_ids:
        raise ValueError("coverage selector batch claim ownership changed")

    def eligible(segment: dict[str, Any]) -> bool:
        if segment.get("primary_class") == "unknown":
            return True
        primary_ids = segment.get("primary_claim_ids", [])
        return bool(primary_ids) and all(
            claim_id in batch_claim_ids for claim_id in primary_ids
        )

    projected, primary = [], 0
    for window in windows:
        ws, we = window["range"]
        for segment in segments:
            ss, se = segment["range"]
            start, end = max(ws, ss), min(we, se)
            if start >= end:
                continue
            if eligible(segment):
                if projected and projected[-1][1] == start:
                    projected[-1] = (projected[-1][0], end)
                else:
                    projected.append((start, end))
            else:
                primary += end - start
    if tuple(projected) != EXPECTED_PROMOTION_RANGES or sum(end - start for start, end in projected) != 1252 or primary != 1502 or _vector_hash([list(item) for item in projected]) != EXPECTED_PROMOTION_RANGE_HASH:
        raise ValueError("selector coverage projection changed")
    return projected, primary


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    return {label: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for label, path in IMPLEMENTATION_PATHS.items()}


def _upstream_payload(text_report: dict[str, Any], direct_report: dict[str, Any]) -> dict[str, Any]:
    return {"artifacts": {"rom-selector-text-bindings-v1": {"manifest": {"path": TEXT_MANIFEST.as_posix(), "sha256": TEXT_MANIFEST_SHA256}, "payload": {"path": TEXT_PAYLOAD.as_posix(), "sha256": TEXT_PAYLOAD_SHA256}, "bundle": {"path": TEXT_BUNDLE.as_posix(), "sha256": TEXT_BUNDLE_SHA256}, "verifier": {"path": TEXT_VERIFIER.as_posix(), "sha256": TEXT_VERIFIER_SHA256}, "verifier_report": text_report}, "rom-selector-direct-source-records-v1": {"manifest": {"path": DIRECT_MANIFEST.as_posix(), "sha256": DIRECT_MANIFEST_SHA256}, "payload": {"path": DIRECT_PAYLOAD.as_posix(), "sha256": DIRECT_PAYLOAD_SHA256}, "bundle": {"path": DIRECT_BUNDLE.as_posix(), "sha256": DIRECT_BUNDLE_SHA256}, "verifier": {"path": DIRECT_VERIFIER.as_posix(), "sha256": DIRECT_VERIFIER_SHA256}, "verifier_report": direct_report}}}


def rebuild_from_rom(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes, bytes]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("fixed ROM identity changed")
    text_payload, direct_payload, reports = _validate_upstream(root)
    _validate_source_domain(rom, text_payload, direct_payload)
    _validate_direct_upstream_semantics(text_payload, direct_payload)
    _validate_selector_semantics(root, rom)
    windows, full_bundle = _make_windows(rom, text_payload, direct_payload)
    projection, primary_overlap = _load_coverage(root, rom, windows)
    promotions, parts, cursor = [], [], 0
    for index, (start, end) in enumerate(projection):
        raw = _bounded(rom, start, end)
        owner = next(window for window in windows if window["range"][0] <= start < window["range"][1])
        promotions.append({"id": f"promotion-{index:02d}", "source_window_id": owner["id"], "range": [start, end], "gba_range": [_gba(start), _gba(end)], "size": end - start, "raw_sha256": _sha(raw), "packed_range": [cursor, cursor + len(raw)], "packed_sha256": _sha(raw), "primary_class": "consumer_code_slice", "claim_kind": "consumer_code_slice", "baseline_unknown_only": True, "instruction_only_claimed": False, "runtime_reachability_claimed": False, "safe_editing": False, "allocatable": False, "promotion_batch": SCHEMA, "coverage_source": {"path": COVERAGE_PATH.as_posix(), "baseline_observation_sha256": COVERAGE_BASELINE_SHA256, "accepted_live_primary_states": ["unknown", SCHEMA]}})
        parts.append(raw)
        cursor += len(raw)
    promotion_bundle = b"".join(parts)
    if len(promotion_bundle) != 1252 or _sha(promotion_bundle) != EXPECTED_PROMOTION_BUNDLE_SHA256:
        raise ValueError("selector promotion bundle changed")
    bridge_count = sum(item["source_window_id"] == "renderer-bridge" for item in promotions)
    mapper_count = sum(item["source_window_id"] == "three-way-mapper" for item in promotions)
    if bridge_count or mapper_count:
        raise ValueError("selector bridge/mapper promotion contract changed")
    summary = {"source_window_count": len(windows), "source_window_bytes": sum(item["size"] for item in windows), "promotion_range_count": len(promotions), "promotion_bytes": sum(item["size"] for item in promotions), "primary_overlap_bytes": primary_overlap, "source_window_range_denominator_sha256": EXPECTED_SOURCE_RANGE_HASH, "promotion_range_denominator_sha256": EXPECTED_PROMOTION_RANGE_HASH, "full_bundle_sha256": EXPECTED_FULL_BUNDLE_SHA256, "promotion_bundle_sha256": EXPECTED_PROMOTION_BUNDLE_SHA256, "bridge_promotion_count": bridge_count, "mapper_promotion_count": mapper_count}
    payload = {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}, "coverage": {"path": COVERAGE_PATH.as_posix(), "baseline_observation": {"size": COVERAGE_BASELINE_SIZE, "sha256": COVERAGE_BASELINE_SHA256, "classified_bytes": COVERAGE_CLASSIFIED_BYTES, "unknown_bytes": COVERAGE_UNKNOWN_BYTES}, "live_hash_pinned": False, "live_hash_pin_omission_reason": "coverage incorporates this artifact's claims; the verifier accepts only unknown or this exact batch while rebuilding the same projection", "accepted_live_primary_states": ["unknown", SCHEMA], "primary_overlap_bytes": primary_overlap}, "upstream": _upstream_payload(reports["text"], reports["direct"]), "selector_domain": _validate_source_domain(rom, text_payload, direct_payload), "source_windows": windows, "promotion_ranges": promotions, "source_window_range_denominator_sha256": EXPECTED_SOURCE_RANGE_HASH, "promotion_range_denominator_sha256": EXPECTED_PROMOTION_RANGE_HASH, "bundles": {"full_source_windows": {"file": FULL_BUNDLE_NAME, "size": len(full_bundle), "sha256": EXPECTED_FULL_BUNDLE_SHA256}, "promotion_ranges": {"file": PROMOTION_BUNDLE_NAME, "size": len(promotion_bundle), "sha256": EXPECTED_PROMOTION_BUNDLE_SHA256}}, "files": {FULL_BUNDLE_NAME: {"size": len(full_bundle), "sha256": EXPECTED_FULL_BUNDLE_SHA256}, PROMOTION_BUNDLE_NAME: {"size": len(promotion_bundle), "sha256": EXPECTED_PROMOTION_BUNDLE_SHA256}}, "summary": summary, "scope": SCOPE, "limitations": LIMITATIONS, "implementation": _implementation(root)}
    return payload, full_bundle, promotion_bundle


def rebuild_payload(root: Path) -> tuple[dict[str, Any], bytes, bytes]:
    root = root.resolve(strict=True)
    return rebuild_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())


def build_payload(root: Path) -> tuple[dict[str, Any], bytes, bytes]:
    return rebuild_payload(root)


def _expected_report(payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema": VERIFY_SCHEMA, "artifact_schema": SCHEMA, "verified": True, **payload["summary"], "errors": []}


def _expected_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA, "artifact_status": "accepted", "files": {name: _sha(raw) for name, raw in sorted(files.items())}, "rom": payload["rom"], "coverage": payload["coverage"], "upstream": payload["upstream"], "scope": SCOPE, "producer": {"command": ["python3", IMPLEMENTATION_PATHS["exporter"].as_posix(), "--root", ".", "--output-dir", f"artifacts/{SCHEMA}"], **payload["implementation"]}, "verification": {"command": ["python3", IMPLEMENTATION_PATHS["verifier"].as_posix(), "--root", ".", "--artifact-dir", f"artifacts/{SCHEMA}"], "schema": VERIFY_SCHEMA, "verifier_sha256": payload["implementation"]["verifier"]["sha256"], "exit_code": 0, "report": _expected_report(payload)}}


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact output path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("artifact output must not be the repository root or an ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("artifact output is not replaceable")
    members = list(target.rglob("*"))
    if any(member.is_symlink() for member in members):
        raise ValueError("artifact output contains a symlink")
    actual = {member.relative_to(target).as_posix() for member in members}
    if actual != EXPECTED_FILES:
        raise ValueError("artifact output is not replaceable: exact file set changed")
    try:
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("artifact output is not replaceable: manifest invalid") from error
    if manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") != "accepted":
        raise ValueError("artifact output is not replaceable: foreign artifact")
    return target


def _install_new(root: Path, target: Path, files: dict[str, bytes], manifest: dict[str, Any], expected_report: dict[str, Any]) -> None:
    target = _reject_symlink_components(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(target.parent)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup: Path | None = None
    try:
        for name, raw in files.items():
            (temporary / name).write_bytes(raw)
        (temporary / "manifest.json").write_bytes(_canonical(manifest))
        completed = subprocess.run([sys.executable, str(_safe_file(root, IMPLEMENTATION_PATHS["verifier"])), "--root", str(root), "--artifact-dir", str(temporary)], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        try:
            report = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("independent verifier returned invalid JSON") from error
        if completed.returncode != 0 or report != expected_report:
            raise ValueError(f"independent verifier rejected candidate artifact: exit={completed.returncode}, report={report}, stderr={completed.stderr.decode('utf-8', 'replace')}")
        if target.exists():
            backup = target.parent / f".{target.name}.old-{os.getpid()}"
            if backup.exists():
                raise ValueError("artifact replacement staging path already exists")
            os.replace(target, backup)
        os.replace(temporary, target)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
            backup = None
    except Exception:
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
            backup = None
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    target = _validate_output(root, output_dir)
    payload, full_bundle, promotion_bundle = rebuild_payload(root)
    files = {PAYLOAD_NAME: _canonical(payload), FULL_BUNDLE_NAME: full_bundle, PROMOTION_BUNDLE_NAME: promotion_bundle}
    _install_new(root, target, files, _expected_manifest(payload, files), _expected_report(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
