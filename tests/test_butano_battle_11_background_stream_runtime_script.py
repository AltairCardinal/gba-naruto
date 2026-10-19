import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_battle_11_background_stream.lua"
)


class Battle11BackgroundStreamRuntimeScriptTest(
    unittest.TestCase
):
    def test_route_is_telemetry_driven_and_proves_both_chunks(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("MGBA_B11_STREAM_OUTPUT_DIR", source)
        self.assertIn("MGBA_B11_STREAM_DONE_MARKER", source)
        self.assertIn(
            "MGBA_B11_STREAM_TELEMETRY_ADDRESS",
            source,
        )
        self.assertIn("PHASE_DEPLOY_UNIT", source)
        self.assertIn("PHASE_DEPLOY_START", source)
        self.assertIn("PHASE_UNIT_SELECTION", source)
        self.assertIn("PHASE_MOVE_SELECTION", source)
        self.assertIn("PHASE_SCRIPT_BLOCKED", source)
        self.assertIn("SCRIPT_WAIT_FOR_INPUT", source)
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
            "background_chunk_index = "
            "emu:read32(telemetry_address + 96)",
            source,
        )
        self.assertIn(
            "background_chunk_count = "
            "emu:read32(telemetry_address + 100)",
            source,
        )
        self.assertIn("telemetry.battle_id == 43", source)
        self.assertIn("telemetry.battle_id == 9", source)
        self.assertIn("telemetry.battle_id == 11", source)
        self.assertIn("local function advance_fixture", source)
        self.assertIn("SAME_STATE_RETRY_FRAMES", source)
        self.assertIn("last_issue_frame", source)
        self.assertIn(
            'advance_fixture("enter-9", telemetry)',
            source,
        )
        self.assertIn(
            'advance_fixture("enter-11", telemetry)',
            source,
        )
        self.assertIn('"battle-11-chunk-0.png"', source)
        self.assertIn('"battle-11-chunk-1.png"', source)
        self.assertIn(
            '"battle-11-chunk-0-return.png"',
            source,
        )
        self.assertIn("telemetry.cursor_x < 13", source)
        self.assertIn("telemetry.cursor_x > 4", source)
        self.assertIn("telemetry.background_chunk_index == 1", source)
        self.assertIn('"observed_chunks":[0,1,0]', source)
        self.assertIn("register-samples.jsonl", source)
        self.assertIn("input-events.jsonl", source)
        self.assertIn("emu:clearKey(active_key)", source)
        self.assertNotIn("emu:removeKey", source)
        self.assertIn('emu:readRegister("pc")', source)
        self.assertIn('emu:readRegister("sp")', source)
        self.assertIn("emu:saveStateFile", source)
        self.assertIn('"status":"capture-complete"', source)


if __name__ == "__main__":
    unittest.main()
