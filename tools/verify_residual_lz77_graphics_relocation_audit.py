#!/usr/bin/env python3
"""Independently verify the residual LZ77 graphics relocation artifact."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
INVENTORY_PATH = Path(
    "artifacts/rom-pointer-lz77-inventory-v1/"
    "rom-pointer-lz77-inventory.json"
)
INVENTORY_SHA256 = (
    "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
)
CATALOG_PATH = Path(
    "artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json"
)
CATALOG_SHA256 = (
    "9c3088165fb65004dbeaa124a800d65795395e37b2dcfb90f2d2eedfdd6cf37d"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
LAYOUT_PATH = Path("sequel/rom-layout.json")
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
ARTIFACT_ID = "residual-lz77-graphics-relocation-v1"
PAYLOAD_SCHEMA = "residual-lz77-graphics-relocation-audit-v1"
REGION_START = 0xBB0000
REGION_END = 0xBC0000
TARGET_ROM_SIZE = 0x1000000
EXPECTED_RESOURCE_COUNT = 20
EXPECTED_POINTER_COUNT = 34
EXPECTED_DECOMPRESSED_SIZE = 36_640
EXPECTED_COMPRESSED_SIZE = 16_574
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/export_rom_pointer_lz77_graphics.py",
    "tools/verify_rom_pointer_lz77_graphics.py",
    "tools/import_residual_lz77_graphics_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_residual_lz77_graphics_relocation_audit.py",
    "tools/verify_residual_lz77_graphics_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "All 20 residual aligned-pointer-reachable 4bpp LZ77 graphics and "
        "all 34 exact source-pointer literals are accounted for. A full "
        "preservation relocation rebuilds a 16 MiB ROM."
    ),
    "editable": (
        "Every resource may replace all of its complete 4bpp tiles while "
        "preserving that resource's decoded tile count. Recompression may "
        "use the entire registered 64 KiB region instead of the old slot."
    ),
    "not_proved": (
        "Changing decoded tile counts or VRAM destinations, editing raw or "
        "LZ77 palettes, the two unresolved palette identities, natural "
        "business names, and final screen-composited runtime equivalence."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} is not a pointer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        result = int(value, 0)
    else:
        raise ValueError(f"{label} is not a pointer")
    if not ROM_BASE <= result < 0x0A000000:
        raise ValueError(f"{label} is outside mapped ROM")
    return result


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as error:
            raise ValueError(f"{label} must be an integer") from error
    raise ValueError(f"{label} must be an integer")


def _power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _validate_layout_and_regions(
    base: bytes,
    layout: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    if layout.get("version") != 1:
        raise ValueError("ROM layout version mismatch")
    base_spec = layout.get("base_rom")
    if (
        not isinstance(base_spec, dict)
        or _integer(base_spec.get("size"), "base_rom.size") != len(base)
        or str(base_spec.get("sha1", "")).lower()
        != hashlib.sha1(base).hexdigest()
    ):
        raise ValueError("ROM layout base contract mismatch")
    profile = layout.get("cartridge_profile")
    if (
        not isinstance(profile, dict)
        or _integer(profile.get("rom_base"), "cartridge_profile.rom_base")
        != ROM_BASE
        or _integer(
            profile.get("max_rom_size"),
            "cartridge_profile.max_rom_size",
        )
        < TARGET_ROM_SIZE
    ):
        raise ValueError("ROM layout cartridge profile mismatch")
    if (
        _integer(layout.get("target_rom_size"), "target_rom_size")
        != TARGET_ROM_SIZE
        or _integer(layout.get("fill_byte"), "fill_byte") != 0xFF
    ):
        raise ValueError("ROM layout target contract mismatch")

    raw_partitions = layout.get("partitions")
    if not isinstance(raw_partitions, list):
        raise ValueError("ROM layout partitions must be an array")
    partitions = []
    partition_ids = set()
    for index, raw in enumerate(raw_partitions):
        if not isinstance(raw, dict):
            raise ValueError(f"ROM layout partition {index} is invalid")
        partition_id = str(raw.get("id", "")).strip()
        owner = str(raw.get("owner", "")).strip()
        origin = str(raw.get("origin", "")).strip()
        if (
            not partition_id
            or partition_id in partition_ids
            or not owner
            or origin not in {"base_ff", "expanded_ff"}
        ):
            raise ValueError("ROM layout partition identity mismatch")
        partition_ids.add(partition_id)
        start = _integer(raw.get("start"), f"{partition_id}.start")
        end = _integer(raw.get("end"), f"{partition_id}.end")
        alignment = _integer(
            raw.get("alignment", 1),
            f"{partition_id}.alignment",
        )
        if (
            start < 0
            or end <= start
            or end > TARGET_ROM_SIZE
            or not _power_of_two(alignment)
            or start % alignment
            or end % alignment
        ):
            raise ValueError("ROM layout partition range mismatch")
        if origin == "base_ff":
            if end > len(base) or base[start:end] != bytes([0xFF]) * (
                end - start
            ):
                raise ValueError("ROM layout base_ff partition mismatch")
        elif start < len(base):
            raise ValueError("ROM layout expanded_ff partition mismatch")
        partitions.append(
            {
                "id": partition_id,
                "owner": owner,
                "origin": origin,
                "start": start,
                "end": end,
                "alignment": alignment,
            }
        )
    partitions.sort(key=lambda row: (row["start"], row["end"], row["id"]))
    for left, right in zip(partitions, partitions[1:]):
        if left["end"] > right["start"]:
            raise ValueError("ROM layout partitions overlap")
    parents = [
        row for row in partitions if row["id"] == "sequel-image-assets"
    ]
    if parents != [
        {
            "id": "sequel-image-assets",
            "owner": "sequel_image_assets",
            "origin": "expanded_ff",
            "start": 0x800000,
            "end": 0xC00000,
            "alignment": 4,
        }
    ]:
        raise ValueError("image resource parent partition mismatch")
    parent = parents[0]

    if (
        registry.get("version") != 1
        or registry.get("parent_partition") != parent["id"]
        or registry.get("parent_owner") != parent["owner"]
    ):
        raise ValueError("image resource registry parent mismatch")
    raw_regions = registry.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("image resource regions must be a non-empty array")
    regions = []
    region_ids = set()
    for index, raw in enumerate(raw_regions):
        if not isinstance(raw, dict):
            raise ValueError(f"image resource region {index} is invalid")
        region_id = str(raw.get("id", "")).strip()
        owner = str(raw.get("owner", "")).strip()
        if not region_id or region_id in region_ids or not owner:
            raise ValueError("image resource region identity mismatch")
        region_ids.add(region_id)
        start = _integer(raw.get("start"), f"{region_id}.start")
        end = _integer(raw.get("end"), f"{region_id}.end")
        alignment = _integer(
            raw.get("alignment", 1),
            f"{region_id}.alignment",
        )
        if (
            start < parent["start"]
            or end <= start
            or end > parent["end"]
            or not _power_of_two(alignment)
            or start % alignment
            or end % alignment
        ):
            raise ValueError("image resource region range mismatch")
        regions.append(
            {
                "id": region_id,
                "owner": owner,
                "start": start,
                "end": end,
                "alignment": alignment,
            }
        )
    regions.sort(key=lambda row: row["start"])
    cursor = parent["start"]
    for region in regions:
        if region["start"] != cursor:
            raise ValueError(
                "image resource regions do not cover the parent continuously"
            )
        cursor = region["end"]
    if cursor != parent["end"]:
        raise ValueError(
            "image resource regions do not cover the parent continuously"
        )
    residual = [
        row for row in regions if row["id"] == "residual-lz77-graphics"
    ]
    if len(residual) != 1:
        raise ValueError("registered residual LZ77 region is missing")
    return residual[0]


def _decode_lz77(data: bytes, offset: int) -> tuple[bytes, int]:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError("invalid type-0x10 LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if size <= 0:
        raise ValueError("invalid type-0x10 LZ77 size")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(data):
            raise ValueError("truncated type-0x10 LZ77 flags")
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(data):
                    raise ValueError("truncated type-0x10 LZ77 back-reference")
                token = (data[cursor] << 8) | data[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid type-0x10 LZ77 distance")
                for _ in range(length):
                    if len(output) >= size:
                        break
                    output.append(output[-distance])
            else:
                if cursor >= len(data):
                    raise ValueError("truncated type-0x10 LZ77 literal")
                output.append(data[cursor])
                cursor += 1
    return bytes(output), cursor - offset


def _encode_lz77(data: bytes) -> bytes:
    if not data or len(data) >= 1 << 24:
        raise ValueError("invalid LZ77 input size")
    output = bytearray(
        (0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, len(data) >> 16)
    )
    positions: dict[bytes, deque[int]] = {}
    cursor = 0
    while cursor < len(data):
        flags_offset = len(output)
        output.append(0)
        flags = 0
        for token_index in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                key = data[cursor : cursor + 3]
                for previous in reversed(positions.get(key, ())):
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
        output[flags_offset] = flags
    return bytes(output)


def _aligned_offsets(data: bytes, pointer: int) -> list[int]:
    encoded = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(data) - 3, 4)
        if data[offset : offset + 4] == encoded
    ]


def _resolve_spec_file(
    root: Path,
    artifact: Path,
    value: object,
    expected_name: str,
) -> Path:
    if not isinstance(value, str):
        raise ValueError("authoring graphics_file must be a path")
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    expected = (artifact / expected_name).resolve()
    if resolved != expected:
        raise ValueError("authoring graphics_file escapes the artifact")
    return resolved


def _mutate_first_tile(raw: bytes, index: int) -> bytes:
    result = bytearray(raw)
    for offset in range(32):
        result[offset] ^= (index * 29 + offset * 7 + 1) & 0xFF
    return bytes(result)


def _rebuild(
    base: bytes,
    resources: list[dict[str, Any]],
    *,
    fixture: bool,
) -> tuple[str, list[dict[str, Any]], int, int]:
    output = bytearray(base + bytes([0xFF]) * (TARGET_ROM_SIZE - len(base)))
    cursor = REGION_START
    allocations = []
    stored = 0
    for index, row in enumerate(resources):
        raw = _mutate_first_tile(row["raw"], index) if fixture else row["raw"]
        encoded = _encode_lz77(raw)
        decoded, consumed = _decode_lz77(encoded, 0)
        if decoded != raw or consumed != len(encoded):
            raise ValueError("independent LZ77 round-trip mismatch")
        cursor = (cursor + 3) & ~3
        end = cursor + len(encoded)
        if end > REGION_END:
            raise ValueError("independent rebuild exceeds registered region")
        if output[cursor:end] != bytes([0xFF]) * len(encoded):
            raise ValueError("independent rebuild allocation is not fill")
        output[cursor:end] = encoded
        new_pointer = ROM_BASE + cursor
        for pointer_offset in row["pointer_offsets"]:
            old = struct.unpack_from("<I", output, pointer_offset)[0]
            if old != row["source_pointer"]:
                raise ValueError("independent pointer before-word mismatch")
            struct.pack_into("<I", output, pointer_offset, new_pointer)
        allocations.append(
            {
                "id": f"residual-lz77-graphics-{index:02d}",
                "offset": cursor,
                "source_pointer": row["source_pointer"],
                "new_pointer": new_pointer,
                "decompressed_size": len(raw),
                "encoded_size": len(encoded),
                "tile_count": len(raw) // 32,
                "replacement_sha256": _sha256(raw),
                "destination_addresses": row["destination_addresses"],
                "palette_binding_kind": row["palette_binding_kind"],
                "palette_source_addresses": row[
                    "palette_source_addresses"
                ],
                "pointer_offsets": row["pointer_offsets"],
            }
        )
        stored += len(encoded)
        cursor = end
    return _sha256(bytes(output)), allocations, cursor, stored


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    manifest_path = artifact / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_id") != ARTIFACT_ID
        or manifest.get("artifact_schema") != PAYLOAD_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("payload_file") != PAYLOAD_NAME
    ):
        raise ValueError("artifact manifest contract mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("artifact file manifest is invalid")
    actual_names = {path.name for path in artifact.iterdir() if path.is_file()}
    if actual_names != set(files) | {"manifest.json"}:
        raise ValueError("artifact file set mismatch")
    for name, expected_hash in files.items():
        if _sha256((artifact / name).read_bytes()) != expected_hash:
            raise ValueError(f"artifact file hash mismatch: {name}")
    payload_path = artifact / PAYLOAD_NAME
    if manifest.get("payload_sha256") != _sha256(payload_path.read_bytes()):
        raise ValueError("artifact payload hash mismatch")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    spec_path = artifact / SPEC_NAME
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if payload.get("schema") != PAYLOAD_SCHEMA:
        raise ValueError("artifact payload schema mismatch")
    if payload.get("scope") != SCOPE or manifest.get("scope") != SCOPE:
        raise ValueError("artifact scope mismatch")
    if payload.get("summary") != manifest.get("summary"):
        raise ValueError("artifact summary mismatch")
    if payload.get("authoring_spec") != {
        "file": SPEC_NAME,
        "sha256": _sha256(spec_path.read_bytes()),
    }:
        raise ValueError("artifact authoring spec hash mismatch")

    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("base ROM contract mismatch")
    layout_bytes = (root / LAYOUT_PATH).read_bytes()
    registry_bytes = (root / REGISTRY_PATH).read_bytes()
    inventory_bytes = (root / INVENTORY_PATH).read_bytes()
    catalog_bytes = (root / CATALOG_PATH).read_bytes()
    if _sha256(inventory_bytes) != INVENTORY_SHA256:
        raise ValueError("source inventory hash mismatch")
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("source graphics catalog hash mismatch")
    layout = json.loads(layout_bytes)
    registry = json.loads(registry_bytes)
    region = _validate_layout_and_regions(base, layout, registry)
    if (
        region["start"] != REGION_START
        or region["end"] != REGION_END
        or region["owner"] != "residual_lz77_graphics"
        or region["alignment"] != 4
    ):
        raise ValueError("registered residual LZ77 region mismatch")
    expected_metadata = {
        "base_rom": {
            "path": "rom/base.gba",
            "size": len(base),
            "sha256": ROM_SHA256,
        },
        "layout": {
            "path": LAYOUT_PATH.as_posix(),
            "sha256": _sha256(layout_bytes),
            "target_rom_size": TARGET_ROM_SIZE,
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
        },
        "region_registry": {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": _sha256(registry_bytes),
            "region": "residual-lz77-graphics",
            "owner": "residual_lz77_graphics",
            "start": REGION_START,
            "end": REGION_END,
        },
        "inventory": {
            "path": INVENTORY_PATH.as_posix(),
            "sha256": INVENTORY_SHA256,
        },
        "catalog": {
            "path": CATALOG_PATH.as_posix(),
            "sha256": CATALOG_SHA256,
        },
    }
    for key, expected in expected_metadata.items():
        if payload.get(key) != expected:
            raise ValueError(f"artifact {key} metadata mismatch")
    expected_implementation = {
        path: _sha256((root / path).read_bytes())
        for path in IMPLEMENTATION_PATHS
    }
    if payload.get("implementation") != expected_implementation:
        raise ValueError("artifact implementation hash mismatch")

    inventory = json.loads(inventory_bytes)
    preview = json.loads(catalog_bytes)
    records = [
        row
        for row in inventory.get("new_records", [])
        if row.get("classification", {}).get("kind") == "graphics"
    ]
    preview_rows = preview.get("graphics")
    if len(records) != EXPECTED_RESOURCE_COUNT or not isinstance(
        preview_rows, list
    ) or len(preview_rows) != EXPECTED_RESOURCE_COUNT:
        raise ValueError("source resource denominator mismatch")
    preview_by_pointer = {
        _pointer(row.get("graphics_address"), "graphics_address"): row
        for row in preview_rows
    }
    resources = []
    total_refs = 0
    total_decoded = 0
    total_compressed = 0
    unresolved = 0
    for row in sorted(
        records,
        key=lambda value: _pointer(value.get("gba_address"), "gba_address"),
    ):
        pointer = _pointer(row.get("gba_address"), "gba_address")
        decoded, consumed = _decode_lz77(base, pointer - ROM_BASE)
        if (
            consumed != row.get("compressed_size")
            or len(decoded) != row.get("decompressed_size")
            or len(decoded) % 32
            or _sha256(decoded) != row.get("decompressed_sha256")
        ):
            raise ValueError("source LZ77 payload mismatch")
        source_preview = preview_by_pointer.get(pointer)
        if (
            source_preview is None
            or source_preview.get("decompressed_size") != len(decoded)
            or source_preview.get("decompressed_sha256") != _sha256(decoded)
        ):
            raise ValueError("source preview payload mismatch")
        pointer_offsets = sorted(
            int(value, 16) - ROM_BASE
            for value in row.get("aligned_pointer_references", [])
        )
        if _aligned_offsets(base, pointer) != pointer_offsets:
            raise ValueError("source pointer denominator mismatch")
        binding = source_preview.get("palette_binding")
        if not isinstance(binding, dict):
            raise ValueError("source palette binding mismatch")
        if binding.get("kind") == "unresolved":
            unresolved += 1
        name = f"graphics_{pointer:08x}.4bpp.bin"
        raw = (artifact / name).read_bytes()
        if raw != decoded:
            raise ValueError("artifact raw graphics differ from base ROM")
        resources.append(
            {
                "source_pointer": pointer,
                "raw_name": name,
                "raw": raw,
                "pointer_offsets": pointer_offsets,
                "destination_addresses": row["classification"].get(
                    "destination_addresses", []
                ),
                "palette_binding_kind": binding.get("kind"),
                "palette_source_addresses": binding.get(
                    "source_addresses", []
                ),
            }
        )
        total_refs += len(pointer_offsets)
        total_decoded += len(decoded)
        total_compressed += consumed
    if (
        total_refs != EXPECTED_POINTER_COUNT
        or total_decoded != EXPECTED_DECOMPRESSED_SIZE
        or total_compressed != EXPECTED_COMPRESSED_SIZE
        or unresolved != 2
    ):
        raise ValueError("source aggregate denominator mismatch")

    expected_spec = {
        "schema": "residual-lz77-graphics-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "source_inventory": INVENTORY_PATH.as_posix(),
        "source_inventory_sha256": INVENTORY_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry_bytes),
        "region": "residual-lz77-graphics",
        "region_owner": "residual_lz77_graphics",
    }
    for key, expected in expected_spec.items():
        if spec.get(key) != expected:
            raise ValueError(f"authoring spec {key} mismatch")
    spec_resources = spec.get("resources")
    if not isinstance(spec_resources, list) or len(spec_resources) != len(
        resources
    ):
        raise ValueError("authoring spec resource denominator mismatch")
    for row, expected in zip(spec_resources, resources):
        if (
            not isinstance(row, dict)
            or _pointer(row.get("source_pointer"), "source_pointer")
            != expected["source_pointer"]
        ):
            raise ValueError("authoring spec resource order mismatch")
        _resolve_spec_file(
            root,
            artifact,
            row.get("graphics_file"),
            expected["raw_name"],
        )

    output_hash, allocations, allocation_end, stored = _rebuild(
        base,
        resources,
        fixture=False,
    )
    fixture_hash, _, _, _ = _rebuild(base, resources, fixture=True)
    summary = {
        "resource_count": EXPECTED_RESOURCE_COUNT,
        "source_pointer_reference_count": EXPECTED_POINTER_COUNT,
        "unexpected_source_pointer_count": 0,
        "decompressed_size": EXPECTED_DECOMPRESSED_SIZE,
        "source_compressed_size": EXPECTED_COMPRESSED_SIZE,
        "unresolved_palette_count": 2,
        "allocation_count": EXPECTED_RESOURCE_COUNT,
        "pointer_patch_count": EXPECTED_POINTER_COUNT,
        "allocation_start": REGION_START,
        "allocation_end": allocation_end,
        "region_end": REGION_END,
        "stored_payload_bytes": stored,
        "allocation_span": allocation_end - REGION_START,
        "remaining_bytes": REGION_END - allocation_end,
        "applied_patch_count": EXPECTED_RESOURCE_COUNT
        + EXPECTED_POINTER_COUNT,
    }
    if payload.get("summary") != summary:
        raise ValueError("artifact summary is not independently reproducible")
    if payload.get("allocations") != allocations:
        raise ValueError("artifact allocation plan mismatch")
    expected_pointers = []
    for allocation in allocations:
        for pointer_offset in allocation["pointer_offsets"]:
            expected_pointers.append(
                {
                    "id": (
                        f"{allocation['id']}.pointer-{pointer_offset:06x}"
                    ),
                    "offset": pointer_offset,
                    "source_pointer": allocation["source_pointer"],
                    "new_pointer": allocation["new_pointer"],
                    "pointer_role": "graphics_source",
                }
            )
    expected_pointers.sort(key=lambda row: row["offset"])
    if payload.get("pointer_patches") != expected_pointers:
        raise ValueError("artifact pointer patch plan mismatch")
    if payload.get("output_rom_sha256") != output_hash:
        raise ValueError("artifact output ROM hash mismatch")
    expected_fixture = {
        "mutation": (
            "xor each resource first 32-byte tile with "
            "(resource_index*29 + byte_offset*7 + 1) & 0xff"
        ),
        "changed_resources": EXPECTED_RESOURCE_COUNT,
        "output_rom_sha256": fixture_hash,
    }
    if payload.get("capability_fixture") != expected_fixture:
        raise ValueError("artifact capability fixture mismatch")
    return {
        "verified_resources": EXPECTED_RESOURCE_COUNT,
        "verified_source_pointers": EXPECTED_POINTER_COUNT,
        "rebuilt_output_rom_sha256": output_hash,
        "capability_fixture_output_rom_sha256": fixture_hash,
    }


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    result = {
        "schema": "residual-lz77-graphics-relocation-verification-v1",
        "verified_resources": 0,
        "verified_source_pointers": 0,
        "rebuilt_output_rom_sha256": None,
        "capability_fixture_output_rom_sha256": None,
        "errors": [],
    }
    try:
        result.update(_verify(root, artifact))
    except Exception as error:  # fail closed with one stable public report
        result["errors"].append(f"{type(error).__name__}: {error}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(f"artifacts/{ARTIFACT_ID}"),
    )
    args = parser.parse_args()
    artifact = args.artifact
    if not artifact.is_absolute():
        artifact = args.root / artifact
    result = verify_audit(args.root, artifact)
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
