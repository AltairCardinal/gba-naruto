#!/usr/bin/env python3
"""Relocate editable battle-map resources into their registered image region."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77, read_lz77_record
from tools.image_resource_regions import ImageResourceRegions
from tools.import_map_resources import (
    CATALOG_PATH,
    CATALOG_SHA256,
    ROLE_POINTER_OFFSETS,
    ROM_SHA256,
    _catalog_resources,
    _validate_resource_payload,
)
from tools.rom_layout import RomLayout


ROM_BASE = 0x08000000
SPEC_SCHEMA = "map-resource-relocation-v1"
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _canonical_offsets(
    value: object,
    *,
    allowed: list[int],
    label: str,
) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise ValueError(f"{label} must be a non-empty integer array")
    if value != sorted(set(value)) or not set(value).issubset(allowed):
        raise ValueError(f"{label} must be a canonical catalog subset")
    return value


def catalog_map_resource_relocations(
    root: Path,
    rom: bytes,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Return all deduplicated map contents and exact aligned pointer users."""
    root = root.resolve()
    if len(rom) != 0x600000 or _sha256(rom) != ROM_SHA256:
        raise ValueError("map relocation base ROM identity mismatch")
    catalog_bytes = (root / CATALOG_PATH).read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("map relocation catalog SHA-256 mismatch")
    catalog = json.loads(catalog_bytes)
    grouped = _catalog_resources(root, catalog, rom)

    physical_to_expected: dict[int, set[int]] = {}
    for resource in grouped.values():
        for offset in resource["physical_offsets"]:
            physical_to_expected[offset] = set()
        for alias in resource["logical_aliases"]:
            physical_to_expected[alias["physical_offset"]].add(
                alias["header_pointer_offset"]
            )
    physical_to_actual = {offset: set() for offset in physical_to_expected}
    pointer_to_offset = {
        ROM_BASE + offset: offset for offset in physical_to_expected
    }
    for pointer_offset in range(0, len(rom) - 3, 4):
        pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
        source_offset = pointer_to_offset.get(pointer)
        if source_offset is not None:
            physical_to_actual[source_offset].add(pointer_offset)

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for key, resource in grouped.items():
        contents = [
            lz77_decompress(rom, offset)
            for offset in resource["physical_offsets"]
        ]
        if any(
            len(content) != resource["decompressed_size"]
            or _sha256(content) != resource["resource_sha256"]
            for content in contents
        ):
            raise ValueError("map relocation physical content mismatch")
        unexpected = sorted(
            {
                pointer_offset
                for offset in resource["physical_offsets"]
                for pointer_offset in (
                    physical_to_actual[offset] - physical_to_expected[offset]
                )
            }
        )
        missing = sorted(
            {
                pointer_offset
                for offset in resource["physical_offsets"]
                for pointer_offset in (
                    physical_to_expected[offset] - physical_to_actual[offset]
                )
            }
        )
        if missing:
            raise ValueError("map relocation expected header pointer is missing")
        result[key] = {
            "resource_type": resource["resource_type"],
            "source_sha256": resource["resource_sha256"],
            "source_size": resource["decompressed_size"],
            "source_file": resource["source_file"],
            "physical_offsets": resource["physical_offsets"],
            "source_pointers": [
                f"0x{ROM_BASE + offset:08X}"
                for offset in resource["physical_offsets"]
            ],
            "logical_aliases": resource["logical_aliases"],
            "source_content": contents[0],
            "unexpected_pointer_offsets": unexpected,
        }
    if (
        len(result) != 166
        or sum(len(row["physical_offsets"]) for row in result.values()) != 217
        or sum(len(row["logical_aliases"]) for row in result.values()) != 249
        or any(row["unexpected_pointer_offsets"] for row in result.values())
    ):
        raise ValueError("map relocation exact denominator mismatch")
    return dict(
        sorted(
            result.items(),
            key=lambda item: (
                min(item[1]["physical_offsets"]),
                item[0][0],
                item[0][1],
            ),
        )
    )


def _validate_linked_map_views(
    catalog: dict[str, Any],
    rom: bytes,
    replacements: dict[int, bytes],
) -> None:
    def content(
        role: str,
        source: dict[str, Any],
        header_pointer_offset: int,
    ) -> bytes:
        value = replacements.get(header_pointer_offset)
        if value is not None:
            return value
        return lz77_decompress(rom, int(source["file_offset"]))

    for entry in catalog["entries"]:
        map_id = int(entry["map_id"])
        header_offset = int(entry["header"]["file_offset"])
        width_tiles, height_tiles = (
            int(value) for value in entry["dimensions_tiles"]
        )
        coarse_width = width_tiles // 4
        coarse_height = height_tiles // 2
        sources = entry["resources"]

        def linked(role: str) -> bytes:
            return content(
                role,
                sources[role],
                header_offset + ROLE_POINTER_OFFSETS[role],
            )

        graphics = linked("tile_graphics")
        palette = linked("bg_palette")
        metatiles = linked("metatile_definitions")
        collision = linked("collision_grid")
        layouts = {"primary_layout": linked("primary_layout")}
        if sources["alternate_layout"] is not None:
            layouts["alternate_layout"] = linked("alternate_layout")
        for role, value in (
            ("tile_graphics", graphics),
            ("bg_palette", palette),
            ("metatile_definitions", metatiles),
            ("collision_grid", collision),
            *layouts.items(),
        ):
            _validate_resource_payload(role, value)

        expected_layout_size = coarse_width * coarse_height * 4
        expected_collision_size = coarse_width * coarse_height * 2
        if len(collision) != expected_collision_size:
            raise ValueError(f"map {map_id} collision grid size mismatch")
        metatile_count = len(metatiles) // 8
        tile_count = len(graphics) // 32
        palette_bank_count = len(palette) // 32
        for role, layout in layouts.items():
            if len(layout) != expected_layout_size:
                raise ValueError(f"map {map_id} {role} size mismatch")
            for offset in range(0, len(layout), 4):
                packed = int.from_bytes(layout[offset : offset + 4], "little")
                for metatile_index in (packed & 0xFFFF, packed >> 16):
                    if metatile_index >= metatile_count:
                        raise ValueError(
                            f"map {map_id} {role} metatile index exceeds "
                            f"{metatile_count}"
                        )
        for offset in range(0, len(metatiles), 2):
            value = int.from_bytes(metatiles[offset : offset + 2], "little")
            tile_index = value & 0x03FF
            palette_bank = (value >> 12) & 0x0F
            if tile_index >= tile_count:
                raise ValueError(
                    f"map {map_id} metatile tile index {tile_index} "
                    f"exceeds {tile_count}"
                )
            if palette_bank >= palette_bank_count:
                raise ValueError(
                    f"map {map_id} metatile palette bank {palette_bank} "
                    f"exceeds {palette_bank_count}"
                )


def _replacement_content(
    root: Path,
    edit: dict[str, Any],
    resource: dict[str, Any],
) -> bytes:
    source = edit.get("content_file")
    if source is None:
        content = resource["source_content"]
    elif isinstance(source, str) and source:
        content = _resolve_path(root, source).read_bytes()
    else:
        raise ValueError("map relocation content_file must be a path")
    expected = edit.get("content_sha256")
    if expected is not None and expected != _sha256(content):
        raise ValueError("map relocation replacement SHA-256 mismatch")
    _validate_resource_payload(resource["resource_type"], content)
    return content


def resolve_map_resource_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    root = root.resolve()
    spec = _json(_resolve_path(root, str(spec_path)))
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    base = rom if rom is not None else (root / "rom/base.gba").read_bytes()
    if spec.get("base_rom_sha256") != _sha256(base):
        raise ValueError("map relocation base ROM SHA-256 mismatch")
    if spec.get("source_catalog") != CATALOG_PATH.as_posix():
        raise ValueError("map relocation source catalog path mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if spec.get("source_catalog_sha256") != _sha256(catalog_bytes):
        raise ValueError("map relocation source catalog SHA-256 mismatch")
    catalog = json.loads(catalog_bytes)
    resources = catalog_map_resource_relocations(root, base)

    layout = layout or RomLayout.from_path(
        root / "sequel/rom-layout.json",
        base,
    )
    try:
        partition = next(
            row
            for row in layout.partitions
            if row.id == spec.get("partition")
        )
    except StopIteration as error:
        raise ValueError("map relocation parent partition is missing") from error
    if (
        partition.id != "sequel-image-assets"
        or partition.owner != "sequel_image_assets"
        or spec.get("owner") != partition.owner
        or partition.origin != "expanded_ff"
    ):
        raise ValueError("map relocation parent partition contract mismatch")
    if spec.get("region_registry") != REGION_REGISTRY_PATH.as_posix():
        raise ValueError("map relocation region registry path mismatch")
    registry_path = root / REGION_REGISTRY_PATH
    registry_bytes = registry_path.read_bytes()
    if spec.get("region_registry_sha256") != _sha256(registry_bytes):
        raise ValueError("map relocation region registry SHA-256 mismatch")
    regions = regions or ImageResourceRegions.from_path(registry_path, layout)
    if regions.parent != partition:
        raise ValueError("map relocation region parent mismatch")
    region = regions.require(
        str(spec.get("region")),
        str(spec.get("region_owner")),
    )
    if region.id != "map-resources" or region.owner != "map_resources":
        raise ValueError("map relocation region contract mismatch")

    edits = spec.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("map relocation edits must be a non-empty array")
    plans: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_resources: set[tuple[str, str]] = set()
    claimed_headers: set[int] = set()
    replacements: dict[int, bytes] = {}
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("map relocation edit must be an object")
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id or edit_id in seen_ids:
            raise ValueError("map relocation edit IDs must be unique")
        seen_ids.add(edit_id)
        key = (edit.get("resource_type"), edit.get("source_sha256"))
        resource = resources.get(key)
        if resource is None or key in seen_resources:
            raise ValueError("unknown or duplicate map relocation resource")
        seen_resources.add(key)
        if edit.get("expected_physical_offsets") != resource["physical_offsets"]:
            raise ValueError("map relocation physical offset contract mismatch")
        expected_headers = [
            row["header_pointer_offset"]
            for row in resource["logical_aliases"]
        ]
        if edit.get("expected_header_pointer_offsets") != expected_headers:
            raise ValueError("map relocation header pointer contract mismatch")
        target_headers = _canonical_offsets(
            edit.get(
                "target_header_pointer_offsets",
                expected_headers,
            ),
            allowed=expected_headers,
            label="target_header_pointer_offsets",
        )
        overlap = claimed_headers.intersection(target_headers)
        if overlap:
            raise ValueError("map relocation header pointer edited twice")
        claimed_headers.update(target_headers)
        content = _replacement_content(root, edit, resource)
        for header_offset in target_headers:
            replacements[header_offset] = content
        plans.append(
            {
                "id": edit_id,
                "resource": resource,
                "content": content,
                "encoded": encode_gba_lz77(content),
                "target_headers": target_headers,
                "content_file": edit.get("content_file"),
            }
        )

    _validate_linked_map_views(catalog, base, replacements)
    plans.sort(
        key=lambda plan: (
            min(plan["resource"]["physical_offsets"]),
            plan["resource"]["resource_type"],
            plan["resource"]["source_sha256"],
        )
    )
    cursor = region.start
    patches: list[dict[str, Any]] = []
    for plan in plans:
        cursor = (cursor + region.alignment - 1) & ~(region.alignment - 1)
        encoded = plan["encoded"]
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError(
                "map relocation region capacity exceeded: "
                f"need 0x{end:X}, end is 0x{region.end:X}"
            )
        resource = plan["resource"]
        new_pointer = ROM_BASE + cursor
        aliases = [
            alias
            for alias in resource["logical_aliases"]
            if alias["header_pointer_offset"] in plan["target_headers"]
        ]
        common = {
            "resource_type": resource["resource_type"],
            "source_sha256": resource["source_sha256"],
            "replacement_sha256": _sha256(plan["content"]),
            "source_size": resource["source_size"],
            "replacement_size": len(plan["content"]),
            "physical_offsets": resource["physical_offsets"],
            "source_pointers": resource["source_pointers"],
            "new_pointer": f"0x{new_pointer:08X}",
            "logical_aliases": aliases,
            "all_header_pointer_offsets": [
                alias["header_pointer_offset"]
                for alias in resource["logical_aliases"]
            ],
            "target_header_pointer_offsets": plan["target_headers"],
            "content_file": plan["content_file"],
        }
        patches.append(
            {
                "id": f"{plan['id']}-allocation",
                "type": "bytes",
                "offset": cursor,
                "before_hex": bytes(
                    [layout.fill_byte] * len(encoded)
                ).hex(),
                "after_hex": encoded.hex(),
                "asset_type": "map_resource_relocation",
                "allocation": {
                    "partition": partition.id,
                    "owner": partition.owner,
                    "region": region.id,
                    "region_owner": region.owner,
                },
                **common,
            }
        )
        after_pointer = struct.pack("<I", new_pointer).hex()
        for alias in aliases:
            pointer_offset = alias["header_pointer_offset"]
            expected_pointer = ROM_BASE + alias["physical_offset"]
            if struct.unpack_from("<I", base, pointer_offset)[0] != expected_pointer:
                raise ValueError("map relocation header pointer precondition mismatch")
            patches.append(
                {
                    "id": (
                        f"{plan['id']}-pointer-"
                        f"{pointer_offset:06x}"
                    ),
                    "type": "bytes",
                    "offset": pointer_offset,
                    "before_hex": struct.pack("<I", expected_pointer).hex(),
                    "after_hex": after_pointer,
                    "asset_type": "map_resource_relocation_pointer",
                    "map_id": alias["map_id"],
                    **common,
                }
            )
        cursor = end
    return patches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    patches = resolve_map_resource_relocation_patches(args.root, args.spec)
    print(json.dumps(patches, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
