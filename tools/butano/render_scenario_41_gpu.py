#!/usr/bin/env python3
"""Offline Mode 0 renderer for hash-bound scenario 41 GPU snapshots."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from tools.butano.analyze_scenario_41_gpu import decode_gpu


WIDTH = 240
HEIGHT = 160
_OBJ_DIMENSIONS = {
    0: ((8, 8), (16, 16), (32, 32), (64, 64)),
    1: ((16, 8), (32, 8), (32, 16), (64, 32)),
    2: ((8, 16), (8, 32), (16, 32), (32, 64)),
}


@dataclass(frozen=True)
class Pixel:
    color: int
    priority: int
    target_bit: int
    order: int
    semitransparent: bool = False


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _rgb(color: int) -> bytes:
    red = color & 0x1F
    green = (color >> 5) & 0x1F
    blue = (color >> 10) & 0x1F
    return bytes(
        (
            (red << 3) | (red >> 2),
            (green << 3) | (green >> 2),
            (blue << 3) | (blue >> 2),
        )
    )


def _bg_map_offset(screen_base: int, size: int, tile_x: int, tile_y: int) -> int:
    block_x = tile_x // 32
    block_y = tile_y // 32
    if size == 0:
        block = 0
    elif size == 1:
        block = block_x
    elif size == 2:
        block = block_y
    else:
        block = block_x + block_y * 2
    index = (tile_y % 32) * 32 + (tile_x % 32)
    return screen_base + block * 0x800 + index * 2


def _background_pixel(
    io: bytes, pram: bytes, vram: bytes, index: int, screen_x: int, screen_y: int
) -> Pixel | None:
    control = _u16(io, 0x08 + index * 2)
    size = (control >> 14) & 3
    dimensions = ((256, 256), (512, 256), (256, 512), (512, 512))[size]
    x = (screen_x + (_u16(io, 0x10 + index * 4) & 0x1FF)) % dimensions[0]
    y = (screen_y + (_u16(io, 0x12 + index * 4) & 0x1FF)) % dimensions[1]
    map_offset = _bg_map_offset(((control >> 8) & 0x1F) * 0x800, size, x // 8, y // 8)
    entry = _u16(vram, map_offset)
    local_x = x & 7
    local_y = y & 7
    if entry & (1 << 10):
        local_x = 7 - local_x
    if entry & (1 << 11):
        local_y = 7 - local_y
    tile = entry & 0x3FF
    character_base = ((control >> 2) & 3) * 0x4000
    if control & (1 << 7):
        tile_offset = character_base + tile * 64 + local_y * 8 + local_x
        palette_index = vram[tile_offset]
        if palette_index == 0:
            return None
    else:
        tile_offset = character_base + tile * 32 + local_y * 4 + local_x // 2
        packed = vram[tile_offset]
        palette_index = (packed >> (4 if local_x & 1 else 0)) & 0xF
        if palette_index == 0:
            return None
        palette_index += ((entry >> 12) & 0xF) * 16
    return Pixel(
        _u16(pram, palette_index * 2),
        control & 3,
        1 << index,
        128 + index,
    )


def _object_pixel(
    dispcnt: int,
    pram: bytes,
    oam: bytes,
    vram: bytes,
    index: int,
    screen_x: int,
    screen_y: int,
) -> Pixel | None:
    offset = index * 8
    attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, offset)
    affine = bool(attr0 & (1 << 8))
    if not affine and attr0 & (1 << 9):
        return None
    if affine:
        raise ValueError(f"affine OAM entry {index} is not supported by the reference renderer")
    shape = (attr0 >> 14) & 3
    if shape == 3:
        raise ValueError(f"active OAM entry {index} uses prohibited shape 3")
    width, height = _OBJ_DIMENSIONS[shape][(attr1 >> 14) & 3]
    origin_x = attr1 & 0x1FF
    origin_y = attr0 & 0xFF
    relative_x = (screen_x - origin_x) & 0x1FF
    relative_y = (screen_y - origin_y) & 0xFF
    if relative_x >= width or relative_y >= height:
        return None
    if attr1 & (1 << 12):
        relative_x = width - 1 - relative_x
    if attr1 & (1 << 13):
        relative_y = height - 1 - relative_y
    color_256 = bool(attr0 & (1 << 13))
    tile_units = 2 if color_256 else 1
    tile_x = relative_x // 8
    tile_y = relative_y // 8
    if dispcnt & (1 << 6):
        stride = (width // 8) * tile_units
    else:
        stride = 32
    tile_unit = (attr2 & 0x3FF) + tile_y * stride + tile_x * tile_units
    tile_offset = 0x10000 + tile_unit * 32
    local_x = relative_x & 7
    local_y = relative_y & 7
    if color_256:
        palette_index = vram[tile_offset + local_y * 8 + local_x]
        if palette_index == 0:
            return None
    else:
        packed = vram[tile_offset + local_y * 4 + local_x // 2]
        palette_index = (packed >> (4 if local_x & 1 else 0)) & 0xF
        if palette_index == 0:
            return None
        palette_index += ((attr2 >> 12) & 0xF) * 16
    return Pixel(
        _u16(pram, 0x200 + palette_index * 2),
        (attr2 >> 10) & 3,
        1 << 4,
        index,
        ((attr0 >> 10) & 3) == 1,
    )


def _blend_rgb8(first: int, second: int, eva: int, evb: int) -> bytes:
    first_rgb = _rgb(first)
    second_rgb = _rgb(second)
    return bytes(
        min(255, (first_rgb[index] * eva + second_rgb[index] * evb) // 16)
        for index in range(3)
    )


def render_mode0(io: bytes, pram: bytes, oam: bytes, vram: bytes) -> bytes:
    """Render a static Mode 0 register snapshot to normalized RGB8 pixels."""

    expected = (0x400, 0x400, 0x400, 0x18000)
    actual = tuple(map(len, (io, pram, oam, vram)))
    if actual != expected:
        raise ValueError(f"GPU region sizes {actual} do not match {expected}")
    decoded = decode_gpu(io, oam)
    if decoded["display"]["mode"] != 0:
        raise ValueError("reference renderer currently requires display mode 0")
    dispcnt = _u16(io, 0)
    if dispcnt & (1 << 7):
        return bytes((255, 255, 255)) * WIDTH * HEIGHT
    enabled_backgrounds = decoded["display"]["enabled_backgrounds"]
    obj_enabled = decoded["display"]["obj_enabled"]
    blend_control = _u16(io, 0x50)
    effect = (blend_control >> 6) & 3
    first_targets = blend_control & 0x3F
    second_targets = (blend_control >> 8) & 0x3F
    alpha = _u16(io, 0x52)
    eva = min(16, alpha & 0x1F)
    evb = min(16, (alpha >> 8) & 0x1F)
    output = bytearray()
    backdrop = Pixel(_u16(pram, 0), 4, 1 << 5, 255)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            pixels = [backdrop]
            for background in enabled_backgrounds:
                pixel = _background_pixel(io, pram, vram, background, x, y)
                if pixel is not None:
                    pixels.append(pixel)
            if obj_enabled:
                for index in range(128):
                    pixel = _object_pixel(dispcnt, pram, oam, vram, index, x, y)
                    if pixel is not None:
                        pixels.append(pixel)
            pixels.sort(key=lambda pixel: (pixel.priority, pixel.order))
            top = pixels[0]
            output_rgb = _rgb(top.color)
            alpha_enabled = top.semitransparent or (effect == 1 and top.target_bit & first_targets)
            if alpha_enabled:
                behind = next(
                    (pixel for pixel in pixels[1:] if pixel.target_bit & second_targets),
                    None,
                )
                if behind is not None:
                    output_rgb = _blend_rgb8(top.color, behind.color, eva, evb)
            output.extend(output_rgb)
    return bytes(output)


def render_boundary(path: Path) -> bytes:
    path = Path(path)
    return render_mode0(
        (path / "io.bin").read_bytes(),
        (path / "pram.bin").read_bytes(),
        (path / "oam.bin").read_bytes(),
        (path / "vram.bin").read_bytes(),
    )
