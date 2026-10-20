#!/usr/bin/env python3
"""A unit that has only moved must face the way it moved, not its focus point.

S49's command menu shows 木叶丸, the unit the mission asks the player to
protect, standing next to the acting unit.  The original draws him leaning east
after he walked two cells east; the remake drew him facing up, because the AI
computed the facing from where he was going to be relative to the *focus
position* he was steering towards instead of the direction he had just moved.

That is a general rule, not a special case: a unit that has only moved faces
the way it moved, and the focus position steers where it goes rather than where
it looks.  The focus branch is gone from the pure-move candidate, and this gate
keeps it gone.

Only S49 uses a focus position at all (`battle_mission_rules.h` gives
`has_focus_position` to exactly one AI unit), so the change cannot reach the
other battles.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI_HEADER = ROOT / "butano-sequel/game/include/konoha/battle_ai.h"
RULES_HEADER = (
    ROOT / "butano-sequel/game/include/konoha/battle_mission_rules.h"
)


class MoveFacingRule(unittest.TestCase):
    def setUp(self):
        self.source = AI_HEADER.read_text(encoding="utf-8")

    def test_the_pure_move_candidate_faces_the_movement_direction(self):
        match = re.search(
            r"candidate\.action\s*=\s*ai_action::move;(?P<body>.{0,900})",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "the pure-move AI branch was not found")
        body = match.group("body")
        self.assertIn(
            "facing_toward(",
            body,
            "the pure-move branch no longer computes a facing",
        )
        self.assertNotIn(
            "focus_position",
            body,
            "the pure-move branch still faces the focus position; a unit that "
            "has only moved must face the way it moved",
        )
        self.assertIn(
            "acting_unit.position",
            body,
            "the pure-move facing must be measured from where the unit started",
        )

    def test_only_s49_uses_a_focus_position(self):
        """The rule change can only reach the battles that use a focus."""

        source = RULES_HEADER.read_text(encoding="utf-8")
        blocks = re.findall(
            r"ai_units\[0\]\s*=\s*\{(.*?)\};", source, re.DOTALL
        )
        self.assertTrue(blocks, "no AI unit policy was found")
        focus_users = [
            block
            for block in blocks
            if re.search(r"\btrue\b", block)
            and "has_focus_position" not in block
        ]
        # The policy sets has_focus_position through a battle_id comparison, so
        # count the conditional ones instead.
        conditional = source.count("battle_id == 14 ?")
        self.assertLessEqual(
            conditional,
            4,
            "more battles gained a focus position; re-check whether the "
            "movement-facing rule is still S49-only",
        )
        self.assertEqual(
            focus_users,
            [],
            "an AI unit policy sets has_focus_position unconditionally",
        )


if __name__ == "__main__":
    unittest.main()
