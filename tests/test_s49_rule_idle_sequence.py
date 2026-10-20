#!/usr/bin/env python3
"""The original redraws the field unit every frame; the remake holds poses.

The original S49 does not animate its field unit in a handful of held poses.
An 1800 frame zero input sweep taken from the battle 14 entry savestate
shows the unit's own art being replaced on 183 of 191 frame transitions,
and 30 of the 32 frames of one cycle are mutually different images.  The
change is **not** a moving silhouette: the 191 transitions never carry an
overall shift (the best shift is always (0, 0)) and 109 of them keep the
silhouette mask bit for bit.  What changes is the unit's **outline colour**:
the changed pixels are exactly the pixels holding one palette index (the 1 px
outline), and that index is rewritten every frame.  See
``notes/s49-field-frame-order-20261020.md``.

The ROM's field slot (``field_idle_and_movement``) says something else: every
character's 32 frame animation holds one of three frames for eight frames at
a time, and the remake implements exactly that.  So the remake can show at
most three distinct images per 32 frame cycle where the original shows
thirty.

The contradiction is the finding.  The original's per frame redraw is **not**
explained by the ROM's hold field, so the frame order (``帧序``) of the
original's field animation is still open on the reverse side, and the remake
cannot reproduce the original's cadence from the ROM table alone.  This gate
pins both sides so the gap cannot be forgotten.

The measurements come from
``tools/butano/measure_s49_rule_idle_sequence.py``.

The reverse-side notes this rule was carried by are
``notes/character-battle-visuals-export-20260729.md`` (the visual matrix,
its timeline schema and its frame table) and
``notes/character-battle-visual-resource-matrix-20260801.md`` (the proof
that a timeline byte selects the drawn frame).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano import measure_s49_rule_idle_sequence as measurement  # noqa: E402


class IdleSequenceOriginalEvidence(unittest.TestCase):
    """The original's redraw cadence, measured from the recorded sweep."""

    def test_the_sweep_is_the_pinned_recording(self):
        payload = measurement.measure(ROOT)
        self.assertEqual(
            payload["original"]["first_frame_sha256"],
            measurement.PINNED_FIRST_FRAME_SHA256,
            "the idle sweep does not start at the pinned frame",
        )
        self.assertEqual(payload["original"]["frames_measured"], 192)

    def test_the_unit_is_redrawn_on_almost_every_frame(self):
        payload = measurement.measure(ROOT)
        sprite = payload["original"]["sprite_region"]
        self.assertEqual(
            sprite["changed_transitions"],
            183,
            "the original no longer redraws the unit on 183 of 191 frame "
            "transitions",
        )
        self.assertEqual(sprite["total_transitions"], 191)

    def test_the_unit_shows_thirty_different_images_in_one_cycle(self):
        payload = measurement.measure(ROOT)
        sprite = payload["original"]["sprite_region"]
        self.assertEqual(
            sprite["distinct_images_in_32_frames"],
            30,
            "the original no longer shows thirty different images inside "
            "32 frames",
        )
        self.assertEqual(
            sprite["identical_neighbouring_frames_in_32"],
            1,
            "the original's cycle no longer holds exactly one repeated frame",
        )

    def test_the_change_is_in_the_unit_and_not_in_the_selection_chrome(self):
        """The bracket and the facing indicator sit in the left columns."""

        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(
            original["changed_region_bbox"],
            [109, 32, 146, 90],
            "the changed region of the original's idle cycle moved",
        )
        self.assertEqual(
            original["full_region"]["distinct_images_in_32_frames"],
            31,
            "the full changed region no longer holds 31 different images",
        )


class RomFieldSlotTimeline(unittest.TestCase):
    """The ROM side: the field slot holds a pose, it does not advance."""

    def test_every_character_has_a_field_slot(self):
        payload = measurement.measure(ROOT)
        self.assertEqual(
            payload["rom_model"]["characters_with_a_field_slot"],
            62,
            "the ROM derived catalog no longer has a field slot for every "
            "character",
        )

    def test_the_thirty_two_frame_cycle_holds_at_most_three_frames(self):
        payload = measurement.measure(ROOT)
        model = payload["rom_model"]
        self.assertIn(
            32,
            model["cycle_length_to_max_distinct_frames"],
            "the ROM's field slot no longer has a 32 frame cycle",
        )
        self.assertLessEqual(
            model["cycle_length_to_max_distinct_frames"][32],
            3,
            "the ROM's 32 frame field cycle now advances more than three "
            "frames; the remake's model may already match the original",
        )

    def test_the_rom_timeline_cannot_explain_the_observed_redraw(self):
        """The contradiction this gate exists to record."""

        payload = measurement.measure(ROOT)
        original = payload["original"]["sprite_region"]
        model = payload["rom_model"]
        self.assertGreater(
            original["distinct_images_in_32_frames"],
            model["cycle_length_to_max_distinct_frames"][32],
            "the original's per frame redraw is no longer unexplained by the "
            "ROM's hold field; reopen the frame order investigation",
        )


class IdleSequenceRemakeConformance(unittest.TestCase):
    """What the remake has to reach for the original's cadence."""

    @unittest.expectedFailure
    def test_the_remake_advances_the_unit_frame_every_frame(self):
        """Missing: the runtime path that advances the field unit per frame.

        The ROM's field slot holds one of three frames for eight frames at a
        time, and the remake implements that.  The original redraws the unit
        on 183 of 191 frame transitions, so the reverse side still has to
        identify which runtime path advances the field unit's visual frame
        every tick; until it does, the remake cannot match the original's
        cadence.
        """

        payload = measurement.measure(ROOT)
        original = payload["original"]["sprite_region"]
        model = payload["rom_model"]
        self.assertGreaterEqual(
            model["cycle_length_to_max_distinct_frames"][32],
            original["distinct_images_in_32_frames"],
            "the remake's field cycle still shows fewer distinct images per "
            "cycle than the original",
        )

    @unittest.expectedFailure
    def test_the_remake_holds_no_more_than_one_frame_per_eight_frames(self):
        """Missing: the original's frame order for the field slot.

        The original's field animation has thirty different images inside
        32 frames, so its frame order is not the ROM's
        ``(0, 8), (1, 8), (2, 8), (1, 8)`` step list.  The frame order table
        has to be read out of the original before the remake can follow it.
        """

        payload = measurement.measure(ROOT)
        model = payload["rom_model"]
        self.assertGreater(
            model["cycle_length_to_max_distinct_frames"][32],
            3,
            "the remake's field cycle is no longer the ROM's three frame "
            "step list",
        )


class EveryExpectedFailureSaysWhatIsMissing(unittest.TestCase):
    """A known gap has to be written down, not just encoded as red."""

    def test_each_expected_failure_documents_the_missing_piece(self):
        gaps = IdleSequenceRemakeConformance
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
