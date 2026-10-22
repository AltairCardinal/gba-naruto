#!/usr/bin/env python3
"""Independently verify generic sprite metadata, pixels, palette, and PNGs."""

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
PAIR_TABLE_OFFSET = 0x53F140
PAIR_ENTRY_COUNT = 43
PAIR_ENTRY_SIZE = 8
TILE_OFFSET_TABLE_OFFSET = 0x53F298
TILE_OFFSET_ENTRY_SIZE = 2
COMPONENT_SIZE = 0x14
TERMINATOR = bytes.fromhex("ffff0000")
GRAPHICS_OFFSET = 0x12F298
GRAPHICS_DECOMPRESSED_SIZE = 1568
GRAPHICS_COMPRESSED_SIZE = 745
PALETTE_OFFSET = 0x12F584
PALETTE_DECOMPRESSED_SIZE = 32
PALETTE_COMPRESSED_SIZE = 20
PAIR_TABLE_SHA256 = (
    "5873ae022e9b6290f876aab367b6dbe95b7a97b9b7a2f15d0861dc747196f3f8"
)
TILE_OFFSET_TABLE_SHA256 = (
    "86d57e438c3b3e9a877ebea8d910e2782c30b5bcbf8ca4f305df1deee6d231d6"
)
RESOLVED_WINDOW_0X28_SHA256 = (
    "439eb69f5ee2eadefe6fbd66b88ba27fb53c6552ac184267a803917fe8e98248"
)
GRAPHICS_COMPRESSED_SHA256 = (
    "57367318445ab783ee8b4ff4fd58deb37105e106a70f0608a531a756e9b059e2"
)
GRAPHICS_SHA256 = (
    "1472c4df7436428d41c668fd6ebb21f58c2a13b0876f372fe3f4b5d602aaa256"
)
PALETTE_COMPRESSED_SHA256 = (
    "7aad1ded0576b67924b8a9e6e8f24698b226929839502a3ef16b43dd6821df69"
)
PALETTE_SHA256 = (
    "043a3dbc0b648314d4289bea8eeca660c17085ddd1c2fb225e50ace435f95ab6"
)

EXPECTED_CODE_SLICES = (
    {
        "name": "static_lz77_resource_loader",
        "file_offset": 0x080A48,
        "gba_address": "0x08080A48",
        "size": 0x60,
        "sha256": "9777e932b276d5062555e38267bc256747172f491803fb228b40c8ea8804dd7f",
    },
    {
        "name": "table_and_runtime_base_loader",
        "file_offset": 0x080B08,
        "gba_address": "0x08080B08",
        "size": 0x74,
        "sha256": "ff28fa10e4606f706a4fd4986126d8a14fe2baf66f1cc2621c5fe6b15d2ff8c2",
    },
    {
        "name": "sprite_task_allocator",
        "file_offset": 0x0625A4,
        "gba_address": "0x080625A4",
        "size": 0x10C,
        "sha256": "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54",
    },
    {
        "name": "component_selector",
        "file_offset": 0x06298C,
        "gba_address": "0x0806298C",
        "size": 0x7E,
        "sha256": "722200eb6511a974b79fe00ee335f21e557cc0fc1898343a5eab4c7032e8ed2f",
    },
    {
        "name": "attr2_and_obj_vram_path",
        "file_offset": 0x063108,
        "gba_address": "0x08063108",
        "size": 0x7E,
        "sha256": "748340bb724a0fc8a4911c8879e8fb0c1152c84bac87b910cb36b3e15d790b17",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer(value: int) -> str:
    return f"0x{value:08X}"


def _offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer {_pointer(pointer)} is outside the ROM")
    return offset


def _read_lz77(rom: bytes, offset: int) -> tuple[bytes, bytes]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"resource is not LZ77 at 0x{offset:06X}")
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


def _tile_block_pixels(
    graphics: bytes,
    *,
    tile_offset: int,
    width_tiles: int,
    height_tiles: int,
) -> bytes:
    tile_count = width_tiles * height_tiles
    if (
        tile_offset < 0
        or width_tiles <= 0
        or height_tiles <= 0
        or (tile_offset + tile_count) * 32 > len(graphics)
    ):
        raise ValueError("invalid 4bpp tile block")
    width = width_tiles * 8
    pixels = bytearray(width * height_tiles * 8)
    for local_tile in range(tile_count):
        tile_x = local_tile % width_tiles
        tile_y = local_tile // width_tiles
        tile_start = (tile_offset + local_tile) * 32
        for y in range(8):
            for x in range(8):
                packed = graphics[tile_start + y * 4 + x // 2]
                pixels[
                    (tile_y * 8 + y) * width + tile_x * 8 + x
                ] = (packed >> (4 if x & 1 else 0)) & 0x0F
    return bytes(pixels)


def _atlas_pixels(
    graphics: bytes,
    *,
    tiles_per_row: int,
) -> tuple[bytes, int, int]:
    tile_count = len(graphics) // 32
    width = min(tile_count, tiles_per_row) * 8
    height = ((tile_count + tiles_per_row - 1) // tiles_per_row) * 8
    pixels = bytearray(width * height)
    for tile in range(tile_count):
        source = _tile_block_pixels(
            graphics,
            tile_offset=tile,
            width_tiles=1,
            height_tiles=1,
        )
        tile_x = tile % tiles_per_row
        tile_y = tile // tiles_per_row
        for y in range(8):
            destination = (tile_y * 8 + y) * width + tile_x * 8
            pixels[destination : destination + 8] = source[y * 8 : y * 8 + 8]
    return bytes(pixels), width, height


def _palette_rgb(palette: bytes) -> list[int]:
    output = []
    for offset in range(0, len(palette), 2):
        color = int.from_bytes(palette[offset : offset + 2], "little") & 0x7FFF
        for shift in (0, 5, 10):
            value = (color >> shift) & 0x1F
            output.append((value << 3) | (value >> 2))
    return output


def _verify_png(
    path: Path,
    *,
    pixels: bytes,
    width: int,
    height: int,
    palette: bytes,
) -> str:
    with Image.open(path) as image:
        image.load()
        if image.mode != "P":
            raise ValueError(f"{path.name}: mode {image.mode} != P")
        if image.size != (width, height):
            raise ValueError(
                f"{path.name}: size {image.size} != {(width, height)}"
            )
        if image.tobytes() != pixels:
            raise ValueError(f"{path.name}: indexed pixels differ from ROM")
        if image.info.get("transparency") != 0:
            raise ValueError(f"{path.name}: transparent index is not 0")
        expected_palette = _palette_rgb(palette)
        actual_palette = image.getpalette()
        if actual_palette is None or actual_palette[: len(expected_palette)] != (
            expected_palette
        ):
            raise ValueError(f"{path.name}: RGB palette differs from ROM")
    return _sha256(path.read_bytes())


def _parse_component(raw: bytes, index: int) -> dict[str, Any]:
    (
        tile_offset,
        flag_02,
        flag_03,
        horizontal_position_input,
        vertical_position_input,
        width,
        height,
        transform_factor_0c,
        transform_factor_0e,
        unknown_10_byte,
        oam_attribute_byte,
        unknown_12,
    ) = struct.unpack("<HBBhhhhhhBBH", raw)
    return {
        "index": index,
        "tile_offset": tile_offset,
        "flag_02": flag_02,
        "flag_03": flag_03,
        "horizontal_position_input": horizontal_position_input,
        "vertical_position_input": vertical_position_input,
        "width": width,
        "height": height,
        "transform_factor_0c": transform_factor_0c,
        "transform_factor_0e": transform_factor_0e,
        "unknown_10_byte": unknown_10_byte,
        "oam_attribute_byte": oam_attribute_byte,
        "unknown_12": unknown_12,
        "raw_hex": raw.hex(),
    }


def _expected_entries(rom: bytes) -> tuple[list[dict[str, Any]], str]:
    entries: list[dict[str, Any]] = []
    windows: list[bytes] = []
    for entry_id in range(PAIR_ENTRY_COUNT):
        pair_offset = PAIR_TABLE_OFFSET + entry_id * PAIR_ENTRY_SIZE
        definition_pointer, animation_pointer = struct.unpack_from(
            "<II",
            rom,
            pair_offset,
        )
        definition_offset = _offset(definition_pointer, len(rom))
        _offset(animation_pointer, len(rom))
        component_list_pointer = struct.unpack_from(
            "<I",
            rom,
            definition_offset,
        )[0]
        component_list_offset = _offset(component_list_pointer, len(rom))
        cursor = component_list_offset
        components: list[dict[str, Any]] = []
        while cursor + 4 <= len(rom):
            if rom[cursor : cursor + 4] == TERMINATOR:
                cursor += 4
                break
            if cursor + COMPONENT_SIZE > len(rom):
                raise ValueError(f"entry {entry_id} component record is truncated")
            raw = rom[cursor : cursor + COMPONENT_SIZE]
            components.append(_parse_component(raw, len(components)))
            cursor += COMPONENT_SIZE
            if len(components) > 32:
                raise ValueError(f"entry {entry_id} component list is unbounded")
        else:
            raise ValueError(f"entry {entry_id} component list has no terminator")
        if cursor != definition_offset:
            raise ValueError(
                f"entry {entry_id} component list does not end at definition"
            )
        component_list_raw = rom[component_list_offset:cursor]
        resolved_window = rom[
            component_list_offset : component_list_offset + 0x28
        ]
        windows.append(resolved_window)
        definition_header = rom[definition_offset : definition_offset + 12]
        tile_base_offset = struct.unpack_from(
            "<H",
            rom,
            TILE_OFFSET_TABLE_OFFSET + entry_id * 2,
        )[0]
        entries.append(
            {
                "id": entry_id,
                "pair_file_offset": pair_offset,
                "definition_pointer": _pointer(definition_pointer),
                "animation_pointer": _pointer(animation_pointer),
                "tile_base_offset": tile_base_offset,
                "component_list_pointer": _pointer(component_list_pointer),
                "component_count": len(components),
                "component_list_size": len(component_list_raw),
                "component_list_sha256": _sha256(component_list_raw),
                "components": components,
                "terminator_raw_hex": TERMINATOR.hex(),
                "definition_header_raw_hex": definition_header.hex(),
                "definition_header_sha256": _sha256(definition_header),
                "resolved_window_0x28_sha256": _sha256(resolved_window),
            }
        )
    return entries, _sha256(b"".join(windows))


def _entry_asset(
    entry: dict[str, Any],
    graphics: bytes,
    palette: bytes,
    artifact_dir: Path,
) -> tuple[dict[str, Any], list[int]]:
    components = entry["components"]
    min_x = min(component["horizontal_position_input"] for component in components)
    min_y = min(component["vertical_position_input"] for component in components)
    max_x = max(
        component["horizontal_position_input"] + component["width"]
        for component in components
    )
    max_y = max(
        component["vertical_position_input"] + component["height"]
        for component in components
    )
    width = max_x - min_x
    height = max_y - min_y
    canvas = bytearray(width * height)
    occupied = bytearray(width * height)
    tile_indices = []
    for component in components:
        width_tiles = component["width"] // 8
        height_tiles = component["height"] // 8
        tile_offset = entry["tile_base_offset"] + component["tile_offset"]
        component_pixels = _tile_block_pixels(
            graphics,
            tile_offset=tile_offset,
            width_tiles=width_tiles,
            height_tiles=height_tiles,
        )
        component_width = component["width"]
        component_height = component["height"]
        x = component["horizontal_position_input"] - min_x
        y = component["vertical_position_input"] - min_y
        for local_y in range(component_height):
            destination = (y + local_y) * width + x
            source = local_y * component_width
            if any(occupied[destination : destination + component_width]):
                raise ValueError(f"entry {entry['id']} components overlap")
            canvas[destination : destination + component_width] = (
                component_pixels[source : source + component_width]
            )
            occupied[destination : destination + component_width] = (
                b"\x01" * component_width
            )
        tile_indices.extend(
            range(tile_offset, tile_offset + width_tiles * height_tiles)
        )
    png_name = f"sprite-id-{entry['id']:02d}.png"
    png_hash = _verify_png(
        artifact_dir / png_name,
        pixels=bytes(canvas),
        width=width,
        height=height,
        palette=palette,
    )
    return (
        {
            "png": png_name,
            "width": width,
            "height": height,
            "source_bounds": {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
            },
            "tile_indices": tile_indices,
            "pixel_sha256": _sha256(bytes(canvas)),
            "png_sha256": png_hash,
        },
        tile_indices,
    )


def _expected_manifest(
    rom: bytes,
    artifact_dir: Path,
) -> dict[str, Any]:
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError("source ROM SHA-256 mismatch")
    pair_table = rom[
        PAIR_TABLE_OFFSET : PAIR_TABLE_OFFSET
        + PAIR_ENTRY_COUNT * PAIR_ENTRY_SIZE
    ]
    tile_offsets = rom[
        TILE_OFFSET_TABLE_OFFSET : TILE_OFFSET_TABLE_OFFSET
        + PAIR_ENTRY_COUNT * TILE_OFFSET_ENTRY_SIZE
    ]
    if _sha256(pair_table) != PAIR_TABLE_SHA256:
        raise ValueError("source pair table SHA-256 mismatch")
    if _sha256(tile_offsets) != TILE_OFFSET_TABLE_SHA256:
        raise ValueError("source tile-offset table SHA-256 mismatch")
    entries, resolved_window_sha256 = _expected_entries(rom)
    if resolved_window_sha256 != RESOLVED_WINDOW_0X28_SHA256:
        raise ValueError("source resolved-window SHA-256 mismatch")

    code_slices = []
    for expected in EXPECTED_CODE_SLICES:
        raw = rom[
            expected["file_offset"] : expected["file_offset"] + expected["size"]
        ]
        if _sha256(raw) != expected["sha256"]:
            raise ValueError(f"source {expected['name']} code slice mismatch")
        code_slices.append(dict(expected))

    graphics_compressed, graphics = _read_lz77(rom, GRAPHICS_OFFSET)
    palette_compressed, palette = _read_lz77(rom, PALETTE_OFFSET)
    resource_checks = (
        (
            "graphics compressed",
            graphics_compressed,
            GRAPHICS_COMPRESSED_SIZE,
            GRAPHICS_COMPRESSED_SHA256,
        ),
        (
            "graphics",
            graphics,
            GRAPHICS_DECOMPRESSED_SIZE,
            GRAPHICS_SHA256,
        ),
        (
            "palette compressed",
            palette_compressed,
            PALETTE_COMPRESSED_SIZE,
            PALETTE_COMPRESSED_SHA256,
        ),
        (
            "palette",
            palette,
            PALETTE_DECOMPRESSED_SIZE,
            PALETTE_SHA256,
        ),
    )
    for name, payload, size, digest in resource_checks:
        if len(payload) != size or _sha256(payload) != digest:
            raise ValueError(f"source {name} identity mismatch")
    if (artifact_dir / "sprite-pack-4bpp.bin").read_bytes() != graphics:
        raise ValueError("sprite-pack-4bpp.bin differs from ROM decompression")
    if (artifact_dir / "palette-16-bgr555.bin").read_bytes() != palette:
        raise ValueError("palette-16-bgr555.bin differs from ROM decompression")

    atlas_pixels, atlas_width, atlas_height = _atlas_pixels(
        graphics,
        tiles_per_row=32,
    )
    atlas_hash = _verify_png(
        artifact_dir / "sprite-pack-atlas.png",
        pixels=atlas_pixels,
        width=atlas_width,
        height=atlas_height,
        palette=palette,
    )
    atlas = {
        "png": "sprite-pack-atlas.png",
        "width": atlas_width,
        "height": atlas_height,
        "tiles_per_row": 32,
        "tile_count": len(graphics) // 32,
        "pixel_sha256": _sha256(atlas_pixels),
        "png_sha256": atlas_hash,
    }

    references = []
    for entry in entries:
        asset, entry_references = _entry_asset(
            entry,
            graphics,
            palette,
            artifact_dir,
        )
        entry["asset"] = asset
        references.extend(entry_references)
    tile_count = len(graphics) // 32
    counts = {tile: references.count(tile) for tile in set(references)}
    tile_coverage = {
        "tile_count": tile_count,
        "tile_reference_count": len(references),
        "referenced_tile_indices": sorted(counts),
        "missing_tile_indices": sorted(set(range(tile_count)) - set(counts)),
        "duplicate_tile_indices": sorted(
            tile for tile, count in counts.items() if count > 1
        ),
        "all_tiles_referenced_exactly_once": (
            sorted(references) == list(range(tile_count))
        ),
    }
    if not tile_coverage["all_tiles_referenced_exactly_once"]:
        raise ValueError("source definitions do not cover the tile pack once")
    artifact_files = sorted(
        [
            "manifest.json",
            "palette-16-bgr555.bin",
            "sprite-pack-4bpp.bin",
            "sprite-pack-atlas.png",
            *(f"sprite-id-{entry_id:02d}.png" for entry_id in range(43)),
        ]
    )
    actual_files = sorted(
        path.name for path in artifact_dir.iterdir() if path.is_file()
    )
    if actual_files != artifact_files:
        raise ValueError(
            f"artifact file set differs: {actual_files} != {artifact_files}"
        )

    return {
        "schema": "sprite-definition-assets-v2",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "pair_table": {
            "file_offset": PAIR_TABLE_OFFSET,
            "gba_address": _pointer(ROM_BASE + PAIR_TABLE_OFFSET),
            "entry_count": PAIR_ENTRY_COUNT,
            "entry_size": PAIR_ENTRY_SIZE,
            "sha256": _sha256(pair_table),
        },
        "tile_offset_table": {
            "file_offset": TILE_OFFSET_TABLE_OFFSET,
            "gba_address": _pointer(ROM_BASE + TILE_OFFSET_TABLE_OFFSET),
            "entry_count": PAIR_ENTRY_COUNT,
            "entry_size": TILE_OFFSET_ENTRY_SIZE,
            "sha256": _sha256(tile_offsets),
        },
        "resolved_window_0x28_definition": (
            "concat in pair-table order of ROM[D_i[0]:D_i[0]+0x28]"
        ),
        "resolved_window_0x28_sha256": resolved_window_sha256,
        "entry_count": len(entries),
        "component_count": sum(entry["component_count"] for entry in entries),
        "multi_component_entry_ids": [
            entry["id"] for entry in entries if entry["component_count"] > 1
        ],
        "static_resources": {
            "graphics": {
                "file_offset": GRAPHICS_OFFSET,
                "gba_address": _pointer(ROM_BASE + GRAPHICS_OFFSET),
                "compressed_size": len(graphics_compressed),
                "compressed_sha256": _sha256(graphics_compressed),
                "decompressed_size": len(graphics),
                "decompressed_sha256": _sha256(graphics),
                "tile_count": len(graphics) // 32,
                "output_bin": "sprite-pack-4bpp.bin",
            },
            "palette": {
                "file_offset": PALETTE_OFFSET,
                "gba_address": _pointer(ROM_BASE + PALETTE_OFFSET),
                "compressed_size": len(palette_compressed),
                "compressed_sha256": _sha256(palette_compressed),
                "decompressed_size": len(palette),
                "decompressed_sha256": _sha256(palette),
                "color_count": len(palette) // 2,
                "transparent_index": 0,
                "output_bin": "palette-16-bgr555.bin",
            },
        },
        "sprite_pack_atlas": atlas,
        "tile_coverage": tile_coverage,
        "artifact_file_count": len(artifact_files),
        "artifact_files": artifact_files,
        "entries": entries,
        "component_schema": {
            "record_size": COMPONENT_SIZE,
            "terminator_raw_hex": TERMINATOR.hex(),
            "terminator_rule": (
                "component +0x00 is read as s16; -1 terminates the list"
            ),
            "field_evidence": {
                "tile_offset": [
                    "0x080629FC",
                    "0x08063108",
                    "0x080631FE",
                ],
                "flag_02": ["0x08062EB4..0x08062EEE"],
                "flag_03": ["0x08062EFC..0x08062F9E"],
                "horizontal_position_input": ["0x08062A26..0x08062A64"],
                "vertical_position_input": ["0x08062A2C..0x08062A7C"],
                "width": [
                    "0x08062A50",
                    "0x08062DCA..0x08062DEC",
                    "0x0806314E",
                ],
                "height": [
                    "0x08062A66",
                    "0x08062DEE..0x08062EB2",
                    "0x08063150",
                ],
                "transform_factor_0c": [
                    "0x08062F12..0x08062F44",
                    "0x08063002..0x08063048",
                ],
                "transform_factor_0e": [
                    "0x08062F56..0x08062F7C",
                    "0x0806301C..0x08063060",
                ],
                "unknown_10_byte": [],
                "oam_attribute_byte": [
                    "0x08062B62..0x08062B6E",
                    "0x08062DB4..0x08062DBC",
                ],
                "unknown_12": [],
            },
        },
        "runtime_chain": {
            "static_resource_loader": "0x08080A48",
            "graphics_loader_call": "0x08080A5C",
            "palette_loader_call": "0x08080A6A",
            "lz77_vram_wrapper": "0x0809C0E8",
            "graphics_source": "0x0812F298",
            "palette_source": "0x0812F584",
            "pair_table_loader": "0x08080B08",
            "sprite_task_allocator": "0x080625A4",
            "pair_index_install": "0x08062668",
            "component_selector": "0x0806298C",
            "attr2_builder": "0x08063108",
            "conditional_component_copy_path": (
                "0x08063134 (not selected by generic task flags 0x49)"
            ),
            "component_stride_and_terminator_check": "0x080631F6..0x08063210",
            "tile_base_global": "0x0202CA24",
            "palette_bank_global": "0x0202CA26",
            "obj_vram_base": "0x06010000",
            "obj_palette_base": "0x05000200",
            "static_graphics_destination_formula": (
                "0x06010000 + u16[0x0202CA24] * 32"
            ),
            "static_palette_destination_formula": (
                "0x05000200 + u8[0x0202CA26] * 32"
            ),
            "task_tile_base_formula": (
                "task.tile_base = u16[0x0202CA24] + tile_base_offset[id]"
            ),
            "attr2_tile_formula": (
                "attr2.tile = task.tile_base + component.tile_offset"
            ),
            "attr2_palette_formula": (
                "attr2.palette = u8[0x0202CA26] << 12"
            ),
            "obj_vram_address_formula": (
                "OBJ tile bytes begin at 0x06010000 + attr2.tile * 32"
            ),
            "obj_palette_address_formula": (
                "OBJ palette bytes begin at 0x05000200 + "
                "u8[0x0202CA26] * 32"
            ),
            "code_slices": code_slices,
        },
        "scope": {
            "kind": (
                "static definition/animation metadata, canonical ROM LZ77 "
                "pixels and palette, plus code-proven OBJ address chain"
            ),
            "pixel_payload_in_pair_table": False,
            "canonical_static_pixels_exported": True,
            "canonical_static_palette_exported": True,
            "runtime_capture_required_for_canonical_assets": False,
            "scene_specific_overwrite_checked": False,
            "animation_sequence_fully_interpreted": False,
        },
    }


def _compare(
    expected: Any,
    actual: Any,
    path: str,
    errors: list[str],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: expected object, got {type(actual).__name__}")
            return
        for key in expected:
            child = f"{path}.{key}" if path else key
            if key not in actual:
                errors.append(f"{child}: missing")
            else:
                _compare(expected[key], actual[key], child, errors)
        for key in actual.keys() - expected.keys():
            child = f"{path}.{key}" if path else key
            errors.append(f"{child}: unexpected")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(f"{path}: expected list, got {type(actual).__name__}")
            return
        if len(expected) != len(actual):
            errors.append(
                f"{path}: expected length {len(expected)}, got {len(actual)}"
            )
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual)
        ):
            _compare(expected_item, actual_item, f"{path}[{index}]", errors)
        return
    if expected != actual:
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")


def verify_sprite_definition_runtime_chain(
    root: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rom = (root / "rom/base.gba").read_bytes()
        expected = _expected_manifest(rom, artifact_dir)
    except (OSError, ValueError, struct.error) as exc:
        return {
            "schema": "sprite-definition-assets-verification-v2",
            "verified_entries": 0,
            "verified_components": 0,
            "verified_assets": 0,
            "verified_tiles": 0,
            "errors": [f"source: {exc}"],
        }
    try:
        actual = json.loads(
            (artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "sprite-definition-assets-verification-v2",
            "verified_entries": 0,
            "verified_components": 0,
            "verified_assets": 0,
            "verified_tiles": 0,
            "errors": [f"manifest: {exc}"],
        }
    _compare(expected, actual, "", errors)
    return {
        "schema": "sprite-definition-assets-verification-v2",
        "verified_entries": 0 if errors else expected["entry_count"],
        "verified_components": 0 if errors else expected["component_count"],
        "verified_assets": 0 if errors else expected["entry_count"],
        "verified_tiles": (
            0 if errors else expected["tile_coverage"]["tile_count"]
        ),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the 0x53F140 generic sprite static assets",
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/sprite-definition-assets-v2"),
    )
    args = parser.parse_args()
    report = verify_sprite_definition_runtime_chain(
        args.root.resolve(),
        args.artifact_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
