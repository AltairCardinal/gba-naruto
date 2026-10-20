#!/usr/bin/env python3
"""The original's status bar state word follows the unit, not the phase.

The original S49 status bar carries a two kanji state word next to the unit
name:

* red ``結束``  (ink 231, 24, 0)  when the unit has already finished its
  action,
* blue ``待機`` (ink 115, 33, 255) when it is still waiting.

The criterion is the **unit's** state.  The recorded original walk shows
both halves of that:

* step 14 shows the red ``結束`` (107 ink pixels) and no blue ``待機`` --
  the displayed unit is the bee that has just acted;
* step 15 shows the blue ``待機`` (150 ink pixels) and no red ``結束`` --
  the displayed unit is 漩涡鸣人, who has not acted yet;
* step 16, the move range preview screen, shows **neither** -- that screen
  has no status bar at all.

The remake used to decide the state word by screen phase, which put the red
``結束`` on the unit selection screen where the original shows the blue
``待機``.  It now decides by the unit's own state.  This gate pins the
original side by measuring the recorded frames and checks the remake on the
*declared* frame pairs of the region comparison receipts.

The measurements come from
``tools/butano/measure_s49_rule_standby_state.py``.

The reverse-side notes this rule was carried by are
``notes/battle-status-bars-export-20260730.md`` (the HUD generator that
draws the status bar) and ``notes/scenario-49-battle-14-runtime-20260720.md``
(the S49 battle 14 runtime facts the walk was taken from).
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.butano import measure_s49_rule_standby_state as measurement  # noqa: E402

SCENE = ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"


def _status_panel_function() -> str:
    source = SCENE.read_text(encoding="utf-8")
    match = re.search(
        r"void render_status_panel_text\([^)]*\)\s*\{",
        source,
    )
    if not match:
        raise AssertionError(
            "render_status_panel_text was not found in the battle runtime "
            "scene"
        )
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("render_status_panel_text has no closing brace")


class StandbyOriginalEvidence(unittest.TestCase):
    """The original's state word, measured from the recorded frames."""

    def test_the_status_bar_has_two_state_inks(self):
        payload = measurement.measure(ROOT)
        original = payload["original"]
        self.assertEqual(original["end_ink"], [231, 24, 0])
        self.assertEqual(original["standby_ink"], [115, 33, 255])

    def test_the_original_shows_both_states(self):
        payload = measurement.measure(ROOT)
        frames = payload["original"]["frames"]
        red = [name for name, ink in frames.items() if ink["end_ink_pixels"]]
        blue = [
            name for name, ink in frames.items() if ink["standby_ink_pixels"]
        ]
        self.assertTrue(red, "the original never shows the red 結束")
        self.assertTrue(blue, "the original never shows the blue 待機")

    def test_no_frame_shows_both_states_at_once(self):
        """Once the first turn has settled the state word is unambiguous.

        The very first frames of the walk are the switch itself: the red
        結束 is still fading out on the right while the blue 待機 fades in
        on the left, so both inks are visible at once.  From step 4 on the
        original never shows both.
        """

        payload = measurement.measure(ROOT)
        frames = payload["original"]["frames"]
        for name, ink in sorted(frames.items()):
            if name < "step-04":
                continue
            with self.subTest(frame=name):
                self.assertFalse(
                    ink["end_ink_pixels"] and ink["standby_ink_pixels"],
                    "a frame shows the red 結束 and the blue 待機 at the same "
                    "time",
                )

    def test_the_finished_unit_shows_the_red_end_word(self):
        payload = measurement.measure(ROOT)
        frames = payload["original"]["frames"]
        self.assertEqual(
            frames["step-14-A.png"]["end_ink_pixels"],
            107,
            "the original's step 14 no longer shows the red 結束",
        )
        self.assertEqual(frames["step-14-A.png"]["standby_ink_pixels"], 0)

    def test_the_waiting_unit_shows_the_blue_standby_word(self):
        payload = measurement.measure(ROOT)
        frames = payload["original"]["frames"]
        self.assertEqual(
            frames["step-15-A.png"]["standby_ink_pixels"],
            150,
            "the original's step 15 no longer shows the blue 待機",
        )
        self.assertEqual(frames["step-15-A.png"]["end_ink_pixels"], 0)

    def test_the_move_range_preview_screen_has_no_status_bar(self):
        payload = measurement.measure(ROOT)
        frames = payload["original"]["frames"]
        self.assertEqual(
            frames["step-16-A.png"],
            {"end_ink_pixels": 0, "standby_ink_pixels": 0},
            "the original's step 16 no longer shows a bare status bar",
        )


class StandbyRemakeConformance(unittest.TestCase):
    """The remake has to follow the unit, and it has to match the pixels."""

    def test_every_declared_pair_has_an_identical_status_bar(self):
        payload = measurement.measure(ROOT)
        pairs = payload["pairs"]
        self.assertTrue(pairs, "no declared frame pair was measured")
        for pair in pairs:
            with self.subTest(baseline=pair["baseline"]):
                self.assertEqual(
                    pair["status_bar_different_pixels"],
                    0,
                    f"the status bar of {pair['original_frame']} and "
                    f"{pair['remake_frame']} differs",
                )

    def test_every_declared_pair_agrees_on_the_state_word(self):
        payload = measurement.measure(ROOT)
        for pair in payload["pairs"]:
            with self.subTest(baseline=pair["baseline"]):
                self.assertEqual(
                    pair["remake_ink"],
                    pair["original_ink"],
                    "the remake draws a different state word than the "
                    "original",
                )

    def test_the_state_word_follows_the_unit_and_not_the_phase(self):
        body = _status_panel_function()
        self.assertIn(
            "unit->completed",
            body,
            "the status panel no longer decides the state word by the unit's "
            "own state",
        )
        self.assertNotIn(
            "battle_scene_phase::unit_selection",
            body,
            "the status panel decides the state word by screen phase again; "
            "the original's criterion is whether the unit has acted",
        )


if __name__ == "__main__":
    unittest.main()
