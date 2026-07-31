#!/usr/bin/env python3
"""Relocate the three world-map background resource bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77, read_lz77_record
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SPEC_SCHEMA = "world-map-background-relocation-v1"
CATALOG_PATH = Path("artifacts/world-map-backgrounds-v1/manifest.json")
CATALOG_SHA256 = (
    "b9b879841b7605af80e143a9f2f9bbe2e64754d6390b708033f92cc831bd4dd3"
)
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")
TABLE_OFFSET = 0x5A8014
TABLE_SIZE = 3 * 12
TABLE_SHA256 = (
    "9ccd6d722b87a8bf910fb45072ad682d89b9cf3432979b163f57283902396f35"
)
ROLE_POINTER_DELTAS = {"graphics": 0, "tilemap": 4, "palette": 8}
ROLE_POINTER_FIELDS = {
    "graphics": "graphics_pointer",
    "tilemap": "tilemap_pointer",
    "palette": "palette_pointer",
}
ROLE_FILE_FIELDS = {
    "graphics": "graphics_file",
    "tilemap": "tilemap_file",
    "palette": "palette_file",
}
ROLE_HASH_FIELDS = {
    "graphics": "graphics_sha256",
    "tilemap": "tilemap_sha256",
    "palette": "palette_sha256",
}
FIXED_SIZES = {"tilemap": 1200, "palette": 320}
MAX_GRAPHICS_TILES = 512


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


def _source_payload(
    rom: bytes,
    pointer: int,
    role: str,
) -> tuple[bytes, int, str]:
    offset = pointer - ROM_BASE
    if role == "palette":
        payload = rom[offset : offset + FIXED_SIZES[role]]
        if len(payload) != FIXED_SIZES[role]:
            raise ValueError("world-map palette source is truncated")
        return payload, len(payload), "raw"
    expected = 32768 if role == "graphics" else FIXED_SIZES[role]
    record = read_lz77_record(rom, offset, expected_size=expected)
    payload = lz77_decompress(rom, offset)
    return payload, len(record), "lz77"


def _validate_page_view(
    page_id: int,
    graphics: bytes,
    tilemap: bytes,
    palette: bytes,
) -> None:
    if (
        not graphics
        or len(graphics) % 64
        or len(graphics) > MAX_GRAPHICS_TILES * 64
    ):
        raise ValueError(
            f"world-map page {page_id} graphics must contain 1.."
            f"{MAX_GRAPHICS_TILES} complete 8bpp tiles"
        )
    if max(graphics) >= 160:
        raise ValueError(
            f"world-map page {page_id} graphics palette index exceeds 159"
        )
    if len(tilemap) != FIXED_SIZES["tilemap"]:
        raise ValueError(
            f"world-map page {page_id} tilemap must be 1200 bytes"
        )
    if len(palette) != FIXED_SIZES["palette"]:
        raise ValueError(
            f"world-map page {page_id} palette must be 320 bytes"
        )
    tile_count = len(graphics) // 64
    for index, entry in enumerate(struct.unpack("<600H", tilemap)):
        if entry & 0xF000:
            raise ValueError(
                f"world-map page {page_id} tilemap palette bank is nonzero "
                f"at cell {index}"
            )
        if entry & 0x03FF >= tile_count:
            raise ValueError(
                f"world-map page {page_id} tilemap tile index is out of range "
                f"at cell {index}"
            )


def catalog_world_map_background_relocation_payloads(
    root: Path,
    rom: bytes | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Rebuild 7 content groups, 9 physical payloads and 9 exact refs."""
    root = Path(root).resolve()
    base = (
        (root / "rom/base.gba").read_bytes()
        if rom is None
        else bytes(rom)
    )
    if _sha256(base) != ROM_SHA256:
        raise ValueError("world-map relocation base ROM SHA-256 mismatch")
    catalog_path = root / CATALOG_PATH
    catalog_raw = catalog_path.read_bytes()
    if _sha256(catalog_raw) != CATALOG_SHA256:
        raise ValueError("world-map relocation catalog SHA-256 mismatch")
    catalog = json.loads(catalog_raw)
    if (
        catalog.get("schema") != "world-map-backgrounds-v1"
        or catalog.get("rom", {}).get("sha256") != ROM_SHA256
        or len(catalog.get("pages", [])) != 3
    ):
        raise ValueError("world-map relocation catalog identity mismatch")
    table = base[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if _sha256(table) != TABLE_SHA256:
        raise ValueError("world-map relocation descriptor table mismatch")

    resources: dict[tuple[str, str], dict[str, Any]] = {}
    expected_by_pointer: dict[int, set[int]] = {}
    for page_id, page in enumerate(catalog["pages"]):
        if page.get("page_id") != page_id:
            raise ValueError("world-map relocation page order mismatch")
        background = page.get("background")
        if not isinstance(background, dict):
            raise ValueError("world-map relocation background is missing")
        row_offset = TABLE_OFFSET + page_id * 12
        row_values = struct.unpack_from("<III", base, row_offset)
        page_view: dict[str, bytes] = {}
        for role, pointer in zip(
            ("graphics", "tilemap", "palette"),
            row_values,
        ):
            if background.get(ROLE_POINTER_FIELDS[role]) != f"0x{pointer:08X}":
                raise ValueError("world-map relocation pointer provenance mismatch")
            payload, stored_size, storage_kind = _source_payload(
                base,
                pointer,
                role,
            )
            digest = _sha256(payload)
            if background.get(ROLE_HASH_FIELDS[role]) != digest:
                raise ValueError("world-map relocation content hash mismatch")
            source_file = background.get(ROLE_FILE_FIELDS[role])
            if not isinstance(source_file, str):
                raise ValueError("world-map relocation source file is missing")
            artifact_payload = (
                catalog_path.parent / source_file
            ).read_bytes()
            if artifact_payload != payload:
                raise ValueError("world-map relocation source artifact mismatch")
            pointer_offset = row_offset + ROLE_POINTER_DELTAS[role]
            physical_offset = pointer - ROM_BASE
            alias = {
                "page_id": page_id,
                "resource_type": role,
                "table_pointer_offset": pointer_offset,
                "source_pointer": pointer,
                "physical_offset": physical_offset,
            }
            key = (role, digest)
            resource = resources.setdefault(
                key,
                {
                    "resource_type": role,
                    "resource_sha256": digest,
                    "decompressed_size": len(payload),
                    "storage_kind": storage_kind,
                    "source_files": [],
                    "physical_offsets": [],
                    "pointer_aliases": [],
                },
            )
            if (
                resource["decompressed_size"] != len(payload)
                or resource["storage_kind"] != storage_kind
            ):
                raise ValueError("world-map relocation content identity collision")
            resource["source_files"].append(source_file)
            resource["physical_offsets"].append(physical_offset)
            resource["pointer_aliases"].append(alias)
            resource.setdefault("stored_sizes", []).append(stored_size)
            expected_by_pointer.setdefault(pointer, set()).add(pointer_offset)
            page_view[role] = payload
        _validate_page_view(
            page_id,
            page_view["graphics"],
            page_view["tilemap"],
            page_view["palette"],
        )

    actual_by_pointer = {pointer: set() for pointer in expected_by_pointer}
    for offset in range(0, len(base) - 3, 4):
        value = int.from_bytes(base[offset : offset + 4], "little")
        if value in actual_by_pointer:
            actual_by_pointer[value].add(offset)
    for resource in resources.values():
        resource["source_files"] = sorted(set(resource["source_files"]))
        resource["physical_offsets"] = sorted(set(resource["physical_offsets"]))
        resource["stored_sizes"] = sorted(resource["stored_sizes"])
        resource["pointer_aliases"].sort(
            key=lambda alias: alias["table_pointer_offset"]
        )
        unexpected: set[int] = set()
        for alias in resource["pointer_aliases"]:
            pointer = alias["source_pointer"]
            expected = expected_by_pointer[pointer]
            actual = actual_by_pointer[pointer]
            if expected - actual:
                raise ValueError(
                    "world-map relocation exact pointer reference missing"
                )
            unexpected.update(actual - expected)
        resource["unexpected_pointer_offsets"] = sorted(unexpected)

    if (
        len(resources) != 7
        or sum(len(row["physical_offsets"]) for row in resources.values()) != 9
        or sum(len(row["pointer_aliases"]) for row in resources.values()) != 9
    ):
        raise ValueError("world-map relocation denominator mismatch")
    return resources


def resolve_world_map_background_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic world-map allocation and pointer redirect plan."""
    root = Path(root).resolve()
    spec_path = _resolve_path(
        root,
        str(spec_path),
        "world-map relocation spec",
    )
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"expected schema {SPEC_SCHEMA}")
    base = (
        (root / "rom/base.gba").read_bytes()
        if rom is None
        else bytes(rom)
    )
    if (
        spec.get("base_rom_sha256") != ROM_SHA256
        or _sha256(base) != ROM_SHA256
    ):
        raise ValueError("world-map relocation base ROM mismatch")
    if (
        spec.get("source_catalog") != CATALOG_PATH.as_posix()
        or spec.get("source_catalog_sha256") != CATALOG_SHA256
    ):
        raise ValueError("world-map relocation catalog contract mismatch")

    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    try:
        partition = next(
            row for row in layout.partitions if row.id == spec.get("partition")
        )
    except StopIteration as error:
        raise ValueError("world-map relocation parent partition is missing") from error
    if (
        partition.id != "sequel-image-assets"
        or partition.owner != "sequel_image_assets"
        or spec.get("owner") != partition.owner
    ):
        raise ValueError("world-map relocation parent contract mismatch")
    registry_path = root / REGION_REGISTRY_PATH
    if (
        spec.get("region_registry") != REGION_REGISTRY_PATH.as_posix()
        or spec.get("region_registry_sha256")
        != _sha256(registry_path.read_bytes())
    ):
        raise ValueError("world-map relocation region registry contract mismatch")
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        str(spec.get("region", "")),
        str(spec.get("region_owner", "")),
    )
    if (
        regions.parent != partition
        or region.id != "world-map-backgrounds"
        or region.owner != "world_map_background_resources"
    ):
        raise ValueError("world-map relocation region contract mismatch")

    resources = catalog_world_map_background_relocation_payloads(root, base)
    if any(row["unexpected_pointer_offsets"] for row in resources.values()):
        raise ValueError("world-map relocation has unknown exact references")
    original_by_pointer_offset: dict[int, bytes] = {}
    for resource in resources.values():
        source = (
            root / CATALOG_PATH.parent / resource["source_files"][0]
        ).read_bytes()
        for alias in resource["pointer_aliases"]:
            original_by_pointer_offset[alias["table_pointer_offset"]] = source

    edits = spec.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("world-map relocation edits must be a non-empty array")
    seen_ids: set[str] = set()
    claimed_pointer_offsets: set[int] = set()
    prepared: list[dict[str, Any]] = []
    replacement_by_pointer_offset: dict[int, bytes] = {}
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("world-map relocation edit must be an object")
        edit_id = edit.get("id")
        if not isinstance(edit_id, str) or not edit_id or edit_id in seen_ids:
            raise ValueError("world-map relocation edit ID is invalid")
        seen_ids.add(edit_id)
        key = (edit.get("resource_type"), edit.get("resource_sha256"))
        resource = resources.get(key)
        if resource is None:
            raise ValueError("world-map relocation resource identity is invalid")
        expected = edit.get("expected")
        if not isinstance(expected, dict):
            raise ValueError("world-map relocation expected data is missing")
        all_pointer_offsets = sorted(
            alias["table_pointer_offset"]
            for alias in resource["pointer_aliases"]
        )
        if (
            expected.get("decompressed_size")
            != resource["decompressed_size"]
            or expected.get("physical_offsets")
            != resource["physical_offsets"]
            or _canonical_offsets(
                expected.get("pointer_offsets"),
                "expected world-map pointer offsets",
            )
            != all_pointer_offsets
        ):
            raise ValueError("world-map relocation provenance contract mismatch")
        target_pointer_offsets = (
            all_pointer_offsets
            if "target_pointer_offsets" not in edit
            else _canonical_offsets(
                edit["target_pointer_offsets"],
                "target world-map pointer offsets",
            )
        )
        if not set(target_pointer_offsets).issubset(all_pointer_offsets):
            raise ValueError(
                "world-map relocation target pointer offsets are not canonical"
            )
        if claimed_pointer_offsets.intersection(target_pointer_offsets):
            raise ValueError("world-map relocation pointer aliases are claimed twice")
        claimed_pointer_offsets.update(target_pointer_offsets)
        content = _resolve_path(
            root,
            edit.get("source_file"),
            "world-map relocation source file",
        ).read_bytes()
        role = resource["resource_type"]
        if role in FIXED_SIZES and len(content) != FIXED_SIZES[role]:
            raise ValueError(
                f"world-map relocation {role} replacement size mismatch"
            )
        if (
            role == "graphics"
            and (
                not content
                or len(content) % 64
                or len(content) > MAX_GRAPHICS_TILES * 64
            )
        ):
            raise ValueError(
                "world-map relocation graphics must contain 1..512 "
                "complete 8bpp tiles"
            )
        selected_aliases = [
            alias
            for alias in resource["pointer_aliases"]
            if alias["table_pointer_offset"] in target_pointer_offsets
        ]
        if len(selected_aliases) != len(target_pointer_offsets):
            raise ValueError("world-map relocation selected alias mismatch")
        for pointer_offset in target_pointer_offsets:
            replacement_by_pointer_offset[pointer_offset] = content
        encoded = (
            content
            if resource["storage_kind"] == "raw"
            else encode_gba_lz77(content)
        )
        prepared.append(
            {
                "edit_id": edit_id,
                "resource": resource,
                "content": content,
                "encoded": encoded,
                "replacement_sha256": _sha256(content),
                "target_pointer_offsets": target_pointer_offsets,
                "selected_aliases": selected_aliases,
                "source_file": edit["source_file"],
            }
        )

    for page_id in range(3):
        row_offset = TABLE_OFFSET + page_id * 12
        view = {}
        for role, delta in ROLE_POINTER_DELTAS.items():
            pointer_offset = row_offset + delta
            view[role] = replacement_by_pointer_offset.get(
                pointer_offset,
                original_by_pointer_offset[pointer_offset],
            )
        _validate_page_view(
            page_id,
            view["graphics"],
            view["tilemap"],
            view["palette"],
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
            raise AssertionError("world-map relocation replacement hash collision")
        group["edit_ids"].add(item["edit_id"])
        group["target_pointer_offsets"].extend(
            item["target_pointer_offsets"]
        )
        group["selected_aliases"].extend(item["selected_aliases"])

    role_order = {"graphics": 0, "tilemap": 1, "palette": 2}
    cursor = region.start
    allocations: list[dict[str, Any]] = []
    redirects: list[dict[str, Any]] = []
    for index, group in enumerate(
        sorted(
            grouped.values(),
            key=lambda item: (
                role_order[item["resource"]["resource_type"]],
                min(item["target_pointer_offsets"]),
                item["replacement_sha256"],
            ),
        )
    ):
        cursor = (cursor + 3) & ~3
        encoded = group["encoded"]
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError(
                "world-map relocation exceeds its registered region"
            )
        target_pointer_offsets = sorted(group["target_pointer_offsets"])
        if len(target_pointer_offsets) != len(set(target_pointer_offsets)):
            raise ValueError("world-map relocation grouped aliases overlap")
        resource = group["resource"]
        role = resource["resource_type"]
        new_pointer = ROM_BASE + cursor
        allocation_id = f"world-map-{role}-{index:02d}"
        allocations.append(
            {
                "id": allocation_id,
                "type": "bytes",
                "asset_type": "world_map_background_relocation",
                "resource_type": role,
                "resource_sha256": resource["resource_sha256"],
                "replacement_sha256": group["replacement_sha256"],
                "decompressed_size": len(group["content"]),
                "encoded_size": len(encoded),
                "storage_kind": resource["storage_kind"],
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
            key=lambda item: item["table_pointer_offset"],
        ):
            pointer_offset = alias["table_pointer_offset"]
            source_pointer = alias["source_pointer"]
            redirects.append(
                {
                    "id": f"{allocation_id}.pointer-{pointer_offset:06x}",
                    "type": "bytes",
                    "asset_type": "world_map_background_pointer",
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
    patches = resolve_world_map_background_relocation_patches(
        args.root,
        args.spec,
    )
    payload = {
        "schema": "world-map-background-relocation-patches-v1",
        "patches": patches,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
