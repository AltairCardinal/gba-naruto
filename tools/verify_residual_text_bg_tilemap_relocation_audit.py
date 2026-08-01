#!/usr/bin/env python3
"""Independently verify the residual text-BG tilemap relocation artifact."""

from __future__ import annotations

import argparse
from collections import deque
from collections import Counter
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
OWNERSHIP_PATH = Path(
    "artifacts/residual-text-bg-tilemap-resource-ownership-v1/"
    "resource-ownership.json"
)
OWNERSHIP_SHA256 = (
    "95c4baf0febd70151d68c08d276bb694daa1f544035466f9b078f73e538d8741"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
LAYOUT_PATH = Path("sequel/rom-layout.json")
ARTIFACT_ID = "residual-text-bg-tilemap-relocation-v1"
PAYLOAD_SCHEMA = "residual-text-bg-tilemap-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
TILEMAP_NAME = "tilemap.bin"
SOURCE_POINTER = 0x08349368
POINTER_OFFSET = 0x08B464
REGION_START = 0xBC0400
REGION_END = 0xBC0C00
TARGET_ROM_SIZE = 0x1000000
IMPLEMENTATION_PATHS = (
    "tools/export_rom_pointer_lz77_inventory.py",
    "tools/verify_rom_pointer_lz77_inventory.py",
    "tools/export_residual_text_bg_tilemap_resource_ownership.py",
    "tools/verify_residual_text_bg_tilemap_resource_ownership.py",
    "tools/import_residual_text_bg_tilemap_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_residual_text_bg_tilemap_relocation_audit.py",
    "tools/verify_residual_text_bg_tilemap_relocation_audit.py",
)
SCOPE = {
    "proved": (
        "The single pointer-reachable residual text-BG tilemap at "
        "0x08349368 and its only aligned source-pointer root relocate into "
        "a 16 MiB ROM, with BG2, graphics and palette ownership bound to a "
        "separately verified artifact."
    ),
    "editable": (
        "All 640 32x20 screen entries may select tile 0..5, palette bank 1, "
        "and standard horizontal or vertical flip bits."
    ),
    "not_proved": (
        "Changing the screenblock destination, coordinated semantic authoring "
        "across its separately relocatable graphics/palette resources, the "
        "runtime ordering against another stream that may reuse 0x06001000, "
        "assigning a natural-language screen identity, and final "
        "screen-composited runtime equivalence."
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
        return int(value, 0)
    raise ValueError(f"{label} must be an integer")


def _power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _decode_lz77(data: bytes, offset: int) -> tuple[bytes, int]:
    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        flags = data[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                token = (data[cursor] << 8) | data[cursor + 1]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                for _ in range(length):
                    if len(output) >= size:
                        break
                    output.append(output[-distance])
            else:
                output.append(data[cursor])
                cursor += 1
    return bytes(output), cursor - offset


def _encode_lz77(data: bytes) -> bytes:
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
                if position + 3 <= len(data):
                    key = data[position : position + 3]
                    bucket = positions.setdefault(key, deque())
                    bucket.append(position)
                    while bucket and position - bucket[0] > 0x1000:
                        bucket.popleft()
            cursor += advance
        output[flag_offset] = flags
    return bytes(output)


def _aligned_offsets(data: bytes, pointer: int) -> list[int]:
    raw = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(data) - 3, 4)
        if data[offset : offset + 4] == raw
    ]


def _tilemap_metadata(data: bytes) -> dict[str, Any]:
    if len(data) != 1280:
        raise ValueError("tilemap size mismatch")
    entries = struct.unpack("<640H", data)
    tiles = [entry & 0x03FF for entry in entries]
    banks = sorted({entry >> 12 for entry in entries})
    if max(tiles) > 5 or banks != [1]:
        raise ValueError("tilemap entry contract mismatch")
    return {
        "entry_count": 640,
        "tile_index_range": [min(tiles), max(tiles)],
        "palette_banks": banks,
        "horizontal_flip_count": sum(bool(entry & 0x0400) for entry in entries),
        "vertical_flip_count": sum(bool(entry & 0x0800) for entry in entries),
    }


def _validate_layout_regions(
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
    if not isinstance(partitions, list) or not partitions:
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
    if any(
        left[1] > right[0]
        for left, right in zip(normalized, normalized[1:])
    ):
        raise ValueError("ROM layout partitions overlap")
    parent = [
        row
        for row in normalized
        if row[2] == "sequel-image-assets"
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
        raise ValueError("region parent mismatch")
    raw_regions = registry.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("image regions are invalid")
    regions = []
    seen = set()
    for row in raw_regions:
        if not isinstance(row, dict):
            raise ValueError("image region is invalid")
        identifier = str(row.get("id", "")).strip()
        owner = str(row.get("owner", "")).strip()
        start = _integer(row.get("start"), f"{identifier}.start")
        end = _integer(row.get("end"), f"{identifier}.end")
        alignment = _integer(row.get("alignment"), "alignment")
        if (
            not identifier
            or identifier in seen
            or not owner
            or start < 0x800000
            or end <= start
            or end > 0xC00000
            or not _power_of_two(alignment)
            or start % alignment
            or end % alignment
        ):
            raise ValueError("region contract mismatch")
        seen.add(identifier)
        regions.append((start, end, identifier, owner, alignment))
    regions.sort()
    cursor = 0x800000
    for row in regions:
        if row[0] != cursor:
            raise ValueError("image regions have a gap or overlap")
        cursor = row[1]
    if cursor != 0xC00000:
        raise ValueError("image regions do not cover parent")
    target = [
        row for row in regions if row[2] == "residual-text-bg-tilemap"
    ]
    if target != [
        (
            REGION_START,
            REGION_END,
            "residual-text-bg-tilemap",
            "residual_text_bg_tilemap",
            4,
        )
    ]:
        raise ValueError("text-BG region mismatch")


def _source(base: bytes, inventory: dict[str, Any]) -> bytes:
    records = [
        row
        for row in inventory.get("new_records", [])
        if row.get("gba_address") == "0x08349368"
    ]
    if len(records) != 1:
        raise ValueError("source denominator mismatch")
    row = records[0]
    decoded, consumed = _decode_lz77(base, SOURCE_POINTER - ROM_BASE)
    classification = row.get("classification", {})
    compressed = base[
        SOURCE_POINTER - ROM_BASE :
        SOURCE_POINTER - ROM_BASE + row.get("compressed_size", 0)
    ]
    if (
        consumed != 178
        or row.get("compressed_size") != 178
        or _sha256(compressed)
        != "259891ea9126d0d1c2683ecfdd392f22f2a8b926eb6f2bd4ef4b601935b7898b"
        or row.get("decompressed_size") != 1280
        or _sha256(decoded)
        != "0876b9165e63106e30681dd9ca5831d629ba8903a9f0d05fd5cbf8f1088e920c"
        or row.get("aligned_pointer_references") != ["0x0808B464"]
        or row.get("literal_load_users") != ["0x0808B348"]
        or classification.get("kind") != "visual_metadata"
        or classification.get("subtype") != "text_bg_tilemap"
        or classification.get("evidence_type")
        != "static_code_and_payload_shape"
        or classification.get("load_route") != "LZ77UnCompVram_wrapper"
        or classification.get("destination_domain") != "VRAM_screenblock"
        or classification.get("destination_addresses") != ["0x06001000"]
        or classification.get("code_windows")
        != [
            {
                "gba_start": "0x0808B348",
                "sha256": (
                    "92015fd81bfad3066111a9d094a367a29"
                    "d4d7e3b7cfeef7489cb36414611d963"
                ),
                "size": 16,
            }
        ]
        or row.get("nearby_direct_calls")
        != [
            {
                "callsite": "0x0808B34C",
                "known_route": "LZ77UnCompVram_wrapper",
                "target": "0x0809C0E8",
            },
            {
                "callsite": "0x0808B352",
                "known_route": None,
                "target": "0x08067158",
            },
        ]
        or _aligned_offsets(base, SOURCE_POINTER) != [POINTER_OFFSET]
    ):
        raise ValueError("source contract mismatch")
    metadata = _tilemap_metadata(decoded)
    if metadata != {
        "entry_count": 640,
        "tile_index_range": [0, 5],
        "palette_banks": [1],
        "horizontal_flip_count": 0,
        "vertical_flip_count": 12,
    }:
        raise ValueError("source tilemap metadata mismatch")
    if Counter(struct.unpack("<640H", decoded)) != Counter(
        {
            0x1000: 516,
            0x1001: 1,
            0x1002: 10,
            0x1003: 1,
            0x1004: 4,
            0x1005: 96,
            0x1801: 1,
            0x1802: 10,
            0x1803: 1,
        }
    ):
        raise ValueError("source tilemap word histogram mismatch")
    return decoded


def _rebuild(
    base: bytes,
    decoded: bytes,
    *,
    fixture: bool,
) -> tuple[str, dict[str, Any], dict[str, Any], int]:
    raw = bytearray(decoded)
    if fixture:
        entry = struct.unpack_from("<H", raw, 0)[0]
        struct.pack_into("<H", raw, 0, (entry & ~0x03FF) | (((entry & 0x03FF) + 1) % 6))
    data = bytes(raw)
    metadata = _tilemap_metadata(data)
    encoded = _encode_lz77(data)
    check, consumed = _decode_lz77(encoded, 0)
    if check != data or consumed != len(encoded):
        raise ValueError("independent LZ77 round-trip mismatch")
    end = REGION_START + len(encoded)
    if end > REGION_END:
        raise ValueError("independent allocation exceeds region")
    output = bytearray(base + bytes([0xFF]) * (TARGET_ROM_SIZE - len(base)))
    if output[REGION_START:end] != bytes([0xFF]) * len(encoded):
        raise ValueError("independent allocation is not fill")
    output[REGION_START:end] = encoded
    if struct.unpack_from("<I", output, POINTER_OFFSET)[0] != SOURCE_POINTER:
        raise ValueError("independent pointer before-word mismatch")
    new_pointer = ROM_BASE + REGION_START
    struct.pack_into("<I", output, POINTER_OFFSET, new_pointer)
    allocation = {
        "id": "residual-text-bg-tilemap",
        "offset": REGION_START,
        "source_pointer": SOURCE_POINTER,
        "new_pointer": new_pointer,
        "replacement_sha256": _sha256(data),
        "decoded_size": len(data),
        "encoded_size": len(encoded),
        **metadata,
        "destination": "0x06001000",
    }
    pointer_patch = {
        "id": "residual-text-bg-tilemap.pointer-08b464",
        "offset": POINTER_OFFSET,
        "source_pointer": SOURCE_POINTER,
        "new_pointer": new_pointer,
        "pointer_role": "tilemap_source",
    }
    return _sha256(bytes(output)), allocation, pointer_patch, end


def _resolve_asset(root: Path, artifact: Path, value: object) -> Path:
    if value != f"artifacts/{ARTIFACT_ID}/{TILEMAP_NAME}":
        raise ValueError("tilemap_file is invalid")
    return (artifact / TILEMAP_NAME).resolve()


def _verify(root: Path, artifact: Path) -> dict[str, Any]:
    expected_names = {
        "manifest.json",
        PAYLOAD_NAME,
        SPEC_NAME,
        TILEMAP_NAME,
    }
    actual_names = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    }
    if actual_names != expected_names:
        raise ValueError("artifact file set mismatch")
    if any(path.is_symlink() for path in artifact.rglob("*")):
        raise ValueError("artifact contains symbolic links")
    manifest = json.loads((artifact / "manifest.json").read_text())
    if (
        manifest.get("schema") != "git-artifact-promotion-v1"
        or manifest.get("artifact_id") != ARTIFACT_ID
        or manifest.get("artifact_schema") != PAYLOAD_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("payload_file") != PAYLOAD_NAME
    ):
        raise ValueError("manifest contract mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest files mismatch")
    if expected_names != set(files) | {"manifest.json"}:
        raise ValueError("artifact file set mismatch")
    for name, digest in files.items():
        if _sha256((artifact / name).read_bytes()) != digest:
            raise ValueError(f"artifact file hash mismatch: {name}")
    payload_path = artifact / PAYLOAD_NAME
    if manifest.get("payload_sha256") != _sha256(payload_path.read_bytes()):
        raise ValueError("payload hash mismatch")
    payload = json.loads(payload_path.read_text())
    spec_path = artifact / SPEC_NAME
    spec = json.loads(spec_path.read_text())
    if (
        payload.get("schema") != PAYLOAD_SCHEMA
        or payload.get("scope") != SCOPE
        or manifest.get("scope") != SCOPE
        or payload.get("summary") != manifest.get("summary")
        or payload.get("authoring_spec")
        != {"file": SPEC_NAME, "sha256": _sha256(spec_path.read_bytes())}
    ):
        raise ValueError("payload contract mismatch")
    base = (root / "rom/base.gba").read_bytes()
    if len(base) != 0x600000 or _sha256(base) != ROM_SHA256:
        raise ValueError("base ROM mismatch")
    inventory_bytes = (root / INVENTORY_PATH).read_bytes()
    if _sha256(inventory_bytes) != INVENTORY_SHA256:
        raise ValueError("inventory hash mismatch")
    ownership_bytes = (root / OWNERSHIP_PATH).read_bytes()
    if _sha256(ownership_bytes) != OWNERSHIP_SHA256:
        raise ValueError("resource ownership hash mismatch")
    ownership = json.loads(ownership_bytes)
    ownership_record = ownership.get("ownership_record", {})
    if (
        ownership.get("schema")
        != "residual-text-bg-tilemap-resource-ownership-v1"
        or ownership.get("summary", {}).get("tilemap_source_count") != 1
        or ownership.get("summary", {}).get("remaining_unresolved_count") != 0
        or ownership_record.get("tilemap_source_pointer") != "0x08349368"
        or ownership_record.get("vram_destination") != "0x06001000"
        or ownership_record.get("tile_index_range") != [0, 5]
        or ownership_record.get("palette_banks") != [1]
        or ownership_record.get("bg", {}).get("control_value") != "0x0204"
        or ownership_record.get("graphics", {}).get("source_pointer")
        != "0x08348F00"
        or ownership_record.get("graphics", {}).get(
            "loaded_tile_index_range"
        )
        != [0, 67]
        or ownership_record.get("palette", {}).get("source_pointer")
        != "0x0834941C"
        or ownership_record.get("palette", {}).get("bank") != 1
    ):
        raise ValueError("resource ownership contract mismatch")
    layout_bytes = (root / LAYOUT_PATH).read_bytes()
    registry_bytes = (root / REGISTRY_PATH).read_bytes()
    _validate_layout_regions(
        base,
        json.loads(layout_bytes),
        json.loads(registry_bytes),
    )
    metadata = {
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
            "region": "residual-text-bg-tilemap",
            "owner": "residual_text_bg_tilemap",
            "start": REGION_START,
            "end": REGION_END,
        },
        "inventory": {
            "path": INVENTORY_PATH.as_posix(),
            "sha256": INVENTORY_SHA256,
        },
        "resource_ownership": {
            "path": OWNERSHIP_PATH.as_posix(),
            "sha256": OWNERSHIP_SHA256,
            "verified_source_count": 1,
        },
    }
    for key, expected in metadata.items():
        if payload.get(key) != expected:
            raise ValueError(f"payload {key} mismatch")
    implementation = {
        path: _sha256((root / path).read_bytes())
        for path in IMPLEMENTATION_PATHS
    }
    if payload.get("implementation") != implementation:
        raise ValueError("implementation hash mismatch")
    if manifest.get("implementation") != implementation:
        raise ValueError("manifest implementation hash mismatch")
    expected_spec = {
        "schema": "residual-text-bg-tilemap-relocation-v1",
        "base_rom_sha256": ROM_SHA256,
        "inventory": INVENTORY_PATH.as_posix(),
        "inventory_sha256": INVENTORY_SHA256,
        "resource_ownership_artifact": OWNERSHIP_PATH.as_posix(),
        "resource_ownership_sha256": OWNERSHIP_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256(registry_bytes),
        "region": "residual-text-bg-tilemap",
        "region_owner": "residual_text_bg_tilemap",
        "source_pointer": "0x08349368",
    }
    for key, expected in expected_spec.items():
        if spec.get(key) != expected:
            raise ValueError(f"spec {key} mismatch")
    source = _source(base, json.loads(inventory_bytes))
    tilemap_path = _resolve_asset(
        root,
        artifact,
        spec.get("tilemap_file"),
    )
    if tilemap_path.read_bytes() != source:
        raise ValueError("artifact tilemap differs from base ROM")
    output_hash, allocation, pointer_patch, end = _rebuild(
        base,
        source,
        fixture=False,
    )
    fixture_hash, _, _, _ = _rebuild(base, source, fixture=True)
    summary = {
        "source_count": 1,
        "source_pointer_reference_count": 1,
        "unexpected_source_pointer_count": 0,
        "compressed_source_size": 178,
        "decoded_size": 1280,
        "entry_count": 640,
        "tile_index_min": 0,
        "tile_index_max": 5,
        "palette_banks": [1],
        "allocation_count": 1,
        "pointer_patch_count": 1,
        "allocation_start": REGION_START,
        "allocation_end": end,
        "region_end": REGION_END,
        "stored_payload_bytes": end - REGION_START,
        "allocation_span": end - REGION_START,
        "remaining_bytes": REGION_END - end,
        "applied_patch_count": 2,
    }
    if payload.get("summary") != summary:
        raise ValueError("summary is not independently reproducible")
    if payload.get("allocation") != allocation:
        raise ValueError("allocation plan mismatch")
    if payload.get("pointer_patch") != pointer_patch:
        raise ValueError("pointer plan mismatch")
    if payload.get("output_rom_sha256") != output_hash:
        raise ValueError("output ROM hash mismatch")
    if payload.get("capability_fixture") != {
        "mutation": "increment entry 0 tile index modulo 6",
        "changed_entries": 1,
        "output_rom_sha256": fixture_hash,
    }:
        raise ValueError("capability fixture mismatch")
    return {
        "verified_sources": 1,
        "verified_source_pointers": 1,
        "rebuilt_output_rom_sha256": output_hash,
        "capability_fixture_output_rom_sha256": fixture_hash,
    }


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    result = {
        "schema": "residual-text-bg-tilemap-relocation-verification-v1",
        "verified_sources": 0,
        "verified_source_pointers": 0,
        "rebuilt_output_rom_sha256": None,
        "capability_fixture_output_rom_sha256": None,
        "errors": [],
    }
    try:
        result.update(_verify(Path(root).resolve(), Path(artifact).resolve()))
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
