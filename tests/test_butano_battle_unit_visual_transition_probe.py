import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_battle_unit_visual_transition_probe.lua"
)


class BattleUnitVisualTransitionProbeTest(unittest.TestCase):
    def test_probe_captures_scenario_43_to_battle_09_boundary(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("MGBA_UNIT_VISUAL_PROBE_OUTPUT_DIR", source)
        self.assertIn("MGBA_UNIT_VISUAL_PROBE_DONE_MARKER", source)
        self.assertIn("MGBA_UNIT_VISUAL_PROBE_TELEMETRY_ADDRESS", source)
        self.assertIn("scenario-43-before-select.png", source)
        self.assertIn("after-select.png", source)
        self.assertIn("emu:readRegister(\"pc\")", source)
        self.assertIn('"status":"capture-complete"', source)


if __name__ == "__main__":
    unittest.main()

