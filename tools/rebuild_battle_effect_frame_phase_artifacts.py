#!/usr/bin/env python3
"""Refresh phase-artifact manifests while proving all captured bytes stay fixed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.export_battle_effect_frame_phase import (
    export_artifact,
    portable_runtime_record,
)
from tools.verify_battle_effect_frame_phase import verify_artifact


ROOT = Path(__file__).resolve().parents[1]


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _repository_path(root: Path, raw: Any, label: str) -> Path:
    if not isinstance(raw, str):
        raise ValueError(f"{label} path is missing")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} path must be repository-relative")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} path escapes repository") from error
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload_hashes(artifact: Path) -> dict[str, str]:
    return {
        path.relative_to(artifact).as_posix(): _sha256(path)
        for path in sorted(artifact.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def _capture_hashes(artifact: Path) -> dict[str, str]:
    return {
        relative: digest
        for relative, digest in _payload_hashes(artifact).items()
        if relative not in {"runtime-audit.json", "guard-summary.json"}
    }


def _canonical_verifier_command(root: Path, artifact: Path) -> list[str]:
    return [
        "python3",
        "tools/verify_battle_effect_frame_phase.py",
        "--artifact",
        artifact.relative_to(root).as_posix(),
    ]


def refresh_artifact(
    root: Path,
    artifact: Path,
    *,
    exporter: Callable[[Path, Path, Path, Path], Any] = export_artifact,
    verifier: Callable[[Path], dict[str, Any]] = verify_artifact,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    artifact = artifact.resolve(strict=True)
    try:
        artifact.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact path escapes repository") from error
    manifest_path = artifact / "manifest.json"
    manifest = _object(manifest_path)
    profile = _repository_path(root, manifest.get("profile", {}).get("path"), "profile")
    guard = artifact / "guard-summary.json"
    audit = artifact / "runtime-audit.json"
    raw = artifact / "raw"
    for required in (guard, audit):
        if not required.is_file():
            raise ValueError(f"artifact input is missing: {required}")
    if not raw.is_dir():
        raise ValueError(f"artifact raw directory is missing: {raw}")

    original_captures = _capture_hashes(artifact)
    expected_guard = portable_runtime_record(_object(guard), root)
    expected_audit = portable_runtime_record(_object(audit), root)
    with tempfile.TemporaryDirectory(prefix=f".{artifact.name}-refresh-", dir=artifact.parent) as tmp:
        temporary = Path(tmp)
        source = temporary / "source"
        shutil.copytree(raw, source)
        shutil.copy2(audit, source / "audit.json")
        rebuilt = temporary / "rebuilt"
        exporter(source, guard, profile, rebuilt)
        if _capture_hashes(rebuilt) != original_captures:
            raise ValueError("refreshed artifact changed captured payload bytes")
        rebuilt_guard = _object(rebuilt / "guard-summary.json")
        rebuilt_audit = _object(rebuilt / "runtime-audit.json")
        if "guard_summary_sha256" in expected_audit:
            expected_audit["guard_summary_sha256"] = _sha256(
                rebuilt / "guard-summary.json"
            )
        if rebuilt_guard != expected_guard or rebuilt_audit != expected_audit:
            raise ValueError("refreshed artifact changed runtime audit semantics")

        backups = {
            manifest_path: temporary / "original-manifest.json",
            audit: temporary / "original-runtime-audit.json",
            guard: temporary / "original-guard-summary.json",
        }
        for destination, backup in backups.items():
            shutil.copy2(destination, backup)
        candidate = temporary / "candidate-manifest.json"
        candidate_manifest = _object(rebuilt / "manifest.json")
        verifier_info = candidate_manifest.get("verifier")
        if not isinstance(verifier_info, dict):
            raise ValueError("refreshed artifact verifier record is missing")
        verifier_info["command"] = _canonical_verifier_command(root, artifact)
        candidate.write_text(
            json.dumps(candidate_manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        candidates = {
            manifest_path: candidate,
            audit: rebuilt / "runtime-audit.json",
            guard: rebuilt / "guard-summary.json",
        }
        try:
            for destination, source in candidates.items():
                shutil.copy2(source, destination)
            result = verifier(artifact)
            if result.get("errors"):
                raise ValueError(
                    "refreshed artifact verification failed: "
                    + "; ".join(str(error) for error in result["errors"])
                )
        except Exception:
            for destination, backup in backups.items():
                shutil.copy2(backup, destination)
            raise
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", required=True, type=Path)
    args = parser.parse_args()
    results = []
    for artifact in args.artifact:
        result = refresh_artifact(ROOT, artifact)
        results.append(
            {
                "artifact": artifact.as_posix(),
                "group_id": result.get("group_id"),
                "verified": result.get("verified"),
            }
        )
    print(json.dumps({"refreshed": results}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
