#!/usr/bin/env python3
"""Export all statically provable BG layers from the 79 tile-assets rows."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import (
    ROM_BASE,
    gba_address,
    gba_pointer,
    indexed_png_from_bgr555,
    read_lz77_record,
    render_4bpp_tile_atlas_indices,
    sha256,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x5A320C
TABLE_ENTRY_COUNT = 79
TABLE_ENTRY_SIZE = 0x44
TABLE_SHA256 = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
SENTINEL_DESCRIPTOR_IDS = (13, 31, 32, 46)
ATLAS_TILES_PER_ROW = 32

LAYER_SPECS = (
    {
        "name": "A",
        "definition_word": None,
        "gfx_word": 3,
        "tilemap_word": 4,
        "palette_word": 5,
        "fixed_width": 30,
        "fixed_height": 14,
        "screen_stride_tiles": 32,
        "bits_per_pixel": 4,
        "palette_size": 32,
        "tile_base": {"kind": "consumer_argument"},
        "palette_bank": {"kind": "consumer_argument"},
    },
    {
        "name": "B",
        "definition_word": None,
        "gfx_word": 6,
        "tilemap_word": 7,
        "palette_word": 8,
        "fixed_width": 32,
        "fixed_height": 14,
        "screen_stride_tiles": 32,
        "bits_per_pixel": 4,
        "palette_size": 32,
        "tile_base": {"kind": "runtime_state"},
        "palette_bank": {"kind": "runtime_state"},
    },
    {
        "name": "C",
        "definition_word": 9,
        "gfx_word": 10,
        "tilemap_word": 11,
        "palette_word": 12,
        "screen_stride_tiles": 64,
        "bits_per_pixel": 8,
        "palette_size": 128,
        "tile_base": {
            "kind": "runtime_state",
            "expression": "state[0x16] >> 1",
        },
        "palette_bank": {"kind": "runtime_state"},
    },
    {
        "name": "D",
        "definition_word": 13,
        "gfx_word": 14,
        "tilemap_word": 15,
        "palette_word": 16,
        "screen_stride_tiles": 64,
        "bits_per_pixel": 4,
        "palette_size": 32,
        "tile_base": {
            "kind": "runtime_state",
            "expression": "u16(state[0x12] + state[0x16])",
            "consumer_gba_address": "0x080992FA",
        },
        "palette_bank": {"kind": "runtime_state"},
    },
)


def render_4bpp_tilemap_indices(
    graphics: bytes,
    tilemap: bytes,
    *,
    width_tiles: int,
    height_tiles: int,
) -> bytes:
    """Render a relative-index GBA text-BG tilemap as palette indices."""
    if not graphics or len(graphics) % 32:
        raise ValueError("BG graphics must contain complete 4bpp tiles")
    if width_tiles <= 0 or height_tiles <= 0:
        raise ValueError("BG tilemap dimensions must be positive")
    expected_size = width_tiles * height_tiles * 2
    if len(tilemap) != expected_size:
        raise ValueError(
            f"BG tilemap is {len(tilemap)} bytes, expected {expected_size}"
        )

    tile_count = len(graphics) // 32
    entries = struct.unpack(f"<{width_tiles * height_tiles}H", tilemap)
    width = width_tiles * 8
    height = height_tiles * 8
    pixels = bytearray(width * height)
    for tile_y in range(height_tiles):
        for tile_x in range(width_tiles):
            entry = entries[tile_y * width_tiles + tile_x]
            source_tile = entry & 0x03FF
            if source_tile >= tile_count:
                raise ValueError(
                    f"tilemap references tile {source_tile}, but graphics "
                    f"contains {tile_count} tiles"
                )
            horizontal_flip = bool(entry & (1 << 10))
            vertical_flip = bool(entry & (1 << 11))
            for local_y in range(8):
                source_y = 7 - local_y if vertical_flip else local_y
                destination_y = tile_y * 8 + local_y
                for local_x in range(8):
                    source_x = 7 - local_x if horizontal_flip else local_x
                    source = (
                        source_tile * 32
                        + source_y * 4
                        + source_x // 2
                    )
                    packed = graphics[source]
                    color = (
                        packed >> (4 if source_x & 1 else 0)
                    ) & 0x0F
                    destination_x = tile_x * 8 + local_x
                    pixels[destination_y * width + destination_x] = color
    return bytes(pixels)


def render_8bpp_tilemap_indices(
    graphics: bytes,
    tilemap: bytes,
    *,
    width_tiles: int,
    height_tiles: int,
) -> bytes:
    """Render a relative-index GBA 8bpp text-BG tilemap."""
    if not graphics or len(graphics) % 64:
        raise ValueError("BG graphics must contain complete 8bpp tiles")
    if width_tiles <= 0 or height_tiles <= 0:
        raise ValueError("BG tilemap dimensions must be positive")
    expected_size = width_tiles * height_tiles * 2
    if len(tilemap) != expected_size:
        raise ValueError(
            f"BG tilemap is {len(tilemap)} bytes, expected {expected_size}"
        )

    tile_count = len(graphics) // 64
    entries = struct.unpack(f"<{width_tiles * height_tiles}H", tilemap)
    width = width_tiles * 8
    height = height_tiles * 8
    pixels = bytearray(width * height)
    for tile_y in range(height_tiles):
        for tile_x in range(width_tiles):
            entry = entries[tile_y * width_tiles + tile_x]
            source_tile = entry & 0x03FF
            if source_tile >= tile_count:
                raise ValueError(
                    f"tilemap references tile {source_tile}, but graphics "
                    f"contains {tile_count} tiles"
                )
            horizontal_flip = bool(entry & (1 << 10))
            vertical_flip = bool(entry & (1 << 11))
            tile_offset = source_tile * 64
            for local_y in range(8):
                source_y = 7 - local_y if vertical_flip else local_y
                destination_y = tile_y * 8 + local_y
                for local_x in range(8):
                    source_x = 7 - local_x if horizontal_flip else local_x
                    color = graphics[
                        tile_offset + source_y * 8 + source_x
                    ]
                    destination_x = tile_x * 8 + local_x
                    pixels[destination_y * width + destination_x] = color
    return bytes(pixels)


def render_8bpp_tile_atlas_indices(
    graphics: bytes,
    *,
    tiles_per_row: int,
) -> tuple[bytes, int, int]:
    """Render every 8bpp tile in ROM order into a lossless indexed atlas."""
    if not graphics or len(graphics) % 64:
        raise ValueError("8bpp atlas graphics must contain complete tiles")
    if tiles_per_row <= 0:
        raise ValueError("8bpp atlas row width must be positive")
    tile_count = len(graphics) // 64
    columns = min(tile_count, tiles_per_row)
    rows = (tile_count + tiles_per_row - 1) // tiles_per_row
    width = columns * 8
    height = rows * 8
    pixels = bytearray(width * height)
    for tile in range(tile_count):
        tile_x = tile % tiles_per_row
        tile_y = tile // tiles_per_row
        for local_y in range(8):
            source = tile * 64 + local_y * 8
            destination = (tile_y * 8 + local_y) * width + tile_x * 8
            pixels[destination : destination + 8] = graphics[
                source : source + 8
            ]
    return bytes(pixels), width, height


def _load_bank_from_rom(rom: bytes) -> tuple[dict[str, Any], list[list[int]]]:
    """Enumerate descriptor rows straight from ROM.

    ``_load_bank`` reads the same ROM words and only uses
    ``sequel/content/tile-assets/bank.json`` as a divergence check, so this
    yields byte-identical rows for worktrees that do not carry that bank.
    """
    table_end = TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    if sha256(rom[TABLE_OFFSET:table_end]) != TABLE_SHA256:
        raise ValueError("tile-assets descriptor table hash mismatch")
    rows = [
        list(struct.unpack_from("<17I", rom, TABLE_OFFSET + index * TABLE_ENTRY_SIZE))
        for index in range(TABLE_ENTRY_COUNT)
    ]
    return (
        {
            "table_offset": TABLE_OFFSET,
            "entry_count": TABLE_ENTRY_COUNT,
            "entry_size": TABLE_ENTRY_SIZE,
            # The table hash is verified against ROM above, which is what
            # "code_verified" asserts; the bank.json cross-check is skipped,
            # not the verification itself.
            "verification": "code_verified",
        },
        rows,
    )


def _load_bank(root: Path, rom: bytes) -> tuple[dict[str, Any], list[list[int]]]:
    bank = json.loads(
        (root / "sequel/content/tile-assets/bank.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        bank.get("table_offset") != TABLE_OFFSET
        or bank.get("entry_count") != TABLE_ENTRY_COUNT
        or bank.get("entry_size") != TABLE_ENTRY_SIZE
        or bank.get("verification") != "code_verified"
        or len(bank.get("entries", [])) != TABLE_ENTRY_COUNT
    ):
        raise ValueError("unexpected tile-assets descriptor bank")

    table_end = TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    if sha256(rom[TABLE_OFFSET:table_end]) != TABLE_SHA256:
        raise ValueError("tile-assets descriptor table hash mismatch")

    rows: list[list[int]] = []
    for index, entry in enumerate(bank["entries"]):
        row_offset = TABLE_OFFSET + index * TABLE_ENTRY_SIZE
        if entry.get("_index") != index:
            raise ValueError(f"tile-assets row {index} has the wrong index")
        if entry.get("_raw_offset") != row_offset:
            raise ValueError(f"tile-assets row {index} has the wrong offset")
        expected = list(struct.unpack_from("<17I", rom, row_offset))
        actual = [entry.get(f"word_{word:02d}") for word in range(17)]
        if actual != expected:
            raise ValueError(
                f"tile-assets bank diverges from ROM at row {index}"
            )
        rows.append(expected)
    return bank, rows


def _definition(
    spec: dict[str, Any],
    words: list[int],
) -> dict[str, Any]:
    definition_word = spec["definition_word"]
    if definition_word is None:
        return {
            "x_tiles": 0,
            "y_tiles": 0,
            "width_tiles": spec["fixed_width"],
            "height_tiles": spec["fixed_height"],
            "screen_stride_tiles": spec["screen_stride_tiles"],
            "source": "consumer_fixed",
        }

    x_tiles, y_tiles, width_tiles, height_tiles = words[
        definition_word
    ].to_bytes(4, "little")
    return {
        "x_tiles": x_tiles,
        "y_tiles": y_tiles,
        "width_tiles": width_tiles,
        "height_tiles": height_tiles,
        "screen_stride_tiles": spec["screen_stride_tiles"],
        "source": "descriptor_packed_bytes",
    }


def _extract_lz(
    rom: bytes,
    pointer: int,
    *,
    expected_size: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    offset = pointer - ROM_BASE
    if not 0 <= offset < len(rom):
        raise ValueError(
            f"LZ pointer is outside the ROM: {gba_pointer(pointer)}"
        )
    compressed = read_lz77_record(
        rom,
        offset,
        expected_size=expected_size,
    )
    decompressed = lz77_decompress(rom, offset)
    if expected_size is not None and len(decompressed) != expected_size:
        raise ValueError(
            f"resource at {gba_pointer(pointer)} decompressed to "
            f"{len(decompressed)}, expected {expected_size}"
        )
    return decompressed, {
        "file_offset": offset,
        "gba_address": gba_pointer(pointer),
        "compressed_size": len(compressed),
        "compressed_sha256": sha256(compressed),
        "decompressed_size": len(decompressed),
        "decompressed_sha256": sha256(decompressed),
    }


def _extract_palette(
    rom: bytes,
    pointer: int,
    *,
    size: int,
) -> tuple[bytes, dict[str, Any]]:
    offset = pointer - ROM_BASE
    if size <= 0 or size % 2:
        raise ValueError("palette size must contain complete BGR555 colors")
    if not 0 <= offset <= len(rom) - size:
        raise ValueError(
            f"palette pointer is outside the ROM: {gba_pointer(pointer)}"
        )
    palette = rom[offset : offset + size]
    return palette, {
        "file_offset": offset,
        "gba_address": gba_pointer(pointer),
        "size": len(palette),
        "sha256": sha256(palette),
    }


def _tilemap_facts(
    tilemap: bytes,
    *,
    tile_count: int | None,
) -> dict[str, Any]:
    entries = struct.unpack(f"<{len(tilemap) // 2}H", tilemap)
    palette_banks = sorted({entry >> 12 for entry in entries})
    if palette_banks != [0]:
        raise ValueError(
            f"source tilemap uses palette banks {palette_banks}, expected [0]"
        )
    indices = [entry & 0x03FF for entry in entries]
    if tile_count is not None and max(indices) >= tile_count:
        raise ValueError(
            f"tilemap references tile {max(indices)}, but graphics contains "
            f"{tile_count} tiles"
        )
    return {
        "tile_index_min": min(indices),
        "tile_index_max": max(indices),
        "used_tile_count": len(set(indices)),
        "horizontal_flip_count": sum(
            bool(entry & (1 << 10)) for entry in entries
        ),
        "vertical_flip_count": sum(
            bool(entry & (1 << 11)) for entry in entries
        ),
        "source_palette_banks": palette_banks,
    }


def _remove_owned_outputs(output_dir: Path) -> None:
    for path in output_dir.iterdir():
        if not path.is_file():
            continue
        if path.name == "manifest.json" or (
            path.suffix == ".png"
            and path.name.startswith(("atlas_", "descriptor_"))
        ):
            path.unlink()


def export_tile_asset_bg_layers(
    root: Path,
    output_dir: Path,
    from_rom: bool = False,
) -> dict[str, Any]:
    """Export native layer images, lossless atlases, and a ROM-bound manifest."""
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    rom = (root / "rom/base.gba").read_bytes()
    rom_sha256 = sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_sha256}"
        )
    bank, rows = (
        _load_bank_from_rom(rom) if from_rom else _load_bank(root, rom)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _remove_owned_outputs(output_dir)

    descriptors: list[dict[str, Any]] = []
    atlases: list[dict[str, Any]] = []
    atlas_by_pair: dict[tuple[str, str, str], dict[str, Any]] = {}
    complete_layer_counts = {spec["name"]: 0 for spec in LAYER_SPECS}
    complete_layer_count = 0
    partial_layer_count = 0
    unique_graphics: set[str] = set()
    unique_tilemaps: set[str] = set()
    unique_palettes: set[str] = set()
    unique_complete_layers: set[tuple[str, str, str]] = set()

    for index, words in enumerate(rows):
        raw_words = [f"0x{word:08X}" for word in words]
        is_sentinel = not any(words)
        if is_sentinel != (index in SENTINEL_DESCRIPTOR_IDS):
            raise ValueError(
                f"unexpected tile-assets sentinel state at row {index}"
            )
        descriptor = {
            "descriptor_id": index,
            "consumer_id": index + 1,
            "descriptor_file_offset": TABLE_OFFSET + index * TABLE_ENTRY_SIZE,
            "descriptor_gba_address": gba_address(
                TABLE_OFFSET + index * TABLE_ENTRY_SIZE
            ),
            "status": "sentinel" if is_sentinel else "complete",
            "raw_words": raw_words,
            "layers": [],
        }
        descriptors.append(descriptor)
        if is_sentinel:
            continue

        for spec in LAYER_SPECS:
            name = spec["name"]
            definition = _definition(spec, words)
            gfx_pointer = words[spec["gfx_word"]]
            tilemap_pointer = words[spec["tilemap_word"]]
            palette_pointer = words[spec["palette_word"]]
            pointers = (gfx_pointer, tilemap_pointer, palette_pointer)
            present_count = sum(bool(pointer) for pointer in pointers)
            layer: dict[str, Any] = {
                "name": name,
                "status": "absent",
                "bits_per_pixel": spec["bits_per_pixel"],
                "bytes_per_tile": spec["bits_per_pixel"] * 8,
                "palette_color_count": spec["palette_size"] // 2,
                "definition": definition,
                "tile_base": spec["tile_base"],
                "palette_bank": spec["palette_bank"],
                "gfx_pointer": (
                    gba_pointer(gfx_pointer) if gfx_pointer else None
                ),
                "tilemap_pointer": (
                    gba_pointer(tilemap_pointer) if tilemap_pointer else None
                ),
                "palette_pointer": (
                    gba_pointer(palette_pointer) if palette_pointer else None
                ),
            }
            descriptor["layers"].append(layer)

            if present_count == 0:
                if name != "D":
                    raise ValueError(
                        f"required layer {name} is absent at row {index}"
                    )
                continue

            expected_map_size = (
                definition["width_tiles"]
                * definition["height_tiles"]
                * 2
            )
            if expected_map_size <= 0:
                raise ValueError(
                    f"layer {name} has invalid dimensions at row {index}"
                )

            if present_count != 3:
                if not (
                    index == 0
                    and name == "D"
                    and pointers == (0, tilemap_pointer, 0)
                    and tilemap_pointer
                ):
                    raise ValueError(
                        f"unexpected partial layer {name} at row {index}"
                    )
                tilemap, tilemap_manifest = _extract_lz(
                    rom,
                    tilemap_pointer,
                    expected_size=expected_map_size,
                )
                facts = _tilemap_facts(tilemap, tile_count=None)
                unique_tilemaps.add(
                    tilemap_manifest["decompressed_sha256"]
                )
                layer.update(
                    {
                        "status": "partial",
                        "missing_components": ["gfx", "palette"],
                        "tilemap": tilemap_manifest,
                        **facts,
                    }
                )
                descriptor["status"] = "partial"
                partial_layer_count += 1
                continue

            expected_gfx_size = 4096 if name == "B" else None
            graphics, graphics_manifest = _extract_lz(
                rom,
                gfx_pointer,
                expected_size=expected_gfx_size,
            )
            bytes_per_tile = spec["bits_per_pixel"] * 8
            if len(graphics) % bytes_per_tile:
                raise ValueError(
                    f"layer {name} graphics is not whole tiles at row {index}"
                )
            tilemap, tilemap_manifest = _extract_lz(
                rom,
                tilemap_pointer,
                expected_size=expected_map_size,
            )
            palette, palette_manifest = _extract_palette(
                rom,
                palette_pointer,
                size=spec["palette_size"],
            )
            tile_count = len(graphics) // bytes_per_tile
            facts = _tilemap_facts(tilemap, tile_count=tile_count)
            renderer = (
                render_8bpp_tilemap_indices
                if spec["bits_per_pixel"] == 8
                else render_4bpp_tilemap_indices
            )
            pixels = renderer(
                graphics,
                tilemap,
                width_tiles=definition["width_tiles"],
                height_tiles=definition["height_tiles"],
            )
            layer_png = indexed_png_from_bgr555(
                pixels,
                palette,
                width=definition["width_tiles"] * 8,
                height=definition["height_tiles"] * 8,
                transparent_index=0,
            )
            layer_filename = f"descriptor_{index:02d}_{name.lower()}.png"
            (output_dir / layer_filename).write_bytes(layer_png)

            graphics_hash = graphics_manifest["decompressed_sha256"]
            tilemap_hash = tilemap_manifest["decompressed_sha256"]
            palette_hash = palette_manifest["sha256"]
            atlas_key = (
                str(spec["bits_per_pixel"]),
                graphics_hash,
                palette_hash,
            )
            atlas = atlas_by_pair.get(atlas_key)
            if atlas is None:
                atlas_renderer = (
                    render_8bpp_tile_atlas_indices
                    if spec["bits_per_pixel"] == 8
                    else render_4bpp_tile_atlas_indices
                )
                atlas_pixels, atlas_width, atlas_height = (
                    atlas_renderer(
                        graphics,
                        tiles_per_row=ATLAS_TILES_PER_ROW,
                    )
                )
                atlas_png = indexed_png_from_bgr555(
                    atlas_pixels,
                    palette,
                    width=atlas_width,
                    height=atlas_height,
                    transparent_index=0,
                )
                atlas_id = len(atlases)
                atlas_filename = f"atlas_{atlas_id:03d}.png"
                (output_dir / atlas_filename).write_bytes(atlas_png)
                atlas = {
                    "atlas_id": atlas_id,
                    "png": atlas_filename,
                    "png_sha256": sha256(atlas_png),
                    "width": atlas_width,
                    "height": atlas_height,
                    "bits_per_pixel": spec["bits_per_pixel"],
                    "bytes_per_tile": bytes_per_tile,
                    "tile_count": tile_count,
                    "graphics_sha256": graphics_hash,
                    "palette_sha256": palette_hash,
                    "reuse_count": 0,
                }
                atlases.append(atlas)
                atlas_by_pair[atlas_key] = atlas
            atlas["reuse_count"] += 1

            layer.update(
                {
                    "status": "complete",
                    "gfx": graphics_manifest,
                    "tilemap": tilemap_manifest,
                    "palette": palette_manifest,
                    "tile_count": tile_count,
                    **facts,
                    "layer_png": layer_filename,
                    "layer_png_sha256": sha256(layer_png),
                    "atlas_id": atlas["atlas_id"],
                    "atlas_png": atlas["png"],
                    "atlas_png_sha256": atlas["png_sha256"],
                }
            )
            complete_layer_counts[name] += 1
            complete_layer_count += 1
            unique_graphics.add(graphics_hash)
            unique_tilemaps.add(tilemap_hash)
            unique_palettes.add(palette_hash)
            unique_complete_layers.add(
                (graphics_hash, tilemap_hash, palette_hash)
            )

    manifest = {
        "schema": "tile-assets-bg-export-v2",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "source_bank": "sequel/content/tile-assets/bank.json",
        "supersedes": {
            "artifact": "artifacts/tile-assets-bg-v1",
            "reason": (
                "v1 decoded consumer-proven 8bpp C layers as 4bpp"
            ),
        },
        "source_table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": gba_address(TABLE_OFFSET),
            "entry_count": TABLE_ENTRY_COUNT,
            "entry_size": TABLE_ENTRY_SIZE,
            "sha256": TABLE_SHA256,
            "verification": bank["verification"],
        },
        "scope": {
            "kind": "native static BG layers and complete mixed-depth atlases",
            "final_composite": False,
            "layer_color_depths": {
                "A": "4bpp",
                "B": "4bpp",
                "C": "8bpp",
                "D": "4bpp",
            },
            "runtime_tile_base_and_palette_bank_preserved_as_unknowns": True,
        },
        "descriptor_count": len(descriptors),
        "sentinel_descriptor_ids": list(SENTINEL_DESCRIPTOR_IDS),
        "complete_layer_counts": complete_layer_counts,
        "complete_layer_count": complete_layer_count,
        "partial_layer_count": partial_layer_count,
        "unique_graphics_count": len(unique_graphics),
        "unique_tilemap_count": len(unique_tilemaps),
        "unique_palette_count": len(unique_palettes),
        "unique_atlas_count": len(atlases),
        "unique_complete_layer_count": len(unique_complete_layers),
        "atlases": atlases,
        "descriptors": descriptors,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--from-rom",
        action="store_true",
        help=(
            "Skip the sequel/content/tile-assets/bank.json divergence check "
            "and enumerate descriptor rows directly from ROM."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/tile-assets-bg-v2"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_tile_asset_bg_layers(
        args.root, args.output_dir, args.from_rom
    )
    print(
        f"Exported {manifest['complete_layer_count']} complete BG layers "
        f"and {manifest['unique_atlas_count']} unique atlases "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
