#!/usr/bin/env python3
"""Wiring contract for the second battle-presentation runtime sample."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/butano/mgba_battle_43_presentation.lua"


class ButanoBattle43PresentationScriptTests(unittest.TestCase):
    def test_route_validates_structured_window_and_portraits_before_play(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("TARGET_BATTLE_ID = 43", source)
        self.assertIn("PHASE_SCRIPT_BLOCKED = 18", source)
        self.assertIn("PHASE_UNIT_SELECTION = 1", source)
        for field in (
            "script_message_window_visible",
            "portrait_0_visible",
            "portrait_0_focused",
            "portrait_0_id",
            "portrait_0_expression",
            "portrait_1_visible",
            "portrait_1_focused",
            "portrait_1_id",
            "portrait_1_expression",
        ):
            self.assertIn(field, source)
        for address in (
            "0x0805B6AB",
            "0x0805B6EC",
            "0x0805B727",
            "0x0805B774",
            "0x0805B7C3",
        ):
            self.assertIn(address, source)
        self.assertIn(
            "script_page_count == #expected_pages",
            source,
        )
        self.assertIn("page_ready_frame = frame + 8", source)
        self.assertIn("page_press_frame = frame + 2", source)
        self.assertLess(
            source.index('emu:screenshot(\n\t\t\t\toutput_dir .. "/page-"'),
            source.index('if page_press_frame and frame >= page_press_frame'),
        )
        self.assertIn('"status":"capture-complete"', source)


if __name__ == "__main__":
    unittest.main()
