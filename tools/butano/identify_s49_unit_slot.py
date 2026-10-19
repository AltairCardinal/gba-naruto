#!/usr/bin/env python3
"""Find which extracted unit slot the original draws a non-acting unit with.

The original's command menu shows the unit that is not acting in greyscale, and
when the greyscale palette is swapped back to the unit's own colour the sprite
turns out to be a **different picture** from the one the remake draws: the
original shows a forward-leaning pose, the remake an upright one.

The remake already extracted all nine visual slots of every character, so this
is a "picked the wrong slot" question rather than a "missing art" one.  This
tool answers it by reducing the original's colourised unit and each candidate
slot frame to a silhouette and comparing them, so the slot is identified by
measurement instead of by eye.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano.compare_s49_unit_silhouette import (  # noqa: E402
    DUMP,
    GRASS,
    WINDOW,
    colourised_original,
)

GRAPHICS = ROOT / "butano-sequel/graphics"
CHARACTER = 2  # 宇智波佐助


def _mask(image: Image.Image) -> set[tuple[int, int]]:
    x0, y0, x1, y1 = WINDOW
    pixels = image.load()
    return {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if pixels[x, y] not in GRASS
    }


def _slot_silhouette(slot: int) -> set[tuple[int, int]]:
    """Silhouette of a slot's first frame, placed where the original drew it."""

    path = GRAPHICS / f"battle_unit_{CHARACTER:02d}_slot_{slot}_part_0_shape_32x64.bmp"
    if not path.is_file():
        return set()
    with Image.open(path) as source:
        image = source.convert("P")
        pixels = image.load()
        width, height = image.size
        # Each frame is 32x64 and the sheet stacks them vertically.
        mask = {
            (x, y)
            for y in range(min(64, height))
            for x in range(width)
            if pixels[x, y] != 0
        }
    if not mask:
        return set()
    # Anchor the slot's bounding box on the original's unit bounding box.
    xs = [point[0] for point in mask]
    ys = [point[1] for point in mask]
    target_x, target_y = 80, 50
    dx = target_x - min(xs)
    dy = target_y - min(ys)
    return {(x + dx, y + dy) for x, y in mask}


def _iou(left, right) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def main() -> int:
    original = colourised_original()
    target = _mask(original)
    print(f"original unit silhouette: {len(target)} px")
    results = []
    for slot in range(9):
        candidate = _slot_silhouette(slot)
        if not candidate:
            print(f"  slot {slot}: no asset")
            continue
        results.append((_iou(target, candidate), slot, len(candidate)))
    results.sort(reverse=True)
    for iou, slot, size in results:
        print(f"  slot {slot}: IoU {iou:.3f} ({size} px)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
