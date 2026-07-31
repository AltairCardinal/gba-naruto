#!/usr/bin/env python3
"""Relocate the four residual cropped/transformed WRAM tilemap sources."""

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
ABI_PATH = Path(
    "artifacts/residual-wram-visual-metadata-abi-v2/"
    "residual-wram-visual-metadata-abi.json"
)
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
SPEC_SCHEMA = "residual-wram-derived-tilemap-relocation-v1"
REGION_ID = "residual-wram-derived-tilemaps"
REGION_OWNER = "residual_wram_derived_tilemaps"

SOURCE_CONTRACTS = {
    0x083F2108: {
        "compressed_size": 140,
        "compressed_sha256": (
            "be925c87a99654108d5cf2fd2d480b1"
            "0a1ac468650c607772b1f3b223993ac1a"
        ),
        "decoded_size": 800,
        "decoded_sha256": (
            "093f55d5337807bf3692331a2ff55eeb"
            "c4f392cc3190af4c51272b9c36c6d7bc"
        ),
        "pointer_offset": 0x08BD60,
        "classification": "direct_cpu_crop_tilemap",
        "width": 40,
        "height": 10,
        "palette_bank": 10,
        "tile_range": (1, 16),
        "destination": "0x06001100",
    },
    0x084634B8: {
        "compressed_size": 177,
        "compressed_sha256": (
            "b0ee9cb86524e286a9d6d52a0e534825"
            "5f7c114d4bbe4471ac0366ad1eda7e26"
        ),
        "decoded_size": 288,
        "decoded_sha256": (
            "dd3ab008ef8b1f7851c30880db3866ef"
            "23606d754ee3cc5bcb48ad9e5ea1daef"
        ),
        "pointer_offset": 0x090BDC,
        "classification": "transformed_strided_queue_tilemap",
        "width": 12,
        "height": 12,
        "palette_bank": 12,
        "tile_range": (0, 54),
        "destination": "0x06000806",
    },
    0x0846356C: {
        "compressed_size": 105,
        "compressed_sha256": (
            "b0d0a49ac1d30c88dffa715308e910d8"
            "1f9cadd8829330c5a2f3db40f2fe065a"
        ),
        "decoded_size": 288,
        "decoded_sha256": (
            "9761b7fb5e5b2fd50784ff98b352bd24"
            "6b947ab3663e12e52ccefe12206aad32"
        ),
        "pointer_offset": 0x090DDC,
        "classification": "transformed_strided_queue_tilemap",
        "width": 12,
        "height": 12,
        "palette_bank": 13,
        "tile_range": (0, 75),
        "destination": "0x06000806",
    },
    0x084635D8: {
        "compressed_size": 175,
        "compressed_sha256": (
            "8362ef30992001077204e7dcced82f9e"
            "f3a170411fa0cdc2bda1f7573a4b77a9"
        ),
        "decoded_size": 288,
        "decoded_sha256": (
            "e4184823135e047462d356aa95f690e9"
            "4b9104b5e8772d58093efba251d3c640"
        ),
        "pointer_offset": 0x090DE8,
        "classification": "transformed_strided_queue_tilemap",
        "width": 12,
        "height": 12,
        "palette_bank": 13,
        "tile_range": (0, 95),
        "destination": "0x06000806",
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _align(value: int) -> int:
    return (value + 3) & ~3


def _pointer_offsets(rom: bytes, pointer: int) -> list[int]:
    needle = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(rom) - 3, 4)
        if rom[offset : offset + 4] == needle
    ]


def _metadata(data: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    if len(data) != contract["decoded_size"]:
        raise ValueError("derived WRAM tilemap size mismatch")
    count = len(data) // 2
    values = struct.unpack(f"<{count}H", data)
    tiles = [value & 0x03FF for value in values]
    banks = sorted({value >> 12 for value in values})
    minimum, maximum = contract["tile_range"]
    if min(tiles) < minimum or max(tiles) > maximum:
        raise ValueError("derived WRAM tilemap tile index exceeds proven range")
    if banks != [contract["palette_bank"]]:
        raise ValueError("derived WRAM tilemap palette bank mismatch")
    if (
        contract["classification"] == "transformed_strided_queue_tilemap"
        and max(tiles) + 0x02BC > 0x03FF
    ):
        raise ValueError("derived WRAM tilemap transformed tile index overflows")
    return {
        "entry_count": count,
        "tile_index_range": (min(tiles), max(tiles)),
        "palette_banks": banks,
        "horizontal_flip_count": sum(bool(value & 0x0400) for value in values),
        "vertical_flip_count": sum(bool(value & 0x0800) for value in values),
    }


def catalog_residual_wram_derived_tilemaps(
    root: Path,
    rom: bytes | None = None,
) -> list[dict[str, Any]]:
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("derived WRAM tilemap base ROM SHA-256 mismatch")
    abi_bytes = (root / ABI_PATH).read_bytes()
    if _sha256(abi_bytes) != ABI_SHA256:
        raise ValueError("derived WRAM tilemap ABI SHA-256 mismatch")
    abi = json.loads(abi_bytes)
    if (
        abi.get("schema") != "residual-wram-visual-metadata-abi-v2"
        or abi.get("summary", {}).get("wram_visual_metadata_denominator") != 7
        or abi.get("summary", {}).get("remaining_unresolved_count") != 0
        or abi.get("remaining_unresolved") != []
    ):
        raise ValueError("derived WRAM tilemap ABI contract mismatch")
    records = {
        int(row["source_pointer"], 16): row
        for row in abi.get("tilemap_sources", [])
        if isinstance(row, dict)
    }
    if set(SOURCE_CONTRACTS) - set(records):
        raise ValueError("derived WRAM tilemap ABI source set mismatch")

    result = []
    for pointer, contract in SOURCE_CONTRACTS.items():
        record = records[pointer]
        offset = pointer - ROM_BASE
        compressed = base[offset : offset + contract["compressed_size"]]
        decoded = lz77_decompress(base, offset)
        metadata = _metadata(decoded, contract)
        expected_tilemap = {
            "width_entries": contract["width"],
            "height_entries": contract["height"],
            "entry_count": contract["decoded_size"] // 2,
            "entry_size": 2,
            "tile_index_range": list(contract["tile_range"]),
            "palette_banks": [contract["palette_bank"]],
            "horizontal_flip_count": metadata["horizontal_flip_count"],
            "vertical_flip_count": metadata["vertical_flip_count"],
        }
        pointer_offsets = _pointer_offsets(base, pointer)
        if (
            len(compressed) != contract["compressed_size"]
            or _sha256(compressed) != contract["compressed_sha256"]
            or _sha256(decoded) != contract["decoded_sha256"]
            or record.get("compressed_sha256")
            != contract["compressed_sha256"]
            or record.get("decompressed_sha256")
            != contract["decoded_sha256"]
            or record.get("classification") != contract["classification"]
            or record.get("tilemap") != expected_tilemap
            or record.get("vram_destination") != contract["destination"]
            or pointer_offsets != [contract["pointer_offset"]]
        ):
            raise ValueError(
                f"derived WRAM tilemap source contract mismatch: "
                f"0x{pointer:08X}"
            )
        result.append(
            {
                "schema": "residual-wram-derived-tilemap-source-v1",
                "source_pointer": pointer,
                "classification": contract["classification"],
                "compressed_size": len(compressed),
                "compressed_sha256": _sha256(compressed),
                "decoded_size": len(decoded),
                "decoded_sha256": _sha256(decoded),
                "pointer_offsets": pointer_offsets,
                "width_entries": contract["width"],
                "height_entries": contract["height"],
                "allowed_tile_index_range": contract["tile_range"],
                "allowed_palette_bank": contract["palette_bank"],
                "vram_destination": contract["destination"],
                "decoded": decoded,
                **metadata,
            }
        )
    return result


def resolve_residual_wram_derived_tilemap_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("derived WRAM tilemap base ROM SHA-256 mismatch")
    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    required = {
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "abi_artifact": ABI_PATH.as_posix(),
        "abi_sha256": ABI_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region": REGION_ID,
        "region_owner": REGION_OWNER,
    }
    for key, expected in required.items():
        if spec.get(key) != expected:
            raise ValueError(f"derived WRAM tilemap {key} mismatch")
    registry_path = root / REGISTRY_PATH
    if spec.get("region_registry_sha256") != _sha256(
        registry_path.read_bytes()
    ):
        raise ValueError("derived WRAM tilemap registry SHA-256 mismatch")
    rows = spec.get("resources")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("derived WRAM tilemap resources must contain 4 rows")
    resources = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("derived WRAM tilemap resource must be an object")
        try:
            pointer = int(row.get("source_pointer", ""), 16)
        except (TypeError, ValueError) as error:
            raise ValueError("derived WRAM tilemap source pointer invalid") from error
        value = row.get("tilemap_file")
        if (
            pointer in resources
            or pointer not in SOURCE_CONTRACTS
            or not isinstance(value, str)
            or not value
        ):
            raise ValueError("derived WRAM tilemap resource contract mismatch")
        path = Path(value)
        resources[pointer] = path if path.is_absolute() else root / path
    if set(resources) != set(SOURCE_CONTRACTS):
        raise ValueError("derived WRAM tilemap resource denominator mismatch")

    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    partition = layout.allocation_partition(
        "sequel-image-assets",
        "sequel_image_assets",
        0x800000,
        0xC00000,
    )
    region = regions.require(REGION_ID, REGION_OWNER)
    catalog = {
        row["source_pointer"]: row
        for row in catalog_residual_wram_derived_tilemaps(root, base)
    }
    patches = []
    cursor = region.start
    for pointer in sorted(resources):
        source = catalog[pointer]
        contract = SOURCE_CONTRACTS[pointer]
        decoded = resources[pointer].read_bytes()
        metadata = _metadata(decoded, contract)
        encoded = encode_gba_lz77(decoded)
        if lz77_decompress(encoded, 0) != decoded:
            raise ValueError("derived WRAM tilemap LZ77 round-trip mismatch")
        offset = _align(cursor)
        end = offset + len(encoded)
        if end > region.end:
            raise ValueError(
                "derived WRAM tilemap batch exceeds its registered region"
            )
        new_pointer = ROM_BASE + offset
        patches.append(
            {
                "id": f"residual-wram-derived-tilemap-{pointer:08x}",
                "type": "bytes",
                "asset_type": "residual_wram_derived_tilemap_relocation",
                "resource_type": "tilemap",
                "classification": source["classification"],
                "source_pointer": pointer,
                "new_pointer": new_pointer,
                "replacement_sha256": _sha256(decoded),
                "decoded_size": len(decoded),
                "encoded_size": len(encoded),
                "width_entries": source["width_entries"],
                "height_entries": source["height_entries"],
                **metadata,
                "vram_destination": source["vram_destination"],
                "offset": offset,
                "before_hex": bytes([layout.fill_byte] * len(encoded)).hex(),
                "after_hex": encoded.hex(),
                "allocation": {
                    "partition": partition.id,
                    "owner": partition.owner,
                    "region": region.id,
                    "region_owner": region.owner,
                },
                "source_file": str(resources[pointer]),
            }
        )
        for pointer_offset in source["pointer_offsets"]:
            patches.append(
                {
                    "id": (
                        f"residual-wram-derived-tilemap-{pointer:08x}."
                        f"pointer-{pointer_offset:06x}"
                    ),
                    "type": "bytes",
                    "asset_type": "residual_wram_derived_tilemap_pointer",
                    "resource_type": "tilemap",
                    "source_pointer": pointer,
                    "new_pointer": new_pointer,
                    "pointer_role": "tilemap_source",
                    "offset": pointer_offset,
                    "before_hex": struct.pack("<I", pointer).hex(),
                    "after_hex": struct.pack("<I", new_pointer).hex(),
                }
            )
        cursor = end
    return patches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = {
        "schema": "residual-wram-derived-tilemap-relocation-patches-v1",
        "patches": resolve_residual_wram_derived_tilemap_relocation_patches(
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
