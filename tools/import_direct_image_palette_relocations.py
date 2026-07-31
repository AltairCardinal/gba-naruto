#!/usr/bin/env python3
"""Relocate every strictly proven direct ROM-to-PRAM image palette."""

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
from tools.gba_image_export import encode_gba_lz77
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


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
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")
SPEC_SCHEMA = "direct-image-palette-relocation-v1"
EXPECTED_LZ_POINTERS = {0x080B9F5C, 0x08348668, 0x083F0AC8}
EXPECTED_RAW_LOGICAL_COUNT = 15
EXPECTED_LOGICAL_COUNT = 18
EXPECTED_PHYSICAL_COUNT = 17
EXPECTED_POINTER_COUNT = 29
RANGE_ALIAS_POINTER = 0x08406010
RANGE_ALIAS_PARENT = 0x08405FF0
RANGE_ALIAS_OFFSET = 0x20
OVERLAP_POINTER = 0x084060A8
OVERLAP_OFFSET = OVERLAP_POINTER - RANGE_ALIAS_PARENT
OVERLAP_SIZE = 0x084060F0 - OVERLAP_POINTER


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_pinned(path: Path, expected_hash: str, label: str) -> bytes:
    data = path.read_bytes()
    if _sha256(data) != expected_hash:
        raise ValueError(f"{label} SHA-256 mismatch")
    return data


def _pointer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a GBA ROM pointer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError as error:
            raise ValueError(f"{label} must be a GBA ROM pointer") from error
    else:
        raise ValueError(f"{label} must be a GBA ROM pointer")
    if not ROM_BASE <= result < 0x0A000000:
        raise ValueError(f"{label} must be a mapped GBA ROM pointer")
    return result


def _resolve(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path")
    path = Path(value)
    return path if path.is_absolute() else root / path


def _aligned_pointer_offsets(rom: bytes, pointer: int) -> list[int]:
    needle = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(rom) - 3, 4)
        if rom[offset : offset + 4] == needle
    ]


def _lz77_resources(base: bytes, inventory: dict[str, Any]) -> list[dict[str, Any]]:
    records = [
        row
        for row in inventory.get("new_records", [])
        if isinstance(row, dict)
        and row.get("classification", {}).get("kind") == "palette"
    ]
    pointers = {
        _pointer(row.get("gba_address"), "palette gba_address")
        for row in records
    }
    if (
        inventory.get("classification_counts", {}).get("palette") != 3
        or pointers != EXPECTED_LZ_POINTERS
    ):
        raise ValueError("direct image palette LZ77 denominator mismatch")
    resources = []
    for row in sorted(
        records,
        key=lambda value: _pointer(value.get("gba_address"), "gba_address"),
    ):
        pointer = _pointer(row.get("gba_address"), "gba_address")
        decoded = lz77_decompress(base, pointer - ROM_BASE)
        expected_refs = row.get("aligned_pointer_references")
        if (
            len(decoded) != 32
            or row.get("decompressed_size") != 32
            or row.get("decompressed_sha256") != _sha256(decoded)
            or not isinstance(expected_refs, list)
        ):
            raise ValueError(
                f"direct image LZ77 palette 0x{pointer:08X} contract mismatch"
            )
        expected_offsets = sorted(
            int(value, 16) - ROM_BASE for value in expected_refs
        )
        actual_offsets = _aligned_pointer_offsets(base, pointer)
        if actual_offsets != expected_offsets:
            raise ValueError(
                f"direct image LZ77 palette 0x{pointer:08X} "
                "pointer denominator mismatch"
            )
        classification = row["classification"]
        resources.append(
            {
                "source_pointer": pointer,
                "storage_kind": "lz77",
                "source_size": row["compressed_size"],
                "decoded_size": 32,
                "decoded_sha256": _sha256(decoded),
                "pointer_offsets": actual_offsets,
                "operations": [
                    {
                        "loader": classification["load_route"],
                        "destination_addresses": classification[
                            "destination_addresses"
                        ],
                        "copy_size": 32,
                    }
                ],
                "range_aliases": [],
                "locked_ranges": [],
            }
        )
    return resources


def _raw_resources(
    base: bytes,
    direct_inventory: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    operations = direct_inventory.get("constant_rom_gpu_operations")
    if (
        not isinstance(operations, list)
        or len(operations) != 23
        or direct_inventory.get("summary", {}).get("unique_source_count")
        != EXPECTED_RAW_LOGICAL_COUNT
        or direct_inventory.get("summary", {}).get(
            "constant_rom_gpu_operation_count"
        )
        != 23
    ):
        raise ValueError("direct image raw palette operation denominator mismatch")
    by_pointer: dict[int, list[dict[str, Any]]] = {}
    for operation in operations:
        if (
            not isinstance(operation, dict)
            or operation.get("destination_domain") != "PRAM"
            or operation.get("loader") not in {"CpuSet", "CpuFastSet"}
            or isinstance(operation.get("copy_size"), bool)
            or not isinstance(operation.get("copy_size"), int)
            or operation["copy_size"] <= 0
            or operation["copy_size"] % 2
        ):
            raise ValueError("direct image raw palette operation mismatch")
        pointer = _pointer(operation.get("source_address"), "source_address")
        by_pointer.setdefault(pointer, []).append(operation)
    if len(by_pointer) != EXPECTED_RAW_LOGICAL_COUNT:
        raise ValueError("direct image raw palette source denominator mismatch")
    if (
        RANGE_ALIAS_POINTER not in by_pointer
        or RANGE_ALIAS_PARENT not in by_pointer
    ):
        raise ValueError("direct image raw palette range alias is missing")

    logical_offsets = {
        pointer: _aligned_pointer_offsets(base, pointer)
        for pointer in by_pointer
    }
    if any(not offsets for offsets in logical_offsets.values()):
        raise ValueError("direct image raw palette has no pointer roots")
    physical_pointers = sorted(set(by_pointer) - {RANGE_ALIAS_POINTER})
    resources = []
    raw_size = 0
    for pointer in physical_pointers:
        source_operations = by_pointer[pointer]
        decoded_size = max(row["copy_size"] for row in source_operations)
        if pointer == RANGE_ALIAS_PARENT:
            if decoded_size != 256:
                raise ValueError("direct image parent palette size mismatch")
        elif decoded_size != 32:
            raise ValueError("direct image raw palette size mismatch")
        decoded = base[pointer - ROM_BASE : pointer - ROM_BASE + decoded_size]
        if len(decoded) != decoded_size:
            raise ValueError("direct image raw palette exceeds base ROM")
        aliases = []
        locked = []
        if pointer == RANGE_ALIAS_PARENT:
            alias_end = RANGE_ALIAS_OFFSET + max(
                row["copy_size"] for row in by_pointer[RANGE_ALIAS_POINTER]
            )
            if alias_end > decoded_size:
                raise ValueError("direct image palette alias exceeds parent")
            aliases.append(
                {
                    "source_pointer": RANGE_ALIAS_POINTER,
                    "parent_offset": RANGE_ALIAS_OFFSET,
                    "pointer_offsets": logical_offsets[RANGE_ALIAS_POINTER],
                }
            )
            overlap_operations = [
                row for row in source_operations if row.get("lz77_overlaps")
            ]
            if (
                len(overlap_operations) != 1
                or overlap_operations[0]["lz77_overlaps"]
                != [
                    {
                        "source_address": f"0x{OVERLAP_POINTER:08X}",
                        "compressed_end_address": "0x08406550",
                    }
                ]
            ):
                raise ValueError("direct image palette LZ77 overlap mismatch")
            locked.append(
                {
                    "offset": OVERLAP_OFFSET,
                    "size": OVERLAP_SIZE,
                    "overlap_pointer": OVERLAP_POINTER,
                }
            )
        resources.append(
            {
                "source_pointer": pointer,
                "storage_kind": "raw",
                "source_size": decoded_size,
                "decoded_size": decoded_size,
                "decoded_sha256": _sha256(decoded),
                "pointer_offsets": logical_offsets[pointer],
                "operations": sorted(
                    source_operations,
                    key=lambda row: int(row["callsite"], 16),
                ),
                "range_aliases": aliases,
                "locked_ranges": locked,
            }
        )
        raw_size += decoded_size
    return resources, raw_size


def catalog_direct_image_palettes(
    root: Path,
    rom: bytes | None = None,
) -> dict[str, Any]:
    """Rebuild the exact 18-logical/17-physical/29-root denominator."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("direct image palette base ROM SHA-256 mismatch")
    lz_inventory = json.loads(
        _read_pinned(
            root / LZ_INVENTORY_PATH,
            LZ_INVENTORY_SHA256,
            "direct image palette LZ77 inventory",
        )
    )
    graphics_catalog = json.loads(
        _read_pinned(
            root / GRAPHICS_CATALOG_PATH,
            GRAPHICS_CATALOG_SHA256,
            "direct image palette graphics catalog",
        )
    )
    direct_inventory = json.loads(
        _read_pinned(
            root / DIRECT_INVENTORY_PATH,
            DIRECT_INVENTORY_SHA256,
            "direct image palette CpuSet inventory",
        )
    )
    lz_resources = _lz77_resources(base, lz_inventory)
    raw_resources, raw_size = _raw_resources(base, direct_inventory)
    resources = sorted(
        lz_resources + raw_resources,
        key=lambda row: row["source_pointer"],
    )
    logical_count = len(resources) + sum(
        len(row["range_aliases"]) for row in resources
    )
    pointer_offsets = []
    for row in resources:
        pointer_offsets.extend(row["pointer_offsets"])
        for alias in row["range_aliases"]:
            pointer_offsets.extend(alias["pointer_offsets"])
    if (
        len(resources) != EXPECTED_PHYSICAL_COUNT
        or logical_count != EXPECTED_LOGICAL_COUNT
        or len(pointer_offsets) != EXPECTED_POINTER_COUNT
        or len(set(pointer_offsets)) != EXPECTED_POINTER_COUNT
        or raw_size != 672
        or sum(
            row["decoded_size"]
            for row in resources
            if row["storage_kind"] == "lz77"
        )
        != 96
        or graphics_catalog.get("summary", {}).get(
            "unresolved_palette_count"
        )
        != 2
    ):
        raise ValueError("direct image palette aggregate contract mismatch")
    return {
        "schema": "direct-image-palette-source-catalog-v1",
        "logical_source_count": logical_count,
        "physical_resource_count": len(resources),
        "pointer_reference_count": len(pointer_offsets),
        "lz77_resource_count": len(lz_resources),
        "raw_resource_count": len(raw_resources),
        "lz77_decoded_size": 96,
        "raw_physical_size": raw_size,
        "overlap_locked_size": OVERLAP_SIZE,
        "unresolved_graphics_palette_count": 2,
        "unexpected_pointer_offsets": [],
        "resources": resources,
    }


def resolve_direct_image_palette_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic full-domain palette allocation and redirect plan."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("direct image palette base ROM SHA-256 mismatch")
    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("direct image palette relocation schema mismatch")
    required = {
        "base_rom_sha256": ROM_SHA256,
        "lz77_inventory": LZ_INVENTORY_PATH.as_posix(),
        "lz77_inventory_sha256": LZ_INVENTORY_SHA256,
        "graphics_catalog": GRAPHICS_CATALOG_PATH.as_posix(),
        "graphics_catalog_sha256": GRAPHICS_CATALOG_SHA256,
        "direct_inventory": DIRECT_INVENTORY_PATH.as_posix(),
        "direct_inventory_sha256": DIRECT_INVENTORY_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region": "direct-image-palettes",
        "region_owner": "direct_image_palettes",
    }
    for key, expected in required.items():
        if spec.get(key) != expected:
            raise ValueError(f"direct image palette relocation {key} mismatch")
    registry_path = root / REGION_REGISTRY_PATH
    if spec.get("region_registry_sha256") != _sha256(
        registry_path.read_bytes()
    ):
        raise ValueError("direct image palette registry SHA-256 mismatch")
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    partition = layout.allocation_partition(
        "sequel-image-assets",
        "sequel_image_assets",
        0x800000,
        0xC00000,
    )
    region = regions.require(
        "direct-image-palettes",
        "direct_image_palettes",
    )
    source_catalog = catalog_direct_image_palettes(root, base)
    source_by_pointer = {
        row["source_pointer"]: row for row in source_catalog["resources"]
    }
    raw_resources = spec.get("resources")
    if not isinstance(raw_resources, list) or len(raw_resources) != len(
        source_by_pointer
    ):
        raise ValueError(
            "direct image palette relocation resource denominator mismatch"
        )

    replacements: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(raw_resources):
        if not isinstance(item, dict):
            raise ValueError(f"direct image palette resource {index} is invalid")
        source_pointer = _pointer(
            item.get("source_pointer"),
            f"resources[{index}].source_pointer",
        )
        source = source_by_pointer.get(source_pointer)
        if source is None or source_pointer in replacements:
            raise ValueError(
                "direct image palette resource IDs must be exact and unique"
            )
        palette_path = _resolve(
            root,
            item.get("palette_file"),
            f"resources[{index}].palette_file",
        )
        decoded = palette_path.read_bytes()
        if len(decoded) != source["decoded_size"] or len(decoded) % 2:
            raise ValueError(
                f"direct image palette 0x{source_pointer:08X} "
                "must preserve its complete BGR555 span"
            )
        source_decoded = (
            lz77_decompress(base, source_pointer - ROM_BASE)
            if source["storage_kind"] == "lz77"
            else base[
                source_pointer - ROM_BASE :
                source_pointer - ROM_BASE + source["decoded_size"]
            ]
        )
        for locked in source["locked_ranges"]:
            start = locked["offset"]
            end = start + locked["size"]
            if decoded[start:end] != source_decoded[start:end]:
                raise ValueError(
                    f"direct image palette 0x{source_pointer:08X} "
                    "changes its cross-domain overlap-locked bytes"
                )
        encoded = (
            encode_gba_lz77(decoded)
            if source["storage_kind"] == "lz77"
            else decoded
        )
        if (
            source["storage_kind"] == "lz77"
            and lz77_decompress(encoded, 0) != decoded
        ):
            raise ValueError(
                f"direct image palette 0x{source_pointer:08X} "
                "LZ77 round-trip mismatch"
            )
        replacements[source_pointer] = {
            "source": source,
            "source_file": str(palette_path),
            "decoded": decoded,
            "encoded": encoded,
            "replacement_sha256": _sha256(decoded),
        }
    if set(replacements) != set(source_by_pointer):
        raise ValueError("direct image palette relocation resource set mismatch")

    cursor = region.start
    allocations: list[dict[str, Any]] = []
    redirects: list[dict[str, Any]] = []
    for index, source_pointer in enumerate(sorted(replacements)):
        item = replacements[source_pointer]
        source = item["source"]
        cursor = (cursor + region.alignment - 1) & ~(region.alignment - 1)
        encoded = item["encoded"]
        end = cursor + len(encoded)
        if end > region.end:
            raise ValueError(
                "direct image palette relocation exceeds its registered region"
            )
        new_pointer = ROM_BASE + cursor
        allocation_id = f"direct-image-palette-{index:02d}"
        logical_sources = [source_pointer] + [
            row["source_pointer"] for row in source["range_aliases"]
        ]
        allocations.append(
            {
                "id": allocation_id,
                "type": "bytes",
                "asset_type": "direct_image_palette_relocation",
                "resource_type": "palette",
                "storage_kind": source["storage_kind"],
                "source_pointer": source_pointer,
                "logical_source_pointers": logical_sources,
                "new_pointer": new_pointer,
                "replacement_sha256": item["replacement_sha256"],
                "decoded_size": len(item["decoded"]),
                "encoded_size": len(encoded),
                "color_count": len(item["decoded"]) // 2,
                "pointer_offsets": source["pointer_offsets"],
                "range_aliases": source["range_aliases"],
                "locked_ranges": source["locked_ranges"],
                "offset": cursor,
                "before_hex": bytes([layout.fill_byte] * len(encoded)).hex(),
                "after_hex": encoded.hex(),
                "allocation": {
                    "partition": partition.id,
                    "owner": partition.owner,
                    "region": region.id,
                    "region_owner": region.owner,
                },
                "source_file": item["source_file"],
            }
        )
        redirect_groups = [
            {
                "source_pointer": source_pointer,
                "new_pointer": new_pointer,
                "pointer_offsets": source["pointer_offsets"],
                "alias_offset": 0,
            }
        ] + [
            {
                "source_pointer": alias["source_pointer"],
                "new_pointer": new_pointer + alias["parent_offset"],
                "pointer_offsets": alias["pointer_offsets"],
                "alias_offset": alias["parent_offset"],
            }
            for alias in source["range_aliases"]
        ]
        for group in redirect_groups:
            for pointer_offset in group["pointer_offsets"]:
                redirects.append(
                    {
                        "id": (
                            f"{allocation_id}.pointer-{pointer_offset:06x}"
                        ),
                        "type": "bytes",
                        "asset_type": "direct_image_palette_pointer",
                        "resource_type": "palette",
                        "source_pointer": group["source_pointer"],
                        "new_pointer": group["new_pointer"],
                        "pointer_role": "palette_source",
                        "alias_offset": group["alias_offset"],
                        "offset": pointer_offset,
                        "before_hex": struct.pack(
                            "<I", group["source_pointer"]
                        ).hex(),
                        "after_hex": struct.pack(
                            "<I", group["new_pointer"]
                        ).hex(),
                    }
                )
        cursor = end
    if len(allocations) != EXPECTED_PHYSICAL_COUNT or len(
        redirects
    ) != EXPECTED_POINTER_COUNT:
        raise ValueError("direct image palette patch denominator mismatch")
    return allocations + sorted(redirects, key=lambda row: row["offset"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_direct_image_palette_relocation_patches(
        args.root,
        args.spec,
    )
    payload = {
        "schema": "direct-image-palette-relocation-patches-v1",
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
