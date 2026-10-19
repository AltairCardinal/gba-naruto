import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_scenario_43_runtime.lua"


class Scenario43RuntimeScriptTest(unittest.TestCase):
    def test_route_captures_formation_clone_enemy_sequence_and_round_two(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("MGBA_S43_OUTPUT_DIR", source)
        self.assertIn("MGBA_S43_DONE_MARKER", source)
        self.assertIn("MGBA_S43_TELEMETRY_ADDRESS", source)
        self.assertIn(
            "PHASE_DEPLOY_UNIT = 0xFFFFFFFE",
            source,
        )
        self.assertIn(
            "PHASE_DEPLOY_START = 0xFFFFFFFD",
            source,
        )
        self.assertIn("drive_deployment(telemetry)", source)
        self.assertIn(
            "deployment_signature(telemetry)",
            source,
        )
        self.assertIn('"deployment-unit-1.png"', source)
        self.assertIn('"deployment-start.png"', source)
        self.assertIn('C.GBA_KEY.SELECT', source)
        self.assertIn('{ 30, "Select" }', source)
        self.assertIn('"formation.png"', source)
        self.assertIn('"clone-created.png"', source)
        self.assertIn('"enemy-unit-1-complete.png"', source)
        self.assertIn('"enemy-unit-2-complete.png"', source)
        self.assertIn('"enemy-unit-3-complete.png"', source)
        self.assertIn('"round-2-player.png"', source)
        self.assertIn('{ 600, "A" }', source)
        self.assertIn('{ 660, "A" }', source)
        self.assertIn("read_telemetry()", source)
        self.assertIn("telemetry.active_units == 5", source)
        self.assertIn("telemetry.enemy_completed", source)
        self.assertIn("telemetry.presentation_busy == 0", source)
        self.assertIn("telemetry.round >= 2", source)
        self.assertIn("due = frame + 3", source)
        self.assertIn("#screenshot_queue == 0", source)
        self.assertIn(
            "telemetry.round >= 2 and\n"
            "\t\t\ttelemetry.presentation_busy == 1",
            source,
        )
        signature_source = source[
            source.index("local function signature"):
            source.index("local function append_sample")
        ]
        self.assertNotIn("telemetry.scene_frame", signature_source)
        self.assertIn('"actual_active_units":%d', source)
        self.assertIn('"actual_round":%d', source)
        self.assertIn("emu:saveStateFile", source)
        self.assertIn('emu:readRegister("pc")', source)
        self.assertIn('emu:readRegister("lr")', source)
        self.assertIn("register-samples.jsonl", source)
        self.assertIn('"status":"capture-complete"', source)


if __name__ == "__main__":
    unittest.main()
