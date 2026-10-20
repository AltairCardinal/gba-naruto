#!/usr/bin/env python3
"""A unit that has only moved faces the way it moved, not its focus point.

In the original S49 the unit the mission asks the player to protect (木叶丸)
starts on scene column 8 and ends the turn on column 10: he walked **two
cells east**, and the original draws him **facing east**.  The focus
position the mission gives him lies north east of his destination
(12, 3 against 10, 7), so "face the focus" and "face the movement
direction" disagree, which is what makes the rule observable in the pixels.

The original side is measured, not narrated:

* the original's command menu frame draws 木叶丸 as the dimmed (greyscale)
  non-acting unit, using the palette that was read out of the original's
  palette RAM;
* the leftmost column of that art is screen column 80, which with the
  camera (240, 24) and the grid model of the reverse side
  (``notes/character-runtime-unit-oam-bindings-20260730.md``) is scene
  column 10;
* the art is not bilaterally symmetric, so the facing is visible.

The remake side is measured on the *declared* frame pairs of the region
comparison receipts with an orientation test: the original's unit region
compared with the remake's has to be much closer than the original's
**mirrored** region compared with the remake's.  A remake that faced the
other way would fail that.

The measurements come from
``tools/butano/measure_s49_rule_ai_facing.py``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano import measure_s49_rule_ai_facing as measurement  # noqa: E402


class AiFacingOriginalEvidence(unittest.TestCase):
    """The original's post-move cell and the observability of the facing."""

    def test_the_original_draws_the_ai_unit_dimmed(self):
        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(
            original["dimmed_receipt"],
            "artifacts/s49-original-gpu-20261020-v2/dimmed-palette-receipt.json",
            "the dimmed palette no longer comes from the original's palette "
            "RAM receipt",
        )
        self.assertEqual(
            original["art_left_column"],
            80,
            "the original's dimmed unit no longer starts at screen column 80",
        )

    def test_the_original_unit_walked_two_cells_east(self):
        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(original["scene_column"], 10)
        self.assertEqual(original["deployment_column"], 8)
        self.assertEqual(original["walked_cells"], 2)
        self.assertEqual(
            original["walked_direction"],
            "east",
            "the original's 木叶丸 no longer walks east",
        )

    def test_facing_the_focus_would_give_a_different_answer(self):
        """Without this the gate could not tell the two rules apart."""

        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(original["facing_the_movement_gives"], "east")
        self.assertEqual(
            original["facing_the_focus_would_give"],
            "north",
            "the focus position no longer disagrees with the movement "
            "direction; the orientation test below would be vacuous",
        )

    def test_the_facing_is_observable_in_the_pixels(self):
        payload = measurement.measure(ROOT)
        self.assertTrue(
            payload["original"]["art_is_mirror_asymmetric"],
            "the original's unit art is bilaterally symmetric, so its "
            "facing cannot be read from the pixels",
        )


class AiFacingRemakeConformance(unittest.TestCase):
    """The remake has to draw the unit in the same orientation."""

    def test_every_declared_pair_faces_the_same_way(self):
        payload = measurement.measure(ROOT)
        pairs = payload["pairs"]
        self.assertTrue(pairs, "no declared frame pair was measured")
        for pair in pairs:
            with self.subTest(baseline=pair["baseline"]):
                self.assertLess(
                    pair["direct_different_pixels"],
                    pair["mirrored_different_pixels"] // 2,
                    f"the remake's unit in {pair['remake_frame']} is not "
                    "drawn in the original's orientation",
                )

    def test_the_orientation_gap_is_not_a_whole_sprite(self):
        """The residual is the animation phase, not a turned around unit."""

        payload = measurement.measure(ROOT)
        for pair in payload["pairs"]:
            with self.subTest(baseline=pair["baseline"]):
                self.assertLess(
                    pair["direct_different_pixels"],
                    2000,
                    "the remake's unit region differs from the original's by "
                    "more than the animation phase accounts for",
                )


if __name__ == "__main__":
    unittest.main()
