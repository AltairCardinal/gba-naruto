#!/usr/bin/env python3
"""Relocate the 24 story BG3 layer resource triples in expanded ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/story-visual-layers-v1/manifest.json")
CATALOG_SHA256 = "556a7319ce57699e2542c578ce0bd1331b93efda58fde1f364271f12f5052fd8"
TABLE_OFFSET = 0x54229C
TABLE_ENTRY_COUNT = 24
TABLE_ENTRY_SIZE = 0x10
ROLE_POINTER_OFFSETS = {"graphics": 0, "palette": 4, "tilemap": 8}
STORY_TILE_BASE = 0x140
MAX_GRAPHICS_SIZE = 0x1800
PALETTE_SIZE = 32
TILEMAP_SIZE = 0x800
SPEC_SCHEMA = "story-visual-resource-relocation-v1"
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_path(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path")
    path = Path(value)
    return path if path.is_absolute() else root / path


def _canonical_offsets(value: object, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise ValueError(f"{label} must be a non-empty integer array")
    offsets = sorted(value)
    if len(offsets) != len(set(offsets)) or any(offset % 4 for offset in offsets):
        raise ValueError(f"{label} must be unique and four-byte aligned")
    return offsets


def _validate_layer_view(
    layer_id: int,
    graphics: bytes,
    palette: bytes,
    tilemap: bytes,
) -> None:
    if not graphics or len(graphics) % 32 or len(graphics) > MAX_GRAPHICS_SIZE:
        raise ValueError(
            f"story visual layer {layer_id} graphics must contain 1..192 "
            "complete 4bpp tiles"
        )
    if len(palette) != PALETTE_SIZE:
        raise ValueError(
            f"story visual layer {layer_id} palette must be {PALETTE_SIZE} bytes"
        )
    if len(tilemap) != TILEMAP_SIZE:
        raise ValueError(
            f"story visual layer {layer_id} tilemap must be {TILEMAP_SIZE} bytes"
        )
    entries = struct.unpack("<1024H", tilemap)
    palette_banks = {entry >> 12 for entry in entries}
    if palette_banks != {15}:
        raise ValueError(
            f"story visual layer {layer_id} must use only palette bank 15"
        )
    tile_count = len(graphics) // 32
    actual_tiles = {entry & 0x03FF for entry in entries}
    expected_tiles = set(range(STORY_TILE_BASE, STORY_TILE_BASE + tile_count))
    if actual_tiles != expected_tiles:
        raise ValueError(
            f"story visual layer {layer_id} tilemap must cover the exact "
            f"contiguous tile range {STORY_TILE_BASE}.."
            f"{STORY_TILE_BASE + tile_count - 1}"
        )


def _load_catalog(root: Path, base: bytes) -> dict[str, Any]:
    if _sha256(base) != ROM_SHA256:
        raise ValueError("story visual relocation base ROM SHA-256 mismatch")
    path = root / CATALOG_PATH
    data = path.read_bytes()
    if _sha256(data) != CATALOG_SHA256:
        raise ValueError("story visual relocation catalog SHA-256 mismatch")
    catalog = json.loads(data)
    if (
        catalog.get("schema") != "story-visual-layer-export-v1"
        or catalog.get("layer_count") != TABLE_ENTRY_COUNT
        or len(catalog.get("layers", [])) != TABLE_ENTRY_COUNT
    ):
        raise ValueError("story visual relocation catalog shape mismatch")
    return catalog


def catalog_story_visual_relocation_payloads(
    root: Path,
    rom: bytes | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Rebuild 49 content groups, 72 physical payloads and 72 exact refs."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    catalog = _load_catalog(root, base)
    resources: dict[tuple[str, str], dict[str, Any]] = {}
    expected_by_pointer: dict[int, set[int]] = {}
    layer_views: dict[int, dict[str, bytes]] = {}

    for layer_id, layer in enumerate(catalog["layers"]):
        descriptor_offset = TABLE_OFFSET + layer_id * TABLE_ENTRY_SIZE
        if (
            layer.get("layer_id") != layer_id
            or layer.get("descriptor_file_offset") != descriptor_offset
        ):
            raise ValueError("story visual relocation layer identity mismatch")
        pointers = struct.unpack_from("<IIII", base, descriptor_offset)
        if pointers[3] != layer.get("config_id"):
            raise ValueError("story visual relocation config identity mismatch")
        view: dict[str, bytes] = {}
        for role, field_offset in ROLE_POINTER_OFFSETS.items():
            pointer = pointers[field_offset // 4]
            physical_offset = pointer - ROM_BASE
            pointer_offset = descriptor_offset + field_offset
            component = layer.get(
                {"graphics": "gfx", "palette": "palette", "tilemap": "tilemap"}[
                    role
                ]
            )
            if (
                not isinstance(component, dict)
                or component.get("file_offset") != physical_offset
            ):
                raise ValueError(
                    "story visual relocation component provenance mismatch"
                )
            content = lz77_decompress(base, physical_offset)
            content_sha256 = _sha256(content)
            if (
                component.get("decompressed_size") != len(content)
                or component.get("decompressed_sha256") != content_sha256
            ):
                raise ValueError(
                    "story visual relocation component content mismatch"
                )
            key = (role, content_sha256)
            resource = resources.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": content_sha256,
                    "decompressed_size": len(content),
                    "content": content,
                    "physical_offsets": [],
                    "compressed_sizes": [],
                    "pointer_aliases": [],
                    "logical_aliases": [],
                },
            )
            if (
                resource["decompressed_size"] != len(content)
                or resource["content"] != content
            ):
                raise ValueError("story visual relocation hash collision")
            alias = {
                "layer_id": layer_id,
                "config_id": layer["config_id"],
                "descriptor_file_offset": descriptor_offset,
                "table_pointer_offset": pointer_offset,
                "physical_offset": physical_offset,
                "source_pointer": pointer,
            }
            resource["physical_offsets"].append(physical_offset)
            resource["compressed_sizes"].append(component["compressed_size"])
            resource["pointer_aliases"].append(alias)
            resource["logical_aliases"].append(alias)
            expected_by_pointer.setdefault(pointer, set()).add(pointer_offset)
            view[role] = content
        _validate_layer_view(
            layer_id,
            view["graphics"],
            view["palette"],
            view["tilemap"],
        )
        layer_views[layer_id] = view

    actual_by_pointer = {pointer: set() for pointer in expected_by_pointer}
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_by_pointer:
            actual_by_pointer[value].add(offset)
    for resource in resources.values():
        unexpected: set[int] = set()
        for alias in resource["pointer_aliases"]:
            pointer = alias["source_pointer"]
            expected = expected_by_pointer[pointer]
            actual = actual_by_pointer[pointer]
            if expected - actual:
                raise ValueError(
                    "story visual relocation exact pointer reference missing"
                )
            unexpected.update(actual - expected)
        resource["physical_offsets"] = sorted(resource["physical_offsets"])
        resource["compressed_sizes"] = sorted(resource["compressed_sizes"])
        resource["pointer_aliases"] = sorted(
            resource["pointer_aliases"],
            key=lambda row: row["table_pointer_offset"],
        )
        resource["logical_aliases"] = list(resource["pointer_aliases"])
        resource["unexpected_pointer_offsets"] = sorted(unexpected)

    type_counts = {
        role: sum(row["resource_type"] == role for row in resources.values())
        for role in ROLE_POINTER_OFFSETS
    }
    if (
        len(resources) != 49
        or type_counts != {"graphics": 24, "palette": 1, "tilemap": 24}
        or sum(len(row["physical_offsets"]) for row in resources.values()) != 72
        or sum(len(row["pointer_aliases"]) for row in resources.values()) != 72
        or len(layer_views) != TABLE_ENTRY_COUNT
    ):
        raise ValueError("story visual relocation denominator mismatch")
    return resources


def resolve_story_visual_resource_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic story-layer payload allocation and pointer plan."""
    root = Path(root).resolve()
    spec_path = _resolve_path(
        root,
        str(spec_path),
        "story visual relocation spec",
    )
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if (
        spec.get("base_rom_sha256") != ROM_SHA256
        or _sha256(base) != ROM_SHA256
    ):
        raise ValueError("story visual relocation base ROM mismatch")
    if (
        spec.get("source_catalog") != CATALOG_PATH.as_posix()
        or spec.get("source_catalog_sha256") != CATALOG_SHA256
    ):
        raise ValueError("story visual relocation catalog contract mismatch")

    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    try:
        partition = next(
            row for row in layout.partitions if row.id == spec.get("partition")
        )
    except StopIteration as error:
        raise ValueError(
            "story visual relocation parent partition is missing"
        ) from error
    if (
        partition.id != "sequel-image-assets"
        or partition.owner != "sequel_image_assets"
        or spec.get("owner") != partition.owner
    ):
        raise ValueError("story visual relocation parent contract mismatch")
    registry_path = root / REGION_REGISTRY_PATH
    if (
        spec.get("region_registry") != REGION_REGISTRY_PATH.as_posix()
        or spec.get("region_registry_sha256")
        != _sha256(registry_path.read_bytes())
    ):
        raise ValueError(
            "story visual relocation region registry contract mismatch"
        )
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        str(spec.get("region", "")),
        str(spec.get("region_owner", "")),
    )
    if (
        regions.parent != partition
        or region.id != "story-visual-layers"
        or region.owner != "story_visual_resources"
    ):
        raise ValueError("story visual relocation region contract mismatch")

    resources = catalog_story_visual_relocation_payloads(root, base)
    if any(
        resource["unexpected_pointer_offsets"]
        for resource in resources.values()
    ):
        raise ValueError("story visual relocation has unknown exact references")
    base_view_by_layer: dict[int, dict[str, bytes]] = {
        layer_id: {} for layer_id in range(TABLE_ENTRY_COUNT)
    }
    for resource in resources.values():
        for alias in resource["pointer_aliases"]:
            base_view_by_layer[alias["layer_id"]][
                resource["resource_type"]
            ] = resource["content"]

    edits = spec.get("edits")
    if not isinstance(edits, list):
        raise ValueError("story visual relocation edits must be an array")
    seen_ids: set[str] = set()
    claimed_pointer_offsets: set[int] = set()
    replacement_by_pointer_offset: dict[int, bytes] = {}
    prepared: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("story visual relocation edit must be an object")
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id or edit_id in seen_ids:
            raise ValueError("story visual relocation edit ID is invalid")
        seen_ids.add(edit_id)
        key = (edit.get("resource_type"), edit.get("resource_sha256"))
        resource = resources.get(key)
        if resource is None:
            raise ValueError("story visual relocation resource identity is invalid")
        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("story visual relocation expected data is missing")
        all_pointer_offsets = sorted(
            alias["table_pointer_offset"]
            for alias in resource["pointer_aliases"]
        )
        if (
            expected.get("decompressed_size") != resource["decompressed_size"]
            or expected.get("physical_offsets") != resource["physical_offsets"]
            or _canonical_offsets(
                expected.get("pointer_offsets"),
                "expected story visual pointer offsets",
            )
            != all_pointer_offsets
        ):
            raise ValueError(
                "story visual relocation provenance contract mismatch"
            )
        target_pointer_offsets = (
            all_pointer_offsets
            if "target_pointer_offsets" not in edit
            else _canonical_offsets(
                edit["target_pointer_offsets"],
                "target story visual pointer offsets",
            )
        )
        if not set(target_pointer_offsets).issubset(all_pointer_offsets):
            raise ValueError(
                "story visual relocation target pointer offsets are not canonical"
            )
        if claimed_pointer_offsets.intersection(target_pointer_offsets):
            raise ValueError(
                "story visual relocation pointer aliases are claimed twice"
            )
        claimed_pointer_offsets.update(target_pointer_offsets)
        content = _resolve_path(
            root,
            edit.get("source_file"),
            "story visual relocation source file",
        ).read_bytes()
        role = resource["resource_type"]
        if role == "graphics":
            if (
                not content
                or len(content) % 32
                or len(content) > MAX_GRAPHICS_SIZE
            ):
                raise ValueError(
                    "story visual relocation graphics must contain 1..192 "
                    "complete 4bpp tiles"
                )
        elif role == "palette":
            if len(content) != PALETTE_SIZE:
                raise ValueError(
                    f"story visual relocation palette must be {PALETTE_SIZE} bytes"
                )
        elif role == "tilemap" and len(content) != TILEMAP_SIZE:
            raise ValueError(
                f"story visual relocation tilemap must be {TILEMAP_SIZE} bytes"
            )
        selected_aliases = [
            alias
            for alias in resource["pointer_aliases"]
            if alias["table_pointer_offset"] in target_pointer_offsets
        ]
        if len(selected_aliases) != len(target_pointer_offsets):
            raise ValueError("story visual relocation selected alias mismatch")
        for pointer_offset in target_pointer_offsets:
            replacement_by_pointer_offset[pointer_offset] = content
        prepared.append(
            {
                "edit_id": edit_id,
                "resource": resource,
                "content": content,
                "encoded": encode_gba_lz77(content),
                "replacement_sha256": _sha256(content),
                "target_pointer_offsets": target_pointer_offsets,
                "selected_aliases": selected_aliases,
                "source_file": edit["source_file"],
            }
        )

    for layer_id, view in base_view_by_layer.items():
        linked = dict(view)
        descriptor_offset = TABLE_OFFSET + layer_id * TABLE_ENTRY_SIZE
        for role, field_offset in ROLE_POINTER_OFFSETS.items():
            linked[role] = replacement_by_pointer_offset.get(
                descriptor_offset + field_offset,
                view[role],
            )
        _validate_layer_view(
            layer_id,
            linked["graphics"],
            linked["palette"],
            linked["tilemap"],
        )

    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in prepared:
        resource = item["resource"]
        key = (
            resource["resource_type"],
            resource["resource_sha256"],
            item["replacement_sha256"],
        )
        group = grouped.setdefault(
            key,
            {
                **item,
                "edit_ids": set(),
                "target_pointer_offsets": [],
                "selected_aliases": [],
            },
        )
        if group["encoded"] != item["encoded"]:
            raise AssertionError("story visual relocation hash collision")
        group["edit_ids"].add(item["edit_id"])
        group["target_pointer_offsets"].extend(
            item["target_pointer_offsets"]
        )
        group["selected_aliases"].extend(item["selected_aliases"])

    type_order = {"graphics": 0, "palette": 1, "tilemap": 2}
    cursor = region.start
    allocations: list[dict[str, Any]] = []
    redirects: list[dict[str, Any]] = []
    for index, group in enumerate(
        sorted(
            grouped.values(),
            key=lambda item: (
                min(item["resource"]["physical_offsets"]),
                type_order[item["resource"]["resource_type"]],
                item["replacement_sha256"],
            ),
        )
    ):
        cursor = (cursor + region.alignment - 1) & -region.alignment
        encoded = group["encoded"]
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError(
                "story visual relocation exceeds its registered region"
            )
        target_pointer_offsets = sorted(group["target_pointer_offsets"])
        if len(target_pointer_offsets) != len(set(target_pointer_offsets)):
            raise ValueError("story visual relocation grouped aliases overlap")
        resource = group["resource"]
        role = resource["resource_type"]
        new_pointer = ROM_BASE + cursor
        allocation_id = f"story-visual-{role}-{index:03d}"
        allocations.append(
            {
                "id": allocation_id,
                "type": "bytes",
                "asset_type": "story_visual_resource_relocation",
                "resource_type": role,
                "resource_sha256": resource["resource_sha256"],
                "replacement_sha256": group["replacement_sha256"],
                "decompressed_size": len(group["content"]),
                "encoded_size": len(encoded),
                "new_pointer": new_pointer,
                "offset": cursor,
                "before_hex": bytes([layout.fill_byte] * len(encoded)).hex(),
                "after_hex": encoded.hex(),
                "allocation": {
                    "partition": partition.id,
                    "owner": partition.owner,
                    "region": region.id,
                    "region_owner": region.owner,
                },
                "physical_offsets": resource["physical_offsets"],
                "all_pointer_offsets": sorted(
                    alias["table_pointer_offset"]
                    for alias in resource["pointer_aliases"]
                ),
                "target_pointer_offsets": target_pointer_offsets,
                "logical_aliases": sorted(
                    group["selected_aliases"],
                    key=lambda alias: alias["table_pointer_offset"],
                ),
                "source_file": group["source_file"],
            }
        )
        for alias in sorted(
            group["selected_aliases"],
            key=lambda row: row["table_pointer_offset"],
        ):
            pointer_offset = alias["table_pointer_offset"]
            source_pointer = alias["source_pointer"]
            redirects.append(
                {
                    "id": f"{allocation_id}.pointer-{pointer_offset:06x}",
                    "type": "bytes",
                    "asset_type": "story_visual_resource_pointer",
                    "resource_type": role,
                    "resource_sha256": resource["resource_sha256"],
                    "source_pointer": source_pointer,
                    "new_pointer": new_pointer,
                    "offset": pointer_offset,
                    "before_hex": source_pointer.to_bytes(4, "little").hex(),
                    "after_hex": new_pointer.to_bytes(4, "little").hex(),
                    "target_pointer_offsets": target_pointer_offsets,
                }
            )
        cursor = end
    return allocations + sorted(redirects, key=lambda patch: patch["offset"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_story_visual_resource_relocation_patches(
        args.root,
        args.spec,
    )
    payload = {
        "schema": "story-visual-resource-relocation-patches-v1",
        "patches": patches,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
