#!/usr/bin/env python3
"""Generate compact Butano OBJ effect sequences from original GPU evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.analyze_original_effect_sequence import (
    ACTION_05_HIT_PALETTE_ADDRESS,
    ACTION_05_HIT_TILES_ADDRESS,
    ROM_BASE,
    analyze_effect_sequence,
)
from tools.extract_tileset import bgr555_to_rgb, lz77_decompress


@dataclass(frozen=True)
class EffectSequenceSpec:
    symbol_prefix: str
    output_prefix: str
    tiles_address: int
    palette_address: int
    first_frame: int
    last_frame: int
    base_tile: int
    tile_count: int
    palette_bank: int
    expected_asset_count: int
    include_semi_transparent: bool = False
    component_capacity: int = 8


ACTION_05_HIT_SPEC = EffectSequenceSpec(
    symbol_prefix="battle_action_05_hit",
    output_prefix="battle_action_05_hit",
    tiles_address=ACTION_05_HIT_TILES_ADDRESS,
    palette_address=ACTION_05_HIT_PALETTE_ADDRESS,
    first_frame=146,
    last_frame=180,
    base_tile=288,
    tile_count=120,
    palette_bank=5,
    expected_asset_count=14,
)

ACTION_05_DUST_SPEC = EffectSequenceSpec(
    symbol_prefix="battle_action_05_dust",
    output_prefix="battle_action_05_dust",
    tiles_address=0x083406F0,
    palette_address=0x083409D0,
    first_frame=70,
    last_frame=135,
    base_tile=256,
    tile_count=32,
    palette_bank=4,
    expected_asset_count=8,
)

ACTION_16_FIRE_HIT_SPEC = EffectSequenceSpec(
    symbol_prefix="battle_action_16_fire_hit",
    output_prefix="battle_action_16_fire_hit",
    tiles_address=0x08345E64,
    palette_address=0x083466C0,
    first_frame=484,
    last_frame=577,
    base_tile=288,
    tile_count=160,
    palette_bank=5,
    expected_asset_count=10,
)

NINJA_TOOL_BOMB_PROJECTILE_SPEC = EffectSequenceSpec(
    symbol_prefix="battle_ninja_tool_bomb_projectile",
    output_prefix="battle_ninja_tool_bomb_projectile",
    tiles_address=0x083426D8,
    palette_address=0x08342898,
    first_frame=97,
    last_frame=132,
    base_tile=256,
    tile_count=64,
    palette_bank=4,
    expected_asset_count=4,
)

NINJA_TOOL_BOMB_SMOKE_SPEC = EffectSequenceSpec(
    symbol_prefix="battle_ninja_tool_bomb_smoke",
    output_prefix="battle_ninja_tool_bomb_smoke",
    tiles_address=0x08340AF8,
    palette_address=0x08341FA8,
    first_frame=147,
    last_frame=274,
    base_tile=472,
    tile_count=304,
    palette_bank=7,
    expected_asset_count=25,
    include_semi_transparent=True,
    component_capacity=16,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _asset_stem(
    spec: EffectSequenceSpec,
    tile_offset: int,
    width: int,
    height: int,
) -> str:
    return (
        f"{spec.output_prefix}_t{tile_offset:03d}_{width}x{height}"
    )


def _decode_component_image(
    tiles: bytes,
    palette: bytes,
    tile_offset: int,
    width: int,
    height: int,
) -> Image.Image:
    if width % 8 or height % 8:
        raise ValueError("OBJ component dimensions must be tile-aligned")
    pixels = bytearray(width * height)
    tiles_wide = width // 8
    for y in range(height):
        tile_y, local_y = divmod(y, 8)
        for x in range(width):
            tile_x, local_x = divmod(x, 8)
            tile_index = (
                tile_offset + tile_y * tiles_wide + tile_x
            )
            byte_offset = tile_index * 32 + local_y * 4 + local_x // 2
            if byte_offset >= len(tiles):
                raise ValueError(
                    f"component references tile {tile_index}, "
                    f"outside {len(tiles) // 32} tiles"
                )
            packed = tiles[byte_offset]
            pixels[y * width + x] = (
                packed >> (4 if local_x & 1 else 0)
            ) & 0x0F

    image = Image.frombytes("P", (width, height), bytes(pixels))
    colors = [
        bgr555_to_rgb(struct.unpack_from("<H", palette, offset)[0])
        for offset in range(0, len(palette), 2)
    ]
    colors.extend([(0, 0, 0)] * (256 - len(colors)))
    image.putpalette(
        [channel for color in colors[:256] for channel in color]
    )
    return image


def _component_cpp(component: dict[str, Any], asset_index: int) -> str:
    result = (
        "battle_effect_component{ "
        f"{component['x']}, {component['y']}, {asset_index}, "
        f"{str(component['horizontal_flip']).lower()}, "
        f"{str(component['vertical_flip']).lower()}, "
        f"{component['priority']}"
    )
    if component.get("semi_transparent", False):
        result += ", true"
    return result + " }"


def _write_header(
    header_path: Path,
    spec: EffectSequenceSpec,
    assets: list[tuple[int, int, int]],
    frames: list[dict[str, Any]],
) -> None:
    asset_indices = {
        signature: index for index, signature in enumerate(assets)
    }
    asset_lines = [
        (
            "        battle_effect_asset{ "
            f"{tile_offset}, {width}, {height} "
            "},"
        )
        for tile_offset, width, height in assets
    ]
    frame_lines = []
    for frame in frames:
        components = []
        for component in frame["components"]:
            signature = (
                component["tile_offset"],
                component["width"],
                component["height"],
            )
            components.append(
                _component_cpp(
                    component,
                    asset_indices[signature],
                )
            )
        if len(components) > spec.component_capacity:
            raise ValueError(
                f"{spec.symbol_prefix} frame has "
                f"{len(components)} components, exceeds "
                f"capacity {spec.component_capacity}"
            )
        padded = components + [
            "battle_effect_component{}"
        ] * (spec.component_capacity - len(components))
        frame_lines.extend(
            [
                "        battle_effect_frame{ {{",
                *[f"            {line}," for line in padded],
                (
                    "        }}, "
                    + str(len(components))
                    + ", "
                    + str(frame["duration"])
                    + " },"
                ),
            ]
        )

    header_guard = (
        header_path.name.upper().replace(".", "_").replace("-", "_")
    )
    text = "\n".join(
        [
            f"#ifndef KONOHA_{header_guard}",
            f"#define KONOHA_{header_guard}",
            "",
            '#include "konoha/battle_effect_sequence.h"',
            "",
            "#include <array>",
            "",
            "namespace konoha",
            "{",
            "",
            (
                "inline constexpr std::array<battle_effect_asset, "
                f"{len(assets)}>"
            ),
            f"{spec.symbol_prefix}_assets = {{{{",
            *asset_lines,
            "}};",
            "",
            "inline constexpr battle_effect_sequence",
            f"{spec.symbol_prefix}_sequence = {{ {{{{",
            *frame_lines,
            f"}}}}, {len(frames)} }};",
            "",
            "}",
            "",
            "#endif",
            "",
        ]
    )
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(text, encoding="utf-8")


def _write_items_header(
    header_path: Path,
    spec: EffectSequenceSpec,
    assets: list[tuple[int, int, int]],
) -> Path:
    if not header_path.name.endswith("_content.h"):
        raise ValueError("generated content header must end in _content.h")
    items_path = header_path.with_name(
        header_path.name.removesuffix("_content.h") + "_items.h"
    )
    stems = [
        _asset_stem(spec, tile_offset, width, height)
        for tile_offset, width, height in assets
    ]
    header_guard = (
        items_path.name.upper().replace(".", "_").replace("-", "_")
    )
    text = "\n".join(
        [
            f"#ifndef KONOHA_{header_guard}",
            f"#define KONOHA_{header_guard}",
            "",
            '#include "bn_sprite_item.h"',
            *[
                f'#include "bn_sprite_items_{stem}.h"'
                for stem in stems
            ],
            "",
            "#include <array>",
            "",
            "namespace konoha",
            "{",
            "",
            (
                "inline constexpr std::array<const bn::sprite_item*, "
                f"{len(assets)}>"
            ),
            f"{spec.symbol_prefix}_sprite_items = {{{{",
            *[
                f"        &bn::sprite_items::{stem},"
                for stem in stems
            ],
            "}};",
            "",
            "}",
            "",
            "#endif",
            "",
        ]
    )
    items_path.write_text(text, encoding="utf-8")
    return items_path


def _compact_frames(
    frames: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    keyframes: list[dict[str, Any]] = []
    for frame in frames:
        if (
            keyframes
            and keyframes[-1]["components"] == frame["components"]
        ):
            keyframes[-1]["duration"] += 1
            keyframes[-1]["original_frame_end"] = frame[
                "original_frame"
            ]
            continue
        keyframes.append(
            {
                "original_frame_start": frame["original_frame"],
                "original_frame_end": frame["original_frame"],
                "duration": 1,
                "components": frame["components"],
            }
        )
    return keyframes


def generate_sequence(
    rom_path: Path,
    trace_dir: Path,
    graphics_dir: Path,
    header_path: Path,
    manifest_path: Path,
    spec: EffectSequenceSpec,
) -> dict[str, Any]:
    analysis = analyze_effect_sequence(
        rom_path,
        trace_dir,
        first_frame=spec.first_frame,
        last_frame=spec.last_frame,
        base_tile=spec.base_tile,
        tile_count=spec.tile_count,
        palette_bank=spec.palette_bank,
        tiles_address=spec.tiles_address,
        palette_address=spec.palette_address,
        include_semi_transparent=spec.include_semi_transparent,
    )
    active_frames = [
        frame
        for frame in analysis["frames"]
        if (
            analysis["active_frame_start"]
            <= frame["original_frame"]
            <= analysis["active_frame_end"]
        )
    ]
    signatures = sorted(
        {
            (
                component["tile_offset"],
                component["width"],
                component["height"],
            )
            for frame in active_frames
            for component in frame["components"]
        }
    )
    if len(signatures) != spec.expected_asset_count:
        raise ValueError(
            f"expected {spec.expected_asset_count} "
            f"{spec.symbol_prefix} component assets, "
            f"got {len(signatures)}"
        )
    keyframes = _compact_frames(active_frames)

    rom = rom_path.read_bytes()
    tiles = lz77_decompress(
        rom, spec.tiles_address - ROM_BASE
    )
    palette = lz77_decompress(
        rom, spec.palette_address - ROM_BASE
    )
    graphics_dir.mkdir(parents=True, exist_ok=True)
    assets = []
    for tile_offset, width, height in signatures:
        stem = _asset_stem(
            spec, tile_offset, width, height
        )
        image_path = graphics_dir / f"{stem}.bmp"
        metadata_path = graphics_dir / f"{stem}.json"
        image = _decode_component_image(
            tiles,
            palette,
            tile_offset,
            width,
            height,
        )
        image.save(image_path)
        metadata_path.write_text(
            json.dumps(
                {
                    "type": "sprite",
                    "height": height,
                    "source": (
                        "rom/base.gba:"
                        f"0x{spec.tiles_address:08X}"
                        f"+tile-{tile_offset}"
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        assets.append(
            {
                "index": len(assets),
                "stem": stem,
                "tile_offset": tile_offset,
                "width": width,
                "height": height,
                "bmp_sha256": _sha256(image_path.read_bytes()),
            }
        )

    _write_header(
        header_path, spec, signatures, keyframes
    )
    items_header_path = _write_items_header(
        header_path, spec, signatures
    )
    result = {
        "schema": "butano-original-oam-effect-sequence-v1",
        "rom_sha256": analysis["rom_sha256"],
        "trace_sha256": analysis["trace_sha256"],
        "source_resources": analysis["resources"],
        "assets": assets,
        "sequence": {
            "original_frame_start": analysis["active_frame_start"],
            "original_frame_end": analysis["active_frame_end"],
            "frame_count": analysis["active_frame_count"],
            "keyframe_count": len(keyframes),
            "duration": sum(
                frame["duration"] for frame in keyframes
            ),
            "maximum_components": analysis["maximum_components"],
            "frames": active_frames,
            "keyframes": keyframes,
        },
        "generated_header": header_path.name,
        "generated_header_sha256": _sha256(header_path.read_bytes()),
        "generated_items_header": items_header_path.name,
        "generated_items_header_sha256": _sha256(
            items_header_path.read_bytes()
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def generate(
    rom_path: Path,
    trace_dir: Path,
    graphics_dir: Path,
    header_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    return generate_sequence(
        rom_path,
        trace_dir,
        graphics_dir,
        header_path,
        manifest_path,
        ACTION_05_HIT_SPEC,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("trace_dir", type=Path)
    parser.add_argument("graphics_dir", type=Path)
    parser.add_argument("header", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--preset",
        choices=(
            "action-05-hit",
            "action-05-dust",
            "action-16-fire-hit",
            "ninja-tool-bomb-projectile",
            "ninja-tool-bomb-smoke",
        ),
        default="action-05-hit",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    specs = {
        "action-05-hit": ACTION_05_HIT_SPEC,
        "action-05-dust": ACTION_05_DUST_SPEC,
        "action-16-fire-hit": ACTION_16_FIRE_HIT_SPEC,
        "ninja-tool-bomb-projectile":
                NINJA_TOOL_BOMB_PROJECTILE_SPEC,
        "ninja-tool-bomb-smoke":
                NINJA_TOOL_BOMB_SMOKE_SPEC,
    }
    spec = specs[args.preset]
    result = generate_sequence(
        args.rom,
        args.trace_dir,
        args.graphics_dir,
        args.header,
        args.manifest,
        spec,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
