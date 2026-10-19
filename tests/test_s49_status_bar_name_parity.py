#!/usr/bin/env python3
"""The remake's status-bar unit name must match the original ROM pixel for pixel.

The 2026-10-19 fidelity pass found that the remake renders Konohamaru's name as
「打木叶」 instead of 「木叶丸」 while the generated character tables, the font
bitmaps and the unit-identity data are all correct.  The cause was the glyph
crop table: `SCENARIO_41_ORIGINAL_GLYPH_SOURCES` pointed one 8-pixel slot to the
left on the menu title line of `menu-0.png`, so 木/叶/丸 were cut from the cells
holding 打/木/叶.  The coordinates are now corrected and the atlas rebuilt.

This gate compares the name strip of both ROMs for every controllable unit of
scenario 49 so the defect stays visible if it returns, and so any future name
regression is caught too.  It is a goal gate: it stays red while any shared
unit name still differs.

The gate needs the recorded original/remake unit-cycle captures.  It skips when
they are absent.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "artifacts/s49-fidelity-20261019-v1"
ORIGINAL = RUN / "original-a6-longsettle"
REMAKE = RUN / "remake-cycle-right-v6-newrom2"
STATUS_BAR = (0, 104, 240, 160)
NAME_STRIP = (8, 130, 110, 154)
# The original cycles 鸣人→佐助→樱→木叶丸→蜜蜂 with A; the remake cycles the
# first four with Right.  Steps 1..4 line up by index.
PAIRS = [(1, 1), (2, 2), (3, 3)]


def capture_available() -> bool:
    return (
        (ORIGINAL / "step-01-A.png").is_file()
        and (REMAKE / "step-01-Right.png").is_file()
    )


class StatusBarNameParityTest(unittest.TestCase):
    def setUp(self):
        if not capture_available():
            self.skipTest("S49 unit-cycle captures are not recorded")

    def name_strip(self, image: Image.Image) -> Image.Image:
        return image.convert("RGB").crop(NAME_STRIP)

    def test_status_bar_name_matches_for_every_shared_controllable_unit(self):
        failures = []
        for original_step, remake_step in PAIRS:
            original = Image.open(
                ORIGINAL / f"step-{original_step:02d}-A.png")
            remake = Image.open(
                REMAKE / f"step-{remake_step:02d}-Right.png")
            left = self.name_strip(original)
            right = self.name_strip(remake)
            difference = ImageChops.difference(left, right)
            pixels = sum(
                1 for value in difference.convert("L").get_flattened_data()
                if value > 8
            )
            if pixels:
                failures.append(
                    f"step {original_step}/{remake_step}: {pixels} name pixels differ")
        self.assertEqual(
            failures, [],
            "status-bar unit names must be pixel-identical to the original: "
            + "; ".join(failures))

    def test_konohamaru_name_strip_is_pixel_identical(self):
        """木叶丸 must now match the original exactly; this was the fixed defect."""
        original = Image.open(ORIGINAL / "step-03-A.png").convert("RGB")
        remake = Image.open(REMAKE / "step-03-Right.png").convert("RGB")
        left = original.crop(NAME_STRIP)
        right = remake.crop(NAME_STRIP)
        difference = ImageChops.difference(left, right)
        pixels = sum(
            1 for value in difference.convert("L").get_flattened_data()
            if value > 8
        )
        self.assertEqual(
            pixels, 0,
            "Konohamaru's name strip must be pixel-identical to the original; "
            f"{pixels} pixels differ")

    def test_status_bar_body_is_a_valid_regression_target(self):
        """The whole status bar is the comparison surface, not just the name."""
        original = Image.open(ORIGINAL / "step-03-A.png").convert("RGB")
        remake = Image.open(REMAKE / "step-03-Right.png").convert("RGB")
        left = original.crop(STATUS_BAR)
        right = remake.crop(STATUS_BAR)
        difference = ImageChops.difference(left, right)
        pixels = sum(
            1 for value in difference.convert("L").get_flattened_data()
            if value > 8
        )
        self.assertEqual(
            pixels, 0,
            "Konohamaru's status bar must match the original exactly; "
            f"{pixels} pixels differ (the name currently renders as 打木叶)")


if __name__ == "__main__":
    unittest.main()
