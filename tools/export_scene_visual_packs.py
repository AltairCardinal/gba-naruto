#!/usr/bin/env python3
"""Export the nine mixed BG/OBJ visual packs at ROM table 0x085A4CE8."""

from __future__ import annotations

import argparse
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

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import (
    ROM_BASE,
    gba_pointer,
    indexed_png_from_bgr555,
    read_lz77_record,
    render_4bpp_tile_atlas_indices,
    render_4bpp_tile_block_indices,
    sha256,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "scene-visual-packs-v1"
TABLE_ADDRESS = 0x085A4CE8
TABLE_OFFSET = TABLE_ADDRESS - ROM_BASE
ENTRY_COUNT = 9
ENTRY_SIZE = 0x1C
TABLE_SHA256 = "b562062061a088aac2e5ce2f2d9f8bbfd34f0cb53a794a7ea5b0f270ecf909b3"
COMPONENT_SIZE = 0x14
COMPONENT_TERMINATOR = b"\xFF\xFF\x00\x00"

CONSUMER_RANGES = {
    "setup_and_initial_row": (
        0x0808BAB0,
        0x0808BEDE,
        "49e5707f975743b374bc93b685bdeb8465674c46b17bf543574ed010f318929f",
    ),
    "indexed_row_loader": (
        0x0808BEE4,
        0x0808BF62,
        "804b19345db90905040aeb7c71e9e5d2464d9ee0fcf821bc6f3fc4ceead08f2a",
    ),
    "sprite_spawner": (
        0x0808C0B4,
        0x0808C164,
        "3fd57f3a23dd6e1a1c1030f272b0213c596b7c3679069d47c0e7b4b82b5b05d3",
    ),
    "presentation_selector": (
        0x0808C18C,
        0x0808C1EC,
        "ba2a35a498752085f4fbcab7a18667f1cd404199b5278eb4c77842ea57c0804e",
    ),
    "controller": (
        0x0808C214,
        0x0808C4C2,
        "c515f1996f65fd8c7a73eb86429fc4bd798a62f4b5cad6b36075fb9aba1ac03b",
    ),
    "sprite_task_allocator": (
        0x080626B4,
        0x0806275E,
        "1b0a793b761f650bfe43d75ad76186c395d6315dd67a130b9575184b11ce2f87",
    ),
    "animation_frame_selector": (
        0x0806298C,
        0x080629F6,
        "d02024aa1d1688f2915f35496f457d5cc4d123b706e980137f9ce3d19e331686",
    ),
    "obj_attr2_writer": (
        0x08063108,
        0x08063120,
        "3a8ba305e8ed98f95bda2f6e81361571db10e20f0c2158d99930573e4d24ba83",
    ),
    "animation_timing_consumer": (
        0x08063256,
        0x080632D8,
        "1ec4801f36351e56d511caaa6cc5fdf31d52142292e64d3c9cf6567eed468be0",
    ),
    "packed_tilemap_copier": (
        0x08063604,
        0x080636C0,
        "844be072d9572bd9a657357e745977ed9435c647d0ec0e811f66c953c84a1bd6",
    ),
}

OBJ_PALETTES = (
    {
        "bank": 0,
        "address": 0x083F2794,
        "destination": 0x05000200,
        "sha256": "14975f2391f88813040bbadc136bbfcaa736a408521af3701054bf0470d5a4f9",
    },
    {
        "bank": 1,
        "address": 0x083F2CB0,
        "destination": 0x05000220,
        "sha256": "bb58f9bc0be9a3b7ad2604ced29815b23d55660c89e70e59430959cf7aed8b2f",
    },
)


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _rom_offset(address: int, rom_size: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset >= rom_size:
        raise ValueError(f"address is outside ROM: {_address(address)}")
    return offset


def _slice(rom: bytes, address: int, size: int) -> bytes:
    offset = _rom_offset(address, len(rom))
    data = rom[offset : offset + size]
    if len(data) != size:
        raise ValueError(f"truncated ROM range at {_address(address)}")
    return data


def _resource(
    rom: bytes,
    pointer: int,
    *,
    expected_size: int | None = None,
) -> tuple[bytes, bytes]:
    offset = _rom_offset(pointer, len(rom))
    compressed = read_lz77_record(rom, offset, expected_size=expected_size)
    decompressed = lz77_decompress(rom, offset)
    if expected_size is not None and len(decompressed) != expected_size:
        raise ValueError(f"unexpected resource size at {_address(pointer)}")
    return compressed, decompressed


def _render_8bpp_tilemap(
    graphics: bytes,
    tilemap: bytes,
    *,
    width_tiles: int,
    height_tiles: int,
) -> tuple[bytes, dict[str, Any]]:
    if not graphics or len(graphics) % 64:
        raise ValueError("8bpp graphics do not contain complete tiles")
    if len(tilemap) != width_tiles * height_tiles * 2:
        raise ValueError("packed tilemap size does not match dimensions")
    entries = struct.unpack(f"<{width_tiles * height_tiles}H", tilemap)
    tile_count = len(graphics) // 64
    width = width_tiles * 8
    height = height_tiles * 8
    pixels = bytearray(width * height)
    referenced: set[int] = set()
    horizontal_flips = 0
    vertical_flips = 0
    palette_banks: set[int] = set()
    for tile_y in range(height_tiles):
        for tile_x in range(width_tiles):
            entry = entries[tile_y * width_tiles + tile_x]
            tile_id = entry & 0x03FF
            if tile_id >= tile_count:
                raise ValueError("tilemap references a tile outside graphics")
            referenced.add(tile_id)
            horizontal = bool(entry & 0x0400)
            vertical = bool(entry & 0x0800)
            horizontal_flips += horizontal
            vertical_flips += vertical
            palette_banks.add(entry >> 12)
            for local_y in range(8):
                source_y = 7 - local_y if vertical else local_y
                for local_x in range(8):
                    source_x = 7 - local_x if horizontal else local_x
                    pixels[
                        (tile_y * 8 + local_y) * width
                        + tile_x * 8
                        + local_x
                    ] = graphics[
                        tile_id * 64 + source_y * 8 + source_x
                    ]
    return bytes(pixels), {
        "referenced_tile_indices": sorted(referenced),
        "missing_tile_indices": sorted(set(range(tile_count)) - referenced),
        "all_tiles_referenced": len(referenced) == tile_count,
        "horizontal_flip_entry_count": horizontal_flips,
        "vertical_flip_entry_count": vertical_flips,
        "palette_bank_values": sorted(palette_banks),
    }


def _component(raw: bytes, component_id: int) -> dict[str, Any]:
    if len(raw) != COMPONENT_SIZE:
        raise ValueError("component record is truncated")
    (
        tile_index,
        tile_flags,
        x,
        y,
        width,
        height,
        scale_x,
        scale_y,
        control,
        affine_mode,
        reserved,
    ) = struct.unpack("<HHhhHHHHBBH", raw)
    if tile_index == 0xFFFF:
        raise ValueError("component terminator parsed as data")
    if width not in (8, 16, 32, 64) or height not in (8, 16, 32, 64):
        raise ValueError("unsupported component dimensions")
    if tile_flags & ~3:
        raise ValueError("unsupported component tile flags")
    if control not in (0, 0xFF) or affine_mode not in (0, 1) or reserved:
        raise ValueError("unsupported component control fields")
    return {
        "component_id": component_id,
        "tile_index": tile_index,
        "tile_flags": tile_flags,
        "horizontal_flip": bool(tile_flags & 1),
        "vertical_flip": bool(tile_flags & 2),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "control": control,
        "affine_mode": affine_mode,
        "raw_hex": raw.hex(),
    }


def _frame_pointers(
    rom: bytes,
    definition_pointer: int,
) -> tuple[list[int], int]:
    cursor = _rom_offset(definition_pointer, len(rom))
    pointers: list[int] = []
    while cursor + 4 <= len(rom):
        pointer = struct.unpack_from("<I", rom, cursor)[0]
        if not ROM_BASE <= pointer < definition_pointer:
            break
        if pointers and pointer <= pointers[-1]:
            raise ValueError("frame pointers are not increasing")
        pointers.append(pointer)
        cursor += 4
        if len(pointers) > 32:
            raise ValueError("unbounded frame pointer table")
    if not pointers:
        raise ValueError("definition has no frame pointers")
    return pointers, ROM_BASE + cursor


def _frames(
    rom: bytes,
    definition_pointer: int,
) -> tuple[list[dict[str, Any]], int, bytes]:
    pointers, timeline_start = _frame_pointers(rom, definition_pointer)
    result: list[dict[str, Any]] = []
    expected_ends = pointers[1:] + [definition_pointer]
    region_start = pointers[0]
    for frame_id, (pointer, expected_end) in enumerate(
        zip(pointers, expected_ends)
    ):
        cursor = _rom_offset(pointer, len(rom))
        start = cursor
        components: list[dict[str, Any]] = []
        while rom[cursor : cursor + 4] != COMPONENT_TERMINATOR:
            raw = rom[cursor : cursor + COMPONENT_SIZE]
            components.append(_component(raw, len(components)))
            cursor += COMPONENT_SIZE
            if len(components) > 32:
                raise ValueError("unbounded component list")
        cursor += len(COMPONENT_TERMINATOR)
        if ROM_BASE + cursor != expected_end:
            raise ValueError("component lists are not contiguous")
        raw = rom[start:cursor]
        result.append(
            {
                "frame_id": frame_id,
                "component_list_pointer": _address(pointer),
                "component_count": len(components),
                "components": components,
                "raw_size": len(raw),
                "raw_sha256": sha256(raw),
            }
        )
    pointer_table = _slice(
        rom,
        definition_pointer,
        len(pointers) * 4,
    )
    definition_region = _slice(
        rom,
        region_start,
        definition_pointer + len(pointer_table) - region_start,
    )
    return result, timeline_start, definition_region


def _animations(
    rom: bytes,
    timeline_start: int,
    animation_pointer: int,
    frame_count: int,
) -> tuple[list[dict[str, Any]], bytes]:
    cursor = _rom_offset(animation_pointer, len(rom))
    pointers: list[int] = []
    while cursor + 4 <= len(rom):
        pointer = struct.unpack_from("<I", rom, cursor)[0]
        if not timeline_start <= pointer < animation_pointer:
            break
        if pointers and pointer <= pointers[-1]:
            raise ValueError("animation pointers are not increasing")
        pointers.append(pointer)
        cursor += 4
        if len(pointers) > 32:
            raise ValueError("unbounded animation pointer table")
    if not pointers:
        raise ValueError("animation table is empty")
    expected_ends = pointers[1:] + [animation_pointer]
    result: list[dict[str, Any]] = []
    for animation_id, (pointer, expected_end) in enumerate(
        zip(pointers, expected_ends)
    ):
        raw = _slice(rom, pointer, 8)
        frame_id, timing_value, terminator, terminator_value = struct.unpack(
            "<HHHH", raw
        )
        if (
            frame_id >= frame_count
            or terminator != 0xFFFF
            or terminator_value
            or pointer + len(raw) != expected_end
        ):
            raise ValueError("unexpected animation timeline format")
        result.append(
            {
                "animation_id": animation_id,
                "timeline_pointer": _address(pointer),
                "frame_id": frame_id,
                "timing_value": timing_value,
                "timing_semantics": "unknown",
                "terminator": [0xFFFF, 0],
                "raw_size": len(raw),
                "raw_sha256": sha256(raw),
            }
        )
    pointer_table_size = len(pointers) * 4
    region = _slice(
        rom,
        pointers[0],
        animation_pointer + pointer_table_size - pointers[0],
    )
    return result, region


def _flip(
    pixels: bytes,
    width: int,
    height: int,
    *,
    horizontal: bool,
    vertical: bool,
) -> bytes:
    if not horizontal and not vertical:
        return pixels
    output = bytearray(len(pixels))
    for y in range(height):
        source_y = height - y - 1 if vertical else y
        for x in range(width):
            source_x = width - x - 1 if horizontal else x
            output[y * width + x] = pixels[source_y * width + source_x]
    return bytes(output)


def _render_frame(
    frame: dict[str, Any],
    graphics: bytes,
    palette: bytes,
) -> tuple[bytes, int, int, dict[str, int], set[int], bytes]:
    components = frame["components"]
    if not components:
        raise ValueError("empty OBJ frame")
    min_x = min(component["x"] for component in components)
    min_y = min(component["y"] for component in components)
    max_x = max(component["x"] + component["width"] for component in components)
    max_y = max(component["y"] + component["height"] for component in components)
    width = max_x - min_x
    height = max_y - min_y
    pixels = bytearray(width * height)
    referenced: set[int] = set()
    for component in components:
        tile_count = component["width"] * component["height"] // 64
        referenced.update(
            range(component["tile_index"], component["tile_index"] + tile_count)
        )
        block, block_width, block_height = render_4bpp_tile_block_indices(
            graphics,
            tile_offset=component["tile_index"],
            width_tiles=component["width"] // 8,
            height_tiles=component["height"] // 8,
        )
        block = _flip(
            block,
            block_width,
            block_height,
            horizontal=component["horizontal_flip"],
            vertical=component["vertical_flip"],
        )
        destination_x = component["x"] - min_x
        destination_y = component["y"] - min_y
        for y in range(block_height):
            for x in range(block_width):
                color = block[y * block_width + x]
                if color:
                    pixels[(destination_y + y) * width + destination_x + x] = color
    raw_pixels = bytes(pixels)
    png = indexed_png_from_bgr555(
        raw_pixels,
        palette,
        width=width,
        height=height,
        transparent_index=0,
    )
    return (
        png,
        width,
        height,
        {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
        referenced,
        raw_pixels,
    )


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


def _replace_output(output_dir: Path, files: dict[str, bytes]) -> None:
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


def export_artifact(
    root: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = validate_output_target(root, Path(output_dir))
    rom = (root / "rom/base.gba").read_bytes()
    if sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")

    table = rom[TABLE_OFFSET : TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE]
    if len(table) != ENTRY_COUNT * ENTRY_SIZE or sha256(table) != TABLE_SHA256:
        raise ValueError("scene visual-pack table SHA-256 mismatch")

    consumer_evidence: dict[str, Any] = {}
    for name, (start, end, expected_hash) in CONSUMER_RANGES.items():
        raw = _slice(rom, start, end - start)
        if sha256(raw) != expected_hash:
            raise ValueError(f"consumer evidence changed: {name}")
        consumer_evidence[name] = {
            "gba_range": [_address(start), _address(end)],
            "size": len(raw),
            "sha256": expected_hash,
        }

    files: dict[str, bytes] = {}
    palettes: list[dict[str, Any]] = []
    palette_data: list[bytes] = []
    for definition in OBJ_PALETTES:
        raw = _slice(rom, definition["address"], 32)
        if sha256(raw) != definition["sha256"]:
            raise ValueError("shared OBJ palette SHA-256 mismatch")
        filename = f"shared/obj-palette-{definition['bank']}.bgr555"
        files[filename] = raw
        palette_data.append(raw)
        palettes.append(
            {
                "bank": definition["bank"],
                "gba_address": _address(definition["address"]),
                "destination": _address(definition["destination"]),
                "size": len(raw),
                "color_count": 16,
                "sha256": definition["sha256"],
                "file": filename,
            }
        )

    packs: list[dict[str, Any]] = []
    total_frames = 0
    for pack_id in range(ENTRY_COUNT):
        entry_address = TABLE_ADDRESS + pack_id * ENTRY_SIZE
        raw_entry = table[pack_id * ENTRY_SIZE : (pack_id + 1) * ENTRY_SIZE]
        (
            bg_gfx_pointer,
            bg_map_pointer,
            bg_palette_pointer,
            obj_gfx_pointer,
            definition_pointer,
            animation_pointer,
            width_tiles,
            height_tiles,
            presentation_id,
            spawn_count,
        ) = struct.unpack("<IIIIIIBBBB", raw_entry)
        if height_tiles != 20 or width_tiles <= 0:
            raise ValueError(f"unexpected packed dimensions in pack {pack_id}")
        if spawn_count not in (1, 2):
            raise ValueError(f"unexpected spawn count in pack {pack_id}")
        prefix = f"pack-{pack_id:02d}"

        bg_compressed, bg_graphics = _resource(rom, bg_gfx_pointer)
        map_size = width_tiles * height_tiles * 2
        map_compressed, tilemap = _resource(
            rom,
            bg_map_pointer,
            expected_size=map_size,
        )
        background_palette = _slice(rom, bg_palette_pointer, 256)
        if len(bg_graphics) % 64:
            raise ValueError("background graphics are not 8bpp tile aligned")
        bg_pixels, map_facts = _render_8bpp_tilemap(
            bg_graphics,
            tilemap,
            width_tiles=width_tiles,
            height_tiles=height_tiles,
        )
        if map_facts["palette_bank_values"] != [0]:
            raise ValueError("8bpp tilemap has nonzero palette-bank bits")
        bg_png = indexed_png_from_bgr555(
            bg_pixels,
            background_palette,
            width=width_tiles * 8,
            height=height_tiles * 8,
        )
        bg_gfx_file = f"{prefix}/background-gfx.8bpp"
        bg_map_file = f"{prefix}/background-tilemap.bin"
        bg_palette_file = f"{prefix}/background-palette.bgr555"
        bg_png_file = f"{prefix}/background.png"
        files[bg_gfx_file] = bg_graphics
        files[bg_map_file] = tilemap
        files[bg_palette_file] = background_palette
        files[bg_png_file] = bg_png

        obj_compressed, obj_graphics = _resource(rom, obj_gfx_pointer)
        if len(obj_graphics) % 32:
            raise ValueError("OBJ graphics are not 4bpp tile aligned")
        obj_file = f"{prefix}/obj-gfx.4bpp"
        files[obj_file] = obj_graphics
        atlas_pixels, atlas_width, atlas_height = (
            render_4bpp_tile_atlas_indices(
                obj_graphics,
                tiles_per_row=16,
            )
        )
        atlases = []
        for bank, palette in enumerate(palette_data):
            atlas_png = indexed_png_from_bgr555(
                atlas_pixels,
                palette,
                width=atlas_width,
                height=atlas_height,
                transparent_index=0,
            )
            atlas_file = f"{prefix}/obj-atlas-palette-{bank}.png"
            files[atlas_file] = atlas_png
            atlases.append(
                {
                    "palette_bank": bank,
                    "file": atlas_file,
                    "width": atlas_width,
                    "height": atlas_height,
                    "sha256": sha256(atlas_png),
                }
            )

        frames, timeline_start, definition_region = _frames(
            rom,
            definition_pointer,
        )
        animations, animation_region = _animations(
            rom,
            timeline_start,
            animation_pointer,
            len(frames),
        )
        if len(frames) != spawn_count or len(animations) != spawn_count:
            raise ValueError("spawn/frame/animation count mismatch")
        if [item["frame_id"] for item in animations] != list(range(spawn_count)):
            raise ValueError("animation frame selection is not one-to-one")
        definition_file = f"{prefix}/obj-definition-region.bin"
        animation_file = f"{prefix}/obj-animation-region.bin"
        files[definition_file] = definition_region
        files[animation_file] = animation_region

        frame_entries = []
        referenced_tiles: set[int] = set()
        for frame in frames:
            palette_bank = frame["frame_id"]
            png, width, height, bounds, referenced, pixels = _render_frame(
                frame,
                obj_graphics,
                palette_data[palette_bank],
            )
            if referenced and max(referenced) >= len(obj_graphics) // 32:
                raise ValueError("OBJ frame references a tile outside graphics")
            referenced_tiles.update(referenced)
            png_file = f"{prefix}/obj-frame-{frame['frame_id']:02d}.png"
            files[png_file] = png
            frame_entries.append(
                {
                    **frame,
                    "palette_bank": palette_bank,
                    "png": {
                        "file": png_file,
                        "width": width,
                        "height": height,
                        "local_bounds": bounds,
                        "pixel_sha256": sha256(pixels),
                        "sha256": sha256(png),
                    },
                }
            )
        obj_tile_count = len(obj_graphics) // 32
        missing_obj_tiles = sorted(
            set(range(obj_tile_count)) - referenced_tiles
        )
        if missing_obj_tiles:
            raise ValueError(f"pack {pack_id} has unreferenced OBJ tiles")
        total_frames += len(frame_entries)

        packs.append(
            {
                "pack_id": pack_id,
                "entry_gba_address": _address(entry_address),
                "entry_sha256": sha256(raw_entry),
                "raw_hex": raw_entry.hex(),
                "presentation_id": presentation_id,
                "spawn_count": spawn_count,
                "background": {
                    "bits_per_pixel": 8,
                    "graphics_pointer": gba_pointer(bg_gfx_pointer),
                    "graphics_compressed_size": len(bg_compressed),
                    "graphics_compressed_sha256": sha256(bg_compressed),
                    "graphics_file": bg_gfx_file,
                    "graphics_sha256": sha256(bg_graphics),
                    "tile_count": len(bg_graphics) // 64,
                    "tilemap_pointer": gba_pointer(bg_map_pointer),
                    "tilemap_compressed_size": len(map_compressed),
                    "tilemap_compressed_sha256": sha256(map_compressed),
                    "tilemap_file": bg_map_file,
                    "tilemap_sha256": sha256(tilemap),
                    "palette_pointer": gba_pointer(bg_palette_pointer),
                    "palette_file": bg_palette_file,
                    "palette_size": len(background_palette),
                    "palette_color_count": len(background_palette) // 2,
                    "palette_sha256": sha256(background_palette),
                    "width_tiles": width_tiles,
                    "height_tiles": height_tiles,
                    **map_facts,
                    "canvas": {
                        "file": bg_png_file,
                        "width": width_tiles * 8,
                        "height": height_tiles * 8,
                        "pixel_sha256": sha256(bg_pixels),
                        "sha256": sha256(bg_png),
                    },
                    "hardware": {
                        "bgcnt": "0x4086",
                        "character_base": "0x06004000",
                        "screen_base": "0x06000000",
                        "hardware_canvas": [512, 256],
                    },
                },
                "obj": {
                    "bits_per_pixel": 4,
                    "graphics_pointer": gba_pointer(obj_gfx_pointer),
                    "graphics_compressed_size": len(obj_compressed),
                    "graphics_compressed_sha256": sha256(obj_compressed),
                    "graphics_file": obj_file,
                    "graphics_sha256": sha256(obj_graphics),
                    "tile_count": obj_tile_count,
                    "definition_pointer": gba_pointer(definition_pointer),
                    "definition_region_file": definition_file,
                    "definition_region_sha256": sha256(definition_region),
                    "animation_pointer": gba_pointer(animation_pointer),
                    "animation_region_file": animation_file,
                    "animation_region_sha256": sha256(animation_region),
                    "atlases": atlases,
                    "frames": frame_entries,
                    "animations": animations,
                    "referenced_tile_indices": sorted(referenced_tiles),
                    "missing_tile_indices": missing_obj_tiles,
                    "all_tiles_referenced": not missing_obj_tiles,
                },
            }
        )

    manifest = {
        "schema": SCHEMA,
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "source_table": {
            "gba_address": _address(TABLE_ADDRESS),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "sha256": TABLE_SHA256,
        },
        "consumer_evidence": consumer_evidence,
        "obj_selection_chain": {
            "loop_index_selects_animation": True,
            "loop_index_selects_palette_bank": True,
            "timeline_frame_id_selects_definition_frame": True,
            "current_rows_map_animation_to_same_numbered_frame": True,
        },
        "shared_obj_palettes": palettes,
        "packs": packs,
        "summary": {
            "pack_count": len(packs),
            "background_canvas_count": len(packs),
            "obj_graphics_pack_count": len(packs),
            "obj_frame_count": total_frames,
            "obj_atlas_count": len(packs) * len(palettes),
        },
        "scope": {
            "all_table_rows_exported": True,
            "native_background_canvases_complete": True,
            "obj_definition_frames_complete": True,
            "obj_animation_frame_sets_complete": True,
            "obj_animation_timing_complete": False,
            "screen_space_composition_complete": False,
            "natural_language_scene_names_complete": False,
            "final_viewport_crop_complete": False,
        },
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    _replace_output(output_dir, files)
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/scene-visual-packs-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_artifact(args.root, args.output_dir)
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
