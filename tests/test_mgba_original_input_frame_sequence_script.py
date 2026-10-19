#!/usr/bin/env python3
"""Contract tests for input-triggered original-ROM frame capture."""

from __future__ import annotations

import unittest
import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_original_input_frame_sequence.lua"


class MgbaOriginalInputFrameSequenceScriptTest(unittest.TestCase):
    def run_record_all(self, key="Right", hold=3, pre=2, count=9):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name)
        environment = os.environ.copy()
        values = {
            "INPUT_STATE": str(output / "input.ss9"),
            "INPUT_STATE_SHA256": "a" * 64,
            "OUTPUT_DIR": str(output),
            "DONE_MARKER": str(output / "done.json"),
            "KEY": key, "HOLD_FRAMES": str(hold),
            "FRAME_COUNT": str(count), "PRE_INPUT_FRAMES": str(pre),
            "RECORD_ALL": "1",
        }
        environment.update({"MGBA_ORIGINAL_INPUT_SEQUENCE_" + k: v for k, v in values.items()})
        harness = '''
        C = {GBA_KEY = {A=0,B=1,UP=2,DOWN=3,LEFT=4,RIGHT=5,L=6,R=7,START=8,SELECT=9}}
        local tick, held, loads = 0, 0, 0
        emu = {}
        function emu:loadStateFile(path) loads = loads + 1; return true end
        function emu:saveStateFile(path)
            local f=assert(io.open(path,"w")); f:write("state"); f:close(); return true
        end
        function emu:addKey(key) held = held + 1 end
        function emu:clearKey(key) held = held - 1 end
        function emu:screenshot(path)
            local f=assert(io.open(path,"w")); f:write(tick .. "," .. held); f:close()
        end
        callbacks = {}
        function callbacks:add(name, callback) self.callback = callback end
        dofile(SCRIPT_PATH)
        for i=0,30 do tick=i; callbacks.callback() end
        assert(held == 0, "key left held")
        local f=assert(io.open(os.getenv("MGBA_ORIGINAL_INPUT_SEQUENCE_OUTPUT_DIR") .. "/loads.txt", "w"))
        f:write(loads); f:close()
        '''.replace("SCRIPT_PATH", json.dumps(str(SCRIPT)))
        result = subprocess.run(["lua", "-"], input=harness, text=True,
                                capture_output=True, env=environment, check=False)
        return result, output

    def test_record_all_keeps_before_press_held_and_release_frames(self):
        result, output = self.run_record_all()
        self.assertEqual(result.returncode, 0, result.stderr)
        frames = sorted(output.glob("frame-*.png"))
        self.assertEqual(len(frames), 9)
        self.assertEqual([p.read_text() for p in frames],
                         [f"{i},{int(3 <= i <= 5)}" for i in range(9)])
        self.assertTrue((output / "final.ss9").is_file())
        self.assertTrue((output / "restored.ss9").is_file())
        self.assertEqual((output / "loads.txt").read_text(), "2")
        audit = json.loads((output / "done.json").read_text())
        self.assertTrue(audit["record_all"])
        self.assertEqual(audit["input_after_frame"], 2)

    def test_zero_input_control_records_the_same_frame_denominator(self):
        result, output = self.run_record_all(key="None")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([p.read_text() for p in sorted(output.glob("frame-*.png"))],
                         [f"{i},0" for i in range(9)])

    def test_rejects_truncated_hold_instead_of_signing_incomplete_capture(self):
        result, output = self.run_record_all(pre=7, hold=3, count=9)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input must finish before capture ends", result.stderr)
        self.assertFalse((output / "done.json").exists())

    def test_capture_loads_state_applies_one_key_then_records_each_frame(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        for token in (
            'required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE")',
            'required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_INPUT_STATE_SHA256")',
            'required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_OUTPUT_DIR")',
            'required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_DONE_MARKER")',
            'required_env("MGBA_ORIGINAL_INPUT_SEQUENCE_KEY")',
            'optional_number("MGBA_ORIGINAL_INPUT_SEQUENCE_HOLD_FRAMES", 6)',
            'optional_number("MGBA_ORIGINAL_INPUT_SEQUENCE_FRAME_COUNT", 300)',
            "emu:loadStateFile(input_state)",
            "emu:addKey",
            "emu:clearKey",
            '"/frame-%03d.png"',
            '"status":"capture-complete"',
            '"input_state_sha256"',
            '"key"',
            '"hold_frames"',
            '"frame_count"',
            "key_pressed = true\n\t\treturn",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

        for forbidden in (
            "emu:write8",
            "emu:write16",
            "emu:write32",
            "emu.memory",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
