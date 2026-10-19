#!/usr/bin/env python3
"""Every opening dialogue line must be pixel-identical to the original ROM.

Three stacked defects used to make the third line render 巨助 instead of 佐助:
a stale glyph cell, a palette that spoke the wrong indices, and a text origin
four pixels off.  A fourth sat outside the label: the original draws a spiral
shell at the bottom-right of the dialogue box while a line waits for input, and
the remake drew nothing there.

This gate compares the whole screen, not a region, because after those four
fixes all three lines match with zero differing pixels.  A full-screen gate is
only meaningful here because these frames share the same backgrounds.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts/s49-fidelity-20261019-v1"
ORIGINAL = RUN / "walk-original-a24"
REMAKE = RUN / "walk-remake-dd-a30-d5fix2"
SCREEN = (0, 0, 240, 160)
# original dialogue step -> remake dialogue step -> speaker named by the original
DIALOGUES = ((11, 14, "小樱"), (12, 15, "鸣人"), (13, 16, "佐助"))


def captures_available() -> bool:
    return all(
        (ORIGINAL / f"step-{o:02d}-A.png").is_file()
        and (REMAKE / f"step-{r:02d}-A.png").is_file()
        for o, r, _ in DIALOGUES
    )


class DialogueFrameParityTest(unittest.TestCase):
    def setUp(self):
        if not captures_available():
            self.skipTest("the dialogue walks are not recorded")

    def test_every_dialogue_frame_is_pixel_identical(self):
        failures = []
        for original_step, remake_step, speaker in DIALOGUES:
            left = Image.open(
                ORIGINAL / f"step-{original_step:02d}-A.png").convert("RGB")
            right = Image.open(
                REMAKE / f"step-{remake_step:02d}-A.png").convert("RGB")
            difference = ImageChops.difference(left.crop(SCREEN), right.crop(SCREEN))
            pixels = sum(
                1 for value in difference.get_flattened_data() if any(value)
            )
            if pixels:
                failures.append(f"{speaker}: {pixels} pixels differ")
        self.assertEqual(
            failures, [],
            "every dialogue line must be pixel-identical to the original: "
            + "; ".join(failures))


if __name__ == "__main__":
    unittest.main()
