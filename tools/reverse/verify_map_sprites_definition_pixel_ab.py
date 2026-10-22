#!/usr/bin/env python3
"""Verify the committed controlled map-sprites definition-pointer pixel A/B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.export_map_sprites_definition_pixel_ab import (
    EXPECTED_RAW_FILES,
    IMPLEMENTATION_FILES,
    MANIFEST_SCHEMA,
    PROMOTION_SCHEMA,
    _build_evidence,
    _validate_source,
    read_object,
    sha256_file,
)


EXPECTED_ARTIFACT_FILES = {
    "baseline.png",
    "candidate.png",
    "evidence.json",
    "manifest.json",
    "raw.tar",
}


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    artifact = Path(artifact).resolve(strict=True)
    actual_files = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    }
    if actual_files != EXPECTED_ARTIFACT_FILES:
        raise ValueError("map-sprites artifact file set mismatch")
    manifest = read_object(artifact / "manifest.json", "map-sprites artifact manifest")
    if (
        manifest.get("schema") != PROMOTION_SCHEMA
        or manifest.get("artifact_schema") != MANIFEST_SCHEMA
        or manifest.get("artifact_id") != "map-sprites-definition-id1-pixel-ab-v1"
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("verifier", {}).get("exit_code") != 0
    ):
        raise ValueError("map-sprites promotion manifest mismatch")
    expected_payload_files = {"baseline.png", "candidate.png", "evidence.json", "raw.tar"}
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != expected_payload_files:
        raise ValueError("map-sprites manifest payload file set mismatch")
    for name, digest in files.items():
        if not isinstance(digest, str) or sha256_file(artifact / name) != digest:
            raise ValueError(f"map-sprites artifact hash mismatch: {name}")
    implementation = manifest.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != set(IMPLEMENTATION_FILES):
        raise ValueError("map-sprites implementation file set mismatch")
    for name, digest in implementation.items():
        if not isinstance(digest, str) or sha256_file(root / name) != digest:
            raise ValueError(f"map-sprites implementation hash mismatch: {name}")

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source"
        source.mkdir()
        with tarfile.open(artifact / "raw.tar", "r") as archive:
            names = tuple(member.name for member in archive.getmembers())
            if names != EXPECTED_RAW_FILES:
                raise ValueError("map-sprites raw archive member set mismatch")
            if any(
                member.isdir()
                or member.issym()
                or member.islnk()
                or Path(member.name).is_absolute()
                or ".." in Path(member.name).parts
                for member in archive.getmembers()
            ):
                raise ValueError("map-sprites raw archive member safety mismatch")
            archive.extractall(source, filter="data")
        facts = _validate_source(root, source)
        expected_evidence = _build_evidence(facts)
        expected_evidence["build"]["manifest_sha256"] = sha256_file(
            source / "build/build-manifest.json"
        )
        evidence = read_object(artifact / "evidence.json", "map-sprites evidence")
        if evidence != expected_evidence:
            raise ValueError("map-sprites evidence mismatch")
        if (artifact / "baseline.png").read_bytes() != (
            source / "runs/baseline/output/final.png"
        ).read_bytes() or (artifact / "candidate.png").read_bytes() != (
            source / "runs/candidate/output/final.png"
        ).read_bytes():
            raise ValueError("map-sprites promoted PNG mismatch")
    return {
        "verified": True,
        "entry_id": evidence["entry_id"],
        "changed_pixel_count": evidence["pixels"]["changed_pixel_count"],
        "bbox_inclusive": evidence["pixels"]["bbox_inclusive"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify_artifact(args.root, args.artifact), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
