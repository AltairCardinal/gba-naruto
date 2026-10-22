#!/usr/bin/env python3
"""Export the frozen terminal tail of the generic Sprite loader."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import sysconfig
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-sprite-loader-tail-v1"
VERIFY_SCHEMA = "rom-sprite-loader-tail-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987"

SOURCE_SCHEMA = "sprite-definition-animations-v1"
SOURCE_DIR = Path("artifacts/sprite-definition-animations-v1")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_EXPORTER = Path("tools/export_sprite_definition_animations.py")
SOURCE_VERIFIER = Path("tools/verify_sprite_definition_animations.py")
SOURCE_TEST = Path("tests/test_export_sprite_definition_animations.py")
SOURCE_MANIFEST_SHA256 = "e432003728c8ea28b95723eeb4f68f9a8cf95b74185eb39fdd6075c71c16b583"
SOURCE_EXPORTER_SHA256 = "23677a3ea2b4d6753218358c6e53eee2745b46e3c691480a1385d5a2f036846a"
SOURCE_VERIFIER_SHA256 = "bffa6e52426b1ad716f81a77770826ce33dc3deb6496a912040457f048aae90e"
SOURCE_TEST_SHA256 = "06a999de6556a4d49bd1afd7d181785290d306c3b1e4dd9b9b08d0be608b2f0e"
SOURCE_VERIFY_SCHEMA = "sprite-definition-animations-verification-v1"
SOURCE_VERIFY_REPORT_SHA256 = "ca8e829cb3ba3d927d8b427af5bd4a5be0d758daca979ac2ce6958e4d3066a27"
SOURCE_LOADER_RANGE = (0x080B08, 0x080B7C)
SOURCE_LOADER_SHA256 = "ff28fa10e4606f706a4fd4986126d8a14fe2baf66f1cc2621c5fe6b15d2ff8c2"
ENTRY_COUNT = 43

TARGET_RANGE = (0x080B58, 0x080B7C)
TARGET_SHA256 = "a318a3e999a3a89c53f42fd3fec03c7608ab325d01061136e2915fe9e4e6af5c"
EXPECTED_PACKED_SHA256 = TARGET_SHA256
TARGET_SOURCE_POINTER = "/code_slices/0"

PAYLOAD_NAME = "rom-sprite-loader-tail.json"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = {MANIFEST_NAME, PAYLOAD_NAME}

SCOPE = {
    "primary_class": "consumer_code_slice",
    "claim_kind": "consumer_code_slice",
    "semantic_label": "fixed 43-entry sprite definition animation consumer loader terminal tail",
    "source_consumer_provenance_bound": True,
    "raw_rom_exact_slice": True,
    "baseline_unknown_only": True,
    "complete_cfg_claimed": False,
    "natural_runtime_reachability_claimed": False,
    "later_unknown_bytes_claimed": False,
    "scene_overwrite_claimed": False,
    "business_semantics_claimed": False,
    "adjacent_bytes_claimed": False,
    "padding_or_free_space_claimed": False,
    "editing_writeback_relocation_claimed": False,
    "allocatable_claimed": False,
    "safe_editing": False,
}

LIMITATIONS = [
    "Only the exact 0x080B58..0x080B7C primary consumer-code-slice tail is classified.",
    "The label is bound to the fixed 43-entry Sprite definition animation loader provenance and raw-ROM hash.",
    "This is not a complete CFG, a natural runtime reachability proof, or a claim about later unknown bytes.",
    "Scene overwrite behavior, business semantics, adjacent bytes, and parser details are not claimed.",
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


def _source_identity(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "manifest": _safe_file(root, SOURCE_MANIFEST),
        "exporter": _safe_file(root, SOURCE_EXPORTER),
        "verifier": _safe_file(root, SOURCE_VERIFIER),
        "test": _safe_file(root, SOURCE_TEST),
    }
    expected_hashes = {
        "manifest": SOURCE_MANIFEST_SHA256,
        "exporter": SOURCE_EXPORTER_SHA256,
        "verifier": SOURCE_VERIFIER_SHA256,
        "test": SOURCE_TEST_SHA256,
    }
    for name, path in paths.items():
        if _sha(path.read_bytes()) != expected_hashes[name]:
            raise ValueError(f"sprite-definition source {name} identity changed")
    if report.get("schema") != SOURCE_VERIFY_SCHEMA or report.get("verified_entries") != ENTRY_COUNT or report.get("errors") != []:
        raise ValueError("sprite-definition source verifier did not close")
    if _sha(_canonical(report)) != SOURCE_VERIFY_REPORT_SHA256:
        raise ValueError("sprite-definition source verifier report identity changed")
    source_manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    if source_manifest.get("schema") != SOURCE_SCHEMA or source_manifest.get("entry_count") != ENTRY_COUNT:
        raise ValueError("sprite-definition source manifest contract changed")
    expected_rom = {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}
    if source_manifest.get("rom") != expected_rom:
        raise ValueError("sprite-definition source ROM identity changed")
    expected_loader = {
        "name": "generic_sprite_loader",
        "start_gba_address": _gba(SOURCE_LOADER_RANGE[0]),
        "end_gba_address_exclusive": _gba(SOURCE_LOADER_RANGE[1]),
        "sha256": SOURCE_LOADER_SHA256,
    }
    code_slices = source_manifest.get("code_slices")
    if not isinstance(code_slices, list) or not code_slices or code_slices[0] != expected_loader:
        raise ValueError("sprite-definition loader provenance changed")
    return {
        "artifact_schema": SOURCE_SCHEMA,
        "manifest": {"path": SOURCE_MANIFEST.as_posix(), "sha256": SOURCE_MANIFEST_SHA256},
        "exporter": {"path": SOURCE_EXPORTER.as_posix(), "sha256": SOURCE_EXPORTER_SHA256},
        "verifier": {"path": SOURCE_VERIFIER.as_posix(), "sha256": SOURCE_VERIFIER_SHA256},
        "test": {"path": SOURCE_TEST.as_posix(), "sha256": SOURCE_TEST_SHA256},
        "verifier_report": {
            "schema": SOURCE_VERIFY_SCHEMA,
            "sha256": SOURCE_VERIFY_REPORT_SHA256,
            "verified_entries": ENTRY_COUNT,
        },
        "entry_count": ENTRY_COUNT,
        "consumer_evidence": {
            "json_pointer": TARGET_SOURCE_POINTER,
            "name": "generic_sprite_loader",
            "file_range": list(SOURCE_LOADER_RANGE),
            "gba_range": [_gba(value) for value in SOURCE_LOADER_RANGE],
            "sha256": SOURCE_LOADER_SHA256,
            "entry_count": ENTRY_COUNT,
        },
    }


def _load_source_verifier(root: Path):
    path = _safe_file(root, SOURCE_VERIFIER)
    if _sha(path.read_bytes()) != SOURCE_VERIFIER_SHA256:
        raise ValueError("sprite-definition source verifier identity changed")
    purelib = sysconfig.get_path("purelib")
    if purelib and purelib not in sys.path:
        sys.path.append(purelib)
    spec = importlib.util.spec_from_file_location("sprite_definition_source_verifier", path)
    if spec is None or spec.loader is None:
        raise ValueError("sprite-definition source verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_source(root: Path) -> dict[str, Any]:
    source_verifier = _load_source_verifier(root)
    report = source_verifier.verify_sprite_definition_animations(root, root / SOURCE_DIR)
    if report.get("errors"):
        raise ValueError(f"sprite-definition source independent verification failed: {report['errors']}")
    return _source_identity(root, report)


def _validate_coverage(raw: bytes) -> dict[str, Any]:
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("sprite loader coverage identity changed")
    try:
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("sprite loader coverage is not valid JSON") from error
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("sprite loader coverage schema changed")
    if coverage.get("base_rom") != {"path": ROM_PATH.as_posix(), "sha256": ROM_SHA256, "size": ROM_SIZE}:
        raise ValueError("sprite loader coverage ROM identity changed")
    if coverage.get("domain") != [0, ROM_SIZE] or coverage.get("policy", {}).get("ranges_are_half_open") is not True:
        raise ValueError("sprite loader coverage domain or range policy changed")
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("sprite loader coverage ledgers are missing")
    start, end = TARGET_RANGE
    for claim in claims:
        claim_range = claim.get("range")
        if not isinstance(claim_range, list) or len(claim_range) != 2:
            raise ValueError("sprite loader coverage claim range is malformed")
        claim_start, claim_end = claim_range
        if not isinstance(claim_start, int) or not isinstance(claim_end, int) or claim_start >= claim_end:
            raise ValueError("sprite loader coverage claim range is invalid")
        if claim_start < end and start < claim_end:
            raise ValueError("sprite loader range overlaps coverage claim")
    cursor = start
    owners = []
    for segment in segments:
        segment_range = segment.get("range")
        if not isinstance(segment_range, list) or len(segment_range) != 2:
            raise ValueError("sprite loader coverage segment range is malformed")
        segment_start, segment_end = segment_range
        if segment_end <= cursor:
            continue
        if segment_start > cursor:
            break
        if segment_start <= cursor < segment_end:
            piece_end = min(segment_end, end)
            if segment.get("primary_class") != "unknown":
                raise ValueError("sprite loader range is not current unknown")
            if segment.get("primary_claim_ids") != [] or segment.get("secondary_claim_ids") != []:
                raise ValueError("sprite loader range has existing primary/secondary ownership")
            owners.append(segment)
            cursor = piece_end
            if cursor == end:
                break
    if cursor != end or not owners:
        raise ValueError("sprite loader range is not fully current unknown")
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
            "path": Path("tools/export_rom_sprite_loader_tail.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tools/export_rom_sprite_loader_tail.py").read_bytes()),
        },
        "test": {
            "path": Path("tests/test_export_rom_sprite_loader_tail.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tests/test_export_rom_sprite_loader_tail.py").read_bytes()),
        },
        "verifier": {
            "path": Path("tools/verify_rom_sprite_loader_tail.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tools/verify_rom_sprite_loader_tail.py").read_bytes()),
        },
    }


def _range_denominator() -> str:
    return _sha(_canonical([list(TARGET_RANGE)]))


def build_payload(root: Path, rom: bytes | None = None, coverage: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    source = _verify_source(root)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    if coverage is None:
        coverage = _safe_file(root, COVERAGE_PATH).read_bytes()
    coverage_identity = _validate_coverage(coverage)
    raw = rom[TARGET_RANGE[0] : TARGET_RANGE[1]]
    if len(raw) != TARGET_RANGE[1] - TARGET_RANGE[0] or _sha(raw) != TARGET_SHA256:
        raise ValueError("sprite loader terminal tail raw bytes changed")
    if _sha(raw) != EXPECTED_PACKED_SHA256:
        raise ValueError("sprite loader terminal tail packed bytes changed")
    row = {
        "id": "generic-sprite-loader-terminal-tail",
        "role": "fixed_43_entry_sprite_definition_animation_consumer_loader_terminal_tail",
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
            "manifest_path": SOURCE_MANIFEST.as_posix(),
            "manifest_sha256": SOURCE_MANIFEST_SHA256,
            "json_pointer": TARGET_SOURCE_POINTER,
            "loader_file_range": list(SOURCE_LOADER_RANGE),
            "loader_gba_range": [_gba(value) for value in SOURCE_LOADER_RANGE],
            "loader_sha256": SOURCE_LOADER_SHA256,
            "entry_count": ENTRY_COUNT,
        },
        "coverage_state": coverage_identity["current_primary_state"],
    }
    payload = {
        "schema": SCHEMA,
        "artifact_status": "accepted",
        "rom": {"path": ROM_PATH.as_posix(), "sha256": ROM_SHA256, "size": len(rom)},
        "coverage": {"path": coverage_identity["path"], "sha256": coverage_identity["sha256"]},
        "source": source,
        "range": row,
        "range_denominator_sha256": _range_denominator(),
        "packed_bytes": raw.hex(),
        "packed_bytes_sha256": _sha(raw),
        "summary": {
            "range_count": 1,
            "bytes": len(raw),
            "packed_bytes": len(raw),
            "current_unknown_bytes": len(raw),
            "primary_overlap_bytes": 0,
            "secondary_overlap_bytes": 0,
        },
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
    }
    return payload, raw


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
                "tools/verify_rom_sprite_loader_tail.py",
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
    verifier_path = _safe_file(root, "tools/verify_rom_sprite_loader_tail.py")
    spec = importlib.util.spec_from_file_location("sprite_loader_tail_packet_verifier", verifier_path)
    if spec is None or spec.loader is None:
        raise ValueError("sprite loader packet verifier cannot be loaded")
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
