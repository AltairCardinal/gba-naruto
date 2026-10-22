#!/usr/bin/env python3
"""Build probe-free ROMs for a motion/effect parameter player-visible A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
PROFILE_SCHEMA = "motion-effect-parameter-pixel-ab-profile-v1"
BUILD_SCHEMA = "motion-effect-parameter-pixel-ab-build-v1"
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
EXPECTED_TABLE_OFFSET = 0x53EE98
EXPECTED_RECORD_SIZE = 10
EXPECTED_FIELD_OFFSET = 4
EXPECTED_CONSUMER_ENTRY = "0x08080764"
EXPECTED_CHILD_SPAWN = "0x08080218"
SOURCE_BANK_EXTRACTION_SHA256 = "683db11e4186ec145314ad4ae238c34f5b5d80fe66a5520a1cf4d77b5b6b5bf0"


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
        raise ValueError(f"motion parameter {label} path mismatch")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"motion parameter {label} must be repository-relative")
    path = (root / relative).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError(f"motion parameter {label} must stay inside repository")
    if not isinstance(expected_sha, str) or sha256_file(path) != expected_sha:
        raise ValueError(f"motion parameter {label} hash mismatch")
    return path


def validate_profile(root: Path, profile_path: Path) -> dict[str, Any]:
    profile = read_object(profile_path, "motion-effect parameter profile")
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("motion parameter profile schema mismatch")
    if profile.get("record_id") != 0:
        raise ValueError("motion parameter runtime closure must target record 0")
    if (
        profile.get("group_id") != 3
        or profile.get("sequence_id") != 3
        or profile.get("natural_gameplay_route") is not True
        or profile.get("input_mode") != "zero-input-active-state"
        or profile.get("inputs") != []
    ):
        raise ValueError("motion parameter profile must use the natural group-3 route")
    if (
        profile.get("table_offset") != EXPECTED_TABLE_OFFSET
        or profile.get("record_size") != EXPECTED_RECORD_SIZE
        or profile.get("field") != "y_offset"
        or profile.get("field_offset") != EXPECTED_FIELD_OFFSET
        or profile.get("before_value") != 0
        or profile.get("after_value") != 32
        or profile.get("consumer_entry") != EXPECTED_CONSUMER_ENTRY
        or profile.get("child_spawn_function") != EXPECTED_CHILD_SPAWN
    ):
        raise ValueError("motion parameter record-0 field contract mismatch")
    timeout = profile.get("timeout_frames")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 600:
        raise ValueError("motion parameter timeout mismatch")

    if profile.get("source_bank_sha256") != SOURCE_BANK_EXTRACTION_SHA256:
        raise ValueError("motion parameter bank extraction hash mismatch")
    bank_value = profile.get("source_bank")
    if not isinstance(bank_value, str) or Path(bank_value).is_absolute() or ".." in Path(bank_value).parts:
        raise ValueError("motion parameter bank path mismatch")
    bank_path = (root / bank_value).resolve(strict=True)
    if root not in bank_path.parents or not bank_path.is_file():
        raise ValueError("motion parameter bank must stay inside repository")
    bank = read_object(bank_path, "motion-effect parameter bank")
    fields = bank.get("entry_format", {}).get("fields")
    entries = bank.get("entries")
    if (
        bank.get("table_offset") != EXPECTED_TABLE_OFFSET
        or bank.get("entry_count") != 15
        or bank.get("entry_size") != EXPECTED_RECORD_SIZE
        or not isinstance(fields, list)
        or not any(
            row == {"offset": 4, "size": 2, "name": "y_offset", "type": "s16"}
            for row in fields
        )
        or not isinstance(entries, list)
        or len(entries) != 15
        or entries[0].get("_index") != 0
        or entries[0].get("_raw_offset") != EXPECTED_TABLE_OFFSET
        or entries[0].get("y_offset") != 0
    ):
        raise ValueError("motion parameter bank contract mismatch")

    phase_profile_path = require_repo_file(
        root,
        profile.get("source_phase_profile"),
        profile.get("source_phase_profile_sha256"),
        "phase profile",
    )
    phase_profile = read_object(phase_profile_path, "source phase profile")
    for label in ("input_state", "input_evidence", "source_phase_manifest"):
        require_repo_file(
            root, profile.get(label), profile.get(f"{label}_sha256"), label
        )
    if (
        phase_profile.get("group_id") != 3
        or phase_profile.get("sequence_id") != 3
        or phase_profile.get("input_mode") != "zero-input-active-state"
        or phase_profile.get("input_state") != profile.get("input_state")
        or phase_profile.get("input_state_sha256") != profile.get("input_state_sha256")
        or phase_profile.get("source_runtime_evidence") != profile.get("input_evidence")
        or phase_profile.get("source_runtime_evidence_sha256")
        != profile.get("input_evidence_sha256")
    ):
        raise ValueError("motion parameter source phase route mismatch")
    phase_artifact = profile.get("source_phase_artifact")
    if not isinstance(phase_artifact, str):
        raise ValueError("motion parameter phase artifact mismatch")
    artifact_path = (root / phase_artifact).resolve(strict=True)
    if root not in artifact_path.parents or not artifact_path.is_dir():
        raise ValueError("motion parameter phase artifact mismatch")
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
        raise ValueError("motion parameter output must be absent or empty")
    profile = validate_profile(root, profile_path)
    base_path = root / "rom/base.gba"
    base = base_path.read_bytes()
    if len(base) != 0x600000 or sha256_bytes(base) != BASE_ROM_SHA256:
        raise ValueError("motion parameter base ROM mismatch")

    patch_offset = (
        profile["table_offset"]
        + profile["record_id"] * profile["record_size"]
        + profile["field_offset"]
    )
    before = struct.pack("<h", profile["before_value"])
    after = struct.pack("<h", profile["after_value"])
    if base[patch_offset : patch_offset + 2] != before:
        raise ValueError("motion parameter base field bytes mismatch")
    candidate = bytearray(base)
    candidate[patch_offset : patch_offset + 2] = after
    candidate = bytes(candidate)
    changed_offsets = [
        index
        for index, pair in enumerate(zip(base, candidate, strict=True))
        if pair[0] != pair[1]
    ]
    if changed_offsets != [patch_offset]:
        raise ValueError("motion parameter authored byte isolation mismatch")

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
        "profile_id": profile["profile_id"],
        "profile_sha256": sha256_file(profile_path),
        "source_rom": "rom/base.gba",
        "source_rom_sha256": BASE_ROM_SHA256,
        "source_bank": profile["source_bank"],
        "source_bank_sha256": profile["source_bank_sha256"],
        "group_id": profile["group_id"],
        "sequence_id": profile["sequence_id"],
        "record_id": profile["record_id"],
        "field": profile["field"],
        "consumer_entry": profile["consumer_entry"],
        "child_spawn_function": profile["child_spawn_function"],
        "natural_gameplay_route": True,
        "input_mode": profile["input_mode"],
        "inputs": profile["inputs"],
        "input_state": profile["input_state"],
        "input_state_sha256": profile["input_state_sha256"],
        "input_evidence": profile["input_evidence"],
        "input_evidence_sha256": profile["input_evidence_sha256"],
        "source_phase_profile": profile["source_phase_profile"],
        "source_phase_profile_sha256": profile["source_phase_profile_sha256"],
        "source_phase_artifact": profile["source_phase_artifact"],
        "source_phase_manifest": profile["source_phase_manifest"],
        "source_phase_manifest_sha256": profile["source_phase_manifest_sha256"],
        "timeout_frames": profile["timeout_frames"],
        "edit": {
            "rom_offset": patch_offset,
            "rom_address": f"0x{0x08000000 + patch_offset:08X}",
            "record_id": profile["record_id"],
            "field": profile["field"],
            "before_value": profile["before_value"],
            "after_value": profile["after_value"],
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
