#!/usr/bin/env python3
"""Refresh pixel-A/B manifests while proving every captured payload stays fixed."""

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

from tools.export_battle_effect_pixel_ab_evidence import export_evidence
from tools.verify_battle_effect_pixel_ab_evidence import verify_evidence


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
