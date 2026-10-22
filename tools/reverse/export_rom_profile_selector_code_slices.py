#!/usr/bin/env python3
"""Export the two frozen profile-selector consumer code slices.

This packet is intentionally narrower than a CFG inventory.  It binds the
exact selector and line-wrapper windows already present in the independently
verified profile-text inventory, and promotes only bytes that are still
current ``unknown`` in the frozen coverage input.
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


SCHEMA = "rom-profile-selector-code-slices-v1"
VERIFY_SCHEMA = "rom-profile-selector-code-slices-verification-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "24cf30aa8049f961ce71737ca9cacfa42c63771643e8bb6784a8a834ee097987"

SOURCE_SCHEMA = "rom-profile-text-inventory-v1"
SOURCE_DIR = Path("artifacts/rom-profile-text-inventory-v1")
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
SOURCE_PAYLOAD = SOURCE_DIR / "profile-text-inventory.json"
SOURCE_REGION = SOURCE_DIR / "profile-text-region.bin"
SOURCE_VERIFIER = Path("tools/verify_rom_profile_text_inventory.py")
SOURCE_EXPORTER = Path("tools/export_rom_profile_text_inventory.py")
SOURCE_TEST = Path("tests/test_export_rom_profile_text_inventory.py")
SOURCE_MANIFEST_SHA256 = "57979c4355a182f219702d48055ff21b3b81d132ffb5240c64e152ecb54503f8"
SOURCE_PAYLOAD_SHA256 = "592c34ae72ec4ad2ebaa4847fdbc700d0ecf2e995ef1c3cec6b13aedc09646e9"
SOURCE_REGION_SHA256 = "b3b663177a39e60f691fde0ff9272df69e875a116abc5a08647c4ec5d17c142d"
SOURCE_EXPORTER_SHA256 = "bb6c5c259ab8caa822c266e7674a4642b2850e0b45764d299b66bf2d23f2e223"
SOURCE_VERIFIER_SHA256 = "87830893bf507866e6966c8f9bda558bee094be890d442f3375970f2d3084009"
SOURCE_TEST_SHA256 = "e95918f1ee0e085c513e0e4fe34056ff4fc1a7f758c6cd1c7302dac5fe30ce6e"
SOURCE_VERIFY_SCHEMA = "rom-profile-text-inventory-verification-v1"
SOURCE_VERIFY_REPORT_SHA256 = "a5d8e815d80976f193d446ccb7fa20dc325fb31edf8e8326666f963b2168e355"

RANGE_SPECS = (
    {
        "id": "profile-pointer-selector",
        "role": "profile_table_selector",
        "source_pointer": "/consumer_evidence/profile_pointer_selector",
        "range": (0x08B19E, 0x08B1B6),
        "sha256": "a85145a1f4f5342a07dda4175aa93de57ea55d5b1bb514c55ea65a1a47acf625",
    },
    {
        "id": "profile-line-wrapper",
        "role": "renderer_line_wrapper",
        "source_pointer": "/consumer_evidence/profile_line_wrapper",
        "range": (0x08D1A4, 0x08D230),
        "sha256": "7646f12d2cdcbeb8b86bb39d491906bb112ac92afd0730ae5b56ac96a7f5c552",
    },
)
EXPECTED_PACKED_SHA256 = "2d0175a6ea9e98f379c4f6e92f2baa0b1272592648c944f12827a51b154615ca"

PAYLOAD_NAME = "rom-profile-selector-code-slices.json"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = {MANIFEST_NAME, PAYLOAD_NAME}

SCOPE = {
    "primary_class": "consumer_code_slice",
    "claim_kind": "consumer_code_slice",
    "profile_table_selector_bound": True,
    "renderer_line_wrapper_bound": True,
    "source_consumer_provenance_bound": True,
    "raw_rom_exact_slices": True,
    "baseline_unknown_only": True,
    "complete_cfg_claimed": False,
    "natural_runtime_reachability_claimed": False,
    "all_profile_ids_complete": False,
    "unicode_decoding_complete": False,
    "business_fields_claimed": False,
    "adjacent_bytes_claimed": False,
    "padding_or_free_space_claimed": False,
    "editing_writeback_relocation_claimed": False,
    "allocatable_claimed": False,
    "safe_editing": False,
}

LIMITATIONS = [
    "Only the two complete source ranges frozen by the profile-text selector and line-wrapper consumer provenance are classified.",
    "The ranges are hash-bound consumer code slices; this packet does not claim a complete CFG or that every byte is an instruction.",
    "Natural runtime reachability, all profile IDs, Unicode decoding, business fields, and exhaustive callers are not claimed.",
    "Adjacent bytes outside the two ranges, padding/free/allocatable status, editing, write-back, and relocation safety are not claimed.",
]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


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
        "files": {
            "profile-text-inventory.json": SOURCE_PAYLOAD_SHA256,
            "profile-text-region.bin": SOURCE_REGION_SHA256,
        },
        "schema": f"{SOURCE_SCHEMA}-artifact-manifest-v1",
        "verification": {
            "command": [
                "python3",
                "tools/verify_rom_profile_text_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-profile-text-inventory-v1",
            ],
            "schema": SOURCE_VERIFY_SCHEMA,
        },
    }


def _source_identity(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    source_manifest_path = _safe_file(root, SOURCE_MANIFEST)
    source_payload_path = _safe_file(root, SOURCE_PAYLOAD)
    source_region_path = _safe_file(root, SOURCE_REGION)
    source_exporter_path = _safe_file(root, SOURCE_EXPORTER)
    source_verifier_path = _safe_file(root, SOURCE_VERIFIER)
    source_test_path = _safe_file(root, SOURCE_TEST)
    if _sha(source_manifest_path.read_bytes()) != SOURCE_MANIFEST_SHA256:
        raise ValueError("profile-text source manifest identity changed")
    if _sha(source_payload_path.read_bytes()) != SOURCE_PAYLOAD_SHA256:
        raise ValueError("profile-text source payload identity changed")
    if _sha(source_region_path.read_bytes()) != SOURCE_REGION_SHA256:
        raise ValueError("profile-text source region identity changed")
    if _sha(source_exporter_path.read_bytes()) != SOURCE_EXPORTER_SHA256:
        raise ValueError("profile-text source exporter identity changed")
    if _sha(source_verifier_path.read_bytes()) != SOURCE_VERIFIER_SHA256:
        raise ValueError("profile-text source verifier identity changed")
    if _sha(source_test_path.read_bytes()) != SOURCE_TEST_SHA256:
        raise ValueError("profile-text source test identity changed")
    if not report.get("verified") or report.get("schema") != SOURCE_VERIFY_SCHEMA:
        raise ValueError("profile-text source verifier did not close")
    if _sha(_canonical(report)) != SOURCE_VERIFY_REPORT_SHA256:
        raise ValueError("profile-text source verifier report identity changed")
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest != _source_manifest_expected():
        raise ValueError("profile-text source manifest contract changed")
    source_payload = json.loads(source_payload_path.read_text(encoding="utf-8"))
    expected_implementation = {
        "exporter": {
            "path": SOURCE_EXPORTER.as_posix(),
            "sha256": SOURCE_EXPORTER_SHA256,
        },
        "test": {"path": SOURCE_TEST.as_posix(), "sha256": SOURCE_TEST_SHA256},
        "verifier": {
            "path": SOURCE_VERIFIER.as_posix(),
            "sha256": SOURCE_VERIFIER_SHA256,
        },
    }
    if source_payload.get("schema") != SOURCE_SCHEMA:
        raise ValueError("profile-text source payload schema changed")
    if source_payload.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "size": ROM_SIZE,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("profile-text source ROM identity changed")
    if source_payload.get("implementation") != expected_implementation:
        raise ValueError("profile-text source implementation identity changed")
    expected_evidence = {
        "profile_pointer_selector": {
            "address": _gba(RANGE_SPECS[0]["range"][0]),
            "gba_range": [_gba(value) for value in RANGE_SPECS[0]["range"]],
            "range": list(RANGE_SPECS[0]["range"]),
            "sha256": RANGE_SPECS[0]["sha256"],
        },
        "profile_line_wrapper": {
            "address": _gba(RANGE_SPECS[1]["range"][0]),
            "call_offset": 0x08D214,
            "call_target": _gba(0x066758),
            "gba_range": [_gba(value) for value in RANGE_SPECS[1]["range"]],
            "range": list(RANGE_SPECS[1]["range"]),
            "sha256": RANGE_SPECS[1]["sha256"],
        },
    }
    consumer_evidence = source_payload.get("consumer_evidence", {})
    for key, expected in expected_evidence.items():
        if consumer_evidence.get(key) != expected:
            raise ValueError(f"profile-text source {key} provenance changed")
    return {
        "artifact_schema": SOURCE_SCHEMA,
        "manifest": {
            "path": SOURCE_MANIFEST.as_posix(),
            "sha256": SOURCE_MANIFEST_SHA256,
        },
        "payload": {
            "path": SOURCE_PAYLOAD.as_posix(),
            "sha256": SOURCE_PAYLOAD_SHA256,
        },
        "region": {
            "path": SOURCE_REGION.as_posix(),
            "sha256": SOURCE_REGION_SHA256,
        },
        "exporter": {
            "path": SOURCE_EXPORTER.as_posix(),
            "sha256": SOURCE_EXPORTER_SHA256,
        },
        "verifier": {
            "path": SOURCE_VERIFIER.as_posix(),
            "sha256": SOURCE_VERIFIER_SHA256,
        },
        "test": {"path": SOURCE_TEST.as_posix(), "sha256": SOURCE_TEST_SHA256},
        "verifier_report": {
            "schema": SOURCE_VERIFY_SCHEMA,
            "sha256": SOURCE_VERIFY_REPORT_SHA256,
        },
    }


def _verify_source(root: Path) -> dict[str, Any]:
    """Run the upstream verifier before consuming any source labels."""

    verifier_path = _safe_file(root, SOURCE_VERIFIER)
    if _sha(verifier_path.read_bytes()) != SOURCE_VERIFIER_SHA256:
        raise ValueError("profile-text source verifier identity changed")
    spec = importlib.util.spec_from_file_location(
        "_profile_text_source_verifier", verifier_path
    )
    if spec is None or spec.loader is None:
        raise ValueError("profile-text source verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.verify_artifact(root, root / SOURCE_DIR)
    if report.get("verified") is not True:
        raise ValueError(f"profile-text source independent verification failed: {report.get('errors', [])}")
    source = _source_identity(root, report)
    return source


def _take(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or start >= end or end > len(rom):
        raise ValueError(f"profile selector ROM range outside input: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _validate_coverage(raw: bytes, ranges: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("profile selector coverage identity changed")
    try:
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("profile selector coverage is not valid JSON") from error
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("profile selector coverage schema changed")
    if coverage.get("base_rom") != {
        "path": ROM_PATH.as_posix(),
        "size": ROM_SIZE,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("profile selector coverage ROM identity changed")
    if coverage.get("domain") != [0, ROM_SIZE]:
        raise ValueError("profile selector coverage domain changed")
    if coverage.get("policy", {}).get("ranges_are_half_open") is not True:
        raise ValueError("profile selector coverage range policy changed")
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("profile selector coverage ledgers are missing")

    for claim in claims:
        claim_range = claim.get("range")
        if not isinstance(claim_range, list) or len(claim_range) != 2:
            raise ValueError("profile selector coverage claim range is malformed")
        claim_start, claim_end = claim_range
        if not isinstance(claim_start, int) or not isinstance(claim_end, int) or claim_start >= claim_end:
            raise ValueError("profile selector coverage claim range is invalid")

    current: list[dict[str, Any]] = []
    for spec in ranges:
        start, end = spec["range"]
        for claim in claims:
            claim_start, claim_end = claim["range"]
            if claim_start < end and start < claim_end:
                raise ValueError(f"profile selector range overlaps coverage claim: {spec['id']}")
        cursor = start
        owners = []
        for segment in segments:
            segment_range = segment.get("range")
            if not isinstance(segment_range, list) or len(segment_range) != 2:
                raise ValueError("profile selector coverage segment range is malformed")
            segment_start, segment_end = segment_range
            if segment_end <= cursor:
                continue
            if segment_start > cursor:
                break
            if segment_start <= cursor < segment_end:
                piece_end = min(segment_end, end)
                if segment.get("primary_class") != "unknown":
                    raise ValueError(f"profile selector range is not current unknown: {spec['id']}")
                if segment.get("primary_claim_ids") != [] or segment.get("secondary_claim_ids") != []:
                    raise ValueError(f"profile selector range has existing ownership: {spec['id']}")
                owners.append(segment)
                cursor = piece_end
                if cursor == end:
                    break
        if cursor != end or not owners:
            raise ValueError(f"profile selector range is not fully covered by unknown segments: {spec['id']}")
        current.append(
            {
                "range": [start, end],
                "primary_class": "unknown",
                "primary_claim_ids": [],
                "secondary_claim_ids": [],
            }
        )
    return {
        "path": COVERAGE_PATH.as_posix(),
        "sha256": COVERAGE_SHA256,
        "current_primary_state": current,
    }


def _implementation(root: Path) -> dict[str, Any]:
    return {
        "exporter": {
            "path": Path("tools/export_rom_profile_selector_code_slices.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tools/export_rom_profile_selector_code_slices.py").read_bytes()),
        },
        "test": {
            "path": Path("tests/test_export_rom_profile_selector_code_slices.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tests/test_export_rom_profile_selector_code_slices.py").read_bytes()),
        },
        "verifier": {
            "path": Path("tools/verify_rom_profile_selector_code_slices.py").as_posix(),
            "sha256": _sha(_safe_file(root, "tools/verify_rom_profile_selector_code_slices.py").read_bytes()),
        },
    }


def _range_denominator(ranges: tuple[dict[str, Any], ...]) -> str:
    return _sha(_canonical([[spec["id"], list(spec["range"])] for spec in ranges]))


def build_payload(root: Path, rom: bytes | None = None, coverage: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    source = _verify_source(root)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    if coverage is None:
        coverage = _safe_file(root, COVERAGE_PATH).read_bytes()
    coverage_identity = _validate_coverage(coverage, RANGE_SPECS)
    coverage_states = {
        tuple(state["range"]): state
        for state in coverage_identity["current_primary_state"]
    }

    rows: list[dict[str, Any]] = []
    packed_parts: list[bytes] = []
    packed_cursor = 0
    for spec in RANGE_SPECS:
        start, end = spec["range"]
        raw = _take(rom, start, end)
        if _sha(raw) != spec["sha256"]:
            raise ValueError(f"profile selector source range changed: {spec['id']}")
        packed_parts.append(raw)
        packed_end = packed_cursor + len(raw)
        rows.append(
            {
                "id": spec["id"],
                "role": spec["role"],
                "claim": {
                    "role": "primary",
                    "primary_class": "consumer_code_slice",
                    "claim_kind": "consumer_code_slice",
                    "promotion_batch": SCHEMA,
                    "promoted_from_primary_class": "unknown",
                    "baseline_unknown_only": True,
                },
                "range": [start, end],
                "gba_range": [_gba(start), _gba(end)],
                "size": len(raw),
                "bytes_hex": raw.hex(),
                "bytes_sha256": _sha(raw),
                "packed_range": [packed_cursor, packed_end],
                "packed_sha256": _sha(raw),
                "source_evidence": {
                    "artifact_schema": SOURCE_SCHEMA,
                    "payload_path": SOURCE_PAYLOAD.as_posix(),
                    "payload_sha256": SOURCE_PAYLOAD_SHA256,
                    "json_pointer": spec["source_pointer"],
                    "evidence_sha256": spec["sha256"],
                    "provenance": "fixed consumer provenance independently verified by tools/verify_rom_profile_text_inventory.py",
                },
                "coverage_state": coverage_states[(start, end)],
            }
        )
        packed_cursor = packed_end
    packed = b"".join(packed_parts)
    if len(packed) != 164 or _sha(packed) != EXPECTED_PACKED_SHA256:
        raise ValueError("profile selector packed bytes changed")

    payload = {
        "schema": SCHEMA,
        "artifact_status": "accepted",
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "coverage": {
            "path": coverage_identity["path"],
            "sha256": coverage_identity["sha256"],
        },
        "source": source,
        "ranges": rows,
        "range_denominator_sha256": _range_denominator(RANGE_SPECS),
        "packed_bytes": packed.hex(),
        "packed_bytes_sha256": _sha(packed),
        "summary": {
            "range_count": len(rows),
            "bytes": sum(row["size"] for row in rows),
            "packed_bytes": len(packed),
            "current_unknown_bytes": sum(row["size"] for row in rows),
            "primary_overlap_bytes": 0,
            "secondary_overlap_bytes": 0,
        },
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": _implementation(root),
    }
    return payload, packed


def _manifest(root: Path, payload: dict[str, Any], payload_bytes: bytes) -> dict[str, Any]:
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
                "tools/verify_rom_profile_selector_code_slices.py",
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
    members = {
        member.relative_to(target).as_posix()
        for member in target.rglob("*")
        if member.is_file()
    }
    if any(member.is_symlink() for member in target.rglob("*")):
        raise ValueError("foreign artifact output directory")
    if members != EXPECTED_FILES:
        raise ValueError("foreign artifact output directory")
    try:
        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("foreign artifact output directory") from error
    if manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("foreign artifact output directory")
    verifier_path = root / "tools/verify_rom_profile_selector_code_slices.py"
    spec = importlib.util.spec_from_file_location(
        "_profile_selector_candidate_verifier", verifier_path
    )
    if spec is None or spec.loader is None:
        raise ValueError("profile selector verifier cannot be loaded")
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
    manifest_bytes = _canonical(_manifest(root, payload, payload_bytes))
    _replace_output(target, payload_bytes, manifest_bytes)
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
