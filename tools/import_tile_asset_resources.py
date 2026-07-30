#!/usr/bin/env python3
"""Relocate editable tile-assets BG resources into the sequel image partition."""

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
from tools.rom_layout import RomLayout


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/tile-assets-bg-v2/manifest.json")
CATALOG_SCHEMA = "tile-assets-bg-export-v2"
SPEC_SCHEMA = "tile-asset-resource-import-v1"
TABLE_OFFSET = 0x5A320C
TABLE_ENTRY_COUNT = 79
TABLE_ENTRY_SIZE = 0x44
TABLE_SHA256 = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
ROLE_WORDS = {
    "A": {"graphics": 3, "tilemap": 4, "palette": 5},
    "B": {"graphics": 6, "tilemap": 7, "palette": 8},
    "C": {"graphics": 10, "tilemap": 11, "palette": 12},
    "D": {"graphics": 14, "tilemap": 15, "palette": 16},
}
EXPECTED_RESOURCE_COUNTS = {
    "graphics": 107,
    "tilemap": 108,
    "palette": 108,
}
SENTINEL_DESCRIPTOR_IDS = {13, 31, 32, 46}


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


def _pointer(value: object) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def _resource_content(
    rom: bytes,
    resource_type: str,
    pointer: int,
    record: dict[str, Any],
) -> tuple[bytes, bytes]:
    offset = pointer - ROM_BASE
    if resource_type in {"graphics", "tilemap"}:
        stored = read_lz77_record(rom, offset)
        content = lz77_decompress(rom, offset)
        if (
            len(stored) != record.get("compressed_size")
            or _sha256(stored) != record.get("compressed_sha256")
            or len(content) != record.get("decompressed_size")
            or _sha256(content) != record.get("decompressed_sha256")
        ):
            raise ValueError(
                f"{resource_type} 0x{pointer:08X} catalog/ROM mismatch"
            )
    else:
        size = record.get("size")
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"palette 0x{pointer:08X} size is invalid")
        content = stored = rom[offset : offset + size]
        if len(content) != size or _sha256(content) != record.get("sha256"):
            raise ValueError(f"palette 0x{pointer:08X} catalog/ROM mismatch")
    return content, stored


def catalog_tile_asset_resources(
    root: Path,
    rom: bytes,
) -> dict[int, dict[str, Any]]:
    """Return all physical payloads and every aligned descriptor reference."""
    root = root.resolve()
    if len(rom) != 0x600000 or _sha256(rom) != ROM_SHA256:
        raise ValueError("tile-assets base ROM identity mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    catalog = json.loads(catalog_bytes)
    if catalog.get("schema") != CATALOG_SCHEMA:
        raise ValueError("tile-assets catalog schema mismatch")
    if catalog.get("rom") != {
        "path": "rom/base.gba",
        "size": len(rom),
        "sha256": ROM_SHA256,
    }:
        raise ValueError("tile-assets catalog ROM provenance mismatch")
    table = catalog.get("source_table")
    if (
        not isinstance(table, dict)
        or table.get("file_offset") != TABLE_OFFSET
        or table.get("entry_count") != TABLE_ENTRY_COUNT
        or table.get("entry_size") != TABLE_ENTRY_SIZE
        or table.get("sha256") != TABLE_SHA256
    ):
        raise ValueError("tile-assets table provenance mismatch")
    table_bytes = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    if _sha256(table_bytes) != TABLE_SHA256:
        raise ValueError("tile-assets table bytes mismatch")
    descriptors = catalog.get("descriptors")
    if not isinstance(descriptors, list) or len(descriptors) != TABLE_ENTRY_COUNT:
        raise ValueError("tile-assets descriptor denominator mismatch")

    resources: dict[int, dict[str, Any]] = {}
    for descriptor_id, descriptor in enumerate(descriptors):
        descriptor_offset = TABLE_OFFSET + descriptor_id * TABLE_ENTRY_SIZE
        if (
            descriptor.get("descriptor_id") != descriptor_id
            or descriptor.get("descriptor_file_offset") != descriptor_offset
        ):
            raise ValueError("tile-assets descriptor identity mismatch")
        raw = table_bytes[
            descriptor_id * TABLE_ENTRY_SIZE :
            (descriptor_id + 1) * TABLE_ENTRY_SIZE
        ]
        words = list(struct.unpack("<17I", raw))
        if descriptor.get("raw_words") != [
            f"0x{word:08X}" for word in words
        ]:
            raise ValueError(
                f"tile-assets descriptor {descriptor_id} raw words mismatch"
            )
        layers = descriptor.get("layers")
        if descriptor_id in SENTINEL_DESCRIPTOR_IDS:
            if any(words) or descriptor.get("status") != "sentinel" or layers:
                raise ValueError(
                    f"tile-assets descriptor {descriptor_id} sentinel mismatch"
                )
            continue
        if not isinstance(layers, list) or len(layers) != 4:
            raise ValueError(
                f"tile-assets descriptor {descriptor_id} layer mismatch"
            )
        for layer in layers:
            name = layer.get("name")
            status = layer.get("status")
            if name not in ROLE_WORDS or status not in {
                "complete",
                "partial",
                "absent",
            }:
                raise ValueError("tile-assets layer identity/status mismatch")
            expected_size = (
                int(layer["definition"]["width_tiles"])
                * int(layer["definition"]["height_tiles"])
                * 2
            )
            for resource_type, word_index in ROLE_WORDS[name].items():
                pointer = words[word_index]
                pointer_text = layer.get(
                    {
                        "graphics": "gfx_pointer",
                        "tilemap": "tilemap_pointer",
                        "palette": "palette_pointer",
                    }[resource_type]
                )
                if bool(pointer) != bool(pointer_text):
                    raise ValueError(
                        f"descriptor {descriptor_id} {name} "
                        f"{resource_type} presence mismatch"
                    )
                if not pointer:
                    continue
                if pointer != _pointer(pointer_text):
                    raise ValueError(
                        f"descriptor {descriptor_id} {name} "
                        f"{resource_type} pointer mismatch"
                    )
                record_key = (
                    "gfx" if resource_type == "graphics" else resource_type
                )
                record = layer.get(record_key)
                if not isinstance(record, dict):
                    raise ValueError("tile-assets resource record is missing")
                content, stored = _resource_content(
                    rom,
                    resource_type,
                    pointer,
                    record,
                )
                digest = _sha256(content)
                pointer_offset = descriptor_offset + word_index * 4
                row = resources.setdefault(
                    pointer,
                    {
                        "resource_type": resource_type,
                        "source_pointer": f"0x{pointer:08X}",
                        "source_offset": pointer - ROM_BASE,
                        "source_sha256": digest,
                        "source_size": len(content),
                        "source_content": content,
                        "source_stored": stored,
                        "storage_kind": (
                            "raw" if resource_type == "palette" else "gba-lz77"
                        ),
                        "bits_per_pixel": set(),
                        "expected_sizes": set(),
                        "logical_aliases": [],
                    },
                )
                if (
                    row["resource_type"] != resource_type
                    or row["source_sha256"] != digest
                    or row["source_content"] != content
                ):
                    raise ValueError(
                        f"tile-assets pointer 0x{pointer:08X} has "
                        "conflicting resource identities"
                    )
                row["bits_per_pixel"].add(int(layer["bits_per_pixel"]))
                if resource_type == "tilemap":
                    row["expected_sizes"].add(expected_size)
                elif resource_type == "palette":
                    row["expected_sizes"].add(
                        int(layer["palette_color_count"]) * 2
                    )
                row["logical_aliases"].append(
                    {
                        "descriptor_id": descriptor_id,
                        "layer": name,
                        "layer_status": status,
                        "resource_type": resource_type,
                        "pointer_offset": pointer_offset,
                        "expected_size": (
                            expected_size
                            if resource_type == "tilemap"
                            else (
                                int(layer["palette_color_count"]) * 2
                                if resource_type == "palette"
                                else len(content)
                            )
                        ),
                    }
                )

    type_counts = {
        kind: sum(row["resource_type"] == kind for row in resources.values())
        for kind in EXPECTED_RESOURCE_COUNTS
    }
    logical_count = sum(
        len(row["logical_aliases"]) for row in resources.values()
    )
    if (
        len(resources) != 323
        or type_counts != EXPECTED_RESOURCE_COUNTS
        or logical_count != 709
    ):
        raise ValueError(
            "tile-assets resource denominator mismatch: "
            f"{len(resources)}/323, {type_counts}, {logical_count}/709"
        )

    pointer_values = set(resources)
    actual_sources: dict[int, set[int]] = {
        pointer: set() for pointer in pointer_values
    }
    for offset in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, offset)[0]
        if value in actual_sources:
            actual_sources[value].add(offset)
    for pointer, row in resources.items():
        row["bits_per_pixel"] = sorted(row["bits_per_pixel"])
        row["expected_sizes"] = sorted(row["expected_sizes"])
        row["logical_aliases"].sort(
            key=lambda item: item["pointer_offset"]
        )
        expected = {
            item["pointer_offset"] for item in row["logical_aliases"]
        }
        actual = actual_sources[pointer]
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        row["missing_pointer_offsets"] = missing
        row["unexpected_pointer_offsets"] = unexpected
        if missing or unexpected:
            raise ValueError(
                f"tile-assets pointer 0x{pointer:08X} reference mismatch: "
                f"missing={missing} unexpected={unexpected}"
            )
    return dict(sorted(resources.items()))


def _replacement_content(
    root: Path,
    edit: dict[str, Any],
    resource: dict[str, Any],
) -> bytes:
    content_file = edit.get("content_file")
    if content_file is None:
        if "content_sha256" in edit:
            raise ValueError("content_sha256 requires content_file")
        return resource["source_content"]
    if not isinstance(content_file, str) or not content_file:
        raise ValueError("content_file must be a non-empty path")
    content = _resolve_path(root, content_file).read_bytes()
    expected = edit.get("content_sha256")
    if expected is not None and expected != _sha256(content):
        raise ValueError("replacement content SHA-256 mismatch")
    return content


def _canonical_offsets(
    value: object,
    *,
    allowed: list[int],
    label: str,
) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, int) for item in value)
        or value != sorted(set(value))
        or not set(value).issubset(allowed)
    ):
        raise ValueError(f"{label} must be a canonical non-empty subset")
    return value


def _validate_all_layers(
    catalog: dict[str, Any],
    resources: dict[int, dict[str, Any]],
    replacements: dict[int, bytes],
) -> None:
    def content(pointer_text: str | None, pointer_offset: int) -> bytes | None:
        if pointer_text is None:
            return None
        pointer = _pointer(pointer_text)
        return replacements.get(pointer_offset, resources[pointer]["source_content"])

    for descriptor in catalog["descriptors"]:
        descriptor_offset = int(descriptor["descriptor_file_offset"])
        for layer in descriptor["layers"]:
            name = layer["name"]
            status = layer["status"]
            words = ROLE_WORDS[name]
            graphics = content(
                layer.get("gfx_pointer"),
                descriptor_offset + words["graphics"] * 4,
            )
            tilemap = content(
                layer.get("tilemap_pointer"),
                descriptor_offset + words["tilemap"] * 4,
            )
            palette = content(
                layer.get("palette_pointer"),
                descriptor_offset + words["palette"] * 4,
            )
            expected_map_size = (
                int(layer["definition"]["width_tiles"])
                * int(layer["definition"]["height_tiles"])
                * 2
            )
            if status == "absent":
                if any(item is not None for item in (graphics, tilemap, palette)):
                    raise ValueError("absent layer gained a resource")
                continue
            if tilemap is None or len(tilemap) != expected_map_size:
                raise ValueError(
                    f"descriptor {descriptor['descriptor_id']} {name} "
                    "tilemap size mismatch"
                )
            if status == "partial":
                if graphics is not None or palette is not None:
                    raise ValueError("partial layer resource contract mismatch")
                continue
            if graphics is None or palette is None:
                raise ValueError("complete layer lost a resource")
            bits_per_pixel = int(layer["bits_per_pixel"])
            bytes_per_tile = bits_per_pixel * 8
            if (
                not graphics
                or len(graphics) % bytes_per_tile
                or len(graphics) // bytes_per_tile > 1024
            ):
                raise ValueError(
                    f"descriptor {descriptor['descriptor_id']} {name} "
                    "graphics tile geometry mismatch"
                )
            expected_palette_size = int(layer["palette_color_count"]) * 2
            if len(palette) != expected_palette_size:
                raise ValueError(
                    f"descriptor {descriptor['descriptor_id']} {name} "
                    "palette size mismatch"
                )
            if (
                bits_per_pixel == 8
                and max(graphics, default=0)
                >= int(layer["palette_color_count"])
            ):
                raise ValueError(
                    f"descriptor {descriptor['descriptor_id']} {name} "
                    "graphics pixel index exceeds palette"
                )
            tile_count = len(graphics) // bytes_per_tile
            for index in range(0, len(tilemap), 2):
                cell = int.from_bytes(tilemap[index : index + 2], "little")
                if cell & 0x03FF >= tile_count:
                    raise ValueError(
                        f"descriptor {descriptor['descriptor_id']} {name} "
                        f"tile index {cell & 0x03FF} exceeds {tile_count}"
                    )
                if cell >> 12:
                    raise ValueError(
                        f"descriptor {descriptor['descriptor_id']} {name} "
                        "uses a non-zero source palette bank"
                    )


def resolve_tile_asset_resource_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
) -> list[dict[str, Any]]:
    root = root.resolve()
    spec_path = _resolve_path(root, str(spec_path))
    spec = _json(spec_path)
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    base = rom if rom is not None else (root / "rom/base.gba").read_bytes()
    if spec.get("base_rom_sha256") != _sha256(base):
        raise ValueError("tile-assets spec base ROM SHA-256 mismatch")
    if spec.get("source_catalog") != CATALOG_PATH.as_posix():
        raise ValueError("tile-assets source catalog path mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_bytes = catalog_path.read_bytes()
    if spec.get("source_catalog_sha256") != _sha256(catalog_bytes):
        raise ValueError("tile-assets source catalog SHA-256 mismatch")
    catalog = json.loads(catalog_bytes)
    resources = catalog_tile_asset_resources(root, base)
    layout = layout or RomLayout.from_path(
        root / "sequel/rom-layout.json",
        base,
    )
    partition_id = spec.get("partition")
    owner = spec.get("owner")
    if partition_id != "sequel-image-assets" or owner != "sequel_image_assets":
        raise ValueError("tile-assets allocation identity mismatch")
    try:
        partition = next(
            row for row in layout.partitions if row.id == partition_id
        )
    except StopIteration as error:
        raise ValueError("tile-assets allocation partition is missing") from error
    if (
        partition.owner != owner
        or partition.origin != "expanded_ff"
        or partition.start < len(base)
    ):
        raise ValueError("tile-assets allocation partition contract mismatch")
    edits = spec.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("tile-assets edits must be a non-empty list")

    plans: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_pointers: set[int] = set()
    claimed_pointer_offsets: set[int] = set()
    replacements: dict[int, bytes] = {}
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("tile-assets edit must be an object")
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id or edit_id in seen_ids:
            raise ValueError("tile-assets edit IDs must be unique")
        seen_ids.add(edit_id)
        pointer = _pointer(edit.get("source_pointer"))
        resource = resources.get(pointer)
        if resource is None:
            raise ValueError(f"unknown tile-assets source pointer 0x{pointer:08X}")
        if pointer in seen_pointers:
            raise ValueError("duplicate tile-assets source pointer")
        seen_pointers.add(pointer)
        if (
            edit.get("resource_type") != resource["resource_type"]
            or edit.get("source_sha256") != resource["source_sha256"]
        ):
            raise ValueError("tile-assets source identity mismatch")
        expected_offsets = [
            row["pointer_offset"] for row in resource["logical_aliases"]
        ]
        if edit.get("expected_pointer_offsets") != expected_offsets:
            raise ValueError("tile-assets pointer offset contract mismatch")
        target_offsets = edit.get(
            "target_pointer_offsets",
            expected_offsets,
        )
        target_offsets = _canonical_offsets(
            target_offsets,
            allowed=expected_offsets,
            label="target_pointer_offsets",
        )
        overlap = claimed_pointer_offsets.intersection(target_offsets)
        if overlap:
            raise ValueError(
                f"tile-assets pointer offsets edited twice: {sorted(overlap)}"
            )
        claimed_pointer_offsets.update(target_offsets)
        content = _replacement_content(root, edit, resource)
        for offset in target_offsets:
            replacements[offset] = content
        encoded = (
            content
            if resource["storage_kind"] == "raw"
            else encode_gba_lz77(content)
        )
        plans.append(
            {
                "id": edit_id,
                "resource": resource,
                "content": content,
                "encoded": encoded,
                "target_offsets": target_offsets,
                "content_file": edit.get("content_file"),
            }
        )

    _validate_all_layers(catalog, resources, replacements)
    plans.sort(key=lambda item: _pointer(item["resource"]["source_pointer"]))
    cursor = partition.start
    patches: list[dict[str, Any]] = []
    for plan in plans:
        cursor = (cursor + 3) & ~3
        encoded = plan["encoded"]
        end = cursor + len(encoded)
        if end > partition.end:
            raise ValueError(
                "tile-assets partition capacity exceeded: "
                f"need 0x{end:X}, end is 0x{partition.end:X}"
            )
        resource = plan["resource"]
        new_pointer = ROM_BASE + cursor
        aliases = [
            row
            for row in resource["logical_aliases"]
            if row["pointer_offset"] in plan["target_offsets"]
        ]
        common = {
            "resource_type": resource["resource_type"],
            "source_pointer": resource["source_pointer"],
            "source_sha256": resource["source_sha256"],
            "replacement_sha256": _sha256(plan["content"]),
            "source_size": resource["source_size"],
            "replacement_size": len(plan["content"]),
            "storage_kind": resource["storage_kind"],
            "new_pointer": f"0x{new_pointer:08X}",
            "logical_aliases": aliases,
            "all_pointer_offsets": [
                row["pointer_offset"] for row in resource["logical_aliases"]
            ],
            "target_pointer_offsets": plan["target_offsets"],
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
                "asset_type": "tile_asset_resource",
                "allocation": {
                    "partition": partition.id,
                    "owner": partition.owner,
                },
                **common,
            }
        )
        before_pointer = struct.pack(
            "<I",
            _pointer(resource["source_pointer"]),
        ).hex()
        after_pointer = struct.pack("<I", new_pointer).hex()
        for alias in aliases:
            patches.append(
                {
                    "id": (
                        f"{plan['id']}-pointer-"
                        f"{alias['pointer_offset']:06x}"
                    ),
                    "type": "bytes",
                    "offset": alias["pointer_offset"],
                    "before_hex": before_pointer,
                    "after_hex": after_pointer,
                    "asset_type": "tile_asset_resource_pointer",
                    "descriptor_id": alias["descriptor_id"],
                    "layer": alias["layer"],
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
    patches = resolve_tile_asset_resource_patches(
        args.root,
        args.spec,
    )
    print(json.dumps(patches, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
