#!/usr/bin/env python3
"""The original's move range is a dither mask, not one flat tint.

The original S49 draws the reachable area of the battlefield with a cyan
overlay that is **not** a single flat colour.  The same map colour comes out
as several different overlay colours depending on the cell, because the
original walks the overlay over the map with a dither mask.  Nineteen map
colours each map to more than one overlay colour, over eighteen distinct
cyan overlay colours.

The remake blends one flat overlay colour into the map
(``battle_range_ui_style.h``: ``move_primary`` RGB5(3,25,31), blend 10/16),
so its overlay field does not match the original's.

This gate pins the original side with the recorded frames (hash pinned) and
states the remake's pass condition.  The remake does not satisfy it yet, so
the conformance tests are ``expectedFailure``: the test run stays green and
unittest reports an *unexpected success* the moment somebody implements the
dither mask.

The measurements come from
``tools/butano/measure_s49_rule_move_grid.py``; nothing here is copied from
a note.

The reverse-side notes this rule was carried by are
``notes/character-battle-visuals-export-20260729.md`` (the unit visual
matrix the overlay art belongs to) and the S49 ledger entry
``s49-move-grid-cost-colors``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano import measure_s49_rule_move_grid as measurement  # noqa: E402


class MoveGridOriginalEvidence(unittest.TestCase):
    """The original's overlay, measured from the recorded frames."""

    def test_the_evidence_frames_are_the_pinned_bytes(self):
        payload = measurement.measure(ROOT)
        pinned = measurement.PINNED_ORIGINAL_HASHES
        recorded = payload["inputs"]["original_frame_sha256"]
        for name, digest in pinned.items():
            self.assertEqual(
                recorded[name],
                digest,
                f"the original evidence frame {name} is not the pinned bytes",
            )

    def test_the_original_overlay_covers_the_reachable_area(self):
        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(
            original["changed_pixels"],
            22735,
            "the original move range frame no longer differs from the plain "
            "frame by the measured amount",
        )
        self.assertEqual(
            original["cyan_pixels"],
            8536,
            "the number of original pixels painted with a cyan overlay "
            "colour changed",
        )

    def test_the_overlay_comes_from_a_small_fixed_cyan_palette(self):
        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(
            original["cyan_overlay_colours"],
            18,
            "the original's move range overlay is no longer an 18 colour "
            "cyan palette",
        )
        self.assertLess(
            original["cyan_overlay_colours"],
            original["distinct_overlay_colours"],
            "every overlay colour is cyan; the move range is not the only "
            "thing that changed in the field area",
        )

    def test_the_overlay_is_a_dither_mask_and_not_a_flat_tint(self):
        """A flat tint would give every base colour exactly one overlay."""

        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(
            original["bases_with_several_cyan_overlays"],
            19,
            "the original's dither mask no longer maps nineteen map colours "
            "to more than one cyan overlay colour",
        )
        self.assertGreater(
            original["bases_with_several_cyan_overlays"],
            1,
            "a single base colour with several overlays is not a dither mask",
        )


class MoveGridRemakeConformance(unittest.TestCase):
    """What the remake has to reach for the original's overlay."""

    @unittest.expectedFailure
    def test_the_remake_reproduces_the_original_overlay_field(self):
        """Missing: the original's 18 colour dither mask for the move range.

        The remake still blends one flat overlay colour into the map
        (``battle_range_ui_style.h`` move_primary RGB5(3,25,31), blend
        10/16).  It has to paint the original's dither mask instead, and
        the move range recording has to be redone afterwards.
        """

        payload = measurement.measure(ROOT)
        self.assertEqual(
            payload["original_vs_remake_different_pixels"],
            0,
            "the remake's move range overlay still differs from the "
            "original's in the field area",
        )

    @unittest.expectedFailure
    def test_the_remake_overlay_uses_the_original_fixed_palette(self):
        """Missing: an overlay palette that does not depend on the base.

        The remake's overlay colours are produced by blending one flat
        colour into the map, so they vary with the base colour; the
        original's overlay comes from a fixed 18 colour palette.
        """

        payload = measurement.measure(ROOT)
        self.assertEqual(
            payload["remake"]["cyan_overlay_colours"],
            payload["original"]["cyan_overlay_colours"],
            "the remake's overlay palette is not the original's fixed "
            "18 colour cyan palette",
        )


class EveryExpectedFailureSaysWhatIsMissing(unittest.TestCase):
    """A known gap has to be written down, not just encoded as red."""

    def test_each_expected_failure_documents_the_missing_piece(self):
        gaps = MoveGridRemakeConformance
        expected = [
            name
            for name in dir(gaps)
            if name.startswith("test_")
            and getattr(getattr(gaps, name), "__unittest_expecting_failure__", False)
        ]
        self.assertTrue(expected, "no known gap is recorded in this file")
        for name in expected:
            with self.subTest(test=name):
                doc = getattr(gaps, name).__doc__ or ""
                self.assertIn(
                    "Missing:",
                    doc,
                    f"{name} is an expected failure without a statement of "
                    "what the remake is missing",
                )


if __name__ == "__main__":
    unittest.main()
