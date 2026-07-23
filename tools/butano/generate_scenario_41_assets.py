#!/usr/bin/env python3
"""Generate deterministic 4bpp Butano graphics for the scenario 41 battle."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import (  # noqa: E402
    lz77_decompress,
    parse_palette,
    read_map_entries,
)
from tools.butano.render_scenario_41_gpu import (  # noqa: E402
    _background_pixel,
    _object_pixel,
    _rgb,
    render_boundary,
)
from tools.butano.analyze_scenario_41_gpu import decode_gpu  # noqa: E402


EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)


PALETTE = (
    (0, 0, 0),
    (18, 48, 20),
    (42, 93, 36),
    (76, 132, 48),
    (121, 167, 61),
    (74, 48, 24),
    (112, 75, 34),
    (49, 62, 78),
    (37, 91, 151),
    (238, 134, 25),
    (252, 211, 56),
    (224, 178, 131),
    (105, 112, 116),
    (208, 216, 206),
    (246, 238, 197),
    (255, 247, 72),
)

MAP_WIDTH = 256
MAP_HEIGHT = 512
GRID_ORIGIN_X = 56
GRID_ORIGIN_Y = 80
CELL_SIZE = 16
OBSTACLES = ((3, 9), (5, 9), (2, 7), (6, 7), (1, 4), (7, 4))


def reconstruct_map(rom_path: Path) -> dict[str, object]:
    """Rebuild map row 41 from its two-metatile coarse layout."""

    rom = Path(rom_path).read_bytes()
    actual_hash = hashlib.sha256(rom).hexdigest()
    if actual_hash != EXPECTED_ROM_SHA256:
        raise ValueError(f"ROM SHA-256 mismatch: {actual_hash}")
    entry = read_map_entries(rom)[41]
    tile_data = lz77_decompress(rom, entry["tile_gfx_ptr"])
    palette_data = lz77_decompress(rom, entry["bg_palette_ptr"])
    layout = lz77_decompress(rom, entry["primary_layout_ptr"])
    metatiles = lz77_decompress(rom, entry["metatile_attributes_ptr"])
    if len(layout) != 9 * 22 * 4 or len(metatiles) % 8:
        raise ValueError("scenario 41 map resources have unexpected dimensions")

    tilemap = [0] * (36 * 44)
    for coarse_y in range(22):
        for coarse_x in range(9):
            value = struct.unpack_from("<I", layout, (coarse_y * 9 + coarse_x) * 4)[0]
            for half, metatile_index in enumerate((value & 0xFFFF, value >> 16)):
                definition_offset = metatile_index * 8
                if definition_offset + 8 > len(metatiles):
                    raise ValueError(f"metatile index {metatile_index} is out of range")
                definition = struct.unpack_from("<4H", metatiles, definition_offset)
                for local_y in range(2):
                    for local_x in range(2):
                        tile_x = coarse_x * 4 + half * 2 + local_x
                        tile_y = coarse_y * 2 + local_y
                        tilemap[tile_y * 36 + tile_x] = definition[local_y * 2 + local_x]

    palette = parse_palette(palette_data)
    pixels = bytearray(288 * 352)
    for tile_y in range(44):
        for tile_x in range(36):
            entry_value = tilemap[tile_y * 36 + tile_x]
            tile_index = entry_value & 0x3FF
            tile_offset = tile_index * 32
            if tile_offset + 32 > len(tile_data):
                raise ValueError(f"tile index {tile_index} is out of range")
            for pixel_y in range(8):
                source_y = 7 - pixel_y if entry_value & (1 << 11) else pixel_y
                for pixel_x in range(8):
                    source_x = 7 - pixel_x if entry_value & (1 << 10) else pixel_x
                    packed = tile_data[tile_offset + source_y * 4 + source_x // 2]
                    color = (packed >> (4 if source_x & 1 else 0)) & 0xF
                    palette_index = 0 if color == 0 else ((entry_value >> 12) & 0xF) * 16 + color
                    pixels[(tile_y * 8 + pixel_y) * 288 + tile_x * 8 + pixel_x] = palette_index

    return {
        "width": 288,
        "height": 352,
        "pixels": bytes(pixels),
        "palette": palette,
        "tilemap": tilemap,
        "source_sha256": {
            "tile_gfx": hashlib.sha256(tile_data).hexdigest(),
            "bg_palette": hashlib.sha256(palette_data).hexdigest(),
            "primary_layout": hashlib.sha256(layout).hexdigest(),
            "metatile_attributes": hashlib.sha256(metatiles).hexdigest(),
        },
    }


def reconstruct_reference_bg(boundary: Path, background: int) -> dict[str, object]:
    """Rebuild one 4bpp text background directly from a reference GPU dump."""

    boundary = Path(boundary)
    io = (boundary / "io.bin").read_bytes()
    pram = (boundary / "pram.bin").read_bytes()
    vram = (boundary / "vram.bin").read_bytes()
    if (len(io), len(pram), len(vram)) != (0x400, 0x400, 0x18000):
        raise ValueError("reference GPU regions have unexpected sizes")
    control = struct.unpack_from("<H", io, 0x08 + background * 2)[0]
    if control & (1 << 7):
        raise ValueError("reference BG exporter currently requires 4bpp text backgrounds")
    size = (control >> 14) & 3
    width, height = ((256, 256), (512, 256), (256, 512), (512, 512))[size]
    character_base = ((control >> 2) & 3) * 0x4000
    screen_base = ((control >> 8) & 0x1F) * 0x800
    pixels = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            block_x = (x // 8) // 32
            block_y = (y // 8) // 32
            if size == 0:
                block = 0
            elif size == 1:
                block = block_x
            elif size == 2:
                block = block_y
            else:
                block = block_x + block_y * 2
            map_index = ((y // 8) % 32) * 32 + ((x // 8) % 32)
            entry = struct.unpack_from(
                "<H", vram, screen_base + block * 0x800 + map_index * 2
            )[0]
            local_x = x & 7
            local_y = y & 7
            if entry & (1 << 10):
                local_x = 7 - local_x
            if entry & (1 << 11):
                local_y = 7 - local_y
            tile_offset = character_base + (entry & 0x3FF) * 32
            packed = vram[tile_offset + local_y * 4 + local_x // 2]
            color = (packed >> (4 if local_x & 1 else 0)) & 0xF
            pixels[y * width + x] = (
                0 if color == 0 else ((entry >> 12) & 0xF) * 16 + color
            )
    return {
        "width": width,
        "height": height,
        "pixels": bytes(pixels),
        "palette": parse_palette(pram[:0x200]),
    }


def reconstruct_reference_sprite(
    boundary: Path,
    object_indices: tuple[int, ...],
    left: int,
    top: int,
    width: int,
    height: int,
) -> dict[str, object]:
    """Composite selected 4bpp, non-affine OAM entries into one sprite canvas."""

    boundary = Path(boundary)
    pram = (boundary / "pram.bin").read_bytes()
    oam = (boundary / "oam.bin").read_bytes()
    vram = (boundary / "vram.bin").read_bytes()
    pixels = bytearray(width * height)
    owners: list[tuple[int, int] | None] = [None] * (width * height)
    palette_bank: int | None = None
    dimensions = {
        0: ((8, 8), (16, 16), (32, 32), (64, 64)),
        1: ((16, 8), (32, 8), (32, 16), (64, 32)),
        2: ((8, 16), (8, 32), (16, 32), (32, 64)),
    }
    for object_index in object_indices:
        attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, object_index * 8)
        if attr0 & (1 << 8) or attr0 & (1 << 13):
            raise ValueError("reference sprite exporter requires non-affine 4bpp OBJ")
        bank = (attr2 >> 12) & 0xF
        if palette_bank is None:
            palette_bank = bank
        elif palette_bank != bank:
            raise ValueError("composited OAM entries must share one palette bank")
        shape = (attr0 >> 14) & 3
        if shape not in dimensions:
            raise ValueError("active OAM shape 3 is prohibited")
        object_width, object_height = dimensions[shape][(attr1 >> 14) & 3]
        origin_x = attr1 & 0x1FF
        origin_y = attr0 & 0xFF
        for local_y in range(object_height):
            target_y = origin_y + local_y - top
            if not 0 <= target_y < height:
                continue
            source_y = object_height - 1 - local_y if attr1 & (1 << 13) else local_y
            for local_x in range(object_width):
                target_x = origin_x + local_x - left
                if not 0 <= target_x < width:
                    continue
                source_x = object_width - 1 - local_x if attr1 & (1 << 12) else local_x
                tile_unit = (
                    (attr2 & 0x3FF)
                    + (source_y // 8) * (object_width // 8)
                    + source_x // 8
                )
                packed = vram[
                    0x10000
                    + tile_unit * 32
                    + (source_y & 7) * 4
                    + (source_x & 7) // 2
                ]
                color = (packed >> (4 if source_x & 1 else 0)) & 0xF
                if color == 0:
                    continue
                pixel_index = target_y * width + target_x
                owner = ((attr2 >> 10) & 3, object_index)
                if owners[pixel_index] is None or owner < owners[pixel_index]:
                    owners[pixel_index] = owner
                    pixels[pixel_index] = color
    if palette_bank is None:
        raise ValueError("at least one OAM entry is required")
    palette_offset = 0x200 + palette_bank * 32
    return {
        "width": width,
        "height": height,
        "pixels": bytes(pixels),
        "palette": parse_palette(pram[palette_offset : palette_offset + 32]),
        "palette_bank": palette_bank,
    }


def reconstruct_screen_layers(
    boundary: Path,
    layer_specs: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...],
) -> tuple[list[tuple[int, int, int]], tuple[bytes, ...]]:
    """Flatten selected original BG/OBJ groups into screen-aligned transparent layers."""

    boundary = Path(boundary)
    io = (boundary / "io.bin").read_bytes()
    pram = (boundary / "pram.bin").read_bytes()
    oam = (boundary / "oam.bin").read_bytes()
    vram = (boundary / "vram.bin").read_bytes()
    dispcnt = struct.unpack_from("<H", io, 0)[0]
    backdrop = tuple(_rgb(struct.unpack_from("<H", pram, 0)[0]))
    colors: list[tuple[int, int, int]] = [backdrop]
    color_indices: dict[tuple[int, int, int], int] = {}
    raw_layers: list[list[tuple[int, int, int] | None]] = []
    for backgrounds, objects in layer_specs:
        raw: list[tuple[int, int, int] | None] = []
        for y in range(160):
            for x in range(240):
                candidates = []
                for background in backgrounds:
                    pixel = _background_pixel(io, pram, vram, background, x, y)
                    if pixel is not None:
                        candidates.append(pixel)
                for object_index in objects:
                    pixel = _object_pixel(dispcnt, pram, oam, vram, object_index, x, y)
                    if pixel is not None:
                        candidates.append(pixel)
                if not candidates:
                    raw.append(None)
                    continue
                candidates.sort(key=lambda pixel: (pixel.priority, pixel.order))
                color = tuple(_rgb(candidates[0].color))
                raw.append(color)
                if color not in color_indices:
                    if len(colors) == 256:
                        raise ValueError("screen-aligned reference layers exceed 255 visible colors")
                    color_indices[color] = len(colors)
                    colors.append(color)
        raw_layers.append(raw)
    layers = []
    for raw in raw_layers:
        pixels = bytearray(256 * 256)
        for y in range(160):
            for x in range(240):
                color = raw[y * 240 + x]
                if color is not None:
                    pixels[y * 256 + x] = color_indices[color]
        layers.append(bytes(pixels))
    return colors, tuple(layers)


def reconstruct_priority_layers(
    boundary: Path,
) -> tuple[list[tuple[int, int, int]], tuple[bytes, ...]]:
    """Rebuild one frame as bottom, middle and top original-priority layers."""

    boundary = Path(boundary)
    io = (boundary / "io.bin").read_bytes()
    oam = (boundary / "oam.bin").read_bytes()
    decoded = decode_gpu(io, oam)
    background_priorities = {
        int(index): data["priority"] for index, data in decoded["backgrounds"].items()
    }
    object_priorities = {
        data["index"]: data["priority"] for data in decoded["objects"]
    }
    specs = []
    for accepted in ((2, 3), (1,), (0,)):
        backgrounds = tuple(
            index for index, priority in background_priorities.items() if priority in accepted
        )
        objects = tuple(
            index for index, priority in object_priorities.items() if priority in accepted
        )
        specs.append((backgrounds, objects))
    return reconstruct_screen_layers(boundary, tuple(specs))


def reconstruct_flattened_screen(
    boundary: Path,
) -> tuple[list[tuple[int, int, int]], bytes]:
    """Encode the final blended 240x160 reference frame as one opaque BG."""

    rgb = render_boundary(Path(boundary))
    palette: list[tuple[int, int, int]] = [(0, 0, 0)]
    indices: dict[tuple[int, int, int], int] = {}
    pixels = bytearray(256 * 256)
    for y in range(160):
        for x in range(240):
            offset = (y * 240 + x) * 3
            color = tuple(rgb[offset : offset + 3])
            index = indices.get(color)
            if index is None:
                if len(palette) == 256:
                    raise ValueError("flattened reference frame exceeds 255 visible colors")
                index = len(palette)
                indices[color] = index
                palette.append(color)
            pixels[y * 256 + x] = index
    return palette, bytes(pixels)


def reconstruct_blended_combat_layers(
    boundary: Path,
) -> tuple[list[tuple[int, int, int]], tuple[bytes, ...]]:
    """Separate BG2 alpha overlays from the map and opaque HUD/OBJ layers."""

    boundary = Path(boundary)
    decoded = decode_gpu(
        (boundary / "io.bin").read_bytes(), (boundary / "oam.bin").read_bytes()
    )
    front_objects = tuple(
        item["index"] for item in decoded["objects"]
    )
    return reconstruct_screen_layers(
        boundary,
        (
            ((0,), ()),
            ((2,), ()),
            ((3,), front_objects),
        ),
    )


def _write_4bpp_bmp(
    path: Path,
    width: int,
    height: int,
    pixels: list[int] | bytes,
    palette: tuple[tuple[int, int, int], ...] | list[tuple[int, int, int]] = PALETTE,
) -> None:
    if len(pixels) != width * height:
        raise ValueError("pixel count does not match BMP dimensions")
    if any(pixel < 0 or pixel > 15 for pixel in pixels):
        raise ValueError("4bpp pixels must be palette indices 0..15")

    packed_width = (width + 1) // 2
    row_size = (packed_width + 3) & ~3
    image_size = row_size * height
    if len(palette) != 16:
        raise ValueError("4bpp BMP palette must contain exactly 16 colors")
    pixel_offset = 14 + 40 + len(palette) * 4
    file_size = pixel_offset + image_size

    output = bytearray()
    output.extend(struct.pack("<2sIHHI", b"BM", file_size, 0, 0, pixel_offset))
    output.extend(
        struct.pack(
            "<IiiHHIIiiII",
            40,
            width,
            height,
            1,
            4,
            0,
            image_size,
            2835,
            2835,
            len(palette),
            len(palette),
        )
    )
    for red, green, blue in palette:
        output.extend(bytes((blue, green, red, 0)))

    for y in range(height - 1, -1, -1):
        row = bytearray()
        start = y * width
        for x in range(0, width, 2):
            high = pixels[start + x]
            low = pixels[start + x + 1] if x + 1 < width else 0
            row.append((high << 4) | low)
        row.extend(bytes(row_size - len(row)))
        output.extend(row)
    path.write_bytes(output)


def _write_8bpp_bmp(
    path: Path,
    width: int,
    height: int,
    pixels: bytes,
    palette: list[tuple[int, int, int]],
) -> None:
    if len(pixels) != width * height:
        raise ValueError("pixel count does not match BMP dimensions")
    if len(palette) > 256:
        raise ValueError("8bpp BMP palette cannot exceed 256 colors")
    row_size = (width + 3) & ~3
    image_size = row_size * height
    pixel_offset = 14 + 40 + 256 * 4
    output = bytearray()
    output.extend(struct.pack("<2sIHHI", b"BM", pixel_offset + image_size, 0, 0, pixel_offset))
    output.extend(
        struct.pack(
            "<IiiHHIIiiII",
            40,
            width,
            height,
            1,
            8,
            0,
            image_size,
            2835,
            2835,
            256,
            256,
        )
    )
    for index in range(256):
        red, green, blue = palette[index] if index < len(palette) else (0, 0, 0)
        output.extend(bytes((blue, green, red, 0)))
    for y in range(height - 1, -1, -1):
        row = pixels[y * width : (y + 1) * width]
        output.extend(row)
        output.extend(bytes(row_size - width))
    path.write_bytes(output)


def _set(pixels: list[int], width: int, height: int, x: int, y: int, color: int) -> None:
    if 0 <= x < width and 0 <= y < height:
        pixels[y * width + x] = color


def _fill_rect(
    pixels: list[int], width: int, height: int, x: int, y: int, w: int, h: int, color: int
) -> None:
    for py in range(y, y + h):
        for px in range(x, x + w):
            _set(pixels, width, height, px, py, color)


def _draw_map() -> list[int]:
    pixels = [1] * (MAP_WIDTH * MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if (x * 3 + y * 5) % 37 == 0:
                pixels[y * MAP_WIDTH + x] = 2

    obstacles = set(OBSTACLES)
    for grid_y in range(22):
        for grid_x in range(9):
            left = GRID_ORIGIN_X + grid_x * CELL_SIZE
            top = GRID_ORIGIN_Y + grid_y * CELL_SIZE
            base = 3 if (grid_x + grid_y) % 2 else 4
            _fill_rect(pixels, MAP_WIDTH, MAP_HEIGHT, left, top, CELL_SIZE, CELL_SIZE, base)
            for edge in range(CELL_SIZE):
                _set(pixels, MAP_WIDTH, MAP_HEIGHT, left + edge, top, 2)
                _set(pixels, MAP_WIDTH, MAP_HEIGHT, left, top + edge, 2)
            if (grid_x, grid_y) in obstacles:
                _fill_rect(pixels, MAP_WIDTH, MAP_HEIGHT, left + 6, top + 8, 4, 7, 6)
                _fill_rect(pixels, MAP_WIDTH, MAP_HEIGHT, left + 3, top + 3, 10, 8, 2)
                _fill_rect(pixels, MAP_WIDTH, MAP_HEIGHT, left + 5, top + 1, 6, 7, 3)
    return pixels


def _draw_naruto(pixels: list[int]) -> None:
    _fill_rect(pixels, 16, 48, 5, 2, 6, 3, 10)
    _set(pixels, 16, 48, 4, 3, 10)
    _set(pixels, 16, 48, 11, 3, 10)
    _fill_rect(pixels, 16, 48, 5, 5, 6, 4, 11)
    _fill_rect(pixels, 16, 48, 4, 5, 8, 2, 8)
    _fill_rect(pixels, 16, 48, 4, 9, 8, 5, 9)
    _fill_rect(pixels, 16, 48, 5, 14, 2, 2, 8)
    _fill_rect(pixels, 16, 48, 9, 14, 2, 2, 8)


def _draw_iruka(pixels: list[int]) -> None:
    offset = 16
    _fill_rect(pixels, 16, 48, 4, offset + 2, 8, 3, 7)
    _fill_rect(pixels, 16, 48, 5, offset + 5, 6, 4, 11)
    _fill_rect(pixels, 16, 48, 4, offset + 5, 8, 2, 12)
    _fill_rect(pixels, 16, 48, 4, offset + 9, 8, 5, 3)
    _fill_rect(pixels, 16, 48, 5, offset + 14, 2, 2, 7)
    _fill_rect(pixels, 16, 48, 9, offset + 14, 2, 2, 7)


def _draw_cursor(pixels: list[int]) -> None:
    offset = 32
    for index in range(6):
        _set(pixels, 16, 48, index, offset, 15)
        _set(pixels, 16, 48, 15 - index, offset, 15)
        _set(pixels, 16, 48, index, offset + 15, 15)
        _set(pixels, 16, 48, 15 - index, offset + 15, 15)
        _set(pixels, 16, 48, 0, offset + index, 15)
        _set(pixels, 16, 48, 15, offset + index, 15)
        _set(pixels, 16, 48, 0, offset + 15 - index, 15)
        _set(pixels, 16, 48, 15, offset + 15 - index, 15)


def _draw_units() -> list[int]:
    pixels = [0] * (16 * 48)
    _draw_naruto(pixels)
    _draw_iruka(pixels)
    _draw_cursor(pixels)
    return pixels


def generate_assets(
    output_dir: Path, rom_path: Path = REPO_ROOT / "rom/base.gba"
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "scenario_41_map.bmp": None,
        "scenario_41_map.json": {
            "type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256
        },
        "scenario_41_move_overlay.bmp": None,
        "scenario_41_move_overlay.json": {
            "type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256
        },
        "scenario_41_naruto.bmp": None,
        "scenario_41_naruto.json": {"type": "sprite", "height": 64},
        "scenario_41_cursor.bmp": None,
        "scenario_41_cursor.json": {"type": "sprite", "height": 64},
        "scenario_41_cursor_shadow.bmp": None,
        "scenario_41_cursor_shadow.json": {"type": "sprite", "height": 64},
        "scenario_41_select_label.bmp": None,
        "scenario_41_select_label.json": {"type": "sprite", "height": 32},
        "scenario_41_facing_ui.bmp": None,
        "scenario_41_facing_ui.json": {
            "type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256
        },
        "scenario_41_facing_naruto.bmp": None,
        "scenario_41_facing_naruto.json": {"type": "sprite", "height": 64},
        "scenario_41_facing_cursor.bmp": None,
        "scenario_41_facing_cursor.json": {"type": "sprite", "height": 64},
        "scenario_41_facing_cursor_shadow.bmp": None,
        "scenario_41_facing_cursor_shadow.json": {"type": "sprite", "height": 64},
        "scenario_41_technique_ui.bmp": None,
        "scenario_41_technique_ui.json": {
            "type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256
        },
        "scenario_41_technique_naruto.bmp": None,
        "scenario_41_technique_naruto.json": {"type": "sprite", "height": 64},
        "scenario_41_technique_cursor.bmp": None,
        "scenario_41_technique_cursor.json": {"type": "sprite", "height": 64},
        "scenario_41_technique_cursor_shadow.bmp": None,
        "scenario_41_technique_cursor_shadow.json": {"type": "sprite", "height": 64},
        "scenario_41_technique_left_marker.bmp": None,
        "scenario_41_technique_left_marker.json": {"type": "sprite", "height": 16},
        "scenario_41_technique_bottom_controls.bmp": None,
        "scenario_41_technique_bottom_controls.json": {"type": "sprite", "height": 32},
        "scenario_41_technique_icons.bmp": None,
        "scenario_41_technique_icons.json": {"type": "sprite", "height": 16},
        "scenario_41_player_hud.bmp": None,
        "scenario_41_player_hud.json": {
            "type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256
        },
        "scenario_41_units.bmp": None,
        "scenario_41_units.json": {"type": "sprite", "height": 16},
    }
    for name in (
        "tutorial_bg", "tutorial_portraits", "tutorial_ui",
        "victory_bg", "victory_actor", "victory_title",
        "postbattle_bg", "postbattle_ui",
    ):
        files[f"scenario_41_{name}.bmp"] = None
        files[f"scenario_41_{name}.json"] = {
            "type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256
        }
    extended_prefixes = (
        "result", "level_up_1", "level_up_2",
        *(f"postbattle_dialogue_{index}" for index in range(1, 12)),
    )
    combat_prefixes = (
        "action_menu_0", "action_menu_1", "end_confirmation",
        "defense_confirmation", "target_select", "attack_confirmation",
        "combat_dialogue", "combat_popup",
    )
    for prefix in (*extended_prefixes, *combat_prefixes):
        for layer in ("bottom", "middle", "top"):
            files[f"scenario_41_{prefix}_{layer}.bmp"] = None
            files[f"scenario_41_{prefix}_{layer}.json"] = {
                "type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256
            }
    reconstructed = reconstruct_map(rom_path)
    player_hud = reconstruct_reference_bg(
        REPO_ROOT / "artifacts/scenario-41-reference-v1/player-turn", 3
    )
    padded = bytearray(512 * 512)
    source_pixels = reconstructed["pixels"]
    for y in range(reconstructed["height"]):
        source_start = y * reconstructed["width"]
        padded_start = y * 512
        padded[padded_start : padded_start + reconstructed["width"]] = source_pixels[
            source_start : source_start + reconstructed["width"]
        ]
    _write_8bpp_bmp(
        output_dir / "scenario_41_map.bmp",
        512,
        512,
        bytes(padded),
        player_hud["palette"],
    )
    player_boundary = REPO_ROOT / "artifacts/scenario-41-reference-v1/player-turn"
    move_overlay = reconstruct_reference_bg(player_boundary, 2)
    _write_8bpp_bmp(
        output_dir / "scenario_41_move_overlay.bmp",
        move_overlay["width"],
        move_overlay["height"],
        move_overlay["pixels"],
        player_hud["palette"],
    )
    naruto = reconstruct_reference_sprite(player_boundary, (11,), 104, 24, 32, 64)
    _write_4bpp_bmp(
        output_dir / "scenario_41_naruto.bmp",
        naruto["width"],
        naruto["height"],
        naruto["pixels"],
        naruto["palette"],
    )
    cursor_indices = tuple(range(3, 11))
    cursor = reconstruct_reference_sprite(
        player_boundary, cursor_indices, 88, 24, 64, 64
    )
    _write_4bpp_bmp(
        output_dir / "scenario_41_cursor.bmp",
        cursor["width"],
        cursor["height"],
        cursor["pixels"],
        cursor["palette"],
    )
    cursor_shadow = reconstruct_reference_sprite(
        player_boundary, tuple(range(12, 16)), 88, 25, 64, 64
    )
    _write_4bpp_bmp(
        output_dir / "scenario_41_cursor_shadow.bmp",
        cursor_shadow["width"],
        cursor_shadow["height"],
        cursor_shadow["pixels"],
        cursor_shadow["palette"],
    )
    select_label = reconstruct_reference_sprite(
        player_boundary, (0, 1, 2), 184, 0, 64, 32
    )
    _write_4bpp_bmp(
        output_dir / "scenario_41_select_label.bmp",
        select_label["width"],
        select_label["height"],
        select_label["pixels"],
        select_label["palette"],
    )
    facing_boundary = REPO_ROOT / "artifacts/scenario-41-reference-v1/first-movedone-facing"
    facing_ui = reconstruct_reference_bg(facing_boundary, 3)
    _write_8bpp_bmp(
        output_dir / "scenario_41_facing_ui.bmp", 256, 256,
        facing_ui["pixels"], player_hud["palette"]
    )
    facing_sprites = {
        "facing_naruto": ((8,), 104, 24, 32, 64),
        "facing_cursor": (tuple(range(0, 8)), 88, 24, 64, 64),
        "facing_cursor_shadow": (tuple(range(9, 13)), 88, 25, 64, 64),
    }
    for name, arguments in facing_sprites.items():
        sprite = reconstruct_reference_sprite(facing_boundary, *arguments)
        _write_4bpp_bmp(
            output_dir / f"scenario_41_{name}.bmp",
            sprite["width"], sprite["height"], sprite["pixels"], sprite["palette"]
        )

    technique_boundary = REPO_ROOT / "artifacts/scenario-41-reference-v1/first-turn-technique-menu"
    technique_ui = reconstruct_reference_bg(technique_boundary, 3)
    _write_8bpp_bmp(
        output_dir / "scenario_41_technique_ui.bmp", 256, 256,
        technique_ui["pixels"], player_hud["palette"]
    )
    technique_sprites = {
        "technique_naruto": ((14,), 104, 24, 32, 64),
        "technique_cursor": (tuple(range(6, 14)), 88, 24, 64, 64),
        "technique_cursor_shadow": (tuple(range(15, 19)), 88, 27, 64, 64),
        "technique_left_marker": ((0,), 0, 40, 8, 16),
        "technique_bottom_controls": ((1, 2, 3), 152, 120, 64, 32),
        "technique_icons": ((4, 5), 80, 40, 32, 16),
    }
    for name, arguments in technique_sprites.items():
        sprite = reconstruct_reference_sprite(technique_boundary, *arguments)
        _write_4bpp_bmp(
            output_dir / f"scenario_41_{name}.bmp",
            sprite["width"], sprite["height"], sprite["pixels"], sprite["palette"]
        )

    layered_boundaries = {
        "tutorial": (
            REPO_ROOT / "artifacts/scenario-41-reference-v1/turn-1-complete",
            (
                ((0,), ()),
                ((), tuple(range(1, 13))),
                ((3,), (0,)),
            ),
            ("tutorial_bg", "tutorial_portraits", "tutorial_ui"),
        ),
        "victory": (
            REPO_ROOT / "artifacts/scenario-41-reference-v1/victory",
            (
                ((0,), ()),
                ((), tuple(range(2, 7))),
                ((3,), (0, 1)),
            ),
            ("victory_bg", "victory_actor", "victory_title"),
        ),
        "postbattle": (
            REPO_ROOT / "artifacts/scenario-41-reference-v1/postbattle",
            (
                ((0,), ()),
                ((3,), (0,)),
            ),
            ("postbattle_bg", "postbattle_ui"),
        ),
    }
    for _, (boundary, specs, names) in layered_boundaries.items():
        palette, layers = reconstruct_screen_layers(boundary, specs)
        for name, pixels in zip(names, layers, strict=True):
            _write_8bpp_bmp(
                output_dir / f"scenario_41_{name}.bmp", 256, 256, pixels, palette
            )
    extended_root = REPO_ROOT / "artifacts/scenario-41-extended-reference-v1"
    for prefix in extended_prefixes:
        boundary = extended_root / prefix.replace("_", "-")
        palette, layers = reconstruct_priority_layers(boundary)
        for layer, pixels in zip(("bottom", "middle", "top"), layers, strict=True):
            _write_8bpp_bmp(
                output_dir / f"scenario_41_{prefix}_{layer}.bmp",
                256,
                256,
                pixels,
                palette,
            )
    combat_root = REPO_ROOT / "artifacts/scenario-41-combat-reference-v1"
    for prefix in combat_prefixes:
        boundary = combat_root / prefix.replace("_", "-")
        if prefix in ("target_select", "attack_confirmation"):
            palette, layers = reconstruct_blended_combat_layers(boundary)
        else:
            palette, flattened = reconstruct_flattened_screen(boundary)
            layers = (flattened, bytes(256 * 256), bytes(256 * 256))
        for layer, pixels in zip(("bottom", "middle", "top"), layers, strict=True):
            _write_8bpp_bmp(
                output_dir / f"scenario_41_{prefix}_{layer}.bmp",
                256,
                256,
                pixels,
                palette,
            )
    _write_8bpp_bmp(
        output_dir / "scenario_41_player_hud.bmp",
        player_hud["width"],
        player_hud["height"],
        player_hud["pixels"],
        player_hud["palette"],
    )
    _write_4bpp_bmp(output_dir / "scenario_41_units.bmp", 16, 48, _draw_units())
    for name, content in files.items():
        if content is not None:
            (output_dir / name).write_text(
                json.dumps(content, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
    return {
        name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
        for name in files
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rom", type=Path, default=REPO_ROOT / "rom/base.gba")
    args = parser.parse_args()
    for name, digest in generate_assets(args.output_dir, args.rom).items():
        print(f"{digest}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
