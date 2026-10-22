#!/usr/bin/env python3
"""Refresh pixel-A/B manifests while proving every captured payload stays fixed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from typing import Any, Callable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.export_battle_effect_pixel_ab_evidence import export_evidence
from tools.export_natural_delayed_battle_effect_pixel_ab import (
    export_evidence as export_natural_evidence,
)
from tools.build_natural_delayed_battle_effect_pixel_ab import (
    build_pair as build_natural_pair,
)
from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence
from tools.verify_natural_delayed_battle_effect_pixel_ab import (
    verify_evidence as verify_natural_evidence,
)


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


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _natural_capture_hashes(source: Path) -> dict[str, str]:
    provenance = {
        "batch-audit.json",
        "build/build-manifest.json",
        "runs/baseline/profile.json",
        "runs/baseline/output/audit.json",
        "runs/candidate/profile.json",
        "runs/candidate/output/audit.json",
    }
    return {
        path.relative_to(source).as_posix(): _sha256(path)
        for path in sorted(source.rglob("*"))
        if path.is_file() and path.relative_to(source).as_posix() not in provenance
    }


def refresh_artifact(
    root: Path,
    artifact: Path,
    *,
    exporter: Callable[[Path, Path, Path, Path], Any] = export_evidence,
    verifier: Callable[[Path, Path], dict[str, Any]] = verify_evidence,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    artifact = artifact.resolve(strict=True)
    try:
        artifact.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact path escapes repository") from error
    manifest_path = artifact / "manifest.json"
    manifest = _object(manifest_path)
    profile = _repository_path(root, manifest.get("profile"), "profile")
    raw = artifact / "raw"
    if not raw.is_dir():
        raise ValueError(f"artifact raw directory is missing: {raw}")

    original_payloads = _payload_hashes(artifact)
    with tempfile.TemporaryDirectory(
        prefix=f".{artifact.name}-refresh-", dir=artifact.parent
    ) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        exporter(root, profile, raw, rebuilt)
        if _payload_hashes(rebuilt) != original_payloads:
            raise ValueError("refreshed artifact changed captured payload bytes")

        backup = Path(temporary) / "original-manifest.json"
        candidate = Path(temporary) / "candidate-manifest.json"
        shutil.copy2(manifest_path, backup)
        shutil.copy2(rebuilt / "manifest.json", candidate)
        candidate.replace(manifest_path)
        result = verifier(root, artifact)
        if result.get("errors") or result.get("verified") is not True:
            backup.replace(manifest_path)
            raise ValueError(
                "refreshed artifact verification failed: "
                + "; ".join(str(error) for error in result.get("errors", []))
            )
    return result


def _extract_raw_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    destination_root = destination.resolve(strict=True)
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        for member in members:
            relative = Path(member.name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or member.issym()
                or member.islnk()
                or member.isdev()
            ):
                raise ValueError("natural pixel raw archive contains unsafe member")
            target = (destination / relative).resolve()
            try:
                target.relative_to(destination_root)
            except ValueError as error:
                raise ValueError(
                    "natural pixel raw archive member escapes destination"
                ) from error
        archive.extractall(destination, members=members, filter="data")


def refresh_natural_artifact(
    root: Path,
    artifact: Path,
    *,
    exporter: Callable[[Path, Path, Path, Path], Any] = export_natural_evidence,
    verifier: Callable[[Path, Path], dict[str, Any]] = verify_natural_evidence,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    artifact = artifact.resolve(strict=True)
    try:
        artifact.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact path escapes repository") from error
    manifest_path = artifact / "manifest.json"
    manifest = _object(manifest_path)
    profile = _repository_path(root, manifest.get("profile"), "profile")
    profile_payload = _object(profile)
    raw_archive = artifact / "raw.tar"
    if not raw_archive.is_file():
        raise ValueError(f"natural pixel raw archive is missing: {raw_archive}")

    with tempfile.TemporaryDirectory(
        prefix=f".{artifact.name}-refresh-", dir=artifact.parent
    ) as temporary:
        temporary_root = Path(temporary)
        source = temporary_root / "source"
        _extract_raw_archive(raw_archive, source)
        captured_hashes = _natural_capture_hashes(source)

        previous_build = _object(source / "build/build-manifest.json")
        current_build_root = temporary_root / "current-build"
        current_build = build_natural_pair(root, profile, current_build_root)
        previous_comparable = dict(previous_build)
        current_comparable = dict(current_build)
        for field in (
            "profile_sha256",
            "source_natural_phase_manifest_sha256",
        ):
            previous_comparable.pop(field, None)
            current_comparable.pop(field, None)
        if previous_comparable != current_comparable:
            raise ValueError("natural pixel provenance rebase changed build semantics")
        _write_json(source / "build/build-manifest.json", current_build)
        build_hash = _sha256(source / "build/build-manifest.json")
        phase_hash = profile_payload.get("source_natural_phase_manifest_sha256")
        if not isinstance(phase_hash, str):
            raise ValueError("natural pixel phase manifest hash is missing")

        batch_path = source / "batch-audit.json"
        batch = _object(batch_path)
        batch["build_manifest_sha256"] = build_hash
        batch_rows = {
            row.get("variant"): row
            for row in batch.get("runs", [])
            if isinstance(row, dict)
        }
        if set(batch_rows) != {"baseline", "candidate"}:
            raise ValueError("natural pixel batch run inventory mismatch")
        for variant in ("baseline", "candidate"):
            run_profile_path = source / f"runs/{variant}/profile.json"
            run_profile = _object(run_profile_path)
            run_profile["source_build_manifest_sha256"] = build_hash
            run_profile["source_natural_phase_manifest_sha256"] = phase_hash
            _write_json(run_profile_path, run_profile)
            run_profile_hash = _sha256(run_profile_path)

            audit_path = source / f"runs/{variant}/output/audit.json"
            audit = _object(audit_path)
            audit["profile_sha256"] = run_profile_hash
            _write_json(audit_path, audit)
            audit_hash = _sha256(audit_path)

            row = batch_rows[variant]
            row["profile_sha256"] = run_profile_hash
            row["audit_sha256"] = audit_hash
            if row.get("rom_sha256") != current_build["variants"][variant]["rom_sha256"]:
                raise ValueError("natural pixel provenance rebase changed runtime ROM")
        _write_json(batch_path, batch)
        if _natural_capture_hashes(source) != captured_hashes:
            raise ValueError("natural pixel provenance rebase changed captured bytes")

        rebuilt = temporary_root / "rebuilt"
        exporter(root, profile, source, rebuilt)
        if any(
            _sha256(rebuilt / name) != _sha256(artifact / name)
            for name in ("baseline.png", "candidate.png")
        ):
            raise ValueError("natural pixel provenance rebase changed final pixels")
        rebuilt_result = verifier(root, rebuilt)
        if rebuilt_result.get("errors") or rebuilt_result.get("verified") is not True:
            raise ValueError(
                "refreshed artifact verification failed before install: "
                + "; ".join(
                    str(error) for error in rebuilt_result.get("errors", [])
                )
            )

        backup = temporary_root / "original-artifact"
        artifact.rename(backup)
        rebuilt.rename(artifact)
        result = verifier(root, artifact)
        if result.get("errors") or result.get("verified") is not True:
            artifact.rename(temporary_root / "failed-artifact")
            backup.rename(artifact)
            raise ValueError(
                "refreshed artifact verification failed: "
                + "; ".join(str(error) for error in result.get("errors", []))
            )
    return result


def refresh_supported_artifact(
    root: Path,
    artifact: Path,
    *,
    generic_refresher: Callable[[Path, Path], dict[str, Any]] = refresh_artifact,
    natural_refresher: Callable[[Path, Path], dict[str, Any]] = refresh_natural_artifact,
) -> dict[str, Any]:
    manifest = _object(Path(artifact).resolve(strict=True) / "manifest.json")
    schema = manifest.get("artifact_schema")
    if schema == "battle-effect-pixel-ab-runtime-v1":
        return generic_refresher(root, artifact)
    if schema == "natural-delayed-battle-effect-pixel-ab-runtime-v1":
        return natural_refresher(root, artifact)
    raise ValueError(f"unsupported pixel artifact schema: {schema}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", required=True, type=Path)
    args = parser.parse_args()
    results = []
    for artifact in args.artifact:
        result = refresh_supported_artifact(ROOT, artifact)
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
