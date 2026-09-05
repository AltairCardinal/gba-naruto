#!/usr/bin/env python3
"""Export the frozen battle status-bar generator caller code slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-battle-status-bar-caller-slice-v1"
VERIFY_SCHEMA = "rom-battle-status-bar-caller-slice-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987"
SOURCE_SCHEMA = "battle-status-bars-v1"
SOURCE_DIR = Path("artifacts/battle-status-bars-v1")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "battle-status-bars.json"
SOURCE_EXPORTER = Path("tools/export_battle_status_bars.py")
SOURCE_VERIFIER = Path("tools/verify_battle_status_bars.py")
SOURCE_TEST = Path("tests/test_export_battle_status_bars.py")
SOURCE_MANIFEST_SHA256 = "d88242fa88213b96d8fe48430a0758a3bb79adf7dd6bb6d22e7d00da9711c0d0"
SOURCE_PAYLOAD_SHA256 = "c8ff2c231c5a0ac111f10c7ca545d285cde0e23c4fca706815ee40277086d4eb"
SOURCE_EXPORTER_SHA256 = "1118ff63553ee1e31606a96b0d6564609beada3a42a37e8118a4e16103b55102"
SOURCE_VERIFIER_SHA256 = "53202cb452c25c762ff6fbface0705c31bb01392177d66f168628919c8b77d32"
SOURCE_TEST_SHA256 = "4a84c9eb211874b0d216bf061f18f213b2bfa3893e10307d76c3e9bc6fb7007e"
SOURCE_VERIFY_SCHEMA = "battle-status-bars-verification-v1"
SOURCE_VERIFY_REPORT_SHA256 = "5e767d4d73caa72fa61ec11cd186f5f5aa4976424c33debd2e23bad689addfcd"
GENERATOR_GBA = "0x08068370"
TARGET_RANGE = (0x07A34C, 0x07AA8C)
TARGET_SHA256 = "f400ef9501381b6e005e7d9c51add8ac5fe3dc4217a3fa6397e1ccdf3dc64c51"
BL_MATCHES = [
    {"gba_address": "0x0806F0D6", "file_offset": 0x06F0D6, "raw_hex": "f9f74bf9"},
    {"gba_address": "0x0806F0EC", "file_offset": 0x06F0EC, "raw_hex": "f9f740f9"},
    {"gba_address": "0x0807A83C", "file_offset": 0x07A83C, "raw_hex": "edf798fd"},
    {"gba_address": "0x0807A8A6", "file_offset": 0x07A8A6, "raw_hex": "edf763fd"},
]
BL_MATCHES_SHA256 = "46237f1e81a3e4e3846aabe4445fb25544e55c1ce6ed776055ae3ac9e49f7dd2"
PAYLOAD_NAME = "rom-battle-status-bar-caller-slice.json"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = {MANIFEST_NAME, PAYLOAD_NAME}

SCOPE = {
    "primary_class": "consumer_code_slice",
    "claim_kind": "consumer_code_slice",
    "semantic_label": "frozen status-bar generator caller hash-bound consumer code slice",
    "source_consumer_provenance_bound": True,
    "raw_rom_exact_slice": True,
    "baseline_unknown_only": True,
    "complete_cfg_claimed": False,
    "every_byte_instruction_claimed": False,
    "natural_runtime_reachability_claimed": False,
    "all_caller_runtime_claimed": False,
    "business_fields_claimed": False,
    "adjacent_bytes_claimed": False,
    "padding_or_free_space_claimed": False,
    "editing_writeback_relocation_claimed": False,
    "allocatable_claimed": False,
    "safe_editing": False,
}
LIMITATIONS = [
    "Only the exact 0x07A34C..0x07AA8C frozen status-bar generator caller slice is classified.",
    "The slice is bound to the source generator provenance and an independent full-ROM 2-byte-aligned Thumb BL denominator.",
    "No complete CFG, every-byte instruction decoding, natural reachability, or all-caller runtime claim is made.",
    "Business fields, adjacent bytes, padding/free/allocatable status, editing, write-back, and relocation are not claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _safe_file(root: Path, relative: Path | str) -> Path:
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative input: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _run_source_verifier(root: Path) -> dict[str, Any]:
    path = _safe_file(root, SOURCE_VERIFIER)
    if _sha(path.read_bytes()) != SOURCE_VERIFIER_SHA256:
        raise ValueError("battle-status source verifier identity changed")
    try:
        result = subprocess.run(
            ["python3", str(path), "--root", str(root), "--artifact-dir", str(root / SOURCE_DIR)],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"battle-status source verifier did not complete: {error}") from error
    if result.returncode != 0:
        raise ValueError(f"battle-status source verifier failed: {result.stdout} {result.stderr}")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("battle-status source verifier output is not JSON") from error
    expected = {"errors": [], "exact_generated_unknown_cell_count": 181, "schema": SOURCE_VERIFY_SCHEMA, "verified": True}
    if report != expected or _sha(_canonical(report)) != SOURCE_VERIFY_REPORT_SHA256:
        raise ValueError("battle-status source verifier report identity changed")
    return report


def _source_identity(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    paths = {"manifest": _safe_file(root, SOURCE_MANIFEST), "payload": _safe_file(root, SOURCE_PAYLOAD), "exporter": _safe_file(root, SOURCE_EXPORTER), "verifier": _safe_file(root, SOURCE_VERIFIER), "test": _safe_file(root, SOURCE_TEST)}
    expected = {"manifest": SOURCE_MANIFEST_SHA256, "payload": SOURCE_PAYLOAD_SHA256, "exporter": SOURCE_EXPORTER_SHA256, "verifier": SOURCE_VERIFIER_SHA256, "test": SOURCE_TEST_SHA256}
    for name, path in paths.items():
        if _sha(path.read_bytes()) != expected[name]:
            raise ValueError(f"battle-status source {name} identity changed")
    source_manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    payload = json.loads(paths["payload"].read_text(encoding="utf-8"))
    if source_manifest.get("artifact_schema") != SOURCE_SCHEMA or payload.get("schema") != SOURCE_SCHEMA:
        raise ValueError("battle-status source schema changed")
    if payload.get("rom") != {"file": "rom/base.gba", "sha256": ROM_SHA256}:
        raise ValueError("battle-status source ROM identity changed")
    if payload.get("implementation") != {"exporter_sha256": SOURCE_EXPORTER_SHA256, "verifier_sha256": SOURCE_VERIFIER_SHA256, "test_sha256": SOURCE_TEST_SHA256}:
        raise ValueError("battle-status source implementation identity changed")
    target = {"file_range": list(TARGET_RANGE), "gba_range": [_gba(value) for value in TARGET_RANGE], "sha256": TARGET_SHA256}
    caller = payload.get("generator", {}).get("callers", [])
    if len(caller) != 2 or caller[1] != {"gba_end_exclusive": _gba(TARGET_RANGE[1]), "gba_start": _gba(TARGET_RANGE[0]), "sha256": TARGET_SHA256, "size": TARGET_RANGE[1] - TARGET_RANGE[0]}:
        raise ValueError("battle-status target caller provenance changed")
    return {
        "artifact_schema": SOURCE_SCHEMA,
        "manifest": {"path": SOURCE_MANIFEST.as_posix(), "sha256": SOURCE_MANIFEST_SHA256},
        "payload": {"path": SOURCE_PAYLOAD.as_posix(), "sha256": SOURCE_PAYLOAD_SHA256},
        "exporter": {"path": SOURCE_EXPORTER.as_posix(), "sha256": SOURCE_EXPORTER_SHA256},
        "verifier": {"path": SOURCE_VERIFIER.as_posix(), "sha256": SOURCE_VERIFIER_SHA256},
        "test": {"path": SOURCE_TEST.as_posix(), "sha256": SOURCE_TEST_SHA256},
        "verifier_report": {"schema": SOURCE_VERIFY_SCHEMA, "sha256": SOURCE_VERIFY_REPORT_SHA256, "verified": True, "exact_generated_unknown_cell_count": 181},
        "generator_gba_address": GENERATOR_GBA,
        "target_caller": target,
    }


def _scan_bl(rom: bytes) -> dict[str, Any]:
    import struct

    found = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        high = first & 0x07FF
        if high & 0x0400:
            high -= 0x0800
        address = ROM_BASE + offset
        destination = (address + 4 + (high << 12) + ((second & 0x07FF) << 1)) & 0xFFFFFFFF
        if destination == int(GENERATOR_GBA, 16):
            found.append({"gba_address": _gba(offset), "file_offset": offset, "raw_hex": rom[offset : offset + 4].hex()})
    if found != BL_MATCHES:
        raise ValueError(f"battle-status full-ROM BL denominator changed: {found}")
    return {
        "algorithm": "full_rom_2byte_aligned_thumb_bl_to_target",
        "target_gba_address": GENERATOR_GBA,
        "alignment": 2,
        "match_count": len(found),
        "matches": found,
        "matches_sha256": _sha(_canonical(found)),
        "outside_target_matches": found[:2],
        "target_slice_matches": found[2:],
    }


def _validate_coverage(raw: bytes) -> dict[str, Any]:
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("battle-status coverage identity changed")
    try:
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("battle-status coverage is not valid JSON") from error
    if coverage.get("schema") != "rom-byte-coverage-v1" or coverage.get("base_rom") != {"path": ROM_PATH.as_posix(), "sha256": ROM_SHA256, "size": ROM_SIZE} or coverage.get("domain") != [0, ROM_SIZE] or coverage.get("policy", {}).get("ranges_are_half_open") is not True:
        raise ValueError("battle-status coverage contract changed")
    segments, claims = coverage.get("segments"), coverage.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("battle-status coverage ledgers are missing")
    start, end = TARGET_RANGE
    for claim in claims:
        item = claim.get("range")
        if not isinstance(item, list) or len(item) != 2 or not all(isinstance(x, int) for x in item) or item[0] >= item[1]:
            raise ValueError("battle-status coverage claim range is malformed")
        if item[0] < end and start < item[1]:
            raise ValueError("battle-status target overlaps a coverage claim")
    target = next((s for s in segments if s.get("range") == [start, end]), None)
    left = next((s for s in segments if s.get("range", [None, None])[1] == start), None)
    right = next((s for s in segments if s.get("range", [None, None])[0] == end), None)
    if target is None or target.get("primary_class") != "unknown" or target.get("primary_claim_ids") != [] or target.get("secondary_claim_ids") != []:
        raise ValueError("battle-status target is not current unknown and unowned")
    if left is None or left.get("primary_class") == "unknown" or not left.get("primary_claim_ids") or right is None or right.get("primary_class") == "unknown" or not right.get("primary_claim_ids"):
        raise ValueError("battle-status caller neighbor ownership boundary changed")
    return {"path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256, "current_primary_state": {"range": list(TARGET_RANGE), "primary_class": "unknown", "primary_claim_ids": [], "secondary_claim_ids": []}, "left_neighbor": {"range": left["range"], "primary_class": left["primary_class"], "primary_claim_ids": left["primary_claim_ids"], "secondary_claim_ids": left.get("secondary_claim_ids", [])}, "right_neighbor": {"range": right["range"], "primary_class": right["primary_class"], "primary_claim_ids": right["primary_claim_ids"], "secondary_claim_ids": right.get("secondary_claim_ids", [])}}


def _implementation(root: Path) -> dict[str, Any]:
    return {"exporter": {"path": "tools/export_rom_battle_status_bar_caller_slice.py", "sha256": _sha(_safe_file(root, "tools/export_rom_battle_status_bar_caller_slice.py").read_bytes())}, "test": {"path": "tests/test_export_rom_battle_status_bar_caller_slice.py", "sha256": _sha(_safe_file(root, "tests/test_export_rom_battle_status_bar_caller_slice.py").read_bytes())}, "verifier": {"path": "tools/verify_rom_battle_status_bar_caller_slice.py", "sha256": _sha(_safe_file(root, "tools/verify_rom_battle_status_bar_caller_slice.py").read_bytes())}}


def _build(root: Path, rom: bytes | None = None, coverage: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    source = _source_identity(root, _run_source_verifier(root))
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    if coverage is None:
        coverage = _safe_file(root, COVERAGE_PATH).read_bytes()
    coverage_state = _validate_coverage(coverage)
    bl = _scan_bl(rom)
    source["bl_denominator"] = bl
    raw = rom[TARGET_RANGE[0] : TARGET_RANGE[1]]
    if len(raw) != TARGET_RANGE[1] - TARGET_RANGE[0] or _sha(raw) != TARGET_SHA256:
        raise ValueError("battle-status target caller raw bytes changed")
    row = {"id": "battle-status-bar-generator-caller", "role": "frozen_status_bar_generator_caller", "primary_class": "consumer_code_slice", "claim_kind": "consumer_code_slice", "promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown", "baseline_unknown_only": True, "runtime_reachability_claimed": False, "instruction_only_claimed": False, "safe_editing": False, "allocatable": False, "range": list(TARGET_RANGE), "gba_range": [_gba(v) for v in TARGET_RANGE], "size": len(raw), "bytes_hex": raw.hex(), "bytes_sha256": _sha(raw), "packed_range": [0, len(raw)], "packed_sha256": _sha(raw), "source_evidence": {"artifact_schema": SOURCE_SCHEMA, "payload_path": SOURCE_PAYLOAD.as_posix(), "payload_sha256": SOURCE_PAYLOAD_SHA256, "json_pointer": "/generator/callers/1", "generator_gba_address": GENERATOR_GBA, "evidence_range": list(TARGET_RANGE), "evidence_gba_range": [_gba(v) for v in TARGET_RANGE], "evidence_sha256": TARGET_SHA256, "full_bl_denominator_sha256": BL_MATCHES_SHA256}, "coverage_state": coverage_state["current_primary_state"]}
    return {"schema": SCHEMA, "artifact_status": "accepted", "rom": {"path": ROM_PATH.as_posix(), "sha256": ROM_SHA256, "size": len(rom)}, "coverage": {"path": coverage_state["path"], "sha256": coverage_state["sha256"]}, "source": source, "range": row, "range_denominator_sha256": _sha(_canonical([list(TARGET_RANGE)])), "packed_bytes": raw.hex(), "packed_bytes_sha256": _sha(raw), "summary": {"range_count": 1, "bytes": len(raw), "packed_bytes": len(raw), "current_unknown_bytes": len(raw), "primary_overlap_bytes": 0, "secondary_overlap_bytes": 0}, "scope": SCOPE, "limitations": LIMITATIONS, "implementation": _implementation(root)}, raw


def build_payload(root: Path, rom: bytes | None = None, coverage: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    return _build(root, rom, coverage)


def _manifest(payload: dict[str, Any], payload_bytes: bytes) -> dict[str, Any]:
    return {"schema": f"{SCHEMA}-artifact-manifest-v1", "artifact_schema": SCHEMA, "artifact_status": "accepted", "files": {PAYLOAD_NAME: _sha(payload_bytes)}, "producer": payload["implementation"], "source": {**payload["source"], "coverage": payload["coverage"]}, "coverage": payload["coverage"], "verification": {"schema": VERIFY_SCHEMA, "command": ["python3", "tools/verify_rom_battle_status_bar_caller_slice.py", "--root", ".", "--artifact-dir", f"artifacts/{SCHEMA}"]}}


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = Path(output)
    if not target.is_absolute():
        target = root / target
    target = target.resolve(strict=False)
    if target.exists() and (not target.is_dir() or any(p.is_symlink() for p in target.rglob("*")) or {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()} != EXPECTED_FILES):
        raise ValueError("foreign artifact output directory")
    payload, _ = build_payload(root)
    payload_bytes = _canonical(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup = None
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_bytes)
        (temporary / MANIFEST_NAME).write_bytes(_canonical(_manifest(payload, payload_bytes)))
        if target.exists():
            backup = target.with_name(f".{target.name}.old-{uuid.uuid4().hex}")
            os.replace(target, backup)
        os.replace(temporary, target)
        if backup is not None:
            import shutil
            shutil.rmtree(backup)
    except BaseException:
        import shutil
        if temporary.exists(): shutil.rmtree(temporary)
        if backup is not None and backup.exists() and not target.exists(): os.replace(backup, target)
        raise
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
