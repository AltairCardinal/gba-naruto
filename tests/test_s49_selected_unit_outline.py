#!/usr/bin/env python3
"""The selected unit must not get a cyan outline the original does not draw.

The remake used to overwrite palette entry 15 of the unit that is currently
acting with RGB5 (0,23,23).  On screen that paints a teal ring around the
unit, and the original has no such ring: across the 25 frames of the original
S49 walk there is not a single pixel of that colour, and the one place the
original does show it is the battle entry, where it is already gone four
frames later.

This gate pins the measured fact rather than the implementation: it counts the
outline colour in both recordings.  It skips when a recording is missing, so a
clean checkout stays green, and it fails when either side starts painting an
outline the other side does not have.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-original-a24"
)
REMAKE = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-remake-dd-a30-banner3"
)

# RGB5 (0,23,23) as the GBA expands it to eight bits per channel.  The
# expansion of a five bit value is not exactly value * 8, so the colour is
# matched as a narrow teal instead of as one literal triple.
OUTLINE_RGB5 = (0, 23, 23)
OUTLINE_MIN = 175
OUTLINE_MAX = 200


def is_outline(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return (
        red <= 8
        and green == blue
        and OUTLINE_MIN <= green <= OUTLINE_MAX
    )


# The status bar and the dialogue panel are chrome, not the battlefield.
FIELD_BOX = (0, 0, 240, 144)


def outline_pixels(path: Path) -> int:
    with Image.open(path) as image:
        pixels = image.convert("RGB").crop(FIELD_BOX).get_flattened_data()
    return sum(1 for pixel in pixels if is_outline(pixel))


class SelectedUnitOutlineTest(unittest.TestCase):
    def test_the_original_never_paints_the_outline(self):
        """The premise of the gate: the original does not draw it."""

        if not ORIGINAL.is_dir():
            self.skipTest("the original walk is unavailable")
        frames = sorted(ORIGINAL.glob("step-*.png"))
        if not frames:
            self.skipTest("the original walk has no frames")
        for frame in frames:
            self.assertEqual(
                outline_pixels(frame),
                0,
                f"the original paints the selected unit outline at "
                f"{frame.name}",
            )

    def test_the_remake_does_not_paint_the_outline_either(self):
        if not REMAKE.is_dir():
            self.skipTest("the remake walk is unavailable")
        frames = sorted(REMAKE.glob("step-*.png"))
        if not frames:
            self.skipTest("the remake walk has no frames")
        for frame in frames:
            self.assertEqual(
                outline_pixels(frame),
                0,
                f"the remake paints the selected unit outline at "
                f"{frame.name}",
            )


if __name__ == "__main__":
    unittest.main()
