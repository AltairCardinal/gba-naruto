from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/mgba_battle_ai_action_observer.lua"


class BattleAiActionObserverScriptTests(unittest.TestCase):
    def test_observer_reads_the_action_only_at_the_runtime_copy_breakpoint(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("0x0807A22C", source)
        self.assertIn("runtime_pointer + 0x770", source)
        self.assertIn('emu:readRegister("r7")', source)
        self.assertIn('emu:readRegister("r1")', source)
        self.assertIn('os.getenv("AI_OBSERVER_INPUT_STATE")', source)
        self.assertIn('os.getenv("AI_OBSERVER_SCRIPT_SHA256")', source)
        self.assertIn('os.getenv("AI_OBSERVER_SKIP_ACTION_IDS")', source)
        self.assertIn('os.getenv("AI_OBSERVER_INPUT_SCHEDULE")', source)
        self.assertIn('"events":', source)
        self.assertIn("input_events", source)
        self.assertNotIn("frame == 60", source)
        self.assertNotIn("frame == 68", source)
        self.assertNotIn("emu:write", source)
        self.assertNotIn("os.exit", source)


if __name__ == "__main__":
    unittest.main()
