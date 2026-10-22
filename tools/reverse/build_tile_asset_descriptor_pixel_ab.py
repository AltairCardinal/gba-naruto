#!/usr/bin/env python3
"""Build a probe-free ROM pair for one tile-assets descriptor pointer A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PROFILE_SCHEMA = "tile-asset-descriptor-pixel-ab-profile-v1"
BUILD_SCHEMA = "tile-asset-descriptor-pixel-ab-build-v1"
TABLE_OFFSET = 0x5A320C
RECORD_SIZE = 0x44
DESCRIPTOR_ID = 2
CONSUMER_ID = 3
FIELD_OFFSET = 0x14
BEFORE_POINTER = 0x0834B228
AFTER_POINTER = 0x08349E74


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def require_repo_file(root: Path, value: object, expected_sha: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"tile descriptor {label} path mismatch")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"tile descriptor {label} must be repository-relative")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"tile descriptor {label} must stay inside repository")
    if not isinstance(expected_sha, str) or sha256_file(path) != expected_sha:
        raise ValueError(f"tile descriptor {label} hash mismatch")
    return path


def validate_profile(root: Path, profile_path: Path) -> dict[str, Any]:
    profile = read_object(profile_path, "tile descriptor pixel A/B profile")
    expected = {
        "schema": PROFILE_SCHEMA,
        "descriptor_id": DESCRIPTOR_ID,
        "consumer_id": CONSUMER_ID,
        "table_offset": TABLE_OFFSET,
        "record_size": RECORD_SIZE,
        "field": "layer_a_palette_pointer",
        "field_offset": FIELD_OFFSET,
        "before_pointer": f"0x{BEFORE_POINTER:08X}",
        "after_pointer": f"0x{AFTER_POINTER:08X}",
        "input_mode": "zero-input-active-state",
        "inputs": [],
        "initializer": "0x080983B8",
        "selector": "0x0808C18C",
        "capture_frame": 100,
    }
    for key, value in expected.items():
        if profile.get(key) != value:
            raise ValueError(f"tile descriptor profile {key} mismatch")
    bank_path = require_repo_file(
        root, profile.get("source_bank"), profile.get("source_bank_sha256"), "bank"
    )
    asset_path = require_repo_file(
        root,
        profile.get("source_asset_manifest"),
        profile.get("source_asset_manifest_sha256"),
        "asset manifest",
    )
    require_repo_file(
        root, profile.get("input_state"), profile.get("input_state_sha256"), "input state"
    )

    bank = read_object(bank_path, "tile-assets bank")
    entries = bank.get("entries")
    if (
        bank.get("table_offset") != TABLE_OFFSET
        or bank.get("entry_size") != RECORD_SIZE
        or bank.get("entry_count") != 79
        or not isinstance(entries, list)
        or len(entries) != 79
        or entries[DESCRIPTOR_ID].get("_raw_offset") != TABLE_OFFSET + DESCRIPTOR_ID * RECORD_SIZE
        or entries[DESCRIPTOR_ID].get("word_05") != BEFORE_POINTER
    ):
        raise ValueError("tile-assets descriptor contract mismatch")

    assets = read_object(asset_path, "tile-assets asset manifest")
    rows = assets.get("descriptors")
    if not isinstance(rows, list):
        raise ValueError("tile-assets asset descriptors missing")
    row = next((item for item in rows if item.get("descriptor_id") == DESCRIPTOR_ID), None)
    if not isinstance(row, dict) or row.get("consumer_id") != CONSUMER_ID:
        raise ValueError("tile-assets descriptor-2 asset row mismatch")
    layers = row.get("layers")
    if not isinstance(layers, list):
        raise ValueError("tile-assets descriptor-2 layers missing")
    layer_a = next((item for item in layers if item.get("name") == "A"), None)
    layer_b = next((item for item in layers if item.get("name") == "B"), None)
    if (
        not isinstance(layer_a, dict)
        or not isinstance(layer_b, dict)
        or layer_a.get("palette_pointer") != f"0x{BEFORE_POINTER:08X}"
        or layer_b.get("palette_pointer") != f"0x{AFTER_POINTER:08X}"
        or layer_a.get("palette", {}).get("size") != 32
        or layer_b.get("palette", {}).get("size") != 32
    ):
        raise ValueError("tile-assets palette redirect contract mismatch")
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
        raise ValueError("tile descriptor output must be absent or empty")
    profile = validate_profile(root, profile_path)
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or sha256_bytes(base) != BASE_ROM_SHA256:
        raise ValueError("tile descriptor base ROM mismatch")

    patch_offset = TABLE_OFFSET + DESCRIPTOR_ID * RECORD_SIZE + FIELD_OFFSET
    before = struct.pack("<I", BEFORE_POINTER)
    after = struct.pack("<I", AFTER_POINTER)
    if base[patch_offset : patch_offset + 4] != before:
        raise ValueError("tile descriptor base pointer bytes mismatch")
    candidate_buffer = bytearray(base)
    candidate_buffer[patch_offset : patch_offset + 4] = after
    candidate = bytes(candidate_buffer)
    changed_offsets = [
        index
        for index, (left, right) in enumerate(zip(base, candidate, strict=True))
        if left != right
    ]
    if changed_offsets != [patch_offset, patch_offset + 1]:
        raise ValueError("tile descriptor authored byte isolation mismatch")

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
        "descriptor_id": DESCRIPTOR_ID,
        "consumer_id": CONSUMER_ID,
        "natural_gameplay_route": True,
        "input_mode": profile["input_mode"],
        "inputs": profile["inputs"],
        "input_state": profile["input_state"],
        "input_state_sha256": profile["input_state_sha256"],
        "capture_frame": profile["capture_frame"],
        "edit": {
            "rom_offset": patch_offset,
            "rom_address": f"0x{0x08000000 + patch_offset:08X}",
            "descriptor_id": DESCRIPTOR_ID,
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
    manifest = build_pair(ROOT, args.profile, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
