#!/usr/bin/env python3
"""Generate deduplicated Butano BG items for the scenario 41 combo timeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.butano.generate_scenario_41_assets import _write_8bpp_bmp  # noqa: E402


def _frame_colors(path: Path) -> set[tuple[int, int, int]]:
    return set(Image.open(path).convert("RGB").get_flattened_data())


def _runtime_frame_path(reference: Path, filename: str) -> Path:
    if filename.startswith("gpu-bases/"):
        return reference / filename
    return reference / "frames" / filename


def _alpha_split_frame(
    path: Path,
) -> tuple[
    list[tuple[int, int, int]], bytes, bytes, bytes
]:
    """Split one screenshot into 10/16 + 10/16 blend and opaque layers."""

    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise ValueError(f"unexpected attack alpha frame dimensions: {path}")
    gba_components = tuple((value << 3) | (value >> 2) for value in range(32))
    gba_component_set = set(gba_components)
    component_pairs = {
        target: [
            (first, second)
            for first in gba_components
            for second in gba_components
            if min(255, (first * 10 + second * 10) // 16) == target
        ]
        for target in range(256)
    }
    palette = [(0, 0, 0)]
    color_indexes: dict[tuple[int, int, int], int] = {}

    def color_index(color: tuple[int, int, int]) -> int:
        result = color_indexes.get(color)
        if result is None:
            if len(palette) == 256:
                raise ValueError("attack alpha split exceeds 255 visible colors")
            result = len(palette)
            color_indexes[color] = result
            palette.append(color)
        return result

    bottom = bytearray(256 * 256)
    middle = bytearray(256 * 256)
    top = bytearray(256 * 256)
    for y in range(160):
        for x in range(240):
            color = image.getpixel((x, y))
            offset = y * 256 + x
            if all(component in gba_component_set for component in color):
                top[offset] = color_index(color)
                continue
            pairs = []
            for component in color:
                candidates = component_pairs[component]
                if not candidates:
                    raise ValueError(f"attack alpha component is not reproducible: {component}")
                pairs.append(min(candidates, key=lambda pair: (abs(pair[0] - pair[1]), pair)))
            first = tuple(pair[0] for pair in pairs)
            second = tuple(pair[1] for pair in pairs)
            if first == (0, 0, 0) or second == (0, 0, 0):
                raise ValueError("attack alpha split produced a transparent blend color")
            middle[offset] = color_index(first)
            bottom[offset] = color_index(second)
    return palette, bytes(bottom), bytes(middle), bytes(top)


def _encode_frame(
    path: Path, color_indexes: dict[tuple[int, int, int], int]
) -> bytes:
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise ValueError(f"unexpected attack frame dimensions: {path}")
    pixels = bytearray(256 * 256)
    for y in range(160):
        for x in range(240):
            color = image.getpixel((x, y))
            pixels[y * 256 + x] = color_indexes[color]
    return bytes(pixels)


def _stable_color_indexes(
    colors_by_frame: list[set[tuple[int, int, int]]],
) -> dict[tuple[int, int, int], int]:
    all_colors = set().union(*colors_by_frame)
    conflicts = {color: set() for color in all_colors}
    for index, frame_colors in enumerate(colors_by_frame):
        adjacent_colors = set(frame_colors)
        if index + 1 < len(colors_by_frame):
            adjacent_colors.update(colors_by_frame[index + 1])
        for color in adjacent_colors:
            conflicts[color].update(adjacent_colors - {color})

    result = {(0, 0, 0): 0}
    remaining = all_colors - {(0, 0, 0)}
    while remaining:
        color = max(
            remaining,
            key=lambda candidate: (
                len({result[item] for item in conflicts[candidate] if item in result}),
                len(conflicts[candidate]),
                candidate,
            ),
        )
        used = {result[item] for item in conflicts[color] if item in result}
        color_index = 0
        while color_index in used:
            color_index += 1
        result[color] = color_index
        remaining.remove(color)
    if max(result.values()) != 139:
        raise ValueError("attack animation stable palette coloring changed")
    return result


def _animation_palettes(
    colors_by_frame: list[set[tuple[int, int, int]]],
    color_indexes: dict[tuple[int, int, int], int],
) -> list[tuple[tuple[int, int, int], ...]]:
    result = []
    for index, frame_colors in enumerate(colors_by_frame):
        adjacent_colors = set(frame_colors)
        if index + 1 < len(colors_by_frame):
            adjacent_colors.update(colors_by_frame[index + 1])
        palette = [(0, 0, 0)] * 140
        for color in adjacent_colors:
            palette[color_indexes[color]] = color
        result.append(tuple(palette))
    return result


def generate_attack_animation_assets(
    reference: Path, graphics: Path, header: Path
) -> dict[str, int]:
    reference = Path(reference)
    graphics = Path(graphics)
    header = Path(header)
    manifest = json.loads((reference / "manifest.json").read_text(encoding="utf-8"))
    timeline = manifest["timeline"]
    source_unique_filenames = list(dict.fromkeys(timeline))
    if len(timeline) != 264 or len(source_unique_filenames) != 173:
        raise ValueError("attack animation manifest has unexpected dimensions")
    runtime_timeline = list(timeline)
    for frame in range(50, 57):
        runtime_timeline[frame] = "gpu-bases/frame-0056/unfaded.png"
    for frame in range(57, 64):
        runtime_timeline[frame] = timeline[64]
    unique_filenames = list(dict.fromkeys(runtime_timeline))
    if len(unique_filenames) != 160:
        raise ValueError("attack animation runtime frame count changed")

    graphics.mkdir(parents=True, exist_ok=True)
    item_names = []
    colors_by_frame = [
        _frame_colors(_runtime_frame_path(reference, filename))
        for filename in runtime_timeline
    ]
    color_indexes = _stable_color_indexes(colors_by_frame)
    timeline_palettes = _animation_palettes(colors_by_frame, color_indexes)
    unique_palettes = list(dict.fromkeys(timeline_palettes))
    if len(unique_palettes) != 80:
        raise ValueError("attack animation palette item count changed")
    palette_to_name = {}
    for palette_index, palette in enumerate(unique_palettes):
        palette_name = f"scenario_41_attack_palette_{palette_index:03d}"
        _write_8bpp_bmp(graphics / f"{palette_name}.bmp", 8, 8, bytes(64), palette)
        (graphics / f"{palette_name}.json").write_text(
            json.dumps(
                {"type": "bg_palette", "bpp_mode": "bpp_8", "colors_count": 140},
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        palette_to_name[palette] = palette_name

    timeline_palette_names = [palette_to_name[palette] for palette in timeline_palettes]
    canonical_palette_names = {}
    timeline_item_keys = []
    for filename, palette_name in zip(runtime_timeline, timeline_palette_names):
        palette_name = canonical_palette_names.setdefault(filename, palette_name)
        timeline_item_keys.append((filename, palette_name))
    item_keys = list(dict.fromkeys(timeline_item_keys))
    if len(item_keys) != 160:
        raise ValueError("attack animation frame/palette item count changed")
    key_to_item = {}
    for item_index, (filename, palette_name) in enumerate(item_keys):
        item_name = f"scenario_41_attack_frame_{item_index:03d}"
        pixels = _encode_frame(_runtime_frame_path(reference, filename), color_indexes)
        embedded_palette = unique_palettes[
            next(
                index
                for index, name in enumerate(
                    palette_to_name[palette] for palette in unique_palettes
                )
                if name == palette_name
            )
        ]
        _write_8bpp_bmp(
            graphics / f"{item_name}.bmp", 256, 256, pixels, embedded_palette
        )
        (graphics / f"{item_name}.json").write_text(
            json.dumps(
                {
                    "type": "regular_bg",
                    "bpp_mode": "bpp_8",
                    "palette_item": palette_name,
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        item_names.append(item_name)
        key_to_item[(filename, palette_name)] = item_name

    alpha_item_names = {"bottom": [], "middle": [], "top": []}
    for frame, filename in enumerate(timeline[:4]):
        palette, bottom, middle, top = _alpha_split_frame(
            reference / "frames" / filename
        )
        palette_name = f"scenario_41_attack_alpha_{frame}_palette"
        _write_8bpp_bmp(
            graphics / f"{palette_name}.bmp", 8, 8, bytes(64), palette
        )
        (graphics / f"{palette_name}.json").write_text(
            json.dumps(
                {
                    "type": "bg_palette",
                    "bpp_mode": "bpp_8",
                    "colors_count": len(palette),
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        for layer, pixels in (("bottom", bottom), ("middle", middle), ("top", top)):
            item_name = f"scenario_41_attack_alpha_{frame}_{layer}"
            _write_8bpp_bmp(
                graphics / f"{item_name}.bmp", 256, 256, pixels, palette
            )
            (graphics / f"{item_name}.json").write_text(
                json.dumps(
                    {
                        "type": "regular_bg",
                        "bpp_mode": "bpp_8",
                        "palette_item": palette_name,
                    },
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            alpha_item_names[layer].append(item_name)

    lines = [
        "#ifndef KONOHA_SCENARIO_41_ATTACK_ANIMATION_FRAMES_H",
        "#define KONOHA_SCENARIO_41_ATTACK_ANIMATION_FRAMES_H",
        "",
        "#include \"bn_regular_bg_item.h\"",
        "#include \"bn_bg_palette_item.h\"",
    ]
    lines.extend(f'#include "bn_regular_bg_items_{name}.h"' for name in item_names)
    lines.extend(
        f'#include "bn_regular_bg_items_{name}.h"'
        for layer in ("bottom", "middle", "top")
        for name in alpha_item_names[layer]
    )
    lines.extend(
        f'#include "bn_bg_palette_items_{palette_to_name[palette]}.h"'
        for palette in unique_palettes
    )
    lines.extend(
        [
            "",
            "#include <array>",
            "",
            "namespace konoha",
            "{",
            "",
            "inline constexpr std::array<const bn::regular_bg_item*, 264>",
            "scenario_41_attack_animation_frames = {",
        ]
    )
    lines.extend(
        f"    &bn::regular_bg_items::{key_to_item[(filename, palette_name)]},"
        for filename, palette_name in timeline_item_keys
    )
    lines.extend(
        [
            "};",
            "",
            "inline constexpr std::array<const bn::bg_palette_item*, 264>",
            "scenario_41_attack_animation_palettes = {",
        ]
    )
    lines.extend(
        f"    &bn::bg_palette_items::{palette_to_name[palette]},"
        for palette in timeline_palettes
    )
    dark_fade = [0] * 264
    dark_fade[50:64] = range(15, 1, -1)
    lines.extend(
        [
            "};",
            "",
        ]
    )
    for layer in ("bottom", "middle", "top"):
        lines.extend(
            [
                "inline constexpr std::array<const bn::regular_bg_item*, 4>",
                f"scenario_41_attack_alpha_{layer} = {{",
            ]
        )
        lines.extend(
            f"    &bn::regular_bg_items::{name},"
            for name in alpha_item_names[layer]
        )
        lines.extend(["};", ""])
    lines.extend(
        [
            "inline constexpr std::array<unsigned char, 264>",
            "scenario_41_attack_animation_dark_fade = {",
            "    " + ", ".join(str(value) for value in dark_fade) + ",",
            "};",
            "",
            "}",
            "",
            "#endif",
            "",
        ]
    )
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text("\n".join(lines), encoding="utf-8")
    return {
        "unique_frames": len(item_keys),
        "timeline_frames": len(timeline),
        "palette_items": len(unique_palettes),
        "fade_frames": 14,
        "alpha_frames": 4,
        "alpha_items": 12,
        "alpha_palettes": 4,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--graphics", type=Path, required=True)
    parser.add_argument("--header", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate_attack_animation_assets(
        args.reference, args.graphics, args.header
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
