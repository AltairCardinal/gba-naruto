#!/usr/bin/env python3
"""Locate the camera scroll offset of a frame inside the S49 map chunk.

The S49 map is one 480x304 sheet of 16-pixel cells (30 x 19 cells) taken from
`rom/base.gba:map-row-14`, so every field frame is a window into that sheet.
Matching the remake's field view and the original's field view against the sheet
turns "the scenery is different" into two measurable numbers: where each side's
camera sits.

Only water and rock pixels are scored, and only a sparse sample of them, so a
flat grass field cannot swamp the measurement and the search stays cheap.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "butano-sequel/graphics/battle_14_map_chunk_0.bmp"
ACTIVE = (480, 304)
SAMPLE_STEP = 3


def distinctive(pixel) -> bool:
    """True for the water and rock pixels that pin a window down."""

    red, green, blue = pixel
    # the three water channels: saturated cyan/teal
    if blue > 140 and green > 100 and red < 120:
        return True
    # the boulders: warm mid tones that grass never reaches
    if 90 < red < 190 and 60 < green < 160 and blue < 120 and abs(red - green) < 40:
        return True
    return False


def sample_points(frame: Image.Image):
    """Sparse sample of the frame's distinctive pixels."""

    pixels = frame.load()
    points = []
    for y in range(0, frame.size[1], SAMPLE_STEP):
        for x in range(0, frame.size[0], SAMPLE_STEP):
            pixel = pixels[x, y]
            if distinctive(pixel):
                points.append((x, y, pixel))
    return points


def best_offset(sheet: Image.Image, frame: Image.Image) -> tuple[int, int, int, int]:
    points = sample_points(frame)
    if not points:
        return 0, 0, 0, 0
    sheet_pixels = sheet.load()
    best = (-1, 0, 0, len(points))
    for oy in range(0, ACTIVE[1] - frame.size[1] + 1, 2):
        for ox in range(0, ACTIVE[0] - frame.size[0] + 1, 2):
            hit = 0
            for x, y, pixel in points:
                sx, sy = ox + x, oy + y
                if 0 <= sx < sheet.size[0] and 0 <= sy < sheet.size[1]:
                    if sheet_pixels[sx, sy] == pixel:
                        hit += 1
            if hit > best[0]:
                best = (hit, ox, oy, len(points))
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", nargs="+", type=Path)
    args = parser.parse_args()

    with Image.open(MAP) as source:
        sheet = source.convert("RGB").crop((0, 0) + ACTIVE)
    for path in args.frames:
        frame = Image.open(path).convert("RGB")
        hit, ox, oy, total = best_offset(sheet, frame)
        print(
            f"{path.name}: camera offset ({ox},{oy}) "
            f"matched {hit}/{total} sampled distinctive pixels"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
