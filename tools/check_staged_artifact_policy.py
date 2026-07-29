#!/usr/bin/env python3
"""Reject newly staged artifact directories that bypass promotion policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


PROMOTION_SCHEMA = "git-artifact-promotion-v1"
DEFAULT_MAX_FILES = 500
DEFAULT_MAX_BYTES = 250 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _new_artifact_roots(root: Path) -> list[str]:
    completed = _git(
        root,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=A",
        "-z",
        "--",
        "artifacts",
    )
    if completed.returncode:
        raise ValueError(completed.stderr.decode("utf-8", "replace"))
    roots = set()
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8", "replace")
        parts = path.split("/")
        if len(parts) < 3:
            raise ValueError(f"artifact files need a named directory: {path}")
        candidate = "/".join(parts[:2])
        exists = _git(root, "cat-file", "-e", f"HEAD:{candidate}")
        if exists.returncode:
            roots.add(candidate)
    return sorted(roots)


def _read_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("manifest.json must contain an object")
    return value


def check(
    root: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[str]:
    errors = []
    for relative_root in _new_artifact_roots(root):
        directory = root / relative_root
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            errors.append(f"{relative_root}: missing manifest.json")
            continue
        try:
            manifest = _read_manifest(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{relative_root}: invalid manifest.json: {error}")
            continue
        if manifest.get("schema") != PROMOTION_SCHEMA:
            errors.append(f"{relative_root}: promotion manifest schema mismatch")
        if manifest.get("artifact_status") != "accepted":
            errors.append(f"{relative_root}: artifact_status is not accepted")
        verifier = manifest.get("verifier")
        if (
            not isinstance(verifier, dict)
            or verifier.get("exit_code") != 0
            or not isinstance(verifier.get("command"), list)
            or not verifier["command"]
        ):
            errors.append(f"{relative_root}: verifier evidence is missing")
        expected = manifest.get("files")
        if not isinstance(expected, dict):
            errors.append(f"{relative_root}: file hash inventory is missing")
            continue
        actual = {
            path.relative_to(directory).as_posix(): path
            for path in directory.rglob("*")
            if path.is_file() and path != manifest_path
        }
        if set(actual) != set(expected):
            errors.append(f"{relative_root}: file inventory mismatch")
            continue
        for relative, path in actual.items():
            if _sha256(path) != expected[relative]:
                errors.append(f"{relative_root}: hash mismatch for {relative}")
        byte_count = sum(path.stat().st_size for path in actual.values())
        if len(actual) + 1 > max_files or byte_count > max_bytes:
            justification = manifest.get("large_artifact_justification")
            if not isinstance(justification, str) or not justification.strip():
                errors.append(
                    f"{relative_root}: exceeds file/byte budget without justification"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    try:
        errors = check(
            args.root.resolve(),
            max_files=args.max_files,
            max_bytes=args.max_bytes,
        )
    except ValueError as error:
        errors = [str(error)]
    if errors:
        for error in errors:
            print(f"artifact-policy: {error}")
        return 1
    print("artifact-policy: staged artifact check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
