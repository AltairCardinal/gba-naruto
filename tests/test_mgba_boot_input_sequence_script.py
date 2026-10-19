#!/usr/bin/env python3
"""Contract tests for the power-on boot input-sequence capture script."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/butano/mgba_boot_input_sequence.lua"


class MgbaBootInputSequenceScriptTest(unittest.TestCase):
    def test_boots_from_power_on_and_saves_every_branch_point(self):
        self.assertTrue(SCRIPT.is_file())
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            'required_env("MGBA_BOOT_SEQUENCE_OUTPUT_DIR")',
            'required_env("MGBA_BOOT_SEQUENCE_DONE_MARKER")',
            'required_env("MGBA_BOOT_SEQUENCE_ROM_SHA256")',
            'required_env("MGBA_BOOT_SEQUENCE_KEY_SEQUENCE")',
            "emu:screenshot",
            "emu:addKey",
            "emu:clearKey",
            "emu:saveStateFile",
            '"/step-00-base.png"',
            '"/step-00-base.ss9"',
            '"/step-%02d-%s.png"',
            '"/step-%02d-%s.ss9"',
            '"status":"capture-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_never_touches_emulator_memory(self):
        script = SCRIPT.read_text(encoding="utf-8")
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
