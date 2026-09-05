#!/usr/bin/env python3
"""Export the fixed zero-padding gaps between verified dialogue targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import uuid

try:
    from tools.verify_rom_dialogue_padding_inventory import (
        BUNDLE_NAME,
        EXPECTED_FILES,
        EXPECTED_SUMMARY,
        LIMITATIONS,
        PAYLOAD_NAME,
        ROM_BASE,
        ROM_PATH,
        ROM_SHA256,
        SCHEMA,
        SCOPE,
        SOURCE_ARTIFACT,
        SOURCE_MANIFEST_SHA256,
        SOURCE_PAYLOAD_NAME,
        SOURCE_PAYLOAD_SHA256,
        SOURCE_VERIFIER,
        SOURCE_VERIFIER_SHA256,
        SOURCE_VERIFY_REPORT,
        VERIFY_SCHEMA,
        verify_dialogue_artifact,
        verify_rom_dialogue_padding_inventory,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from verify_rom_dialogue_padding_inventory import (
        BUNDLE_NAME,
        EXPECTED_FILES,
        EXPECTED_SUMMARY,
        LIMITATIONS,
        PAYLOAD_NAME,
        ROM_BASE,
        ROM_PATH,
        ROM_SHA256,
        SCHEMA,
        SCOPE,
        SOURCE_ARTIFACT,
        SOURCE_MANIFEST_SHA256,
        SOURCE_PAYLOAD_NAME,
        SOURCE_PAYLOAD_SHA256,
        SOURCE_VERIFIER,
        SOURCE_VERIFIER_SHA256,
        SOURCE_VERIFY_REPORT,
        VERIFY_SCHEMA,
        verify_dialogue_artifact,
        verify_rom_dialogue_padding_inventory,
    )


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
        "exporter_sha256": _sha(Path(__file__).read_bytes()),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_dialogue_padding_inventory.py").read_bytes()
        ),
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


def _source_artifact_record(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
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
    if _sha(manifest_raw) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source dialogue manifest SHA-256 changed")
    if _sha(payload_raw) != SOURCE_PAYLOAD_SHA256:
        raise ValueError("source dialogue payload SHA-256 changed")
    if _sha(verifier_path.read_bytes()) != SOURCE_VERIFIER_SHA256:
        raise ValueError("source dialogue verifier SHA-256 changed")
    report = verify_dialogue_artifact(root, artifact)
    if report != SOURCE_VERIFY_REPORT:
        raise ValueError(f"source dialogue verification changed: {report}")
    payload = json.loads(payload_raw)
    record = {
        "path": SOURCE_ARTIFACT.as_posix(),
        "manifest_sha256": SOURCE_MANIFEST_SHA256,
        "payload_file": SOURCE_PAYLOAD_NAME,
        "payload_sha256": SOURCE_PAYLOAD_SHA256,
        "verifier_path": SOURCE_VERIFIER.as_posix(),
        "verifier_sha256": SOURCE_VERIFIER_SHA256,
        "verifier_report": SOURCE_VERIFY_REPORT,
        "target_count": 1_220,
    }
    return record, payload


def _build(root: Path) -> tuple[dict[str, Any], bytes]:
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    source_artifact, source_payload = _source_artifact_record(root)
    rows = source_payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 305:
        raise ValueError("source dialogue row denominator changed")
    targets: list[dict[str, Any]] = []
    for row in rows:
        row_targets = row.get("targets") if isinstance(row, dict) else None
        if not isinstance(row_targets, list) or len(row_targets) != 4:
            raise ValueError("source dialogue target denominator changed")
        for target in row_targets:
            target_id = len(targets)
            if (
                not isinstance(target, dict)
                or target.get("target_id") != target_id
                or not isinstance(target.get("range"), list)
                or len(target["range"]) != 2
            ):
                raise ValueError(f"source dialogue target {target_id} changed")
            start, end = target["range"]
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start >= end
                or target.get("bytes_sha256") != _sha(rom[start:end])
            ):
                raise ValueError(f"source dialogue target {target_id} range changed")
            targets.append({"target_id": target_id, "range": [start, end]})
    if len(targets) != 1_220:
        raise ValueError("source dialogue target denominator changed")
    if any(
        left["range"][1] > right["range"][0]
        for left, right in zip(targets[:-1], targets[1:], strict=True)
    ):
        raise ValueError("source dialogue target order or overlap changed")

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
                "gba_range": [_addr(ROM_BASE + start), _addr(ROM_BASE + end)],
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
    bundle_raw = bytes(bundle)
    payload = {
        "schema": SCHEMA,
        "implementation": _implementation(root),
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "source_artifact": source_artifact,
        "summary": summary,
        "gaps": gaps,
        "files": {
            BUNDLE_NAME: {"size": len(bundle_raw), "sha256": _sha(bundle_raw)}
        },
        "scope": SCOPE,
        "limitations": LIMITATIONS,
    }
    return payload, bundle_raw


def _manifest(
    root: Path, payload: dict[str, Any], payload_raw: bytes, bundle_raw: bytes
) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "rom": payload["rom"],
        "source_artifact": payload["source_artifact"],
        "summary": EXPECTED_SUMMARY,
        "files": {
            PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            BUNDLE_NAME: {"size": len(bundle_raw), "sha256": _sha(bundle_raw)},
        },
        "implementation": payload["implementation"],
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
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
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
            raise ValueError("dialogue padding output path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError(
            "dialogue padding output cannot be repository root or ancestor"
        )
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("existing path is not a replaceable dialogue padding artifact")
    members = list(target.iterdir())
    if not members:
        return target
    if (
        {member.name for member in members} != EXPECTED_FILES
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError(
            "existing directory is not a replaceable dialogue padding artifact"
        )
    try:
        manifest = json.loads((target / "manifest.json").read_bytes())
        payload = json.loads((target / PAYLOAD_NAME).read_bytes())
        records = manifest["files"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(
            "existing directory is not a replaceable dialogue padding artifact"
        ) from error
    for name in (PAYLOAD_NAME, BUNDLE_NAME):
        path = target / name
        record = records.get(name)
        if (
            not isinstance(record, dict)
            or record.get("size") != path.stat().st_size
            or record.get("sha256") != _sha(path.read_bytes())
        ):
            raise ValueError(
                "existing directory is not a replaceable dialogue padding artifact"
            )
    if (
        manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("rom", {}).get("sha256") != ROM_SHA256
        or manifest.get("source_artifact", {}).get("manifest_sha256")
        != SOURCE_MANIFEST_SHA256
        or set(records) != {PAYLOAD_NAME, BUNDLE_NAME}
        or payload.get("schema") != SCHEMA
        or payload.get("rom", {}).get("sha256") != ROM_SHA256
    ):
        raise ValueError(
            "existing directory is not a replaceable dialogue padding artifact"
        )
    report = verify_rom_dialogue_padding_inventory(root, target)
    if report.get("verified") is not True:
        raise ValueError(
            "existing directory is not a replaceable dialogue padding artifact: "
            f"independent verification failed: {report.get('errors', [])}"
        )
    return target


def _replace_output_dir(output_dir: Path, temporary: Path) -> None:
    backup: Path | None = None
    try:
        if output_dir.exists():
            backup = output_dir.with_name(
                f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            )
            os.replace(output_dir, backup)
        os.replace(temporary, output_dir)
    except BaseException:
        if backup is not None and backup.exists() and not output_dir.exists():
            os.replace(backup, output_dir)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup)


def export_rom_dialogue_padding_inventory(
    root: Path, output_dir: Path
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    payload, bundle_raw = _build(root)
    payload_raw = _canonical_json(payload)
    manifest = _manifest(root, payload, payload_raw, bundle_raw)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-dialogue-padding-", dir=output_dir.parent)
    )
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        (temporary / BUNDLE_NAME).write_bytes(bundle_raw)
        (temporary / "manifest.json").write_bytes(_canonical_json(manifest))
        _validate_output_dir(root, temporary)
        _replace_output_dir(output_dir, temporary)
        return payload
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_rom_dialogue_padding_inventory(args.root, output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
