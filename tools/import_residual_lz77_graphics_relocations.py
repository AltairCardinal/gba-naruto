#!/usr/bin/env python3
"""Relocate all residual aligned-pointer-reachable LZ77 graphics."""

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
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")
SPEC_SCHEMA = "residual-lz77-graphics-relocation-v1"
EXPECTED_RESOURCE_COUNT = 20
EXPECTED_POINTER_COUNT = 34
EXPECTED_DECOMPRESSED_SIZE = 36_640
EXPECTED_COMPRESSED_SIZE = 16_574


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


def catalog_residual_lz77_graphics(
    root: Path,
    rom: bytes | None = None,
) -> dict[str, Any]:
    """Rebuild the exact 20-resource/34-pointer source denominator."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual LZ77 graphics base ROM SHA-256 mismatch")
    inventory = json.loads(
        _read_pinned(
            root / INVENTORY_PATH,
            INVENTORY_SHA256,
            "residual LZ77 source inventory",
        )
    )
    preview_catalog = json.loads(
        _read_pinned(
            root / CATALOG_PATH,
            CATALOG_SHA256,
            "residual LZ77 graphics catalog",
        )
    )
    records = [
        row
        for row in inventory.get("new_records", [])
        if isinstance(row, dict)
        and row.get("classification", {}).get("kind") == "graphics"
    ]
    previews = preview_catalog.get("graphics")
    if (
        inventory.get("classification_counts", {}).get("graphics")
        != EXPECTED_RESOURCE_COUNT
        or len(records) != EXPECTED_RESOURCE_COUNT
        or not isinstance(previews, list)
        or len(previews) != EXPECTED_RESOURCE_COUNT
    ):
        raise ValueError("residual LZ77 graphics denominator mismatch")
    preview_by_pointer = {
        _pointer(row.get("graphics_address"), "graphics_address"): row
        for row in previews
        if isinstance(row, dict)
    }
    if len(preview_by_pointer) != EXPECTED_RESOURCE_COUNT:
        raise ValueError("residual LZ77 graphics preview IDs mismatch")

    resources = []
    total_references = 0
    total_decompressed = 0
    total_compressed = 0
    unresolved_palettes = 0
    unexpected: list[int] = []
    for row in sorted(
        records,
        key=lambda item: _pointer(item.get("gba_address"), "gba_address"),
    ):
        source_pointer = _pointer(row.get("gba_address"), "gba_address")
        preview = preview_by_pointer.get(source_pointer)
        if preview is None:
            raise ValueError(
                f"residual LZ77 graphics 0x{source_pointer:08X} has no preview"
            )
        source_offset = source_pointer - ROM_BASE
        decoded = lz77_decompress(base, source_offset)
        compressed_size = row.get("compressed_size")
        if (
            not decoded
            or len(decoded) % 32
            or row.get("decompressed_size") != len(decoded)
            or preview.get("decompressed_size") != len(decoded)
            or preview.get("decompressed_sha256") != _sha256(decoded)
            or isinstance(compressed_size, bool)
            or not isinstance(compressed_size, int)
            or compressed_size <= 4
        ):
            raise ValueError(
                f"residual LZ77 graphics 0x{source_pointer:08X} payload mismatch"
            )
        expected_offsets = row.get("aligned_pointer_references")
        if (
            not isinstance(expected_offsets, list)
            or not expected_offsets
            or any(not isinstance(value, str) for value in expected_offsets)
        ):
            raise ValueError(
                f"residual LZ77 graphics 0x{source_pointer:08X} references invalid"
            )
        expected = sorted(int(value, 16) - ROM_BASE for value in expected_offsets)
        actual = _aligned_pointer_offsets(base, source_pointer)
        if actual != expected:
            unexpected.extend(sorted(set(actual) - set(expected)))
            raise ValueError(
                f"residual LZ77 graphics 0x{source_pointer:08X} "
                "pointer denominator mismatch"
            )
        binding = preview.get("palette_binding")
        if not isinstance(binding, dict) or not isinstance(
            binding.get("kind"), str
        ):
            raise ValueError(
                f"residual LZ77 graphics 0x{source_pointer:08X} "
                "palette evidence mismatch"
            )
        if binding["kind"] == "unresolved":
            unresolved_palettes += 1
        classification = row.get("classification")
        if not isinstance(classification, dict):
            raise ValueError("residual LZ77 graphics classification mismatch")
        resources.append(
            {
                "source_pointer": source_pointer,
                "source_offset": source_offset,
                "pointer_offsets": actual,
                "decompressed_size": len(decoded),
                "decompressed_sha256": _sha256(decoded),
                "compressed_size": compressed_size,
                "compressed_sha256": row.get("compressed_sha256"),
                "destination_addresses": classification.get(
                    "destination_addresses", []
                ),
                "palette_binding_kind": binding["kind"],
                "palette_source_addresses": binding.get(
                    "source_addresses", []
                ),
            }
        )
        total_references += len(actual)
        total_decompressed += len(decoded)
        total_compressed += compressed_size
    if (
        total_references != EXPECTED_POINTER_COUNT
        or total_decompressed != EXPECTED_DECOMPRESSED_SIZE
        or total_compressed != EXPECTED_COMPRESSED_SIZE
        or unresolved_palettes != 2
    ):
        raise ValueError("residual LZ77 graphics aggregate contract mismatch")
    return {
        "schema": "residual-lz77-graphics-source-catalog-v1",
        "resource_count": len(resources),
        "pointer_reference_count": total_references,
        "decompressed_size": total_decompressed,
        "compressed_size": total_compressed,
        "unresolved_palette_count": unresolved_palettes,
        "unexpected_pointer_offsets": unexpected,
        "resources": resources,
    }


def resolve_residual_lz77_graphics_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic full-domain allocation and pointer-redirection plan."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual LZ77 graphics base ROM SHA-256 mismatch")
    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("residual LZ77 graphics relocation schema mismatch")
    required = {
        "base_rom_sha256": ROM_SHA256,
        "source_inventory": INVENTORY_PATH.as_posix(),
        "source_inventory_sha256": INVENTORY_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region": "residual-lz77-graphics",
        "region_owner": "residual_lz77_graphics",
    }
    for key, expected in required.items():
        if spec.get(key) != expected:
            raise ValueError(
                f"residual LZ77 graphics relocation {key} mismatch"
            )
    registry_path = root / REGION_REGISTRY_PATH
    registry_hash = _sha256(registry_path.read_bytes())
    if spec.get("region_registry_sha256") != registry_hash:
        raise ValueError(
            "residual LZ77 graphics region registry SHA-256 mismatch"
        )
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    partition = layout.allocation_partition(
        "sequel-image-assets",
        "sequel_image_assets",
        0x800000,
        0xC00000,
    )
    region = regions.require(
        "residual-lz77-graphics",
        "residual_lz77_graphics",
    )
    source_catalog = catalog_residual_lz77_graphics(root, base)
    source_by_pointer = {
        row["source_pointer"]: row for row in source_catalog["resources"]
    }

    raw_resources = spec.get("resources")
    if not isinstance(raw_resources, list) or len(raw_resources) != len(
        source_by_pointer
    ):
        raise ValueError(
            "residual LZ77 graphics relocation resource denominator mismatch"
        )
    replacements: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(raw_resources):
        if not isinstance(item, dict):
            raise ValueError(
                f"residual LZ77 graphics resource {index} must be an object"
            )
        source_pointer = _pointer(
            item.get("source_pointer"),
            f"resources[{index}].source_pointer",
        )
        source = source_by_pointer.get(source_pointer)
        if source is None or source_pointer in replacements:
            raise ValueError(
                "residual LZ77 graphics resource IDs must be exact and unique"
            )
        graphics_path = _resolve(
            root,
            item.get("graphics_file"),
            f"resources[{index}].graphics_file",
        )
        decoded = graphics_path.read_bytes()
        if len(decoded) != source["decompressed_size"] or len(decoded) % 32:
            raise ValueError(
                f"residual LZ77 graphics 0x{source_pointer:08X} "
                "must preserve its complete decoded tile span"
            )
        encoded = encode_gba_lz77(decoded)
        if lz77_decompress(encoded, 0) != decoded:
            raise ValueError(
                f"residual LZ77 graphics 0x{source_pointer:08X} "
                "LZ77 round-trip mismatch"
            )
        replacements[source_pointer] = {
            "source": source,
            "source_file": str(graphics_path),
            "decoded": decoded,
            "encoded": encoded,
            "replacement_sha256": _sha256(decoded),
        }
    if set(replacements) != set(source_by_pointer):
        raise ValueError(
            "residual LZ77 graphics relocation resource set mismatch"
        )

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
                "residual LZ77 graphics relocation exceeds its registered region"
            )
        new_pointer = ROM_BASE + cursor
        allocation_id = f"residual-lz77-graphics-{index:02d}"
        allocations.append(
            {
                "id": allocation_id,
                "type": "bytes",
                "asset_type": "residual_lz77_graphics_relocation",
                "resource_type": "graphics",
                "source_pointer": source_pointer,
                "new_pointer": new_pointer,
                "replacement_sha256": item["replacement_sha256"],
                "decompressed_size": len(item["decoded"]),
                "encoded_size": len(encoded),
                "tile_count": len(item["decoded"]) // 32,
                "destination_addresses": source["destination_addresses"],
                "palette_binding_kind": source["palette_binding_kind"],
                "palette_source_addresses": source[
                    "palette_source_addresses"
                ],
                "pointer_offsets": source["pointer_offsets"],
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
        for pointer_offset in source["pointer_offsets"]:
            redirects.append(
                {
                    "id": (
                        f"{allocation_id}.pointer-{pointer_offset:06x}"
                    ),
                    "type": "bytes",
                    "asset_type": "residual_lz77_graphics_pointer",
                    "resource_type": "graphics",
                    "source_pointer": source_pointer,
                    "new_pointer": new_pointer,
                    "pointer_role": "graphics_source",
                    "offset": pointer_offset,
                    "before_hex": struct.pack("<I", source_pointer).hex(),
                    "after_hex": struct.pack("<I", new_pointer).hex(),
                }
            )
        cursor = end
    return allocations + sorted(redirects, key=lambda row: row["offset"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    patches = resolve_residual_lz77_graphics_relocation_patches(
        args.root,
        args.spec,
    )
    payload = {
        "schema": "residual-lz77-graphics-relocation-patches-v1",
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
