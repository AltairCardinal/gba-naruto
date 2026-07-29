#!/usr/bin/env python3
"""Render tracked mGBA Mode 0 checkpoints with indexed OBJ coverage."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import struct

from PIL import Image

try:
    from tools.export_runtime_bg_composites import _layer_pixels
    from tools.inspect_mgba_savestate import load_gba_state
except ModuleNotFoundError:
    from export_runtime_bg_composites import _layer_pixels
    from inspect_mgba_savestate import load_gba_state


WIDTH = 240
HEIGHT = 160
OBJ_DIMENSIONS = {
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


def _clamp_coefficient(value: int) -> int:
    return min(16, value & 0x1F)


def _channels(color: int) -> tuple[int, int, int]:
    return color & 0x1F, (color >> 5) & 0x1F, (color >> 10) & 0x1F


def _bgr555(red: int, green: int, blue: int) -> int:
    return red | green << 5 | blue << 10


def blend_alpha_bgr555(first: int, second: int, eva: int, evb: int) -> int:
    eva = _clamp_coefficient(eva)
    evb = _clamp_coefficient(evb)
    first_channels = _channels(first)
    second_channels = _channels(second)
    values = [
        min(31, (first_channels[index] * eva + second_channels[index] * evb) >> 4)
        for index in range(3)
    ]
    return _bgr555(*values)


def brighten_bgr555(color: int, evy: int) -> int:
    evy = _clamp_coefficient(evy)
    values = [
        value + ((31 - value) * evy >> 4) for value in _channels(color)
    ]
    return _bgr555(*values)


def darken_bgr555(color: int, evy: int) -> int:
    evy = _clamp_coefficient(evy)
    values = [value - (value * evy >> 4) for value in _channels(color)]
    return _bgr555(*values)


def _rgb8(color: int) -> bytes:
    return bytes((value << 3 | value >> 2) for value in _channels(color))


def _blend_alpha_rgb8(first: int, second: int, eva: int, evb: int) -> bytes:
    eva = _clamp_coefficient(eva)
    evb = _clamp_coefficient(evb)
    first_rgb = _rgb8(first)
    second_rgb = _rgb8(second)
    return bytes(
        min(255, (first_rgb[index] * eva + second_rgb[index] * evb) >> 4)
        for index in range(3)
    )


def _brighten_rgb8(color: int, evy: int) -> bytes:
    evy = _clamp_coefficient(evy)
    return bytes(
        value + ((255 - value) * evy >> 4) for value in _rgb8(color)
    )


def _darken_rgb8(color: int, evy: int) -> bytes:
    evy = _clamp_coefficient(evy)
    red, green, blue = _rgb8(color)
    # mGBA's 32-bit software renderer applies the operation to packed
    # mColor masks. The unshifted red channel therefore subtracts a floored
    # product, while shifted green/blue channels reduce to complement
    # multiplication before the mask is restored.
    return bytes(
        (
            red - (red * evy >> 4),
            green * (16 - evy) >> 4,
            blue * (16 - evy) >> 4,
        )
    )


def in_window_range(value: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= value < end
    return value >= start or value < end


def _window_contains(
    x: int, y: int, horizontal: int, vertical: int
) -> bool:
    return in_window_range(x, horizontal >> 8, horizontal & 0xFF) and (
        in_window_range(y, vertical >> 8, vertical & 0xFF)
    )


def _active_objects(oam: bytes) -> list[tuple[int, int, int, int]]:
    objects = []
    for index in range(128):
        attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, index * 8)
        affine = bool(attr0 & (1 << 8))
        if not affine and attr0 & (1 << 9):
            continue
        shape = (attr0 >> 14) & 3
        if shape == 3:
            raise ValueError(f"active OAM entry {index} uses prohibited shape 3")
        objects.append((index, attr0, attr1, attr2))
    return objects


def _object_coverage(
    dispcnt: int,
    pram: bytes,
    oam: bytes,
    vram: bytes,
) -> tuple[list[list[Pixel]], list[bool], dict[str, int]]:
    candidates: list[list[Pixel]] = [[] for _ in range(WIDTH * HEIGHT)]
    obj_window = [False] * (WIDTH * HEIGHT)
    stats = Counter()
    for index, attr0, attr1, attr2 in _active_objects(oam):
        stats["active"] += 1
        affine = bool(attr0 & (1 << 8))
        double_size = affine and bool(attr0 & (1 << 9))
        matrix: tuple[int, int, int, int] | None = None
        if affine:
            stats["affine"] += 1
            matrix_index = (attr1 >> 9) & 0x1F
            matrix = tuple(
                struct.unpack_from(
                    "<h",
                    oam,
                    (matrix_index * 4 + component) * 8 + 6,
                )[0]
                for component in range(4)
            )
        shape = (attr0 >> 14) & 3
        width, height = OBJ_DIMENSIONS[shape][(attr1 >> 14) & 3]
        output_width = width << int(double_size)
        output_height = height << int(double_size)
        origin_x = attr1 & 0x1FF
        origin_y = attr0 & 0xFF
        if origin_x >= 256:
            origin_x -= 512
        if origin_y >= 160:
            origin_y -= 256
        horizontal_flip = not affine and bool(attr1 & (1 << 12))
        vertical_flip = not affine and bool(attr1 & (1 << 13))
        color_256 = bool(attr0 & (1 << 13))
        object_mode = (attr0 >> 10) & 3
        if object_mode == 1:
            stats["semitransparent"] += 1
        elif object_mode == 2:
            stats["obj_window"] += 1
        elif object_mode == 3:
            raise ValueError(f"active OAM entry {index} uses prohibited mode 3")
        tile_units = 2 if color_256 else 1
        for local_y in range(output_height):
            screen_y = origin_y + local_y
            if not 0 <= screen_y < HEIGHT:
                continue
            for local_x in range(output_width):
                screen_x = origin_x + local_x
                if not 0 <= screen_x < WIDTH:
                    continue
                if affine:
                    assert matrix is not None
                    pa, pb, pc, pd = matrix
                    relative_x = local_x - output_width // 2
                    relative_y = local_y - output_height // 2
                    source_x = (
                        pa * relative_x
                        + pb * relative_y
                        + (width << 7)
                    ) >> 8
                    source_y = (
                        pc * relative_x
                        + pd * relative_y
                        + (height << 7)
                    ) >> 8
                    if not (
                        0 <= source_x < width
                        and 0 <= source_y < height
                    ):
                        continue
                else:
                    source_x = (
                        width - 1 - local_x
                        if horizontal_flip
                        else local_x
                    )
                    source_y = (
                        height - 1 - local_y
                        if vertical_flip
                        else local_y
                    )
                tile_x, pixel_x = divmod(source_x, 8)
                tile_y, pixel_y = divmod(source_y, 8)
                if dispcnt & (1 << 6):
                    stride = width // 8 * tile_units
                else:
                    stride = 32
                base_tile_unit = attr2 & 0x3FF
                if color_256:
                    base_tile_unit &= ~1
                tile_unit = (
                    base_tile_unit
                    + tile_y * stride
                    + tile_x * tile_units
                )
                tile_offset = 0x10000 + tile_unit * 32
                if color_256:
                    pixel_offset = tile_offset + pixel_y * 8 + pixel_x
                    if pixel_offset >= len(vram):
                        raise ValueError(f"OAM {index} 8bpp tile exceeds OBJ VRAM")
                    palette_index = vram[pixel_offset]
                else:
                    pixel_offset = tile_offset + pixel_y * 4 + pixel_x // 2
                    if pixel_offset >= len(vram):
                        raise ValueError(f"OAM {index} 4bpp tile exceeds OBJ VRAM")
                    packed = vram[pixel_offset]
                    palette_index = (
                        packed >> (4 if pixel_x & 1 else 0)
                    ) & 0xF
                    if palette_index:
                        palette_index += ((attr2 >> 12) & 0xF) * 16
                if palette_index == 0:
                    continue
                position = screen_y * WIDTH + screen_x
                if object_mode == 2:
                    obj_window[position] = True
                    continue
                color = _u16(pram, 0x200 + palette_index * 2)
                candidates[position].append(
                    Pixel(
                        color=color,
                        priority=(attr2 >> 10) & 3,
                        target_bit=1 << 4,
                        order=index,
                        semitransparent=object_mode == 1,
                    )
                )
    return candidates, obj_window, dict(stats)


def _window_control(
    io: bytes,
    dispcnt: int,
    x: int,
    y: int,
    obj_window_pixel: bool,
) -> int:
    windows_enabled = dispcnt & 0xE000
    if not windows_enabled:
        return 0x3F
    if dispcnt & 0x2000 and _window_contains(
        x, y, _u16(io, 0x40), _u16(io, 0x44)
    ):
        return _u16(io, 0x48) & 0x3F
    if dispcnt & 0x4000 and _window_contains(
        x, y, _u16(io, 0x42), _u16(io, 0x46)
    ):
        return (_u16(io, 0x48) >> 8) & 0x3F
    outside = _u16(io, 0x4A)
    if dispcnt & 0x8000 and obj_window_pixel:
        return (outside >> 8) & 0x3F
    return outside & 0x3F


def render_mode0(
    io: bytes,
    pram: bytes,
    oam: bytes,
    vram: bytes,
) -> tuple[bytes, dict[str, int]]:
    expected = (0x400, 0x400, 0x400, 0x18000)
    if tuple(map(len, (io, pram, oam, vram))) != expected:
        raise ValueError("invalid GPU memory region sizes")
    dispcnt = _u16(io, 0)
    if dispcnt & 7:
        raise ValueError("renderer requires display mode 0")
    if _u16(io, 0x4C):
        raise ValueError("renderer does not support nonzero mosaic")
    if dispcnt & (1 << 7):
        return bytes((255, 255, 255)) * WIDTH * HEIGHT, {}
    enabled_backgrounds = [
        index for index in range(4) if dispcnt & (1 << (8 + index))
    ]
    bg_colors: dict[int, list[int | None]] = {}
    for index in enabled_backgrounds:
        _, bg_colors[index] = _layer_pixels(
            io, pram[:0x200], vram[:0x10000], index
        )
    if dispcnt & (1 << 12):
        obj_pixels, obj_window, obj_stats = _object_coverage(
            dispcnt, pram, oam, vram
        )
    else:
        obj_pixels = [[] for _ in range(WIDTH * HEIGHT)]
        obj_window = [False] * (WIDTH * HEIGHT)
        obj_stats = {"active": len(_active_objects(oam))}
    blend_control = _u16(io, 0x50)
    effect = (blend_control >> 6) & 3
    first_targets = blend_control & 0x3F
    second_targets = (blend_control >> 8) & 0x3F
    alpha = _u16(io, 0x52)
    eva, evb = alpha & 0x1F, (alpha >> 8) & 0x1F
    evy = _u16(io, 0x54) & 0x1F
    backdrop = Pixel(_u16(pram, 0), 4, 1 << 5, 255)
    output = bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            position = y * WIDTH + x
            control = _window_control(
                io, dispcnt, x, y, obj_window[position]
            )
            pixels = [backdrop]
            for index in enabled_backgrounds:
                color = bg_colors[index][position]
                if color is not None and control & (1 << index):
                    pixels.append(
                        Pixel(
                            color=color,
                            priority=_u16(io, 0x08 + index * 2) & 3,
                            target_bit=1 << index,
                            order=128 + index,
                        )
                    )
            if control & (1 << 4):
                pixels.extend(obj_pixels[position])
            pixels.sort(key=lambda pixel: (pixel.priority, pixel.order))
            top = pixels[0]
            output_rgb = _rgb8(top.color)
            effects_enabled = bool(control & (1 << 5))
            force_alpha = top.semitransparent and effects_enabled
            if effects_enabled and (
                force_alpha or (effect == 1 and top.target_bit & first_targets)
            ):
                behind = next(
                    (
                        pixel
                        for pixel in pixels[1:]
                        if pixel.target_bit & second_targets
                    ),
                    None,
                )
                if behind is not None:
                    output_rgb = _blend_alpha_rgb8(
                        top.color, behind.color, eva, evb
                    )
            elif (
                effects_enabled
                and effect == 2
                and top.target_bit & first_targets
            ):
                output_rgb = _brighten_rgb8(top.color, evy)
            elif (
                effects_enabled
                and effect == 3
                and top.target_bit & first_targets
            ):
                output_rgb = _darken_rgb8(top.color, evy)
            output.extend(output_rgb)
    return bytes(output), obj_stats


def render_checkpoint(path: Path) -> tuple[bytes, dict[str, int]]:
    state = load_gba_state(path)
    return render_mode0(
        state.read_memory(0x04000000, 0x400),
        state.read_memory(0x05000000, 0x400),
        state.read_memory(0x07000000, 0x400),
        state.read_memory(0x06000000, 0x18000),
    )


def _screenshot_rgb(path: Path) -> bytes:
    with Image.open(path) as image:
        if image.size != (WIDTH, HEIGHT):
            raise ValueError(f"{path.name} screenshot size is {image.size}")
        return image.convert("RGB").tobytes()


def audit_checkpoint_corpus(checkpoint_root: Path) -> dict[str, object]:
    paths = sorted(Path(checkpoint_root).glob("*.ss9"))
    blend_effects = Counter()
    mismatches = []
    totals = Counter()
    for path in paths:
        state = load_gba_state(path)
        io = state.read_memory(0x04000000, 0x400)
        oam = state.read_memory(0x07000000, 0x400)
        dispcnt = _u16(io, 0)
        if (dispcnt & 7) == 0:
            totals["mode0"] += 1
        if dispcnt & 0x2000:
            totals["win0"] += 1
        blend_effects[(_u16(io, 0x50) >> 6) & 3] += 1
        for _, attr0, _, _ in _active_objects(oam):
            totals["active_oam"] += 1
            if attr0 & (1 << 8):
                totals["affine_oam"] += 1
            object_mode = (attr0 >> 10) & 3
            if object_mode == 1:
                totals["semitransparent_oam"] += 1
            elif object_mode == 2:
                totals["obj_window_oam"] += 1
        rendered, _ = render_checkpoint(path)
        screenshot = _screenshot_rgb(path)
        if rendered != screenshot:
            differing_bytes = sum(
                left != right for left, right in zip(rendered, screenshot)
            )
            differing_pixels = sum(
                rendered[offset : offset + 3]
                != screenshot[offset : offset + 3]
                for offset in range(0, len(rendered), 3)
            )
            mismatches.append(
                {
                    "path": path.name,
                    "differing_bytes": differing_bytes,
                    "differing_pixels": differing_pixels,
                }
            )
    return {
        "schema": "mode0-checkpoint-render-audit-v1",
        "checkpoint_count": len(paths),
        "mode0_checkpoint_count": totals["mode0"],
        "active_oam_count": totals["active_oam"],
        "affine_oam_count": totals["affine_oam"],
        "semitransparent_oam_count": totals["semitransparent_oam"],
        "obj_window_oam_count": totals["obj_window_oam"],
        "win0_checkpoint_count": totals["win0"],
        "blend_effect_counts": dict(sorted(blend_effects.items())),
        "exact_rgb_checkpoint_count": len(paths) - len(mismatches),
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoints",
        type=Path,
        default=Path("artifacts/runtime-checkpoints"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            audit_checkpoint_corpus(args.checkpoints),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
