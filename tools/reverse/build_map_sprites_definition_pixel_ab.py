#!/usr/bin/env python3
"""Build the isolated ROM pair for the controlled map-sprites definition A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PROFILE_SCHEMA = "map-sprites-definition-pixel-ab-profile-v1"
BUILD_SCHEMA = "map-sprites-definition-pixel-ab-build-v1"
TABLE_OFFSET = 0x53F140
ENTRY_SIZE = 8
ENTRY_ID = 1
DONOR_ENTRY_ID = 37
BEFORE_POINTER = 0x0812F5D8
AFTER_POINTER = 0x0812F7CC


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def require_repo_file(root: Path, value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"map-sprites {label} path mismatch")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"map-sprites {label} must be repository-relative")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"map-sprites {label} must stay inside repository")
    if not isinstance(digest, str) or sha256_file(path) != digest:
        raise ValueError(f"map-sprites {label} hash mismatch")
    return path


def validate_profile(root: Path, profile_path: Path) -> dict[str, Any]:
    profile = read_object(profile_path, "map-sprites pixel A/B profile")
    expected = {
        "schema": PROFILE_SCHEMA,
        "table_offset": TABLE_OFFSET,
        "entry_size": ENTRY_SIZE,
        "entry_id": ENTRY_ID,
        "field": "definition_ptr",
        "field_offset": 0,
        "before_pointer": f"0x{BEFORE_POINTER:08X}",
        "after_pointer": f"0x{AFTER_POINTER:08X}",
        "donor_entry_id": DONOR_ENTRY_ID,
        "task_slot": 123,
        "input_mode": "zero-input-controlled-task-materialization",
        "inputs": [],
        "capture_post_boundary_frames": 2,
    }
    for key, value in expected.items():
        if profile.get(key) != value:
            raise ValueError(f"map-sprites profile {key} mismatch")
    bank_path = require_repo_file(
        root, profile.get("source_bank"), profile.get("source_bank_sha256"), "bank"
    )
    assets_path = require_repo_file(
        root,
        profile.get("source_asset_manifest"),
        profile.get("source_asset_manifest_sha256"),
        "asset manifest",
    )
    require_repo_file(
        root, profile.get("input_state"), profile.get("input_state_sha256"), "input state"
    )
    bank = read_object(bank_path, "map-sprites bank")
    entries = bank.get("entries")
    if (
        bank.get("table_offset") != TABLE_OFFSET
        or bank.get("entry_size") != ENTRY_SIZE
        or bank.get("entry_count") != 43
        or not isinstance(entries, list)
        or len(entries) != 43
        or entries[ENTRY_ID].get("definition_ptr") != BEFORE_POINTER
        or entries[DONOR_ENTRY_ID].get("definition_ptr") != AFTER_POINTER
    ):
        raise ValueError("map-sprites bank contract mismatch")
    assets = read_object(assets_path, "sprite-definition asset manifest")
    rows = assets.get("entries")
    if (
        not isinstance(rows, list)
        or len(rows) != 43
        or rows[ENTRY_ID].get("definition_pointer") != f"0x{BEFORE_POINTER:08X}"
        or rows[DONOR_ENTRY_ID].get("definition_pointer") != f"0x{AFTER_POINTER:08X}"
        or rows[ENTRY_ID].get("animation_pointer") != "0x0812F5E4"
        or rows[ENTRY_ID].get("component_count") != 1
        or rows[DONOR_ENTRY_ID].get("component_count") != 2
    ):
        raise ValueError("sprite-definition donor contract mismatch")
    return profile


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_pair(root: Path, profile_path: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("map-sprites output must be absent or empty")
    profile = validate_profile(root, profile_path)
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or sha256_bytes(base) != BASE_ROM_SHA256:
        raise ValueError("map-sprites base ROM mismatch")
    patch_offset = TABLE_OFFSET + ENTRY_ID * ENTRY_SIZE
    before = struct.pack("<I", BEFORE_POINTER)
    after = struct.pack("<I", AFTER_POINTER)
    if base[patch_offset : patch_offset + 4] != before:
        raise ValueError("map-sprites base definition bytes mismatch")
    candidate_buffer = bytearray(base)
    candidate_buffer[patch_offset : patch_offset + 4] = after
    candidate = bytes(candidate_buffer)
    changed_offsets = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    if changed_offsets != [patch_offset, patch_offset + 1]:
        raise ValueError("map-sprites authored byte isolation mismatch")

    output.mkdir(parents=True, exist_ok=True)
    variants: dict[str, dict[str, object]] = {}
    for name, rom in (("baseline", base), ("candidate", candidate)):
        variant_dir = output / name
        variant_dir.mkdir()
        rom_path = variant_dir / f"{name}.gba"
        rom_path.write_bytes(rom)
        variants[name] = {
            "rom_path": rom_path.relative_to(output).as_posix(),
            "rom_sha256": sha256_bytes(rom),
            "rom_size": len(rom),
        }
    manifest: dict[str, Any] = {
        "schema": BUILD_SCHEMA,
        "profile": profile_path.relative_to(root).as_posix(),
        "profile_sha256": sha256_file(profile_path),
        "source_rom": "rom/base.gba",
        "source_rom_sha256": BASE_ROM_SHA256,
        "source_bank": profile["source_bank"],
        "source_bank_sha256": profile["source_bank_sha256"],
        "source_asset_manifest": profile["source_asset_manifest"],
        "source_asset_manifest_sha256": profile["source_asset_manifest_sha256"],
        "entry_id": ENTRY_ID,
        "donor_entry_id": DONOR_ENTRY_ID,
        "natural_gameplay_route": False,
        "controlled_task_materialization": True,
        "task_slot": profile["task_slot"],
        "input_mode": profile["input_mode"],
        "inputs": profile["inputs"],
        "input_state": profile["input_state"],
        "input_state_sha256": profile["input_state_sha256"],
        "capture_post_boundary_frames": profile["capture_post_boundary_frames"],
        "edit": {
            "rom_offset": patch_offset,
            "rom_address": f"0x{0x08000000 + patch_offset:08X}",
            "field": profile["field"],
            "before_pointer": profile["before_pointer"],
            "after_pointer": profile["after_pointer"],
            "before_bytes": before.hex(),
            "after_bytes": after.hex(),
            "changed_rom_offsets": changed_offsets,
        },
        "variants": variants,
        "boundary": profile["boundary"],
    }
    write_json(output / "build-manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_pair(ROOT, args.profile, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
