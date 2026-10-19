import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "mgba_battle_41_shared_runtime.lua"
HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_runtime_scene.h"
)
SOURCE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_runtime_scene.cpp"
)


class Scenario41SharedRuntimeScriptTest(unittest.TestCase):
    def test_route_drives_real_controller_and_captures_animation_stages(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("MGBA_S41_SHARED_OUTPUT_DIR", source)
        self.assertIn("MGBA_S41_SHARED_DONE_MARKER", source)
        self.assertIn("MGBA_S41_SHARED_TELEMETRY_ADDRESS", source)
        self.assertIn("MGBA_S41_SHARED_CONTINUE_RESULTS", source)
        self.assertIn("PHASE_DEPLOY_UNIT = 0xFFFFFFFE", source)
        self.assertIn("PHASE_ACTION_SELECTION = 6", source)
        self.assertIn("PHASE_SCRIPT_BLOCKED = 18", source)
        self.assertIn("PHASE_TRAINING = 19", source)
        self.assertIn("PHASE_TARGET_CONFIRMATION = 20", source)
        self.assertIn("PHASE_END_CONFIRMATION = 21", source)
        self.assertIn("PHASE_TARGET_PREVIEW = 22", source)
        self.assertIn("SCRIPT_WAIT_FOR_INPUT = 1", source)
        self.assertIn("ACTION_COMBO = 5", source)
        self.assertIn("ACTION_TRAIN = 8", source)
        self.assertIn("COMMAND_ABILITY = 1", source)
        self.assertRegex(
            source,
            r"telemetry\.selected_command\s*~=\s*"
            r"COMMAND_ABILITY",
        )
        self.assertIn(
            "script_phase = emu:read32(telemetry_address + 148)",
            source,
        )
        self.assertIn(
            "script_selector = emu:read32(telemetry_address + 152)",
            source,
        )
        self.assertRegex(
            source,
            r"script_command_index\s*=\s*"
            r"emu:read32\(telemetry_address \+ 156\)",
        )
        self.assertRegex(
            source,
            r"script_text_address\s*=\s*"
            r"emu:read32\(telemetry_address \+ 160\)",
        )
        self.assertIn(
            "dialogue_ready_scene_frame = telemetry.scene_frame + 2",
            source,
        )
        self.assertIn(
            "telemetry.scene_frame < dialogue_ready_scene_frame",
            source,
        )
        self.assertIn(
            "telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT",
            source,
        )
        self.assertIn("telemetry.presentation_busy == 1", source)
        self.assertIn('"movement.png"', source)
        self.assertIn('"dialogue.png"', source)
        self.assertIn('"turn-1-complete.png"', source)
        self.assertRegex(
            source,
            r"telemetry\.script_selector\s*==\s*2",
        )
        self.assertIn('"preparation-root.png"', source)
        self.assertIn('"preparation-menu-0.png"', source)
        self.assertIn('"preparation-menu-1.png"', source)
        self.assertIn('"preparation-menu-2.png"', source)
        self.assertIn('"preparation-menu-3.png"', source)
        self.assertIn('"preparation-confirmation-yes.png"', source)
        self.assertIn('"preparation-confirmation-no.png"', source)
        self.assertIn('"action-menu-0.png"', source)
        self.assertIn('"action-menu-1.png"', source)
        self.assertIn('"move-ui.png"', source)
        self.assertIn('"target.png"', source)
        self.assertRegex(
            source,
            re.compile(
                r"move_cursor_to\(\s*telemetry,\s*"
                r"telemetry\.first_active_enemy_x,\s*"
                r"telemetry\.first_active_enemy_y\s*\)\s*then\s*"
                r".*?capture_once\(\"target\",\s*"
                r"\"target\.png\"\)",
                re.DOTALL,
            ),
        )
        self.assertIn('"attack-confirmation.png"', source)
        self.assertIn('"end-confirmation.png"', source)
        self.assertIn('"facing.png"', source)
        self.assertIn('"defense-confirmation.png"', source)
        self.assertIn('"combat-start.png"', source)
        self.assertIn('"combat-impact.png"', source)
        self.assertIn('"combat-return.png"', source)
        self.assertIn('"enemy-initiated-combat.png"', source)
        self.assertIn(
            "route_round == 4 and round_stage == 0",
            source,
        )
        self.assertIn('"outcome.png"', source)
        self.assertIn('"result.png"', source)
        self.assertIn('"level-up.png"', source)
        self.assertIn('"training-before.png"', source)
        self.assertIn('"training-after.png"', source)
        self.assertIn('"training-passive.png"', source)
        self.assertIn('"result-complete.png"', source)
        self.assertIn('"/progress.json"', source)
        self.assertIn('"/combat-trace.json"', source)
        self.assertIn("presentation_trace_records", source)
        self.assertIn('"/heartbeat.json"', source)
        self.assertIn('"/heartbeat.png"', source)
        self.assertIn("result_total_experience", source)
        self.assertIn("result_hp_growth", source)
        self.assertIn("elapsed >= 60", source)
        self.assertNotIn("elapsed >= 88", source)
        self.assertIn("settle_ready_frame = frame + 2", source)
        self.assertIn("frame < settle_ready_frame", source)
        self.assertIn('"last_resolved_action_id":%d', source)
        self.assertIn('"training_action_id":%d', source)
        self.assertIn('"training_level_before":%d', source)
        self.assertIn('"training_level_after":%d', source)
        self.assertIn('"training_points_before":%d', source)
        self.assertIn('"training_points_after":%d', source)
        self.assertIn(
            "training_action_id = emu:read32(telemetry_address + 340)",
            source,
        )
        self.assertIn(
            "training_points = emu:read32(telemetry_address + 348)",
            source,
        )
        self.assertIn(
            "training_entry_kind = emu:read32(telemetry_address + 356)",
            source,
        )
        self.assertIn(
            "presentation_combat_stage = "
            "emu:read32(telemetry_address + 364)",
            source,
        )
        self.assertIn(
            "presentation_combat_stage_frame = "
            "emu:read32(telemetry_address + 368)",
            source,
        )
        self.assertIn(
            '"presentation_combat_stage":%d',
            source,
        )
        self.assertIn(
            '"presentation_combat_stage_frame":%d',
            source,
        )
        self.assertRegex(
            source,
            r"telemetry\.training_entry_kind\s*==\s*"
            r"TRAINING_SECONDARY_PASSIVE",
        )
        self.assertIn(
            "cursor_unit_id = emu:read32(telemetry_address + 304)",
            source,
        )
        self.assertIn(
            "cursor_unit_active = emu:read32(telemetry_address + 324)",
            source,
        )
        self.assertIn(
            "selected_unit_x = emu:read32(telemetry_address + 384)",
            source,
        )
        self.assertIn(
            "selected_unit_y = emu:read32(telemetry_address + 388)",
            source,
        )
        self.assertRegex(
            source,
            r"first_active_enemy_x\s*=\s*"
            r"emu:read32\(telemetry_address \+ 392\)",
        )
        self.assertRegex(
            source,
            r"first_active_enemy_y\s*=\s*"
            r"emu:read32\(telemetry_address \+ 396\)",
        )
        self.assertRegex(
            source,
            r"telemetry\.cursor_unit_id\s*~=\s*"
            r"telemetry\.selected_unit",
        )
        self.assertIn(
            "move_cursor_to(telemetry, target_x, target_y)",
            source,
        )
        self.assertIn(
            "drive_round(telemetry, 1, 4, 10, false)",
            source,
        )
        self.assertIn(
            "drive_round(telemetry, 2, 4, 7, false)",
            source,
        )
        self.assertIn(
            "drive_round(telemetry, 3, 5, 6, false)",
            source,
        )
        self.assertIn(
            "drive_round(telemetry, 4, "
            "telemetry.first_active_enemy_x, "
            "telemetry.first_active_enemy_y + 1, true)",
            source,
        )
        self.assertRegex(
            source,
            r"round_stage == 0\s+and\s+"
            r"telemetry\.phase == PHASE_UNIT_SELECTION",
        )
        self.assertRegex(
            source,
            r"round_stage == 1\s+and\s+"
            r"telemetry\.phase == PHASE_UNIT_SELECTION",
        )
        self.assertRegex(
            source,
            r"round_stage == 2\s+and\s+"
            r"telemetry\.phase == PHASE_MOVE_SELECTION",
        )
        self.assertRegex(
            source,
            re.compile(
                r"telemetry\.phase\s*==\s*"
                r"PHASE_DEFENSE_DECISION.*?"
                r'press\("Down"\)',
                re.DOTALL,
            ),
        )
        self.assertIn(
            "finish_route_round()",
            source,
        )
        self.assertRegex(
            source,
            r"attack\s+and\s+round_stage\s*>=\s*5\s+and\s+"
            r"telemetry\.phase\s*==\s*PHASE_OUTCOME",
        )
        self.assertIn(
            "assert(telemetry.result_round_bonus_experience == 0)",
            source,
        )
        self.assertIn(
            "assert(telemetry.result_total_experience == 150)",
            source,
        )
        self.assertIn(
            "assert(telemetry.result_experience_after == 0)",
            source,
        )
        self.assertNotIn("MGBA_S41_SHARED_CONSUME_TOOL37", source)
        self.assertNotIn("ACTION_TOOL = 37", source)
        self.assertIn('"status":"capture-complete"', source)

    def test_runtime_telemetry_exposes_live_actor_and_enemy_positions(self):
        header = HEADER.read_text(encoding="utf-8")
        source = SOURCE.read_text(encoding="utf-8")

        for field in (
            "selected_unit_x",
            "selected_unit_y",
            "first_active_enemy_x",
            "first_active_enemy_y",
        ):
            with self.subTest(field=field):
                self.assertIn(f"std::uint32_t {field} = 0;", header)
                self.assertIn(f"output.{field}", source)

    def test_results_can_preserve_the_level_up_training_point(self):
        source = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_S41_SHARED_SKIP_TRAINING",
            "if skip_training then",
            "assert(campaign.naruto_training_points == 1)",
            "assert(campaign.naruto_action_8_level == 0)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
