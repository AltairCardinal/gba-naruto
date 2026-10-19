#!/usr/bin/env python3
"""Derive component-rendered scenario 41 assets from the bound reference map."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.butano.generate_scenario_41_assets import reconstruct_map


ACTOR_BOX = (96, 128, 128, 160)
ACTOR_GRASS_SOURCE = (64, 128, 96, 160)
CURSOR_BOX = (160, 128, 192, 160)
CURSOR_GRASS_SOURCE = (192, 128, 224, 160)
ACTOR_SEED_COLORS = {
    (99, 90, 57),
    (123, 123, 16),
    (140, 140, 66),
    (189, 173, 107),
    (231, 189, 107),
    (255, 222, 148),
}
BACKGROUND_CHUNK_WIDTH = 512
BACKGROUND_CHUNK_HEIGHT = 512
GBA_VIEWPORT_WIDTH = 240


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _extract_actor(source: Image.Image) -> Image.Image:
    indexed = source.crop(ACTOR_BOX)
    rgb = indexed.convert("RGB")
    mask = [[False for _ in range(32)] for _ in range(32)]
    for y in range(32):
        seed_x = [x for x in range(32) if rgb.getpixel((x, y)) in ACTOR_SEED_COLORS]
        if seed_x:
            left = max(0, min(seed_x) - 1)
            right = min(31, max(seed_x) + 1)
            for x in range(left, right + 1):
                mask[y][x] = True

    result = Image.new("P", (32, 32), 0)
    result.putpalette(source.getpalette())
    for y in range(32):
        for x in range(32):
            if mask[y][x]:
                result.putpixel((x, y), indexed.getpixel((x, y)))
    return result


def plan_map_chunk_origins(
    active_width: int,
    *,
    chunk_width: int = BACKGROUND_CHUNK_WIDTH,
    viewport_width: int = GBA_VIEWPORT_WIDTH,
) -> list[int]:
    if active_width <= 0:
        raise ValueError("active map width must be positive")
    if chunk_width <= 0:
        raise ValueError("background chunk width must be positive")
    if viewport_width <= 0 or viewport_width > chunk_width:
        raise ValueError("viewport width must fit inside a chunk")
    if active_width <= chunk_width:
        return [0]

    maximum_step = chunk_width - viewport_width
    if maximum_step <= 0:
        raise ValueError("chunk overlap leaves no horizontal progress")
    final_origin = active_width - chunk_width
    origins = [0]
    while origins[-1] < final_origin:
        next_origin = min(
            origins[-1] + maximum_step,
            final_origin,
        )
        if next_origin <= origins[-1]:
            raise ValueError("unable to cover active map width")
        origins.append(next_origin)
    return origins


def _indexed_map_image(reconstructed: dict[str, object]) -> Image.Image:
    palette = list(reconstructed["palette"])
    flat_palette = [
        component
        for color in palette
        for component in color
    ]
    flat_palette.extend([0] * (256 * 3 - len(flat_palette)))
    active = Image.new(
        "P",
        (
            int(reconstructed["width"]),
            int(reconstructed["height"]),
        ),
        0,
    )
    active.putpalette(flat_palette)
    active.putdata(reconstructed["pixels"])
    return active


def generate_map_chunks(
    rom_path: Path,
    battle_id: int,
    output_dir: Path,
    asset_stem: str,
    manifest_path: Path,
    *,
    viewport_width: int = GBA_VIEWPORT_WIDTH,
) -> dict[str, object]:
    reconstructed = reconstruct_map(rom_path, battle_id)
    active_width = int(reconstructed["width"])
    active_height = int(reconstructed["height"])
    if active_height > BACKGROUND_CHUNK_HEIGHT:
        raise ValueError(
            f"battle map {battle_id} exceeds the vertical "
            f"{BACKGROUND_CHUNK_HEIGHT}px background limit"
        )
    origins = plan_map_chunk_origins(
        active_width,
        viewport_width=viewport_width,
    )
    active = _indexed_map_image(reconstructed)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_count = len(origins)
    for index, origin in enumerate(origins):
        chunk = Image.new(
            "P",
            (BACKGROUND_CHUNK_WIDTH, BACKGROUND_CHUNK_HEIGHT),
            0,
        )
        chunk.putpalette(active.getpalette())
        visible_width = min(
            BACKGROUND_CHUNK_WIDTH,
            active_width - origin,
        )
        chunk.paste(
            active.crop(
                (
                    origin,
                    0,
                    origin + visible_width,
                    active_height,
                )
            ),
            (0, 0),
        )
        chunk_path = (
            output_dir
            / f"{asset_stem}_chunk_{index}.bmp"
        )
        chunk.save(chunk_path)
        _write_json(
            chunk_path.with_suffix(".json"),
            {
                "type": "regular_bg",
                "bpp_mode": "bpp_8",
                "colors_count": 256,
                "compression": "auto_no_huffman",
                "source": (
                    f"rom/base.gba:map-row-{battle_id}"
                ),
                "active_size": [
                    visible_width,
                    active_height,
                ],
                "map_active_size": [
                    active_width,
                    active_height,
                ],
                "chunk_index": index,
                "chunk_count": chunk_count,
                "world_origin": [origin, 0],
                "collision_source": (
                    "generated_battle_map_content.h:"
                    f"{battle_id}"
                ),
            },
        )

    manifest: dict[str, object] = {
        "battle_id": battle_id,
        "source": f"rom/base.gba:map-row-{battle_id}",
        "active_size": [active_width, active_height],
        "chunk_size": [
            BACKGROUND_CHUNK_WIDTH,
            BACKGROUND_CHUNK_HEIGHT,
        ],
        "viewport_width": viewport_width,
        "origins": origins,
        "source_sha256": reconstructed["source_sha256"],
    }
    _write_json(manifest_path, manifest)
    return manifest


def _generate_background_cpp_header(
    entries: list[dict[str, object]],
) -> str:
    include_lines: list[str] = []
    for entry in entries:
        battle_id = int(entry["battle_id"])
        for chunk_index in range(
            len(entry["origins"])
        ):
            include_lines.append(
                '#include "bn_regular_bg_items_'
                f"battle_{battle_id:02d}_map_chunk_"
                f'{chunk_index}.h"'
            )

    lines = [
        "// Generated by "
        "tools/generate_butano_battle_runtime_assets.py. "
        "Do not edit.",
        "#ifndef "
        "KONOHA_GENERATED_BATTLE_BACKGROUND_CONTENT_H",
        "#define "
        "KONOHA_GENERATED_BATTLE_BACKGROUND_CONTENT_H",
        "",
        '#include "bn_regular_bg_item.h"',
        *include_lines,
        "",
        "#include <array>",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace konoha",
        "{",
        "",
        "struct battle_background_content_entry",
        "{",
        "    int battle_id = -1;",
        "    int pixel_width = 0;",
        "    int pixel_height = 0;",
        "    std::array<const bn::regular_bg_item*, 4> "
        "items = {};",
        "    std::array<int, 4> origins = {};",
        "    std::uint8_t chunk_count = 0;",
        "",
        "    [[nodiscard]] constexpr bool valid() const",
        "    {",
        "        return battle_id >= 0 && "
        "pixel_width > 0 &&",
        "                pixel_height > 0 && "
        "chunk_count > 0;",
        "    }",
        "};",
        "",
        "inline constexpr std::array<"
        f"battle_background_content_entry, {len(entries)}>",
        "        battle_background_content = {{",
    ]
    for entry in entries:
        battle_id = int(entry["battle_id"])
        active_width, active_height = entry["active_size"]
        origins = list(entry["origins"])
        item_values = [
            "&bn::regular_bg_items::"
            f"battle_{battle_id:02d}_map_chunk_{index}"
            for index in range(len(origins))
        ]
        item_values.extend(
            ["nullptr"] * (4 - len(item_values))
        )
        origin_values = origins + [0] * (4 - len(origins))
        lines.extend(
            [
                "    battle_background_content_entry{",
                f"        {battle_id}, "
                f"{active_width}, {active_height},",
                "        std::array<"
                "const bn::regular_bg_item*, 4>{{",
                "            "
                + ", ".join(item_values),
                "        }},",
                "        std::array<int, 4>{{ "
                + ", ".join(
                    str(value)
                    for value in origin_values
                )
                + " }},",
                f"        {len(origins)}",
                "    },",
            ]
        )
    lines.extend(
        [
            "}};",
            "",
            "[[nodiscard]] inline constexpr const "
            "battle_background_content_entry*",
            "generated_battle_background_entry(int battle_id)",
            "{",
            "    return battle_id >= 0 &&",
            "                   battle_id < static_cast<int>(",
            "                           "
            "battle_background_content.size()) ?",
            "            &battle_background_content[",
            "                    static_cast<std::size_t>(",
            "                            battle_id)] :",
            "            nullptr;",
            "}",
            "",
            "}",
            "",
            "#endif",
            "",
        ]
    )
    return "\n".join(lines)


def generate_all_map_chunks(
    rom_path: Path,
    output_dir: Path,
    header_path: Path,
    catalog_path: Path,
) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    total_chunks = 0
    for battle_id in range(47):
        manifest_name = (
            f"battle_{battle_id:02d}_map_chunks.json"
        )
        manifest = generate_map_chunks(
            rom_path,
            battle_id,
            output_dir,
            f"battle_{battle_id:02d}_map",
            output_dir / manifest_name,
        )
        entry = {
            "battle_id": battle_id,
            "active_size": manifest["active_size"],
            "origins": manifest["origins"],
            "manifest": manifest_name,
            "source_sha256": manifest["source_sha256"],
        }
        entries.append(entry)
        total_chunks += len(manifest["origins"])

    catalog: dict[str, object] = {
        "map_count": len(entries),
        "chunk_count": total_chunks,
        "chunk_size": [
            BACKGROUND_CHUNK_WIDTH,
            BACKGROUND_CHUNK_HEIGHT,
        ],
        "viewport_width": GBA_VIEWPORT_WIDTH,
        "entries": entries,
    }
    _write_json(catalog_path, catalog)
    header_path.parent.mkdir(parents=True, exist_ok=True)
    header_path.write_text(
        _generate_background_cpp_header(entries),
        encoding="utf-8",
    )
    return catalog


def generate_map(
    rom_path: Path,
    battle_id: int,
    clean_map_path: Path,
    clean_json_path: Path,
) -> None:
    reconstructed = reconstruct_map(rom_path, battle_id)
    active_width = int(reconstructed["width"])
    active_height = int(reconstructed["height"])
    if active_width > 512 or active_height > 512:
        raise ValueError(
            f"battle map {battle_id} exceeds the 512x512 Butano background"
        )
    active = _indexed_map_image(reconstructed)
    clean = Image.new("P", (512, 512), 0)
    clean.putpalette(active.getpalette())
    clean.paste(active, (0, 0))

    clean_map_path.parent.mkdir(parents=True, exist_ok=True)
    clean.save(clean_map_path)
    _write_json(
        clean_json_path,
        {
            "type": "regular_bg",
            "bpp_mode": "bpp_8",
            "colors_count": 256,
            "compression": "auto_no_huffman",
            "source": f"rom/base.gba:map-row-{battle_id}",
            "active_size": [active_width, active_height],
            "collision_source": (
                f"generated_battle_map_content.h:{battle_id}"
            ),
        },
    )


def generate(
    source_path: Path,
    clean_map_path: Path,
    enemy_path: Path,
    clean_json_path: Path,
    enemy_json_path: Path,
    rom_path: Path = REPO_ROOT / "rom" / "base.gba",
) -> None:
    with Image.open(source_path) as opened:
        source = opened.copy()
    if source.mode != "P" or source.size != (512, 512):
        raise ValueError("scenario 41 reference map must be a 512x512 indexed image")

    generate_map(
        rom_path,
        41,
        clean_map_path,
        clean_json_path,
    )
    _extract_actor(source).save(enemy_path)
    _write_json(
        enemy_json_path,
        {"type": "sprite", "height": 32, "bpp_mode": "bpp_8"},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graphics",
        type=Path,
        default=Path("butano-sequel/graphics"),
    )
    args = parser.parse_args()
    graphics = args.graphics
    generate(
        graphics / "scenario_41_map.bmp",
        graphics / "scenario_41_clean_map.bmp",
        graphics / "scenario_41_enemy.bmp",
        graphics / "scenario_41_clean_map.json",
        graphics / "scenario_41_enemy.json",
    )
    generate_map(
        REPO_ROOT / "rom" / "base.gba",
        9,
        graphics / "battle_09_clean_map.bmp",
        graphics / "battle_09_clean_map.json",
    )
    generate_all_map_chunks(
        REPO_ROOT / "rom" / "base.gba",
        graphics,
        (
            REPO_ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "generated_battle_background_content.h"
        ),
        graphics / "battle_background_catalog.json",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
