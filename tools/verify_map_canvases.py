#!/usr/bin/env python3
"""Independently verify the complete 47-row battle-map canvas export."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x53D910
TABLE_ADDRESS = ROM_BASE + TABLE_OFFSET
ENTRY_COUNT = 47
ENTRY_SIZE = 32
TABLE_SHA256 = "977b4393a2c5d37124d09e772de42f11d2d9abff9ec832d1160aeeb194a6566c"
MAP_40_TILEMAP_SHA256 = (
    "adc300b0566b30eb5988d7974e237dd5a4c16847908b2cffaf48bcb4f09015b9"
)
MAP_40_PIXELS_SHA256 = (
    "a4dd82c0d71778e2defc354375cb4819ceea66c5934af48725d6c9dad40cf419"
)

RESOURCE_SPECS = {
    "tile_graphics": (1, "tile-graphics", ".4bpp.bin"),
    "bg_palette": (2, "bg-palettes", ".bgr555.bin"),
    "primary_layout": (3, "primary-layouts", ".u32le.bin"),
    "alternate_layout": (4, "alternate-layouts", ".u32le.bin"),
    "metatile_definitions": (5, "metatile-definitions", ".u16le.bin"),
    "collision_grid": (6, "collision-grids", ".u16le.bin"),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _read_lz77(rom: bytes, offset: int) -> bytes:
    if not 0 <= offset <= len(rom) - 4 or rom[offset] != 0x10:
        raise ValueError(f"not GBA LZ77 at 0x{offset:06X}")
    target_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    output = bytearray()
    cursor = offset + 4
    mask = 0
    flags = 0
    while len(output) < target_size:
        if mask == 0:
            if cursor >= len(rom):
                raise ValueError("truncated LZ77 flags")
            flags = rom[cursor]
            cursor += 1
            mask = 0x80
        if flags & mask:
            if cursor + 2 > len(rom):
                raise ValueError("truncated LZ77 copy")
            code = int.from_bytes(rom[cursor : cursor + 2], "big")
            cursor += 2
            count = (code >> 12) + 3
            distance = (code & 0x0FFF) + 1
            if distance > len(output) or len(output) + count > target_size:
                raise ValueError("invalid LZ77 copy")
            for _ in range(count):
                output.append(output[-distance])
        else:
            if cursor >= len(rom):
                raise ValueError("truncated LZ77 literal")
            output.append(rom[cursor])
            cursor += 1
        mask >>= 1
    return bytes(output)


def _row(rom: bytes, map_id: int) -> dict[str, Any]:
    offset = TABLE_OFFSET + map_id * ENTRY_SIZE
    fields = struct.unpack_from("<8I", rom, offset)
    width = fields[0] & 0xFFFF
    height = fields[0] >> 16

    def pointer(index: int) -> int | None:
        value = fields[index]
        if value == 0:
            return None
        if not ROM_BASE <= value < ROM_BASE + len(rom):
            raise ValueError(f"map {map_id} field {index} pointer is outside ROM")
        return value - ROM_BASE

    return {
        "map_id": map_id,
        "offset": offset,
        "raw": rom[offset : offset + ENTRY_SIZE],
        "width": width,
        "height": height,
        "pointers": {name: pointer(index) for name, (index, _, _) in RESOURCE_SPECS.items()},
        "flags": fields[7],
    }


def _expand_layout(
    width: int,
    height: int,
    layout: bytes,
    metatiles: bytes,
) -> tuple[list[int], list[int]]:
    coarse_width = width // 4
    coarse_height = height // 2
    if width % 4 or height % 2:
        raise ValueError("coarse dimensions are not 4x2 aligned")
    if len(layout) != coarse_width * coarse_height * 4:
        raise ValueError("layout size mismatch")
    if not metatiles or len(metatiles) % 8:
        raise ValueError("metatile size mismatch")
    tilemap = [0] * (width * height)
    used: set[int] = set()
    for coarse_index, packed in enumerate(
        struct.iter_unpack("<I", layout)
    ):
        coarse_x = coarse_index % coarse_width
        coarse_y = coarse_index // coarse_width
        value = packed[0]
        for half in range(2):
            metatile = (value >> (half * 16)) & 0xFFFF
            used.add(metatile)
            start = metatile * 8
            if start + 8 > len(metatiles):
                raise ValueError(f"metatile {metatile} is outside definitions")
            words = struct.unpack_from("<4H", metatiles, start)
            destination_x = coarse_x * 4 + half * 2
            destination_y = coarse_y * 2
            tilemap[destination_y * width + destination_x] = words[0]
            tilemap[destination_y * width + destination_x + 1] = words[1]
            tilemap[(destination_y + 1) * width + destination_x] = words[2]
            tilemap[(destination_y + 1) * width + destination_x + 1] = words[3]
    return tilemap, sorted(used)


def _pixels_reference(
    width_tiles: int,
    height_tiles: int,
    tilemap: list[int],
    graphics: bytes,
    palette: bytes,
) -> tuple[bytes, dict[str, Any]]:
    tile_count = len(graphics) // 32
    palette_banks = len(palette) // 32
    if not graphics or len(graphics) % 32 or not palette or len(palette) % 32:
        raise ValueError("unaligned graphics or palette")
    width = width_tiles * 8
    height = height_tiles * 8
    pixels = bytearray(width * height)
    banks: Counter[int] = Counter()
    horizontal = 0
    vertical = 0
    maximum_tile = 0
    for map_index, entry in enumerate(tilemap):
        tile = entry & 0x03FF
        bank = entry >> 12
        if tile >= tile_count or bank >= palette_banks:
            raise ValueError("tile or palette bank outside resource")
        banks[bank] += 1
        horizontal += bool(entry & 0x0400)
        vertical += bool(entry & 0x0800)
        maximum_tile = max(maximum_tile, tile)
        destination_tile_x = map_index % width_tiles
        destination_tile_y = map_index // width_tiles
        for local in range(64):
            output_x = local % 8
            output_y = local // 8
            source_x = 7 - output_x if entry & 0x0400 else output_x
            source_y = 7 - output_y if entry & 0x0800 else output_y
            byte = graphics[tile * 32 + source_y * 4 + source_x // 2]
            color = (byte >> ((source_x & 1) * 4)) & 0x0F
            pixels[
                (destination_tile_y * 8 + output_y) * width
                + destination_tile_x * 8
                + output_x
            ] = 0 if color == 0 else bank * 16 + color
    return bytes(pixels), {
        "maximum_tile_index": maximum_tile,
        "palette_bank_usage": {
            str(bank): count for bank, count in sorted(banks.items())
        },
        "horizontal_flip_count": horizontal,
        "vertical_flip_count": vertical,
    }


def _palette_rgb(palette: bytes) -> list[int]:
    rgb: list[int] = []
    for offset in range(0, len(palette), 2):
        color = int.from_bytes(palette[offset : offset + 2], "little") & 0x7FFF
        for shift in (0, 5, 10):
            value = (color >> shift) & 0x1F
            rgb.append((value << 3) | (value >> 2))
    return rgb


def _compare(expected: Any, actual: Any, path: str, errors: list[str]) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: expected object")
            return
        for key in expected:
            if key not in actual:
                errors.append(f"{path}.{key}: missing")
            else:
                _compare(expected[key], actual[key], f"{path}.{key}", errors)
        for key in actual.keys() - expected.keys():
            errors.append(f"{path}.{key}: unexpected")
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(f"{path}: expected list")
            return
        if len(expected) != len(actual):
            errors.append(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            _compare(left, right, f"{path}[{index}]", errors)
    elif expected != actual:
        errors.append(f"{path}: {actual!r} != {expected!r}")


def verify_map_canvases(
    root: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    artifact_dir = Path(artifact_dir)
    errors: list[str] = []
    rom_path = root / "rom/base.gba"
    rom = rom_path.read_bytes()
    if _sha256(rom) != ROM_SHA256:
        return {
            "verified_maps": 0,
            "verified_canvases": 0,
            "errors": ["rom.sha256: unexpected base ROM"],
        }
    table = rom[TABLE_OFFSET : TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE]
    if _sha256(table) != TABLE_SHA256:
        return {
            "verified_maps": 0,
            "verified_canvases": 0,
            "errors": ["map_header_table.sha256: mismatch"],
        }
    try:
        actual_manifest = json.loads(
            (artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        return {
            "verified_maps": 0,
            "verified_canvases": 0,
            "errors": [f"manifest.json: {error}"],
        }

    expected_files = {"manifest.json"}
    entries: list[dict[str, Any]] = []
    unique: dict[str, set[str]] = {name: set() for name in RESOURCE_SPECS}
    verified_canvases = 0
    alternate_count = 0
    for map_id in range(ENTRY_COUNT):
        row = _row(rom, map_id)
        resources: dict[str, Any] = {}
        payloads: dict[str, bytes | None] = {}
        for name, (_, directory, suffix) in RESOURCE_SPECS.items():
            pointer = row["pointers"][name]
            if pointer is None:
                resources[name] = None
                payloads[name] = None
                continue
            content = _read_lz77(rom, pointer)
            payloads[name] = content
            digest = _sha256(content)
            unique[name].add(digest)
            relative = Path("resources") / directory / f"{digest}{suffix}"
            expected_files.add(relative.as_posix())
            try:
                actual_content = (artifact_dir / relative).read_bytes()
                if actual_content != content:
                    errors.append(f"{relative.as_posix()}: bytes differ from ROM")
            except OSError as error:
                errors.append(f"{relative.as_posix()}: {error}")
            resources[name] = {
                "gba_address": _address(pointer + ROM_BASE),
                "file_offset": pointer,
                "decompressed_size": len(content),
                "sha256": digest,
                "output_bin": relative.as_posix(),
            }

        primary_tilemap, primary_used = _expand_layout(
            row["width"],
            row["height"],
            payloads["primary_layout"],
            payloads["metatile_definitions"],
        )
        primary_pixels, primary_facts = _pixels_reference(
            row["width"],
            row["height"],
            primary_tilemap,
            payloads["tile_graphics"],
            payloads["bg_palette"],
        )
        variant_inputs = [
            ("primary", primary_tilemap, primary_pixels, primary_used, primary_facts)
        ]
        if payloads["alternate_layout"] is not None:
            alternate_tilemap, alternate_used = _expand_layout(
                row["width"],
                row["height"],
                payloads["alternate_layout"],
                payloads["metatile_definitions"],
            )
            alternate_pixels, alternate_facts = _pixels_reference(
                row["width"],
                row["height"],
                alternate_tilemap,
                payloads["tile_graphics"],
                payloads["bg_palette"],
            )
            variant_inputs.append(
                (
                    "alternate",
                    alternate_tilemap,
                    alternate_pixels,
                    alternate_used,
                    alternate_facts,
                )
            )
            alternate_count += 1

        variants: list[dict[str, Any]] = []
        for name, tilemap, pixels, used_metatiles, facts in variant_inputs:
            canvas_error_start = len(errors)
            tilemap_bytes = struct.pack(f"<{len(tilemap)}H", *tilemap)
            tilemap_relative = Path("tilemaps") / (
                f"map-{map_id:02d}-{name}-u16le.bin"
            )
            canvas_relative = Path("canvases") / f"map-{map_id:02d}-{name}.png"
            expected_files.update(
                (tilemap_relative.as_posix(), canvas_relative.as_posix())
            )
            try:
                if (artifact_dir / tilemap_relative).read_bytes() != tilemap_bytes:
                    errors.append(
                        f"{tilemap_relative.as_posix()}: bytes differ from ROM"
                    )
            except OSError as error:
                errors.append(f"{tilemap_relative.as_posix()}: {error}")

            canvas_path = artifact_dir / canvas_relative
            png_sha256 = ""
            try:
                with Image.open(canvas_path) as image:
                    image.load()
                    if image.mode != "P":
                        errors.append(
                            f"{canvas_relative.as_posix()}: mode {image.mode} != P"
                        )
                    expected_size = (row["width"] * 8, row["height"] * 8)
                    if image.size != expected_size:
                        errors.append(
                            f"{canvas_relative.as_posix()}: "
                            f"size {image.size} != {expected_size}"
                        )
                    if image.tobytes() != pixels:
                        errors.append(
                            f"{canvas_relative.as_posix()}: pixels differ from ROM"
                        )
                    if "transparency" in image.info:
                        errors.append(
                            f"{canvas_relative.as_posix()}: unexpected transparency"
                        )
                    actual_palette = image.getpalette()
                    expected_palette = _palette_rgb(payloads["bg_palette"])
                    if (
                        actual_palette is None
                        or actual_palette[: len(expected_palette)] != expected_palette
                    ):
                        errors.append(
                            f"{canvas_relative.as_posix()}: palette differs from ROM"
                        )
                png_sha256 = _sha256(canvas_path.read_bytes())
            except (OSError, ValueError) as error:
                errors.append(f"{canvas_relative.as_posix()}: {error}")
            if len(errors) == canvas_error_start:
                verified_canvases += 1

            variants.append(
                {
                    "name": name,
                    "header_role": name,
                    "width": row["width"] * 8,
                    "height": row["height"] * 8,
                    "candidate_static_canvas": name == "alternate",
                    "runtime_selection_proven": (
                        map_id == 41 and name == "primary"
                    ),
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
            )

        if map_id == 40:
            if variants[0]["tilemap_sha256"] != MAP_40_TILEMAP_SHA256:
                errors.append("map 40 primary tilemap golden digest mismatch")
            if variants[0]["indexed_pixels_sha256"] != MAP_40_PIXELS_SHA256:
                errors.append("map 40 primary pixel golden digest mismatch")

        entries.append(
            {
                "map_id": map_id,
                "header": {
                    "file_offset": row["offset"],
                    "file_offset_hex": f"0x{row['offset']:08X}",
                    "gba_address": _address(row["offset"] + ROM_BASE),
                    "raw_hex": row["raw"].hex(),
                    "sha256": _sha256(row["raw"]),
                },
                "dimensions_tiles": [row["width"], row["height"]],
                "dimensions_pixels": [row["width"] * 8, row["height"] * 8],
                "coarse_grid_dimensions": [
                    row["width"] // 4,
                    row["height"] // 2,
                ],
                "flags": row["flags"],
                "resources": resources,
                "variants": variants,
            }
        )

    expected_manifest = {
        "schema": "map-canvases-v1",
        "rom": {"path": "rom/base.gba", "sha256": _sha256(rom)},
        "map_header_table": {
            "file_offset": TABLE_OFFSET,
            "gba_address": _address(TABLE_ADDRESS),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "sha256": _sha256(table),
        },
        "map_count": ENTRY_COUNT,
        "canvas_count": verified_canvases,
        "alternate_canvas_count": alternate_count,
        "unique_resource_counts": {
            "tile_graphics": len(unique["tile_graphics"]),
            "bg_palettes": len(unique["bg_palette"]),
            "primary_layouts": len(unique["primary_layout"]),
            "alternate_layouts": len(unique["alternate_layout"]),
            "metatile_definitions": len(unique["metatile_definitions"]),
            "collision_grids": len(unique["collision_grid"]),
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
    _compare(expected_manifest, actual_manifest, "manifest", errors)

    actual_files = {
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file()
    }
    for missing in sorted(expected_files - actual_files):
        errors.append(f"{missing}: missing")
    for unexpected in sorted(actual_files - expected_files):
        errors.append(f"{unexpected}: unexpected")
    return {
        "verified_maps": ENTRY_COUNT,
        "verified_canvases": verified_canvases,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/map-canvases-v1"),
    )
    args = parser.parse_args()
    result = verify_map_canvases(args.root, args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
