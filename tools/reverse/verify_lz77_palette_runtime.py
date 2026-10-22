#!/usr/bin/env python3
"""Verify the two natural LZ77 load-boundary and negative OAM captures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
ENTRY_RULES = {
    "0x0812D2F0": {
        "route": "scenario-41-target-confirmation",
        "destination": 0x06016400,
        "decompressed_size": 1344,
        "tile_range": (800, 841),
        "target_pc": 0x08071BD0,
        "hit_frame": 114,
        "candidate_bank": 15,
        "candidate_source": 0x08457EA8,
    },
    "0x083496F8": {
        "route": "profile-browser-init",
        "destination": 0x06017580,
        "decompressed_size": 128,
        "tile_range": (940, 943),
        "target_pc": 0x0808B5EE,
        "hit_frame": 54,
        "candidate_bank": 14,
        "candidate_source": 0x083496B0,
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _rom_matches(rom: bytes, target: bytes) -> list[int]:
    matches = []
    start = 0
    while True:
        offset = rom.find(target, start)
        if offset < 0:
            return matches
        matches.append(0x08000000 + offset)
        start = offset + 1


def _active_target_objects(
    data: bytes, tile_first: int, tile_last: int
) -> list[dict[str, int]]:
    objects = []
    if len(data) != 0x400:
        raise ValueError("OAM dump is not 0x400 bytes")
    for index in range(128):
        attr0, attr1, attr2, _ = struct.unpack_from("<4H", data, index * 8)
        hidden = ((attr0 >> 8) & 3) == 2
        tile = attr2 & 0x3FF
        if not hidden and tile_first <= tile <= tile_last:
            objects.append(
                {
                    "index": index,
                    "attr0": attr0,
                    "attr1": attr1,
                    "attr2": attr2,
                    "tile": tile,
                    "palette_bank": (attr2 >> 12) & 15,
                }
            )
    return objects


def verify(root: Path, artifact_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact_dir = artifact_dir.resolve()
    errors: list[str] = []
    manifest: dict[str, Any] = {}
    evidence: dict[str, Any] = {}

    try:
        manifest = _json(artifact_dir / "manifest.json")
        evidence = _json(artifact_dir / "evidence.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "schema": "lz77-palette-runtime-verification-v1",
            "verified": False,
            "entry_count": 0,
            "palette_bindings_promoted": 0,
            "errors": [str(error)],
        }

    if manifest.get("schema") != "git-artifact-promotion-v1":
        errors.append("manifest schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        errors.append("manifest artifact status is not accepted")
    expected_files = manifest.get("files")
    if not isinstance(expected_files, dict):
        errors.append("manifest file hash inventory is missing")
        expected_files = {}
    actual_files = {
        path.relative_to(artifact_dir).as_posix(): path
        for path in artifact_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if set(actual_files) != set(expected_files):
        errors.append("manifest file inventory mismatch")
    for relative, expected_hash in expected_files.items():
        path = actual_files.get(relative)
        if path is None:
            continue
        if _sha256(path) != expected_hash:
            errors.append(f"hash mismatch: {relative}")
    if manifest.get("payload_sha256") != _sha256(artifact_dir / "evidence.json"):
        errors.append("payload hash mismatch")

    try:
        rom_path = root / evidence["rom"]["path"]
        rom = rom_path.read_bytes()
        actual_rom_sha256 = _sha256(rom_path)
        if actual_rom_sha256 != EXPECTED_ROM_SHA256:
            errors.append("ROM hash mismatch")
        if evidence["rom"].get("sha256") != actual_rom_sha256:
            errors.append("evidence ROM hash mismatch")
        evidence_binary_sha256 = evidence["emulator"]["binary_sha256"]
        probe = evidence["probe"]
        if probe.get("post_hit_watch_frames") != 240:
            errors.append("evidence probe watch duration mismatch")
        for name in ("path", "test"):
            path = root / probe[name]
            hash_field = f"{name}_sha256" if name == "test" else "sha256"
            if _sha256(path) != probe[hash_field]:
                errors.append(f"probe {name} hash mismatch")
        inventory = _json(
            root
            / "artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json"
        )
        payload_bundle = (
            root / "artifacts/rom-pointer-lz77-inventory-v1/uncovered-payloads.bin"
        ).read_bytes()
        source_records = {
            record["gba_address"]: record for record in inventory["new_records"]
        }

        entries = evidence.get("entries")
        if not isinstance(entries, list) or len(entries) != 2:
            errors.append("evidence must contain exactly two entries")
            entries = []
        seen_addresses: set[str] = set()
        for entry in entries:
            address = entry.get("graphics_address")
            rule = ENTRY_RULES.get(address)
            if rule is None:
                errors.append(f"unexpected graphics entry: {address}")
                continue
            seen_addresses.add(address)
            if entry.get("route") != rule["route"]:
                errors.append(f"{address}: route mismatch")
            if entry.get("destination") != _address(rule["destination"]):
                errors.append(f"{address}: destination mismatch")
            if entry.get("decompressed_size") != rule["decompressed_size"]:
                errors.append(f"{address}: decompressed size mismatch")
            if entry.get("target_pc") != _address(rule["target_pc"]):
                errors.append(f"{address}: target PC mismatch")
            if entry.get("hit_frame") != rule["hit_frame"]:
                errors.append(f"{address}: hit frame mismatch")
            if entry.get("target_tiles") != list(rule["tile_range"]):
                errors.append(f"{address}: target tiles mismatch")
            if entry.get("candidate_palette_bank") != rule["candidate_bank"]:
                errors.append(f"{address}: candidate palette bank mismatch")
            if entry.get("candidate_unique_rom_source") != _address(
                rule["candidate_source"]
            ):
                errors.append(f"{address}: candidate palette source mismatch")
            expected_negative_declarations = {
                "payload_exact_at_hit": True,
                "hardware_oam_reference_at_hit": False,
                "shadow_oam_reference_at_hit": False,
                "post_hit_oam_reference_observed": False,
            }
            for field, expected in expected_negative_declarations.items():
                if entry.get(field) is not expected:
                    errors.append(f"{address}: {field} declaration mismatch")
            input_path = artifact_dir / entry["input_state"]
            if _sha256(input_path) != entry["input_state_sha256"]:
                errors.append(f"{address}: input state hash mismatch")
            audit_path = artifact_dir / entry["audit"]
            audit = _json(audit_path)
            if _sha256(audit_path) != entry["audit_sha256"]:
                errors.append(f"{address}: audit hash mismatch")
            if audit.get("route") != entry.get("route"):
                errors.append(f"{address}: audit route mismatch")
            if audit.get("input_state_sha256") != entry.get("input_state_sha256"):
                errors.append(f"{address}: audit input state hash mismatch")
            if audit.get("rom_sha256") != evidence["rom"].get("sha256"):
                errors.append(f"{address}: audit ROM hash mismatch")
            if audit.get("binary_sha256") != evidence_binary_sha256:
                errors.append(f"{address}: audit emulator hash mismatch")
            if audit.get("target_pc") != entry.get("target_pc"):
                errors.append(f"{address}: audit target PC mismatch")
            if audit.get("hit_frame") != entry.get("hit_frame"):
                errors.append(f"{address}: audit hit frame mismatch")
            if audit.get("hit_pc") != _address(rule["target_pc"] + 2):
                errors.append(f"{address}: audit callback PC mismatch")
            if (
                audit.get("outcome") != "oam-not-observed"
                or audit.get("object") is not None
                or audit.get("post_hit_watch_frames") != 240
                or audit.get("target_tiles") != list(rule["tile_range"])
            ):
                errors.append(f"{address}: audit outcome mismatch")
            if audit.get("frame") != rule["hit_frame"] + 240:
                errors.append(f"{address}: audit final frame mismatch")
            run_dir = audit_path.parent
            guard_path = run_dir / "guard.json"
            guard = _json(guard_path)
            if _sha256(guard_path) != entry["guard_sha256"]:
                errors.append(f"{address}: guard hash mismatch")
            if (
                guard.get("reason") != "completed"
                or guard.get("exit_code") != 0
                or guard.get("degraded") is not False
                or guard.get("peak_tree_rss_mib", 513) > 512
            ):
                errors.append(f"{address}: guard result mismatch")

            source = source_records[address]
            start = source["decompressed_bundle_offset"]
            payload = payload_bundle[start : start + source["decompressed_size"]]
            vram = (run_dir / "vram.bin").read_bytes()
            destination_offset = rule["destination"] - 0x06000000
            actual_payload = vram[
                destination_offset : destination_offset + len(payload)
            ]
            if actual_payload != payload:
                errors.append(f"{address}: target VRAM payload mismatch")
            if hashlib.sha256(payload).hexdigest() != entry["decompressed_sha256"]:
                errors.append(f"{address}: decompressed payload hash mismatch")

            for name in ("oam.bin", "shadow-oam.bin"):
                if _active_target_objects(
                    (run_dir / name).read_bytes(), *rule["tile_range"]
                ):
                    errors.append(f"{address}: unexpected target object in {name}")
            pram = (run_dir / "pram.bin").read_bytes()
            bank = rule["candidate_bank"]
            palette = pram[0x200 + bank * 32 : 0x220 + bank * 32]
            if hashlib.sha256(palette).hexdigest() != entry["candidate_palette_sha256"]:
                errors.append(f"{address}: candidate palette hash mismatch")
            if _rom_matches(rom, palette) != [rule["candidate_source"]]:
                errors.append(f"{address}: candidate palette source is not unique")
            if entry.get("palette_binding_status") != "unresolved":
                errors.append(f"{address}: palette binding was promoted without OAM")
        if seen_addresses != set(ENTRY_RULES):
            errors.append("evidence graphics entry set mismatch")
        conclusion = evidence.get("conclusion")
        if not isinstance(conclusion, dict):
            errors.append("evidence conclusion is missing")
        elif (
            conclusion.get("load_boundaries_runtime_verified") != len(ENTRY_RULES)
            or conclusion.get("palette_bindings_promoted") != 0
        ):
            errors.append("evidence conclusion counts mismatch")
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))

    entries = evidence.get("entries")
    entry_count = len(entries) if isinstance(entries, list) else 0
    promoted = (
        sum(entry.get("palette_binding_status") != "unresolved" for entry in entries)
        if isinstance(entries, list)
        else 0
    )
    return {
        "schema": "lz77-palette-runtime-verification-v1",
        "verified": not errors,
        "entry_count": entry_count,
        "palette_bindings_promoted": promoted,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/lz77-palette-runtime-v1"),
    )
    args = parser.parse_args()
    artifact_dir = (
        args.artifact_dir
        if args.artifact_dir.is_absolute()
        else args.root / args.artifact_dir
    )
    report = verify(args.root, artifact_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
