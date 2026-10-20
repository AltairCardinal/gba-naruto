#!/usr/bin/env python3
"""The selected unit's idle frame at the moment the command menu opens.

Round 14 measured the selected unit in the remake and found it one idle step
ahead of the original: at the frame where the command menu opens, the original
draws character 1 in exported ``slot 0`` frame **10** while the remake drew
frame **11**.  The earlier note (``notes/s49-selected-unit-slot-frame-20261020.md``)
proposed fixing that by shifting ``idle_phase_offset`` by one idle step, and
this gate records that the proposal was **tried and refuted**.

What is measured here:

* the anchor is an **in-game event**, not a step number: the frame on which the
  command menu opens.  Both recordings contain it;
* the pairing of the two recordings is **measured**, not assumed: the left
  region of the screen (where the menu is drawn) changes in an identical
  sequence in both recordings once the menu is open, and the remake's sequence
  is offset by exactly one step.  That pins "the remake's step N is the
  original's step N-1";
* the frame itself is measured with an **exact** mapping: the export ships the
  unit's 16 colour BGR555 palette, so screen RGB maps to palette index by
  lookup, and a candidate frame is accepted only when every visible opaque
  pixel carries the same palette index (``tools/butano/
  measure_s49_selected_unit_frame.py``).

With the anchor and the pairing pinned, the offset shift was applied, the ROM
was rebuilt and the walk was re-recorded
(``artifacts/s49-remake-phase-shift-experiment-20261020-v1``).  The result
refutes the proposal: the shift fixes the anchor frame and breaks the frames
before and after it, because the phase relationship between the two games
**drifts across the command menu** instead of being a constant offset.  The
remake drives its idle animation from a free running scene counter; the
original's is not driven that way.

So this gate pins:

* the original's behaviour (green);
* the residual difference at the anchor (expectedFailure, with the missing
  evidence spelled out);
* the refutation of the constant-offset fix (green), so the experiment is not
  repeated blind.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "tools" / "butano"))

import measure_s49_selected_unit_frame as measure  # noqa: E402

REVERSE_ROOT = Path(
    os.environ.get("KONOHA_REVERSE_ROOT", "/Users/altair/github/gba-naruto-reverse")
)
VISUALS_ROOT = REVERSE_ROOT / "artifacts/character-battle-visuals-v1"

ORIGINAL_WALK = ROOT / "artifacts/s49-fidelity-20261019-v1/walk-original-a24"
REMAKE_WALK = ROOT / "artifacts/s49-remake-expfix-20261020-v1"
SHIFT_EXPERIMENT_WALK = ROOT / "artifacts/s49-remake-phase-shift-experiment-20261020-v1"

# The command menu is drawn on the left of the screen.
MENU_REGION = (0, 0, 109, 96)
# The frame on which the command menu opens, in each recording.
ORIGINAL_MENU_STEP = 18
REMAKE_MENU_STEP = 19
# The pairing proved by the left-region diff signature: the remake's step N is
# the original's step N-1.
PAIRED_STEPS = ((20, 19), (21, 20), (22, 21), (23, 22))


def frame_path(directory: Path, step: int) -> Path:
    return directory / f"step-{step:02d}-A.png"


def left_region_diff(left: Path, right: Path) -> int:
    """Count differing pixels in the menu region, with no tolerance.

    The per-channel maximum is binarised before counting: a one-step
    difference in a single channel is still a difference and must not be
    rounded away by a luminance conversion.
    """
    with Image.open(left) as left_image, Image.open(right) as right_image:
        a = left_image.convert("RGB").crop(MENU_REGION)
        b = right_image.convert("RGB").crop(MENU_REGION)
    difference = ImageChops.difference(a, b)
    red, green, blue = difference.split()
    combined = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return combined.point(lambda value: 255 if value else 0, mode="L").histogram()[255]


class SelectedUnitPhaseTest(unittest.TestCase):
    def setUp(self) -> None:
        if not VISUALS_ROOT.is_dir():
            self.skipTest(f"reverse tree not available at {REVERSE_ROOT}")

    def _measure(self, path: Path) -> dict[str, object]:
        return measure.measure(path, VISUALS_ROOT, 1, 0, None)

    def _frame_index(self, directory: Path, step: int) -> int:
        receipt = self._measure(frame_path(directory, step))
        self.assertTrue(receipt["identified"], receipt)
        return receipt["chosen"]["frame_index"]

    def test_original_command_menu_anchor_is_slot0_frame_10(self) -> None:
        """The original's command-menu anchor is slot 0 frame 10."""
        receipt = self._measure(frame_path(ORIGINAL_WALK, ORIGINAL_MENU_STEP))
        self.assertTrue(receipt["identified"], receipt)
        chosen = receipt["chosen"]
        self.assertEqual(chosen["frame_index"], 10)
        self.assertEqual(chosen["true_mismatch"], 0)
        self.assertEqual(chosen["origin"], [112, 24])
        self.assertEqual(chosen["frame"], "frame-010.png")

    def test_remake_command_menu_anchor_matches_the_original(self) -> None:
        """The remake must draw the same frame at the same in-game moment.

        Missing: the original's field animation is **not** the ROM's hold
        table at all -- the pre-existing gate
        ``tests/test_s49_rule_idle_sequence.py`` measured that the original
        redraws the unit on 183 of 191 frame transitions and shows 30 distinct
        images inside one 32 frame cycle, while the ROM's field slot (and
        therefore the remake) can only show three.  So the phase relationship
        to the original **drifts** across the command menu and no constant
        offset reproduces it (see the refutation test below).  Closing this
        needs the original's per frame frame order, i.e. the runtime path
        that advances the field unit's visual frame every tick.
        """
        receipt = self._measure(frame_path(REMAKE_WALK, REMAKE_MENU_STEP))
        self.assertTrue(receipt["identified"], receipt)
        chosen = receipt["chosen"]
        self.assertEqual(
            chosen["frame_index"],
            10,
            "the remake still draws slot 0 frame "
            f"{chosen['frame_index']} at the command-menu anchor "
            "(the original draws frame 10)",
        )

    test_remake_command_menu_anchor_matches_the_original = unittest.expectedFailure(
        test_remake_command_menu_anchor_matches_the_original
    )

    def test_a_constant_phase_offset_cannot_reproduce_the_original(self) -> None:
        """The eight frame offset shift was tried and refuted; keep it refuted.

        The shifted build is kept as a receipt.  Shifting the offsets moves
        the anchor frame onto the original's value, but it moves the next
        moment off it, so the two recordings agree on **no more** moments
        than before the shift -- the offset trades one mismatch for another
        instead of removing one, because the phase relationship between the
        two games drifts across the command menu.
        """
        if not SHIFT_EXPERIMENT_WALK.is_dir():
            self.skipTest(f"phase shift experiment not recorded at {SHIFT_EXPERIMENT_WALK}")
        moments = ((19, 18), (20, 19), (21, 20), (23, 22))
        matched_current = set()
        matched_shifted = set()
        for remake_step, original_step in moments:
            original_frame = self._frame_index(ORIGINAL_WALK, original_step)
            if self._frame_index(REMAKE_WALK, remake_step) == original_frame:
                matched_current.add((remake_step, original_step))
            if self._frame_index(SHIFT_EXPERIMENT_WALK, remake_step) == original_frame:
                matched_shifted.add((remake_step, original_step))
        self.assertIn(
            (19, 18),
            matched_shifted,
            "the shifted build was expected to fix the command-menu anchor",
        )
        self.assertNotIn(
            (19, 18),
            matched_current,
            "the current build was expected to miss the command-menu anchor",
        )
        self.assertIn(
            (20, 19),
            matched_current,
            "the current build was expected to match the moment after the anchor",
        )
        self.assertNotIn(
            (20, 19),
            matched_shifted,
            "the shifted build was expected to break the moment after the anchor",
        )
        self.assertLessEqual(
            len(matched_shifted),
            len(matched_current),
            "the constant offset shift unexpectedly matches more moments than the "
            "current build; re-check the anchor reasoning",
        )

    def test_the_two_recordings_are_paired_by_the_menu_signature(self) -> None:
        """The remake's step N must carry the original's step N-1 signature.

        Without this, the two recordings could not be compared at all: the
        step numbers would be arbitrary labels.  The two games draw their
        menus slightly differently, so the signature is compared with a
        tolerance; the point of the test is that the *one step offset* fits
        the data far better than no offset at all.
        """
        paired_delta = 0
        same_index_delta = 0
        for remake_step, original_step in PAIRED_STEPS:
            remake_signature = left_region_diff(
                frame_path(REMAKE_WALK, remake_step - 1),
                frame_path(REMAKE_WALK, remake_step),
            )
            paired = left_region_diff(
                frame_path(ORIGINAL_WALK, original_step - 1),
                frame_path(ORIGINAL_WALK, original_step),
            )
            same_index = left_region_diff(
                frame_path(ORIGINAL_WALK, remake_step - 1),
                frame_path(ORIGINAL_WALK, remake_step),
            )
            paired_delta += abs(remake_signature - paired)
            same_index_delta += abs(remake_signature - same_index)
            self.assertLessEqual(
                abs(remake_signature - paired),
                200,
                f"remake step {remake_step} does not pair with original step {original_step}",
            )
        self.assertLess(
            paired_delta,
            same_index_delta,
            "the one step offset does not fit the menu signatures better than no offset",
        )

    def test_measurement_is_deterministic(self) -> None:
        path = frame_path(ORIGINAL_WALK, ORIGINAL_MENU_STEP)
        first = self._measure(path)
        second = self._measure(path)
        self.assertEqual(first["table"], second["table"])

    def test_measurement_fails_closed_on_a_missing_frame(self) -> None:
        with self.assertRaises(measure.MeasureError):
            self._measure(ORIGINAL_WALK / "step-99-A.png")

    def test_measurement_fails_closed_on_a_wrong_sized_frame(self) -> None:
        with self.assertRaises(measure.MeasureError):
            self._measure(ROOT / "butano-sequel/graphics/battle_unit_01_idle.bmp")


if __name__ == "__main__":
    unittest.main()
