#!/usr/bin/env python3
"""Independently verify the direct image palette relocation artifact."""

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
LZ_INVENTORY_PATH = Path(
    "artifacts/rom-pointer-lz77-inventory-v1/"
    "rom-pointer-lz77-inventory.json"
)
LZ_INVENTORY_SHA256 = (
    "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
)
GRAPHICS_CATALOG_PATH = Path(
    "artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json"
)
GRAPHICS_CATALOG_SHA256 = (
    "9c3088165fb65004dbeaa124a800d65795395e37b2dcfb90f2d2eedfdd6cf37d"
)
DIRECT_INVENTORY_PATH = Path(
    "artifacts/rom-direct-cpuset-gpu-inventory-v1/"
    "rom-direct-cpuset-gpu-inventory.json"
)
DIRECT_INVENTORY_SHA256 = (
    "aaf98e551ccd103b27432231ec607702cfc370768a403a7ca56d766b861275eb"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
LAYOUT_PATH = Path("sequel/rom-layout.json")
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
ARTIFACT_ID = "direct-image-palette-relocation-v1"
PAYLOAD_SCHEMA = "direct-image-palette-relocation-audit-v1"
REGION_START = 0xBC0000
REGION_END = 0xBC0400
TARGET_ROM_SIZE = 0x1000000
EXPECTED_LZ_POINTERS = {0x080B9F5C, 0x08348668, 0x083F0AC8}
EXPECTED_LOGICAL_COUNT = 18
EXPECTED_PHYSICAL_COUNT = 17
EXPECTED_POINTER_COUNT = 29
RANGE_ALIAS_POINTER = 0x08406010
RANGE_ALIAS_PARENT = 0x08405FF0
RANGE_ALIAS_OFFSET = 0x20
OVERLAP_POINTER = 0x084060A8
OVERLAP_OFFSET = 0xB8
OVERLAP_SIZE = 72
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/export_rom_pointer_lz77_graphics.py",
    "tools/verify_rom_pointer_lz77_graphics.py",
    "tools/export_rom_direct_cpuset_gpu_inventory.py",
    "tools/verify_rom_direct_cpuset_gpu_inventory.py",
    "tools/import_direct_image_palette_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_direct_image_palette_relocation_audit.py",
    "tools/verify_direct_image_palette_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "All 18 strictly proven direct ROM-to-PRAM palette source addresses "
        "and all 29 exact aligned source-pointer roots are accounted for as "
        "17 physical allocations. A preservation relocation rebuilds a "
        "16 MiB ROM."
    ),
    "editable": (
        "All three 16-color LZ77 palettes and every non-overlap-locked raw "
        "BGR555 byte may be replaced at fixed decoded size. The nested "
        "0x08406010 source remains an alias of 0x08405FF0+0x20."
    ),
    "not_proved": (
        "Editing the 72 bytes shared with the scene LZ77 stream, assigning "
        "palettes to the two unresolved graphics, changing PRAM destinations "
        "or copy lengths, and final screen-composited runtime equivalence."
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _pointer(value: object, label: str) -> int:
    result = _integer(value, label)
    if not ROM_BASE <= result < 0x0A000000:
        raise ValueError(f"{label} is outside mapped ROM")
    return result


def _power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


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
                    raise ValueError("truncated type-0x10 LZ77 token")
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
        flag_offset = len(output)
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
        output[flag_offset] = flags
    return bytes(output)


def _aligned_offsets(data: bytes, pointer: int) -> list[int]:
    encoded = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(data) - 3, 4)
        if data[offset : offset + 4] == encoded
    ]


def _validate_layout_and_regions(
    base: bytes,
    layout: dict[str, Any],
    registry: dict[str, Any],
) -> None:
    if layout.get("version") != 1:
        raise ValueError("ROM layout version mismatch")
    base_spec = layout.get("base_rom")
    if (
        not isinstance(base_spec, dict)
        or _integer(base_spec.get("size"), "base size") != len(base)
        or str(base_spec.get("sha1", "")).lower()
        != hashlib.sha1(base).hexdigest()
        or _integer(layout.get("target_rom_size"), "target size")
        != TARGET_ROM_SIZE
        or _integer(layout.get("fill_byte"), "fill byte") != 0xFF
    ):
        raise ValueError("ROM layout base or target contract mismatch")
    partitions = layout.get("partitions")
    if not isinstance(partitions, list):
        raise ValueError("ROM layout partitions are invalid")
    normalized = []
    seen = set()
    for row in partitions:
        if not isinstance(row, dict):
            raise ValueError("ROM layout partition is invalid")
        identifier = str(row.get("id", "")).strip()
        owner = str(row.get("owner", "")).strip()
        origin = str(row.get("origin", "")).strip()
        start = _integer(row.get("start"), f"{identifier}.start")
        end = _integer(row.get("end"), f"{identifier}.end")
        alignment = _integer(row.get("alignment", 1), "alignment")
        if (
            not identifier
            or identifier in seen
            or not owner
            or origin not in {"base_ff", "expanded_ff"}
            or start < 0
            or end <= start
            or end > TARGET_ROM_SIZE
            or not _power_of_two(alignment)
            or start % alignment
            or end % alignment
        ):
            raise ValueError("ROM layout partition contract mismatch")
        seen.add(identifier)
        normalized.append(
            (start, end, identifier, owner, origin, alignment)
        )
    normalized.sort()
    if any(left[1] > right[0] for left, right in zip(normalized, normalized[1:])):
        raise ValueError("ROM layout partitions overlap")
    parent = [
        row for row in normalized if row[2] == "sequel-image-assets"
    ]
    if parent != [
        (
            0x800000,
            0xC00000,
            "sequel-image-assets",
            "sequel_image_assets",
            "expanded_ff",
            4,
        )
    ]:
        raise ValueError("image resource parent partition mismatch")
    if (
        registry.get("version") != 1
        or registry.get("parent_partition") != "sequel-image-assets"
        or registry.get("parent_owner") != "sequel_image_assets"
    ):
        raise ValueError("image region registry parent mismatch")
    raw_regions = registry.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("image regions are invalid")
    regions = []
    identifiers = set()
    for row in raw_regions:
        if not isinstance(row, dict):
            raise ValueError("image region is invalid")
        identifier = str(row.get("id", "")).strip()
        owner = str(row.get("owner", "")).strip()
        start = _integer(row.get("start"), f"{identifier}.start")
        end = _integer(row.get("end"), f"{identifier}.end")
        alignment = _integer(row.get("alignment", 1), "alignment")
        if (
            not identifier
            or identifier in identifiers
            or not owner
            or start < 0x800000
            or end <= start
            or end > 0xC00000
            or not _power_of_two(alignment)
            or start % alignment
            or end % alignment
        ):
            raise ValueError("image region contract mismatch")
        identifiers.add(identifier)
        regions.append((start, end, identifier, owner, alignment))
    regions.sort()
    cursor = 0x800000
    for row in regions:
        if row[0] != cursor:
            raise ValueError("image regions have a gap or overlap")
        cursor = row[1]
    if cursor != 0xC00000:
        raise ValueError("image regions do not cover the parent")
    direct = [
        row for row in regions if row[2] == "direct-image-palettes"
    ]
    if direct != [
        (
            REGION_START,
            REGION_END,
            "direct-image-palettes",
            "direct_image_palettes",
            4,
        )
    ]:
        raise ValueError("direct image palette region mismatch")


def _resolve_spec_file(
    root: Path,
    artifact: Path,
    value: object,
    expected_name: str,
) -> Path:
    if not isinstance(value, str):
        raise ValueError("palette_file must be a path")
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if resolved != (artifact / expected_name).resolve():
        raise ValueError("palette_file escapes the artifact")
    return resolved


def _build_source_catalog(
    base: bytes,
    lz_inventory: dict[str, Any],
    graphics_catalog: dict[str, Any],
    direct_inventory: dict[str, Any],
) -> list[dict[str, Any]]:
    lz_records = [
        row
        for row in lz_inventory.get("new_records", [])
        if row.get("classification", {}).get("kind") == "palette"
    ]
    if (
        len(lz_records) != 3
        or {
            _pointer(row.get("gba_address"), "gba_address")
            for row in lz_records
        }
        != EXPECTED_LZ_POINTERS
    ):
        raise ValueError("LZ77 palette denominator mismatch")
    resources = []
    for row in sorted(
        lz_records,
        key=lambda value: _pointer(value.get("gba_address"), "gba_address"),
    ):
        pointer = _pointer(row.get("gba_address"), "gba_address")
        raw, consumed = _decode_lz77(base, pointer - ROM_BASE)
        refs = sorted(
            int(value, 16) - ROM_BASE
            for value in row.get("aligned_pointer_references", [])
        )
        if (
            len(raw) != 32
            or consumed != row.get("compressed_size")
            or _sha256(raw) != row.get("decompressed_sha256")
            or _aligned_offsets(base, pointer) != refs
        ):
            raise ValueError("LZ77 palette source mismatch")
        resources.append(
            {
                "source_pointer": pointer,
                "storage_kind": "lz77",
                "decoded_size": 32,
                "raw": raw,
                "pointer_offsets": refs,
                "range_aliases": [],
                "locked_ranges": [],
            }
        )
    operations = direct_inventory.get("constant_rom_gpu_operations")
    if (
        not isinstance(operations, list)
        or len(operations) != 23
        or direct_inventory.get("summary", {}).get("unique_source_count")
        != 15
    ):
        raise ValueError("raw palette operation denominator mismatch")
    by_pointer: dict[int, list[dict[str, Any]]] = {}
    for row in operations:
        if (
            row.get("destination_domain") != "PRAM"
            or row.get("loader") not in {"CpuSet", "CpuFastSet"}
        ):
            raise ValueError("raw palette operation mismatch")
        pointer = _pointer(row.get("source_address"), "source_address")
        by_pointer.setdefault(pointer, []).append(row)
    if len(by_pointer) != 15:
        raise ValueError("raw palette source denominator mismatch")
    for pointer in sorted(set(by_pointer) - {RANGE_ALIAS_POINTER}):
        size = max(row["copy_size"] for row in by_pointer[pointer])
        if (pointer == RANGE_ALIAS_PARENT and size != 256) or (
            pointer != RANGE_ALIAS_PARENT and size != 32
        ):
            raise ValueError("raw palette size mismatch")
        start = pointer - ROM_BASE
        raw = base[start : start + size]
        aliases = []
        locked = []
        if pointer == RANGE_ALIAS_PARENT:
            aliases = [
                {
                    "source_pointer": RANGE_ALIAS_POINTER,
                    "parent_offset": RANGE_ALIAS_OFFSET,
                    "pointer_offsets": _aligned_offsets(
                        base,
                        RANGE_ALIAS_POINTER,
                    ),
                }
            ]
            overlaps = [
                row
                for row in by_pointer[pointer]
                if row.get("lz77_overlaps")
            ]
            if (
                len(overlaps) != 1
                or overlaps[0]["lz77_overlaps"]
                != [
                    {
                        "source_address": "0x084060A8",
                        "compressed_end_address": "0x08406550",
                    }
                ]
            ):
                raise ValueError("raw palette overlap mismatch")
            locked = [
                {
                    "offset": OVERLAP_OFFSET,
                    "size": OVERLAP_SIZE,
                    "overlap_pointer": OVERLAP_POINTER,
                }
            ]
        resources.append(
            {
                "source_pointer": pointer,
                "storage_kind": "raw",
                "decoded_size": size,
                "raw": raw,
                "pointer_offsets": _aligned_offsets(base, pointer),
                "range_aliases": aliases,
                "locked_ranges": locked,
            }
        )
    resources.sort(key=lambda row: row["source_pointer"])
    logical = len(resources) + sum(
        len(row["range_aliases"]) for row in resources
    )
    roots = sum(
        len(row["pointer_offsets"])
        + sum(len(alias["pointer_offsets"]) for alias in row["range_aliases"])
        for row in resources
    )
    if (
        len(resources) != EXPECTED_PHYSICAL_COUNT
        or logical != EXPECTED_LOGICAL_COUNT
        or roots != EXPECTED_POINTER_COUNT
        or sum(
            row["decoded_size"]
            for row in resources
            if row["storage_kind"] == "raw"
        )
        != 672
        or graphics_catalog.get("summary", {}).get(
            "unresolved_palette_count"
        )
        != 2
    ):
        raise ValueError("palette source aggregate mismatch")
    return resources


def _mutate(raw: bytes, source_pointer: int, index: int) -> bytes:
    result = bytearray(raw)
    result[2] ^= (index * 17 + 1) & 0xFF
    if source_pointer == RANGE_ALIAS_PARENT:
        result[0x22] ^= 0x5A
    return bytes(result)


def _rebuild(
    base: bytes,
    resources: list[dict[str, Any]],
    *,
    fixture: bool,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], int, int]:
    output = bytearray(base + bytes([0xFF]) * (TARGET_ROM_SIZE - len(base)))
    cursor = REGION_START
    allocations = []
    redirects = []
    stored = 0
    for index, row in enumerate(resources):
        raw = (
            _mutate(row["raw"], row["source_pointer"], index)
            if fixture
            else row["raw"]
        )
        encoded = _encode_lz77(raw) if row["storage_kind"] == "lz77" else raw
        if row["storage_kind"] == "lz77":
            decoded, consumed = _decode_lz77(encoded, 0)
            if decoded != raw or consumed != len(encoded):
                raise ValueError("independent LZ77 round-trip mismatch")
        cursor = (cursor + 3) & ~3
        end = cursor + len(encoded)
        if end > REGION_END:
            raise ValueError("independent palette rebuild exceeds region")
        if output[cursor:end] != bytes([0xFF]) * len(encoded):
            raise ValueError("independent palette allocation is not fill")
        output[cursor:end] = encoded
        new_pointer = ROM_BASE + cursor
        allocation_id = f"direct-image-palette-{index:02d}"
        logical_sources = [row["source_pointer"]] + [
            alias["source_pointer"] for alias in row["range_aliases"]
        ]
        allocations.append(
            {
                "id": allocation_id,
                "offset": cursor,
                "source_pointer": row["source_pointer"],
                "logical_source_pointers": logical_sources,
                "new_pointer": new_pointer,
                "storage_kind": row["storage_kind"],
                "decoded_size": len(raw),
                "encoded_size": len(encoded),
                "color_count": len(raw) // 2,
                "replacement_sha256": _sha256(raw),
                "pointer_offsets": row["pointer_offsets"],
                "range_aliases": row["range_aliases"],
                "locked_ranges": row["locked_ranges"],
            }
        )
        groups = [
            (
                row["source_pointer"],
                new_pointer,
                row["pointer_offsets"],
                0,
            )
        ] + [
            (
                alias["source_pointer"],
                new_pointer + alias["parent_offset"],
                alias["pointer_offsets"],
                alias["parent_offset"],
            )
            for alias in row["range_aliases"]
        ]
        for source_pointer, target, offsets, alias_offset in groups:
            for pointer_offset in offsets:
                old = struct.unpack_from("<I", output, pointer_offset)[0]
                if old != source_pointer:
                    raise ValueError("independent pointer before-word mismatch")
                struct.pack_into("<I", output, pointer_offset, target)
                redirects.append(
                    {
                        "id": (
                            f"{allocation_id}.pointer-{pointer_offset:06x}"
                        ),
                        "offset": pointer_offset,
                        "source_pointer": source_pointer,
                        "new_pointer": target,
                        "pointer_role": "palette_source",
                        "alias_offset": alias_offset,
                    }
                )
        cursor = end
        stored += len(encoded)
    redirects.sort(key=lambda row: row["offset"])
    return _sha256(bytes(output)), allocations, redirects, cursor, stored


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
    lz_bytes = (root / LZ_INVENTORY_PATH).read_bytes()
    graphics_bytes = (root / GRAPHICS_CATALOG_PATH).read_bytes()
    direct_bytes = (root / DIRECT_INVENTORY_PATH).read_bytes()
    if (
        _sha256(lz_bytes) != LZ_INVENTORY_SHA256
        or _sha256(graphics_bytes) != GRAPHICS_CATALOG_SHA256
        or _sha256(direct_bytes) != DIRECT_INVENTORY_SHA256
    ):
        raise ValueError("source inventory hash mismatch")
    layout = json.loads(layout_bytes)
    registry = json.loads(registry_bytes)
    _validate_layout_and_regions(base, layout, registry)
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
            "region": "direct-image-palettes",
            "owner": "direct_image_palettes",
            "start": REGION_START,
            "end": REGION_END,
        },
        "lz77_inventory": {
            "path": LZ_INVENTORY_PATH.as_posix(),
            "sha256": LZ_INVENTORY_SHA256,
        },
        "graphics_catalog": {
            "path": GRAPHICS_CATALOG_PATH.as_posix(),
            "sha256": GRAPHICS_CATALOG_SHA256,
        },
        "direct_inventory": {
            "path": DIRECT_INVENTORY_PATH.as_posix(),
            "sha256": DIRECT_INVENTORY_SHA256,
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

    resources = _build_source_catalog(
        base,
        json.loads(lz_bytes),
        json.loads(graphics_bytes),
        json.loads(direct_bytes),
    )
    expected_spec = {
        "schema": "direct-image-palette-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "lz77_inventory": LZ_INVENTORY_PATH.as_posix(),
        "lz77_inventory_sha256": LZ_INVENTORY_SHA256,
        "graphics_catalog": GRAPHICS_CATALOG_PATH.as_posix(),
        "graphics_catalog_sha256": GRAPHICS_CATALOG_SHA256,
        "direct_inventory": DIRECT_INVENTORY_PATH.as_posix(),
        "direct_inventory_sha256": DIRECT_INVENTORY_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry_bytes),
        "region": "direct-image-palettes",
        "region_owner": "direct_image_palettes",
    }
    for key, expected in expected_spec.items():
        if spec.get(key) != expected:
            raise ValueError(f"authoring spec {key} mismatch")
    spec_resources = spec.get("resources")
    if not isinstance(spec_resources, list) or len(spec_resources) != len(
        resources
    ):
        raise ValueError("authoring spec resource denominator mismatch")
    for row, source in zip(spec_resources, resources):
        pointer = source["source_pointer"]
        name = f"palette_{pointer:08x}.bgr555.bin"
        if (
            not isinstance(row, dict)
            or _pointer(row.get("source_pointer"), "source_pointer") != pointer
        ):
            raise ValueError("authoring spec resource order mismatch")
        path = _resolve_spec_file(
            root,
            artifact,
            row.get("palette_file"),
            name,
        )
        raw = path.read_bytes()
        if raw != source["raw"]:
            raise ValueError("artifact palette differs from base ROM")

    output_hash, allocations, redirects, end, stored = _rebuild(
        base,
        resources,
        fixture=False,
    )
    fixture_hash, _, _, _, _ = _rebuild(base, resources, fixture=True)
    summary = {
        "logical_source_count": EXPECTED_LOGICAL_COUNT,
        "physical_resource_count": EXPECTED_PHYSICAL_COUNT,
        "source_pointer_reference_count": EXPECTED_POINTER_COUNT,
        "unexpected_source_pointer_count": 0,
        "lz77_resource_count": 3,
        "raw_resource_count": 14,
        "lz77_decoded_size": 96,
        "raw_physical_size": 672,
        "overlap_locked_size": OVERLAP_SIZE,
        "unresolved_graphics_palette_count": 2,
        "allocation_count": EXPECTED_PHYSICAL_COUNT,
        "pointer_patch_count": EXPECTED_POINTER_COUNT,
        "allocation_start": REGION_START,
        "allocation_end": end,
        "region_end": REGION_END,
        "stored_payload_bytes": stored,
        "allocation_span": end - REGION_START,
        "remaining_bytes": REGION_END - end,
        "applied_patch_count": EXPECTED_PHYSICAL_COUNT
        + EXPECTED_POINTER_COUNT,
    }
    if payload.get("summary") != summary:
        raise ValueError("artifact summary is not independently reproducible")
    if payload.get("allocations") != allocations:
        raise ValueError("artifact allocation plan mismatch")
    if payload.get("pointer_patches") != redirects:
        raise ValueError("artifact pointer plan mismatch")
    if payload.get("output_rom_sha256") != output_hash:
        raise ValueError("artifact output ROM hash mismatch")
    expected_fixture = {
        "mutation": (
            "xor byte 2 in every physical palette and byte 0x22 in "
            "0x08405FF0 to cover its nested logical alias"
        ),
        "changed_resources": EXPECTED_PHYSICAL_COUNT,
        "changed_logical_sources": EXPECTED_LOGICAL_COUNT,
        "output_rom_sha256": fixture_hash,
    }
    if payload.get("capability_fixture") != expected_fixture:
        raise ValueError("artifact capability fixture mismatch")
    return {
        "verified_physical_resources": EXPECTED_PHYSICAL_COUNT,
        "verified_logical_sources": EXPECTED_LOGICAL_COUNT,
        "verified_source_pointers": EXPECTED_POINTER_COUNT,
        "rebuilt_output_rom_sha256": output_hash,
        "capability_fixture_output_rom_sha256": fixture_hash,
    }


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact).resolve()
    result = {
        "schema": "direct-image-palette-relocation-verification-v1",
        "verified_physical_resources": 0,
        "verified_logical_sources": 0,
        "verified_source_pointers": 0,
        "rebuilt_output_rom_sha256": None,
        "capability_fixture_output_rom_sha256": None,
        "errors": [],
    }
    try:
        result.update(_verify(root, artifact))
    except Exception as error:
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
