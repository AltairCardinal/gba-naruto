import json
import os
import subprocess
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tools" / "butano" / "toolchain.lock"


class ButanoBuildTest(unittest.TestCase):
    def test_campaign_battle_uses_live_preparation_and_upgrade_flow(
        self,
    ):
        main = (
            ROOT / "butano-sequel/src/main.cpp"
        ).read_text(encoding="utf-8")
        scene = (
            ROOT
            / "butano-sequel/game/src"
            / "battle_preparation_scene.cpp"
        )
        self.assertTrue(scene.is_file())
        source = scene.read_text(encoding="utf-8")
        self.assertIn(
            "konoha/battle_preparation_flow.h",
            source,
        )
        self.assertIn(
            "battle_preparation_flow flow",
            source,
        )
        self.assertIn("bn::keypad::a_pressed()", source)
        self.assertIn("bn::keypad::b_pressed()", source)
        self.assertIn("bn::keypad::up_pressed()", source)
        self.assertIn("bn::keypad::down_pressed()", source)
        self.assertIn("bn::keypad::left_pressed()", source)
        self.assertIn("bn::keypad::right_pressed()", source)
        self.assertIn("flow.confirm()", source)
        self.assertIn("flow.cancel()", source)
        self.assertIn("flow.move(", source)
        self.assertIn("flow.switch_character(", source)
        self.assertIn("render_preparation_text(", source)
        self.assertIn("装备忍具", source)
        self.assertIn("卸下忍具", source)
        self.assertIn(
            "battle_preparation_phase::equip",
            source,
        )
        self.assertIn(
            "battle_preparation_phase::unequip",
            source,
        )
        self.assertIn(
            "state.last_equipment_error",
            source,
        )
        self.assertRegex(
            source,
            r"regular_bg_items::\s*"
            r"battle_01_map_chunk_0",
        )
        self.assertIn(
            "konoha/battle_preparation_scene.h",
            main,
        )
        self.assertIn(
            "konoha::run_battle_preparation_scene(",
            main,
        )
        self.assertLess(
            main.index(
                "konoha::run_battle_preparation_scene("
            ),
            main.index("konoha::run_battle_campaign_stage("),
        )
        self.assertIn(
            "campaign_checkpoint.inventory.ninja_tools[67] = 1",
            main,
        )
        self.assertIn(
            "campaign_checkpoint.inventory.ninja_tools[1] = 1",
            main,
        )
        self.assertIn(
            "campaign_checkpoint.inventory.materials[6] = 1",
            main,
        )

    def test_visible_runtime_accepts_explicit_dynamic_deployment_request(
        self,
    ):
        runtime_header = (
            ROOT
            / "butano-sequel/game/include/konoha"
            / "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        runtime_source = (
            ROOT
            / "butano-sequel/game/src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "struct battle_runtime_scene_request",
            runtime_header,
        )
        self.assertIn(
            "battle_scenario_load_policy load_policy",
            runtime_header,
        )
        self.assertIn(
            "run_battle_scene(",
            runtime_header,
        )
        self.assertIn(
            "run_battle_32_arena_fixture_scene()",
            runtime_header,
        )
        self.assertIn(
            "config.load_policy",
            runtime_source,
        )
        self.assertNotIn(
            "content.kind ==\n"
            "                    battle_content_entry_kind::\n"
            "                            fixed_roster",
            runtime_source,
        )
        self.assertIn(
            "battle_content_entry_kind::empty",
            runtime_source,
        )
        self.assertIn(
            "request.arena_roster = &roster",
            runtime_source,
        )
        self.assertIn(
            "run_battle_32_arena_fixture_scene()",
            runtime_source,
        )

    def test_battle_11_uses_shared_background_streaming_runtime(self):
        graphics = ROOT / "butano-sequel" / "graphics"
        manifest_path = (
            graphics / "battle_11_map_chunks.json"
        )
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["battle_id"], 11)
        self.assertEqual(manifest["active_size"], [544, 480])
        self.assertEqual(manifest["origins"], [0, 32])
        for index in range(2):
            self.assertTrue(
                (
                    graphics
                    / f"battle_11_map_chunk_{index}.bmp"
                ).is_file()
            )

        runtime_header = (
            ROOT
            / "butano-sequel/game/include/konoha"
            / "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        runtime_source = (
            ROOT
            / "butano-sequel/game/src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "konoha/battle_background_stream.h",
            runtime_source,
        )
        self.assertIn(
            "konoha/generated_battle_background_content.h",
            runtime_source,
        )
        self.assertIn(
            "generated_battle_background_entry(",
            runtime_source,
        )
        self.assertNotIn(
            "bn_regular_bg_items_battle_11_map_chunk_0.h",
            runtime_source,
        )
        self.assertNotIn(
            "bn_regular_bg_items_battle_11_map_chunk_1.h",
            runtime_source,
        )
        self.assertNotIn(
            "&bn::regular_bg_items::battle_",
            runtime_source,
        )
        self.assertIn(
            "background_content->pixel_width !=",
            runtime_source,
        )
        self.assertIn(
            "scenario.grid_width * cell_width",
            runtime_source,
        )
        self.assertIn("battle_background_stream", runtime_source)
        self.assertIn("map.set_item(", runtime_source)
        self.assertIn("run_battle_11_scene()", runtime_source)
        self.assertIn("run_battle_11_scene()", runtime_header)
        self.assertIn("background_chunk_index", runtime_header)
        self.assertIn("background_chunk_count", runtime_header)
        self.assertNotIn(
            "battle_scene_controller<12, 17, 30>",
            runtime_source,
        )

    def test_scenario_43_scene_renders_shared_controller_snapshots(self):
        main = (ROOT / "butano-sequel" / "src" / "main.cpp").read_text(
            encoding="utf-8"
        )
        scenario_43_path = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_43_scene.cpp"
        )
        self.assertTrue(scenario_43_path.is_file())
        scenario_43_scene = scenario_43_path.read_text(encoding="utf-8")
        runtime_header_path = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_runtime_scene.h"
        )
        runtime_source_path = (
            ROOT
            / "butano-sequel"
            / "game"
            / "src"
            / "battle_runtime_scene.cpp"
        )
        self.assertTrue(runtime_header_path.is_file())
        self.assertTrue(runtime_source_path.is_file())
        runtime_source = runtime_source_path.read_text(encoding="utf-8")
        encounter_runtime = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_encounter_runtime.h"
        ).read_text(encoding="utf-8")
        scenario_loader = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_scenario_loader.h"
        ).read_text(encoding="utf-8")
        player_flow = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_player_action_flow.h"
        ).read_text(encoding="utf-8")
        action_execution = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_action_execution.h"
        ).read_text(encoding="utf-8")
        action_system = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_action_system.h"
        ).read_text(encoding="utf-8")
        turn_flow = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_turn_flow.h"
        ).read_text(encoding="utf-8")

        self.assertNotIn("konoha/scenario_43_scene.h", main)
        self.assertNotIn("konoha::run_scenario_43_scene()", main)
        self.assertIn(
            "konoha::run_battle_campaign_stage(",
            main,
        )
        self.assertLess(len(scenario_43_scene.splitlines()), 40)
        self.assertIn("run_battle_43_scene()", scenario_43_scene)
        self.assertNotIn("run_battle_09_scene()", scenario_43_scene)
        self.assertNotIn("run_battle_11_scene()", scenario_43_scene)
        self.assertNotIn(
            "run_battle_32_arena_fixture_scene()",
            scenario_43_scene,
        )
        self.assertIn("battle_runtime_scene_config", runtime_source)
        self.assertIn("run_visible_battle_scene", runtime_source)
        self.assertIn(
            "konoha_battle_runtime_telemetry",
            runtime_source,
        )
        self.assertIn("capture_telemetry(", runtime_source)
        self.assertIn("_movement_map_workspace", encounter_runtime)
        self.assertIn("_path_workspace", encounter_runtime)
        self.assertIn(
            "battle_encounter_load_workspace",
            encounter_runtime,
        )
        self.assertIn("_load_workspace", encounter_runtime)
        self.assertIn(
            "battle_encounter_transaction_workspace",
            encounter_runtime,
        )
        self.assertIn(
            "_transaction_workspace",
            encounter_runtime,
        )
        self.assertNotIn(
            "battle_session<MaxUnits> next_session = _session;",
            encounter_runtime,
        )
        self.assertNotIn(
            "battle_player_action_flow<MaxUnits> next_flow =",
            encounter_runtime,
        )
        self.assertIn(
            "battle_player_action_flow<MaxUnits> next =\n"
            "                _player_flow;\n"
            "        return next.preview_target(",
            encounter_runtime,
        )
        self.assertIn(
            "confirm_target_in_place",
            encounter_runtime,
        )
        self.assertIn(
            "confirm_target_in_place",
            player_flow,
        )
        self.assertIn("resolve_in_place", action_execution)
        self.assertIn(
            "resolve_area_draft_in_place",
            action_system,
        )
        self.assertIn(
            "resolve_draft_in_place",
            action_system,
        )
        self.assertIn(
            "after_effects_in_place",
            turn_flow,
        )
        self.assertIn(
            "load_battle_scenario_into_empty",
            scenario_loader,
        )
        self.assertIn(
            "load_battle_scenario_into_empty",
            encounter_runtime,
        )
        self.assertNotIn(
            "battle_session<MaxUnits> candidate_session;",
            encounter_runtime,
        )
        self.assertIn(
            "pathfinder_workspace<Width, Height>",
            encounter_runtime,
        )
        self.assertIn("konoha/battle_runtime_grid.h", runtime_source)
        self.assertIn("BN_DATA_EWRAM_BSS static", runtime_source)
        self.assertIn(
            "battle_runtime_controller",
            runtime_source,
        )
        self.assertNotIn(
            "run_visible_battle_scene<",
            runtime_source,
        )
        self.assertNotIn(
            "template<int Width, int Height>",
            runtime_source,
        )
        self.assertIn(
            "konoha/battle_content_catalog.h",
            runtime_source,
        )
        self.assertIn(
            "generated_battle_content_entry(",
            runtime_source,
        )
        self.assertIn(
            "konoha/battle_deployment_flow.h",
            runtime_source,
        )
        self.assertIn(
            "deployment.prepare(",
            runtime_source,
        )
        self.assertIn(
            "run_deployment_confirmation(",
            runtime_source,
        )
        self.assertIn(
            "wait_for_deployment_release(",
            runtime_source,
        )
        self.assertIn(
            "bn::keypad::a_held()",
            runtime_source,
        )
        self.assertLess(
            runtime_source.index(
                "run_deployment_confirmation(",
                runtime_source.index(
                    "run_visible_battle_scene(",
                ),
            ),
            runtime_source.index(
                "controller.load(",
            ),
        )
        deployment_runner = runtime_source[
            runtime_source.index(
                "run_deployment_confirmation(",
            ):
            runtime_source.index(
                "[[nodiscard]] battle_runtime_scene_exit\n"
                "run_visible_battle_scene(",
            )
        ]
        self.assertIn(
            "wait_for_deployment_release(",
            deployment_runner,
        )
        self.assertNotIn(
            "0xFF - slot.selector",
            runtime_source,
        )
        self.assertIn("content.scenario", runtime_source)
        self.assertIn("content.map", runtime_source)
        self.assertIn("content.conditions", runtime_source)
        self.assertNotIn(
            "battle_scenario_definitions[config.battle_id]",
            runtime_source,
        )
        self.assertNotIn(
            "battle_map_definitions[config.battle_id]",
            runtime_source,
        )
        self.assertNotIn(
            "battle_condition_variants[config.condition_battle_id]",
            runtime_source,
        )
        self.assertNotIn("condition_battle_id", runtime_source)
        self.assertNotIn("condition_variant", runtime_source)
        self.assertIn(
            "konoha/generated_battle_background_content.h",
            runtime_source,
        )
        self.assertIn(
            "generated_battle_background_entry(",
            runtime_source,
        )
        self.assertNotIn(
            "bn_regular_bg_items_battle_09_clean_map.h",
            runtime_source,
        )
        self.assertIn("camera_x(", runtime_source)
        self.assertIn("camera_y(", runtime_source)
        self.assertIn("for(std::size_t index = 0;", runtime_source)
        self.assertIn("state.units[index]", runtime_source)
        self.assertIn("state.active_unit_count", runtime_source)
        self.assertIn("presentation.affects(unit.id)", runtime_source)
        self.assertIn('"AI DONE "', runtime_source)
        self.assertIn("controller.tick()", runtime_source)
        self.assertIn("konoha/battle_scene_presentation.h", runtime_source)
        self.assertIn("battle_scene_presentation presentation;", runtime_source)
        self.assertIn("presentation.begin(", runtime_source)
        self.assertIn("take_presentation_event()", runtime_source)
        self.assertIn("presentation.pose(", runtime_source)
        self.assertIn("presentation.busy()", runtime_source)
        self.assertIn(
            "presentation.event().has_resource",
            runtime_source,
        )
        self.assertIn('"CHAKRA +"', runtime_source)
        self.assertIn('"REST HP +"', runtime_source)
        self.assertIn(
            "grid_point camera_focus = state.cursor;",
            runtime_source,
        )
        self.assertIn(
            "camera_focus = presentation_event.origin;",
            runtime_source,
        )
        self.assertIn("camera_x(camera_focus, config)", runtime_source)
        self.assertIn("camera_y(camera_focus, config)", runtime_source)
        self.assertNotIn("battle_session<", runtime_source)
        self.assertNotIn("battle_action_resolver", runtime_source)
        self.assertNotIn("battle_ai_turn_flow::execute", runtime_source)
        self.assertNotIn(".hp =", runtime_source)
        self.assertNotIn(
            "state.units[index].position =",
            runtime_source,
        )
        self.assertIn(
            "visual_unit.position =\n"
            "                map_visual_position;",
            runtime_source,
        )
        self.assertTrue(
            (
                ROOT
                / "butano-sequel"
                / "graphics"
                / "battle_09_clean_map.bmp"
            ).is_file()
        )

    def test_generic_battle_scene_renders_identity_and_action_snapshots(self):
        runtime_header = (
            ROOT
            / "butano-sequel/game/include/konoha"
            / "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        runtime_source = (
            ROOT
            / "butano-sequel/game/src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'konoha/generated_battle_identity_content.h',
            runtime_source,
        )
        self.assertIn(
            'konoha/battle_identity_sprite_font.h',
            runtime_source,
        )
        self.assertIn(
            "battle_identity_sprite_font",
            runtime_source,
        )
        self.assertIn("battle_unit_identity(", runtime_source)
        self.assertIn("battle_active_action_identity(", runtime_source)
        self.assertIn("battle_ninja_tool_identity(", runtime_source)
        self.assertIn("state.player.action_entries", runtime_source)
        self.assertIn(
            "state.player.selected_defense_kind",
            runtime_source,
        )
        self.assertIn(
            "state.player.selected_defense_action_id",
            runtime_source,
        )
        self.assertIn("unit->level", runtime_source)
        self.assertIn("unit->attack", runtime_source)
        self.assertIn("unit->defense", runtime_source)
        self.assertIn("unit->agility", runtime_source)
        self.assertIn("unit->movement", runtime_source)
        self.assertNotIn("battle_action_catalog::build(", runtime_source)
        self.assertNotIn("build_primary_action_loadout(", runtime_source)
        self.assertNotIn('detail = "ACTION "', runtime_source)
        self.assertNotIn('detail += " C";', runtime_source)
        self.assertIn(
            "selected_menu_action->action_level",
            runtime_source,
        )
        self.assertIn('detail += " LV";', runtime_source)
        runtime_start = runtime_source.index(
            "const int initial_camera_x ="
        )
        runtime_cursor = runtime_source.index(
            "ensure_map_cursor(",
            runtime_start,
        )
        text_clear = runtime_source.rindex(
            "text_sprites.clear();",
            0,
            runtime_start,
        )
        script_clear = runtime_source.rindex(
            "script_glyph_sprites.clear();",
            0,
            runtime_start,
        )
        self.assertLess(
            text_clear,
            runtime_cursor,
        )
        self.assertLess(
            script_clear,
            runtime_cursor,
        )
        transition_update = runtime_source.index(
            "bn::core::update();",
            runtime_start,
        )
        self.assertLess(
            script_clear,
            transition_update,
        )
        self.assertLess(transition_update, runtime_cursor)
        self.assertIn("selected_character_id", runtime_header)
        self.assertIn("action_count", runtime_header)
        self.assertIn("action_index", runtime_header)
        self.assertIn("selected_action_id", runtime_header)
        self.assertIn("selected_action_error", runtime_header)
        self.assertIn("selected_action_kind", runtime_header)
        self.assertIn("selected_action_tool_slot", runtime_header)
        self.assertIn(
            "request.load_policy.character_equipped_tools[1][0] = 1;",
            runtime_source,
        )

    def test_active_battle_is_component_rendered_instead_of_state_screenshots(self):
        runtime = (
            ROOT / "butano-sequel" / "game" / "src" / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("battle_scene_snapshot<12>", runtime)
        self.assertIn("update_unit_sprites(", runtime)
        self.assertIn("battle_background_stream", runtime)
        self.assertIn("render_text(", runtime)
        self.assertNotIn("scenario_41_battle", runtime)
        self.assertNotIn("scenario_41_extended_layers", runtime)
        self.assertFalse(
            (
                ROOT
                / "butano-sequel"
                / "game"
                / "src"
                / "scenario_41_scene.cpp"
            ).exists()
        )

    def test_generic_runtime_uses_character_visual_catalog_for_every_unit(self):
        runtime_source = (
            ROOT
            / "butano-sequel"
            / "game"
            / "src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        generated = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "generated_battle_unit_visual_content.h"
        )

        self.assertTrue(generated.is_file())
        self.assertIn(
            "konoha/generated_battle_unit_visual_content.h",
            runtime_source,
        )
        self.assertRegex(
            runtime_source,
            r"battle_unit_visual_slot_for\(\s*"
            r"visual_character_id,\s*sample\.slot\s*\)",
        )
        self.assertIn(
            "sprite->set_item(*item, graphics_index)",
            runtime_source,
        )
        self.assertIn(
            "std::array<battle_unit_sprite_state, 12>",
            runtime_source,
        )
        self.assertIn(
            "if(! unit.active && ! presentation_target)",
            runtime_source,
        )
        self.assertIn("sprite_state.reset()", runtime_source)
        self.assertIn(
            "battle_unit_visual_max_components",
            runtime_source,
        )
        self.assertIn(
            "battle_unit_visual_animation::frame_at(",
            runtime_source,
        )
        self.assertNotIn(
            "bn_sprite_items_scenario_41_naruto.h",
            runtime_source,
        )
        self.assertNotIn(
            "bn_sprite_items_scenario_41_enemy.h",
            runtime_source,
        )

    def test_scenario_41_uses_generated_action_domain_instead_of_fixed_damage_ability(self):
        definition = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_definition.h"
        ).read_text(encoding="utf-8")
        controller = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_scene_controller.h"
        ).read_text(encoding="utf-8")
        self.assertIn("konoha/generated_battle_action_content.h", definition)
        self.assertIn("battle_action_catalog::build", definition)
        self.assertIn("scenario_41_tutorial_action", definition)
        self.assertNotIn("scenario_41_player_actions", definition)
        self.assertNotIn("scenario_41_combo_action", definition)
        self.assertNotIn("scenario_41_enemy_actions", definition)
        self.assertNotIn("materialize_action_loadout", definition)
        self.assertNotIn("effect_node_kind::damage, 80", definition)
        self.assertIn("konoha/battle_encounter_runtime.h", controller)
        self.assertNotIn("battle_action_resolver::resolve_draft", controller)
        self.assertNotIn("battle_action_resolver::resolve_area_draft", controller)
        self.assertNotIn("ability_resolver::resolve_draft", controller)
        self.assertIn("_runtime.load(", controller)
        self.assertNotIn("instantiate_unit(", controller)
        self.assertIn("konoha/generated_battle_scenario_content.h", definition)
        self.assertIn("battle_scenario_definitions[41]", definition)

    def test_scenario_41_routes_victory_through_ordered_condition_interpreter(self):
        definition = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_definition.h"
        ).read_text(encoding="utf-8")
        controller = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_scene_controller.h"
        ).read_text(encoding="utf-8")
        player_flow = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_player_action_flow.h"
        ).read_text(encoding="utf-8")
        ai_flow = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_ai_turn_flow.h"
        ).read_text(encoding="utf-8")

        self.assertIn('konoha/battle_conditions.h', definition)
        self.assertIn('konoha/generated_battle_condition_content.h', definition)
        self.assertIn("scenario_41_condition_variant", definition)
        self.assertIn("battle_condition_variants[9][0]", definition)
        self.assertIn("konoha/battle_turn_flow.h", player_flow)
        self.assertIn("battle_turn_flow::after_effects", player_flow)
        self.assertIn("battle_turn_flow::complete_defense", player_flow)
        self.assertIn("battle_turn_flow::after_effects", ai_flow)
        self.assertIn("battle_turn_flow::complete_defense", ai_flow)
        self.assertNotIn("battle_turn_flow::after_effects", controller)
        self.assertNotIn("battle_turn_flow::complete_defense", controller)
        self.assertIn("battle_result_system::preview(", controller)
        self.assertIn("battle_result_system::apply_experience(", controller)

    def test_scenario_41_uses_shared_session_action_tail_for_player_and_ai(self):
        controller = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_scene_controller.h"
        ).read_text(encoding="utf-8")

        self.assertIn("konoha/battle_encounter_runtime.h", controller)
        for call in (
            "_runtime.begin_player_unit(",
            "_runtime.open_move_selection(",
            "_runtime.preview_move(",
            "_runtime.confirm_move_selection(",
            "_runtime.reopen_move_selection(",
            "_runtime.cancel_unit_action(",
            "_runtime.open_action_selection(",
            "_runtime.preview_target(",
            "_runtime.confirm_target(",
            "_runtime.end_without_action(",
            "_runtime.select_facing(",
            "_runtime.complete_without_defense(",
            "_runtime.open_defense_selection(",
            "_runtime.complete_selected_defense(",
            "_runtime.run_ai(",
        ):
            with self.subTest(call=call):
                self.assertIn(call, controller)
        self.assertNotIn("battle_action_resolver::resolve_draft", controller)
        self.assertNotIn("battle_ai_turn_flow::execute(", controller)
        self.assertNotIn("battle_turn_flow::complete_defense(", controller)

    def test_scenario_41_enemy_uses_shared_ai_turn_flow(self):
        controller = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_scene_controller.h"
        ).read_text(encoding="utf-8")
        definition = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_definition.h"
        ).read_text(encoding="utf-8")

        self.assertIn("konoha/battle_encounter_runtime.h", controller)
        self.assertIn("_runtime.run_ai(", controller)
        self.assertNotIn("battle_ai_turn_flow::execute(", controller)
        self.assertNotIn("battle_ai::plan(", controller)
        self.assertNotIn("battle_action_resolver::resolve_draft", controller)
        self.assertNotIn("battle_action_resolver::resolve_area_draft", controller)
        self.assertNotIn("scenario_41_enemy_actions", controller)
        self.assertNotIn("scenario_41_enemy_actions", definition)

    def test_battle_scene_obeys_presentation_and_domain_input_contract(self):
        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        controller = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_scene_controller.h"
        ).read_text(encoding="utf-8")

        self.assertIn("bn::keypad::l_pressed()", scene)
        self.assertIn("bn::keypad::r_pressed()", scene)
        self.assertIn("controller.cycle_unit(-1)", scene)
        self.assertIn("controller.cycle_unit(1)", scene)
        self.assertIn("_runtime.cycle_roster_unit", controller)
        self.assertNotIn("scenario_41_battle", scene)

    def test_benchmark_rom_wiring_is_declared(self):
        makefile = (ROOT / "butano-sequel" / "Makefile").read_text(encoding="utf-8")
        main = (ROOT / "butano-sequel" / "src" / "main.cpp").read_text(
            encoding="utf-8"
        )
        self_test_header = (
            ROOT
            / "butano-sequel"
            / "benchmark"
            / "include"
            / "konoha_bench"
            / "self_test.h"
        ).read_text(encoding="utf-8")
        self_test_source = (
            ROOT
            / "butano-sequel"
            / "benchmark"
            / "src"
            / "self_test.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("benchmark/src", makefile)
        self.assertIn("benchmark/include", makefile)
        self.assertIn("konoha_bench/self_test.h", main)
        self.assertIn("konoha_bench::run_self_tests()", main)
        self.assertIn(
            "konoha/battle_content_catalog.h",
            self_test_source,
        )
        self.assertIn(
            "validate_generated_battle_content_catalog()",
            self_test_source,
        )
        self.assertIn("1U << 5", self_test_source)
        self.assertIn("pass_mask == 0x3F", self_test_header)

    def test_scenario_41_uses_shared_battle_runtime(self):
        makefile = (ROOT / "butano-sequel" / "Makefile").read_text(encoding="utf-8")
        main = (ROOT / "butano-sequel" / "src" / "main.cpp").read_text(
            encoding="utf-8"
        )
        runtime = (
            ROOT / "butano-sequel" / "game" / "src" / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("game/src", makefile)
        self.assertIn("game/include", makefile)
        self.assertIn("graphics", makefile)
        self.assertIn("konoha/battle_runtime_scene.h", main)
        self.assertIn(
            "konoha::run_battle_campaign_stage(",
            main,
        )
        self.assertNotIn("konoha::run_scenario_41_scene()", main)
        self.assertIn("battle_runtime_controller controller;", runtime)
        self.assertIn("controller.load(", runtime)
        self.assertIn("controller.start()", runtime)
        self.assertIn("controller.snapshot()", runtime)
        self.assertFalse(
            (
                ROOT
                / "butano-sequel"
                / "game"
                / "src"
                / "scenario_41_scene.cpp"
            ).exists()
        )
        self.assertFalse(
            (
                ROOT
                / "butano-sequel"
                / "game"
                / "include"
                / "konoha"
                / "scenario_41_battle.h"
            ).exists()
        )
        attack_frames = (
            ROOT
            / "references"
            / "scenario-41-attack-animation"
            / "scenario_41_attack_animation_frames.h"
        )
        self.assertTrue(attack_frames.is_file())
        self.assertIn(
            "std::array<const bn::regular_bg_item*, 264>",
            attack_frames.read_text(encoding="utf-8"),
        )
        self.assertFalse(
            any(
                (ROOT / "butano-sequel" / "graphics").glob(
                    "scenario_41_attack_*"
                )
            ),
            "旧整屏攻击录屏资产只能保留为离线参考，不能进入生产 graphics",
        )
        action_animation = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_action_animation.h"
        )
        self.assertTrue(action_animation.is_file())
        self.assertIn(
            "static constexpr int frame_count = 96",
            action_animation.read_text(encoding="utf-8"),
        )
        self.assertIn("battle_action_animation::pose(", runtime)
        self.assertIn("update_unit_sprites(", runtime)
        self.assertIn("render_text(", runtime)
        self.assertNotIn("scenario_41_extended_layers", runtime)
        self.assertNotIn("scenario_41_prebattle_frames", runtime)
        for keypad_call in (
            "a_pressed()",
            "b_pressed()",
            "start_pressed()",
            "left_pressed()",
            "right_pressed()",
            "up_pressed()",
            "down_pressed()",
        ):
            with self.subTest(keypad_call=keypad_call):
                self.assertIn(keypad_call, runtime)

    def test_original_ui_sound_assets_are_maxmod_compatible(self):
        makefile = (ROOT / "butano-sequel" / "Makefile").read_text(encoding="utf-8")
        self.assertIn("AUDIO           :=  audio", makefile)
        self.assertIn("AUDIOBACKEND    :=  maxmod", makefile)
        for cue in (102, 103, 104, 105):
            path = ROOT / "butano-sequel" / "audio" / f"sound_{cue}.wav"
            with self.subTest(cue=cue):
                self.assertTrue(path.is_file())
                with wave.open(str(path), "rb") as stream:
                    self.assertEqual(stream.getnchannels(), 1)
                    self.assertEqual(stream.getsampwidth(), 1)
                    self.assertEqual(stream.getframerate(), 22050)

    def test_build_rejects_stale_null_audio_objects(self):
        build_script = (
            ROOT / "tools" / "butano" / "build.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("bn_audio_manager.bn_noflto.d", build_script)
        self.assertIn("bn_hw_audio_maxmod.h", build_script)
        self.assertIn("make clean", build_script)

    def test_toolchain_lock_uses_immutable_digest(self):
        self.assertTrue(LOCK.is_file(), "toolchain lock is missing")
        values = {}
        for line in LOCK.read_text(encoding="utf-8").splitlines():
            key, value = line.split("=", 1)
            values[key] = value
        self.assertEqual(values["BUTANO_VERSION"], "21.7.1")
        self.assertEqual(
            values["BUTANO_COMMIT"],
            "112a1827c9c6d9e6041a7e93e66f04c4561a6415",
        )
        self.assertRegex(
            values["DEVKITARM_IMAGE"],
            r"^devkitpro/devkitarm@sha256:[0-9a-f]{64}$",
        )

    @unittest.skipUnless(
        os.environ.get("RUN_BUTANO_INTEGRATION") == "1",
        "set RUN_BUTANO_INTEGRATION=1 to build the ROM",
    )
    def test_minimal_rom_builds_with_expected_header(self):
        build_script = ROOT / "tools" / "butano" / "build.sh"
        self.assertTrue(build_script.is_file(), "Butano build entrypoint is missing")
        subprocess.run([str(build_script)], cwd=ROOT, check=True)
        rom = ROOT / "butano-sequel" / "butano-sequel.gba"
        data = rom.read_bytes()
        self.assertGreater(len(data), 192)
        self.assertLessEqual(
            len(data),
            16 * 1024 * 1024,
            "完整角色动画 ROM 必须保持在标准 16 MiB GBA 卡带边界内",
        )
        self.assertEqual(data[0xA0:0xAC].rstrip(b"\0"), b"KONOHA BASE")
        self.assertEqual(data[0xAC:0xB0], b"KNBT")
        elf = (ROOT / "butano-sequel" / "butano-sequel.elf").read_bytes()
        self.assertIn(b"run_self_tests", elf)
        self.assertIn(b"run_battle_41_scene", elf)
        for symbol in (
            b"scenario_41_prebattle_menu_0",
            b"scenario_41_postbattle_dialogue_11",
            b"sound_002",
            b"sound_005",
            b"sound_008",
            b"sound_014",
            b"sound_015",
            b"sound_116",
            b"sound_138",
            b"sound_149",
            b"sound_158",
        ):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, elf)
        self.assertNotIn(b"scenario_41_attack_frame_159", elf)


if __name__ == "__main__":
    unittest.main()
