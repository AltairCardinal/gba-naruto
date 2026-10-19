#!/usr/bin/env python3
"""Contract tests for consecutive original-ROM frame capture."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_original_frame_sequence.lua"


class MgbaOriginalFrameSequenceScriptTest(unittest.TestCase):
    def test_capture_is_state_driven_and_zero_input(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        for token in (
            'required_env("MGBA_ORIGINAL_SEQUENCE_INPUT_STATE")',
            'required_env("MGBA_ORIGINAL_SEQUENCE_INPUT_STATE_SHA256")',
            'required_env("MGBA_ORIGINAL_SEQUENCE_OUTPUT_DIR")',
            'required_env("MGBA_ORIGINAL_SEQUENCE_DONE_MARKER")',
            'optional_number("MGBA_ORIGINAL_SEQUENCE_FRAME_COUNT", 32)',
            "emu:loadStateFile(input_state)",
            '"/frame-%02d.png"',
            '"status":"capture-complete"',
            '"input_state_sha256"',
            '"frame_count"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

        for forbidden in (
            "emu:addKey",
            "emu:clearKey",
            "emu:write8",
            "emu:write16",
            "emu:write32",
            "emu.memory",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
