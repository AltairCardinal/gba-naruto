#!/usr/bin/env python3
"""Contract tests for scenario-49 original-ROM UI boundary capture."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/butano/mgba_original_s49_ui_boundaries.lua"


class MgbaOriginalS49UiBoundariesScriptTest(unittest.TestCase):
    def test_capture_uses_only_loaded_state_and_scripted_keys(self):
        self.assertTrue(SCRIPT.is_file())
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            'required_env("MGBA_ORIGINAL_S49_INPUT_STATE")',
            'required_env("MGBA_ORIGINAL_S49_INPUT_STATE_SHA256")',
            'required_env("MGBA_ORIGINAL_S49_OUTPUT_DIR")',
            'required_env("MGBA_ORIGINAL_S49_DONE_MARKER")',
            'required_env("MGBA_ORIGINAL_S49_KEY_SEQUENCE")',
            "emu:loadStateFile(input_state)",
            "emu:addKey",
            "emu:clearKey",
            '"/step-00-base.png"',
            '"/step-%02d-%s.png"',
            '"/step-%02d-%s.ss9"',
            '"zero_input_frames"',
            '"settle_frames"',
            '"status":"capture-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        for forbidden in (
            "emu:write8",
            "emu:write16",
            "emu:write32",
            "emu.memory",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
