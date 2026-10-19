#!/usr/bin/env python3
"""Wiring contract for the mGBA battle-41 presentation route."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "tools/butano/mgba_battle_41_presentation.lua"
)


class ButanoBattle41PresentationScriptTests(unittest.TestCase):
    def test_route_requires_all_five_rom_pages_before_unit_selection(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("PHASE_SCRIPT_BLOCKED = 18", source)
        self.assertIn("PHASE_UNIT_SELECTION = 1", source)
        self.assertIn("SCRIPT_WAIT_FOR_INPUT = 1", source)
        for address in (
            "0x0805B2C0",
            "0x0805B2EC",
            "0x0805B327",
            "0x0805B37E",
            "0x0805B3CB",
        ):
            self.assertIn(address, source)
        self.assertIn("script_page_count == 5", source)
        self.assertIn(
            'if press("A") then\n'
            "\t\t\tpage_ready_frame = nil",
            source,
        )
        self.assertIn(
            "unit_selection_ready_frame = frame + 3",
            source,
        )
        self.assertIn(
            'output_dir .. "/stalled-page.json"',
            source,
        )
        self.assertIn(
            '"status":"page-advance-stalled"',
            source,
        )
        self.assertIn("page_advance_deadline = frame + 30", source)
        self.assertIn('"status":"capture-complete"', source)


if __name__ == "__main__":
    unittest.main()
