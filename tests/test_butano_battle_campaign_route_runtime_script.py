import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_battle_campaign_route.lua"
)
GENERATED_MAP_CONTENT = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "generated_battle_map_content.h"
)


class ButanoBattleCampaignRouteRuntimeScriptTest(unittest.TestCase):
    def test_optional_assert_breakpoint_preserves_runtime_failure_evidence(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_ASSERT_ADDRESS",
            "emu:setBreakpoint(on_butano_assert, assert_address)",
            '"/assert-hit.json"',
            '"/assert-hit.png"',
            '"/assert-hit.ss9"',
            'write_file(done_marker_path, payload)',
            'emu:readRegister("pc")',
            'emu:readRegister("lr")',
            'emu:readRegister("sp")',
            "emu:read32(stack_pointer + index * 4)",
            '"stack_words":[',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_script_stays_below_the_lua_main_chunk_local_limit(self):
        compiler = shutil.which("luac")
        if compiler is None:
            self.skipTest("luac is unavailable")
        subprocess.run(
            [compiler, "-p", str(SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_optional_ui_capture_records_live_interactive_phases(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_CAPTURE_UI",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_CAPTURE_ENTRY_SEQUENCE",
            "capture_ui_phase",
            '"/ui-phase-%d.png"',
            '"/ui-phase-1-frame-%02d.png"',
            "entry_sequence_capture_index < 32",
            "phase ~= PHASE_UNIT_SELECTION",
            "phase ~= PHASE_MOVE_SELECTION",
            "battle.move_preview_x == battle.selected_unit_x",
            "battle.move_preview_y == battle.selected_unit_y",
            "PHASE_COMMAND_SELECTION",
            "PHASE_ACTION_SELECTION",
            "PHASE_TARGET_SELECTION",
            "PHASE_TARGET_PREVIEW",
            "PHASE_TARGET_CONFIRMATION",
            "phase == PHASE_TARGET_SELECTION or",
            "phase == PHASE_TARGET_PREVIEW or",
            "phase == PHASE_TARGET_CONFIRMATION then",
            "PHASE_END_CONFIRMATION",
            "PHASE_FACING_SELECTION",
            "PHASE_SCRIPT_BLOCKED",
            "PHASE_LEVEL_UP",
            "PHASE_TRAINING",
            "battle.script_phase ~= SCRIPT_WAIT_FOR_INPUT",
            "battle.script_message_window_visible ~= 1",
            "emu:read32(battle_telemetry_address + 160)",
            "emu:read32(battle_telemetry_address + 164)",
            'output_dir .. "/ui-phase-18.json"',
            'emu:saveStateFile(output_dir .. "/ui-phase-18.ss9")',
            "PHASE_RESULT",
            "if battle and capture_ui_phase(battle) then",
            '"/ui-sasuke-focus.png"',
            '"/ui-enemy-initiated-duel.png"',
            '"/ui-command-after-move.png"',
            '"/ui-command-after-move.json"',
            "captured_command_after_move",
            "battle.move_preview_x ~= battle.selected_unit_x",
            "battle.move_preview_y ~= battle.selected_unit_y",
            "battle.current_side == SIDE_ENEMY",
            "battle.presentation_combat_stage >= 1",
            "battle.presentation_combat_stage <= 3",
            "phase == PHASE_FACING_SELECTION and",
            "battle.selected_character_id ~= 2",
            "battle.selected_action_target_kind ~=",
            "TARGET_OPPONENT_UNIT",
            "phase == PHASE_SCRIPT_BLOCKED and 8 or 2",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)
        self.assertIn(
            "phase ~= PHASE_RESULT and\n"
            "\t\t\tphase ~= PHASE_LEVEL_UP and\n"
            "\t\t\tphase ~= PHASE_TRAINING then",
            script,
        )

    def test_scenario_49_ui_capture_records_prebattle_root_and_confirmation(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "prebattle_task_menu_root_captured",
            "prebattle_task_confirmation_ready_frame",
            "prebattle_task_confirmation_captured",
            '"/prebattle-task-menu-root.png"',
            '"/prebattle-task-confirmation.png"',
            "expected_scenario == 49",
            "expected_battle == 14",
            "preparation_step == 0",
            "preparation_step == 3",
            "prebattle_task_confirmation_ready_frame =",
            "frame + 8",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_facing_capture_changes_the_selected_direction_before_screenshot(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "facing_direction_probe_staged",
            "if phase == PHASE_FACING_SELECTION and",
            "not facing_direction_probe_staged",
            'press("Down")',
            "ui_phase_ready_frame[phase] = frame + 8",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_homologous_enemy_duel_probe_ends_player_actions_and_captures_each_combat_stage(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_HOMOLOGOUS_ENEMY_DUEL_PROBE",
            "scenario_49_homologous_enemy_duel_probe",
            "scenario_49_homologous_enemy_duel_started",
            "scenario_49_homologous_enemy_duel_last_stage",
            '"/homologous-enemy-duel-stage-%d.png"',
            '"/homologous-enemy-duel-stage-%d.json"',
            '"status":"homologous-enemy-duel-complete"',
            "battle.current_side == SIDE_ENEMY",
            "battle.presentation_combat_stage_frame >= 2",
            "expected_command = COMMAND_END_ACTION",
            "SCENARIO_49_HOMOLOGOUS_NARUTO_ROUND_1",
            "SCENARIO_49_HOMOLOGOUS_NARUTO_ROUND_2",
            "SCENARIO_49_HOMOLOGOUS_NARUTO_ROUND_2 = { x = 7, y = 4 }",
            "scenario_49_move_cursor_to(",
            "write_file(done_marker_path, audit)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_target_status_capture_requires_the_original_preview_semantics(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "captured_homologous_target_status",
            "homologous_target_status_ready_frame",
            "battle.phase == PHASE_TARGET_PREVIEW",
            "battle.selected_character_id == 1",
            "battle.selected_action_id == ACTION_TAIJUTSU",
            "battle.cursor_unit_hp == 25",
            "battle.cursor_unit_attack == 14",
            "battle.cursor_unit_defense == 6",
            "battle.cursor_unit_agility == 24",
            '"/ui-target-status-homologous.png"',
            '"/ui-target-status-homologous.json"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_cold_saved_route_launches_battle_42(self):
        self.assertTrue(SCRIPT.is_file())
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_OUTPUT_DIR",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_DONE_MARKER",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_BATTLE_TELEMETRY_ADDRESS",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_CAMPAIGN_TELEMETRY_ADDRESS",
            "CAMPAIGN_TELEMETRY_MAGIC",
            "campaign.scenario_id == expected_scenario",
            "battle.battle_id == expected_battle",
            "drive_deployment(battle)",
            "PREPARATION_SETTLE_FRAME = 120",
            "battle.phase == PHASE_UNIT_SELECTION",
            "entry_ready_frame = frame + 2",
            "selected_character_id",
            '"active_units":%d',
            'preparation_step == 0 and press("Down")',
            'preparation_step == 3 and not active_key',
            'preparation_step == 2 and press("A")',
            'frame >= next_press_frame and press("A")',
            '"status":"campaign-route-battle-entry"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_completion_mode_drives_battle_42_and_verifies_saved_scenario_43(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_COMPLETE_STAGE",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_SCENARIO",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_BATTLE",
            "drive_stage_completion(battle)",
            "campaign.scenario_id == expected_next_scenario",
            "campaign.save_verified == 1",
            "campaign.naruto_level == expected_naruto_level",
            "expected_naruto_experience",
            "expected_mission_experience",
            "expected_battle_experience",
            "expected_round_bonus_experience",
            "expected_total_experience",
            "move_candidates",
            "move_target_distance == 1",
            "postbattle_task_menu_ready_frame",
            "postbattle_task_menu_capture_step",
            '"/postbattle-task-menu.png"',
            '"/postbattle-task-menu-root.png"',
            'postbattle_task_menu_capture_step == 0',
            'postbattle_task_menu_capture_step = 1',
            '"status":"campaign-route-stage-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn('"/stage-complete.png"', script)
        self.assertNotIn("emu:write", script)

    def test_completion_mode_can_drive_scenario_43_multi_unit_stage(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NEXT_SCENARIO",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_MISSION_EXPERIENCE",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_BATTLE_EXPERIENCE",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_ROUND_BONUS_EXPERIENCE",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_TOTAL_EXPERIENCE",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NARUTO_LEVEL",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NARUTO_EXPERIENCE",
            "MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_NARUTO_TRAINING_POINTS",
            "PHASE_LEVEL_UP",
            "ACTION_SHADOW_CLONE",
            "shadow_clone_verified",
            "completion_round_limit",
            "PLAYER_MOVEMENT_BUDGET",
            "candidate_origin_distance",
            "move_unit",
            "battle.selected_unit",
            "battle.last_resolved_action_id == ACTION_SHADOW_CLONE",
            '"shadow_clone_verified":%d',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)

    def test_completion_mode_resolves_scenario_44_bells_objective(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "scenario_44_completion",
            "OBJECTIVE_INTERACTION_X = 4",
            "OBJECTIVE_INTERACTION_Y = 3",
            "battle.first_active_enemy_x == NO_COORDINATE",
            "battle.battlefield_object_count == 0",
            "objective_facing_staged",
            'press("Down")',
            "expected_result_participant_count",
            '"objective_verified":%d',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)

    def test_completion_mode_can_drive_scenario_45_team_seven_stage(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "scenario_45_completion",
            "scenario_45_completion and 150",
            "scenario_45_completion and 275",
            "scenario_45_completion and 5",
            "scenario_44_completion or scenario_45_completion",
            'collectgarbage("step", 64)',
            '"result_participant_count":%d',
            '"result_mission_experience":%d',
            '"result_battle_experience":%d',
            '"result_round_bonus_experience":%d',
            '"result_total_experience":%d',
            "PHASE_COMBINATION_DECISION = 7",
            "ACTION_KIND_NINJA_TOOL = 1",
            "ACTION_CROSS_SHURIKEN = 1",
            "ACTION_SASUKE_FIRE = 16",
            "cross_shuriken_verified",
            "sasuke_fire_verified",
            "sakura_finisher_verified",
            "battle.selected_character_id == 3",
            "battle.selected_action_kind ==",
            "campaign.naruto_tool_0",
            "campaign.owned_tool_1",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)

    def test_scenario_46_probe_observes_mission_rules_from_runtime_domain(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_SCENARIO_46_RULE_PROBE",
            "scenario_46_rule_probe",
            "COMMAND_DIRECT_ATTACK = 2",
            "PLAYER_ERROR_ACTION_REJECTED = 7",
            "ACTION_SHADOW_CLONE = 7",
            "EFFECT_DAMAGE = 1",
            "TARGET_OPPONENT_UNIT = 2",
            "selected_action_effect_code =",
            "emu:read32(battle_telemetry_address + 400)",
            "selected_action_target_kind =",
            "emu:read32(battle_telemetry_address + 404)",
            "direct_attack_rejected",
            "shadow_clone_transformed",
            '"status":"scenario-46-rule-probe"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)

    def test_scenario_46_completion_uses_exact_map_units_and_legal_inputs(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "scenario_46_completion",
            "read_battle_units",
            "selected_unit_chakra =",
            "move_preview_x =",
            "move_preview_y =",
            "SCENARIO_46_MAP",
            "scenario_46_planned_destination",
            "scenario_46_capture_count",
            "scenario_46_designated_character",
            "scenario_46_drive_completion",
            "PHASE_CHAKRA_SELECTION",
            "scenario_46_presented_captures == 5",
            '"scenario_46_presented_captures":%d',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)

    def test_runtime_failures_are_written_to_the_artifact_directory(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "local function drive_frame()",
            "xpcall(drive_frame",
            'output_dir .. "/failure.txt"',
            "tostring(error_message)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_progress_diagnostics_include_post_battle_progression_values(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "result_level_before =",
            "emu:read32(battle_telemetry_address + 132)",
            "result_level_after =",
            "emu:read32(battle_telemetry_address + 136)",
            "result_experience_after =",
            "emu:read32(battle_telemetry_address + 140)",
            '"result_level_before":%d',
            '"result_level_after":%d',
            '"result_experience_after":%d',
            '"training_points":%d',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_scenario_46_capture_tracking_does_not_block_the_frame_callback(self):
        script = SCRIPT.read_text(encoding="utf-8")
        capture_block = script[
            script.index("local captured ="):
            script.index(
                "scenario_46_previous_active_units =",
                script.index("local captured ="),
            )
        ]

        self.assertIn('"capture-%d.json"', capture_block)
        self.assertNotIn("emu:screenshot", capture_block)

    def test_scenario_46_driver_confirms_chakra_amount(self):
        script = SCRIPT.read_text(encoding="utf-8")
        driver = script[
            script.index(
                "local function scenario_46_drive_completion"
            ):
            script.index(
                "local function scenario_45_attack_range"
            )
        ]

        self.assertIn(
            "elseif battle.phase == PHASE_CHAKRA_SELECTION then",
            driver,
        )
        self.assertIn('press("A")', driver)

    def test_scenario_46_route_passability_matches_generated_battle_9(self):
        script = SCRIPT.read_text(encoding="utf-8")
        map_content = GENERATED_MAP_CONTENT.read_text(
            encoding="utf-8"
        )
        route_block = re.search(
            r"local SCENARIO_46_MAP = \{(?P<body>.*?)\n\}",
            script,
            re.DOTALL,
        )
        self.assertIsNotNone(route_block)
        route_rows = re.findall(
            r'"([.#]{16})"',
            route_block.group("body"),
        )
        self.assertEqual(len(route_rows), 32)

        definition = re.search(
            r"battle_map_definition\{\s*9,\s*16,\s*32,\s*"
            r"(?P<offset>\d+),\s*(?P<count>\d+)\s*\}",
            map_content,
        )
        self.assertIsNotNone(definition)
        self.assertEqual(int(definition.group("count")), 512)
        raw_cells = [
            int(value, 16)
            for value in re.findall(
                r"battle_map_cell\{\s*0x([0-9A-Fa-f]{4})\s*\}",
                map_content,
            )
        ]
        offset = int(definition.group("offset"))
        battle_cells = raw_cells[offset:offset + 512]
        generated_rows = [
            "".join(
                "." if raw & 0xF == 0 else "#"
                for raw in battle_cells[row * 16:(row + 1) * 16]
            )
            for row in range(32)
        ]

        self.assertEqual(route_rows, generated_rows)

    def test_scenario_47_completion_drives_real_three_v_five_battle(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "scenario_47_completion",
            "SCENARIO_47_MAP",
            "scenario_47_drive_completion",
            "scenario_47_planned_destination",
            "scenario_47_active_enemy_count",
            "scenario_47_defeated_enemies == 5",
            "scenario_47_rest_verified",
            "scenario_47_shadow_clone_verified",
            "PHASE_REST_CONFIRMATION",
            "COMMAND_REST",
            '"scenario_47_defeated_enemies":%d',
            '"scenario_47_rest_verified":%d',
            '"scenario_47_shadow_clone_verified":%d',
            "scenario_47_completion and 75",
            "scenario_47_completion and 200",
            "scenario_47_completion and 85",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)

    def test_scenario_47_route_passability_matches_generated_battle_13(self):
        script = SCRIPT.read_text(encoding="utf-8")
        map_content = GENERATED_MAP_CONTENT.read_text(
            encoding="utf-8"
        )
        route_block = re.search(
            r"local SCENARIO_47_MAP = \{(?P<body>.*?)\n\}",
            script,
            re.DOTALL,
        )
        self.assertIsNotNone(route_block)
        route_rows = re.findall(
            r'"([.#]{13})"',
            route_block.group("body"),
        )
        self.assertEqual(len(route_rows), 21)

        definition = re.search(
            r"battle_map_definition\{\s*13,\s*13,\s*21,\s*"
            r"(?P<offset>\d+),\s*(?P<count>\d+)\s*\}",
            map_content,
        )
        self.assertIsNotNone(definition)
        self.assertEqual(int(definition.group("count")), 273)
        raw_cells = [
            int(value, 16)
            for value in re.findall(
                r"battle_map_cell\{\s*0x([0-9A-Fa-f]{4})\s*\}",
                map_content,
            )
        ]
        offset = int(definition.group("offset"))
        battle_cells = raw_cells[offset:offset + 273]
        generated_rows = [
            "".join(
                "." if raw & 0xF == 0 else "#"
                for raw in battle_cells[row * 13:(row + 1) * 13]
            )
            for row in range(21)
        ]

        self.assertEqual(route_rows, generated_rows)

    def test_scenario_49_completion_drives_allied_ai_escort_battle(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "scenario_49_completion",
            "expected_scenario == 49",
            "expected_battle == 14",
            "SCENARIO_49_MAP",
            "scenario_49_weakest_enemy",
            "scenario_49_priority_enemy",
            "actor.id >= 10",
            "battle.units[7]",
            "SCENARIO_49_NARUTO_GUARD",
            "SCENARIO_49_SASUKE_GUARD",
            "scenario_49_enemy_in_range",
            "scenario_49_planned_destination",
            "scenario_49_move_cursor_to",
            "scenario_49_move_menu_probe",
            '"/scenario_49-move-menu.json"',
            "assert(scenario_49_move_menu_probe == 3)",
            "scenario_49_drive_completion",
            "unit.hp = emu:read32(",
            "unit.chakra = emu:read32(",
            "unit.side = emu:read32(",
            "unit.control = emu:read32(",
            "resource_preview_amount =",
            "resource_preview_maximum_amount =",
            "condition_outcome =",
            "scenario_49_replenished_sasuke",
            "scenario_49_skip_replenish_under_pressure",
            "scenario_49_used_fireball",
            "scenario_49_shadow_clone_created",
            "scenario_49_combination_followup",
            "scenario_49_combination_target_adjacent",
            "PHASE_TARGET_PREVIEW",
            "PHASE_TARGET_CONFIRMATION",
            "PHASE_END_CONFIRMATION",
            "PHASE_DEFENSE_SELECTION",
            "scenario_49_defense_no_staged",
            "scenario_49_defeated_enemies == 5",
            "scenario_49_allied_ai_survived",
            "scenario_49_active_enemy_count(battle) > 2",
            '"scenario_49-transition-%04d.json"',
            "scenario_49_completion and 100",
            "scenario_49_completion and 225",
            "scenario_49_completion and 6",
            "scenario_49_completion and 0 or 110",
            "scenario_49_completion and 5",
            "assert(battle.round <= 16)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)
        self.assertNotIn(
            "scenario_49_second_shadow_clone_created",
            script,
        )
        self.assertIn(
            '"MGBA_BATTLE_CAMPAIGN_ROUTE_EXPECTED_ROUND_BONUS_EXPERIENCE",\n'
            "\t0\n",
            script,
        )
        self.assertIn(
            "scenario_49_completion) and\n\t\t\t125 or 100",
            script,
        )

    def test_scenario_49_completion_advances_six_training_summary_pages(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "scenario_49_training_summary_page",
            "if scenario_49_training_summary_page < 6 then",
            "scenario_49_training_summary_page =",
            "scenario_49_training_summary_page + 1",
            "captured_scenario_49_training_pages",
            "battle.training_detail_page",
            "scenario_49_training_page_ready_frame",
            "battle_telemetry_address + 824",
            '"/ui-training-page-%d.png"',
            'press("A")',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_scenario_49_sasuke_taijutsu_probe_requires_complete_presentation(self):
        script = SCRIPT.read_text(encoding="utf-8")

        for token in (
            "MGBA_BATTLE_CAMPAIGN_ROUTE_SASUKE_TAIJUTSU_PROBE",
            "scenario_49_sasuke_taijutsu_probe",
            "presentation_combat_stage =",
            "battle_telemetry_address + 364",
            "presentation_combat_stage_frame =",
            "battle_telemetry_address + 368",
            "scenario_49_sasuke_taijutsu_target_confirmed",
            "scenario_49_sasuke_taijutsu_presentation_started",
            "finish_scenario_49_sasuke_taijutsu_probe",
            "assert(battle.selected_character_id == 2)",
            "assert(battle.last_resolved_action_id == ACTION_TAIJUTSU)",
            "assert(scenario_49_sasuke_taijutsu_max_stage >= 7)",
            '"scenario-49-sasuke-taijutsu-complete"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

        self.assertNotIn("emu:write", script)

    def test_scenario_49_route_passability_matches_generated_battle_14(self):
        script = SCRIPT.read_text(encoding="utf-8")
        map_content = GENERATED_MAP_CONTENT.read_text(
            encoding="utf-8"
        )
        route_block = re.search(
            r"local SCENARIO_49_MAP = \{(?P<body>.*?)\n\}",
            script,
            re.DOTALL,
        )
        self.assertIsNotNone(route_block)
        route_rows = re.findall(
            r'"([.#]{15})"',
            route_block.group("body"),
        )
        self.assertEqual(len(route_rows), 19)

        definition = re.search(
            r"battle_map_definition\{\s*14,\s*15,\s*19,\s*"
            r"(?P<offset>\d+),\s*(?P<count>\d+)\s*\}",
            map_content,
        )
        self.assertIsNotNone(definition)
        self.assertEqual(int(definition.group("count")), 285)
        raw_cells = [
            int(value, 16)
            for value in re.findall(
                r"battle_map_cell\{\s*0x([0-9A-Fa-f]{4})\s*\}",
                map_content,
            )
        ]
        offset = int(definition.group("offset"))
        battle_cells = raw_cells[offset:offset + 285]
        generated_rows = [
            "".join(
                "." if raw & 0xF == 0 else "#"
                for raw in battle_cells[row * 15:(row + 1) * 15]
            )
            for row in range(19)
        ]

        self.assertEqual(route_rows, generated_rows)


if __name__ == "__main__":
    unittest.main()
