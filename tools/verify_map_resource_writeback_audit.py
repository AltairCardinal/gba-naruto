#!/usr/bin/env python3
"""Independently verify the battle-map fixed-slot write-back audit."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_ID = "map-resource-writeback-v1"
PAYLOAD_NAME = "map-resource-writeback.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/map-canvases-v1/manifest.json")
CATALOG_SHA256 = "12a231a570a1cb9e56bec7e2f87cb6de4ac48d673765b1ba536bbc5b0137e19c"
IMPLEMENTATION_PATHS = (
    "tools/gba_image_export.py",
    "tools/import_map_resources.py",
    "tools/export_map_resource_writeback_audit.py",
    "tools/verify_map_resource_writeback_audit.py",
    "tools/build_mod.py",
    "tests/test_import_map_resources.py",
)
ROLE_POINTER_OFFSETS = {
    "tile_graphics": 4,
    "bg_palette": 8,
    "primary_layout": 12,
    "alternate_layout": 16,
    "metatile_definitions": 20,
    "collision_grid": 24,
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_record(data: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError(f"invalid GBA LZ77 header at 0x{offset:06X}")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    produced = 0
    while produced < size:
        if cursor >= len(data):
            raise ValueError("truncated GBA LZ77 flags")
        flags = data[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if produced >= size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(data):
                    raise ValueError("truncated GBA LZ77 reference")
                length = (data[cursor] >> 4) + 3
                distance = (
                    ((data[cursor] & 0x0F) << 8) | data[cursor + 1]
                ) + 1
                if distance > produced or produced + length > size:
                    raise ValueError("invalid GBA LZ77 reference")
                cursor += 2
                produced += length
            else:
                if cursor >= len(data):
                    raise ValueError("truncated GBA LZ77 literal")
                cursor += 1
                produced += 1
    return data[offset:cursor]


def _decompress(data: bytes, offset: int) -> bytes:
    record = _read_record(data, offset)
    size = int.from_bytes(record[1:4], "little")
    cursor = 4
    output = bytearray()
    while len(output) < size:
        flags = record[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= size:
                break
            if flags & (1 << bit):
                token = int.from_bytes(record[cursor : cursor + 2], "big")
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                for _ in range(length):
                    output.append(output[-distance])
            else:
                output.append(record[cursor])
                cursor += 1
    return bytes(output)


def _encode(data: bytes) -> bytes:
    if not data or len(data) >= 1 << 24:
        raise ValueError("invalid GBA LZ77 input length")
    output = bytearray(
        (0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, len(data) >> 16)
    )
    positions: dict[bytes, deque[int]] = {}
    cursor = 0
    while cursor < len(data):
        flag_offset = len(output)
        output.append(0)
        flags = 0
        for token_index in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                for previous in reversed(
                    positions.get(data[cursor : cursor + 3], ())
                ):
                    distance = cursor - previous
                    if distance > 0x1000:
                        break
                    length = 3
                    while (
                        length < 18
                        and cursor + length < len(data)
                        and data[previous + length] == data[cursor + length]
                    ):
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                    if length == 18:
                        break
            if best_length >= 3:
                flags |= 1 << (7 - token_index)
                token = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((token >> 8, token & 0xFF))
                advance = best_length
            else:
                output.append(data[cursor])
                advance = 1
            for position in range(cursor, cursor + advance):
                if position + 3 > len(data):
                    continue
                key = data[position : position + 3]
                bucket = positions.setdefault(key, deque())
                bucket.append(position)
                while bucket and position - bucket[0] > 0x1000:
                    bucket.popleft()
            cursor += advance
        output[flag_offset] = flags
    return bytes(output)


def _group_resources(
    rom: bytes,
    catalog: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    if catalog.get("schema") != "map-canvases-v1":
        raise ValueError("map canvas catalog schema mismatch")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 47:
        raise ValueError("map canvas catalog denominator mismatch")
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    reference_count = 0
    for entry in entries:
        map_id = int(entry["map_id"])
        header_offset = int(entry["header"]["file_offset"])
        for role, pointer_delta in ROLE_POINTER_OFFSETS.items():
            source = entry["resources"].get(role)
            if source is None:
                continue
            reference_count += 1
            offset = int(source["file_offset"])
            content = _decompress(rom, offset)
            digest = _sha256_bytes(content)
            if (
                digest != source["sha256"]
                or len(content) != int(source["decompressed_size"])
            ):
                raise ValueError(f"map {map_id} {role} ROM provenance mismatch")
            raw_pointer = int.from_bytes(
                rom[
                    header_offset + pointer_delta :
                    header_offset + pointer_delta + 4
                ],
                "little",
            )
            if raw_pointer != 0x08000000 + offset:
                raise ValueError(f"map {map_id} {role} header pointer mismatch")
            key = (role, digest)
            row = grouped.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": digest,
                    "decompressed_size": len(content),
                    "source_file": source["output_bin"],
                    "physical_offsets": set(),
                    "logical_aliases": [],
                },
            )
            row["physical_offsets"].add(offset)
            row["logical_aliases"].append(
                {
                    "map_id": map_id,
                    "resource_type": role,
                    "header_pointer_offset": header_offset + pointer_delta,
                    "physical_offset": offset,
                }
            )
    for row in grouped.values():
        row["physical_offsets"] = sorted(row["physical_offsets"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (
                item["map_id"],
                item["header_pointer_offset"],
            ),
        )
    if (
        len(grouped) != 166
        or sum(len(row["physical_offsets"]) for row in grouped.values()) != 217
        or reference_count != 249
    ):
        raise ValueError("map resource denominator mismatch")
    return grouped


def _resource_record(
    rom: bytes,
    row: dict[str, Any],
) -> dict[str, Any]:
    role = row["resource_type"]
    digest = row["resource_sha256"]
    content = _decompress(rom, row["physical_offsets"][0])
    original_encoded = _encode(content)
    mutated = bytearray(content)
    mutation_offset = 2 if role == "bg_palette" and len(mutated) > 2 else 0
    before = mutated[mutation_offset]
    mutated[mutation_offset] ^= 1
    mutated_bytes = bytes(mutated)
    mutation_encoded = _encode(mutated_bytes)
    slots = []
    for offset in row["physical_offsets"]:
        source = _read_record(rom, offset)
        if _decompress(rom, offset) != content:
            raise ValueError(f"{role}/{digest} physical alias mismatch")
        slots.append(
            {
                "file_offset": offset,
                "gba_address": f"0x{0x08000000 + offset:08X}",
                "slot_size": len(source),
                "source_compressed_sha256": _sha256_bytes(source),
                "original_reencoded_size": len(original_encoded),
                "original_slot_margin": len(source) - len(original_encoded),
                "original_roundtrip_fit": len(original_encoded) <= len(source),
                "mutation_encoded_size": len(mutation_encoded),
                "mutation_slot_margin": len(source) - len(mutation_encoded),
                "mutation_fit": len(mutation_encoded) <= len(source),
            }
        )
    return {
        "resource_type": role,
        "resource_sha256": digest,
        "decompressed_size": len(content),
        "source_file": row["source_file"],
        "logical_alias_count": len(row["logical_aliases"]),
        "logical_aliases": row["logical_aliases"],
        "physical_slot_count": len(slots),
        "physical_slots": slots,
        "original_reencoded_sha256": _sha256_bytes(original_encoded),
        "original_fit_all_aliases": all(
            slot["original_roundtrip_fit"] for slot in slots
        ),
        "mutation": {
            "kind": "first_editable_unit_low_bit_toggle",
            "resource_type": role,
            "offset": mutation_offset,
            "before": before,
            "after": mutated[mutation_offset],
        },
        "mutation_decompressed_sha256": _sha256_bytes(mutated_bytes),
        "mutation_encoded_sha256": _sha256_bytes(mutation_encoded),
        "mutation_fit_all_aliases": all(
            slot["mutation_fit"] for slot in slots
        ),
    }


def _expected_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256_bytes(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    if _sha256(catalog_path) != CATALOG_SHA256:
        raise ValueError("map canvas catalog SHA-256 mismatch")
    grouped = _group_resources(rom, _json(catalog_path))
    resources = [
        _resource_record(rom, grouped[key])
        for key in sorted(grouped)
    ]
    physical_slots = sum(row["physical_slot_count"] for row in resources)
    logical_references = sum(row["logical_alias_count"] for row in resources)
    original_content_fit = sum(
        row["original_fit_all_aliases"] for row in resources
    )
    original_slot_fit = sum(
        slot["original_roundtrip_fit"]
        for row in resources
        for slot in row["physical_slots"]
    )
    mutation_content_fit = sum(
        row["mutation_fit_all_aliases"] for row in resources
    )
    mutation_slot_fit = sum(
        slot["mutation_fit"]
        for row in resources
        for slot in row["physical_slots"]
    )
    scope = {
        "all_content_resources_audited": True,
        "all_physical_slots_audited": True,
        "all_logical_references_accounted": True,
        "original_roundtrip_capacity_complete": True,
        "guarded_in_place_importer_available": True,
        "atomic_all_alias_capacity_gate": True,
        "linked_resource_index_validation_complete": True,
        "deterministic_first_byte_mutation_audited": True,
        "arbitrary_edit_capacity_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_pixel_equivalence": False,
        "generic_image_writeback_complete": False,
    }
    return {
        "schema": "map-resource-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
            "size": len(rom),
        },
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
            "content_resource_count": 166,
            "physical_slot_count": 217,
            "logical_reference_count": 249,
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "mutation_model": {
            "kind": "first_editable_unit_low_bit_toggle",
            "palette_byte_offset": 2,
            "other_resource_byte_offset": 0,
            "purpose": (
                "bounded capacity witness only; overflow remains fail-closed"
            ),
        },
        "resources": resources,
        "summary": {
            "content_resource_count": len(resources),
            "physical_slot_count": physical_slots,
            "logical_reference_count": logical_references,
            "original_roundtrip_fit_content_count": original_content_fit,
            "original_roundtrip_fit_slot_count": original_slot_fit,
            "mutation_fit_all_alias_content_count": mutation_content_fit,
            "mutation_overflow_content_count": (
                len(resources) - mutation_content_fit
            ),
            "mutation_fit_slot_count": mutation_slot_fit,
            "mutation_overflow_slot_count": physical_slots - mutation_slot_fit,
            "minimum_original_slot_margin": min(
                slot["original_slot_margin"]
                for row in resources
                for slot in row["physical_slots"]
            ),
            "minimum_mutation_slot_margin": min(
                slot["mutation_slot_margin"]
                for row in resources
                for slot in row["physical_slots"]
            ),
        },
        "scope": scope,
    }


def verify_map_resource_writeback_audit(
    root: Path,
    artifact: Path,
) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    content_count = physical_count = logical_count = 0
    try:
        manifest = _json(artifact / "manifest.json")
        payload_path = artifact / PAYLOAD_NAME
        payload = _json(payload_path)
        if manifest.get("schema") != "git-artifact-promotion-v1":
            errors.append("promotion manifest schema mismatch")
        if manifest.get("artifact_id") != ARTIFACT_ID:
            errors.append("artifact ID mismatch")
        if manifest.get("artifact_status") != "accepted":
            errors.append("artifact is not accepted")
        actual_files = {
            path.relative_to(artifact).as_posix(): path
            for path in artifact.rglob("*")
            if path.is_file() and path.name != "manifest.json"
        }
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != set(actual_files):
            errors.append("artifact file inventory mismatch")
            files = {}
        for relative, expected_hash in files.items():
            if (
                relative in actual_files
                and _sha256(actual_files[relative]) != expected_hash
            ):
                errors.append(f"artifact hash mismatch: {relative}")
        payload_hash = _sha256(payload_path)
        if manifest.get("payload_sha256") != payload_hash:
            errors.append("payload hash mismatch")

        expected = _expected_payload(root)
        content_count = expected["summary"]["content_resource_count"]
        physical_count = expected["summary"]["physical_slot_count"]
        logical_count = expected["summary"]["logical_reference_count"]
        if payload.get("resources") != expected["resources"]:
            errors.append("resource records mismatch")
        for key in (
            "schema",
            "artifact_id",
            "rom",
            "source_catalog",
            "implementation",
            "mutation_model",
            "summary",
            "scope",
        ):
            if payload.get(key) != expected[key]:
                errors.append(f"{key.replace('_', ' ')} mismatch")
        if manifest.get("scope") != expected["scope"]:
            errors.append("promotion scope mismatch")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": "map-resource-writeback-verification-v1",
        "verified": not errors,
        "content_resource_count": content_count,
        "physical_slot_count": physical_count,
        "logical_reference_count": logical_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    artifact = (
        args.artifact if args.artifact.is_absolute()
        else args.root / args.artifact
    )
    report = verify_map_resource_writeback_audit(args.root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
