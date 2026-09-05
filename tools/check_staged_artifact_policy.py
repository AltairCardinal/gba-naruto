#!/usr/bin/env python3
"""Validate new artifact directories in frozen Git index and baseline trees."""

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


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _new_artifact_roots(
    root: Path, tree: str, baseline: str | None
) -> list[str]:
    if baseline is not None:
        completed = _git(
            root, "diff", "--name-only", "--diff-filter=A", "-z",
            baseline, tree, "--", "artifacts",
        )
    else:
        completed = _git(
            root, "ls-tree", "-r", "--name-only", "-z", tree, "--", "artifacts",
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
        if baseline is not None:
            kind = _git(root, "cat-file", "-t", f"{baseline}:{candidate}")
            if kind.returncode == 0 and kind.stdout.strip() == b"tree":
                continue
        roots.add(candidate)
    return sorted(roots)


def _read_manifest(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("manifest.json must contain an object")
    return value


def _staged_members(root: Path, tree: str, directory: str) -> dict[str, bytes]:
    completed = _git(root, "ls-tree", "-r", "-z", tree, "--", directory)
    if completed.returncode:
        raise ValueError(completed.stderr.decode("utf-8", "replace"))
    members = {}
    for entry in completed.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        relative = path.decode("utf-8").removeprefix(directory + "/")
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise ValueError(f"non-regular staged member: {relative}")
        blob = _git(root, "cat-file", "blob", oid.decode("ascii"))
        if blob.returncode:
            raise ValueError(blob.stderr.decode("utf-8", "replace"))
        members[relative] = blob.stdout
    return members


def check(
    root: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[str]:
    errors = []
    # Freeze the baseline and index. Every subsequent read uses immutable objects,
    # so worktree edits cannot validate different bytes from the proposed commit.
    head = _git(root, "rev-parse", "--verify", "HEAD^{tree}")
    baseline = head.stdout.decode("ascii").strip() if head.returncode == 0 else None
    snapshot = _git(root, "write-tree")
    if snapshot.returncode:
        raise ValueError(snapshot.stderr.decode("utf-8", "replace"))
    tree = snapshot.stdout.decode("ascii").strip()
    for relative_root in _new_artifact_roots(root, tree, baseline):
        try:
            actual = _staged_members(root, tree, relative_root)
        except (ValueError, UnicodeError) as error:
            errors.append(f"{relative_root}: {error}")
            continue
        manifest_raw = actual.pop("manifest.json", None)
        if manifest_raw is None:
            errors.append(f"{relative_root}: missing manifest.json")
            continue
        try:
            manifest = _read_manifest(manifest_raw)
        except (ValueError, UnicodeError) as error:
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
        if set(actual) != set(expected):
            errors.append(f"{relative_root}: file inventory mismatch")
            continue
        for relative, raw in actual.items():
            receipt = expected[relative]
            expected_hash = receipt
            expected_size = None
            if isinstance(receipt, dict):
                if (
                    set(receipt) != {"sha256", "size"}
                    or type(receipt.get("size")) is not int
                    or receipt["size"] < 0
                ):
                    errors.append(f"{relative_root}: malformed file receipt for {relative}")
                    continue
                expected_hash = receipt["sha256"]
                expected_size = receipt["size"]
            if (
                not isinstance(expected_hash, str)
                or len(expected_hash) != 64
                or any(c not in "0123456789abcdef" for c in expected_hash)
            ):
                errors.append(f"{relative_root}: malformed file receipt for {relative}")
                continue
            if hashlib.sha256(raw).hexdigest() != expected_hash:
                errors.append(f"{relative_root}: hash mismatch for {relative}")
            if expected_size is not None and len(raw) != expected_size:
                errors.append(f"{relative_root}: size mismatch for {relative}")
        byte_count = sum(map(len, actual.values()))
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
