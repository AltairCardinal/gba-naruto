#!/usr/bin/env python3
"""Independently verify the 0x085A4CE8 scene visual-pack artifact."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "scene-visual-packs-v1"
TABLE_ADDRESS = 0x085A4CE8
TABLE_OFFSET = TABLE_ADDRESS - ROM_BASE
ENTRY_COUNT = 9
ENTRY_SIZE = 0x1C
TABLE_SHA256 = "b562062061a088aac2e5ce2f2d9f8bbfd34f0cb53a794a7ea5b0f270ecf909b3"
TERMINATOR = b"\xFF\xFF\x00\x00"
CONSUMERS = {
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
    "sprite_motion_callback": (
        0x0808C030,
        0x0808C078,
        "ee6f94b5978f5824f37d73b77344cbec1f474c1f6535b8469f90e8e910a95515",
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
PALETTES = (
    (
        0x083F2794,
        0x05000200,
        "14975f2391f88813040bbadc136bbfcaa736a408521af3701054bf0470d5a4f9",
    ),
    (
        0x083F2CB0,
        0x05000220,
        "bb58f9bc0be9a3b7ad2604ced29815b23d55660c89e70e59430959cf7aed8b2f",
    ),
)

OBJ_ANIMATION_RUNTIME = {
    "spawner_requested_flags": "0x000000A0",
    "allocator_active_bit": "0x00000001",
    "initial_task_flags": "0x000000A1",
    "termination_policy_bits": "0x20",
    "timer_storage": "u16",
    "timer_initial": 0,
    "timer_increment_per_update": 1,
    "duration_compare": "duration_ticks == timer_after_increment",
    "zero_duration_first_expiry_updates": 65536,
    "terminator_frame_index": -1,
    "terminator_policy": "reset_frame_cursor_and_timer_then_loop",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _slice(rom: bytes, address: int, size: int) -> bytes:
    offset = address - ROM_BASE
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"invalid ROM range at {_address(address)}")
    return rom[offset : offset + size]


def _lz(rom: bytes, pointer: int) -> tuple[bytes, bytes]:
    offset = pointer - ROM_BASE
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"invalid LZ77 resource at {_address(pointer)}")
    size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 back-reference")
                first, second = rom[cursor : cursor + 2]
                cursor += 2
                length = (first >> 4) + 3
                distance = ((first & 15) << 8 | second) + 1
                if distance > len(output) or len(output) + length > size:
                    raise ValueError("invalid LZ77 back-reference")
                for _ in range(length):
                    output.append(output[-distance])
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return rom[offset:cursor], bytes(output)


def _palette_rgb(raw: bytes) -> bytes:
    result = bytearray()
    for offset in range(0, len(raw), 2):
        value = struct.unpack_from("<H", raw, offset)[0]
        red = value & 31
        green = value >> 5 & 31
        blue = value >> 10 & 31
        result.extend(
            (
                (red << 3) | (red >> 2),
                (green << 3) | (green >> 2),
                (blue << 3) | (blue >> 2),
            )
        )
    return bytes(result)


def _png(raw: bytes) -> tuple[int, int, bytes, bytes, bytes | None]:
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG signature")
    cursor = 8
    chunks: dict[bytes, list[bytes]] = {}
    while cursor < len(raw):
        if cursor + 12 > len(raw):
            raise ValueError("truncated PNG chunk")
        size = struct.unpack_from(">I", raw, cursor)[0]
        kind = raw[cursor + 4 : cursor + 8]
        data = raw[cursor + 8 : cursor + 8 + size]
        checksum = struct.unpack_from(">I", raw, cursor + 8 + size)[0]
        if binascii.crc32(kind + data) & 0xFFFFFFFF != checksum:
            raise ValueError("PNG CRC mismatch")
        chunks.setdefault(kind, []).append(data)
        cursor += size + 12
        if kind == b"IEND":
            break
    if cursor != len(raw):
        raise ValueError("data follows PNG IEND")
    ihdr = chunks[b"IHDR"][0]
    width, height, depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", ihdr)
    )
    if (depth, color_type, compression, filtering, interlace) != (8, 3, 0, 0, 0):
        raise ValueError("unexpected indexed PNG format")
    scanlines = zlib.decompress(b"".join(chunks[b"IDAT"]))
    if len(scanlines) != height * (width + 1):
        raise ValueError("unexpected PNG scanline length")
    pixels = bytearray()
    for row in range(height):
        start = row * (width + 1)
        if scanlines[start] != 0:
            raise ValueError("unsupported PNG filter")
        pixels.extend(scanlines[start + 1 : start + 1 + width])
    transparency = (
        chunks.get(b"tRNS", [None])[0]
        if b"tRNS" in chunks
        else None
    )
    return width, height, bytes(pixels), chunks[b"PLTE"][0], transparency


def _background(
    graphics: bytes,
    tilemap: bytes,
    width_tiles: int,
    height_tiles: int,
) -> tuple[bytes, set[int], int, int, set[int]]:
    if len(graphics) % 64 or len(tilemap) != width_tiles * height_tiles * 2:
        raise ValueError("invalid background resources")
    entries = struct.unpack(f"<{width_tiles * height_tiles}H", tilemap)
    tile_count = len(graphics) // 64
    width = width_tiles * 8
    pixels = bytearray(width * height_tiles * 8)
    referenced: set[int] = set()
    horizontal_count = 0
    vertical_count = 0
    palette_banks: set[int] = set()
    for tile_y in range(height_tiles):
        for tile_x in range(width_tiles):
            entry = entries[tile_y * width_tiles + tile_x]
            tile = entry & 0x03FF
            if tile >= tile_count:
                raise ValueError("background tile is outside graphics")
            referenced.add(tile)
            horizontal = bool(entry & 0x0400)
            vertical = bool(entry & 0x0800)
            horizontal_count += horizontal
            vertical_count += vertical
            palette_banks.add(entry >> 12)
            for y in range(8):
                source_y = 7 - y if vertical else y
                for x in range(8):
                    source_x = 7 - x if horizontal else x
                    pixels[
                        (tile_y * 8 + y) * width + tile_x * 8 + x
                    ] = graphics[tile * 64 + source_y * 8 + source_x]
    return (
        bytes(pixels),
        referenced,
        horizontal_count,
        vertical_count,
        palette_banks,
    )


def _component(raw: bytes, component_id: int) -> dict[str, Any]:
    values = struct.unpack("<HHhhHHHHBBH", raw)
    tile, flags, x, y, width, height, sx, sy, control, affine, reserved = values
    if (
        tile == 0xFFFF
        or flags & ~3
        or width not in (8, 16, 32, 64)
        or height not in (8, 16, 32, 64)
        or control not in (0, 0xFF)
        or affine not in (0, 1)
        or reserved
    ):
        raise ValueError("invalid component record")
    return {
        "component_id": component_id,
        "tile_index": tile,
        "tile_flags": flags,
        "horizontal_flip": bool(flags & 1),
        "vertical_flip": bool(flags & 2),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "scale_x": sx,
        "scale_y": sy,
        "control": control,
        "affine_mode": affine,
        "raw_hex": raw.hex(),
    }


def _definitions(
    rom: bytes,
    pointer: int,
) -> tuple[list[dict[str, Any]], int, bytes]:
    cursor = pointer - ROM_BASE
    frame_pointers = []
    while cursor + 4 <= len(rom):
        value = struct.unpack_from("<I", rom, cursor)[0]
        if not ROM_BASE <= value < pointer:
            break
        if frame_pointers and value <= frame_pointers[-1]:
            raise ValueError("unordered frame pointers")
        frame_pointers.append(value)
        cursor += 4
    if not frame_pointers:
        raise ValueError("missing frame pointers")
    timeline_start = ROM_BASE + cursor
    frames = []
    for frame_id, (start_address, end_address) in enumerate(
        zip(frame_pointers, frame_pointers[1:] + [pointer])
    ):
        start = start_address - ROM_BASE
        cursor = start
        components = []
        while rom[cursor : cursor + 4] != TERMINATOR:
            raw = rom[cursor : cursor + 0x14]
            if len(raw) != 0x14:
                raise ValueError("truncated component")
            components.append(_component(raw, len(components)))
            cursor += 0x14
        cursor += 4
        if ROM_BASE + cursor != end_address:
            raise ValueError("non-contiguous component lists")
        raw = rom[start:cursor]
        frames.append(
            {
                "frame_id": frame_id,
                "component_list_pointer": _address(start_address),
                "component_count": len(components),
                "components": components,
                "raw_size": len(raw),
                "raw_sha256": _sha(raw),
            }
        )
    region = _slice(
        rom,
        frame_pointers[0],
        pointer + len(frame_pointers) * 4 - frame_pointers[0],
    )
    return frames, timeline_start, region


def _animations(
    rom: bytes,
    timeline_start: int,
    pointer: int,
    frame_count: int,
) -> tuple[list[dict[str, Any]], bytes]:
    cursor = pointer - ROM_BASE
    pointers = []
    while cursor + 4 <= len(rom):
        value = struct.unpack_from("<I", rom, cursor)[0]
        if not timeline_start <= value < pointer:
            break
        if pointers and value <= pointers[-1]:
            raise ValueError("unordered animation pointers")
        pointers.append(value)
        cursor += 4
    if not pointers:
        raise ValueError("missing animation pointers")
    result = []
    for animation_id, (start, end) in enumerate(
        zip(pointers, pointers[1:] + [pointer])
    ):
        raw = _slice(rom, start, 8)
        frame, timing, terminator, terminator_value = struct.unpack("<HHHH", raw)
        if (
            frame >= frame_count
            or terminator != 0xFFFF
            or terminator_value
            or start + 8 != end
        ):
            raise ValueError("invalid animation timeline")
        result.append(
            {
                "animation_id": animation_id,
                "timeline_pointer": _address(start),
                "frame_id": frame,
                "timing_value": timing,
                "duration_ticks": timing,
                "timing_semantics": "u16_timer_equality_after_increment",
                "timer_period_updates": timing or 65536,
                "termination_policy": "loop",
                "playback": [
                    {
                        "frame_id": frame,
                        "start_update": 0,
                        "end_update_exclusive": timing or 65536,
                    }
                ],
                "terminator": [0xFFFF, 0],
                "raw_size": 8,
                "raw_sha256": _sha(raw),
            }
        )
    region = _slice(
        rom,
        pointers[0],
        pointer + len(pointers) * 4 - pointers[0],
    )
    return result, region


def _tile_block(
    graphics: bytes,
    tile_offset: int,
    width_tiles: int,
    height_tiles: int,
) -> bytes:
    output = bytearray(width_tiles * 8 * height_tiles * 8)
    width = width_tiles * 8
    for tile_y in range(height_tiles):
        for tile_x in range(width_tiles):
            tile = tile_offset + tile_y * width_tiles + tile_x
            for y in range(8):
                for x in range(8):
                    packed = graphics[tile * 32 + y * 4 + x // 2]
                    output[
                        (tile_y * 8 + y) * width + tile_x * 8 + x
                    ] = packed >> (4 if x & 1 else 0) & 15
    return bytes(output)


def _flip(
    pixels: bytes,
    width: int,
    height: int,
    horizontal: bool,
    vertical: bool,
) -> bytes:
    output = bytearray(len(pixels))
    for y in range(height):
        source_y = height - y - 1 if vertical else y
        for x in range(width):
            source_x = width - x - 1 if horizontal else x
            output[y * width + x] = pixels[source_y * width + source_x]
    return bytes(output)


def _frame_pixels(
    frame: dict[str, Any],
    graphics: bytes,
) -> tuple[bytes, int, int, dict[str, int], set[int]]:
    components = frame["components"]
    min_x = min(item["x"] for item in components)
    min_y = min(item["y"] for item in components)
    max_x = max(item["x"] + item["width"] for item in components)
    max_y = max(item["y"] + item["height"] for item in components)
    width = max_x - min_x
    height = max_y - min_y
    output = bytearray(width * height)
    referenced: set[int] = set()
    for item in components:
        width_tiles = item["width"] // 8
        height_tiles = item["height"] // 8
        tile_count = width_tiles * height_tiles
        referenced.update(
            range(item["tile_index"], item["tile_index"] + tile_count)
        )
        block = _tile_block(
            graphics,
            item["tile_index"],
            width_tiles,
            height_tiles,
        )
        block = _flip(
            block,
            item["width"],
            item["height"],
            item["horizontal_flip"],
            item["vertical_flip"],
        )
        destination_x = item["x"] - min_x
        destination_y = item["y"] - min_y
        for y in range(item["height"]):
            for x in range(item["width"]):
                color = block[y * item["width"] + x]
                if color:
                    output[
                        (destination_y + y) * width + destination_x + x
                    ] = color
    return (
        bytes(output),
        width,
        height,
        {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
        referenced,
    )


def _atlas(graphics: bytes) -> tuple[bytes, int, int]:
    tile_count = len(graphics) // 32
    columns = min(tile_count, 16)
    rows = (tile_count + 15) // 16
    width = columns * 8
    pixels = bytearray(width * rows * 8)
    for tile in range(tile_count):
        tile_x = tile % 16
        tile_y = tile // 16
        for y in range(8):
            for x in range(8):
                packed = graphics[tile * 32 + y * 4 + x // 2]
                pixels[
                    (tile_y * 8 + y) * width + tile_x * 8 + x
                ] = packed >> (4 if x & 1 else 0) & 15
    return bytes(pixels), width, rows * 8


def _expect_file(
    artifact: Path,
    relative: str,
    expected: bytes,
    expected_files: set[str],
) -> bytes:
    expected_files.add(relative)
    actual = (artifact / relative).read_bytes()
    if actual != expected:
        raise ValueError(f"file differs from ROM-derived bytes: {relative}")
    return actual


def _expect_png(
    artifact: Path,
    relative: str,
    *,
    pixels: bytes,
    width: int,
    height: int,
    palette: bytes,
    transparent: bool,
    expected_files: set[str],
) -> bytes:
    expected_files.add(relative)
    raw = (artifact / relative).read_bytes()
    actual_width, actual_height, actual_pixels, plte, trns = _png(raw)
    if (actual_width, actual_height, actual_pixels) != (width, height, pixels):
        raise ValueError(f"PNG raster mismatch: {relative}")
    if plte != _palette_rgb(palette):
        raise ValueError(f"PNG palette mismatch: {relative}")
    expected_alpha = (
        b"\x00" + b"\xFF" * (len(palette) // 2 - 1)
        if transparent
        else None
    )
    if trns != expected_alpha:
        raise ValueError(f"PNG transparency mismatch: {relative}")
    return raw


def _verify(root: Path, artifact: Path) -> tuple[int, int, int]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    table = rom[TABLE_OFFSET : TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE]
    if _sha(table) != TABLE_SHA256:
        raise ValueError("source table SHA-256 mismatch")
    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("manifest schema mismatch")
    if manifest.get("rom") != {
        "path": "rom/base.gba",
        "size": len(rom),
        "sha256": ROM_SHA256,
    }:
        raise ValueError("manifest ROM binding mismatch")
    if manifest.get("source_table") != {
        "gba_address": _address(TABLE_ADDRESS),
        "entry_count": ENTRY_COUNT,
        "entry_size": ENTRY_SIZE,
        "sha256": TABLE_SHA256,
    }:
        raise ValueError("manifest source-table binding mismatch")
    for name, (start, end, expected_hash) in CONSUMERS.items():
        if _sha(_slice(rom, start, end - start)) != expected_hash:
            raise ValueError(f"consumer evidence changed: {name}")
        record = manifest["consumer_evidence"][name]
        if record != {
            "gba_range": [_address(start), _address(end)],
            "size": end - start,
            "sha256": expected_hash,
        }:
            raise ValueError(f"consumer manifest mismatch: {name}")
    if manifest.get("obj_selection_chain") != {
        "loop_index_selects_animation": True,
        "loop_index_selects_palette_bank": True,
        "timeline_frame_id_selects_definition_frame": True,
        "current_rows_map_animation_to_same_numbered_frame": True,
    }:
        raise ValueError("OBJ selection-chain manifest mismatch")
    if manifest.get("obj_animation_runtime") != OBJ_ANIMATION_RUNTIME:
        raise ValueError("OBJ animation-runtime manifest mismatch")

    expected_files = {"manifest.json"}
    palette_data = []
    for bank, (address, destination, expected_hash) in enumerate(PALETTES):
        raw = _slice(rom, address, 32)
        if _sha(raw) != expected_hash:
            raise ValueError("shared OBJ palette changed")
        relative = f"shared/obj-palette-{bank}.bgr555"
        _expect_file(artifact, relative, raw, expected_files)
        palette_data.append(raw)
        if manifest["shared_obj_palettes"][bank] != {
            "bank": bank,
            "gba_address": _address(address),
            "destination": _address(destination),
            "size": 32,
            "color_count": 16,
            "sha256": expected_hash,
            "file": relative,
        }:
            raise ValueError("shared OBJ palette manifest mismatch")

    packs = manifest.get("packs")
    if not isinstance(packs, list) or len(packs) != ENTRY_COUNT:
        raise ValueError("manifest does not contain nine packs")
    total_frames = 0
    total_animations = 0
    for pack_id, pack in enumerate(packs):
        raw_entry = table[pack_id * ENTRY_SIZE : (pack_id + 1) * ENTRY_SIZE]
        values = struct.unpack("<IIIIIIBBBB", raw_entry)
        (
            bg_pointer,
            map_pointer,
            pal_pointer,
            obj_pointer,
            def_pointer,
            anim_pointer,
            width_tiles,
            height_tiles,
            presentation,
            spawn_count,
        ) = values
        if (
            pack["pack_id"] != pack_id
            or pack["entry_gba_address"]
            != _address(TABLE_ADDRESS + pack_id * ENTRY_SIZE)
            or pack["entry_sha256"] != _sha(raw_entry)
            or pack["raw_hex"] != raw_entry.hex()
            or pack["presentation_id"] != presentation
            or pack["spawn_count"] != spawn_count
        ):
            raise ValueError(f"pack {pack_id} descriptor mismatch")
        prefix = f"pack-{pack_id:02d}"

        bg_compressed, graphics = _lz(rom, bg_pointer)
        map_compressed, tilemap = _lz(rom, map_pointer)
        palette = _slice(rom, pal_pointer, 256)
        if len(tilemap) != width_tiles * height_tiles * 2:
            raise ValueError("background dimensions do not match tilemap")
        pixels, referenced, hflips, vflips, banks = _background(
            graphics,
            tilemap,
            width_tiles,
            height_tiles,
        )
        if banks != {0} or referenced != set(range(len(graphics) // 64)):
            raise ValueError("background tile coverage mismatch")
        bg = pack["background"]
        bg_gfx_file = f"{prefix}/background-gfx.8bpp"
        bg_map_file = f"{prefix}/background-tilemap.bin"
        bg_palette_file = f"{prefix}/background-palette.bgr555"
        bg_png_file = f"{prefix}/background.png"
        _expect_file(artifact, bg_gfx_file, graphics, expected_files)
        _expect_file(artifact, bg_map_file, tilemap, expected_files)
        _expect_file(artifact, bg_palette_file, palette, expected_files)
        png_raw = _expect_png(
            artifact,
            bg_png_file,
            pixels=pixels,
            width=width_tiles * 8,
            height=height_tiles * 8,
            palette=palette,
            transparent=False,
            expected_files=expected_files,
        )
        expected_background = {
            "bits_per_pixel": 8,
            "graphics_pointer": _address(bg_pointer),
            "graphics_compressed_size": len(bg_compressed),
            "graphics_compressed_sha256": _sha(bg_compressed),
            "graphics_file": bg_gfx_file,
            "graphics_sha256": _sha(graphics),
            "tile_count": len(graphics) // 64,
            "tilemap_pointer": _address(map_pointer),
            "tilemap_compressed_size": len(map_compressed),
            "tilemap_compressed_sha256": _sha(map_compressed),
            "tilemap_file": bg_map_file,
            "tilemap_sha256": _sha(tilemap),
            "palette_pointer": _address(pal_pointer),
            "palette_file": bg_palette_file,
            "palette_size": 256,
            "palette_color_count": 128,
            "palette_sha256": _sha(palette),
            "width_tiles": width_tiles,
            "height_tiles": height_tiles,
            "referenced_tile_indices": sorted(referenced),
            "missing_tile_indices": [],
            "all_tiles_referenced": True,
            "horizontal_flip_entry_count": hflips,
            "vertical_flip_entry_count": vflips,
            "palette_bank_values": [0],
            "canvas": {
                "file": bg_png_file,
                "width": width_tiles * 8,
                "height": height_tiles * 8,
                "pixel_sha256": _sha(pixels),
                "sha256": _sha(png_raw),
            },
            "hardware": {
                "bgcnt": "0x4086",
                "character_base": "0x06004000",
                "screen_base": "0x06000000",
                "hardware_canvas": [512, 256],
            },
        }
        if bg != expected_background:
            raise ValueError(f"pack {pack_id} background manifest mismatch")

        obj_compressed, obj_graphics = _lz(rom, obj_pointer)
        obj_file = f"{prefix}/obj-gfx.4bpp"
        _expect_file(artifact, obj_file, obj_graphics, expected_files)
        atlas_pixels, atlas_width, atlas_height = _atlas(obj_graphics)
        expected_atlases = []
        for bank, obj_palette in enumerate(palette_data):
            relative = f"{prefix}/obj-atlas-palette-{bank}.png"
            raw = _expect_png(
                artifact,
                relative,
                pixels=atlas_pixels,
                width=atlas_width,
                height=atlas_height,
                palette=obj_palette,
                transparent=True,
                expected_files=expected_files,
            )
            expected_atlases.append(
                {
                    "palette_bank": bank,
                    "file": relative,
                    "width": atlas_width,
                    "height": atlas_height,
                    "sha256": _sha(raw),
                }
            )
        frames, timeline_start, definition_region = _definitions(
            rom,
            def_pointer,
        )
        animations, animation_region = _animations(
            rom,
            timeline_start,
            anim_pointer,
            len(frames),
        )
        if len(frames) != spawn_count or len(animations) != spawn_count:
            raise ValueError("spawn/frame/animation count mismatch")
        expected_animations = []
        for animation in animations:
            timeline_file = (
                f"{prefix}/obj-animation-{animation['animation_id']:02d}.json"
            )
            entry = {**animation, "timeline_file": timeline_file}
            _expect_file(
                artifact,
                timeline_file,
                (json.dumps(entry, ensure_ascii=False, indent=2) + "\n").encode(
                    "utf-8"
                ),
                expected_files,
            )
            expected_animations.append(entry)
        def_file = f"{prefix}/obj-definition-region.bin"
        anim_file = f"{prefix}/obj-animation-region.bin"
        _expect_file(artifact, def_file, definition_region, expected_files)
        _expect_file(artifact, anim_file, animation_region, expected_files)
        expected_frames = []
        referenced_obj: set[int] = set()
        for frame in frames:
            frame_id = frame["frame_id"]
            frame_pixels, width, height, bounds, referenced_tiles = (
                _frame_pixels(frame, obj_graphics)
            )
            referenced_obj.update(referenced_tiles)
            relative = f"{prefix}/obj-frame-{frame_id:02d}.png"
            raw = _expect_png(
                artifact,
                relative,
                pixels=frame_pixels,
                width=width,
                height=height,
                palette=palette_data[frame_id],
                transparent=True,
                expected_files=expected_files,
            )
            expected_frames.append(
                {
                    **frame,
                    "palette_bank": frame_id,
                    "png": {
                        "file": relative,
                        "width": width,
                        "height": height,
                        "local_bounds": bounds,
                        "pixel_sha256": _sha(frame_pixels),
                        "sha256": _sha(raw),
                    },
                }
            )
        tile_count = len(obj_graphics) // 32
        if referenced_obj != set(range(tile_count)):
            raise ValueError("OBJ definition does not cover all source tiles")
        expected_obj = {
            "bits_per_pixel": 4,
            "graphics_pointer": _address(obj_pointer),
            "graphics_compressed_size": len(obj_compressed),
            "graphics_compressed_sha256": _sha(obj_compressed),
            "graphics_file": obj_file,
            "graphics_sha256": _sha(obj_graphics),
            "tile_count": tile_count,
            "definition_pointer": _address(def_pointer),
            "definition_region_file": def_file,
            "definition_region_sha256": _sha(definition_region),
            "animation_pointer": _address(anim_pointer),
            "animation_region_file": anim_file,
            "animation_region_sha256": _sha(animation_region),
            "atlases": expected_atlases,
            "frames": expected_frames,
            "animations": expected_animations,
            "referenced_tile_indices": sorted(referenced_obj),
            "missing_tile_indices": [],
            "all_tiles_referenced": True,
        }
        if pack["obj"] != expected_obj:
            raise ValueError(f"pack {pack_id} OBJ manifest mismatch")
        total_frames += len(frames)
        total_animations += len(expected_animations)

    expected_summary = {
        "pack_count": 9,
        "background_canvas_count": 9,
        "obj_graphics_pack_count": 9,
        "obj_frame_count": total_frames,
        "obj_animation_count": total_animations,
        "obj_atlas_count": 18,
    }
    if manifest.get("summary") != expected_summary:
        raise ValueError("manifest summary mismatch")
    expected_scope = {
        "all_table_rows_exported": True,
        "native_background_canvases_complete": True,
        "obj_definition_frames_complete": True,
        "obj_animation_frame_sets_complete": True,
        "obj_animation_timing_complete": True,
        "screen_space_composition_complete": False,
        "natural_language_scene_names_complete": False,
        "final_viewport_crop_complete": False,
    }
    if manifest.get("scope") != expected_scope:
        raise ValueError("manifest scope mismatch")
    actual_files = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("artifact file set mismatch")
    return len(packs), total_frames, total_animations


def verify_artifact(
    root: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    errors = []
    pack_count = 0
    frame_count = 0
    animation_count = 0
    try:
        pack_count, frame_count, animation_count = _verify(
            Path(root).resolve(),
            Path(artifact_dir).resolve(),
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "verified": not errors,
        "errors": errors,
        "pack_count": pack_count,
        "obj_frame_count": frame_count,
        "obj_animation_count": animation_count,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/scene-visual-packs-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
