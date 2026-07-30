#!/usr/bin/env python3
"""Independently verify the fullscreen BG fixed-slot write-back audit."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


ARTIFACT_ID = "bg-resource-writeback-v1"
PAYLOAD_NAME = "bg-resource-writeback.json"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/bg-resource-canvases-v1/manifest.json")
CATALOG_SHA256 = "27096c9129823cc7d4f98aeb1fde304419a1c6abfadaf1cff6e13b80bf2fa99e"
TABLE_OFFSET = 0x59903C
TABLE_ENTRY_COUNT = 14
TABLE_ENTRY_SIZE = 16
TABLE_SHA256 = "57e9b8b6b7c3003615c39539f80934f142efeb1e6674114fbaca98bc629f7da2"
VALID_ENTRY_IDS = tuple(range(1, 8)) + tuple(range(9, 14))
ROLE_POINTER_OFFSETS = {"graphics": 0, "palette": 4, "tilemap": 8}
MUTATION_OFFSETS = {"graphics": 0, "palette": 2, "tilemap": 0}
IMPLEMENTATION_PATHS = (
    "tools/gba_image_export.py",
    "tools/import_bg_resources.py",
    "tools/export_bg_resource_writeback_audit.py",
    "tools/verify_bg_resource_writeback_audit.py",
    "tools/build_mod.py",
    "tools/automated_test.py",
    "tests/test_import_bg_resources.py",
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
                distance = (((data[cursor] & 0x0F) << 8) | data[cursor + 1]) + 1
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


def _validate_entry(
    entry_id: int,
    mode: int,
    graphics: bytes,
    palette: bytes,
    tilemap: bytes,
) -> None:
    if len(palette) != 384 or len(tilemap) != 640:
        raise ValueError(f"BG entry {entry_id} payload size mismatch")
    tile_size = 64 if mode else 32
    if not graphics or len(graphics) % tile_size:
        raise ValueError(f"BG entry {entry_id} graphics format mismatch")
    if mode and max(graphics) >= 192:
        raise ValueError(f"BG entry {entry_id} 8bpp palette index mismatch")
    tile_count = len(graphics) // tile_size
    for value in struct.unpack("<320H", tilemap):
        if value & 0x03FF >= tile_count:
            raise ValueError(f"BG entry {entry_id} tile index mismatch")
        if not mode and ((value >> 12) & 0x0F) * 16 + 15 >= 192:
            raise ValueError(f"BG entry {entry_id} palette bank mismatch")


def _group_resources(
    rom: bytes,
    catalog: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    if catalog.get("schema") != "bg-resource-canvases-v1":
        raise ValueError("BG resource catalog schema mismatch")
    table = catalog.get("table")
    if (
        not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
        or table.get("empty_entry_ids") != [0, 8]
        or table.get("sha256") != TABLE_SHA256
    ):
        raise ValueError("BG resource table provenance mismatch")
    table_bytes = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    if _sha256_bytes(table_bytes) != TABLE_SHA256:
        raise ValueError("BG resource table hash mismatch")
    for entry_id in (0, 8):
        start = entry_id * TABLE_ENTRY_SIZE
        if table_bytes[start : start + TABLE_ENTRY_SIZE] != bytes(TABLE_ENTRY_SIZE):
            raise ValueError("BG resource sentinel mismatch")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or len(entries) != 12:
        raise ValueError("BG resource catalog denominator mismatch")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    entry_views: dict[int, dict[str, Any]] = {}
    physical_spans: dict[int, int] = {}
    reference_count = 0
    for expected_id, entry in zip(VALID_ENTRY_IDS, entries, strict=True):
        entry_id = int(entry["entry_id"])
        entry_offset = int(entry["descriptor_file_offset"])
        mode = int(entry["mode_flag"])
        if (
            entry_id != expected_id
            or entry_offset != TABLE_OFFSET + entry_id * TABLE_ENTRY_SIZE
            or mode not in (0, 1)
            or entry.get("pixel_mode") != ("8bpp" if mode else "4bpp")
        ):
            raise ValueError("BG resource entry identity mismatch")
        descriptor = table_bytes[
            entry_id * TABLE_ENTRY_SIZE : (entry_id + 1) * TABLE_ENTRY_SIZE
        ]
        if int.from_bytes(descriptor[12:16], "little") != mode:
            raise ValueError("BG resource mode mismatch")
        view: dict[str, Any] = {"mode": mode}
        for role, pointer_delta in ROLE_POINTER_OFFSETS.items():
            reference_count += 1
            source = entry[role]
            offset = int(source["file_offset"])
            pointer = int.from_bytes(
                descriptor[pointer_delta : pointer_delta + 4],
                "little",
            )
            if pointer != 0x08000000 + offset:
                raise ValueError(
                    f"BG resource entry {entry_id} {role} pointer mismatch"
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
                    f"BG resource entry {entry_id} {role} ROM provenance mismatch"
                )
            if (
                offset in physical_spans
                and physical_spans[offset] != offset + len(record)
            ):
                raise ValueError("conflicting BG physical slot provenance")
            physical_spans[offset] = offset + len(record)
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
            if row["decompressed_size"] != len(content):
                raise ValueError("conflicting BG content identity")
            row["source_files"].add(source["file"])
            row["physical_offsets"].add(offset)
            row["logical_aliases"].append(
                {
                    "entry_id": entry_id,
                    "mode_flag": mode,
                    "resource_type": role,
                    "table_pointer_offset": entry_offset + pointer_delta,
                    "physical_offset": offset,
                    "source_file": source["file"],
                }
            )
            view[role] = content
        _validate_entry(
            entry_id,
            mode,
            view["graphics"],
            view["palette"],
            view["tilemap"],
        )
        entry_views[entry_id] = view
    spans = sorted((start, end) for start, end in physical_spans.items())
    if any(
        start < previous_end
        for (_, previous_end), (start, _) in zip(spans, spans[1:])
    ):
        raise ValueError("BG physical slots overlap")
    for row in grouped.values():
        row["source_files"] = sorted(row["source_files"])
        row["physical_offsets"] = sorted(row["physical_offsets"])
        row["logical_aliases"] = sorted(
            row["logical_aliases"],
            key=lambda item: (item["entry_id"], item["table_pointer_offset"]),
        )
    if (
        len(grouped) != 31
        or sum(len(row["physical_offsets"]) for row in grouped.values()) != 36
        or reference_count != 36
    ):
        raise ValueError("BG resource denominator mismatch")
    return grouped


def _resource_record(rom: bytes, row: dict[str, Any]) -> dict[str, Any]:
    role = row["resource_type"]
    digest = row["resource_sha256"]
    content = _decompress(rom, row["physical_offsets"][0])
    original_encoded = _encode(content)
    mutated = bytearray(content)
    mutation_offset = MUTATION_OFFSETS[role]
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
        raise ValueError("BG resource catalog SHA-256 mismatch")
    grouped = _group_resources(rom, _json(catalog_path))
    resources = [_resource_record(rom, grouped[key]) for key in sorted(grouped)]
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
    ) != (31, 36, 36, 31, 36, 20, 21, 21):
        raise ValueError("BG write-back denominator mismatch")
    scope = {
        "all_content_resources_audited": True,
        "all_physical_slots_audited": True,
        "all_logical_references_accounted": True,
        "original_roundtrip_capacity_complete": True,
        "guarded_in_place_importer_available": True,
        "atomic_all_alias_capacity_gate": True,
        "explicit_physical_slot_targeting_available": True,
        "linked_resource_validation_complete": True,
        "deterministic_first_unit_mutation_audited": True,
        "arbitrary_edit_capacity_complete": False,
        "resource_relocation_complete": False,
        "pointer_rewrite_complete": False,
        "runtime_pixel_equivalence": False,
        "canvas_png_writeback_complete": False,
        "runtime_entry_selection_complete": False,
    }
    return {
        "schema": "bg-resource-writeback-audit-v1",
        "artifact_id": ARTIFACT_ID,
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256, "size": len(rom)},
        "source_catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
            "content_resource_count": 31,
            "physical_slot_count": 36,
            "logical_reference_count": 36,
        },
        "implementation": {
            relative: _sha256(root / relative) for relative in IMPLEMENTATION_PATHS
        },
        "mutation_model": {
            "kind": "first_editable_unit_low_bit_toggle",
            "graphics_byte_offset": 0,
            "palette_byte_offset": 2,
            "tilemap_byte_offset": 0,
            "purpose": "bounded capacity witness only; overflow remains fail-closed",
        },
        "resources": resources,
        "summary": {
            "content_resource_count": len(resources),
            "physical_slot_count": physical_slots,
            "logical_reference_count": logical_references,
            "original_roundtrip_fit_content_count": original_content_fit,
            "original_roundtrip_fit_slot_count": original_slot_fit,
            "mutation_fit_all_alias_content_count": mutation_content_fit,
            "mutation_overflow_content_count": len(resources) - mutation_content_fit,
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


def verify_bg_resource_writeback_audit(
    root: Path,
    artifact: Path,
) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    expected: dict[str, Any] | None = None
    try:
        expected = _expected_payload(root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"could not reconstruct expected audit: {error}")
    try:
        manifest = _json(artifact / "manifest.json")
        payload_path = artifact / PAYLOAD_NAME
        payload = _json(payload_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"could not read artifact: {error}")
        return {"verified": False, "errors": errors}

    payload_digest = _sha256(payload_path)
    if manifest.get("schema") != "git-artifact-promotion-v1":
        errors.append("promotion manifest schema mismatch")
    if manifest.get("artifact_id") != ARTIFACT_ID:
        errors.append("promotion artifact ID mismatch")
    if manifest.get("artifact_schema") != "bg-resource-writeback-audit-v1":
        errors.append("promotion artifact schema mismatch")
    if manifest.get("artifact_status") != "accepted":
        errors.append("promotion artifact status mismatch")
    if manifest.get("payload_file") != PAYLOAD_NAME:
        errors.append("promotion payload file mismatch")
    if manifest.get("payload_sha256") != payload_digest:
        errors.append("promotion payload hash mismatch")
    if manifest.get("files") != {PAYLOAD_NAME: payload_digest}:
        errors.append("promotion file inventory mismatch")
    verifier = manifest.get("verifier")
    expected_command = [
        "python3",
        "tools/verify_bg_resource_writeback_audit.py",
        "--root",
        ".",
        "--artifact",
        f"artifacts/{ARTIFACT_ID}",
    ]
    if (
        not isinstance(verifier, dict)
        or verifier.get("command") != expected_command
        or verifier.get("exit_code") != 0
    ):
        errors.append("promotion verifier evidence mismatch")
    if expected is not None:
        if manifest.get("scope") != expected["scope"]:
            errors.append("promotion scope mismatch")
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
                errors.append(f"payload {key} mismatch")
    summary = payload.get("summary", {})
    return {
        "verified": not errors,
        "content_resources": summary.get("content_resource_count"),
        "physical_slots": summary.get("physical_slot_count"),
        "logical_references": summary.get("logical_reference_count"),
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
        args.artifact
        if args.artifact.is_absolute()
        else args.root / args.artifact
    )
    report = verify_bg_resource_writeback_audit(args.root, artifact)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
