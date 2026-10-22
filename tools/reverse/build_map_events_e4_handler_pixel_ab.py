#!/usr/bin/env python3
"""Build the isolated natural E4 primary-handler ROM pair."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PROFILE_SCHEMA = "map-events-e4-handler-pixel-ab-profile-v1"
BUILD_SCHEMA = "map-events-e4-handler-pixel-ab-build-v1"
TABLE_OFFSET = 0x53E698
ENTRY_SIZE = 8
ENTRY_ID = 0xE4
FIELD_OFFSET = 0
BEFORE_POINTER = 0x0807F209
AFTER_POINTER = 0x0809C149
NOOP_CODE_OFFSET = 0x09C148


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


def require_repo_path(
    root: Path, value: object, digest: object, label: str, *, directory: bool = False
) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"map-events {label} path mismatch")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"map-events {label} must be repository-relative")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or (path.is_dir() if directory else path.is_file()) is False:
        raise ValueError(f"map-events {label} must stay inside repository")
    hashed = path / "manifest.json" if directory else path
    if not isinstance(digest, str) or sha256_file(hashed) != digest:
        raise ValueError(f"map-events {label} hash mismatch")
    return path


def validate_profile(root: Path, profile_path: Path) -> dict[str, Any]:
    profile = read_object(profile_path, "map-events E4 pixel A/B profile")
    expected = {
        "schema": PROFILE_SCHEMA,
        "table_offset": TABLE_OFFSET,
        "entry_size": ENTRY_SIZE,
        "entry_id": ENTRY_ID,
        "field": "primary_handler_ptr",
        "field_offset": FIELD_OFFSET,
        "before_pointer": f"0x{BEFORE_POINTER:08X}",
        "after_pointer": f"0x{AFTER_POINTER:08X}",
        "after_target_instruction": "bx lr",
        "encoded_action": "0xC3",
        "natural_expiry_action": "0xE4",
        "input_mode": "zero-input-natural-expiry",
        "inputs": [],
        "capture_post_dispatch_frames": 3,
    }
    for key, value in expected.items():
        if profile.get(key) != value:
            raise ValueError(f"map-events profile {key} mismatch")
    bank_path = require_repo_path(
        root, profile.get("source_bank"), profile.get("source_bank_sha256"), "bank"
    )
    chain_path = require_repo_path(
        root,
        profile.get("source_chain_manifest"),
        profile.get("source_chain_manifest_sha256"),
        "chain manifest",
    )
    phase_path = require_repo_path(
        root,
        profile.get("source_phase_artifact"),
        profile.get("source_phase_manifest_sha256"),
        "phase artifact",
        directory=True,
    )
    require_repo_path(
        root, profile.get("input_state"), profile.get("input_state_sha256"), "input state"
    )
    require_repo_path(
        root,
        profile.get("input_evidence"),
        profile.get("input_evidence_sha256"),
        "input evidence",
    )
    bank = read_object(bank_path, "map-events bank")
    entries = bank.get("entries")
    if (
        bank.get("table_offset") != TABLE_OFFSET
        or bank.get("entry_size") != ENTRY_SIZE
        or bank.get("entry_count") != 256
        or not isinstance(entries, list)
        or len(entries) != 256
        or entries[ENTRY_ID].get("primary_handler_ptr") != BEFORE_POINTER
        or entries[ENTRY_ID].get("secondary_handler_ptr") != 0
    ):
        raise ValueError("map-events bank contract mismatch")
    chain = read_object(chain_path, "battlefield-object effect chain")
    mappings = chain.get("mappings")
    if (
        chain.get("identity") != "ninja_tool_battlefield_object_delayed_effect_chain"
        or not isinstance(mappings, list)
        or not any(
            row.get("encoded_action") == "0xC3"
            and row.get("expiry_action") == "0xE4"
            and row.get("primary_handler") == f"0x{BEFORE_POINTER:08X}"
            and row.get("secondary_handler") is None
            for row in mappings
            if isinstance(row, dict)
        )
    ):
        raise ValueError("map-events natural chain contract mismatch")
    phase = read_object(phase_path / "manifest.json", "natural group-3 phase manifest")
    if (
        phase.get("artifact_status") != "accepted"
        or phase.get("group_id") != 3
        or phase.get("input_mode") != "zero-input-active-state"
        or phase.get("inputs") != []
        or phase.get("input_state")
        != {"path": profile["input_state"], "sha256": profile["input_state_sha256"]}
    ):
        raise ValueError("map-events natural phase contract mismatch")
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
        raise ValueError("map-events output must be absent or empty")
    profile = validate_profile(root, profile_path)
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or sha256_bytes(base) != BASE_ROM_SHA256:
        raise ValueError("map-events base ROM mismatch")
    patch_offset = TABLE_OFFSET + ENTRY_ID * ENTRY_SIZE + FIELD_OFFSET
    before = struct.pack("<I", BEFORE_POINTER)
    after = struct.pack("<I", AFTER_POINTER)
    if base[patch_offset : patch_offset + 4] != before:
        raise ValueError("map-events E4 primary bytes mismatch")
    if base[NOOP_CODE_OFFSET : NOOP_CODE_OFFSET + 2] != bytes.fromhex("7047"):
        raise ValueError("map-events candidate no-op target mismatch")
    candidate_buffer = bytearray(base)
    candidate_buffer[patch_offset : patch_offset + 4] = after
    candidate = bytes(candidate_buffer)
    changed_offsets = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    if changed_offsets != [patch_offset, patch_offset + 1, patch_offset + 2]:
        raise ValueError("map-events authored byte isolation mismatch")

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
        "source_chain_manifest": profile["source_chain_manifest"],
        "source_chain_manifest_sha256": profile["source_chain_manifest_sha256"],
        "source_phase_artifact": profile["source_phase_artifact"],
        "source_phase_manifest_sha256": profile["source_phase_manifest_sha256"],
        "entry_id": ENTRY_ID,
        "field": profile["field"],
        "natural_gameplay_route": True,
        "input_mode": profile["input_mode"],
        "inputs": profile["inputs"],
        "input_state": profile["input_state"],
        "input_state_sha256": profile["input_state_sha256"],
        "input_evidence": profile["input_evidence"],
        "input_evidence_sha256": profile["input_evidence_sha256"],
        "capture_post_dispatch_frames": profile["capture_post_dispatch_frames"],
        "edit": {
            "rom_offset": patch_offset,
            "rom_address": f"0x{0x08000000 + patch_offset:08X}",
            "field": profile["field"],
            "before_pointer": profile["before_pointer"],
            "after_pointer": profile["after_pointer"],
            "after_target_instruction": profile["after_target_instruction"],
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
