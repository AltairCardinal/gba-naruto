#!/usr/bin/env python3
"""Independently rebuild and verify runtime-screen-composites-v1."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

from PIL import Image


SCHEMA = "runtime-screen-composites-v1"
WIDTH = 240
HEIGHT = 160
STATE_SIZE = 0x61000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SHADOW_OAM_ADDRESS = 0x0300027C
PHASE_CASES = {
    "alternate-character-submenu.ss9": (0x3F4, 0x3FA),
    "skill-list-pre-controller.ss9": (0x3FA, 0x3F8),
}
BG_DIMENSIONS = ((256, 256), (512, 256), (256, 512), (512, 512))
OBJ_DIMENSIONS = {
    0: ((8, 8), (16, 16), (32, 32), (64, 64)),
    1: ((16, 8), (32, 8), (32, 16), (64, 32)),
    2: ((8, 16), (8, 32), (16, 32), (32, 64)),
}
SCOPE = {
    "all_tracked_mode0_static_frames_rendered": True,
    "hardware_oam_domain_used_for_rendering": True,
    "89_of_91_screenshot_pixels_exact": True,
    "two_screenshot_phase_mismatches_accounted_for": True,
    "natural_mode0_text_bg_normal_1d_obj_alpha_darken_covered": True,
    "synthetic_2d_8bpp_semitransparent_obj_window_brighten_win1_covered": True,
    "unexplained_screenshot_mismatches_remaining": False,
    "natural_affine_obj_normal_and_mirror_bound_pixels_covered": True,
    "synthetic_affine_double_size_covered": True,
    "synthetic_mode0_bg_normal_and_affine_obj_mosaic_source_model_covered": True,
    "natural_nonzero_mosaic_runtime_covered": False,
    "physical_gba_mosaic_verified": False,
    "obj_window_mosaic_physical_semantics_complete": False,
    "scanline_register_changes_complete": False,
    "cross_frame_timing_complete": False,
    "screenshot_capture_phase_timing_complete": False,
    "physical_gba_display_output_verified": False,
    "all_game_visual_states_complete": False,
}
MOSAIC_REFERENCE_MODEL = {
    "implementation": "mGBA software renderer",
    "commit": "1d65391d3531f9338300f306c4e1d76c258ce657",
    "sources": [
        {
            "path": "src/gba/renderers/software-mode0.c",
            "sha256": "1e4104200fa1c068ff4ff17c24d8f99f9e1aed112d75e5088773e1bb6a318783",
            "role": "mode0-text-bg-mosaic",
        },
        {
            "path": "src/gba/renderers/software-obj.c",
            "sha256": "b737ba2372054156fd987f95ed9350e3370f469cb38b40367657c70c02667fe9",
            "role": "normal-and-affine-obj-horizontal-mosaic",
        },
        {
            "path": "src/gba/renderers/video-software.c",
            "sha256": "39a03b64a3fe9ab384a17de7d92d215298e9f5b64415f7c550d33779c2bbaf70",
            "role": "obj-vertical-mosaic",
        },
    ],
}


@dataclass(frozen=True)
class Pixel:
    color: int
    priority: int
    target: int
    order: int
    semitransparent: bool = False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _chunks(raw: bytes) -> list[tuple[bytes, bytes]]:
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("checkpoint is not a PNG container")
    result = []
    cursor = len(PNG_SIGNATURE)
    while cursor < len(raw):
        if cursor + 12 > len(raw):
            raise ValueError("truncated PNG chunk")
        size = struct.unpack_from(">I", raw, cursor)[0]
        tag = raw[cursor + 4 : cursor + 8]
        start, end = cursor + 8, cursor + 8 + size
        if end + 4 > len(raw):
            raise ValueError("truncated PNG payload")
        payload = raw[start:end]
        stored = struct.unpack_from(">I", raw, end)[0]
        if stored != zlib.crc32(tag + payload) & 0xFFFFFFFF:
            raise ValueError(f"PNG {tag!r} CRC mismatch")
        result.append((tag, payload))
        cursor = end + 4
        if tag == b"IEND":
            if cursor != len(raw):
                raise ValueError("data after PNG IEND")
            return result
    raise ValueError("PNG has no IEND")


def _state(path: Path) -> bytes:
    payloads = [payload for tag, payload in _chunks(path.read_bytes()) if tag == b"gbAs"]
    if len(payloads) != 1:
        raise ValueError(f"{path.name}: expected one gbAs chunk")
    decompressor = zlib.decompressobj()
    state = decompressor.decompress(payloads[0], STATE_SIZE + 1)
    state += decompressor.flush()
    if (
        len(state) != STATE_SIZE
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise ValueError(f"{path.name}: invalid gbAs state")
    version = struct.unpack_from("<I", state, 0)[0]
    if not 0x01000000 <= version <= 0x0100000B:
        raise ValueError(f"{path.name}: unsupported state version")
    return state


def _memory(state: bytes, address: int, size: int) -> bytes:
    regions = (
        (0x04000000, 0x400, 0x400),
        (0x05000000, 0x400, 0x800),
        (0x07000000, 0x400, 0xC00),
        (0x06000000, 0x18000, 0x1000),
        (0x03000000, 0x8000, 0x19000),
    )
    for base, length, offset in regions:
        relative = address - base
        if 0 <= relative and relative + size <= length:
            return state[offset + relative : offset + relative + size]
    raise ValueError(f"unsupported memory range 0x{address:08X}+0x{size:X}")


def _map_offset(base: int, size: int, tile_x: int, tile_y: int) -> int:
    if size == 0:
        block = 0
    elif size == 1:
        block = tile_x // 32
    elif size == 2:
        block = tile_y // 32
    else:
        block = tile_x // 32 + (tile_y // 32) * 2
    return base + block * 0x800 + ((tile_y % 32) * 32 + tile_x % 32) * 2


def _bg_layer(io: bytes, palette: bytes, vram: bytes, index: int) -> list[int | None]:
    control = _u16(io, 8 + index * 2)
    mosaic = _u16(io, 0x4C)
    mosaic_enabled = bool(control & 0x40)
    mosaic_width = (mosaic & 0xF) + 1
    mosaic_height = (mosaic >> 4 & 0xF) + 1
    size = (control >> 14) & 3
    width, height = BG_DIMENSIONS[size]
    scroll_x = _u16(io, 0x10 + index * 4) & 0x1FF
    scroll_y = _u16(io, 0x12 + index * 4) & 0x1FF
    map_base = ((control >> 8) & 31) * 0x800
    char_base = ((control >> 2) & 3) * 0x4000
    is_8bpp = bool(control & 0x80)
    colors: list[int | None] = []
    for sy in range(HEIGHT):
        sample_y = sy - sy % mosaic_height if mosaic_enabled else sy
        y = (sample_y + scroll_y) % height
        for sx in range(WIDTH):
            sample_x = sx - sx % mosaic_width if mosaic_enabled else sx
            x = (sample_x + scroll_x) % width
            map_at = _map_offset(map_base, size, x // 8, y // 8)
            if map_at + 2 > len(vram):
                raise ValueError(f"BG{index}: tilemap outside VRAM")
            entry = _u16(vram, map_at)
            px, py = x & 7, y & 7
            if entry & 0x400:
                px = 7 - px
            if entry & 0x800:
                py = 7 - py
            tile = entry & 0x3FF
            if is_8bpp:
                at = char_base + tile * 64 + py * 8 + px
                if at >= len(vram):
                    raise ValueError(f"BG{index}: tile outside VRAM")
                palette_index = vram[at]
            else:
                at = char_base + tile * 32 + py * 4 + px // 2
                if at >= len(vram):
                    raise ValueError(f"BG{index}: tile outside VRAM")
                packed = vram[at]
                palette_index = (packed >> (4 if px & 1 else 0)) & 15
                if palette_index:
                    palette_index += ((entry >> 12) & 15) * 16
            colors.append(
                None if not palette_index else _u16(palette, palette_index * 2)
            )
    return colors


def _active_objects(oam: bytes) -> list[tuple[int, int, int, int]]:
    result = []
    for index in range(128):
        attr0, attr1, attr2 = struct.unpack_from("<HHH", oam, index * 8)
        affine = bool(attr0 & 0x100)
        if not affine and attr0 & 0x200:
            continue
        if (attr0 >> 14) & 3 == 3:
            raise ValueError(f"OAM {index}: prohibited shape 3")
        result.append((index, attr0, attr1, attr2))
    return result


def _object_pixels(
    dispcnt: int, mosaic: int, pram: bytes, oam: bytes, vram: bytes
) -> tuple[list[list[Pixel]], list[bool], dict[str, int]]:
    candidates: list[list[Pixel]] = [[] for _ in range(WIDTH * HEIGHT)]
    obj_window = [False] * (WIDTH * HEIGHT)
    stats = Counter()
    for index, attr0, attr1, attr2 in _active_objects(oam):
        stats["active"] += 1
        affine = bool(attr0 & 0x100)
        double_size = affine and bool(attr0 & 0x200)
        matrix: tuple[int, int, int, int] | None = None
        if affine:
            stats["affine"] += 1
            matrix_index = attr1 >> 9 & 31
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
        origin_x, origin_y = attr1 & 0x1FF, attr0 & 0xFF
        if origin_x >= 256:
            origin_x -= 512
        if origin_y >= 160:
            origin_y -= 256
        hflip = not affine and bool(attr1 & 0x1000)
        vflip = not affine and bool(attr1 & 0x2000)
        is_8bpp = bool(attr0 & 0x2000)
        mode = (attr0 >> 10) & 3
        mosaic_enabled = bool(attr0 & 0x1000)
        mosaic_width = (mosaic >> 8 & 0xF) + 1
        mosaic_height = (mosaic >> 12 & 0xF) + 1
        if mode == 1:
            stats["semitransparent"] += 1
        elif mode == 2:
            stats["obj_window"] += 1
        elif mode == 3:
            raise ValueError(f"OAM {index}: prohibited mode 3")
        tile_units = 2 if is_8bpp else 1
        base = attr2 & 0x3FF
        if is_8bpp:
            base &= ~1
        stride = width // 8 * tile_units if dispcnt & 0x40 else 32
        for local_y in range(output_height):
            screen_y = origin_y + local_y
            if not 0 <= screen_y < HEIGHT:
                continue
            sample_screen_y = screen_y
            if mosaic_enabled and mosaic_height > 1:
                sample_screen_y -= sample_screen_y % mosaic_height
                sample_screen_y = min(
                    max(sample_screen_y, origin_y),
                    origin_y + output_height - 1,
                )
            sample_local_y = sample_screen_y - origin_y
            screen_start = max(0, origin_x)
            screen_end = min(WIDTH, origin_x + output_width)
            if (
                mosaic_enabled
                and mosaic_width > 1
                and mode != 2
                and screen_end < WIDTH
                and screen_end % mosaic_width
            ):
                screen_end = min(
                    WIDTH,
                    screen_end
                    + mosaic_width
                    - screen_end % mosaic_width,
                )
            first_mosaic_boundary = (
                screen_start
                if screen_start % mosaic_width == 0
                else screen_start
                + mosaic_width
                - screen_start % mosaic_width
            )
            for screen_x in range(screen_start, screen_end):
                local_x = screen_x - origin_x
                sample_screen_x = screen_x
                if mosaic_enabled and mosaic_width > 1 and mode != 2:
                    if affine and screen_x < first_mosaic_boundary:
                        sample_screen_x = screen_start - 1
                    else:
                        sample_screen_x -= sample_screen_x % mosaic_width
                sample_local_x = sample_screen_x - origin_x
                if affine:
                    assert matrix is not None
                    pa, pb, pc, pd = matrix
                    relative_x = sample_local_x - output_width // 2
                    relative_y = sample_local_y - output_height // 2
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
                    sample_local_x = min(
                        max(sample_local_x, 0), width - 1
                    )
                    sample_local_y = min(
                        max(sample_local_y, 0), height - 1
                    )
                    source_x = (
                        width - 1 - sample_local_x
                        if hflip
                        else sample_local_x
                    )
                    source_y = (
                        height - 1 - sample_local_y
                        if vflip
                        else sample_local_y
                    )
                tile_x, pixel_x = divmod(source_x, 8)
                tile_y, pixel_y = divmod(source_y, 8)
                tile_unit = base + tile_y * stride + tile_x * tile_units
                tile_at = 0x10000 + tile_unit * 32
                if is_8bpp:
                    at = tile_at + pixel_y * 8 + pixel_x
                    if at >= len(vram):
                        raise ValueError(f"OAM {index}: tile outside VRAM")
                    palette_index = vram[at]
                else:
                    at = tile_at + pixel_y * 4 + pixel_x // 2
                    if at >= len(vram):
                        raise ValueError(f"OAM {index}: tile outside VRAM")
                    palette_index = (
                        vram[at] >> (4 if pixel_x & 1 else 0)
                    ) & 15
                    if palette_index:
                        palette_index += ((attr2 >> 12) & 15) * 16
                if not palette_index:
                    continue
                position = screen_y * WIDTH + screen_x
                if mode == 2:
                    obj_window[position] = True
                else:
                    candidates[position].append(
                        Pixel(
                            _u16(pram, 0x200 + palette_index * 2),
                            (attr2 >> 10) & 3,
                            0x10,
                            index,
                            mode == 1,
                        )
                    )
    return candidates, obj_window, dict(stats)


def _window_range(value: int, start: int, end: int) -> bool:
    if start == end:
        return False
    return start <= value < end if start < end else value >= start or value < end


def _inside(x: int, y: int, horizontal: int, vertical: int) -> bool:
    return _window_range(x, horizontal >> 8, horizontal & 0xFF) and _window_range(
        y, vertical >> 8, vertical & 0xFF
    )


def _window(io: bytes, dispcnt: int, x: int, y: int, obj_pixel: bool) -> int:
    if not dispcnt & 0xE000:
        return 0x3F
    if dispcnt & 0x2000 and _inside(
        x, y, _u16(io, 0x40), _u16(io, 0x44)
    ):
        return _u16(io, 0x48) & 0x3F
    if dispcnt & 0x4000 and _inside(
        x, y, _u16(io, 0x42), _u16(io, 0x46)
    ):
        return _u16(io, 0x48) >> 8 & 0x3F
    outside = _u16(io, 0x4A)
    if dispcnt & 0x8000 and obj_pixel:
        return outside >> 8 & 0x3F
    return outside & 0x3F


def _rgb8(color: int) -> bytes:
    return bytes(
        (channel << 3) | (channel >> 2)
        for channel in (color & 31, color >> 5 & 31, color >> 10 & 31)
    )


def _coefficient(value: int) -> int:
    return min(16, value & 31)


def _alpha(first: int, second: int, eva: int, evb: int) -> bytes:
    a, b = _rgb8(first), _rgb8(second)
    eva, evb = _coefficient(eva), _coefficient(evb)
    return bytes(min(255, (a[i] * eva + b[i] * evb) >> 4) for i in range(3))


def _brighten(color: int, evy: int) -> bytes:
    evy = _coefficient(evy)
    return bytes(value + ((255 - value) * evy >> 4) for value in _rgb8(color))


def _darken(color: int, evy: int) -> bytes:
    evy = _coefficient(evy)
    red, green, blue = _rgb8(color)
    return bytes(
        (
            red - (red * evy >> 4),
            green * (16 - evy) >> 4,
            blue * (16 - evy) >> 4,
        )
    )


def _render(
    io: bytes, pram: bytes, oam: bytes, vram: bytes
) -> tuple[bytes, dict[str, int]]:
    if tuple(map(len, (io, pram, oam, vram))) != (0x400, 0x400, 0x400, 0x18000):
        raise ValueError("invalid GPU region sizes")
    dispcnt = _u16(io, 0)
    if dispcnt & 7:
        raise ValueError("renderer requires Mode 0")
    if dispcnt & 0x80:
        return bytes((255, 255, 255)) * WIDTH * HEIGHT, {}
    enabled = [i for i in range(4) if dispcnt & (1 << (8 + i))]
    backgrounds = {
        i: _bg_layer(io, pram[:0x200], vram[:0x10000], i) for i in enabled
    }
    if dispcnt & 0x1000:
        objects, obj_window, stats = _object_pixels(
            dispcnt, _u16(io, 0x4C), pram, oam, vram
        )
    else:
        objects = [[] for _ in range(WIDTH * HEIGHT)]
        obj_window = [False] * (WIDTH * HEIGHT)
        stats = {"active": len(_active_objects(oam))}
    blend = _u16(io, 0x50)
    effect, first_targets, second_targets = (blend >> 6) & 3, blend & 63, blend >> 8 & 63
    alpha = _u16(io, 0x52)
    eva, evb, evy = alpha & 31, alpha >> 8 & 31, _u16(io, 0x54) & 31
    backdrop = Pixel(_u16(pram, 0), 4, 0x20, 255)
    output = bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            position = y * WIDTH + x
            control = _window(io, dispcnt, x, y, obj_window[position])
            pixels = [backdrop]
            for index in enabled:
                color = backgrounds[index][position]
                if color is not None and control & (1 << index):
                    pixels.append(
                        Pixel(
                            color,
                            _u16(io, 8 + index * 2) & 3,
                            1 << index,
                            128 + index,
                        )
                    )
            if control & 0x10:
                pixels.extend(objects[position])
            pixels.sort(key=lambda item: (item.priority, item.order))
            top = pixels[0]
            rgb = _rgb8(top.color)
            effects = bool(control & 0x20)
            force_alpha = top.semitransparent and effects
            if effects and (
                force_alpha or effect == 1 and top.target & first_targets
            ):
                behind = next(
                    (
                        item
                        for item in pixels[1:]
                        if item.target & second_targets
                    ),
                    None,
                )
                if behind is not None:
                    rgb = _alpha(top.color, behind.color, eva, evb)
            elif effects and effect == 2 and top.target & first_targets:
                rgb = _brighten(top.color, evy)
            elif effects and effect == 3 and top.target & first_targets:
                rgb = _darken(top.color, evy)
            output.extend(rgb)
    return bytes(output), stats


def _screenshot(path: Path) -> bytes:
    with Image.open(path) as image:
        if image.size != (WIDTH, HEIGHT):
            raise ValueError(f"{path.name}: unexpected screenshot size")
        return image.convert("RGB").tobytes()


def _png(rgb: bytes) -> bytes:
    image = Image.frombytes("RGB", (WIDTH, HEIGHT), rgb)
    output = BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _difference(left: bytes, right: bytes) -> tuple[int, int, list[list[int]]]:
    byte_count = sum(a != b for a, b in zip(left, right))
    coordinates = [
        [offset // 3 % WIDTH, offset // 3 // WIDTH]
        for offset in range(0, len(left), 3)
        if left[offset : offset + 3] != right[offset : offset + 3]
    ]
    return byte_count, len(coordinates), coordinates


def _bbox(coordinates: list[list[int]]) -> list[int] | None:
    if not coordinates:
        return None
    xs, ys = [item[0] for item in coordinates], [item[1] for item in coordinates]
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]


def _object_rect(oam: bytes, index: int) -> list[int]:
    attr0, attr1 = struct.unpack_from("<HH", oam, index * 8)
    width, height = OBJ_DIMENSIONS[(attr0 >> 14) & 3][(attr1 >> 14) & 3]
    x, y = attr1 & 0x1FF, attr0 & 0xFF
    if x >= 256:
        x -= 512
    if y >= 160:
        y -= 256
    return [x, y, x + width, y + height]


def _domain(data: bytes, address: int) -> dict[str, object]:
    return {
        "address": f"0x{address:08X}",
        "size": len(data),
        "sha256": _sha(data),
    }


def _phase(
    path: Path,
    io: bytes,
    pram: bytes,
    vram: bytes,
    hardware: bytes,
    shadow: bytes,
    screenshot: bytes,
    coordinates: list[list[int]],
) -> dict[str, object]:
    serialized_tile, screenshot_tile = PHASE_CASES[path.name]
    attr0, attr1, attr2 = struct.unpack_from("<HHH", hardware, 0)
    if attr2 & 0x3FF != serialized_tile:
        raise ValueError(f"{path.name}: serialized tile mismatch")
    counterfactual = bytearray(hardware)
    struct.pack_into("<H", counterfactual, 4, (attr2 & 0xFC00) | screenshot_tile)
    counterfactual_rgb, _ = _render(io, pram, bytes(counterfactual), vram)
    rect = _object_rect(hardware, 0)
    inside = all(
        rect[0] <= x < rect[2] and rect[1] <= y < rect[3]
        for x, y in coordinates
    )
    return {
        "classification": "embedded-png-cursor-tile-phase-mismatch",
        "oam_index": 0,
        "hardware_shadow_oam_equal": hardware == shadow,
        "hardware_oam_entry_hex": hardware[:8].hex(),
        "shadow_oam_entry_hex": shadow[:8].hex(),
        "attr0": f"0x{attr0:04X}",
        "attr1": f"0x{attr1:04X}",
        "attr2": f"0x{attr2:04X}",
        "serialized_tile": serialized_tile,
        "screenshot_exact_tile": screenshot_tile,
        "object_screen_rect": rect,
        "all_differences_within_object_rect": inside,
        "differing_pixel_coordinates_sha256": _sha(
            json.dumps(coordinates, separators=(",", ":")).encode("utf-8")
        ),
        "counterfactual_rendered_rgb_sha256": _sha(counterfactual_rgb),
        "single_oam_tile_substitution_exact": counterfactual_rgb == screenshot,
        "unexplained_difference_count": (
            0 if counterfactual_rgb == screenshot and inside else len(coordinates)
        ),
    }


def _checkpoint(root: Path, path: Path) -> tuple[dict[str, object], bytes]:
    state = _state(path)
    io = _memory(state, 0x04000000, 0x400)
    pram = _memory(state, 0x05000000, 0x400)
    vram = _memory(state, 0x06000000, 0x18000)
    hardware = _memory(state, 0x07000000, 0x400)
    shadow = _memory(state, SHADOW_OAM_ADDRESS, 0x400)
    rendered, stats = _render(io, pram, hardware, vram)
    screenshot = _screenshot(path)
    differing_bytes, differing_pixels, coordinates = _difference(
        rendered, screenshot
    )
    phase = None
    if differing_pixels:
        if path.name not in PHASE_CASES:
            raise ValueError(f"{path.name}: unexplained mismatch")
        phase = _phase(
            path, io, pram, vram, hardware, shadow, screenshot, coordinates
        )
        if (
            not phase["hardware_shadow_oam_equal"]
            or not phase["single_oam_tile_substitution_exact"]
            or phase["unexplained_difference_count"]
        ):
            raise ValueError(f"{path.name}: phase proof failed")
    elif path.name in PHASE_CASES:
        raise ValueError(f"{path.name}: expected phase mismatch disappeared")
    member = f"frames/{path.stem}.png"
    png = _png(rendered)
    return (
        {
            "path": path.relative_to(root).as_posix(),
            "checkpoint_sha256": _sha(path.read_bytes()),
            "oam_input_domain": "hardware-oam-0x07000000",
            "domains": {
                "io": _domain(io, 0x04000000),
                "pram": _domain(pram, 0x05000000),
                "vram": _domain(vram, 0x06000000),
                "hardware_oam": _domain(hardware, 0x07000000),
                "shadow_oam": _domain(shadow, SHADOW_OAM_ADDRESS),
            },
            "display": {
                "dispcnt": f"0x{_u16(io, 0):04X}",
                "mode": _u16(io, 0) & 7,
                "obj_mapping": "1d" if _u16(io, 0) & 0x40 else "2d",
                "enabled_backgrounds": [
                    i for i in range(4) if _u16(io, 0) & (1 << (8 + i))
                ],
            },
            "active_oam_count": int(stats.get("active", 0)),
            "rendered_frame": {
                "archive_member": member,
                "png_sha256": _sha(png),
                "rgb_sha256": _sha(rendered),
                "width": WIDTH,
                "height": HEIGHT,
            },
            "rendered_rgb_sha256": _sha(rendered),
            "screenshot_rgb_sha256": _sha(screenshot),
            "rgb_exact": rendered == screenshot,
            "differing_bytes": differing_bytes,
            "differing_pixels": differing_pixels,
            "difference_bbox": _bbox(coordinates),
            "phase_classification": phase,
        },
        png,
    )


def _affine_runtime_goldens(root: Path) -> list[dict[str, object]]:
    evidence_root = root / "artifacts/battle-effect-affine-runtime-v1"
    cases = (
        ("raw/state-0154.ss9", 2, "runtime-object-02.png"),
        (
            "mirror-raw/mirrored.ss9",
            5,
            "runtime-object-mirrored.png",
        ),
    )
    records = []
    for state_relative, object_index, reference_relative in cases:
        state_path = evidence_root / state_relative
        state = _state(state_path)
        io = _memory(state, 0x04000000, 0x400)
        pram = _memory(state, 0x05000000, 0x400)
        vram = _memory(state, 0x06000000, 0x18000)
        hardware = _memory(state, 0x07000000, 0x400)
        isolated = bytearray(hardware)
        for index in range(128):
            struct.pack_into("<H", isolated, index * 8, 0x0200)
        start = object_index * 8
        isolated[start : start + 6] = hardware[start : start + 6]
        candidates, _, stats = _object_pixels(
            _u16(io, 0),
            _u16(io, 0x4C),
            pram,
            bytes(isolated),
            vram,
        )
        attr0, attr1, attr2 = struct.unpack_from("<HHH", hardware, start)
        matrix_index = attr1 >> 9 & 31
        matrix = tuple(
            struct.unpack_from(
                "<h",
                hardware,
                (matrix_index * 4 + component) * 8 + 6,
            )[0]
            for component in range(4)
        )
        width, height = OBJ_DIMENSIONS[(attr0 >> 14) & 3][(attr1 >> 14) & 3]
        if attr0 & 0x200:
            width *= 2
            height *= 2
        origin_x, origin_y = attr1 & 0x1FF, attr0 & 0xFF
        if origin_x >= 256:
            origin_x -= 512
        if origin_y >= 160:
            origin_y -= 256
        rgba = bytearray()
        for local_y in range(height):
            for local_x in range(width):
                x, y = origin_x + local_x, origin_y + local_y
                pixels = (
                    candidates[y * WIDTH + x]
                    if 0 <= x < WIDTH and 0 <= y < HEIGHT
                    else []
                )
                if pixels:
                    if len(pixels) != 1:
                        raise ValueError(
                            f"{state_path.name}: isolated affine overlap"
                        )
                    rgba.extend((*_rgb8(pixels[0].color), 255))
                else:
                    rgba.extend((0, 0, 0, 0))
        reference_path = evidence_root / reference_relative
        with Image.open(reference_path) as image:
            reference_rgba = image.convert("RGBA").tobytes()
            reference_size = list(image.size)
        if bytes(rgba) != reference_rgba or reference_size != [width, height]:
            raise ValueError(
                f"{state_path.name}: affine object does not match reference"
            )
        records.append(
            {
                "state_path": state_path.relative_to(root).as_posix(),
                "state_sha256": _sha(state_path.read_bytes()),
                "object_index": object_index,
                "attributes": {
                    "attr0": f"0x{attr0:04X}",
                    "attr1": f"0x{attr1:04X}",
                    "attr2": f"0x{attr2:04X}",
                    "affine": True,
                    "double_size": bool(attr0 & 0x200),
                    "matrix_index": matrix_index,
                    "matrix": {
                        name: value
                        for name, value in zip(
                            ("PA", "PB", "PC", "PD"), matrix
                        )
                    },
                },
                "domains": {
                    "io": _domain(io, 0x04000000),
                    "pram": _domain(pram, 0x05000000),
                    "vram": _domain(vram, 0x06000000),
                    "hardware_oam": _domain(hardware, 0x07000000),
                },
                "reference_png": {
                    "path": reference_path.relative_to(root).as_posix(),
                    "sha256": _sha(reference_path.read_bytes()),
                    "rgba_sha256": _sha(reference_rgba),
                    "width": width,
                    "height": height,
                },
                "rendered_rgba_sha256": _sha(bytes(rgba)),
                "rgba_exact": True,
                "isolated_active_oam_count": int(stats.get("active", 0)),
                "isolated_affine_oam_count": int(stats.get("affine", 0)),
            }
        )
    return records


def _archive(members: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name], compresslevel=9)
    return output.getvalue()


def _expected(root: Path) -> tuple[dict[str, object], bytes, dict[str, object]]:
    paths = sorted((root / "artifacts/runtime-checkpoints").glob("*.ss9"))
    if not paths:
        raise ValueError("no tracked checkpoints")
    records: list[dict[str, object]] = []
    members: dict[str, bytes] = {}
    for path in paths:
        record, png = _checkpoint(root, path)
        records.append(record)
        members[str(record["rendered_frame"]["archive_member"])] = png
    archive = _archive(members)
    exact = sum(bool(row["rgb_exact"]) for row in records)
    affine_goldens = _affine_runtime_goldens(root)
    implementation = {
        "exporter_sha256": _sha(
            (root / "tools/export_runtime_screen_composites.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            (root / "tools/verify_runtime_screen_composites.py").read_bytes()
        ),
        "renderer_sha256": _sha(
            (root / "tools/render_mode0_checkpoint.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_runtime_screen_composites.py").read_bytes()
        ),
        "renderer_test_sha256": _sha(
            (root / "tests/test_render_mode0_checkpoint.py").read_bytes()
        ),
        "renderer_source_verifier_sha256": _sha(
            (root / "tools/verify_mgba_renderer_source.py").read_bytes()
        ),
    }
    data = {
        "schema": SCHEMA,
        "implementation": implementation,
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_glob": "*.ss9",
            "checkpoint_count": len(records),
            "affine_runtime_evidence_root": (
                "artifacts/battle-effect-affine-runtime-v1"
            ),
            "affine_runtime_evidence_manifest_sha256": _sha(
                (
                    root
                    / "artifacts/battle-effect-affine-runtime-v1/manifest.json"
                ).read_bytes()
            ),
        },
        "renderer": {
            "display_mode": 0,
            "screen_size": [WIDTH, HEIGHT],
            "semantics": "serialized IO/PRAM/VRAM/hardware-OAM static frame",
            "oam_input_address": "0x07000000",
            "shadow_oam_diagnostic_address": f"0x{SHADOW_OAM_ADDRESS:08X}",
            "mosaic_reference_model": MOSAIC_REFERENCE_MODEL,
        },
        "summary": {
            "checkpoint_count": len(records),
            "exact_rgb_count": exact,
            "screenshot_phase_mismatch_count": len(records) - exact,
            "unexplained_mismatch_count": sum(
                int((row["phase_classification"] or {}).get(
                    "unexplained_difference_count", 0
                ))
                for row in records
            ),
            "active_oam_count": sum(int(row["active_oam_count"]) for row in records),
            "archive_member_count": len(members),
            "affine_runtime_golden_count": len(affine_goldens),
        },
        "archive": {
            "file": "frames.zip",
            "size": len(archive),
            "sha256": _sha(archive),
            "member_count": len(members),
            "deterministic_zip_timestamp": "1980-01-01T00:00:00",
        },
        "checkpoints": records,
        "affine_runtime_goldens": affine_goldens,
        "scope": SCOPE,
    }
    data_bytes = (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    promotion = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            "frames.zip": _sha(archive),
            "runtime-screen-composites.json": _sha(data_bytes),
        },
        "source": {
            "checkpoint_root": "artifacts/runtime-checkpoints",
            "checkpoint_count": len(records),
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_runtime_screen_composites.py",
                "--root",
                ".",
                "--output-dir",
                "artifacts/runtime-screen-composites-v1",
            ],
            **implementation,
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_runtime_screen_composites.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/runtime-screen-composites-v1",
            ],
            "verifier_sha256": implementation["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": "runtime-screen-composites-verification-v1",
                "verified": True,
                "checkpoint_count": len(records),
                "exact_rgb_count": exact,
                "errors": [],
            },
        },
        "experiment": {
            "task": "runtime-screen-composites",
            "run_id": "tracked-mode0-screen-mosaic-20260730-05",
        },
    }
    return data, archive, promotion


def verify_artifact(root: Path, artifact: Path) -> dict[str, object]:
    root, artifact = Path(root).resolve(), Path(artifact).resolve()
    errors: list[str] = []
    try:
        expected, expected_archive, expected_promotion = _expected(root)
    except Exception as error:
        return {
            "schema": "runtime-screen-composites-verification-v1",
            "verified": False,
            "checkpoint_count": 0,
            "exact_rgb_count": 0,
            "errors": [f"independent rebuild failed: {error}"],
        }
    try:
        actual = json.loads(
            (artifact / "runtime-screen-composites.json").read_text(encoding="utf-8")
        )
        if actual != expected:
            errors.append("runtime data does not match independent reconstruction")
    except Exception as error:
        errors.append(f"runtime data read failed: {error}")
    try:
        promotion = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        if promotion != expected_promotion:
            errors.append("promotion manifest does not match reconstruction")
    except Exception as error:
        errors.append(f"promotion manifest read failed: {error}")
    try:
        actual_archive = (artifact / "frames.zip").read_bytes()
        if actual_archive != expected_archive:
            errors.append("frames.zip does not match independent reconstruction")
        with zipfile.ZipFile(BytesIO(actual_archive)) as bundle:
            if bundle.testzip() is not None:
                errors.append("frames.zip has a corrupt member")
    except Exception as error:
        errors.append(f"archive verification failed: {error}")
    files = sorted(
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file()
    )
    expected_files = [
        "frames.zip",
        "manifest.json",
        "runtime-screen-composites.json",
    ]
    if files != expected_files:
        errors.append(f"unexpected artifact files: {files}")
    return {
        "schema": "runtime-screen-composites-verification-v1",
        "verified": not errors,
        "checkpoint_count": len(expected["checkpoints"]),
        "exact_rgb_count": expected["summary"]["exact_rgb_count"],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/runtime-screen-composites-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
