#!/usr/bin/env python3
"""Export the complete 0x0859903C fullscreen BG resource table."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress  # noqa: E402
from tools.gba_image_export import (  # noqa: E402
    indexed_png_from_bgr555,
    read_lz77_record,
)


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x59903C
ENTRY_COUNT = 14
ENTRY_SIZE = 16
TABLE_SIZE = ENTRY_COUNT * ENTRY_SIZE
TABLE_SHA256 = "57e9b8b6b7c3003615c39539f80934f142efeb1e6674114fbaca98bc629f7da2"
CONSUMER_OFFSET = 0x088348
CONSUMER_END_OFFSET = 0x08842A
CONSUMER_SHA256 = "1d581ddbdfb89f17de5b5e52fd1b34d9952fcaddf8e4f24f1f86982facf6db27"
DIRECT_CALLERS = (0x0807AAA6, 0x0808F522, 0x08091716, 0x080930D6)
EMPTY_ENTRY_IDS = (0, 8)
WIDTH_TILES = 32
SOURCE_HEIGHT_TILES = 10
VISIBLE_HEIGHT_TILES = 20
SCREENBLOCK_HEIGHT_TILES = 32
TILEMAP_SIZE = WIDTH_TILES * SOURCE_HEIGHT_TILES * 2
PALETTE_SIZE = 0x180
SCHEMA = "bg-resource-canvases-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _pointer_offset(pointer: int, rom_size: int, label: str) -> int:
    offset = pointer - ROM_BASE
    if pointer < ROM_BASE or offset < 0 or offset >= rom_size:
        raise ValueError(f"{label} pointer is outside ROM: {_address(pointer)}")
    return offset


def validate_output_target(root: Path, output_dir: Path) -> Path:
    root = root.resolve()
    requested = output_dir.expanduser()
    if requested.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = requested.resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be the repository or its ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("existing output target is not a directory")
        try:
            existing = json.loads(
                (target / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            ) from error
        if existing.get("schema") != SCHEMA:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            )
    return target


def _replace_output_transactionally(
    output_dir: Path,
    files: dict[str, bytes],
    manifest: dict[str, Any],
) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.tmp-",
            dir=output_dir.parent,
        )
    )
    backup: Path | None = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            backup = output_dir.parent / (
                f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            )
            output_dir.rename(backup)
        try:
            temporary.rename(output_dir)
        except BaseException:
            if backup is not None and backup.exists() and not output_dir.exists():
                backup.rename(output_dir)
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and output_dir.exists():
            shutil.rmtree(backup)


def render_bg_indices(
    graphics: bytes,
    tilemap: bytes,
    *,
    mode_8bpp: bool,
    height_tiles: int,
) -> tuple[bytes, dict[str, Any]]:
    if len(tilemap) != TILEMAP_SIZE:
        raise ValueError(f"tilemap must be exactly {TILEMAP_SIZE} bytes")
    tile_size = 64 if mode_8bpp else 32
    if not graphics or len(graphics) % tile_size:
        raise ValueError("graphics payload does not contain complete tiles")

    tile_count = len(graphics) // tile_size
    if not SOURCE_HEIGHT_TILES <= height_tiles <= SCREENBLOCK_HEIGHT_TILES:
        raise ValueError("render height must include the 10 source rows")
    fill_entry = 0x001E if mode_8bpp else 0x0000
    entries = list(struct.unpack(f"<{TILEMAP_SIZE // 2}H", tilemap))
    entries.extend(
        [fill_entry] * (WIDTH_TILES * height_tiles - len(entries))
    )
    pixels = bytearray(WIDTH_TILES * 8 * height_tiles * 8)
    maximum_tile_index = 0
    maximum_palette_bank = 0
    horizontal_flips = 0
    vertical_flips = 0
    for tile_y in range(height_tiles):
        for tile_x in range(WIDTH_TILES):
            entry = entries[tile_y * WIDTH_TILES + tile_x]
            tile_index = entry & 0x03FF
            palette_bank = (entry >> 12) & 0x0F
            if tile_index >= tile_count:
                raise ValueError(
                    f"tile index {tile_index} exceeds {tile_count} tiles"
                )
            maximum_tile_index = max(maximum_tile_index, tile_index)
            maximum_palette_bank = max(maximum_palette_bank, palette_bank)
            horizontal_flips += bool(entry & 0x0400)
            vertical_flips += bool(entry & 0x0800)
            tile_offset = tile_index * tile_size
            for pixel_y in range(8):
                source_y = 7 - pixel_y if entry & 0x0800 else pixel_y
                for pixel_x in range(8):
                    source_x = 7 - pixel_x if entry & 0x0400 else pixel_x
                    if mode_8bpp:
                        color = graphics[
                            tile_offset + source_y * 8 + source_x
                        ]
                    else:
                        packed = graphics[
                            tile_offset + source_y * 4 + source_x // 2
                        ]
                        local_color = (
                            packed >> (4 if source_x & 1 else 0)
                        ) & 0x0F
                        color = (
                            0
                            if local_color == 0
                            else palette_bank * 16 + local_color
                        )
                    output_x = tile_x * 8 + pixel_x
                    output_y = tile_y * 8 + pixel_y
                    pixels[output_y * WIDTH_TILES * 8 + output_x] = color
    return bytes(pixels), {
        "tile_count": tile_count,
        "maximum_tile_index": maximum_tile_index,
        "maximum_palette_bank": maximum_palette_bank,
        "horizontal_flip_count": horizontal_flips,
        "vertical_flip_count": vertical_flips,
        "consumer_fill_entry": fill_entry,
        "consumer_filled_row_count": height_tiles - SOURCE_HEIGHT_TILES,
    }


def _resource(
    rom: bytes,
    *,
    entry_id: int,
    kind: str,
    pointer: int,
    files: dict[str, bytes],
) -> tuple[dict[str, Any], bytes]:
    offset = _pointer_offset(pointer, len(rom), f"entry {entry_id} {kind}")
    compressed = read_lz77_record(rom, offset)
    decompressed = lz77_decompress(rom, offset)
    prefix = f"entry-{entry_id:02d}/{kind}"
    compressed_file = f"{prefix}.lz77.bin"
    file = f"{prefix}.bin"
    files[compressed_file] = compressed
    files[file] = decompressed
    return (
        {
            "gba_pointer": _address(pointer),
            "file_offset": offset,
            "compressed_file": compressed_file,
            "compressed_size": len(compressed),
            "compressed_sha256": _sha256(compressed),
            "file": file,
            "decompressed_size": len(decompressed),
            "decompressed_sha256": _sha256(decompressed),
        },
        decompressed,
    )


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    output_dir = validate_output_target(root, output_dir)
    rom = (root / "rom" / "base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")

    table = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if len(table) != TABLE_SIZE or _sha256(table) != TABLE_SHA256:
        raise ValueError("BG resource table SHA-256 mismatch")
    consumer = rom[CONSUMER_OFFSET:CONSUMER_END_OFFSET]
    if _sha256(consumer) != CONSUMER_SHA256:
        raise ValueError("BG resource consumer SHA-256 mismatch")

    files: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []
    graphics_hashes: set[str] = set()
    palette_hashes: set[str] = set()
    tilemap_hashes: set[str] = set()
    for entry_id in range(ENTRY_COUNT):
        values = struct.unpack_from("<4I", table, entry_id * ENTRY_SIZE)
        if entry_id in EMPTY_ENTRY_IDS:
            if values != (0, 0, 0, 0):
                raise ValueError(f"entry {entry_id} must be the empty sentinel")
            continue
        if not all(values[:3]) or values[3] not in (0, 1):
            raise ValueError(f"entry {entry_id} is not a valid BG descriptor")

        graphics_record, graphics = _resource(
            rom,
            entry_id=entry_id,
            kind="graphics",
            pointer=values[0],
            files=files,
        )
        palette_record, palette = _resource(
            rom,
            entry_id=entry_id,
            kind="palette-bgr555",
            pointer=values[1],
            files=files,
        )
        tilemap_record, tilemap = _resource(
            rom,
            entry_id=entry_id,
            kind="tilemap-u16le",
            pointer=values[2],
            files=files,
        )
        if len(palette) != PALETTE_SIZE:
            raise ValueError(f"entry {entry_id} palette size is not 0x180")
        if len(tilemap) != TILEMAP_SIZE:
            raise ValueError(f"entry {entry_id} tilemap size is not 0x280")

        mode_8bpp = bool(values[3])
        source_pixels, source_facts = render_bg_indices(
            graphics,
            tilemap,
            mode_8bpp=mode_8bpp,
            height_tiles=SOURCE_HEIGHT_TILES,
        )
        pixels, render_facts = render_bg_indices(
            graphics,
            tilemap,
            mode_8bpp=mode_8bpp,
            height_tiles=VISIBLE_HEIGHT_TILES,
        )
        if pixels and max(pixels) >= len(palette) // 2:
            raise ValueError(
                f"entry {entry_id} references a palette index outside 0x180"
            )
        png = indexed_png_from_bgr555(
            pixels,
            palette,
            width=WIDTH_TILES * 8,
            height=VISIBLE_HEIGHT_TILES * 8,
        )
        source_png = indexed_png_from_bgr555(
            source_pixels,
            palette,
            width=WIDTH_TILES * 8,
            height=SOURCE_HEIGHT_TILES * 8,
        )
        png_file = f"entry-{entry_id:02d}/canvas.png"
        source_png_file = f"entry-{entry_id:02d}/source-strip.png"
        files[png_file] = png
        files[source_png_file] = source_png
        graphics_hashes.add(graphics_record["decompressed_sha256"])
        palette_hashes.add(palette_record["decompressed_sha256"])
        tilemap_hashes.add(tilemap_record["decompressed_sha256"])
        tilemap_record.update(
            {
                "width_tiles": WIDTH_TILES,
                "height_tiles": SOURCE_HEIGHT_TILES,
                "entry_format": (
                    "bits0..9 tile, bit10 hflip, bit11 vflip, "
                    "bits12..15 palette bank"
                ),
            }
        )
        entries.append(
            {
                "entry_id": entry_id,
                "descriptor_file_offset": TABLE_OFFSET + entry_id * ENTRY_SIZE,
                "descriptor_gba_address": _address(
                    ROM_BASE + TABLE_OFFSET + entry_id * ENTRY_SIZE
                ),
                "mode_flag": values[3],
                "pixel_mode": "8bpp" if mode_8bpp else "4bpp",
                "graphics": graphics_record,
                "palette": palette_record,
                "tilemap": tilemap_record,
                "canvas": {
                    "png": png_file,
                    "width": WIDTH_TILES * 8,
                    "height": VISIBLE_HEIGHT_TILES * 8,
                    "indexed_pixel_sha256": _sha256(pixels),
                    "png_sha256": _sha256(png),
                    **render_facts,
                },
                "source_strip": {
                    "png": source_png_file,
                    "width": WIDTH_TILES * 8,
                    "height": SOURCE_HEIGHT_TILES * 8,
                    "indexed_pixel_sha256": _sha256(source_pixels),
                    "png_sha256": _sha256(source_png),
                    **source_facts,
                },
            }
        )

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "rom": {
            "file": "rom/base.gba",
            "sha256": ROM_SHA256,
        },
        "table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + TABLE_OFFSET),
            "gba_end": _address(ROM_BASE + TABLE_OFFSET + TABLE_SIZE),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "empty_entry_ids": list(EMPTY_ENTRY_IDS),
            "sha256": TABLE_SHA256,
        },
        "consumer": {
            "gba_start": _address(ROM_BASE + CONSUMER_OFFSET),
            "gba_end": _address(ROM_BASE + CONSUMER_END_OFFSET),
            "sha256": CONSUMER_SHA256,
            "direct_callers": list(DIRECT_CALLERS),
            "descriptor_formula": "0x0859903C + entry_id * 0x10",
            "graphics_destination": "0x06000000 + char_base_block * 0x4000",
            "palette_destination": "0x05000000",
            "tilemap_destination": "0x06000000 + screen_base_block * 0x0800",
            "mode_flag_effect": "nonzero sets BG control bit 7 (8bpp)",
            "post_decompression_fill": (
                "rows 10..31: 4bpp entry 0x0000, "
                "8bpp entry 0x001E"
            ),
            "entry_selection": {
                "battle_header_formula": (
                    "u8[0x0853D910 + battle_id * 0x20 + 0x1C]"
                ),
                "battle_header_entry_distribution": {
                    "1": 23,
                    "2": 3,
                    "3": 5,
                    "4": 4,
                    "5": 1,
                    "6": 1,
                    "7": 10,
                },
                "special_input_formula": (
                    "input_id > 49: entry_id = input_id - 41"
                ),
                "fixed_entry_calls": {
                    "0x08091716": 9,
                    "0x080930D6": 1,
                },
                "loader_bounds_check": False,
            },
        },
        "summary": {
            "canvas_count": len(entries),
            "4bpp_canvas_count": sum(
                entry["pixel_mode"] == "4bpp" for entry in entries
            ),
            "8bpp_canvas_count": sum(
                entry["pixel_mode"] == "8bpp" for entry in entries
            ),
            "unique_graphics_count": len(graphics_hashes),
            "unique_palette_count": len(palette_hashes),
            "unique_tilemap_count": len(tilemap_hashes),
        },
        "entries": entries,
        "scope": {
            "all_static_table_entries_exported": True,
            "full_source_space_canvases_rendered": True,
            "4bpp_and_8bpp_modes_verified": True,
            "runtime_entry_selection_complete": False,
            "scrolling_and_layer_composition_complete": False,
            "scene_names_complete": False,
        },
    }
    _replace_output_transactionally(output_dir, files, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / SCHEMA,
    )
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output_dir)
    print(
        json.dumps(
            {
                "artifact": str(args.output_dir),
                "canvases": manifest["summary"]["canvas_count"],
                "4bpp": manifest["summary"]["4bpp_canvas_count"],
                "8bpp": manifest["summary"]["8bpp_canvas_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
