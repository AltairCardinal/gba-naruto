#!/usr/bin/env python3
"""Derive component-rendered scenario 41 assets from the bound reference map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


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


def generate(
    source_path: Path,
    clean_map_path: Path,
    enemy_path: Path,
    clean_json_path: Path,
    enemy_json_path: Path,
) -> None:
    with Image.open(source_path) as opened:
        source = opened.copy()
    if source.mode != "P" or source.size != (512, 512):
        raise ValueError("scenario 41 reference map must be a 512x512 indexed image")

    clean = source.copy()
    clean.paste(source.crop(ACTOR_GRASS_SOURCE), ACTOR_BOX[:2])
    clean.paste(source.crop(CURSOR_GRASS_SOURCE), CURSOR_BOX[:2])

    clean_map_path.parent.mkdir(parents=True, exist_ok=True)
    clean.save(clean_map_path)
    _extract_actor(source).save(enemy_path)
    _write_json(
        clean_json_path,
        {"type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256},
    )
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
