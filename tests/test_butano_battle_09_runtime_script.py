import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_battle_09_multi_unit.lua"


class Battle09RuntimeScriptTest(unittest.TestCase):
    def test_route_captures_three_players_five_enemies_and_round_two(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("MGBA_B09_OUTPUT_DIR", source)
        self.assertIn("MGBA_B09_DONE_MARKER", source)
        self.assertIn("MGBA_B09_TELEMETRY_ADDRESS", source)
        self.assertIn('C.GBA_KEY.SELECT', source)
        self.assertIn('{ 30, "Select" }', source)
        self.assertIn("PHASE_UNIT_SELECTION", source)
        self.assertIn("PHASE_MOVE_SELECTION", source)
        self.assertIn("PHASE_COMMAND_SELECTION", source)
        self.assertIn("PHASE_ENEMY_TURN", source)
        self.assertIn("COMMAND_END_ACTION", source)
        for screenshot in (
            "formation-3v5.png",
            "player-1-selected.png",
            "player-2-selected.png",
            "player-3-selected.png",
            "enemy-phase-start.png",
            "enemy-done-1-of-5.png",
            "enemy-done-2-of-5.png",
            "enemy-done-3-of-5.png",
            "enemy-done-4-of-5.png",
            "round-2-player.png",
        ):
            with self.subTest(screenshot=screenshot):
                self.assertIn(f'"{screenshot}"', source)

        self.assertIn("register-samples.jsonl", source)
        self.assertIn('emu:readRegister("pc")', source)
        self.assertIn('emu:readRegister("lr")', source)
        self.assertIn('emu:readRegister("sp")', source)
        self.assertIn("emu:read16(0x04000130)", source)
        self.assertIn("read_telemetry()", source)
        self.assertIn("telemetry.cursor_x", source)
        self.assertIn("telemetry.cursor_y", source)
        self.assertIn("telemetry.last_control_error", source)
        self.assertIn("telemetry.last_player_error", source)
        self.assertIn("telemetry.render_stage", source)
        self.assertIn("telemetry.presentation_busy", source)
        self.assertIn("telemetry.round >= 2", source)
        self.assertIn("telemetry.enemy_completed", source)
        self.assertIn('"expected_active_units":8', source)
        self.assertIn('"expected_round":2', source)
        self.assertIn("emu:saveStateFile", source)
        self.assertIn('"status":"capture-complete"', source)


if __name__ == "__main__":
    unittest.main()
