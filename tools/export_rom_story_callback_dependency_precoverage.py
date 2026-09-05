#!/usr/bin/env python3
"""Freeze the immutable baseline for the story-callback dependency packet."""

from __future__ import annotations

import argparse
import ctypes
import errno
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


SOURCE_COVERAGE = Path("sequel/rom-byte-coverage.json")
SOURCE_SHA256 = "b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82"
SOURCE_SIZE = 31_201_261
ARCHIVE_NAME = "rom-byte-coverage.json.gz"
OFFICIAL_ARTIFACT = Path(
    "artifacts/rom-story-callback-dependency-closures-precoverage-v1"
)
IMPLEMENTATION_PATHS = {
    "exporter": Path("tools/export_rom_story_callback_dependency_precoverage.py"),
    "test": Path("tests/test_export_rom_story_callback_dependency_precoverage.py"),
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _safe_file(root: Path, relative: Path) -> Path:
    root = root.resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe input path")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("unsafe input path")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(root) or not result.is_file():
        raise ValueError("unsafe input path")
    return result


def build_snapshot(root: Path) -> tuple[bytes, dict[str, Any]]:
    root = root.resolve(strict=True)
    raw = _safe_file(root, SOURCE_COVERAGE).read_bytes()
    if len(raw) != SOURCE_SIZE or _sha(raw) != SOURCE_SHA256:
        raise ValueError("story callback precoverage identity changed")
    coverage = json.loads(raw)
    if raw != _canonical(coverage):
        raise ValueError("story callback precoverage is not canonical JSON")
    summary = coverage.get("summary", {})
    if tuple(summary.get(key) for key in (
        "classified_bytes", "unknown_bytes", "claim_count", "segment_count"
    )) != (6_198_347, 93_109, 16_793, 18_552):
        raise ValueError("story callback precoverage summary changed")
    return raw, {
        "path": SOURCE_COVERAGE.as_posix(),
        "sha256": SOURCE_SHA256,
        "size": SOURCE_SIZE,
    }


def _publish_exclusive(source: Path, destination: Path) -> None:
    source, destination = source.absolute(), destination.absolute()
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd,
                  os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            if code == errno.EEXIST:
                raise FileExistsError(destination)
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)


def _authorized(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = (output if output.is_absolute() else root / output).absolute()
    if not lexical.is_relative_to(root):
        raise ValueError("unauthorized output")
    for parent in (lexical, *lexical.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("unauthorized output")
    resolved = lexical.resolve(strict=False)
    relative = resolved.relative_to(root)
    if relative != OFFICIAL_ARTIFACT and relative.parts[:2] != ("build", "experiments"):
        raise ValueError("unauthorized output")
    return resolved


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    output = _authorized(root, output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    snapshot_raw, source = build_snapshot(root)
    archive_raw = gzip.compress(snapshot_raw, compresslevel=9, mtime=0)
    manifest = {
        "schema": "rom-byte-coverage-prepromotion-baseline-v1",
        "artifact_status": "accepted",
        "source": source,
        "files": {ARCHIVE_NAME: {
            "compression": "gzip",
            "file": ARCHIVE_NAME,
            "sha256": _sha(archive_raw),
            "size": len(archive_raw),
            "uncompressed_sha256": SOURCE_SHA256,
            "uncompressed_size": SOURCE_SIZE,
        }},
        "implementation": {
            name: {
                "path": path.as_posix(),
                "sha256": _sha(_safe_file(root, path).read_bytes()),
            }
            for name, path in IMPLEMENTATION_PATHS.items()
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=output.parent, prefix=".story-dependency-precoverage-"
    ) as directory:
        stage = Path(directory)
        (stage / ARCHIVE_NAME).write_bytes(archive_raw)
        (stage / "manifest.json").write_bytes(_canonical(manifest))
        _publish_exclusive(stage, output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
