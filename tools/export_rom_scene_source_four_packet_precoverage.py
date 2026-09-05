#!/usr/bin/env python3
"""Reconstruct and freeze the exact precoverage for the 2026-09-05 batch."""

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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.audit_rom_byte_coverage import (  # noqa: E402
    _cfg_code_aggregate,
    _canonical_json_bytes,
    atomize_claims,
)


SOURCE_COVERAGE = Path("sequel/rom-byte-coverage.json")
SOURCE_SHA256 = "9bab52d3d4b34490bf0699a2994294c73770bdcdfea1775cbd1d12dc48893fb4"
SOURCE_SIZE = 31_201_261
SNAPSHOT_SHA256 = "ae7c69330285bd3d668612b057a793f1b98edda5e0df421a8bda6f5e90290024"
SNAPSHOT_SIZE = 30_889_492
ROM_SIZE = 6_291_456
ARCHIVE_NAME = "rom-byte-coverage.json.gz"
OFFICIAL_ARTIFACT = Path(
    "artifacts/rom-scene-source-four-packet-precoverage-v1"
)
EXPERIMENT_ROOT = Path(
    "build/experiments/active/scene-source-four-packet-tier2-20260905"
)
REMOVED_BATCHES = {
    "rom-v17-v18-helper-cfg-v1": (14, 1_254),
    "rom-fixed-pair-tables-v1": (2, 42),
    "rom-prebattle-menu-controller-cfg-v1": (52, 1_920),
    "rom-scene-source-closures-v1": (73, 1_015),
}
IMPLEMENTATION_PATHS = {
    "exporter": Path("tools/export_rom_scene_source_four_packet_precoverage.py"),
    "test": Path("tests/test_export_rom_scene_source_four_packet_precoverage.py"),
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
    source_raw = _safe_file(root, SOURCE_COVERAGE).read_bytes()
    if len(source_raw) != SOURCE_SIZE or _sha(source_raw) != SOURCE_SHA256:
        raise ValueError("post-batch coverage identity changed")
    source = json.loads(source_raw)
    removed = []
    retained = []
    for claim in source["claims"]:
        if claim.get("promotion_batch") in REMOVED_BATCHES:
            removed.append(claim)
        else:
            retained.append(claim)
    for batch, (claim_count, byte_count) in REMOVED_BATCHES.items():
        selected = [claim for claim in removed
                    if claim.get("promotion_batch") == batch]
        actual = (len(selected), sum(
            claim["range"][1] - claim["range"][0] for claim in selected))
        if actual != (claim_count, byte_count):
            raise ValueError(f"removed batch denominator changed: {batch}")
    if len(removed) != 141 or sum(
            claim["range"][1] - claim["range"][0] for claim in removed) != 4_231:
        raise ValueError("removed batch union changed")

    segments = atomize_claims(ROM_SIZE, retained)
    totals: dict[str, int] = {}
    for segment in segments:
        size = segment["range"][1] - segment["range"][0]
        totals[segment["primary_class"]] = (
            totals.get(segment["primary_class"], 0) + size
        )
    reconstructed = json.loads(json.dumps(source))
    reconstructed["claims"] = retained
    reconstructed["segments"] = segments
    reconstructed["summary"].update({
        "rom_bytes": ROM_SIZE,
        "accounted_bytes": sum(totals.values()),
        "classified_bytes": sum(totals.values()) - totals.get("unknown", 0),
        "unknown_bytes": totals.get("unknown", 0),
        "claim_count": len(retained),
        "segment_count": len(segments),
    })
    reconstructed["summary"].update(_cfg_code_aggregate(retained))
    snapshot_raw = _canonical_json_bytes(reconstructed)
    if len(snapshot_raw) != SNAPSHOT_SIZE or _sha(snapshot_raw) != SNAPSHOT_SHA256:
        raise ValueError("reconstructed precoverage identity changed")
    source_receipt = {
        "path": SOURCE_COVERAGE.as_posix(),
        "sha256": SOURCE_SHA256,
        "size": SOURCE_SIZE,
        "removed_batches": {
            batch: {"claim_count": value[0], "bytes": value[1]}
            for batch, value in REMOVED_BATCHES.items()
        },
        "removed_claim_count": len(removed),
        "removed_bytes": sum(
            claim["range"][1] - claim["range"][0] for claim in removed),
    }
    return snapshot_raw, source_receipt


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
    try:
        relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("unauthorized output") from error
    if ".." in relative.parts:
        raise ValueError("unauthorized output")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("unauthorized output")
    resolved = lexical.resolve(strict=False)
    official = (root / OFFICIAL_ARTIFACT).resolve(strict=False)
    experiment = (root / EXPERIMENT_ROOT).resolve(strict=True)
    if resolved != lexical or (resolved != official
                               and not resolved.is_relative_to(experiment)):
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
        "recovery": {
            "kind": "reverse-exact-four-packet-projection",
            "source": source,
        },
        "files": {ARCHIVE_NAME: {
            "compression": "gzip", "file": ARCHIVE_NAME,
            "sha256": _sha(archive_raw), "size": len(archive_raw),
            "uncompressed_sha256": SNAPSHOT_SHA256,
            "uncompressed_size": SNAPSHOT_SIZE,
        }},
        "implementation": {
            name: {"path": path.as_posix(),
                   "sha256": _sha(_safe_file(root, path).read_bytes())}
            for name, path in IMPLEMENTATION_PATHS.items()
        },
        "producer": {"command": [
            "python3", "tools/export_rom_scene_source_four_packet_precoverage.py",
            "--root", ".", "--output",
            OFFICIAL_ARTIFACT.as_posix(),
        ]},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,
                                     prefix=".scene-source-precoverage-") as raw:
        stage = Path(raw)
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
