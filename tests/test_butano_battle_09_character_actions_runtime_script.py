import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "tools/butano"
    / "mgba_battle_09_character_actions.lua"
)


class Battle09CharacterActionsRuntimeScriptTest(unittest.TestCase):
    def test_route_is_state_driven_and_proves_distinct_character_actions(self):
        self.assertTrue(SCRIPT.is_file())
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("MGBA_B09_ACTION_OUTPUT_DIR", source)
        self.assertIn("MGBA_B09_ACTION_DONE_MARKER", source)
        self.assertIn("MGBA_B09_ACTION_TELEMETRY_ADDRESS", source)
        self.assertIn("PHASE_ACTION_SELECTION", source)
        self.assertIn("PHASE_COMBINATION_DECISION = 7", source)
        self.assertIn("PHASE_TARGET_SELECTION", source)
        self.assertIn("PHASE_SCRIPT_BLOCKED = 18", source)
        self.assertIn("SCRIPT_WAIT_FOR_INPUT = 1", source)
        self.assertIn(
            "script_phase = emu:read32(telemetry_address + 148)",
            source,
        )
        self.assertIn(
            "telemetry.script_phase == SCRIPT_WAIT_FOR_INPUT",
            source,
        )
        self.assertIn(
            "PHASE_DEPLOY_UNIT = 0xFFFFFFFE",
            source,
        )
        self.assertIn(
            "PHASE_DEPLOY_START = 0xFFFFFFFD",
            source,
        )
        self.assertIn(
            "telemetry.phase == PHASE_DEPLOY_UNIT or",
            source,
        )
        self.assertIn(
            'local initial_press = { frame = 30, key = "A" }',
            source,
        )
        self.assertIn(
            "if frame == initial_press.frame then",
            source,
        )
        self.assertIn("telemetry.battle_id == 41", source)
        self.assertIn('"deployment-unit-1.png"', source)
        self.assertIn('"deployment-start.png"', source)
        self.assertIn("ACTION_CLONE = 1", source)
        self.assertIn("ACTION_TELEPORT = 2", source)
        self.assertIn(
            "local sasuke_fire_standalone_selected = false",
            source,
        )
        self.assertIn(
            "telemetry.phase == PHASE_COMBINATION_DECISION",
            source,
        )
        self.assertIn(
            'issue_key("Down", telemetry)',
            source,
        )
        self.assertIn(
            'issue_key("A", telemetry)',
            source,
        )
        self.assertIn(
            "selected_character_id = "
            "emu:read32(telemetry_address + 72)",
            source,
        )
        self.assertIn(
            "action_count = emu:read32(telemetry_address + 76)",
            source,
        )
        self.assertIn(
            "selected_action_level = emu:read32(telemetry_address + 332)",
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
            "cursor_unit_id = emu:read32(telemetry_address + 304)",
            source,
        )
        self.assertIn(
            "cursor_unit_active = "
            "emu:read32(telemetry_address + 324)",
            source,
        )
        self.assertIn("FIRE_STAGING_X = 7", source)
        self.assertIn("FIRE_STAGING_Y = 14", source)
        self.assertIn("FIRE_ATTACK_X = 7", source)
        self.assertIn("FIRE_ATTACK_Y = 11", source)
        self.assertIn("ACTION_05_SECOND_STAGING_X = 7", source)
        self.assertIn("ACTION_05_SECOND_STAGING_Y = 11", source)
        self.assertIn("ACTION_05_ATTACK_X = 7", source)
        self.assertIn("ACTION_05_ATTACK_Y = 10", source)
        self.assertIn("ACTION_05_EXECUTION_ROUND = 3", source)
        self.assertIn("sasuke_action_05_round_2_staged", source)
        self.assertIn("drive_action_05_adjacent_target", source)
        self.assertIn("requested_attack_y", source)
        self.assertIn("FIRST_ENEMY_UNIT_ID = 4", source)
        self.assertIn("LAST_ENEMY_UNIT_ID = 8", source)
        self.assertIn(
            "telemetry.cursor_unit_id >= FIRST_ENEMY_UNIT_ID",
            source,
        )
        self.assertIn(
            "telemetry.cursor_unit_id <= LAST_ENEMY_UNIT_ID",
            source,
        )
        self.assertIn("if telemetry.round >= 2 then", source)
        self.assertIn("if execute_sasuke_combat then", source)
        self.assertIn(
            "(execute_sasuke_action_05 or execute_sasuke_bomb) and\n"
            "\t\t\t\ttelemetry.round < ACTION_05_EXECUTION_ROUND",
            source,
        )
        self.assertIn(
            "if execute_sasuke_action_05 or execute_sasuke_bomb then",
            source,
        )
        self.assertIn(
            "if execute_sasuke_combat and\n"
            "\t\t\t\ttelemetry.selected_unit == 2 and",
            source,
        )
        self.assertIn('"script_phase":%d', source)
        self.assertIn(
            "telemetry.scene_frame >=\n"
            "\t\t\t\t\tlast_release_scene_frame and",
            source,
        )
        self.assertIn(
            "telemetry.phase == PHASE_SCRIPT_BLOCKED or",
            source,
        )
        self.assertIn(
            "action_index = emu:read32(telemetry_address + 80)",
            source,
        )
        self.assertIn(
            "selected_action_id = "
            "emu:read32(telemetry_address + 84)",
            source,
        )
        self.assertIn(
            "selected_action_error = "
            "emu:read32(telemetry_address + 88)",
            source,
        )
        self.assertIn(
            "last_resolved_action_id = "
            "emu:read32(telemetry_address + 92)",
            source,
        )
        self.assertIn(
            "selected_action_kind = "
            "emu:read32(telemetry_address + 104)",
            source,
        )
        self.assertIn(
            "selected_action_tool_slot = "
            "emu:read32(telemetry_address + 108)",
            source,
        )
        self.assertIn(
            "presentation_resource_resolved = "
            "emu:read32(telemetry_address + 208)",
            source,
        )
        self.assertIn(
            "presentation_resource_type = "
            "emu:read32(telemetry_address + 212)",
            source,
        )
        self.assertIn(
            "presentation_resource_amount = "
            "emu:read32(telemetry_address + 216)",
            source,
        )
        self.assertIn(
            "presentation_resource_hp_delta = "
            "signed32(emu:read32(telemetry_address + 220))",
            source,
        )
        self.assertIn(
            "presentation_resource_chakra_delta = "
            "signed32(emu:read32(telemetry_address + 224))",
            source,
        )
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
        self.assertIn(
            "MGBA_B09_ACTION_REQUIRE_AI_RESOURCE",
            source,
        )
        self.assertIn(
            "MGBA_B09_ACTION_EXECUTE_SASUKE_ACTION_05",
            source,
        )
        self.assertIn(
            "MGBA_B09_ACTION_EXECUTE_SASUKE_BOMB",
            source,
        )
        self.assertIn(
            "presentation_combat_resource = "
            "emu:read32(telemetry_address + 380)",
            source,
        )
        self.assertIn(
            "COMBAT_RESOURCE_ACTION_05_DUST = 4",
            source,
        )
        self.assertIn(
            "COMBAT_RESOURCE_NINJA_TOOL_BOMB_PROJECTILE = 7",
            source,
        )
        self.assertIn(
            "COMBAT_RESOURCE_NINJA_TOOL_BOMB_SMOKE = 8",
            source,
        )
        self.assertIn("ACTION_BOMB = 49", source)
        for frame in (1, 20, 58):
            self.assertRegex(
                source,
                re.compile(
                    rf'key = "sasuke-action-05-dust-{frame:02d}",\s+'
                    rf'name = "sasuke-action-05-dust-{frame:02d}\.png",\s+'
                    rf"due_frame = {frame},"
                ),
            )
        self.assertRegex(
            source,
            re.compile(
                r'key = "sasuke-action-05-reentry-60",\s+'
                r'name = "sasuke-action-05-reentry-60\.png",\s+'
                r"due_frame = 61,"
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r'key = "sasuke-action-05-impact-00",\s+'
                r'name = "sasuke-action-05-impact-00\.png",\s+'
                r"due_frame = 1,"
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r'key = "sasuke-bomb-projectile-07",\s+'
                r'name = "sasuke-bomb-projectile-07\.png",\s+'
                r"stage = COMBAT_STAGE_ACTION_MOVIE,\s+"
                r"resource =\s+"
                r"COMBAT_RESOURCE_NINJA_TOOL_BOMB_PROJECTILE,\s+"
                r"due_frame = 6,"
            ),
        )
        for key in (
            "A",
            "B",
            "Down",
            "Left",
            "Right",
            "Up",
            "R",
            "Select",
        ):
            self.assertIn(f"{key} = C.GBA_KEY.", source)

        for screenshot in (
            "formation-3v5.png",
            "deployment-unit-1.png",
            "deployment-start.png",
            "naruto-selected.png",
            "naruto-actions.png",
            "naruto-tool.png",
            "naruto-teleport-result.png",
            "sakura-selected.png",
            "sakura-actions.png",
            "sakura-clone-result.png",
            "sasuke-action-2.png",
            "sasuke-action-5.png",
            "sasuke-action-16.png",
            "enemy-phase-active-9.png",
            "round-2-active-9.png",
            "enemy-resource-action.png",
            "sasuke-action-05-dust-01.png",
            "sasuke-action-05-dust-20.png",
            "sasuke-action-05-dust-58.png",
            "sasuke-action-05-reentry-60.png",
            "sasuke-action-05-impact-00.png",
            "sasuke-action-05-impact-04.png",
            "sasuke-action-05-impact-08.png",
            "sasuke-action-05-impact-12.png",
            "sasuke-action-05-impact-15.png",
            "sasuke-action-05-map-restored.png",
            "sasuke-fire-map-restored.png",
            "sasuke-fire-cutin-slide.png",
            "sasuke-fire-cutin-fade.png",
            "sasuke-bomb-projectile-01.png",
            "sasuke-bomb-projectile-07.png",
            "sasuke-bomb-impact-08.png",
            "sasuke-bomb-smoke-01.png",
            "sasuke-bomb-smoke-40.png",
            "sasuke-bomb-smoke-80.png",
            "sasuke-bomb-smoke-110.png",
            "sasuke-bomb-map-restored.png",
        ):
            with self.subTest(screenshot=screenshot):
                self.assertIn(f'"{screenshot}"', source)

        self.assertIn("telemetry.action_count == 4", source)
        self.assertIn("telemetry.selected_action_level == 1", source)
        self.assertIn('"expected_action_level":1', source)
        self.assertNotIn("os.exit(", source)
        self.assertIn("telemetry.selected_action_kind == 1", source)
        self.assertIn("observed.naruto_tool", source)
        self.assertIn("observed.ai_resource", source)
        self.assertIn("observed.ai_substitution", source)
        self.assertIn(
            "telemetry.presentation_resource_resolved == 1",
            source,
        )
        self.assertIn(
            "telemetry.selected_action_id == ACTION_TELEPORT",
            source,
        )
        self.assertIn(
            "telemetry.selected_action_id == ACTION_CLONE",
            source,
        )
        self.assertIn(
            "telemetry.last_resolved_action_id == ACTION_TELEPORT",
            source,
        )
        self.assertIn(
            "telemetry.last_resolved_action_id == ACTION_CLONE",
            source,
        )
        self.assertIn("telemetry.active_units == 9", source)
        self.assertIn("telemetry.player_completed >= 3", source)
        self.assertIn("local expected_active_units =", source)
        self.assertIn("execute_sasuke_combat and 8 or 9", source)
        self.assertIn('"sasuke_bomb_executed":%s', source)
        self.assertIn(
            "telemetry.active_units == expected_active_units",
            source,
        )
        self.assertIn('"expected_active_units":%d', source)
        self.assertIn("local expected_completion_round =", source)
        self.assertIn('"expected_round":%d', source)
        self.assertIn('"naruto_tool":1', source)
        self.assertIn("register-samples.jsonl", source)
        self.assertIn("input-events.jsonl", source)
        self.assertIn('emu:readRegister("pc")', source)
        self.assertIn('emu:readRegister("lr")', source)
        self.assertIn('emu:readRegister("sp")', source)
        self.assertIn("emu:read16(0x04000130)", source)
        self.assertIn("emu:read16(0x04000208)", source)
        self.assertIn("emu:read16(0x04000200)", source)
        self.assertIn("emu:read16(0x04000202)", source)
        self.assertIn("emu:read16(0x04000004)", source)
        self.assertIn("MGBA_B09_ACTION_TRAP_ADDRESS", source)
        self.assertIn("MGBA_B09_ACTION_TRAP_AFTER_HITS", source)
        self.assertIn("MGBA_B09_ACTION_TRAP_START_FRAME", source)
        self.assertIn("execution-trap.jsonl", source)
        self.assertIn("MGBA_B09_ACTION_WATCH_ADDRESS", source)
        self.assertIn("MGBA_B09_ACTION_WATCH_START_FRAME", source)
        self.assertIn("MGBA_B09_ACTION_WATCH_AFTER_HITS", source)
        self.assertIn("memory-write-trap.jsonl", source)
        self.assertIn("C.WATCHPOINT_TYPE.WRITE_CHANGE", source)
        self.assertIn('"r0":"0x%08X"', source)
        self.assertIn('"r1":"0x%08X"', source)
        self.assertIn('"r2":"0x%08X"', source)
        self.assertIn("emu:setBreakpoint", source)
        self.assertIn(
            "frame >= trap_start_frame and not trap_breakpoint",
            source,
        )
        self.assertIn('emu:readRegister("r12")', source)
        self.assertIn("emu:read32(stack_pointer + offset)", source)
        self.assertIn("emu:read32(0x0201F980 + offset)", source)
        self.assertIn("emu:read32(0x0300294C + offset)", source)
        self.assertIn("frame % 120 == 0", source)
        self.assertIn("periodic-stall.png", source)
        self.assertIn("emu:saveStateFile", source)
        self.assertIn('"status":"capture-complete"', source)


if __name__ == "__main__":
    unittest.main()
