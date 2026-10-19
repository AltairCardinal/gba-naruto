#!/usr/bin/env python3
"""Identify which character the original draws for the unit that is not acting.

S49's command menu shows one unit in colour and one in greyscale.  Greyscaling
the colour one back shows a forward-leaning character with a white head
covering and a red collar.  The remake draws an upright blue-vest character in
that slot instead, and none of that character's nine visual slots — 54 frames in
total — matches the leaning picture.

This tool searches every character's idle art for the silhouette that matches,
so the answer is "different art" or "different character" rather than a guess.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano.compare_s49_unit_silhouette import (  # noqa: E402
    GRASS,
    WINDOW,
    colourised_original,
)

GRAPHICS = ROOT / "butano-sequel/graphics"


def _mask(image: Image.Image) -> set[tuple[int, int]]:
    x0, y0, x1, y1 = WINDOW
    pixels = image.load()
    return {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if pixels[x, y] not in GRASS
    }


def _iou(left, right) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _candidate(character: int, slot: int, frame: int):
    path = GRAPHICS / (
        f"battle_unit_{character:02d}_slot_{slot}_part_0_shape_32x64.bmp"
    )
    if not path.is_file():
        return None
    with Image.open(path) as source:
        image = source.convert("P")
        pixels = image.load()
        width, height = image.size
        if (frame + 1) * 64 > height:
            return None
        mask = {
            (x, y)
            for y in range(64)
            for x in range(width)
            if pixels[x, frame * 64 + y] != 0
        }
    if not mask:
        return None
    xs = [point[0] for point in mask]
    ys = [point[1] for point in mask]
    dx = 80 - min(xs)
    dy = 50 - min(ys)
    return {(x + dx, y + dy) for x, y in mask}


def main() -> int:
    target = _mask(colourised_original())
    print(f"original unit silhouette: {len(target)} px")
    results = []
    for character in range(1, 63):
        for slot in range(9):
            for frame in range(16):
                candidate = _candidate(character, slot, frame)
                if not candidate:
                    break
                results.append((_iou(target, candidate), character, slot, frame))
    results.sort(reverse=True)
    for iou, character, slot, frame in results[:12]:
        print(
            f"  character {character:2d} slot {slot} frame {frame}: "
            f"IoU {iou:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
