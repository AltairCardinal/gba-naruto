import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_battle_32_dynamic_deployment.lua"
)


class Battle32DynamicDeploymentRuntimeScriptTest(
    unittest.TestCase
):
    def test_route_proves_injected_placeholder_roster_and_round_two(
        self,
    ):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("MGBA_B32_DEPLOY_OUTPUT_DIR", source)
        self.assertIn("MGBA_B32_DEPLOY_DONE_MARKER", source)
        self.assertIn(
            "MGBA_B32_DEPLOY_TELEMETRY_ADDRESS",
            source,
        )
        self.assertIn(
            "selected_character_id =",
            source,
        )
        self.assertIn(
            "emu:read32(telemetry_address + 72)",
            source,
        )
        self.assertIn(
            "render_stage = "
            "emu:read32(telemetry_address + 64)",
            source,
        )
        self.assertIn("emu:read16(0x04000200)", source)
        self.assertIn("emu:read16(0x04000202)", source)
        self.assertIn("emu:read32(0x04000208)", source)
        self.assertIn("emu:read32(0x03007FF8)", source)
        self.assertIn(
            "ai_secondary_planned = "
            "emu:read32(telemetry_address + 228)",
            source,
        )
        self.assertIn(
            "ai_defense_action_id = "
            "emu:read32(telemetry_address + 236)",
            source,
        )
        self.assertIn("telemetry.battle_id == 41", source)
        self.assertIn("telemetry.battle_id == 43", source)
        self.assertIn("telemetry.battle_id == 9", source)
        self.assertIn("telemetry.battle_id == 11", source)
        self.assertIn("telemetry.battle_id == 32", source)
        self.assertIn(
            "expected_deployment = { 1, 2, 3, 12, 35, 1 }",
            source,
        )
        self.assertIn("observed_deployment", source)
        self.assertIn("observed_ai_substitution", source)
        self.assertIn(
            "assert(observed_ai_substitution)",
            source,
        )
        self.assertIn("COMMAND_END_ACTION", source)
        self.assertIn("PHASE_SCRIPT_BLOCKED = 18", source)
        self.assertIn("SCRIPT_WAIT_FOR_INPUT = 1", source)
        self.assertIn(
            "script_phase = "
            "emu:read32(telemetry_address + 148)",
            source,
        )
        self.assertIn(
            "script_command_index = "
            "emu:read32(telemetry_address + 156)",
            source,
        )
        self.assertIn(
            "telemetry.script_phase == "
            "SCRIPT_WAIT_FOR_INPUT",
            source,
        )
        self.assertIn(
            'issue_key("A", telemetry, true)',
            source,
        )
        self.assertIn("telemetry.round >= 2", source)
        self.assertIn('"deployment":[1,2,3,12,35,1]', source)
        self.assertIn('"status":"capture-complete"', source)
        self.assertIn("next_bootstrap_select_frame", source)
        self.assertIn(
            "frame >= next_bootstrap_select_frame",
            source,
        )
        self.assertIn("emu:clearKey(active_key)", source)
        self.assertNotIn("emu:removeKey", source)


if __name__ == "__main__":
    unittest.main()
