#!/usr/bin/env python3
"""Export the frozen chapter-root table-selector consumer code slice.

The packet contains exactly one raw-ROM range.  Its only semantic label is a
hash-bound consumer slice for the primary/alternate chapter-root table
selector; it is not a CFG or runtime-reachability claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-chapter-selector-code-slice-v1"
VERIFY_SCHEMA = "rom-chapter-selector-code-slice-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987"

SOURCE_SCHEMA = "rom-chapter-script-inventory-v1"
SOURCE_DIR = Path("artifacts/rom-chapter-script-inventory-v1")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "chapter-script-inventory.json"
SOURCE_BUNDLE = SOURCE_DIR / "chapter-script-bytes.bin"
SOURCE_EXPORTER = Path("tools/export_rom_chapter_script_inventory.py")
SOURCE_VERIFIER = Path("tools/verify_rom_chapter_script_inventory.py")
SOURCE_TEST = Path("tests/test_export_rom_chapter_script_inventory.py")
SOURCE_MANIFEST_SHA256 = "ad77f775f927b89e4a499ddff82e077c38b2767cd86348b65053cb8ca4136f0e"
SOURCE_PAYLOAD_SHA256 = "813cd10394e5fac239aefd6043437796b1a63f95d8d068d714871b8dd3edcabc"
SOURCE_BUNDLE_SHA256 = "eba1393714485ab78d0dbde6cb1b9cf407e031ce8c2a86068038a3920d5f0699"
SOURCE_EXPORTER_SHA256 = "707a00b57c6dbbfb3da22f5ef385a0243c600ef1b30f8b70527446c290ddba42"
SOURCE_VERIFIER_SHA256 = "b9bf0203bddd8ca85981bd7957d95171c11187a117447bc5a0e92e384777911c"
SOURCE_TEST_SHA256 = "95f7d1eb1aa22efc6f6cb4e183af3564ef644831b6468dde0d00e0cad368e941"
SOURCE_VERIFY_SCHEMA = "rom-chapter-script-inventory-verification-v1"
SOURCE_VERIFY_REPORT_SHA256 = "c3decb8c05249571c458faee06713f21258b8445304b5dd3eeab370853a2717e"

TARGET_RANGE = (0x08F594, 0x08F5D4)
TARGET_SHA256 = "0c586c11a8c452e4096d4cf444bb5c75628d099020ff8e5642f99634ea022efd"
EXPECTED_PACKED_SHA256 = TARGET_SHA256
TARGET_SOURCE_POINTER = "/consumer_evidence/table_selector"

PAYLOAD_NAME = "rom-chapter-selector-code-slice.json"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = {MANIFEST_NAME, PAYLOAD_NAME}

SCOPE = {
    "primary_class": "consumer_code_slice",
    "claim_kind": "consumer_code_slice",
    "semantic_label": "primary/alternate chapter root table selector",
    "source_consumer_provenance_bound": True,
    "raw_rom_exact_slice": True,
    "baseline_unknown_only": True,
    "complete_cfg_claimed": False,
    "natural_gameplay_reachability_claimed": False,
    "chapter_script_gap_claimed": False,
    "adjacent_bytes_claimed": False,
    "business_fields_claimed": False,
    "padding_or_free_space_claimed": False,
    "editing_writeback_relocation_claimed": False,
    "allocatable_claimed": False,
    "safe_editing": False,
}

LIMITATIONS = [
    "Only the exact 0x08F594..0x08F5D4 primary/alternate chapter-root table selector range is classified.",
    "This is a hash-bound consumer code slice, not a complete CFG or an instruction-only claim.",
    "Natural gameplay reachability, chapter-script gaps, business fields, adjacent bytes, and parser semantics are not claimed.",
    "Padding/free/allocatable status, editing, write-back, and relocation safety are not claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _safe_file(root: Path, relative: Path | str) -> Path:
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative input: {relative}")
    path = root / relative
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = path.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink():
        raise ValueError(f"artifact member must not be a symlink: {name}")
    resolved = path.resolve(strict=True)
    if resolved != artifact and artifact not in resolved.parents:
        raise ValueError(f"artifact member escapes directory: {name}")
    if not resolved.is_file():
        raise ValueError(f"artifact member is not a file: {name}")
    return resolved


def _source_manifest_expected() -> dict[str, Any]:
    return {
        "artifact_schema": SOURCE_SCHEMA,
        "artifact_status": "accepted",
        "files": {
            "chapter-script-bytes.bin": SOURCE_BUNDLE_SHA256,
            "chapter-script-inventory.json": SOURCE_PAYLOAD_SHA256,
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_chapter_script_inventory.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/rom-chapter-script-inventory-v1",
            ],
            "exporter_sha256": SOURCE_EXPORTER_SHA256,
            "test_sha256": SOURCE_TEST_SHA256,
            "verifier_sha256": SOURCE_VERIFIER_SHA256,
        },
        "schema": "git-artifact-promotion-v1",
        "scope": {
            "fixed_pointer_table_denominator_complete": True,
            "interpreter_consumed_byte_union_complete": True,
            "natural_gameplay_root_reachability_complete": False,
            "natural_language_decoding_complete": False,
            "static_control_flow_closure_complete": True,
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_chapter_script_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-chapter-script-inventory-v1",
            ],
            "exit_code": 0,
            "report": {
                "dynamic_opcode_06_nodes": 42,
                "errors": [],
                "internal_gap_bytes": 3769,
                "internal_gap_count": 91,
                "merged_range_bytes": 334060,
                "merged_range_count": 92,
                "node_overlap_bytes": 0,
                "non_null_script_slots": 200,
                "observed_opcode_count": 43,
                "packed_script_bytes": 334060,
                "parse_failure_count": 0,
                "pointer_table_slot_count": 204,
                "raw_node_bytes": 334060,
                "schema": SOURCE_VERIFY_SCHEMA,
                "terminal_node_count": 590,
                "unique_instruction_nodes": 18994,
                "unique_script_roots": 188,
                "verified": True,
            },
            "verifier_sha256": SOURCE_VERIFIER_SHA256,
        },
    }


def _source_identity(root: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = {
        "manifest": _safe_file(root, SOURCE_MANIFEST),
        "payload": _safe_file(root, SOURCE_PAYLOAD),
        "bundle": _safe_file(root, SOURCE_BUNDLE),
        "exporter": _safe_file(root, SOURCE_EXPORTER),
        "verifier": _safe_file(root, SOURCE_VERIFIER),
        "test": _safe_file(root, SOURCE_TEST),
    }
    expected_hashes = {
        "manifest": SOURCE_MANIFEST_SHA256,
        "payload": SOURCE_PAYLOAD_SHA256,
        "bundle": SOURCE_BUNDLE_SHA256,
        "exporter": SOURCE_EXPORTER_SHA256,
        "verifier": SOURCE_VERIFIER_SHA256,
        "test": SOURCE_TEST_SHA256,
    }
    for name, path in paths.items():
        if _sha(path.read_bytes()) != expected_hashes[name]:
            raise ValueError(f"chapter-script source {name} identity changed")
    if report.get("verified") is not True or report.get("schema") != SOURCE_VERIFY_SCHEMA:
        raise ValueError("chapter-script source verifier did not close")
    if _sha(_canonical(report)) != SOURCE_VERIFY_REPORT_SHA256:
        raise ValueError("chapter-script source verifier report identity changed")
    source_manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    if source_manifest != _source_manifest_expected():
        raise ValueError("chapter-script source manifest contract changed")
    source_payload = json.loads(paths["payload"].read_text(encoding="utf-8"))
    expected_implementation = {
        "exporter_sha256": SOURCE_EXPORTER_SHA256,
        "test_sha256": SOURCE_TEST_SHA256,
        "verifier_sha256": SOURCE_VERIFIER_SHA256,
    }
    if source_payload.get("schema") != SOURCE_SCHEMA:
        raise ValueError("chapter-script source payload schema changed")
    if source_payload.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "sha256": ROM_SHA256,
        "size": ROM_SIZE,
    }:
        raise ValueError("chapter-script source ROM identity changed")
    if source_payload.get("implementation") != expected_implementation:
        raise ValueError("chapter-script source implementation identity changed")
    evidence = source_payload.get("consumer_evidence", {}).get("table_selector")
    expected_evidence = {
        "file_range": list(TARGET_RANGE),
        "gba_range": [_gba(value) for value in TARGET_RANGE],
        "sha256": TARGET_SHA256,
    }
    if evidence != expected_evidence:
        raise ValueError("chapter-script table-selector provenance changed")
    source = {
        "artifact_schema": SOURCE_SCHEMA,
        "manifest": {"path": SOURCE_MANIFEST.as_posix(), "sha256": SOURCE_MANIFEST_SHA256},
        "payload": {"path": SOURCE_PAYLOAD.as_posix(), "sha256": SOURCE_PAYLOAD_SHA256},
        "bundle": {"path": SOURCE_BUNDLE.as_posix(), "sha256": SOURCE_BUNDLE_SHA256},
        "exporter": {"path": SOURCE_EXPORTER.as_posix(), "sha256": SOURCE_EXPORTER_SHA256},
        "verifier": {"path": SOURCE_VERIFIER.as_posix(), "sha256": SOURCE_VERIFIER_SHA256},
        "test": {"path": SOURCE_TEST.as_posix(), "sha256": SOURCE_TEST_SHA256},
        "verifier_report": {"schema": SOURCE_VERIFY_SCHEMA, "sha256": SOURCE_VERIFY_REPORT_SHA256},
        "consumer_evidence": {
            "json_pointer": TARGET_SOURCE_POINTER,
            "range": list(TARGET_RANGE),
            "sha256": TARGET_SHA256,
        },
    }
    return source, source_payload


def _load_source_verifier(root: Path):
    path = _safe_file(root, SOURCE_VERIFIER)
    if _sha(path.read_bytes()) != SOURCE_VERIFIER_SHA256:
        raise ValueError("chapter-script source verifier identity changed")
    spec = importlib.util.spec_from_file_location("chapter_script_source_verifier", path)
    if spec is None or spec.loader is None:
        raise ValueError("chapter-script source verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_source(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Independently verify the upstream packet before consuming its labels."""

    source_verifier = _load_source_verifier(root)
    report = source_verifier.verify_artifact(root, root / SOURCE_DIR)
    if report.get("verified") is not True:
        raise ValueError(f"chapter-script source independent verification failed: {report.get('errors', [])}")
    return _source_identity(root, report)


def _take(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or start >= end or end > len(rom):
        raise ValueError(f"chapter selector ROM range outside input: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _validate_coverage(raw: bytes) -> dict[str, Any]:
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("chapter selector coverage identity changed")
    try:
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("chapter selector coverage is not valid JSON") from error
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("chapter selector coverage schema changed")
    if coverage.get("base_rom") != {
        "path": ROM_PATH.as_posix(),
        "sha256": ROM_SHA256,
        "size": ROM_SIZE,
    }:
        raise ValueError("chapter selector coverage ROM identity changed")
    if coverage.get("domain") != [0, ROM_SIZE]:
        raise ValueError("chapter selector coverage domain changed")
    if coverage.get("policy", {}).get("ranges_are_half_open") is not True:
        raise ValueError("chapter selector coverage range policy changed")
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("chapter selector coverage ledgers are missing")
    start, end = TARGET_RANGE
    for claim in claims:
        claim_range = claim.get("range")
        if not isinstance(claim_range, list) or len(claim_range) != 2:
            raise ValueError("chapter selector coverage claim range is malformed")
        claim_start, claim_end = claim_range
        if not isinstance(claim_start, int) or not isinstance(claim_end, int) or claim_start >= claim_end:
            raise ValueError("chapter selector coverage claim range is invalid")
        if claim_start < end and start < claim_end:
            raise ValueError("chapter selector range overlaps coverage claim")
    cursor = start
    owners = []
    for segment in segments:
        segment_range = segment.get("range")
        if not isinstance(segment_range, list) or len(segment_range) != 2:
            raise ValueError("chapter selector coverage segment range is malformed")
        segment_start, segment_end = segment_range
        if segment_end <= cursor:
            continue
        if segment_start > cursor:
            break
        if segment_start <= cursor < segment_end:
            piece_end = min(segment_end, end)
            if segment.get("primary_class") != "unknown":
                raise ValueError("chapter selector range is not current unknown")
            if segment.get("primary_claim_ids") != [] or segment.get("secondary_claim_ids") != []:
                raise ValueError("chapter selector range has existing primary/secondary ownership")
            owners.append(segment)
            cursor = piece_end
            if cursor == end:
                break
    if cursor != end or not owners:
        raise ValueError("chapter selector range is not fully current unknown")
    return {
        "path": COVERAGE_PATH.as_posix(),
        "sha256": COVERAGE_SHA256,
        "current_primary_state": {
            "range": list(TARGET_RANGE),
            "primary_class": "unknown",
            "primary_claim_ids": [],
            "secondary_claim_ids": [],
        },
    }


def _implementation(root: Path) -> dict[str, Any]:
    return {
        "exporter": {
            "path": Path("tools/export_rom_chapter_selector_code_slice.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tools/export_rom_chapter_selector_code_slice.py").read_bytes()),
        },
        "test": {
            "path": Path("tests/test_export_rom_chapter_selector_code_slice.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tests/test_export_rom_chapter_selector_code_slice.py").read_bytes()),
        },
        "verifier": {
            "path": Path("tools/verify_rom_chapter_selector_code_slice.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tools/verify_rom_chapter_selector_code_slice.py").read_bytes()),
        },
    }


def _range_denominator() -> str:
    return _sha(_canonical([list(TARGET_RANGE)]))


def build_payload(root: Path, rom: bytes | None = None, coverage: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    source, _ = _verify_source(root)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    if coverage is None:
        coverage = _safe_file(root, COVERAGE_PATH).read_bytes()
    coverage_identity = _validate_coverage(coverage)
    raw = _take(rom, *TARGET_RANGE)
    if _sha(raw) != TARGET_SHA256:
        raise ValueError("chapter selector source range changed")
    packed = raw
    if _sha(packed) != EXPECTED_PACKED_SHA256:
        raise ValueError("chapter selector packed bytes changed")
    state = coverage_identity["current_primary_state"]
    row = {
        "id": "chapter-root-table-selector",
        "role": "primary_alternate_chapter_root_table_selector",
        "primary_class": "consumer_code_slice",
        "claim_kind": "consumer_code_slice",
        "promotion_batch": SCHEMA,
        "promoted_from_primary_class": "unknown",
        "baseline_unknown_only": True,
        "runtime_reachability_claimed": False,
        "instruction_only_claimed": False,
        "safe_editing": False,
        "allocatable": False,
        "range": list(TARGET_RANGE),
        "gba_range": [_gba(value) for value in TARGET_RANGE],
        "size": len(raw),
        "bytes_hex": raw.hex(),
        "bytes_sha256": _sha(raw),
        "packed_range": [0, len(raw)],
        "packed_sha256": _sha(raw),
        "source_evidence": {
            "artifact_schema": SOURCE_SCHEMA,
            "payload_path": SOURCE_PAYLOAD.as_posix(),
            "payload_sha256": SOURCE_PAYLOAD_SHA256,
            "json_pointer": TARGET_SOURCE_POINTER,
            "evidence_range": list(TARGET_RANGE),
            "evidence_sha256": TARGET_SHA256,
        },
        "coverage_state": state,
    }
    payload = {
        "schema": SCHEMA,
        "artifact_status": "accepted",
        "rom": {"path": ROM_PATH.as_posix(), "sha256": ROM_SHA256, "size": len(rom)},
        "coverage": {"path": coverage_identity["path"], "sha256": coverage_identity["sha256"]},
        "source": source,
        "range": row,
        "range_denominator_sha256": _range_denominator(),
        "packed_bytes": packed.hex(),
        "packed_bytes_sha256": _sha(packed),
        "summary": {
            "range_count": 1,
            "bytes": len(raw),
            "packed_bytes": len(packed),
            "current_unknown_bytes": len(raw),
            "primary_overlap_bytes": 0,
            "secondary_overlap_bytes": 0,
        },
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
    }
    return payload, packed


def _manifest(payload: dict[str, Any], payload_bytes: bytes) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: _sha(payload_bytes)},
        "producer": payload["implementation"],
        "source": {**payload["source"], "coverage": payload["coverage"]},
        "coverage": payload["coverage"],
        "verification": {
            "schema": VERIFY_SCHEMA,
            "command": [
                "python3",
                "tools/verify_rom_chapter_selector_code_slice.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
        },
    }


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact output path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("artifact output must not be the repository root or its ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("foreign artifact output directory")
    members = {member.relative_to(target).as_posix() for member in target.rglob("*") if member.is_file()}
    if any(member.is_symlink() for member in target.rglob("*")) or members != EXPECTED_FILES:
        raise ValueError("foreign artifact output directory")
    try:
        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("foreign artifact output directory") from error
    if manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("foreign artifact output directory")
    verifier_path = _safe_file(root, "tools/verify_rom_chapter_selector_code_slice.py")
    spec = importlib.util.spec_from_file_location("chapter_selector_packet_verifier", verifier_path)
    if spec is None or spec.loader is None:
        raise ValueError("chapter selector packet verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.verify_artifact(root, target)
    if report.get("verified") is not True:
        raise ValueError(f"existing artifact failed independent verification: {report.get('errors', [])}")
    return target


def _replace_output(target: Path, payload_bytes: bytes, manifest_bytes: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup: Path | None = None
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_bytes)
        (temporary / MANIFEST_NAME).write_bytes(manifest_bytes)
        if target.exists():
            backup = target.with_name(f".{target.name}.old-{uuid.uuid4().hex}")
            os.replace(target, backup)
        os.replace(temporary, target)
        if backup is not None:
            shutil.rmtree(backup)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = _validate_output(root, Path(output))
    payload, _ = build_payload(root)
    payload_bytes = _canonical(payload)
    _replace_output(target, payload_bytes, _canonical(_manifest(payload, payload_bytes)))
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
