from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_battle_effect_dispatcher_tracer.lua"


class BattleEffectDispatcherTracerTests(unittest.TestCase):
    def test_uses_nonblocking_callbacks_and_explicit_state_restore(self):
        text = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('required_env("TRACER_INPUT_STATE")', text)
        self.assertIn("emu:loadStateFile(input_state)", text)
        self.assertIn("frame >= frame_limit", text)
        self.assertNotIn("while not complete do emu:frameAdvance()", text)


if __name__ == "__main__":
    unittest.main()
