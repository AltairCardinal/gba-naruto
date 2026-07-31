#!/usr/bin/env python3
"""Relocate the single proven residual text-BG tilemap."""

from __future__ import annotations

import argparse
from collections import Counter
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
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
SPEC_SCHEMA = "residual-text-bg-tilemap-relocation-v1"
SOURCE_POINTER = 0x08349368
POINTER_OFFSET = 0x08B464
DECODED_SIZE = 1280
ENTRY_COUNT = 640
MAX_TILE_INDEX = 5
PALETTE_BANK = 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _aligned_pointer_offsets(rom: bytes, pointer: int) -> list[int]:
    needle = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(rom) - 3, 4)
        if rom[offset : offset + 4] == needle
    ]


def _tilemap_metadata(data: bytes) -> dict[str, Any]:
    if len(data) != DECODED_SIZE:
        raise ValueError("residual text-BG tilemap must be exactly 1280 bytes")
    entries = struct.unpack("<640H", data)
    tiles = [entry & 0x03FF for entry in entries]
    banks = sorted({entry >> 12 for entry in entries})
    if max(tiles) > MAX_TILE_INDEX:
        raise ValueError("residual text-BG tilemap tile index exceeds 5")
    if banks != [PALETTE_BANK]:
        raise ValueError("residual text-BG tilemap must use palette bank 1")
    return {
        "entry_count": ENTRY_COUNT,
        "tile_index_range": (min(tiles), max(tiles)),
        "palette_banks": banks,
        "horizontal_flip_count": sum(bool(entry & (1 << 10)) for entry in entries),
        "vertical_flip_count": sum(bool(entry & (1 << 11)) for entry in entries),
    }


def catalog_residual_text_bg_tilemap(
    root: Path,
    rom: bytes | None = None,
) -> dict[str, Any]:
    """Rebuild the exact one-payload/one-root text-BG tilemap catalog."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual text-BG tilemap base ROM SHA-256 mismatch")
    inventory_bytes = (root / INVENTORY_PATH).read_bytes()
    if _sha256(inventory_bytes) != INVENTORY_SHA256:
        raise ValueError("residual text-BG tilemap inventory SHA-256 mismatch")
    inventory = json.loads(inventory_bytes)
    matches = [
        row
        for row in inventory.get("new_records", [])
        if row.get("gba_address") == f"0x{SOURCE_POINTER:08X}"
    ]
    if len(matches) != 1:
        raise ValueError("residual text-BG tilemap source denominator mismatch")
    record = matches[0]
    compressed = base[
        SOURCE_POINTER - ROM_BASE :
        SOURCE_POINTER - ROM_BASE + record.get("compressed_size", 0)
    ]
    decoded = lz77_decompress(base, SOURCE_POINTER - ROM_BASE)
    classification = record.get("classification")
    expected_tilemap = {
        "width_entries": 32,
        "height_entries": 20,
        "entry_count": ENTRY_COUNT,
        "entry_size": 2,
        "tile_index_min": 0,
        "tile_index_max": MAX_TILE_INDEX,
        "palette_banks": [PALETTE_BANK],
        "horizontal_flip_count": 0,
        "vertical_flip_count": 12,
    }
    if (
        record.get("compressed_size") != 178
        or record.get("compressed_sha256")
        != "259891ea9126d0d1c2683ecfdd392f22f2a8b926eb6f2bd4ef4b601935b7898b"
        or _sha256(compressed) != record.get("compressed_sha256")
        or record.get("decompressed_size") != DECODED_SIZE
        or record.get("decompressed_sha256")
        != "0876b9165e63106e30681dd9ca5831d629ba8903a9f0d05fd5cbf8f1088e920c"
        or _sha256(decoded) != record.get("decompressed_sha256")
        or record.get("aligned_pointer_references") != ["0x0808B464"]
        or record.get("literal_load_users") != ["0x0808B348"]
        or not isinstance(classification, dict)
        or classification.get("kind") != "visual_metadata"
        or classification.get("subtype") != "text_bg_tilemap"
        or classification.get("evidence_type")
        != "static_code_and_payload_shape"
        or classification.get("load_route") != "LZ77UnCompVram_wrapper"
        or classification.get("destination_domain") != "VRAM_screenblock"
        or classification.get("destination_addresses") != ["0x06001000"]
        or classification.get("tilemap") != expected_tilemap
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
        or record.get("nearby_direct_calls")
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
    ):
        raise ValueError("residual text-BG tilemap source contract mismatch")
    pointer_offsets = _aligned_pointer_offsets(base, SOURCE_POINTER)
    if pointer_offsets != [POINTER_OFFSET]:
        raise ValueError("residual text-BG tilemap pointer denominator mismatch")
    metadata = _tilemap_metadata(decoded)
    if (
        metadata["tile_index_range"] != (0, MAX_TILE_INDEX)
        or metadata["horizontal_flip_count"] != 0
        or metadata["vertical_flip_count"] != 12
    ):
        raise ValueError("residual text-BG tilemap payload contract mismatch")
    return {
        "schema": "residual-text-bg-tilemap-source-catalog-v1",
        "source_pointer": SOURCE_POINTER,
        "compressed_size": record["compressed_size"],
        "compressed_end_pointer": SOURCE_POINTER + record["compressed_size"],
        "compressed_sha256": record["compressed_sha256"],
        "decoded_size": len(decoded),
        "decoded_sha256": _sha256(decoded),
        "pointer_offsets": pointer_offsets,
        "literal_load_users": [0x0808B348],
        "loader": "LZ77UnCompVram_wrapper",
        "destination": "0x06001000",
        "code_window_sha256": classification["code_windows"][0]["sha256"],
        "decoded": decoded,
        "word_histogram": dict(
            sorted(Counter(struct.unpack("<640H", decoded)).items())
        ),
        **metadata,
    }


def resolve_residual_text_bg_tilemap_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Return one allocation and the single exact source-pointer redirect."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual text-BG tilemap base ROM SHA-256 mismatch")
    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    required = {
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "inventory": INVENTORY_PATH.as_posix(),
        "inventory_sha256": INVENTORY_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region": "residual-text-bg-tilemap",
        "region_owner": "residual_text_bg_tilemap",
        "source_pointer": f"0x{SOURCE_POINTER:08X}",
    }
    for key, expected in required.items():
        if spec.get(key) != expected:
            raise ValueError(f"residual text-BG tilemap {key} mismatch")
    registry_path = root / REGISTRY_PATH
    if spec.get("region_registry_sha256") != _sha256(registry_path.read_bytes()):
        raise ValueError("residual text-BG tilemap registry SHA-256 mismatch")
    tilemap_value = spec.get("tilemap_file")
    if not isinstance(tilemap_value, str) or not tilemap_value:
        raise ValueError("residual text-BG tilemap file path is invalid")
    tilemap_path = Path(tilemap_value)
    if not tilemap_path.is_absolute():
        tilemap_path = root / tilemap_path
    decoded = tilemap_path.read_bytes()
    metadata = _tilemap_metadata(decoded)
    encoded = encode_gba_lz77(decoded)
    if lz77_decompress(encoded, 0) != decoded:
        raise ValueError("residual text-BG tilemap LZ77 round-trip mismatch")
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    partition = layout.allocation_partition(
        "sequel-image-assets",
        "sequel_image_assets",
        0x800000,
        0xC00000,
    )
    region = regions.require(
        "residual-text-bg-tilemap",
        "residual_text_bg_tilemap",
    )
    catalog = catalog_residual_text_bg_tilemap(root, base)
    offset = region.start
    end = offset + len(encoded)
    if end > region.end:
        raise ValueError(
            "residual text-BG tilemap exceeds its registered region"
        )
    new_pointer = ROM_BASE + offset
    allocation = {
        "id": "residual-text-bg-tilemap",
        "type": "bytes",
        "asset_type": "residual_text_bg_tilemap_relocation",
        "resource_type": "tilemap",
        "source_pointer": SOURCE_POINTER,
        "new_pointer": new_pointer,
        "replacement_sha256": _sha256(decoded),
        "decoded_size": len(decoded),
        "encoded_size": len(encoded),
        **metadata,
        "destination": catalog["destination"],
        "offset": offset,
        "before_hex": bytes([layout.fill_byte] * len(encoded)).hex(),
        "after_hex": encoded.hex(),
        "allocation": {
            "partition": partition.id,
            "owner": partition.owner,
            "region": region.id,
            "region_owner": region.owner,
        },
        "source_file": str(tilemap_path),
    }
    redirect = {
        "id": "residual-text-bg-tilemap.pointer-08b464",
        "type": "bytes",
        "asset_type": "residual_text_bg_tilemap_pointer",
        "resource_type": "tilemap",
        "source_pointer": SOURCE_POINTER,
        "new_pointer": new_pointer,
        "pointer_role": "tilemap_source",
        "offset": POINTER_OFFSET,
        "before_hex": struct.pack("<I", SOURCE_POINTER).hex(),
        "after_hex": struct.pack("<I", new_pointer).hex(),
    }
    return [allocation, redirect]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = {
        "schema": "residual-text-bg-tilemap-relocation-patches-v1",
        "patches": resolve_residual_text_bg_tilemap_relocation_patches(
            args.root,
            args.spec,
        ),
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
