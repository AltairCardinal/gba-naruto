#!/usr/bin/env python3
"""Export every valid ROM battle-effect graphics/palette resource pair."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import struct
from pathlib import Path
from typing import Any

from PIL import Image


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x59911C
TABLE_ADDRESS = ROM_BASE + TABLE_OFFSET
ENTRY_COUNT = 19
ENTRY_SIZE = 8
TABLE_SHA256 = "7d9f94e05b975940bd2e17f55681120782cb7b6f07d0ab6245adef7260d24130"
CODE_SLICES = (
    {
        "name": "effect_resource_builder",
        "file_offset": 0x07FDCC,
        "gba_start": "0x0807FDCC",
        "gba_end": "0x0807FE2C",
        "sha256": "2715bad870d8d7ea84bd03c537f08200be80b178c0dd570aea30155bb9431a84",
    },
    {
        "name": "effect_sequence_selector",
        "file_offset": 0x07FE2C,
        "gba_start": "0x0807FE2C",
        "gba_end": "0x080800A4",
        "sha256": "690232cbbed4b7f9d19602e91feca3299191cccb8369a10d3235b2d415751c94",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer {_address(pointer)} is outside the ROM")
    return offset


def _read_lz77(rom: bytes, offset: int) -> tuple[bytes, bytes]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"resource is not GBA LZ77 at 0x{offset:06X}")
    output_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    output = bytearray()
    cursor = offset + 4
    while len(output) < output_size:
        if cursor >= len(rom):
            raise ValueError(f"truncated LZ77 flags at 0x{cursor:06X}")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= output_size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError(
                        f"truncated LZ77 back-reference at 0x{cursor:06X}"
                    )
                first = rom[cursor]
                second = rom[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                distance = ((first & 0x0F) << 8) + second + 1
                if distance > len(output):
                    raise ValueError(
                        f"invalid LZ77 distance {distance} at 0x{cursor - 2:06X}"
                    )
                if len(output) + length > output_size:
                    raise ValueError("LZ77 copy exceeds declared output size")
                source = len(output) - distance
                for _ in range(length):
                    output.append(output[source])
                    source += 1
            else:
                if cursor >= len(rom):
                    raise ValueError(f"truncated LZ77 literal at 0x{cursor:06X}")
                output.append(rom[cursor])
                cursor += 1
    return rom[offset:cursor], bytes(output)


def _palette_rgb(palette: bytes) -> list[int]:
    if len(palette) != 32:
        raise ValueError(f"expected a 16-color palette, got {len(palette)} bytes")
    rgb: list[int] = []
    for offset in range(0, len(palette), 2):
        color = int.from_bytes(palette[offset : offset + 2], "little") & 0x7FFF
        for shift in (0, 5, 10):
            value = (color >> shift) & 0x1F
            rgb.append((value << 3) | (value >> 2))
    return rgb


def _atlas_pixels(graphics: bytes) -> tuple[bytes, int, int, int]:
    if not graphics or len(graphics) % 32:
        raise ValueError(
            f"4bpp graphics size must be a non-zero multiple of 32: {len(graphics)}"
        )
    tile_count = len(graphics) // 32
    tiles_per_row = min(16, tile_count)
    width = tiles_per_row * 8
    height = ((tile_count + tiles_per_row - 1) // tiles_per_row) * 8
    pixels = bytearray(width * height)
    for tile_index in range(tile_count):
        tile_x = tile_index % tiles_per_row
        tile_y = tile_index // tiles_per_row
        tile_start = tile_index * 32
        for y in range(8):
            destination = (tile_y * 8 + y) * width + tile_x * 8
            for x in range(8):
                packed = graphics[tile_start + y * 4 + x // 2]
                pixels[destination + x] = (
                    packed >> (4 if x & 1 else 0)
                ) & 0x0F
    return bytes(pixels), width, height, tiles_per_row


def _png_bytes(
    pixels: bytes,
    width: int,
    height: int,
    palette: bytes,
) -> bytes:
    image = Image.frombytes("P", (width, height), pixels)
    rgb = _palette_rgb(palette)
    image.putpalette(rgb + [0] * (768 - len(rgb)))
    image.info["transparency"] = 0
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _code_slices(rom: bytes) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for expected in CODE_SLICES:
        item = dict(expected)
        start = int(item["file_offset"])
        end = int(str(item["gba_end"]), 16) - ROM_BASE
        actual = _sha256(rom[start:end])
        if actual != item["sha256"]:
            raise ValueError(
                f"{item['name']} SHA-256 mismatch: "
                f"expected {item['sha256']}, got {actual}"
            )
        result.append(item)
    return result


def export_battle_effect_resource_pairs(
    root: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    output_dir = Path(output_dir)
    rom_path = root / "rom/base.gba"
    rom = rom_path.read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_sha256}"
        )

    table = rom[TABLE_OFFSET : TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE]
    if len(table) != ENTRY_COUNT * ENTRY_SIZE:
        raise ValueError("battle-effect resource-pair table is truncated")
    if _sha256(table) != TABLE_SHA256:
        raise ValueError("battle-effect resource-pair table SHA-256 mismatch")
    if table[:ENTRY_SIZE] != b"\0" * ENTRY_SIZE:
        raise ValueError("battle-effect resource group zero is not the sentinel")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    entries: list[dict[str, Any]] = []
    for group_id in range(1, ENTRY_COUNT):
        graphics_pointer, palette_pointer = struct.unpack_from(
            "<II",
            table,
            group_id * ENTRY_SIZE,
        )
        graphics_compressed, graphics = _read_lz77(
            rom,
            _rom_offset(graphics_pointer, len(rom)),
        )
        palette_compressed, palette = _read_lz77(
            rom,
            _rom_offset(palette_pointer, len(rom)),
        )
        if len(graphics) % 32:
            raise ValueError(
                f"group {group_id} graphics are not 4bpp tile aligned"
            )
        if len(palette) != 32:
            raise ValueError(
                f"group {group_id} palette size is {len(palette)}, expected 32"
            )

        graphics_name = f"group-{group_id:02d}-graphics-4bpp.bin"
        palette_name = f"group-{group_id:02d}-palette-bgr555.bin"
        atlas_name = f"group-{group_id:02d}-atlas.png"
        graphics_path = output_dir / graphics_name
        palette_path = output_dir / palette_name
        atlas_path = output_dir / atlas_name
        graphics_path.write_bytes(graphics)
        palette_path.write_bytes(palette)
        pixels, width, height, tiles_per_row = _atlas_pixels(graphics)
        png = _png_bytes(pixels, width, height, palette)
        atlas_path.write_bytes(png)

        entries.append(
            {
                "group_id": group_id,
                "table_entry_file_offset": TABLE_OFFSET + group_id * ENTRY_SIZE,
                "table_entry_gba_address": _address(
                    TABLE_ADDRESS + group_id * ENTRY_SIZE
                ),
                "pair_raw_hex": table[
                    group_id * ENTRY_SIZE : (group_id + 1) * ENTRY_SIZE
                ].hex(),
                "graphics": {
                    "gba_address": _address(graphics_pointer),
                    "file_offset": graphics_pointer - ROM_BASE,
                    "compressed_size": len(graphics_compressed),
                    "compressed_sha256": _sha256(graphics_compressed),
                    "decompressed_size": len(graphics),
                    "decompressed_sha256": _sha256(graphics),
                    "tile_count": len(graphics) // 32,
                    "output_bin": graphics_name,
                },
                "palette": {
                    "gba_address": _address(palette_pointer),
                    "file_offset": palette_pointer - ROM_BASE,
                    "compressed_size": len(palette_compressed),
                    "compressed_sha256": _sha256(palette_compressed),
                    "decompressed_size": len(palette),
                    "decompressed_sha256": _sha256(palette),
                    "color_count": 16,
                    "transparent_index": 0,
                    "output_bin": palette_name,
                },
                "atlas": {
                    "png": atlas_name,
                    "width": width,
                    "height": height,
                    "tiles_per_row": tiles_per_row,
                    "tile_order": (
                        "GBA 4bpp tiles, row-major, "
                        f"{tiles_per_row} tiles per row"
                    ),
                    "sha256": _sha256(png),
                },
            }
        )

    manifest: dict[str, Any] = {
        "schema": "battle-effect-resource-pairs-v1",
        "rom": {
            "path": "rom/base.gba",
            "sha256": rom_sha256,
        },
        "resource_pair_table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": _address(TABLE_ADDRESS),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "valid_group_ids": list(range(1, ENTRY_COUNT)),
            "sha256": _sha256(table),
        },
        "valid_resource_pair_count": len(entries),
        "entries": entries,
        "consumer_code_slices": _code_slices(rom),
        "scope": {
            "canonical_static_graphics_exported": True,
            "canonical_static_palettes_exported": True,
            "resource_group_to_sequence_mapping_complete": False,
            "oam_composition_complete": False,
            "frame_hold_timing_complete": False,
            "audio_binding_complete": False,
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/battle-effect-resource-pairs-v1"),
    )
    args = parser.parse_args()
    manifest = export_battle_effect_resource_pairs(args.root, args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "resource_pairs": manifest["valid_resource_pair_count"],
                "errors": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
