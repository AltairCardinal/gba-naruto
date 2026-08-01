#!/usr/bin/env python3
"""Independently verify the battle-effect fixed-slot write-back audit."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_ID = "battle-effect-resource-writeback-v1"
PAYLOAD_NAME = "battle-effect-resource-writeback.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path(
    "artifacts/battle-effect-resource-pairs-v1/manifest.json"
)
CATALOG_SHA256 = "716ac580326077127797c634d1f19bbc0aadcfd4db9c577730728b112f002963"
TABLE_OFFSET = 0x59911C
TABLE_ENTRY_COUNT = 19
TABLE_ENTRY_SIZE = 8
ROLE_POINTER_OFFSETS = {"graphics": 0, "palette": 4}
IMPLEMENTATION_PATHS = (
    "tools/gba_image_export.py",
    "tools/import_battle_effect_resources.py",
    "tools/export_battle_effect_resource_writeback_audit.py",
    "tools/verify_battle_effect_resource_writeback_audit.py",
    "tools/build_mod.py",
    "tests/test_import_battle_effect_resources.py",
    "tests/test_vram_safe_fixed_slot_audits.py",
)


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
                    if distance == 1:
                        continue
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
    if catalog.get("schema") != "battle-effect-resource-pairs-v1":
        raise ValueError("battle-effect resource catalog schema mismatch")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 18:
        raise ValueError("battle-effect resource catalog denominator mismatch")
    table = catalog.get("resource_pair_table")
    if (
        not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
        or table.get("valid_group_ids") != list(range(1, TABLE_ENTRY_COUNT))
    ):
        raise ValueError("battle-effect resource table provenance mismatch")
    table_bytes = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    if _sha256_bytes(table_bytes) != table.get("sha256"):
        raise ValueError("battle-effect resource table hash mismatch")
    if table_bytes[:TABLE_ENTRY_SIZE] != bytes(TABLE_ENTRY_SIZE):
        raise ValueError("battle-effect resource sentinel mismatch")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    reference_count = 0
    for expected_group_id, entry in enumerate(entries, 1):
        group_id = int(entry["group_id"])
        entry_offset = int(entry["table_entry_file_offset"])
        if (
            group_id != expected_group_id
            or entry_offset != TABLE_OFFSET + group_id * TABLE_ENTRY_SIZE
        ):
            raise ValueError("battle-effect group identity mismatch")
        pair = table_bytes[
            group_id * TABLE_ENTRY_SIZE :
            (group_id + 1) * TABLE_ENTRY_SIZE
        ]
        if entry.get("pair_raw_hex") != pair.hex():
            raise ValueError(f"battle-effect group {group_id} pair mismatch")
        for role, pointer_delta in ROLE_POINTER_OFFSETS.items():
            reference_count += 1
            source = entry[role]
            offset = int(source["file_offset"])
            pointer = int.from_bytes(
                rom[
                    entry_offset + pointer_delta :
                    entry_offset + pointer_delta + 4
                ],
                "little",
            )
            if pointer != 0x08000000 + offset:
                raise ValueError(
                    f"battle-effect group {group_id} {role} pointer mismatch"
                )
            record = _read_record(rom, offset)
            content = _decompress(rom, offset)
            digest = _sha256_bytes(content)
            if (
                len(record) != int(source["compressed_size"])
                or _sha256_bytes(record) != source["compressed_sha256"]
                or len(content) != int(source["decompressed_size"])
                or digest != source["decompressed_sha256"]
            ):
                raise ValueError(
                    f"battle-effect group {group_id} {role} "
                    "ROM provenance mismatch"
                )
            if role == "graphics" and (
                not content or len(content) % 32
            ):
                raise ValueError("battle-effect graphics format mismatch")
            if role == "palette" and len(content) != 32:
                raise ValueError("battle-effect palette format mismatch")
            key = (role, digest)
            row = grouped.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": digest,
                    "decompressed_size": len(content),
                    "source_files": set(),
                    "physical_offsets": set(),
                    "logical_aliases": [],
                },
            )
            row["source_files"].add(source["output_bin"])
            row["physical_offsets"].add(offset)
            row["logical_aliases"].append(
                {
                    "group_id": group_id,
                    "resource_type": role,
                    "table_pointer_offset": entry_offset + pointer_delta,
                    "physical_offset": offset,
                    "source_file": source["output_bin"],
                }
            )
    for row in grouped.values():
        row["source_files"] = sorted(row["source_files"])
        row["physical_offsets"] = sorted(row["physical_offsets"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (
                item["group_id"],
                item["table_pointer_offset"],
            ),
        )
    if (
        len(grouped) != 34
        or sum(len(row["physical_offsets"]) for row in grouped.values()) != 35
        or reference_count != 36
    ):
        raise ValueError("battle-effect resource denominator mismatch")
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
    mutation_offset = 2 if role == "palette" else 0
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
        "source_files": row["source_files"],
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
        raise ValueError("battle-effect resource catalog SHA-256 mismatch")
    grouped = _group_resources(rom, _json(catalog_path))
    resources = [
        _resource_record(rom, grouped[key])
        for key in sorted(grouped)
    ]
    physical_slots = sum(
        row["physical_slot_count"] for row in resources
    )
    logical_references = sum(
        row["logical_alias_count"] for row in resources
    )
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
    mutation_logical_fit = sum(
        row["logical_alias_count"]
        for row in resources
        if row["mutation_fit_all_aliases"]
    )
    if (
        len(resources),
        physical_slots,
        logical_references,
        original_content_fit,
        original_slot_fit,
        mutation_content_fit,
        mutation_slot_fit,
        mutation_logical_fit,
    ) != (34, 35, 36, 34, 35, 23, 24, 24):
        raise ValueError("battle-effect write-back denominator mismatch")
    scope = {
        "all_content_resources_audited": True,
        "all_physical_slots_audited": True,
        "all_logical_references_accounted": True,
        "original_roundtrip_capacity_complete": True,
        "guarded_in_place_importer_available": True,
        "atomic_all_alias_capacity_gate": True,
        "explicit_physical_slot_targeting_available": True,
        "deterministic_first_unit_mutation_audited": True,
        "vram_safe_encoding_audited": True,
        "arbitrary_edit_capacity_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_pixel_equivalence": False,
        "generic_image_writeback_complete": False,
    }
    return {
        "schema": "battle-effect-resource-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {
            "path": "rom/base.gba",
            "sha256": ROM_SHA256,
            "size": len(rom),
        },
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
            "content_resource_count": 34,
            "physical_slot_count": 35,
            "logical_reference_count": 36,
        },
        "implementation": {
            relative: _sha256(root / relative)
            for relative in IMPLEMENTATION_PATHS
        },
        "mutation_model": {
            "kind": "first_editable_unit_low_bit_toggle",
            "graphics_byte_offset": 0,
            "palette_byte_offset": 2,
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
            "mutation_fit_logical_reference_count": mutation_logical_fit,
            "mutation_overflow_logical_reference_count": (
                logical_references - mutation_logical_fit
            ),
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


def verify_battle_effect_resource_writeback_audit(
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
        "schema": "battle-effect-resource-writeback-verification-v1",
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
    report = verify_battle_effect_resource_writeback_audit(
        args.root,
        artifact,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
