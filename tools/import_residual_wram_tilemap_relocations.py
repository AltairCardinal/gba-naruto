#!/usr/bin/env python3
"""Relocate the three code-proven residual WRAM-to-VRAM tilemaps."""

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
    "artifacts/residual-wram-tilemap-abi-v1/"
    "residual-wram-tilemap-abi.json"
)
ABI_SHA256 = "07e1f89b5aaff938184d5d31bea4174e995f96d10b8ffbee56bff0f609a27dfc"
OWNERSHIP_PATH = Path(
    "artifacts/residual-wram-tilemap-resource-ownership-v1/"
    "resource-ownership.json"
)
OWNERSHIP_SHA256 = (
    "1eea02442ad5ad7e717d450433404c3e9cac2fe21214c79be83a37aa90b5ced7"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
SPEC_SCHEMA = "residual-wram-tilemap-relocation-v1"
REGION_ID = "residual-wram-tilemaps"
REGION_OWNER = "residual_wram_tilemaps"

SOURCE_CONTRACTS = {
    0x0834928C: {
        "compressed_size": 217,
        "compressed_sha256": (
            "cb1292f414680f00ebab4509e0d1eaab"
            "0db80c4faf5e9c79da1b694a862e7146"
        ),
        "decoded_size": 600,
        "decoded_sha256": (
            "4396144ffc41de6ee3d0da6383f82569"
            "5bd37aefde1cb2100bd5672200d9140d"
        ),
        "pointer_offset": 0x08AEE0,
        "literal_load_user": "0x0808AD30",
        "queue_call": "0x0808AD46",
        "vram_destination": "0x0600001E",
        "width_entries": 15,
        "height_entries": 20,
        "palette_bank": 1,
        "tile_index_range": (6, 67),
        "horizontal_flip_count": 20,
        "vertical_flip_count": 15,
        "screenblock": {"index": 0, "row": 0, "column": 15},
    },
    0x083F1C98: {
        "compressed_size": 454,
        "compressed_sha256": (
            "39e185414978bea615798e9db6d669053"
            "467063c98acf41754622c20630c3b4d"
        ),
        "decoded_size": 576,
        "decoded_sha256": (
            "8661e87accb82f8d07b4102c70203fe1"
            "9093710d794b0cdde0f1d8ae96db2790"
        ),
        "pointer_offset": 0x08BD38,
        "literal_load_user": "0x0808BBD4",
        "queue_call": "0x0808BBEE",
        "vram_destination": "0x0600F810",
        "width_entries": 24,
        "height_entries": 12,
        "palette_bank": 8,
        "tile_index_range": (0, 267),
        "horizontal_flip_count": 0,
        "vertical_flip_count": 0,
        "screenblock": {"index": 31, "row": 0, "column": 8},
    },
    0x085B67E0: {
        "compressed_size": 150,
        "compressed_sha256": (
            "c257690932ef3f9f181c8408ff1a4f02"
            "f03e4dd6f9312261317dd61c7f427846"
        ),
        "decoded_size": 138,
        "decoded_sha256": (
            "2c841501108a1892a34aa8d877eee414"
            "fe2eed9f0bb0dce1e8700332a7726675"
        ),
        "pointer_offset": 0x08BD48,
        "literal_load_user": "0x0808BBF8",
        "queue_call": "0x0808BC12",
        "vram_destination": "0x0600FC4E",
        "width_entries": 23,
        "height_entries": 3,
        "palette_bank": 9,
        "tile_index_range": (0, 86),
        "horizontal_flip_count": 0,
        "vertical_flip_count": 0,
        "screenblock": {"index": 31, "row": 17, "column": 7},
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _align(value: int, alignment: int = 4) -> int:
    return (value + alignment - 1) & -alignment


def _aligned_pointer_offsets(rom: bytes, pointer: int) -> list[int]:
    needle = struct.pack("<I", pointer)
    return [
        offset
        for offset in range(0, len(rom) - 3, 4)
        if rom[offset : offset + 4] == needle
    ]


def _metadata(data: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    decoded_size = contract["decoded_size"]
    if len(data) != decoded_size:
        raise ValueError(
            f"WRAM tilemap must be exactly {decoded_size} bytes"
        )
    entry_count = decoded_size // 2
    values = struct.unpack(f"<{entry_count}H", data)
    tiles = [value & 0x03FF for value in values]
    banks = sorted({value >> 12 for value in values})
    minimum, maximum = contract["tile_index_range"]
    if min(tiles) < minimum or max(tiles) > maximum:
        raise ValueError("WRAM tilemap tile index exceeds its proven range")
    if banks != [contract["palette_bank"]]:
        raise ValueError("WRAM tilemap palette bank mismatch")
    return {
        "entry_count": entry_count,
        "tile_index_range": (min(tiles), max(tiles)),
        "palette_banks": banks,
        "horizontal_flip_count": sum(
            bool(value & (1 << 10)) for value in values
        ),
        "vertical_flip_count": sum(
            bool(value & (1 << 11)) for value in values
        ),
    }


def _ownership_records(root: Path) -> dict[int, dict[str, Any]]:
    ownership_bytes = (root / OWNERSHIP_PATH).read_bytes()
    if _sha256(ownership_bytes) != OWNERSHIP_SHA256:
        raise ValueError("residual WRAM tilemap ownership SHA-256 mismatch")
    ownership = json.loads(ownership_bytes)
    if (
        ownership.get("schema")
        != "residual-wram-tilemap-resource-ownership-v1"
        or ownership.get("summary", {}).get("tilemap_source_count") != 7
        or ownership.get("summary", {}).get("remaining_unresolved_count") != 0
        or not ownership.get("scope", {}).get(
            "graphics_and_palette_ownership_complete"
        )
    ):
        raise ValueError("residual WRAM tilemap ownership contract mismatch")
    records = ownership.get("ownership_records")
    if not isinstance(records, list) or len(records) != 7:
        raise ValueError("residual WRAM tilemap ownership denominator mismatch")
    return {
        int(record["tilemap_source_pointer"], 16): record
        for record in records
    }


def catalog_residual_wram_tilemaps(
    root: Path,
    rom: bytes | None = None,
) -> list[dict[str, Any]]:
    """Rebuild the exact three-source/three-root migration catalog."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual WRAM tilemap base ROM SHA-256 mismatch")
    abi_bytes = (root / ABI_PATH).read_bytes()
    if _sha256(abi_bytes) != ABI_SHA256:
        raise ValueError("residual WRAM tilemap ABI SHA-256 mismatch")
    abi = json.loads(abi_bytes)
    if (
        abi.get("schema") != "residual-wram-tilemap-abi-v1"
        or abi.get("summary")
        != {
            "wram_visual_metadata_denominator": 7,
            "direct_tilemap_queue_abi_count": 3,
            "remaining_unresolved_count": 4,
            "tilemap_entry_count": 657,
            "tilemap_payload_bytes": 1314,
        }
        or abi.get("remaining_unresolved")
        != ["0x083F2108", "0x084634B8", "0x0846356C", "0x084635D8"]
    ):
        raise ValueError("residual WRAM tilemap ABI contract mismatch")
    records = abi.get("tilemaps")
    if not isinstance(records, list) or len(records) != 3:
        raise ValueError("residual WRAM tilemap ABI denominator mismatch")
    by_pointer = {
        int(record.get("source_pointer", "0"), 16): record
        for record in records
        if isinstance(record, dict)
    }
    if set(by_pointer) != set(SOURCE_CONTRACTS):
        raise ValueError("residual WRAM tilemap source set mismatch")
    ownership = _ownership_records(root)
    if not set(SOURCE_CONTRACTS).issubset(ownership):
        raise ValueError("residual WRAM tilemap ownership source mismatch")

    result = []
    for pointer, contract in SOURCE_CONTRACTS.items():
        record = by_pointer[pointer]
        owner = ownership[pointer]
        source_offset = pointer - ROM_BASE
        compressed = base[
            source_offset : source_offset + contract["compressed_size"]
        ]
        decoded = lz77_decompress(base, source_offset)
        expected_tilemap = {
            "entry_count": contract["decoded_size"] // 2,
            "entry_size": 2,
            "height_entries": contract["height_entries"],
            "horizontal_flip_count": contract["horizontal_flip_count"],
            "palette_banks": [contract["palette_bank"]],
            "tile_index_range": list(contract["tile_index_range"]),
            "vertical_flip_count": contract["vertical_flip_count"],
            "width_entries": contract["width_entries"],
        }
        if (
            record.get("compressed_size") != contract["compressed_size"]
            or record.get("compressed_sha256")
            != contract["compressed_sha256"]
            or _sha256(compressed) != contract["compressed_sha256"]
            or record.get("decompressed_size") != contract["decoded_size"]
            or record.get("decompressed_sha256")
            != contract["decoded_sha256"]
            or _sha256(decoded) != contract["decoded_sha256"]
            or record.get("load_route") != "LZ77UnCompWram_wrapper"
            or record.get("submit_route") != "strided_gpu_copy_queue"
            or record.get("queue_consumer") != "0x0806365C"
            or record.get("queue_call") != contract["queue_call"]
            or record.get("vram_destination")
            != contract["vram_destination"]
            or record.get("tilemap") != expected_tilemap
            or record.get("screenblock") != contract["screenblock"]
        ):
            raise ValueError(
                f"residual WRAM tilemap source contract mismatch: "
                f"0x{pointer:08X}"
            )
        if (
            owner.get("vram_destination")
            != contract["vram_destination"]
            or owner.get("source_tile_index_range")
            != list(contract["tile_index_range"])
            or owner.get("effective_tile_index_range")
            != list(contract["tile_index_range"])
            or owner.get("palettes", [{}])[0].get("bank")
            != contract["palette_bank"]
        ):
            raise ValueError(
                f"residual WRAM tilemap ownership mismatch: "
                f"0x{pointer:08X}"
            )
        pointer_offsets = _aligned_pointer_offsets(base, pointer)
        if pointer_offsets != [contract["pointer_offset"]]:
            raise ValueError(
                f"residual WRAM tilemap pointer denominator mismatch: "
                f"0x{pointer:08X}"
            )
        metadata = _metadata(decoded, contract)
        if (
            metadata["tile_index_range"] != contract["tile_index_range"]
            or metadata["horizontal_flip_count"]
            != contract["horizontal_flip_count"]
            or metadata["vertical_flip_count"]
            != contract["vertical_flip_count"]
        ):
            raise ValueError(
                f"residual WRAM tilemap payload contract mismatch: "
                f"0x{pointer:08X}"
            )
        result.append(
            {
                "schema": "residual-wram-tilemap-source-v1",
                "source_pointer": pointer,
                "compressed_size": len(compressed),
                "compressed_sha256": _sha256(compressed),
                "decoded_size": len(decoded),
                "decoded_sha256": _sha256(decoded),
                "pointer_offsets": pointer_offsets,
                "literal_load_users": [contract["literal_load_user"]],
                "queue_call": contract["queue_call"],
                "queue_consumer": "0x0806365C",
                "vram_destination": contract["vram_destination"],
                "screenblock": contract["screenblock"],
                "width_entries": contract["width_entries"],
                "height_entries": contract["height_entries"],
                "allowed_tile_index_range": contract["tile_index_range"],
                "allowed_palette_bank": contract["palette_bank"],
                "decoded": decoded,
                **metadata,
            }
        )
    return result


def resolve_residual_wram_tilemap_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Return three allocations and their three exact pointer redirects."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("residual WRAM tilemap base ROM SHA-256 mismatch")
    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    required = {
        "schema": SPEC_SCHEMA,
        "base_rom_sha256": ROM_SHA256,
        "abi_artifact": ABI_PATH.as_posix(),
        "abi_sha256": ABI_SHA256,
        "resource_ownership_artifact": OWNERSHIP_PATH.as_posix(),
        "resource_ownership_sha256": OWNERSHIP_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region": REGION_ID,
        "region_owner": REGION_OWNER,
    }
    for key, expected in required.items():
        if spec.get(key) != expected:
            raise ValueError(f"residual WRAM tilemap {key} mismatch")
    registry_path = root / REGISTRY_PATH
    if spec.get("region_registry_sha256") != _sha256(
        registry_path.read_bytes()
    ):
        raise ValueError("residual WRAM tilemap registry SHA-256 mismatch")
    raw_resources = spec.get("resources")
    if not isinstance(raw_resources, list) or len(raw_resources) != 3:
        raise ValueError("residual WRAM tilemap resources must contain 3 rows")
    resources: dict[int, Path] = {}
    for row in raw_resources:
        if not isinstance(row, dict):
            raise ValueError("residual WRAM tilemap resource must be an object")
        try:
            pointer = int(row.get("source_pointer", ""), 16)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "residual WRAM tilemap source pointer is invalid"
            ) from error
        file_value = row.get("tilemap_file")
        if (
            pointer in resources
            or pointer not in SOURCE_CONTRACTS
            or not isinstance(file_value, str)
            or not file_value
        ):
            raise ValueError("residual WRAM tilemap resource contract mismatch")
        path = Path(file_value)
        resources[pointer] = path if path.is_absolute() else root / path
    if set(resources) != set(SOURCE_CONTRACTS):
        raise ValueError("residual WRAM tilemap resource denominator mismatch")

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
        for row in catalog_residual_wram_tilemaps(root, base)
    }
    patches: list[dict[str, Any]] = []
    cursor = region.start
    for pointer in sorted(resources):
        source = catalog[pointer]
        contract = SOURCE_CONTRACTS[pointer]
        decoded = resources[pointer].read_bytes()
        metadata = _metadata(decoded, contract)
        encoded = encode_gba_lz77(decoded)
        if lz77_decompress(encoded, 0) != decoded:
            raise ValueError("residual WRAM tilemap LZ77 round-trip mismatch")
        offset = _align(cursor)
        end = offset + len(encoded)
        if end > region.end:
            raise ValueError(
                "residual WRAM tilemap batch exceeds its registered region"
            )
        new_pointer = ROM_BASE + offset
        patches.append(
            {
                "id": f"residual-wram-tilemap-{pointer:08x}",
                "type": "bytes",
                "asset_type": "residual_wram_tilemap_relocation",
                "resource_type": "tilemap",
                "source_pointer": pointer,
                "new_pointer": new_pointer,
                "replacement_sha256": _sha256(decoded),
                "decoded_size": len(decoded),
                "encoded_size": len(encoded),
                "width_entries": source["width_entries"],
                "height_entries": source["height_entries"],
                **metadata,
                "vram_destination": source["vram_destination"],
                "screenblock": source["screenblock"],
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
                        f"residual-wram-tilemap-{pointer:08x}."
                        f"pointer-{pointer_offset:06x}"
                    ),
                    "type": "bytes",
                    "asset_type": "residual_wram_tilemap_pointer",
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
        "schema": "residual-wram-tilemap-relocation-patches-v1",
        "patches": resolve_residual_wram_tilemap_relocation_patches(
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
