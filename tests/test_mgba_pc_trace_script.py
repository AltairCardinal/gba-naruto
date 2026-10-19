#!/usr/bin/env python3
"""Contract tests for the per-frame PC trace script."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/butano/mgba_pc_trace.lua"


class MgbaPcTraceScriptTest(unittest.TestCase):
    def test_samples_pc_per_frame_and_writes_a_receipt(self):
        self.assertTrue(SCRIPT.is_file())
        script = SCRIPT.read_text(encoding="utf-8")
        for token in (
            'required_env("MGBA_PC_TRACE_INPUT_STATE")',
            'required_env("MGBA_PC_TRACE_OUTPUT_DIR")',
            'required_env("MGBA_PC_TRACE_DONE_MARKER")',
            "emu:loadStateFile(input_state)",
            'emu:readRegister("pc")',
            'emu:addKey(key_codes[input_key])',
            "emu:clearKey(key_codes[input_key])",
            '"/pc-trace.txt"',
            '"status":"pc-trace-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_trace_script_never_writes_emulator_memory(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("emu:write8", "emu:write16", "emu:write32", "emu.memory"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
