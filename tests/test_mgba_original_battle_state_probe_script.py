#!/usr/bin/env python3
"""Contract tests for the read-only original-ROM battle state probe."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_original_battle_state_probe.lua"


class MgbaOriginalBattleStateProbeScriptTest(unittest.TestCase):
    def test_probe_reads_units_without_mutating_or_driving_the_game(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        for token in (
            'required_env("MGBA_ORIGINAL_BATTLE_PROBE_INPUT_STATE")',
            'required_env("MGBA_ORIGINAL_BATTLE_PROBE_INPUT_STATE_SHA256")',
            'required_env("MGBA_ORIGINAL_BATTLE_PROBE_OUTPUT")',
            'required_env("MGBA_ORIGINAL_BATTLE_PROBE_DONE_MARKER")',
            "emu:loadStateFile(input_state)",
            "0x020240C0",
            "0x01D4",
            "0x02026804",
            '"character_id"',
            '"affiliation"',
            '"current_hp"',
            '"maximum_hp"',
            '"position_x"',
            '"position_y"',
            '"state_word"',
            '"status":"probe-complete"',
            '"input_state_sha256"',
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
