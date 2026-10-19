#!/usr/bin/env python3
"""The unit the original greys out is 木叶丸, and the remake draws 佐助 there.

S49's command menu shows two units: the one acting, in colour, and the one not
acting, greyscaled.  The remake draws an upright blue-vest character where the
original draws a forward-leaning one with a white head covering and a yellow
tunic.  Neither of the nine visual slots of the remake's character matches, and
none of its 54 frames does either.

Searching every character's idle art settles it: the original's greyscaled unit
is **character 30, 木叶丸** — the character the mission is about ("protect
木叶丸 from the bees").  The remake puts 宇智波佐助 in that slot instead.

That is not a palette or an art problem: the two builds are showing **different
people** in the same place.  Fixing it means fixing the unit roster and the
placements, which is a battle-logic change rather than a sprite change.

The greyscale palette itself is covered by `test_s49_unit_dimmed_palette.py`.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

DUMP = ROOT / "artifacts/s49-original-gpu-20261020-v2/step-18"
GRAPHICS = ROOT / "butano-sequel/graphics"

KONOHA = 30
SASUKE = 2

# The unit the original paints at this spot.
UNIT_BOX = (80, 50, 110, 103)

GRASS = frozenset(
    {
        (173, 173, 49),
        (198, 198, 66),
        (132, 189, 49),
        (198, 239, 82),
        (123, 156, 41),
        (156, 231, 66),
        (222, 222, 90),
        (148, 148, 33),
        (115, 140, 33),
        (231, 255, 107),
        (199, 199, 199),
        (84, 189, 49),
    }
)


_CACHE: dict[str, Image.Image] = {}


def _colourised_original() -> Image.Image:
    if "frame" not in _CACHE:
        import sys

        sys.path.insert(0, str(ROOT))
        from tools.butano.compare_s49_unit_silhouette import (
            colourised_original,
        )

        _CACHE["frame"] = colourised_original()
    return _CACHE["frame"]


def _mask(image: Image.Image) -> set[tuple[int, int]]:
    x0, y0, x1, y1 = UNIT_BOX
    pixels = image.load()
    return {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if pixels[x, y] not in GRASS
    }


def _idle_mask(character: int, frame: int) -> set[tuple[int, int]]:
    path = GRAPHICS / f"battle_unit_{character:02d}_slot_0_part_0_shape_32x64.bmp"
    if not path.is_file():
        return set()
    with Image.open(path) as source:
        image = source.convert("P")
        pixels = image.load()
        width, height = image.size
        if (frame + 1) * 64 > height:
            return set()
        mask = {
            (x, y)
            for y in range(64)
            for x in range(width)
            if pixels[x, frame * 64 + y] != 0
        }
    if not mask:
        return set()
    xs = [point[0] for point in mask]
    ys = [point[1] for point in mask]
    dx = UNIT_BOX[0] - min(xs)
    dy = UNIT_BOX[1] - min(ys)
    return {(x + dx, y + dy) for x, y in mask}


def _iou(left, right) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _best_iou(target, character: int) -> tuple[float, int]:
    best = (0.0, -1)
    for frame in range(16):
        candidate = _idle_mask(character, frame)
        if not candidate:
            break
        iou = _iou(target, candidate)
        if iou > best[0]:
            best = (iou, frame)
    return best


@unittest.skipUnless(
    (DUMP / "pram.bin").is_file(), "the GPU probe dump is unavailable"
)
class InactiveUnitIdentity(unittest.TestCase):
    def setUp(self):
        self.target = _mask(_colourised_original())

    def test_the_original_greys_out_konoha(self):
        iou, frame = _best_iou(self.target, KONOHA)
        self.assertGreaterEqual(
            iou,
            0.85,
            f"character {KONOHA} no longer matches the original's greyscaled "
            f"unit (best IoU {iou:.3f} at frame {frame})",
        )

    def test_it_is_not_sasuke(self):
        iou, _ = _best_iou(self.target, SASUKE)
        self.assertLess(
            iou,
            0.80,
            f"character {SASUKE} now matches the original's greyscaled unit; "
            f"the remake may already place the right character there",
        )

    def test_the_two_characters_are_really_different(self):
        konoha = _idle_mask(KONOHA, 6)
        sasuke = _idle_mask(SASUKE, 0)
        # The two characters share a body plan, so the silhouettes overlap;
        # what separates them is the pose and the clothing, and it is the
        # higher-scoring match against the original that identifies the unit.
        self.assertLess(
            _iou(konoha, sasuke),
            0.75,
            "木叶丸 and 佐助 now share a silhouette, which would make the "
            "identity question meaningless",
        )


if __name__ == "__main__":
    unittest.main()
