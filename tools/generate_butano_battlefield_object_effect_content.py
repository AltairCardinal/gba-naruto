#!/usr/bin/env python3
"""Generate the ROM-derived type-2 battlefield-object expiry sprite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.butano.indexed_bmp import write_4bpp_bmp
from tools.extract_tileset import lz77_decompress


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
GRAPHICS_POINTER = 0x083478F4
PALETTE_POINTER = 0x083480C8
FRAME_WIDTH = 32
FRAME_HEIGHT = 32
FRAME_COUNT = 7
TILE_BYTES = 32
TILES_PER_FRAME = 16


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gba_color(value: int) -> tuple[int, int, int]:
    return (
        (value & 0x1F) * 255 // 31,
        ((value >> 5) & 0x1F) * 255 // 31,
        ((value >> 10) & 0x1F) * 255 // 31,
    )


def _frame_pixels(graphics: bytes) -> bytes:
    expected_size = FRAME_COUNT * TILES_PER_FRAME * TILE_BYTES
    if len(graphics) != expected_size:
        raise ValueError(
            f"unexpected type-2 expiry graphics size: {len(graphics)}"
        )
    pixels = bytearray(FRAME_WIDTH * FRAME_HEIGHT * FRAME_COUNT)
    for frame in range(FRAME_COUNT):
        frame_y = frame * FRAME_HEIGHT
        for tile in range(TILES_PER_FRAME):
            tile_x = (tile % 4) * 8
            tile_y = frame_y + (tile // 4) * 8
            tile_offset = (
                frame * TILES_PER_FRAME + tile
            ) * TILE_BYTES
            tile_data = graphics[
                tile_offset : tile_offset + TILE_BYTES
            ]
            for y in range(8):
                for x in range(8):
                    packed = tile_data[y * 4 + x // 2]
                    color = (
                        packed & 0x0F
                        if x % 2 == 0
                        else packed >> 4
                    )
                    pixels[
                        (tile_y + y) * FRAME_WIDTH + tile_x + x
                    ] = color
    return bytes(pixels)


def generate_battlefield_object_effect_content(
    root: Path, output_dir: Path
) -> dict[str, Any]:
    root = Path(root)
    output_dir = Path(output_dir)
    rom = (root / "rom/base.gba").read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_sha256}"
        )

    graphics = lz77_decompress(
        rom, GRAPHICS_POINTER - 0x08000000
    )
    palette_bytes = lz77_decompress(
        rom, PALETTE_POINTER - 0x08000000
    )
    if len(palette_bytes) != 32:
        raise ValueError("type-2 expiry palette must contain 16 colors")
    palette = [
        _gba_color(
            int.from_bytes(
                palette_bytes[index * 2 : index * 2 + 2],
                "little",
            )
        )
        for index in range(16)
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    write_4bpp_bmp(
        output_dir / "battlefield_object_type_2_expiry.bmp",
        FRAME_WIDTH,
        FRAME_HEIGHT * FRAME_COUNT,
        _frame_pixels(graphics),
        palette,
    )
    metadata = {
        "type": "sprite",
        "height": FRAME_HEIGHT,
        "source": "rom/base.gba:sequence-7-resource-group-18",
    }
    (
        output_dir / "battlefield_object_type_2_expiry.json"
    ).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": 1,
        "rom_sha256": rom_sha256,
        "effect_sequence": 7,
        "sequence_resource_group": 0x12,
        "graphics_pointer": f"0x{GRAPHICS_POINTER:08X}",
        "palette_pointer": f"0x{PALETTE_POINTER:08X}",
        "frame_width": FRAME_WIDTH,
        "frame_height": FRAME_HEIGHT,
        "frame_count": FRAME_COUNT,
        "graphics_decompressed_size": len(graphics),
        "graphics_decompressed_sha256": _sha256(graphics),
        "palette_decompressed_sha256": _sha256(palette_bytes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("butano-sequel/graphics"),
    )
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    result = generate_battlefield_object_effect_content(
        args.root, args.output_dir
    )
    encoded = (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
