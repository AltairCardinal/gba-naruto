#!/usr/bin/env python3
"""Build a direct ID-1 Cutscene OBJ primary-pointer A/B pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_cutscene_obj_id1_pixel_ab import (
    INPUT_STATE,
    INPUT_STATE_SHA256,
    build_pair as build_relocated_pair,
)


SCHEMA = "cutscene-obj-id1-primary-ptr-ab-build-v1"
POINTER_OFFSET = 0x53DF78
BEFORE_POINTER = 0x08BA04C0
AFTER_POINTER = 0x08BA09CC
DONOR_RESOURCE_ID = 2
EXPECTED_BASELINE_SHA256 = (
    "4da5caf8e6aedf78182b13e75829931398dfb61aee7b7f5f45cd6ec324a33c16"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise ValueError("Cutscene OBJ primary-pointer ROM sizes differ")
    return [
        index
        for index, (before, after) in enumerate(zip(left, right))
        if before != after
    ]


def build_pair(root: Path, output: Path) -> dict[str, Any]:
    """Build two production-relocated ROMs differing only at 0x53DF78."""

    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Cutscene OBJ primary-pointer output directory must be empty")

    with tempfile.TemporaryDirectory() as temporary:
        parent_dir = Path(temporary) / "relocated"
        parent = build_relocated_pair(root, parent_dir)
        baseline = (parent_dir / "baseline/baseline.gba").read_bytes()
        if (
            _sha256(baseline) != EXPECTED_BASELINE_SHA256
            or struct.unpack_from("<I", baseline, POINTER_OFFSET)[0]
            != BEFORE_POINTER
            or baseline[AFTER_POINTER - 0x08000000] != 0x10
        ):
            raise ValueError("Cutscene OBJ relocated baseline identity mismatch")

        candidate = bytearray(baseline)
        struct.pack_into("<I", candidate, POINTER_OFFSET, AFTER_POINTER)
        candidate = bytes(candidate)
        differences = _changed_offsets(baseline, candidate)
        if differences != [POINTER_OFFSET, POINTER_OFFSET + 1]:
            raise ValueError("Cutscene OBJ primary-pointer edit is not isolated")

        output.mkdir(parents=True, exist_ok=True)
        variants: dict[str, dict[str, Any]] = {}
        for name, rom in (("baseline", baseline), ("candidate", candidate)):
            variant_dir = output / name
            variant_dir.mkdir()
            rom_path = variant_dir / f"{name}.gba"
            rom_path.write_bytes(rom)
            variants[name] = {
                "rom_path": rom_path.relative_to(output).as_posix(),
                "rom_sha256": _sha256(rom),
                "rom_size": len(rom),
                "primary_pointer": struct.unpack_from(
                    "<I", rom, POINTER_OFFSET
                )[0],
            }

        parent_manifest = parent_dir / "build-manifest.json"
        manifest = {
            "schema": SCHEMA,
            "parent_schema": parent["schema"],
            "parent_build_manifest_sha256": _sha256_file(parent_manifest),
            "input_state": INPUT_STATE.as_posix(),
            "input_state_sha256": INPUT_STATE_SHA256,
            "input": {
                "key": "A",
                "down_frame": 5,
                "up_frame": 13,
                "capture_frame": 512,
            },
            "edit": {
                "offset": POINTER_OFFSET,
                "resource_id": 1,
                "field": "primary_ptr",
                "before_pointer": BEFORE_POINTER,
                "after_pointer": AFTER_POINTER,
                "donor_resource_id": DONOR_RESOURCE_ID,
            },
            "isolation": {
                "changed_rom_offsets": differences,
                "other_bytes_equal": True,
                "same_rom_size": len(baseline) == len(candidate),
            },
            "variants": variants,
        }
    _write_json(output / "build-manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_pair(args.root, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
