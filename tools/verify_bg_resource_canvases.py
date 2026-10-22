#!/usr/bin/env python3
"""Independently verify the 0x0859903C BG canvas artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image


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
DIRECT_CALLERS = [0x0807AAA6, 0x0808F522, 0x08091716, 0x080930D6]
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


def _read_lz77(rom: bytes, offset: int) -> tuple[bytes, bytes]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"resource is not LZ77 at 0x{offset:06X}")
    declared_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    output = bytearray()
    cursor = offset + 4
    while len(output) < declared_size:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= declared_size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 back-reference")
                length = (rom[cursor] >> 4) + 3
                displacement = (
                    ((rom[cursor] & 0x0F) << 8) | rom[cursor + 1]
                )
                cursor += 2
                source = len(output) - displacement - 1
                if source < 0 or len(output) + length > declared_size:
                    raise ValueError("invalid LZ77 back-reference")
                for _ in range(length):
                    output.append(output[source])
                    source += 1
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return rom[offset:cursor], bytes(output)


def _render(
    graphics: bytes,
    tilemap: bytes,
    *,
    mode_8bpp: bool,
    height_tiles: int,
) -> tuple[bytes, dict[str, int]]:
    if len(tilemap) != TILEMAP_SIZE:
        raise ValueError("invalid tilemap size")
    tile_size = 64 if mode_8bpp else 32
    if not graphics or len(graphics) % tile_size:
        raise ValueError("invalid graphics tile alignment")
    tile_count = len(graphics) // tile_size
    if not SOURCE_HEIGHT_TILES <= height_tiles <= SCREENBLOCK_HEIGHT_TILES:
        raise ValueError("invalid render height")
    fill_entry = 0x001E if mode_8bpp else 0x0000
    entries = list(struct.unpack(f"<{TILEMAP_SIZE // 2}H", tilemap))
    entries.extend(
        [fill_entry] * (WIDTH_TILES * height_tiles - len(entries))
    )
    pixels = bytearray(256 * height_tiles * 8)
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
                raise ValueError("tilemap index exceeds graphics")
            maximum_tile_index = max(maximum_tile_index, tile_index)
            maximum_palette_bank = max(maximum_palette_bank, palette_bank)
            horizontal_flips += int(bool(entry & 0x0400))
            vertical_flips += int(bool(entry & 0x0800))
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
                    pixels[
                        (tile_y * 8 + pixel_y) * 256
                        + tile_x * 8
                        + pixel_x
                    ] = color
    return bytes(pixels), {
        "tile_count": tile_count,
        "maximum_tile_index": maximum_tile_index,
        "maximum_palette_bank": maximum_palette_bank,
        "horizontal_flip_count": horizontal_flips,
        "vertical_flip_count": vertical_flips,
        "consumer_fill_entry": fill_entry,
        "consumer_filled_row_count": height_tiles - SOURCE_HEIGHT_TILES,
    }


def _palette_rgb(raw: bytes) -> list[int]:
    result: list[int] = []
    for offset in range(0, len(raw), 2):
        value = struct.unpack_from("<H", raw, offset)[0]
        for component in (
            value & 0x1F,
            (value >> 5) & 0x1F,
            (value >> 10) & 0x1F,
        ):
            result.append((component << 3) | (component >> 2))
    return result


def _expect_equal(
    errors: list[str],
    label: str,
    actual: Any,
    expected: Any,
) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    expected_files = {"manifest.json"}
    verified_canvases = 0
    try:
        root = root.resolve()
        artifact_dir = artifact_dir.resolve()
        rom = (root / "rom" / "base.gba").read_bytes()
        _expect_equal(errors, "ROM SHA-256", _sha256(rom), ROM_SHA256)
        table = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
        _expect_equal(errors, "table size", len(table), TABLE_SIZE)
        _expect_equal(errors, "table SHA-256", _sha256(table), TABLE_SHA256)
        consumer = rom[CONSUMER_OFFSET:CONSUMER_END_OFFSET]
        _expect_equal(
            errors,
            "consumer SHA-256",
            _sha256(consumer),
            CONSUMER_SHA256,
        )

        manifest = json.loads(
            (artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
        _expect_equal(errors, "schema", manifest.get("schema"), SCHEMA)
        _expect_equal(
            errors,
            "ROM metadata",
            manifest.get("rom"),
            {
                "file": "rom/base.gba",
                "sha256": ROM_SHA256,
            },
        )
        expected_table = {
            "file_offset": TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + TABLE_OFFSET),
            "gba_end": _address(ROM_BASE + TABLE_OFFSET + TABLE_SIZE),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "empty_entry_ids": list(EMPTY_ENTRY_IDS),
            "sha256": TABLE_SHA256,
        }
        _expect_equal(errors, "table metadata", manifest.get("table"), expected_table)
        expected_consumer = {
            "gba_start": _address(ROM_BASE + CONSUMER_OFFSET),
            "gba_end": _address(ROM_BASE + CONSUMER_END_OFFSET),
            "sha256": CONSUMER_SHA256,
            "direct_callers": DIRECT_CALLERS,
            "descriptor_formula": "0x0859903C + entry_id * 0x10",
            "graphics_destination": (
                "0x06000000 + char_base_block * 0x4000"
            ),
            "palette_destination": "0x05000000",
            "tilemap_destination": (
                "0x06000000 + screen_base_block * 0x0800"
            ),
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
        }
        _expect_equal(
            errors,
            "consumer metadata",
            manifest.get("consumer"),
            expected_consumer,
        )

        entries = manifest.get("entries")
        if not isinstance(entries, list):
            errors.append("entries must be a list")
            entries = []
        expected_ids = list(range(1, 8)) + list(range(9, 14))
        _expect_equal(
            errors,
            "entry IDs",
            [entry.get("entry_id") for entry in entries],
            expected_ids,
        )
        graphics_hashes: set[str] = set()
        palette_hashes: set[str] = set()
        tilemap_hashes: set[str] = set()
        for index, entry_id in enumerate(expected_ids):
            if index >= len(entries):
                break
            entry = entries[index]
            values = struct.unpack_from(
                "<4I",
                table,
                entry_id * ENTRY_SIZE,
            )
            _expect_equal(
                errors,
                f"entry {entry_id} descriptor_file_offset",
                entry.get("descriptor_file_offset"),
                TABLE_OFFSET + entry_id * ENTRY_SIZE,
            )
            _expect_equal(
                errors,
                f"entry {entry_id} descriptor_gba_address",
                entry.get("descriptor_gba_address"),
                _address(
                    ROM_BASE + TABLE_OFFSET + entry_id * ENTRY_SIZE
                ),
            )
            _expect_equal(
                errors,
                f"entry {entry_id} mode_flag",
                entry.get("mode_flag"),
                values[3],
            )
            _expect_equal(
                errors,
                f"entry {entry_id} pixel_mode",
                entry.get("pixel_mode"),
                "8bpp" if values[3] else "4bpp",
            )
            resources: dict[str, bytes] = {}
            for key, pointer, filename_kind in (
                ("graphics", values[0], "graphics"),
                ("palette", values[1], "palette-bgr555"),
                ("tilemap", values[2], "tilemap-u16le"),
            ):
                offset = pointer - ROM_BASE
                compressed, decompressed = _read_lz77(rom, offset)
                record = entry.get(key, {})
                compressed_file = (
                    f"entry-{entry_id:02d}/{filename_kind}.lz77.bin"
                )
                file = f"entry-{entry_id:02d}/{filename_kind}.bin"
                expected_files.update((compressed_file, file))
                for label, actual, expected in (
                    ("gba_pointer", record.get("gba_pointer"), _address(pointer)),
                    ("file_offset", record.get("file_offset"), offset),
                    (
                        "compressed_file",
                        record.get("compressed_file"),
                        compressed_file,
                    ),
                    (
                        "compressed_size",
                        record.get("compressed_size"),
                        len(compressed),
                    ),
                    (
                        "compressed_sha256",
                        record.get("compressed_sha256"),
                        _sha256(compressed),
                    ),
                    ("file", record.get("file"), file),
                    (
                        "decompressed_size",
                        record.get("decompressed_size"),
                        len(decompressed),
                    ),
                    (
                        "decompressed_sha256",
                        record.get("decompressed_sha256"),
                        _sha256(decompressed),
                    ),
                ):
                    _expect_equal(
                        errors,
                        f"entry {entry_id} {key}.{label}",
                        actual,
                        expected,
                    )
                for relative, expected_data in (
                    (compressed_file, compressed),
                    (file, decompressed),
                ):
                    path = artifact_dir / relative
                    try:
                        actual_data = path.read_bytes()
                    except OSError as error:
                        errors.append(f"{relative}: {error}")
                    else:
                        if actual_data != expected_data:
                            errors.append(f"{relative}: content mismatch")
                resources[key] = decompressed

            tilemap_record = entry.get("tilemap", {})
            for key, expected in {
                "width_tiles": WIDTH_TILES,
                "height_tiles": SOURCE_HEIGHT_TILES,
                "entry_format": (
                    "bits0..9 tile, bit10 hflip, bit11 vflip, "
                    "bits12..15 palette bank"
                ),
            }.items():
                _expect_equal(
                    errors,
                    f"entry {entry_id} tilemap.{key}",
                    tilemap_record.get(key),
                    expected,
                )

            if len(resources.get("palette", b"")) != PALETTE_SIZE:
                errors.append(f"entry {entry_id}: palette size mismatch")
                continue
            if len(resources.get("tilemap", b"")) != TILEMAP_SIZE:
                errors.append(f"entry {entry_id}: tilemap size mismatch")
                continue
            source_pixels, source_facts = _render(
                resources["graphics"],
                resources["tilemap"],
                mode_8bpp=bool(values[3]),
                height_tiles=SOURCE_HEIGHT_TILES,
            )
            pixels, facts = _render(
                resources["graphics"],
                resources["tilemap"],
                mode_8bpp=bool(values[3]),
                height_tiles=VISIBLE_HEIGHT_TILES,
            )
            if pixels and max(pixels) >= len(resources["palette"]) // 2:
                errors.append(f"entry {entry_id}: palette index out of range")
                continue
            canvas = entry.get("canvas", {})
            png_file = f"entry-{entry_id:02d}/canvas.png"
            expected_files.add(png_file)
            for key, expected in {
                "png": png_file,
                "width": 256,
                "height": 160,
                "indexed_pixel_sha256": _sha256(pixels),
                **facts,
            }.items():
                _expect_equal(
                    errors,
                    f"entry {entry_id} canvas.{key}",
                    canvas.get(key),
                    expected,
                )
            png_path = artifact_dir / png_file
            try:
                png_bytes = png_path.read_bytes()
                _expect_equal(
                    errors,
                    f"entry {entry_id} canvas.png_sha256",
                    canvas.get("png_sha256"),
                    _sha256(png_bytes),
                )
                with Image.open(png_path) as image:
                    _expect_equal(
                        errors,
                        f"entry {entry_id} PNG format",
                        image.format,
                        "PNG",
                    )
                    image.load()
                    _expect_equal(
                        errors,
                        f"entry {entry_id} PNG mode",
                        image.mode,
                        "P",
                    )
                    _expect_equal(
                        errors,
                        f"entry {entry_id} PNG size",
                        image.size,
                        (256, 160),
                    )
                    _expect_equal(
                        errors,
                        f"entry {entry_id} PNG pixels",
                        image.tobytes(),
                        pixels,
                    )
                    palette = image.getpalette() or []
                    expected_palette = _palette_rgb(resources["palette"])
                    _expect_equal(
                        errors,
                        f"entry {entry_id} PNG palette",
                        palette[: len(expected_palette)],
                        expected_palette,
                    )
                    if "transparency" in image.info:
                        errors.append(
                            f"entry {entry_id} PNG unexpectedly has transparency"
                        )
            except (OSError, ValueError) as error:
                errors.append(f"{png_file}: {error}")

            source_strip = entry.get("source_strip", {})
            source_png_file = f"entry-{entry_id:02d}/source-strip.png"
            expected_files.add(source_png_file)
            for key, expected in {
                "png": source_png_file,
                "width": 256,
                "height": 80,
                "indexed_pixel_sha256": _sha256(source_pixels),
                **source_facts,
            }.items():
                _expect_equal(
                    errors,
                    f"entry {entry_id} source_strip.{key}",
                    source_strip.get(key),
                    expected,
                )
            source_path = artifact_dir / source_png_file
            try:
                source_png = source_path.read_bytes()
                _expect_equal(
                    errors,
                    f"entry {entry_id} source_strip.png_sha256",
                    source_strip.get("png_sha256"),
                    _sha256(source_png),
                )
                with Image.open(source_path) as image:
                    _expect_equal(
                        errors,
                        f"entry {entry_id} source PNG format",
                        image.format,
                        "PNG",
                    )
                    image.load()
                    _expect_equal(
                        errors,
                        f"entry {entry_id} source PNG mode",
                        image.mode,
                        "P",
                    )
                    _expect_equal(
                        errors,
                        f"entry {entry_id} source PNG size",
                        image.size,
                        (256, 80),
                    )
                    _expect_equal(
                        errors,
                        f"entry {entry_id} source PNG pixels",
                        image.tobytes(),
                        source_pixels,
                    )
                    palette = image.getpalette() or []
                    expected_palette = _palette_rgb(resources["palette"])
                    _expect_equal(
                        errors,
                        f"entry {entry_id} source PNG palette",
                        palette[: len(expected_palette)],
                        expected_palette,
                    )
                    if "transparency" in image.info:
                        errors.append(
                            f"entry {entry_id} source PNG unexpectedly "
                            "has transparency"
                        )
            except (OSError, ValueError) as error:
                errors.append(f"{source_png_file}: {error}")

            graphics_hashes.add(_sha256(resources["graphics"]))
            palette_hashes.add(_sha256(resources["palette"]))
            tilemap_hashes.add(_sha256(resources["tilemap"]))
            if not any(
                error.startswith(f"entry {entry_id} ")
                or error.startswith(f"entry-{entry_id:02d}/")
                for error in errors
            ):
                verified_canvases += 1

        expected_summary = {
            "canvas_count": 12,
            "4bpp_canvas_count": 7,
            "8bpp_canvas_count": 5,
            "unique_graphics_count": len(graphics_hashes),
            "unique_palette_count": len(palette_hashes),
            "unique_tilemap_count": len(tilemap_hashes),
        }
        _expect_equal(
            errors,
            "summary",
            manifest.get("summary"),
            expected_summary,
        )
        expected_scope = {
            "all_static_table_entries_exported": True,
            "full_source_space_canvases_rendered": True,
            "4bpp_and_8bpp_modes_verified": True,
            "runtime_entry_selection_complete": False,
            "scrolling_and_layer_composition_complete": False,
            "scene_names_complete": False,
        }
        _expect_equal(errors, "scope", manifest.get("scope"), expected_scope)
        actual_files = {
            path.relative_to(artifact_dir).as_posix()
            for path in artifact_dir.rglob("*")
            if path.is_file()
        }
        _expect_equal(
            errors,
            "artifact file set",
            sorted(actual_files),
            sorted(expected_files),
        )
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as error:
        errors.append(str(error))

    verified = not errors and verified_canvases == 12
    return {
        "verified": verified,
        "errors": errors,
        "canvases": 12 if verified else 0,
        "expected_canvases": 12,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "artifacts"
        / SCHEMA,
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
