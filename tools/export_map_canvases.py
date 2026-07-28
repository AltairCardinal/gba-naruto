#!/usr/bin/env python3
"""Export all 47 ROM battle maps as editor-ready canvases and raw resources."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import (  # noqa: E402
    ROM_BASE,
    lz77_decompress,
    parse_palette,
    read_map_entries,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x53D910
TABLE_ADDRESS = ROM_BASE + TABLE_OFFSET
ENTRY_COUNT = 47
ENTRY_SIZE = 32
TABLE_SHA256 = "977b4393a2c5d37124d09e772de42f11d2d9abff9ec832d1160aeeb194a6566c"


RESOURCE_SPECS = {
    "tile_graphics": ("tile_gfx_ptr", "tile-graphics", ".4bpp.bin"),
    "bg_palette": ("bg_palette_ptr", "bg-palettes", ".bgr555.bin"),
    "primary_layout": ("primary_layout_ptr", "primary-layouts", ".u32le.bin"),
    "alternate_layout": (
        "alternate_layout_ptr",
        "alternate-layouts",
        ".u32le.bin",
    ),
    "metatile_definitions": (
        "metatile_attributes_ptr",
        "metatile-definitions",
        ".u16le.bin",
    ),
    "collision_grid": ("collision_grid_ptr", "collision-grids", ".u16le.bin"),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _write_resource(
    output_dir: Path,
    rom: bytes,
    pointer: int | None,
    directory: str,
    suffix: str,
) -> tuple[dict[str, Any] | None, bytes | None]:
    if pointer is None:
        return None, None
    content = lz77_decompress(rom, pointer)
    digest = _sha256(content)
    relative = Path("resources") / directory / f"{digest}{suffix}"
    destination = output_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != content:
            raise ValueError(f"deduplicated resource collision: {relative}")
    else:
        destination.write_bytes(content)
    return (
        {
            "gba_address": _address(pointer + ROM_BASE),
            "file_offset": pointer,
            "decompressed_size": len(content),
            "sha256": digest,
            "output_bin": relative.as_posix(),
        },
        content,
    )


def _expand_tilemap(
    width_tiles: int,
    height_tiles: int,
    layout: bytes,
    metatiles: bytes,
) -> tuple[list[int], list[int]]:
    if width_tiles <= 0 or height_tiles <= 0:
        raise ValueError("map dimensions must be positive")
    if width_tiles % 4 or height_tiles % 2:
        raise ValueError(
            f"map dimensions must align to 4x2 coarse cells: "
            f"{width_tiles}x{height_tiles}"
        )
    coarse_width = width_tiles // 4
    coarse_height = height_tiles // 2
    expected_layout_size = coarse_width * coarse_height * 4
    if len(layout) != expected_layout_size:
        raise ValueError(
            f"layout size {len(layout)} != {expected_layout_size}"
        )
    if not metatiles or len(metatiles) % 8:
        raise ValueError("metatile definitions must be non-empty 8-byte records")

    tilemap = [0] * (width_tiles * height_tiles)
    used_metatiles: set[int] = set()
    for coarse_y in range(coarse_height):
        for coarse_x in range(coarse_width):
            packed = struct.unpack_from(
                "<I",
                layout,
                (coarse_y * coarse_width + coarse_x) * 4,
            )[0]
            for half, metatile_index in enumerate(
                (packed & 0xFFFF, packed >> 16)
            ):
                definition_offset = metatile_index * 8
                if definition_offset + 8 > len(metatiles):
                    raise ValueError(
                        f"metatile index {metatile_index} is out of range"
                    )
                used_metatiles.add(metatile_index)
                definition = struct.unpack_from(
                    "<4H",
                    metatiles,
                    definition_offset,
                )
                for local_y in range(2):
                    for local_x in range(2):
                        tile_x = coarse_x * 4 + half * 2 + local_x
                        tile_y = coarse_y * 2 + local_y
                        tilemap[tile_y * width_tiles + tile_x] = definition[
                            local_y * 2 + local_x
                        ]
    return tilemap, sorted(used_metatiles)


def _render_indexed_pixels(
    width_tiles: int,
    height_tiles: int,
    tilemap: list[int],
    graphics: bytes,
    palette: bytes,
) -> tuple[bytes, dict[str, Any]]:
    if not graphics or len(graphics) % 32:
        raise ValueError("tile graphics must be non-empty 4bpp tiles")
    if not palette or len(palette) % 32:
        raise ValueError("BG palette must contain complete 16-color banks")
    tile_count = len(graphics) // 32
    palette_bank_count = len(palette) // 32
    width = width_tiles * 8
    height = height_tiles * 8
    pixels = bytearray(width * height)
    palette_banks: Counter[int] = Counter()
    horizontal_flips = 0
    vertical_flips = 0
    maximum_tile_index = 0
    for tile_y in range(height_tiles):
        for tile_x in range(width_tiles):
            entry = tilemap[tile_y * width_tiles + tile_x]
            tile_index = entry & 0x03FF
            palette_bank = (entry >> 12) & 0x0F
            if tile_index >= tile_count:
                raise ValueError(
                    f"tile index {tile_index} exceeds {tile_count} tiles"
                )
            if palette_bank >= palette_bank_count:
                raise ValueError(
                    f"palette bank {palette_bank} exceeds "
                    f"{palette_bank_count} banks"
                )
            palette_banks[palette_bank] += 1
            maximum_tile_index = max(maximum_tile_index, tile_index)
            if entry & 0x0400:
                horizontal_flips += 1
            if entry & 0x0800:
                vertical_flips += 1
            tile_offset = tile_index * 32
            for pixel_y in range(8):
                source_y = 7 - pixel_y if entry & 0x0800 else pixel_y
                for pixel_x in range(8):
                    source_x = 7 - pixel_x if entry & 0x0400 else pixel_x
                    packed = graphics[
                        tile_offset + source_y * 4 + source_x // 2
                    ]
                    color = (
                        packed >> (4 if source_x & 1 else 0)
                    ) & 0x0F
                    pixels[
                        (tile_y * 8 + pixel_y) * width
                        + tile_x * 8
                        + pixel_x
                    ] = (
                        0 if color == 0 else palette_bank * 16 + color
                    )
    return bytes(pixels), {
        "maximum_tile_index": maximum_tile_index,
        "palette_bank_usage": {
            str(bank): count for bank, count in sorted(palette_banks.items())
        },
        "horizontal_flip_count": horizontal_flips,
        "vertical_flip_count": vertical_flips,
    }


def _write_indexed_png(
    path: Path,
    width: int,
    height: int,
    pixels: bytes,
    palette_data: bytes,
) -> str:
    palette = parse_palette(palette_data)
    rgb = [channel for color in palette for channel in color]
    if len(rgb) > 768:
        raise ValueError("BG palette exceeds 256 colors")
    image = Image.frombytes("P", (width, height), pixels)
    image.putpalette(rgb + [0] * (768 - len(rgb)))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False)
    return _sha256(path.read_bytes())


def _variant_manifest(
    output_dir: Path,
    map_id: int,
    name: str,
    width_tiles: int,
    height_tiles: int,
    layout: bytes,
    metatiles: bytes,
    graphics: bytes,
    palette: bytes,
) -> dict[str, Any]:
    tilemap, used_metatiles = _expand_tilemap(
        width_tiles,
        height_tiles,
        layout,
        metatiles,
    )
    pixels, facts = _render_indexed_pixels(
        width_tiles,
        height_tiles,
        tilemap,
        graphics,
        palette,
    )
    tilemap_bytes = struct.pack(f"<{len(tilemap)}H", *tilemap)
    tilemap_relative = Path("tilemaps") / (
        f"map-{map_id:02d}-{name}-u16le.bin"
    )
    canvas_relative = Path("canvases") / f"map-{map_id:02d}-{name}.png"
    tilemap_path = output_dir / tilemap_relative
    tilemap_path.parent.mkdir(parents=True, exist_ok=True)
    tilemap_path.write_bytes(tilemap_bytes)
    width = width_tiles * 8
    height = height_tiles * 8
    png_sha256 = _write_indexed_png(
        output_dir / canvas_relative,
        width,
        height,
        pixels,
        palette,
    )
    return {
        "name": name,
        "header_role": name,
        "width": width,
        "height": height,
        "candidate_static_canvas": name == "alternate",
        "runtime_selection_proven": map_id == 41 and name == "primary",
        "tilemap_bin": tilemap_relative.as_posix(),
        "tilemap_sha256": _sha256(tilemap_bytes),
        "tilemap_entry_count": len(tilemap),
        "canvas_png": canvas_relative.as_posix(),
        "canvas_png_sha256": png_sha256,
        "indexed_pixels_sha256": _sha256(pixels),
        "used_metatile_count": len(used_metatiles),
        "minimum_metatile_index": min(used_metatiles),
        "maximum_metatile_index": max(used_metatiles),
        **facts,
    }


def export_map_canvases(
    root: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    output_dir = Path(output_dir)
    rom = (root / "rom/base.gba").read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_sha256}"
        )
    table = rom[TABLE_OFFSET : TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE]
    if len(table) != ENTRY_COUNT * ENTRY_SIZE:
        raise ValueError("map header table is truncated")
    if _sha256(table) != TABLE_SHA256:
        raise ValueError("map header table SHA-256 mismatch")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    entries: list[dict[str, Any]] = []
    resource_hashes: dict[str, set[str]] = {
        name: set() for name in RESOURCE_SPECS
    }
    canvas_count = 0
    alternate_count = 0
    for source_entry in read_map_entries(rom):
        map_id = source_entry["map_id"]
        width_tiles = source_entry["width_tiles"]
        height_tiles = source_entry["height_tiles"]
        resources: dict[str, Any] = {}
        payloads: dict[str, bytes | None] = {}
        for name, (pointer_key, directory, suffix) in RESOURCE_SPECS.items():
            resource, payload = _write_resource(
                output_dir,
                rom,
                source_entry[pointer_key],
                directory,
                suffix,
            )
            resources[name] = resource
            payloads[name] = payload
            if resource is not None:
                resource_hashes[name].add(resource["sha256"])

        variants = [
            _variant_manifest(
                output_dir,
                map_id,
                "primary",
                width_tiles,
                height_tiles,
                payloads["primary_layout"],
                payloads["metatile_definitions"],
                payloads["tile_graphics"],
                payloads["bg_palette"],
            )
        ]
        if payloads["alternate_layout"] is not None:
            variants.append(
                _variant_manifest(
                    output_dir,
                    map_id,
                    "alternate",
                    width_tiles,
                    height_tiles,
                    payloads["alternate_layout"],
                    payloads["metatile_definitions"],
                    payloads["tile_graphics"],
                    payloads["bg_palette"],
                )
            )
            alternate_count += 1
        canvas_count += len(variants)

        header_offset = source_entry["file_offset"]
        header = rom[header_offset : header_offset + ENTRY_SIZE]
        entries.append(
            {
                "map_id": map_id,
                "header": {
                    "file_offset": header_offset,
                    "file_offset_hex": f"0x{header_offset:08X}",
                    "gba_address": _address(header_offset + ROM_BASE),
                    "raw_hex": header.hex(),
                    "sha256": _sha256(header),
                },
                "dimensions_tiles": [width_tiles, height_tiles],
                "dimensions_pixels": [width_tiles * 8, height_tiles * 8],
                "coarse_grid_dimensions": [
                    width_tiles // 4,
                    height_tiles // 2,
                ],
                "flags": source_entry["flags"],
                "resources": resources,
                "variants": variants,
            }
        )

    manifest: dict[str, Any] = {
        "schema": "map-canvases-v1",
        "rom": {
            "path": "rom/base.gba",
            "sha256": rom_sha256,
        },
        "map_header_table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": _address(TABLE_ADDRESS),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "sha256": _sha256(table),
        },
        "map_count": len(entries),
        "canvas_count": canvas_count,
        "alternate_canvas_count": alternate_count,
        "unique_resource_counts": {
            "tile_graphics": len(resource_hashes["tile_graphics"]),
            "bg_palettes": len(resource_hashes["bg_palette"]),
            "primary_layouts": len(resource_hashes["primary_layout"]),
            "alternate_layouts": len(resource_hashes["alternate_layout"]),
            "metatile_definitions": len(
                resource_hashes["metatile_definitions"]
            ),
            "collision_grids": len(resource_hashes["collision_grid"]),
        },
        "entries": entries,
        "consumer_contract": {
            "header_selector": "0x08068FB4",
            "resource_loader": "0x08068FF0",
            "collision_loader": "0x08069264",
            "coarse_cell_size_tiles": [4, 2],
            "layout_u32_halves": (
                "low_u16=left_2x2_metatile, "
                "high_u16=right_2x2_metatile"
            ),
            "metatile_record": "4 little-endian GBA BG u16 entries",
            "bg_entry_bits": {
                "tile_index": "0..9",
                "horizontal_flip": 10,
                "vertical_flip": 11,
                "palette_bank": "12..15",
            },
        },
        "scope": {
            "all_primary_static_canvases_exported": True,
            "all_alternate_static_canvases_exported": True,
            "raw_editor_resources_exported": True,
            "alternate_runtime_selection_complete": False,
            "runtime_scroll_and_chunk_selection_complete": False,
            "dynamic_occupancy_overlay_included": False,
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
        default=Path("artifacts/map-canvases-v1"),
    )
    args = parser.parse_args()
    manifest = export_map_canvases(args.root, args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "maps": manifest["map_count"],
                "canvases": manifest["canvas_count"],
                "errors": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
