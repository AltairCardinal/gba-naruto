#!/usr/bin/env python3
"""Export all 24 ROM-backed story visual text layers as indexed PNG."""

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
    sha256,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x54229C
TABLE_ENTRY_COUNT = 24
TABLE_ENTRY_SIZE = 0x10
LINKED_DESCRIPTOR_TABLE_OFFSET = 0x5A320C
LINKED_DESCRIPTOR_COUNT = 79
LINKED_DESCRIPTOR_SIZE = 0x44
LINKED_DESCRIPTOR_TABLE_SHA256 = (
    "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
)
STORY_TILE_BASE = 0x140
SCREEN_TILE_COLUMNS = 32
SCREEN_TILE_ROWS = 32
CANVAS_WIDTH = SCREEN_TILE_COLUMNS * 8
CANVAS_HEIGHT = SCREEN_TILE_ROWS * 8
PALETTE_SIZE = 32
TILEMAP_SIZE = SCREEN_TILE_COLUMNS * SCREEN_TILE_ROWS * 2


def render_story_visual_indices(
    tiles: bytes,
    tilemap: bytes,
    *,
    tile_base: int = STORY_TILE_BASE,
) -> bytes:
    """Render one 4bpp GBA text-BG screen block to local palette indices."""
    if not tiles or len(tiles) % 32:
        raise ValueError("story visual graphics must contain complete 4bpp tiles")
    if len(tilemap) != TILEMAP_SIZE:
        raise ValueError(
            f"story visual tilemap must be {TILEMAP_SIZE} bytes"
        )
    entries = struct.unpack("<1024H", tilemap)
    tile_count = len(tiles) // 32
    pixels = bytearray(CANVAS_WIDTH * CANVAS_HEIGHT)
    for y in range(CANVAS_HEIGHT):
        tile_y, local_y = divmod(y, 8)
        for x in range(CANVAS_WIDTH):
            tile_x, local_x = divmod(x, 8)
            entry = entries[tile_y * SCREEN_TILE_COLUMNS + tile_x]
            source_x = 7 - local_x if entry & (1 << 10) else local_x
            source_y = 7 - local_y if entry & (1 << 11) else local_y
            source_tile = (entry & 0x03FF) - tile_base
            if not 0 <= source_tile < tile_count:
                raise ValueError(
                    f"tilemap references tile {entry & 0x03FF}, outside "
                    f"{tile_base}..{tile_base + tile_count - 1}"
                )
            source = (
                source_tile * 32
                + source_y * 4
                + source_x // 2
            )
            packed = tiles[source]
            pixels[y * CANVAS_WIDTH + x] = (
                packed >> (4 if source_x & 1 else 0)
            ) & 0x0F
    return bytes(pixels)


def _extract_component(
    rom: bytes,
    pointer: int,
    *,
    expected_size: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    offset = pointer - ROM_BASE
    if not 0 <= offset < len(rom):
        raise ValueError(
            f"story visual pointer is outside ROM: {gba_pointer(pointer)}"
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


def _load_banks(
    root: Path,
    rom: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bank = json.loads(
        (root / "sequel/content/battle-encounters/bank.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        bank.get("table_offset") != TABLE_OFFSET
        or bank.get("entry_count") != TABLE_ENTRY_COUNT
        or bank.get("entry_size") != TABLE_ENTRY_SIZE
        or len(bank.get("entries", [])) != TABLE_ENTRY_COUNT
        or bank.get("verification") not in {"code_verified", "runtime_verified"}
    ):
        raise ValueError("unexpected story visual descriptor bank")

    linked = json.loads(
        (root / "sequel/content/tile-assets/bank.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        linked.get("table_offset") != LINKED_DESCRIPTOR_TABLE_OFFSET
        or linked.get("entry_count") != LINKED_DESCRIPTOR_COUNT
        or linked.get("entry_size") != LINKED_DESCRIPTOR_SIZE
        or len(linked.get("entries", [])) != LINKED_DESCRIPTOR_COUNT
        or linked.get("verification") not in {"code_verified", "runtime_verified"}
    ):
        raise ValueError("unexpected linked visual descriptor bank")

    for index, entry in enumerate(bank["entries"]):
        descriptor_offset = TABLE_OFFSET + index * TABLE_ENTRY_SIZE
        if entry.get("_index") != index:
            raise ValueError(f"story visual row {index} has wrong index")
        if entry.get("_raw_offset") != descriptor_offset:
            raise ValueError(f"story visual row {index} has wrong offset")
        expected = struct.unpack_from("<IIII", rom, descriptor_offset)
        actual = (
            entry.get("gfx_lz_ptr"),
            entry.get("palette_lz_ptr"),
            entry.get("tilemap_lz_ptr"),
            entry.get("config_id"),
        )
        if actual != expected:
            raise ValueError(
                f"story visual bank diverges from ROM at row {index}"
            )
        if not 0 <= expected[3] < LINKED_DESCRIPTOR_COUNT:
            raise ValueError(
                f"story visual row {index} links descriptor {expected[3]}, "
                "outside the linked bank"
            )

    linked_table_end = (
        LINKED_DESCRIPTOR_TABLE_OFFSET
        + LINKED_DESCRIPTOR_COUNT * LINKED_DESCRIPTOR_SIZE
    )
    linked_table = rom[LINKED_DESCRIPTOR_TABLE_OFFSET:linked_table_end]
    if sha256(linked_table) != LINKED_DESCRIPTOR_TABLE_SHA256:
        raise ValueError("linked visual descriptor table hash mismatch")
    for index, entry in enumerate(linked["entries"]):
        row_offset = (
            LINKED_DESCRIPTOR_TABLE_OFFSET
            + index * LINKED_DESCRIPTOR_SIZE
        )
        if entry.get("_index") != index:
            raise ValueError(
                f"linked visual descriptor {index} has wrong index"
            )
        if entry.get("_raw_offset") != row_offset:
            raise ValueError(
                f"linked visual descriptor {index} has wrong offset"
            )
        expected = struct.unpack_from("<17I", rom, row_offset)
        actual = tuple(entry.get(f"word_{word:02d}") for word in range(17))
        if actual != expected:
            raise ValueError(
                "linked visual descriptor bank diverges from ROM "
                f"at row {index}"
            )
    return bank, linked


def export_story_visual_layers(
    root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Export all layers and return a ROM-bound deterministic manifest."""
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
    bank, linked = _load_banks(root, rom)
    output_dir.mkdir(parents=True, exist_ok=True)

    layers: list[dict[str, Any]] = []
    unique_graphics: set[str] = set()
    unique_palettes: set[str] = set()
    unique_tilemaps: set[str] = set()
    unique_layers: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(bank["entries"]):
        graphics, graphics_manifest = _extract_component(
            rom,
            entry["gfx_lz_ptr"],
        )
        palette, palette_manifest = _extract_component(
            rom,
            entry["palette_lz_ptr"],
            expected_size=PALETTE_SIZE,
        )
        tilemap, tilemap_manifest = _extract_component(
            rom,
            entry["tilemap_lz_ptr"],
            expected_size=TILEMAP_SIZE,
        )
        if len(graphics) % 32:
            raise ValueError(
                f"story visual {index} graphics is not whole 4bpp tiles"
            )

        tile_count = len(graphics) // 32
        entries = struct.unpack("<1024H", tilemap)
        tile_indices = {value & 0x03FF for value in entries}
        palette_banks = sorted({value >> 12 for value in entries})
        expected_tiles = set(
            range(STORY_TILE_BASE, STORY_TILE_BASE + tile_count)
        )
        if tile_indices != expected_tiles:
            raise ValueError(
                f"story visual {index} tilemap does not cover its exact "
                "contiguous tile resource"
            )
        if palette_banks != [15]:
            raise ValueError(
                f"story visual {index} uses palette banks {palette_banks}, "
                "expected bank 15"
            )

        pixels = render_story_visual_indices(graphics, tilemap)
        png = indexed_png_from_bgr555(
            pixels,
            palette,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            transparent_index=0,
        )
        config_id = entry["config_id"]
        filename = (
            f"story_visual_layer_{index:02d}_config_{config_id:02d}.png"
        )
        (output_dir / filename).write_bytes(png)

        graphics_hash = graphics_manifest["decompressed_sha256"]
        palette_hash = palette_manifest["decompressed_sha256"]
        tilemap_hash = tilemap_manifest["decompressed_sha256"]
        unique_graphics.add(graphics_hash)
        unique_palettes.add(palette_hash)
        unique_tilemaps.add(tilemap_hash)
        unique_layers.add((graphics_hash, palette_hash, tilemap_hash))
        descriptor_offset = TABLE_OFFSET + index * TABLE_ENTRY_SIZE
        layers.append(
            {
                "layer_id": index,
                "descriptor_file_offset": descriptor_offset,
                "descriptor_gba_address": gba_address(descriptor_offset),
                "config_id": config_id,
                "linked_visual_descriptor_id": config_id,
                "gfx_pointer": gba_pointer(entry["gfx_lz_ptr"]),
                "palette_pointer": gba_pointer(entry["palette_lz_ptr"]),
                "tilemap_pointer": gba_pointer(entry["tilemap_lz_ptr"]),
                "gfx": graphics_manifest,
                "palette": palette_manifest,
                "tilemap": tilemap_manifest,
                "tile_base": STORY_TILE_BASE,
                "tile_count": tile_count,
                "tile_index_min": min(tile_indices),
                "tile_index_max": max(tile_indices),
                "palette_banks": palette_banks,
                "horizontal_flip_used": any(
                    value & (1 << 10) for value in entries
                ),
                "vertical_flip_used": any(
                    value & (1 << 11) for value in entries
                ),
                "png": filename,
                "png_sha256": sha256(png),
            }
        )

    table_bytes = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    manifest = {
        "schema": "story-visual-layer-export-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "source_bank": "sequel/content/battle-encounters/bank.json",
        "source_table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": gba_address(TABLE_OFFSET),
            "entry_count": TABLE_ENTRY_COUNT,
            "entry_size": TABLE_ENTRY_SIZE,
            "sha256": sha256(table_bytes),
            # This export consumes only the ROM-backed descriptor identity.
            # Preserve that stable floor after the bank gains separate runtime
            # evidence so existing image artifacts remain byte-identical.
            "verification": "code_verified",
        },
        "linked_visual_descriptor_bank": {
            "path": "sequel/content/tile-assets/bank.json",
            "file_offset": LINKED_DESCRIPTOR_TABLE_OFFSET,
            "gba_address": gba_address(LINKED_DESCRIPTOR_TABLE_OFFSET),
            "entry_count": linked["entry_count"],
            "entry_size": linked["entry_size"],
            "sha256": LINKED_DESCRIPTOR_TABLE_SHA256,
            # This export only consumes the ROM-backed table identity.  Keep the
            # manifest's claim at that stable floor so a later runtime upgrade
            # does not invalidate otherwise byte-identical image artifacts.
            "verification": "code_verified",
            "relationship": (
                "consumer stores config_id and indexes this 0x44-byte table; "
                "the linked visual is outside this transparent BG3 layer"
            ),
        },
        "runtime_layout": {
            "background": "BG3",
            "character_base": "0x0600C000",
            "graphics_destination": "0x0600E800",
            "tile_base": STORY_TILE_BASE,
            "palette_destination": "0x050001E0",
            "palette_bank": 15,
            "tilemap_destination": "0x06001800",
            "screen_block": 3,
            "canvas": [CANVAS_WIDTH, CANVAS_HEIGHT],
            "transparent_palette_index": 0,
        },
        "layer_count": len(layers),
        "unique_graphics_count": len(unique_graphics),
        "unique_palette_count": len(unique_palettes),
        "unique_tilemap_count": len(unique_tilemaps),
        "unique_layer_count": len(unique_layers),
        "layers": layers,
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
        "--output-dir",
        type=Path,
        default=Path("artifacts/story-visual-layers-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_story_visual_layers(args.root, args.output_dir)
    print(
        f"Exported {manifest['layer_count']} story visual layers "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
