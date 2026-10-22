#!/usr/bin/env python3
"""Independently verify the fixed dialogue inter-record zero-padding inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

try:
    from tools.verify_rom_dialogue_text_inventory import (
        verify_artifact as verify_dialogue_artifact,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from verify_rom_dialogue_text_inventory import (
        verify_artifact as verify_dialogue_artifact,
    )


SCHEMA = "rom-dialogue-padding-inventory-v1"
VERIFY_SCHEMA = "rom-dialogue-padding-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SIZE = 6_291_456
TABLE_START = 0x461CE4
TABLE_END = 0x4634B8
ROW_COUNT = 305
ROW_SIZE = 20
TEXT_START = 0x459414
SOURCE_ARTIFACT = Path("artifacts/rom-dialogue-text-inventory-v1")
SOURCE_PAYLOAD_NAME = "dialogue-text-inventory.json"
SOURCE_MANIFEST_SHA256 = "0e8f3276ff5eac20c089299174abeac36b930fd71e368b16cc97e0cce22e4d7d"
SOURCE_PAYLOAD_SHA256 = "b25734be4eaed46aa199792d98e7e998389942cba914d38e2790533a558b3952"
SOURCE_VERIFIER = Path("tools/verify_rom_dialogue_text_inventory.py")
SOURCE_VERIFIER_SHA256 = "ac74891c2fc7807d727aa9de7b4fcb11a2e6dc622dc769bf3cd166b8c5481377"
SOURCE_VERIFY_REPORT = {
    "schema": "rom-dialogue-text-inventory-verification-v1",
    "verified": True,
    "table_row_count": 305,
    "table_byte_count": 6_100,
    "sentinel_count": 305,
    "direct_pointer_slot_count": 1_220,
    "direct_target_count": 1_220,
    "unique_target_count": 1_220,
    "duplicate_target_count": 0,
    "overlapping_target_range_count": 0,
    "direct_target_bytes": 18_207,
    "target_payload_bytes": 16_987,
    "newline_target_count": 170,
    "newline_count": 203,
    "errors": [],
}
PAYLOAD_NAME = "dialogue-padding-inventory.json"
BUNDLE_NAME = "dialogue-padding-zero.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
EXPECTED_SUMMARY = {
    "source_target_count": 1_220,
    "gap_count": 1_219,
    "padding_bytes": 16_814,
    "zero_byte_count": 16_814,
    "nonzero_gap_count": 0,
}
SCOPE = {
    "source_dialogue_inventory_verified": True,
    "fixed_target_denominator_complete": True,
    "adjacent_gap_denominator_complete": True,
    "all_gap_bytes_zero": True,
    "text_semantics_claimed": False,
    "runtime_reachability_claimed": False,
    "safe_allocatable_space_claimed": False,
}
LIMITATIONS = [
    "the gaps are structural padding between independently pointed NUL targets, not text payload",
    "zero padding is not claimed to be free or safe allocatable ROM space",
    "the inventory does not prove natural gameplay reachability of every dialogue row",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_dialogue_padding_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_dialogue_padding_inventory.py").read_bytes()
        ),
    }


def _safe_repo_input(
    root: Path, relative: Path, *, directory: bool
) -> Path:
    requested = (root / relative).absolute()
    try:
        resolved = requested.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise ValueError(
            f"source dialogue input is missing, outside the repository, or uses a symlink: {relative}"
        ) from error
    if resolved != requested or (directory and not requested.is_dir()) or (
        not directory and not requested.is_file()
    ):
        raise ValueError(f"source dialogue input uses a symlink: {relative}")
    return requested


def _source_artifact_record(root: Path) -> dict[str, Any]:
    artifact = _safe_repo_input(root, SOURCE_ARTIFACT, directory=True)
    members = list(artifact.rglob("*"))
    if any(member.is_symlink() for member in members):
        raise ValueError("source dialogue artifact contains a symlink")
    manifest_path = _safe_repo_input(
        root, SOURCE_ARTIFACT / "manifest.json", directory=False
    )
    payload_path = _safe_repo_input(
        root, SOURCE_ARTIFACT / SOURCE_PAYLOAD_NAME, directory=False
    )
    verifier_path = _safe_repo_input(root, SOURCE_VERIFIER, directory=False)
    manifest_raw = manifest_path.read_bytes()
    payload_raw = payload_path.read_bytes()
    verifier_raw = verifier_path.read_bytes()
    if _sha(manifest_raw) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source dialogue manifest SHA-256 changed")
    if _sha(payload_raw) != SOURCE_PAYLOAD_SHA256:
        raise ValueError("source dialogue payload SHA-256 changed")
    if _sha(verifier_raw) != SOURCE_VERIFIER_SHA256:
        raise ValueError("source dialogue verifier SHA-256 changed")
    report = verify_dialogue_artifact(root, artifact)
    if report != SOURCE_VERIFY_REPORT:
        raise ValueError(f"source dialogue verification changed: {report}")
    return {
        "path": SOURCE_ARTIFACT.as_posix(),
        "manifest_sha256": SOURCE_MANIFEST_SHA256,
        "payload_file": SOURCE_PAYLOAD_NAME,
        "payload_sha256": SOURCE_PAYLOAD_SHA256,
        "verifier_path": SOURCE_VERIFIER.as_posix(),
        "verifier_sha256": SOURCE_VERIFIER_SHA256,
        "verifier_report": SOURCE_VERIFY_REPORT,
        "target_count": 1_220,
    }


def _rebuild_targets_and_gaps(
    rom: bytes,
) -> tuple[list[dict[str, Any]], bytes, dict[str, int]]:
    if TABLE_END - TABLE_START != ROW_COUNT * ROW_SIZE:
        raise AssertionError("dialogue table constants are inconsistent")
    targets: list[dict[str, Any]] = []
    for row_id, words in enumerate(
        struct.iter_unpack("<5I", rom[TABLE_START:TABLE_END])
    ):
        if words[0] != 0:
            raise ValueError(f"source dialogue row {row_id} sentinel changed")
        for pointer in words[1:]:
            target_id = len(targets)
            start = pointer - ROM_BASE
            if not TEXT_START <= start < TABLE_START:
                raise ValueError(f"source dialogue target {target_id} escapes text bank")
            try:
                end = rom.index(b"\0", start, TABLE_START) + 1
            except ValueError as error:
                raise ValueError(
                    f"source dialogue target {target_id} has no NUL"
                ) from error
            payload = rom[start : end - 1]
            if any(value < 0x20 and value != 0x0A for value in payload):
                raise ValueError(
                    f"source dialogue target {target_id} control byte changed"
                )
            targets.append({"target_id": target_id, "range": [start, end]})

    if len(targets) != 1_220:
        raise ValueError("source dialogue target denominator changed")
    starts = [target["range"][0] for target in targets]
    if starts != sorted(starts) or len(starts) != len(set(starts)):
        raise ValueError("source dialogue target order changed")
    if any(
        left["range"][1] > right["range"][0]
        for left, right in zip(targets[:-1], targets[1:], strict=True)
    ):
        raise ValueError("source dialogue targets overlap")

    gaps: list[dict[str, Any]] = []
    bundle = bytearray()
    nonzero_gap_count = 0
    zero_byte_count = 0
    for gap_id, (left, right) in enumerate(
        zip(targets[:-1], targets[1:], strict=True)
    ):
        start = left["range"][1]
        end = right["range"][0]
        if start >= end:
            raise ValueError(f"dialogue adjacent gap {gap_id} is empty")
        raw = rom[start:end]
        nonzero = sum(value != 0 for value in raw)
        nonzero_gap_count += bool(nonzero)
        zero_byte_count += len(raw) - nonzero
        packed_start = len(bundle)
        bundle.extend(raw)
        packed_end = len(bundle)
        gaps.append(
            {
                "gap_id": gap_id,
                "range": [start, end],
                "gba_range": [
                    _addr(ROM_BASE + start),
                    _addr(ROM_BASE + end),
                ],
                "size": len(raw),
                "bytes_sha256": _sha(raw),
                "packed_range": [packed_start, packed_end],
                "left_target": left,
                "right_target": right,
                "classification": "dialogue_inter_record_zero_padding",
            }
        )
    summary = {
        "source_target_count": len(targets),
        "gap_count": len(gaps),
        "padding_bytes": len(bundle),
        "zero_byte_count": zero_byte_count,
        "nonzero_gap_count": nonzero_gap_count,
    }
    if summary != EXPECTED_SUMMARY or any(bundle):
        raise ValueError(f"dialogue padding denominator changed: {summary}")
    return gaps, bytes(bundle), summary


def _expected_manifest(
    root: Path,
    payload_raw: bytes,
    bundle_raw: bytes,
    source_artifact: dict[str, Any],
) -> dict[str, Any]:
    implementation = _implementation(root)
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "source_artifact": source_artifact,
        "summary": EXPECTED_SUMMARY,
        "files": {
            PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            BUNDLE_NAME: {"size": len(bundle_raw), "sha256": _sha(bundle_raw)},
        },
        "implementation": implementation,
        "scope": SCOPE,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_dialogue_padding_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": implementation["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                **EXPECTED_SUMMARY,
                "errors": [],
            },
        },
    }


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("dialogue padding artifact path uses a symlink")
        if not cursor.exists():
            break
    return requested


def verify_rom_dialogue_padding_inventory(
    root: Path, artifact_dir: Path
) -> dict[str, Any]:
    errors: list[str] = []
    summary = {key: 0 for key in EXPECTED_SUMMARY}
    try:
        root = Path(root).resolve(strict=True)
        requested = Path(artifact_dir)
        if not requested.is_absolute():
            requested = root / requested
        artifact = _reject_symlink_components(requested).resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("dialogue padding artifact is not a directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("dialogue padding artifact contains a symlink")
        actual_files = {
            member.relative_to(artifact).as_posix()
            for member in members
            if member.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError(
                f"dialogue padding artifact file set changed: {sorted(actual_files)}"
            )

        rom = (root / ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        source_artifact = _source_artifact_record(root)
        expected_gaps, expected_bundle, summary = _rebuild_targets_and_gaps(rom)

        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_raw)
        bundle_raw = (artifact / BUNDLE_NAME).read_bytes()
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        if payload_raw != _canonical_json(payload):
            raise ValueError("dialogue padding payload is not canonical JSON")
        expected_payload = {
            "schema": SCHEMA,
            "implementation": _implementation(root),
            "rom": {
                "path": ROM_PATH.as_posix(),
                "size": ROM_SIZE,
                "sha256": ROM_SHA256,
            },
            "source_artifact": source_artifact,
            "summary": EXPECTED_SUMMARY,
            "gaps": expected_gaps,
            "files": {
                BUNDLE_NAME: {
                    "size": len(expected_bundle),
                    "sha256": _sha(expected_bundle),
                }
            },
            "scope": SCOPE,
            "limitations": LIMITATIONS,
        }
        if payload != expected_payload:
            raise ValueError("dialogue padding payload differs from ROM reconstruction")
        if bundle_raw != expected_bundle:
            raise ValueError("dialogue padding bundle differs from ROM reconstruction")
        expected_manifest = _expected_manifest(
            root, payload_raw, bundle_raw, source_artifact
        )
        if manifest != expected_manifest:
            raise ValueError("dialogue padding promotion manifest bindings changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        **summary,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_rom_dialogue_padding_inventory(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
