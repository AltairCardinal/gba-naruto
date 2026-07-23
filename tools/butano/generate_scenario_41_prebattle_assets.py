#!/usr/bin/env python3
"""Generate Butano backgrounds for scenario 41's prebattle menu."""

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


BOUNDARIES = (
    "menu-0",
    "menu-1",
    "menu-2",
    "menu-3",
    "confirmation-yes",
    "confirmation-no",
)


def generate_prebattle_assets(
    reference: Path, graphics: Path, header: Path
) -> dict[str, int]:
    reference = Path(reference)
    graphics = Path(graphics)
    header = Path(header)
    manifest = json.loads((reference / "manifest.json").read_text(encoding="utf-8"))
    if tuple(manifest["boundaries"]) != BOUNDARIES:
        raise ValueError("prebattle reference boundaries changed")
    images = {
        name: Image.open(reference / "screens" / manifest["boundaries"][name]["file"])
        .convert("RGB")
        for name in BOUNDARIES
    }
    if any(image.size != (240, 160) for image in images.values()):
        raise ValueError("prebattle reference dimensions changed")
    colors = sorted(
        set().union(*(set(image.get_flattened_data()) for image in images.values()))
    )
    palette = [(0, 0, 0), *colors]
    if len(palette) != 17:
        raise ValueError("prebattle palette changed")
    color_indexes = {color: index + 1 for index, color in enumerate(colors)}
    graphics.mkdir(parents=True, exist_ok=True)
    palette_name = "scenario_41_prebattle_palette"
    _write_8bpp_bmp(graphics / f"{palette_name}.bmp", 8, 8, bytes(64), palette)
    (graphics / f"{palette_name}.json").write_text(
        json.dumps(
            {"type": "bg_palette", "bpp_mode": "bpp_8", "colors_count": 17},
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    item_names = []
    for name, image in images.items():
        item_name = "scenario_41_prebattle_" + name.replace("-", "_")
        pixels = bytearray(256 * 256)
        for y in range(160):
            for x in range(240):
                pixels[y * 256 + x] = color_indexes[image.getpixel((x, y))]
        _write_8bpp_bmp(
            graphics / f"{item_name}.bmp", 256, 256, bytes(pixels), palette
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
    lines = [
        "#ifndef KONOHA_SCENARIO_41_PREBATTLE_FRAMES_H",
        "#define KONOHA_SCENARIO_41_PREBATTLE_FRAMES_H",
        "",
        "#include \"bn_regular_bg_item.h\"",
    ]
    lines.extend(f'#include "bn_regular_bg_items_{name}.h"' for name in item_names)
    lines.extend(
        [
            "",
            "#include <array>",
            "",
            "namespace konoha",
            "{",
            "",
            "inline constexpr std::array<const bn::regular_bg_item*, 4>",
            "scenario_41_prebattle_menu_frames = {",
        ]
    )
    lines.extend(
        f"    &bn::regular_bg_items::{name}," for name in item_names[:4]
    )
    lines.extend(
        [
            "};",
            "",
            "inline constexpr std::array<const bn::regular_bg_item*, 2>",
            "scenario_41_prebattle_confirmation_frames = {",
        ]
    )
    lines.extend(
        f"    &bn::regular_bg_items::{name}," for name in item_names[4:]
    )
    lines.extend(["};", "", "}", "", "#endif", ""])
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text("\n".join(lines), encoding="utf-8")
    return {"screens": 6, "colors": len(palette)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--graphics", type=Path, required=True)
    parser.add_argument("--header", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate_prebattle_assets(args.reference, args.graphics, args.header)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
