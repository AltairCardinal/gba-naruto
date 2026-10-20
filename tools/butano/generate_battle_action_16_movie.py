#!/usr/bin/env python3
"""Generate layered Butano assets for the original action 16 movie."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit_butano_reverse_provenance import provenance_block
from tools.extract_tileset import bgr555_to_rgb, lz77_decompress

#: The products this generator writes.  The provenance auditor reads this
#: registry to learn the product set; it never guesses the set from a file
#: name pattern.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/"
    "generated_battle_action_16_movie_runtime_content.h",
)

#: The signed reverse result that records the cut-in portrait palette the
#: runtime header consumes.
CUTIN_PORTRAIT_PALETTE_FAMILY = "battle-visual-catalog-v1"
CUTIN_PORTRAIT_PALETTE_MANIFEST_SHA256 = (
    "1ccbdfda751953328104c845e061074150324ca69a569330a25263e5be787bcc"
)

ROM_BASE = 0x08000000
REFERENCE_FRAME = 360
CUTIN_REFERENCE_FRAME = 250
ACTOR_FIRE_TILES_0_ADDRESS = 0x0837AFB8
ACTOR_FIRE_TILES_1_ADDRESS = 0x0837C1E4
STREAK_TILES_ADDRESS = 0x083497BC
TITLE_TILE_ADDRESSES = (
    0x083E64D8,
    0x083E65D8,
    0x083E5974,
)
TITLE_PALETTE_ADDRESS = 0x083E4AF0
CUTIN_PORTRAIT_TILES_ADDRESS = 0x0834B248
CUTIN_PORTRAIT_TILEMAP_ADDRESS = 0x0834C1CC
CUTIN_PORTRAIT_PALETTE_ADDRESS = 0x0834C418
BG_SIZE = 256
MOVIE_FIRST_FRAME = 311
MOVIE_LAST_FRAME = 437
FIRE_PALETTE_FIRST_COLOR = 64
FIRE_PALETTE_COLOR_COUNT = 16
CUTIN_SHARED_PALETTE_ANCHOR_ROW = 255
CUTIN_SHARED_PALETTE_ITEM = (
    "battle_action_16_cutin_shared_palette"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cutin_fade_contract(trace_dir: Path) -> dict[str, int]:
    io = (
        trace_dir
        / "gpu-frame-0300-io.bin"
    ).read_bytes()
    if len(io) != 0x400:
        raise ValueError("cut-in fade IO region has unexpected size")
    window_horizontal = struct.unpack_from("<H", io, 0x40)[0]
    window_vertical = struct.unpack_from("<H", io, 0x44)[0]
    window_inside = struct.unpack_from("<H", io, 0x48)[0]
    window_outside = struct.unpack_from("<H", io, 0x4A)[0]
    blend_control = struct.unpack_from("<H", io, 0x50)[0]
    fade_steps = struct.unpack_from("<H", io, 0x54)[0]
    result = {
        "window_left": window_horizontal >> 8,
        "window_top": window_vertical >> 8,
        "window_right": window_horizontal & 0xFF,
        "window_bottom": window_vertical & 0xFF,
        "blend_control": blend_control,
        "window_inside": window_inside,
        "window_outside": window_outside,
        "fade_steps": fade_steps,
    }
    expected = {
        "window_left": 0,
        "window_top": 32,
        "window_right": 240,
        "window_bottom": 112,
        "blend_control": 0x00B7,
        "window_inside": 0x3F3F,
        "window_outside": 0x3F1F,
        "fade_steps": 6,
    }
    if result != expected:
        raise ValueError(
            f"unexpected cut-in fade contract: {result}"
        )
    return result


def _palette(raw: bytes, *, offset: int = 0, count: int = 256) -> list[int]:
    colors = [
        bgr555_to_rgb(struct.unpack_from("<H", raw, offset + index * 2)[0])
        for index in range(count)
    ]
    colors.extend([(0, 0, 0)] * (256 - len(colors)))
    return [channel for color in colors for channel in color]


def _render_background(
    vram: bytes,
    pram: bytes,
    *,
    character_base: int,
    screen_base: int,
    colors_256: bool,
) -> Image.Image:
    pixels = bytearray(BG_SIZE * BG_SIZE)
    for y in range(BG_SIZE):
        tile_y, local_y = divmod(y, 8)
        for x in range(BG_SIZE):
            tile_x, local_x = divmod(x, 8)
            map_offset = screen_base + (tile_y * 32 + tile_x) * 2
            entry = struct.unpack_from("<H", vram, map_offset)[0]
            if entry & (1 << 10):
                local_x = 7 - local_x
            if entry & (1 << 11):
                local_y = 7 - local_y
            tile_index = entry & 0x03FF
            if colors_256:
                tile_offset = (
                    character_base
                    + tile_index * 64
                    + local_y * 8
                    + local_x
                )
                color = vram[tile_offset]
            else:
                tile_offset = (
                    character_base
                    + tile_index * 32
                    + local_y * 4
                    + local_x // 2
                )
                packed = vram[tile_offset]
                color = (packed >> (4 if local_x & 1 else 0)) & 0x0F
                if color:
                    color += ((entry >> 12) & 0x0F) * 16
            pixels[y * BG_SIZE + x] = color

    image = Image.frombytes("P", (BG_SIZE, BG_SIZE), bytes(pixels))
    image.putpalette(_palette(pram))
    return image


def _render_title_sprite(tiles: bytes, palette: bytes) -> Image.Image:
    pixels = bytearray(32 * 32)
    for y in range(32):
        tile_y, local_y = divmod(y, 8)
        for x in range(32):
            tile_x, local_x = divmod(x, 8)
            tile_index = tile_y * 4 + tile_x
            offset = tile_index * 32 + local_y * 4 + local_x // 2
            packed = tiles[offset]
            pixels[y * 32 + x] = (
                packed >> (4 if local_x & 1 else 0)
            ) & 0x0F
    image = Image.frombytes("P", (32, 32), bytes(pixels))
    image.putpalette(_palette(palette, count=16))
    return image


def _preserve_shared_palette(
    images: tuple[Image.Image, ...],
    palette_bgr555_raw: bytes,
) -> tuple[tuple[Image.Image, ...], dict[str, Any]]:
    if not images:
        raise ValueError(
            "shared palette preservation requires at least one image"
        )
    if len(palette_bgr555_raw) != 256 * 2:
        raise ValueError("cut-in shared palette must contain 256 colors")

    source_palette = images[0].getpalette()
    if source_palette is None:
        raise ValueError("shared palette source image has no palette")
    for image in images[1:]:
        if image.getpalette() != source_palette:
            raise ValueError("cut-in components must share the source palette")

    used_source_indices = sorted(
        set().union(*(set(image.tobytes()) for image in images))
    )
    used_source_indices = [
        index for index in used_source_indices if index != 0
    ]
    remapped_images = []
    for image in images:
        if image.width < 256 or image.height <= (
            CUTIN_SHARED_PALETTE_ANCHOR_ROW
        ):
            raise ValueError(
                "cut-in image cannot hold the palette anchor"
            )
        pixels = bytearray(image.tobytes())
        anchor_offset = (
            CUTIN_SHARED_PALETTE_ANCHOR_ROW * image.width
        )
        pixels[
            anchor_offset :
            anchor_offset + 256
        ] = bytes(range(256))
        remapped = Image.frombytes("P", image.size, bytes(pixels))
        remapped.putpalette(source_palette)
        remapped_images.append(remapped)

    bgr555_colors = [
        color & 0x7FFF
        for color in struct.unpack("<256H", palette_bgr555_raw)
    ]
    normalized_palette_raw = struct.pack(
        "<256H",
        *bgr555_colors,
    )
    return tuple(remapped_images), {
        "color_count": 256,
        "anchor_row": CUTIN_SHARED_PALETTE_ANCHOR_ROW,
        "palette_sha256": _sha256(normalized_palette_raw),
        "source_indices": used_source_indices,
        "bgr555_colors": bgr555_colors,
    }


def _write_background(
    output_dir: Path,
    stem: str,
    image: Image.Image,
    source: dict[str, Any],
    *,
    palette_item: str | None = None,
) -> dict[str, Any]:
    image_path = output_dir / f"{stem}.bmp"
    metadata_path = output_dir / f"{stem}.json"
    image.save(image_path)
    metadata = {
        "type": "regular_bg",
        "bpp_mode": "bpp_8",
        "colors_count": 256,
        "compression": "auto_no_huffman",
        "source": source,
        "active_size": [240, 160],
        "component_pipeline": (
            "original tiles + tilemap + palette -> Butano regular BG"
        ),
    }
    if palette_item is not None:
        metadata["palette_item"] = palette_item
    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "stem": stem,
        "bmp_sha256": _sha256(image_path.read_bytes()),
        "metadata_sha256": _sha256(metadata_path.read_bytes()),
    }


def _write_title_sprite(
    output_dir: Path,
    index: int,
    image: Image.Image,
    tile_address: int,
) -> dict[str, Any]:
    stem = f"battle_action_16_movie_title_{index}"
    image_path = output_dir / f"{stem}.bmp"
    metadata_path = output_dir / f"{stem}.json"
    image.save(image_path)
    metadata_path.write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": 32,
                "source": {
                    "tiles": f"rom/base.gba:0x{tile_address:08X}",
                    "palette": (
                        f"rom/base.gba:0x{TITLE_PALETTE_ADDRESS:08X}"
                    ),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "stem": stem,
        "bmp_sha256": _sha256(image_path.read_bytes()),
        "metadata_sha256": _sha256(metadata_path.read_bytes()),
    }


def _load_runtime_timeline(trace_dir: Path) -> dict[str, Any]:
    palettes: list[list[int]] = []
    blend_top_weights: list[int] = []
    blend_bottom_weights: list[int] = []
    frame_hashes: list[dict[str, Any]] = []
    for frame in range(MOVIE_FIRST_FRAME, MOVIE_LAST_FRAME + 1):
        prefix = trace_dir / f"gpu-frame-{frame:04d}"
        pram = prefix.with_name(prefix.name + "-pram.bin").read_bytes()
        io = prefix.with_name(prefix.name + "-io.bin").read_bytes()
        if len(pram) != 0x400 or len(io) != 0x400:
            raise ValueError(
                f"frame {frame} GPU regions have unexpected sizes"
            )
        palette_offset = FIRE_PALETTE_FIRST_COLOR * 2
        palette_raw = pram[
            palette_offset :
            palette_offset + FIRE_PALETTE_COLOR_COUNT * 2
        ]
        palettes.append(
            list(struct.unpack("<16H", palette_raw))
        )
        blend_control = struct.unpack_from("<H", io, 0x50)[0]
        blend_alpha = struct.unpack_from("<H", io, 0x52)[0]
        # The original movie blends fire BG1 over actor BG0 and streak BG2.
        if 347 <= frame <= 421 and (
            blend_control & 0x3FFF
        ) != 0x0542:
            raise ValueError(
                f"frame {frame} has unexpected blend control "
                f"0x{blend_control:04X}"
            )
        blend_top_weights.append(blend_alpha & 0x1F)
        blend_bottom_weights.append((blend_alpha >> 8) & 0x1F)
        frame_hashes.append(
            {
                "frame": frame,
                "pram_sha256": _sha256(pram),
                "io_sha256": _sha256(io),
            }
        )
    return {
        "palettes": palettes,
        "blend_top_weights": blend_top_weights,
        "blend_bottom_weights": blend_bottom_weights,
        "frame_hashes": frame_hashes,
    }


def _write_runtime_header(
    path: Path,
    timeline: dict[str, Any],
    cutin_palette: list[int],
) -> None:
    palettes = timeline["palettes"]
    top_weights = timeline["blend_top_weights"]
    bottom_weights = timeline["blend_bottom_weights"]
    palette_rows = []
    for palette in palettes:
        values = ", ".join(f"0x{color:04X}" for color in palette)
        palette_rows.append(f"        {{{{{values}}}}}")

    def weight_rows(values: list[int]) -> str:
        rows = []
        for offset in range(0, len(values), 16):
            rows.append(
                "        "
                + ", ".join(
                    str(value)
                    for value in values[offset : offset + 16]
                )
            )
        return ",\n".join(rows)

    cutin_palette_rows = []
    for offset in range(0, len(cutin_palette), 16):
        cutin_palette_rows.append(
            "        "
            + ", ".join(
                f"bn::color(0x{color:04X})"
                for color in cutin_palette[
                    offset : offset + 16
                ]
            )
        )

    provenance = provenance_block(
        sources=(
            (
                CUTIN_PORTRAIT_PALETTE_FAMILY,
                CUTIN_PORTRAIT_PALETTE_MANIFEST_SHA256,
            ),
        ),
        roms=(
            (
                CUTIN_PORTRAIT_PALETTE_ADDRESS - ROM_BASE,
                32,
                "e6a298bb50adddb4fb1020899f19a567"
                "04130182965a3442d8b4550b6789caeb",
            ),
        ),
        not_applicable=(
            "the fire palettes and the blend weights come from the captured "
            "original gpu trace (pram and io dumps), not from a rom byte "
            "region",
        ),
    )
    payload = f"""// Generated by tools/butano/generate_battle_action_16_movie.py. Do not edit.
{provenance}
#ifndef KONOHA_GENERATED_BATTLE_ACTION_16_MOVIE_RUNTIME_CONTENT_H
#define KONOHA_GENERATED_BATTLE_ACTION_16_MOVIE_RUNTIME_CONTENT_H

#include <array>
#include <cstdint>

#include "bn_color.h"

namespace konoha
{{

inline constexpr int battle_action_16_movie_original_first_frame =
        {MOVIE_FIRST_FRAME};
inline constexpr std::array<bn::color, {len(cutin_palette)}>
        battle_action_16_cutin_palette = {{{{
{",\n".join(cutin_palette_rows)}
}}}};
inline constexpr std::array<
        std::array<std::uint16_t, {FIRE_PALETTE_COLOR_COUNT}>,
        {len(palettes)}> battle_action_16_movie_fire_palettes = {{{{
{",\n".join(palette_rows)}
}}}};
inline constexpr std::array<std::uint8_t, {len(top_weights)}>
        battle_action_16_movie_blend_top_weights = {{{{
{weight_rows(top_weights)}
}}}};
inline constexpr std::array<std::uint8_t, {len(bottom_weights)}>
        battle_action_16_movie_blend_bottom_weights = {{{{
{weight_rows(bottom_weights)}
}}}};

}}

#endif
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _write_cutin_palette_header(path: Path) -> None:
    guard = (
        "BN_BG_PALETTE_ITEMS_"
        "BATTLE_ACTION_16_CUTIN_SHARED_PALETTE_H"
    )
    payload = f"""#ifndef {guard}
#define {guard}

#include "bn_bg_palette_item.h"
#include "bn_span.h"
#include "konoha/generated_battle_action_16_movie_runtime_content.h"

namespace bn::bg_palette_items
{{

inline constexpr bg_palette_item {CUTIN_SHARED_PALETTE_ITEM}(
        bn::span<const bn::color>(
                konoha::battle_action_16_cutin_palette.data(),
                konoha::battle_action_16_cutin_palette.size()),
        bn::bpp_mode::BPP_8);

}}

#endif
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _cutin_components(
    rom: bytes,
    trace_dir: Path,
    output_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    prefix = trace_dir / f"gpu-frame-{CUTIN_REFERENCE_FRAME:04d}"
    vram = prefix.with_name(prefix.name + "-vram.bin").read_bytes()
    pram = prefix.with_name(prefix.name + "-pram.bin").read_bytes()
    io = prefix.with_name(prefix.name + "-io.bin").read_bytes()
    if (len(vram), len(pram), len(io)) != (0x18000, 0x400, 0x400):
        raise ValueError("cut-in GPU regions have unexpected sizes")

    portrait_tiles = lz77_decompress(
        rom,
        CUTIN_PORTRAIT_TILES_ADDRESS - ROM_BASE,
    )
    portrait_tilemap = lz77_decompress(
        rom,
        CUTIN_PORTRAIT_TILEMAP_ADDRESS - ROM_BASE,
    )
    portrait_palette = rom[
        CUTIN_PORTRAIT_PALETTE_ADDRESS - ROM_BASE :
        CUTIN_PORTRAIT_PALETTE_ADDRESS - ROM_BASE + 32
    ]
    if portrait_tiles != vram[0xC000:0xDC00]:
        raise ValueError("cut-in portrait ROM tiles do not match VRAM")
    if portrait_palette != pram[12 * 32 : 13 * 32]:
        raise ValueError("cut-in portrait ROM palette does not match PRAM")
    if len(portrait_tilemap) != 30 * 14 * 2:
        raise ValueError("cut-in portrait tilemap must be 30x14")
    for y in range(14):
        for x in range(30):
            source_entry = struct.unpack_from(
                "<H",
                portrait_tilemap,
                (y * 30 + x) * 2,
            )[0]
            vram_entry = struct.unpack_from(
                "<H",
                vram,
                0x1000 + (y * 32 + x) * 2,
            )[0]
            if vram_entry != source_entry | 0xC000:
                raise ValueError(
                    "cut-in portrait ROM tilemap does not match VRAM"
                )

    portrait = _render_background(
        vram,
        pram,
        character_base=0xC000,
        screen_base=0x1000,
        colors_256=False,
    )
    portrait_width = BG_SIZE * 2
    portrait_pixels = bytearray(portrait_width * BG_SIZE)
    source_portrait_pixels = portrait.tobytes()
    for y in range(112):
        source_offset = y * BG_SIZE
        target_offset = y * portrait_width
        portrait_pixels[
            target_offset : target_offset + BG_SIZE
        ] = source_portrait_pixels[
            source_offset : source_offset + BG_SIZE
        ]
    clipped_portrait = Image.frombytes(
        "P",
        (portrait_width, BG_SIZE),
        bytes(portrait_pixels),
    )
    clipped_portrait.putpalette(portrait.getpalette())
    dialogue = _render_background(
        vram,
        pram,
        character_base=0x0000,
        screen_base=0x1800,
        colors_256=False,
    )
    (
        clipped_portrait,
        dialogue,
    ), shared_palette = _preserve_shared_palette(
        (clipped_portrait, dialogue),
        pram[: 256 * 2],
    )
    gpu_source = {
        "reference_frame": CUTIN_REFERENCE_FRAME,
        "vram_sha256": _sha256(vram),
        "pram_sha256": _sha256(pram),
        "io_sha256": _sha256(io),
        "shared_palette_sha256": shared_palette["palette_sha256"],
        "shared_palette_anchor_row": shared_palette["anchor_row"],
    }
    backgrounds = [
        _write_background(
            output_dir,
            "battle_action_16_cutin_portrait",
            clipped_portrait,
            {
                **gpu_source,
                "role": "cutin_portrait",
                "rom_tiles": (
                    f"rom/base.gba:0x{CUTIN_PORTRAIT_TILES_ADDRESS:08X}"
                ),
                "rom_tilemap": (
                    f"rom/base.gba:0x{CUTIN_PORTRAIT_TILEMAP_ADDRESS:08X}"
                ),
                "rom_palette": (
                    f"rom/base.gba:0x{CUTIN_PORTRAIT_PALETTE_ADDRESS:08X}"
                ),
            },
            palette_item=CUTIN_SHARED_PALETTE_ITEM,
        ),
        _write_background(
            output_dir,
            "battle_action_16_cutin_dialogue",
            dialogue,
            {
                **gpu_source,
                "role": "cutin_dialogue",
                "component": "BG3 tiles + tilemap + palette",
            },
            palette_item=CUTIN_SHARED_PALETTE_ITEM,
        ),
    ]
    resources = {
        "portrait_tiles": {
            "address": f"0x{CUTIN_PORTRAIT_TILES_ADDRESS:08X}",
            "size": len(portrait_tiles),
            "sha256": _sha256(portrait_tiles),
        },
        "portrait_tilemap": {
            "address": f"0x{CUTIN_PORTRAIT_TILEMAP_ADDRESS:08X}",
            "size": len(portrait_tilemap),
            "sha256": _sha256(portrait_tilemap),
        },
        "portrait_palette": {
            "address": f"0x{CUTIN_PORTRAIT_PALETTE_ADDRESS:08X}",
            "size": len(portrait_palette),
            "sha256": _sha256(portrait_palette),
        },
    }
    return backgrounds, resources, shared_palette


def generate(
    rom_path: Path,
    trace_dir: Path,
    output_dir: Path,
    *,
    cutin_trace_dir: Path | None = None,
    manifest_path: Path | None = None,
    runtime_header_path: Path | None = None,
    cutin_palette_header_path: Path | None = None,
) -> dict[str, Any]:
    rom = rom_path.read_bytes()
    prefix = trace_dir / f"gpu-frame-{REFERENCE_FRAME:04d}"
    vram = prefix.with_name(prefix.name + "-vram.bin").read_bytes()
    pram = prefix.with_name(prefix.name + "-pram.bin").read_bytes()
    io = prefix.with_name(prefix.name + "-io.bin").read_bytes()
    oam = prefix.with_name(prefix.name + "-oam.bin").read_bytes()
    if (len(vram), len(pram), len(io), len(oam)) != (
        0x18000,
        0x400,
        0x400,
        0x400,
    ):
        raise ValueError("reference GPU regions have unexpected sizes")

    def decoded(address: int) -> bytes:
        return lz77_decompress(rom, address - ROM_BASE)

    resources = {
        "actor_fire_tiles_0": decoded(ACTOR_FIRE_TILES_0_ADDRESS),
        "actor_fire_tiles_1": decoded(ACTOR_FIRE_TILES_1_ADDRESS),
        "streak_tiles": decoded(STREAK_TILES_ADDRESS),
    }
    if resources["actor_fire_tiles_0"] != vram[0x4000:0x5D80]:
        raise ValueError("actor/fire ROM tiles do not match reference VRAM")
    if resources["actor_fire_tiles_1"] != vram[0x5D80:0x6880]:
        raise ValueError("actor/fire tail tiles do not match reference VRAM")
    if resources["streak_tiles"] != vram[0xC000:0xD000]:
        raise ValueError("streak ROM tiles do not match reference VRAM")

    output_dir.mkdir(parents=True, exist_ok=True)
    backgrounds = []
    layer_specs = (
        (
            "battle_action_16_movie_actor",
            0x4000,
            0x0000,
            True,
            {"role": "actor", "bg_control": "0x0086"},
        ),
        (
            "battle_action_16_movie_fire",
            0x4000,
            0x0800,
            False,
            {"role": "fire", "bg_control": "0x0105"},
        ),
        (
            "battle_action_16_movie_streaks",
            0xC000,
            0x1000,
            False,
            {"role": "streaks", "bg_control": "0x020F"},
        ),
        (
            "battle_action_16_movie_dialogue",
            0x0000,
            0x1800,
            False,
            {"role": "dialogue", "bg_control": "0x0300"},
        ),
    )
    for stem, character_base, screen_base, colors_256, source in layer_specs:
        source = {
            **source,
            "reference_frame": REFERENCE_FRAME,
            "vram_sha256": _sha256(vram),
            "pram_sha256": _sha256(pram),
        }
        backgrounds.append(
            _write_background(
                output_dir,
                stem,
                _render_background(
                    vram,
                    pram,
                    character_base=character_base,
                    screen_base=screen_base,
                    colors_256=colors_256,
                ),
                source,
            )
        )

    title_palette = rom[
        TITLE_PALETTE_ADDRESS - ROM_BASE :
        TITLE_PALETTE_ADDRESS - ROM_BASE + 32
    ]
    if title_palette != pram[0x3A0:0x3C0]:
        raise ValueError("title palette does not match reference PRAM")
    title_sprites = []
    for index, address in enumerate(TITLE_TILE_ADDRESSES):
        tiles = decoded(address)
        if len(tiles) != 512:
            raise ValueError("title component must be one 32x32 OBJ")
        start = 0x16800 + index * 0x200
        if tiles != vram[start : start + 0x200]:
            raise ValueError("title component does not match reference VRAM")
        title_sprites.append(
            _write_title_sprite(
                output_dir,
                index,
                _render_title_sprite(tiles, title_palette),
                address,
            )
        )

    timeline = _load_runtime_timeline(trace_dir)
    (
        cutin_backgrounds,
        cutin_rom_resources,
        cutin_shared_palette,
    ) = _cutin_components(
        rom,
        cutin_trace_dir or trace_dir,
        output_dir,
    )
    cutin_fade_contract = _cutin_fade_contract(trace_dir)
    if runtime_header_path is not None:
        _write_runtime_header(
            runtime_header_path,
            timeline,
            cutin_shared_palette["bgr555_colors"],
        )
    if cutin_palette_header_path is not None:
        _write_cutin_palette_header(
            cutin_palette_header_path
        )

    def timeline_anchor(frame: int) -> dict[str, Any]:
        index = frame - MOVIE_FIRST_FRAME
        return {
            "fire_palette_sha256": _sha256(
                struct.pack(
                    "<16H",
                    *timeline["palettes"][index],
                )
            ),
            "blend_weights": {
                "top": timeline["blend_top_weights"][index],
                "bottom": timeline["blend_bottom_weights"][index],
            },
        }

    manifest = {
        "schema": "butano-original-action-16-movie-components-v1",
        "rom_sha256": _sha256(rom),
        "reference_frame": REFERENCE_FRAME,
        "gpu_regions": {
            "io_sha256": _sha256(io),
            "vram_sha256": _sha256(vram),
            "pram_sha256": _sha256(pram),
            "oam_sha256": _sha256(oam),
        },
        "rom_resources": {
            name: {
                "address": f"0x{address:08X}",
                "size": len(resources[name]),
                "sha256": _sha256(resources[name]),
            }
            for name, address in (
                ("actor_fire_tiles_0", ACTOR_FIRE_TILES_0_ADDRESS),
                ("actor_fire_tiles_1", ACTOR_FIRE_TILES_1_ADDRESS),
                ("streak_tiles", STREAK_TILES_ADDRESS),
            )
        },
        "backgrounds": backgrounds,
        "cutin_backgrounds": cutin_backgrounds,
        "cutin_rom_resources": cutin_rom_resources,
        "cutin_shared_palette": cutin_shared_palette,
        "cutin_fade_contract": cutin_fade_contract,
        "title_sprites": title_sprites,
        "runtime_contract": {
            "movie_frames": [321, 437],
            "actor_scroll_x": 128,
            "fire_scroll_x_at_reference": 508,
            "streak_scroll_x_at_reference": 90,
            "title_oam_top_left": [[84, 4], [108, 4], [132, 4]],
        },
        "runtime_timeline": {
            "original_frames": [
                MOVIE_FIRST_FRAME,
                MOVIE_LAST_FRAME,
            ],
            "frame_count": len(timeline["palettes"]),
            "fire_palette_first_color": FIRE_PALETTE_FIRST_COLOR,
            "fire_palette_color_count": FIRE_PALETTE_COLOR_COUNT,
            "frame_hashes_sha256": _sha256(
                json.dumps(
                    timeline["frame_hashes"],
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
            "anchors": {
                "360": timeline_anchor(360),
                "400": timeline_anchor(400),
            },
        },
    }
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("trace_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--runtime-header", type=Path)
    parser.add_argument("--cutin-palette-header", type=Path)
    parser.add_argument("--cutin-trace-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    print(
        json.dumps(
            generate(
                args.rom,
                args.trace_dir,
                args.output_dir,
                cutin_trace_dir=args.cutin_trace_dir,
                manifest_path=args.manifest,
                runtime_header_path=args.runtime_header,
                cutin_palette_header_path=(
                    args.cutin_palette_header
                ),
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
