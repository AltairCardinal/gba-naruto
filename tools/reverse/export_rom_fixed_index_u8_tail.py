#!/usr/bin/env python3
"""Export the four fixed-immediate u8 lookup bytes at 0x53E492."""

from __future__ import annotations

import argparse
import ctypes
import errno
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
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
        raise ValueError("unsafe repository-relative path")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("input has symlink member or ancestor")
    result = (root / relative).resolve(strict=True)
    if not result.is_relative_to(root) or not result.is_file():
        raise ValueError("input escapes repository")
    return result


def _thumb_bl_target(raw: bytes, source: int) -> int | None:
    if source < 0 or source + 4 > len(raw) or source & 1:
        return None
    high, low = struct.unpack_from("<HH", raw, source)
    if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
        return None
    delta = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if delta & 0x400000:
        delta -= 0x800000
    return source + 4 + delta


def _scan_target_bl(raw: bytes, target: int) -> list[int]:
    return [offset for offset in range(0, len(raw) - 3, 2)
            if _thumb_bl_target(raw, offset) == target]


def _scan_word(raw: bytes, word: bytes) -> list[int]:
    return [offset for offset in range(len(raw) - 3) if raw[offset:offset + 4] == word]


def _scan_literal_loads(raw: bytes, literal_offset: int) -> list[int]:
    result = []
    for offset in range(0, len(raw) - 1, 2):
        instruction = int.from_bytes(raw[offset:offset + 2], "little")
        if instruction & 0xF800 != 0x4800:
            continue
        target = ((offset + 4) & ~3) + (instruction & 0xFF) * 4
        if target == literal_offset:
            result.append(offset)
    return result


def _segment_at(coverage: dict[str, Any], offset: int) -> dict[str, Any]:
    matches = [row for row in coverage.get("segments", [])
               if row.get("range", [0, 0])[0] <= offset < row.get("range", [0, 0])[1]]
    if len(matches) != 1:
        raise ValueError(f"coverage segment denominator changed at 0x{offset:06X}")
    return matches[0]


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
            row
            for row in coverage.get("segments", [])
            if row.get("range", [0, 0])[0] < end
            and row.get("range", [0, 0])[1] > start
        ),
        key=lambda row: tuple(row["range"]),
    )
    cursor = start
    for row in rows:
        row_start, row_end = row["range"]
        covered_start = max(start, row_start)
        covered_end = min(end, row_end)
        if covered_start != cursor or covered_end <= covered_start:
            raise ValueError("provenance owner range has a gap or overlap")
        if (
            row.get("primary_class") != expected_class
            or tuple(row.get("primary_claim_ids", ())) != expected_ids
            or row.get("secondary_claim_ids") != []
        ):
            raise ValueError("provenance owner changed within range")
        cursor = covered_end
    if cursor != end:
        raise ValueError("provenance owner range is not fully covered")


def _coverage(root: Path) -> dict[str, Any]:
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
    if value.get("schema") != "rom-byte-coverage-v1" or value.get("base_rom") != {
        "path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
        raise ValueError("coverage ROM contract changed")
    _assert_owner_range(value, CANDIDATE_RANGE, "unknown", ())
    for expected_range, expected_class, expected_ids in OWNER_SEGMENTS:
        _assert_owner_range(value, expected_range, expected_class, expected_ids)
    return {"path": COVERAGE_PATH.as_posix(), "size": len(raw), "sha256": _sha(raw),
            "snapshot_artifact": PRECOVERAGE_ARTIFACT.as_posix(),
            "snapshot_manifest_sha256": PRECOVERAGE_MANIFEST_SHA256,
            "snapshot_archive_sha256": PRECOVERAGE_ARCHIVE_SHA256,
            "candidate_current_unknown": True, "provenance_owners_preserved": True}


def _raw_contract(raw: bytes) -> dict[str, Any]:
    if raw[CANDIDATE_RANGE[0]:CANDIDATE_RANGE[1]] != CANDIDATE_RAW or _sha(CANDIDATE_RAW) != CANDIDATE_SHA256:
        raise ValueError("candidate bytes changed")
    if _sha(raw[CONSUMER_RANGE[0]:CONSUMER_RANGE[1]]) != CONSUMER_SHA256:
        raise ValueError("consumer bytes changed")
    proof = raw[PROOF_RANGE[0]:PROOF_RANGE[1]]
    if proof != PROOF_RAW or _sha(proof) != PROOF_SHA256:
        raise ValueError("consumer proof changed")
    expected_halfwords = (0x0600, 0x0E00, 0x4D21, 0x4A22, 0x1880, 0x7800)
    if struct.unpack("<6H", proof) != expected_halfwords:
        raise ValueError("u8 index/load dataflow changed")
    literal = raw[LITERAL_RANGE[0]:LITERAL_RANGE[1]]
    if literal != LITERAL_RAW or _sha(literal) != LITERAL_SHA256 or int.from_bytes(literal, "little") != LITERAL_VALUE:
        raise ValueError("table-base literal changed")
    if _scan_word(raw, LITERAL_RAW) != [LITERAL_RANGE[0]]:
        raise ValueError("table-base word occurrence denominator changed")
    if _scan_literal_loads(raw, LITERAL_RANGE[0]) != [0x07C72E]:
        raise ValueError("literal-LDR denominator changed")
    calls = _scan_target_bl(raw, CALL_TARGET)
    if calls != list(CALL_OFFSETS):
        raise ValueError("target-limited BL denominator changed")
    windows = []
    for index, (start, end, expected, digest) in enumerate(CALLER_WINDOWS):
        window = raw[start:end]
        if window != expected or _sha(window) != digest:
            raise ValueError("fixed caller window changed")
        first, second = struct.unpack_from("<HH", window)
        if first != 0x2000 | FIXED_INDICES[index] or second != 0x2100:
            raise ValueError("fixed caller immediate setup changed")
        call = start + 4
        if _thumb_bl_target(raw, call) != CALL_TARGET:
            raise ValueError("fixed caller target changed")
        windows.append({"file_range": [start, end], "call_offset": call,
                        "index_u8": FIXED_INDICES[index], "raw_hex": window.hex(),
                        "sha256": _sha(window)})
    if _sha(b"".join(raw[start:end] for start, end, _, _ in CALLER_WINDOWS)) != CALLER_CONCAT_SHA256:
        raise ValueError("fixed caller concatenation changed")
    return {"target_limited_bl_offsets": calls,
            "target_limited_bl_count": len(calls),
            "fixed_immediate_callers": windows,
            "excluded_non_fixed_call_offsets": list(EXCLUDED_NON_FIXED_CALL_OFFSETS),
            "literal_word_occurrences": [LITERAL_RANGE[0]],
            "literal_ldr_offsets": [0x07C72E]}


def _build_from_rom(root: Path, raw: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if verify_identity and (len(raw) != ROM_SIZE or _sha(raw) != ROM_SHA256):
        raise ValueError("ROM identity changed")
    evidence = _raw_contract(raw)
    coverage = _coverage(root)
    values = list(raw[CANDIDATE_RANGE[0]:CANDIDATE_RANGE[1]])
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
                               "candidate_values_u8": values,
                               "candidate_sha256": CANDIDATE_SHA256},
            "consumer": {"range": list(CONSUMER_RANGE), "sha256": CONSUMER_SHA256,
                         "proof_range": list(PROOF_RANGE), "proof_sha256": PROOF_SHA256,
                         "proof_raw_hex": PROOF_RAW.hex(),
                         "literal_range": list(LITERAL_RANGE), "literal_value": LITERAL_VALUE,
                         "literal_sha256": LITERAL_SHA256},
            "caller_denominator": evidence,
            "promotion": {"promotion_batch": SCHEMA, "claims": [claim],
                          "claim_count": 1, "promotion_bytes": 4,
                          "range_order": "file_offset_ascending"},
            "scope": NON_CLAIMS}


def build_payload(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    return _build_from_rom(root, _safe_file(root, ROM_PATH).read_bytes())


def _publish_exclusive(source: Path, destination: Path) -> None:
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 4
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 1
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd, os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    if ".." in output.parts:
        raise ValueError("output path traversal is not allowed")
    lexical = output if output.is_absolute() else root / output
    if not lexical.is_relative_to(root):
        raise ValueError("output escapes repository")
    if not lexical.parent.resolve(strict=False).is_relative_to(root):
        raise ValueError("output parent escapes repository")
    for parent in [lexical, *lexical.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("output has symlink ancestor")
    if lexical.exists():
        raise FileExistsError("output already exists")
    payload_raw = _canonical(build_payload(root))
    relative = lexical.relative_to(root).as_posix()
    paths = {"contract": CONTRACT_PATH, "exporter": EXPORTER_PATH,
             "verifier": VERIFIER_PATH, "test": TEST_PATH}
    manifest = {"schema": "git-artifact-promotion-v1", "artifact_schema": SCHEMA,
                "artifact_status": "accepted",
                "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
                "summary": {"promotion_bytes": 4, "claim_count": 1,
                            "target_limited_bl_count": 13, "fixed_caller_count": 4},
                "producer": {"command": ["python3", EXPORTER_PATH.as_posix(), "--root", ".", "--output", relative]},
                "verifier": {"command": ["python3", VERIFIER_PATH.as_posix(), "--root", ".", "--artifact", relative]},
                "implementation": {name + "_sha256": _sha(_safe_file(root, path).read_bytes())
                                   for name, path in paths.items()}}
    lexical.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=lexical.parent, prefix=".fixed-index-u8-tail-") as directory:
        stage = Path(directory)
        (stage / PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_fixed_index_u8_tail import verify_artifact
        report = verify_artifact(root, stage, expected_artifact=lexical)
        if not report["verified"]:
            raise ValueError(report["errors"])
        _publish_exclusive(stage, lexical)
    return lexical


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
