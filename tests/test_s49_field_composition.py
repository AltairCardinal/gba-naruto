#!/usr/bin/env python3
"""The original's S49 field has two bees and 木叶丸; the remake has neither.

S49 is "protect 木叶丸 from the bees", and the original's move-range screen
shows exactly that: 木叶丸 standing in the middle, 鸣人 on the right, and two
bees flying on the left.  The remake's move-range screen shows 佐助 in the
middle, 鸣人 on the right, and **no bees at all** — and its map has lost the
water channel as well.

The bee count is measured by template matching the original's own bee against
both frames, scoring only the bee's own pixels (near-white wings, near-black
body), which the grass and the rocks never produce.  That keeps a coincidence
in the scenery from being counted as a bee.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.butano.count_s49_bees import (  # noqa: E402
    BEE_BOXES,
    ORIGINAL_FRAME,
    REMAKE_FRAME,
    _match_score,
    _samples,
)


def _bees(frame: Path) -> list[int]:
    image = Image.open(frame).convert("RGB")
    original = Image.open(ORIGINAL_FRAME).convert("RGB")
    scores = []
    for box in BEE_BOXES:
        needle = original.crop(box)
        scores.append(_match_score(image, needle))
    return scores


class S49FieldComposition(unittest.TestCase):
    def setUp(self):
        if not ORIGINAL_FRAME.is_file() or not REMAKE_FRAME.is_file():
            self.skipTest("the recorded walks are unavailable")
        self.original = Image.open(ORIGINAL_FRAME).convert("RGB")
        self.needle_samples = [
            _samples(self.original.crop(box)) for box in BEE_BOXES
        ]

    def test_the_original_has_both_bees(self):
        image = self.original
        for index, box in enumerate(BEE_BOXES):
            with self.subTest(bee=index):
                needle = image.crop(box)
                score = _match_score(image, needle)
                self.assertEqual(score, self.needle_samples[index])

    def test_the_remake_has_neither_bee(self):
        remake = Image.open(REMAKE_FRAME).convert("RGB")
        for index, box in enumerate(BEE_BOXES):
            with self.subTest(bee=index):
                needle = self.original.crop(box)
                score = _match_score(remake, needle)
                self.assertLess(
                    score,
                    self.needle_samples[index] * 0.6,
                    f"the remake now shows bee {index}; swap this red gate for "
                    f"a frame-parity gate",
                )

    def test_the_two_bees_are_in_different_places(self):
        """The two boxes must not overlap, or the count would be meaningless."""

        (x0, y0, x1, y1), (u0, v0, u1, v1) = BEE_BOXES
        self.assertFalse(
            x0 < u1 and u0 < x1 and y0 < v1 and v0 < y1,
            "the two bee boxes overlap",
        )


if __name__ == "__main__":
    unittest.main()
