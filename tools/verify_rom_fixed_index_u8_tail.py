#!/usr/bin/env python3
"""Independently rebuild and verify the fixed-index u8 tail artifact."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.rom_fixed_index_u8_tail_contract import *


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe repository-relative input")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("input symlink rejected")
    value = (root / relative).resolve(strict=True)
    if not value.is_relative_to(root) or not value.is_file():
        raise ValueError("input escapes repository")
    return value


def _safe_artifact(root: Path, artifact: Path) -> Path:
    lexical = artifact if artifact.is_absolute() else root / artifact
    if not lexical.is_relative_to(root):
        raise ValueError("artifact escapes repository")
    cursor = root
    for part in lexical.relative_to(root).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact symlink rejected")
    value = lexical.resolve(strict=True)
    if not value.is_relative_to(root) or not value.is_dir():
        raise ValueError("artifact is not a safe directory")
    return value


def _decode_bl(raw: bytes, source: int) -> int | None:
    if source & 1 or source + 4 > len(raw):
        return None
    high = raw[source] | raw[source + 1] << 8
    low = raw[source + 2] | raw[source + 3] << 8
    if high >> 11 != 0b11110 or low >> 11 != 0b11111:
        return None
    signed = ((high & 0x7FF) << 12) + ((low & 0x7FF) << 1)
    signed = signed - 0x800000 if signed >= 0x400000 else signed
    return source + 4 + signed


def _raw_scan_calls(raw: bytes) -> list[int]:
    found, source = [], 0
    while source + 4 <= len(raw):
        if _decode_bl(raw, source) == CALL_TARGET:
            found.append(source)
        source += 2
    return found


def _raw_scan_word(raw: bytes) -> list[int]:
    found, cursor = [], 0
    while True:
        cursor = raw.find(LITERAL_RAW, cursor)
        if cursor < 0:
            return found
        found.append(cursor)
        cursor += 1


def _raw_scan_ldr_to_literal(raw: bytes) -> list[int]:
    found = []
    for source in range(0, len(raw) - 1, 2):
        opcode = raw[source] | raw[source + 1] << 8
        if opcode >> 11 == 0b01001:
            resolved = ((source + 4) & 0xFFFFFFFC) + ((opcode & 0xFF) << 2)
            if resolved == LITERAL_RANGE[0]:
                found.append(source)
    return found


def _segment(coverage: dict[str, Any], offset: int) -> dict[str, Any]:
    rows = [item for item in coverage.get("segments", [])
            if item.get("range", [0, 0])[0] <= offset < item.get("range", [0, 0])[1]]
    if len(rows) != 1:
        raise ValueError("coverage segment denominator changed")
    return rows[0]


def _assert_owner_range(
    coverage: dict[str, Any],
    expected_range: tuple[int, int],
    expected_class: str,
    expected_ids: tuple[str, ...],
) -> None:
    start, end = expected_range
    if start < 0 or end <= start:
        raise ValueError("invalid provenance owner range")
    rows = sorted(
        (
            item
            for item in coverage.get("segments", [])
            if item.get("range", [0, 0])[0] < end
            and item.get("range", [0, 0])[1] > start
        ),
        key=lambda item: tuple(item["range"]),
    )
    cursor = start
    for item in rows:
        item_start, item_end = item["range"]
        covered_start = max(start, item_start)
        covered_end = min(end, item_end)
        if covered_start != cursor or covered_end <= covered_start:
            raise ValueError("provenance owner range has a gap or overlap")
        if (
            item.get("primary_class") != expected_class
            or tuple(item.get("primary_claim_ids", ())) != expected_ids
            or item.get("secondary_claim_ids") != []
        ):
            raise ValueError("provenance owner changed within range")
        cursor = covered_end
    if cursor != end:
        raise ValueError("provenance owner range is not fully covered")


def _coverage_contract(root: Path) -> dict[str, Any]:
    artifact = (root / PRECOVERAGE_ARTIFACT).resolve(strict=True)
    if not artifact.is_relative_to(root) or not artifact.is_dir():
        raise ValueError("precoverage artifact escaped repository")
    if {item.name for item in artifact.iterdir()} != {
        "manifest.json", PRECOVERAGE_ARCHIVE_NAME
    }:
        raise ValueError("precoverage artifact members changed")
    manifest_raw = _safe_file(
        root, PRECOVERAGE_ARTIFACT / "manifest.json").read_bytes()
    archive_raw = _safe_file(
        root, PRECOVERAGE_ARTIFACT / PRECOVERAGE_ARCHIVE_NAME).read_bytes()
    if (
        len(manifest_raw) != PRECOVERAGE_MANIFEST_SIZE
        or _sha(manifest_raw) != PRECOVERAGE_MANIFEST_SHA256
        or len(archive_raw) != PRECOVERAGE_ARCHIVE_SIZE
        or _sha(archive_raw) != PRECOVERAGE_ARCHIVE_SHA256
    ):
        raise ValueError("precoverage artifact identity changed")
    manifest = json.loads(manifest_raw)
    if (
        manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("source") != {
            "path": COVERAGE_PATH.as_posix(),
            "sha256": COVERAGE_SHA256,
            "size": COVERAGE_SIZE,
        }
    ):
        raise ValueError("precoverage manifest contract changed")
    raw = gzip.decompress(archive_raw)
    if len(raw) != COVERAGE_SIZE or _sha(raw) != COVERAGE_SHA256:
        raise ValueError("precoverage raw identity changed")
    value = json.loads(raw)
    if value.get("schema") != "rom-byte-coverage-v1" or value.get("base_rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("coverage schema or ROM changed")
    _assert_owner_range(value, CANDIDATE_RANGE, "unknown", ())
    for expected_range, expected_class, ids in OWNER_SEGMENTS:
        _assert_owner_range(value, expected_range, expected_class, ids)
    return {"path": COVERAGE_PATH.as_posix(), "size": len(raw), "sha256": _sha(raw),
            "snapshot_artifact": PRECOVERAGE_ARTIFACT.as_posix(),
            "snapshot_manifest_sha256": PRECOVERAGE_MANIFEST_SHA256,
            "snapshot_archive_sha256": PRECOVERAGE_ARCHIVE_SHA256,
            "candidate_current_unknown": True, "provenance_owners_preserved": True}


def _semantic_rebuild(raw: bytes) -> dict[str, Any]:
    candidate = raw[slice(*CANDIDATE_RANGE)]
    if candidate != CANDIDATE_RAW or _sha(candidate) != CANDIDATE_SHA256:
        raise ValueError("candidate bytes changed")
    if _sha(raw[slice(*CONSUMER_RANGE)]) != CONSUMER_SHA256:
        raise ValueError("consumer bytes changed")
    proof = raw[slice(*PROOF_RANGE)]
    if proof != PROOF_RAW or _sha(proof) != PROOF_SHA256:
        raise ValueError("consumer proof changed")
    if struct.unpack("<6H", proof) != (0x0600, 0x0E00, 0x4D21, 0x4A22, 0x1880, 0x7800):
        raise ValueError("consumer u8 lookup semantics changed")
    literal = raw[slice(*LITERAL_RANGE)]
    if literal != LITERAL_RAW or _sha(literal) != LITERAL_SHA256 or int.from_bytes(literal, "little") != LITERAL_VALUE:
        raise ValueError("literal identity changed")
    occurrences, loads, calls = _raw_scan_word(raw), _raw_scan_ldr_to_literal(raw), _raw_scan_calls(raw)
    if occurrences != [LITERAL_RANGE[0]]:
        raise ValueError("word occurrence denominator changed")
    if loads != [0x07C72E]:
        raise ValueError("literal LDR denominator changed")
    if calls != list(CALL_OFFSETS):
        raise ValueError("BL denominator changed")
    fixed_rows, concat = [], bytearray()
    for index, (start, end, expected, digest) in enumerate(CALLER_WINDOWS):
        window = raw[start:end]
        concat.extend(window)
        if window != expected or _sha(window) != digest:
            raise ValueError("fixed caller bytes changed")
        mov_r0, mov_r1 = struct.unpack_from("<HH", window)
        call = start + 4
        if mov_r0 != (0x2000 | FIXED_INDICES[index]) or mov_r1 != 0x2100 or _decode_bl(raw, call) != CALL_TARGET:
            raise ValueError("fixed caller semantics changed")
        fixed_rows.append({"file_range": [start, end], "call_offset": call,
                           "index_u8": FIXED_INDICES[index], "raw_hex": window.hex(),
                           "sha256": _sha(window)})
    if _sha(bytes(concat)) != CALLER_CONCAT_SHA256:
        raise ValueError("fixed caller order changed")
    return {"target_limited_bl_offsets": calls, "target_limited_bl_count": 13,
            "fixed_immediate_callers": fixed_rows,
            "excluded_non_fixed_call_offsets": list(EXCLUDED_NON_FIXED_CALL_OFFSETS),
            "literal_word_occurrences": occurrences, "literal_ldr_offsets": loads}


def _rebuild_from_rom(root: Path, raw: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if verify_identity and (len(raw) != ROM_SIZE or _sha(raw) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    denominator = _semantic_rebuild(raw)
    coverage = _coverage_contract(root)
    claim = {"id": "fixed-index-u8-tail-53e492", "role": "primary",
             "primary_class": "fixed_index_u8_lookup_tail",
             "claim_kind": "fixed_index_u8_lookup_tail_bytes",
             "range": list(CANDIDATE_RANGE), "byte_size": 4,
             "bytes_sha256": CANDIDATE_SHA256, "promoted_from_primary_class": "unknown"}
    return {"schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(raw), "sha256": ROM_SHA256},
            "coverage_baseline": coverage,
            "lookup_binding": {"logical_base_file_offset": TABLE_BASE,
                               "consumer_index_width": "u8", "load_width": "u8",
                               "address_expression": "0x0853E424 + u8(r0)",
                               "fixed_indices": list(FIXED_INDICES),
                               "candidate_range": list(CANDIDATE_RANGE),
                               "candidate_raw_hex": CANDIDATE_RAW.hex(),
                               "candidate_values_u8": list(raw[slice(*CANDIDATE_RANGE)]),
                               "candidate_sha256": CANDIDATE_SHA256},
            "consumer": {"range": list(CONSUMER_RANGE), "sha256": CONSUMER_SHA256,
                         "proof_range": list(PROOF_RANGE), "proof_sha256": PROOF_SHA256,
                         "proof_raw_hex": PROOF_RAW.hex(), "literal_range": list(LITERAL_RANGE),
                         "literal_value": LITERAL_VALUE, "literal_sha256": LITERAL_SHA256},
            "caller_denominator": denominator,
            "promotion": {"promotion_batch": SCHEMA, "claims": [claim],
                          "claim_count": 1, "promotion_bytes": 4,
                          "range_order": "file_offset_ascending"},
            "scope": NON_CLAIMS}


def rebuild_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _rebuild_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())


def verify_artifact(root: Path, artifact: Path, *, expected_artifact: Path | None = None) -> dict[str, Any]:
    try:
        root = root.resolve(strict=True)
        directory = _safe_artifact(root, artifact)
        members = list(directory.iterdir())
        if {path.name for path in members} != {PAYLOAD_NAME, MANIFEST_NAME}:
            raise ValueError("artifact file denominator changed")
        if any(path.is_symlink() or not path.is_file() for path in members):
            raise ValueError("artifact member type changed")
        payload_raw = (directory / PAYLOAD_NAME).read_bytes()
        manifest_raw = (directory / MANIFEST_NAME).read_bytes()
        payload, manifest = json.loads(payload_raw), json.loads(manifest_raw)
        if payload_raw != _canonical(payload) or manifest_raw != _canonical(manifest):
            raise ValueError("artifact JSON is not canonical")
        if payload != rebuild_payload(root):
            raise ValueError("payload contract changed")
        receipt = expected_artifact if expected_artifact is not None else directory
        receipt = receipt if receipt.is_absolute() else root / receipt
        relative = receipt.resolve(strict=False).relative_to(root).as_posix()
        paths = {"contract": CONTRACT_PATH, "exporter": EXPORTER_PATH,
                 "verifier": VERIFIER_PATH, "test": TEST_PATH}
        expected_manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
            "artifact_status": "accepted",
            "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
            "summary": {"promotion_bytes": 4, "claim_count": 1,
                        "target_limited_bl_count": 13, "fixed_caller_count": 4},
            "producer": {"command": ["python3", EXPORTER_PATH.as_posix(), "--root", ".", "--output", relative]},
            "verifier": {"command": ["python3", VERIFIER_PATH.as_posix(), "--root", ".", "--artifact", relative]},
            "implementation": {name + "_sha256": _sha(_safe_file(root, path).read_bytes())
                               for name, path in paths.items()}}
        if manifest != expected_manifest:
            raise ValueError("manifest contract changed")
        return {"schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True,
                "errors": [], "promotion_bytes": 4, "claim_count": 1,
                "target_limited_bl_count": 13, "fixed_caller_count": 4,
                "excluded_non_fixed_call_count": 9}
    except Exception as error:
        return {"schema": VERIFY_SCHEMA, "verified": False, "contract_ok": False,
                "errors": [str(error)], "promotion_bytes": 0, "claim_count": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
