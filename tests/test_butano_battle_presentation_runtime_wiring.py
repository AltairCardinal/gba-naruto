#!/usr/bin/env python3
"""Static wiring guard for the visible battle-presentation runtime."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoBattlePresentationRuntimeWiringTests(unittest.TestCase):
    def test_scene_enables_scripts_renders_rom_glyphs_and_ticks_waits(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "bn_sprite_items_battle_presentation_glyphs.h",
            source,
        )
        self.assertIn("render_script_glyphs(", source)
        self.assertRegex(
            source,
            r"config\.progression_roster,\s*true,\s*"
            r"battle_mission_rules_for\(",
        )
        self.assertRegex(
            source,
            r"script_blocked\s*&&\s*"
            r"state\.script\.phase\s*==\s*"
            r"battle_presentation_script_phase::\s*wait_frames",
        )

    def test_script_confirmation_is_not_gated_by_combat_map_controls(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        function_start = source.index("run_visible_battle_scene(")
        loop_start = source.index("while(true)", function_start)
        loop = source[
            loop_start:
            source.index("state = controller.snapshot()", loop_start)
        ]
        script_input = re.search(
            r"state\.phase\s*==\s*battle_scene_phase::\s*"
            r"script_blocked\s*&&\s*state\.script\.phase\s*==\s*"
            r"battle_presentation_script_phase::\s*wait_for_input"
            r".*?!\s*script_confirmation_latched\s*&&\s*"
            r"bn::keypad::a_held\(\).*?"
            r"controller\.confirm\(\)",
            loop,
            re.DOTALL,
        )
        self.assertIsNotNone(script_input)
        self.assertIn(
            "if(! bn::keypad::a_held())\n"
            "        {\n"
            "            script_confirmation_latched = false;",
            loop,
        )
        self.assertLess(
            script_input.start(),
            loop.index("else if(presentation.combat().\n"
                       "                        map_controls_enabled())"),
        )
        self.assertLess(
            script_input.start(),
            loop.index("if(presentation_frame)"),
        )

    def test_script_wait_does_not_pop_the_presentation_fifo(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        function_start = source.index("run_visible_battle_scene(")
        loop_start = source.index("while(true)", function_start)
        loop = source[
            loop_start:
            source.index("state = controller.snapshot()", loop_start)
        ]

        self.assertIn(
            "const bool script_waiting_for_input =",
            loop,
        )
        self.assertRegex(
            loop,
            r"presentation_event\s*=\s*"
            r"! presentation_frame\s*&&\s*"
            r"! script_waiting_for_input\s*\?\s*"
            r"controller\s*\.take_presentation_event\(\)\s*:\s*"
            r"battle_scene_presentation_event\{\}",
        )
        self.assertIn(
            "if(script_waiting_for_input)",
            loop,
        )

    def test_initial_script_uses_the_original_map_origin_until_resume(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"initial_camera_focus\s*=\s*"
            r"state\.phase\s*==\s*battle_scene_phase::\s*"
            r"script_blocked\s*\?\s*grid_point\{\}\s*:\s*"
            r"state\.cursor",
        )
        self.assertIn(
            "grid_point camera_focus = initial_camera_focus;",
            source,
        )
        self.assertRegex(
            source,
            r"state\.phase\s*!=\s*battle_scene_phase::\s*"
            r"enemy_turn\s*&&\s*state\.phase\s*!=\s*"
            r"battle_scene_phase::\s*script_blocked",
        )

    def test_duel_position_and_facing_are_wired_to_unit_side(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "facing = battle_duel_facing(unit.side);",
            source,
        )
        self.assertRegex(
            source,
            r"battle_duel_facing\(\s*unit\.side\)",
        )
        self.assertIn(
            "battle_duel_screen_x(unit.side);",
            source,
        )
        self.assertNotIn("battle_duel_role", source)

    def test_dialogue_background_uses_exclusive_regular_bg_cohort(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        for token in (
            "bn_regular_bg_items_battle_ui_dialogue_background.h",
            "class battle_dialogue_background_runtime_renderer",
            "battle_dialogue_background_runtime_renderer&",
            "dialogue_background_renderer.update(",
            "dialogue_background_renderer.reset();",
            "ensure_battle_map_background(",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertRegex(
            source,
            r"void update\(\s*bool visible,\s*"
            r"bn::optional<bn::regular_bg_ptr>& map\)",
        )
        dialogue_renderer = source[
            source.index(
                "class battle_dialogue_background_runtime_renderer"
            ):
            source.index(
                "class battle_presentation_message_window_runtime_renderer"
            )
        ]
        self.assertIn("map.reset();", dialogue_renderer)
        self.assertIn("bn::core::update();", dialogue_renderer)
        self.assertRegex(
            dialogue_renderer,
            r"battle_ui_dialogue_background\s*"
            r"\.create_bg\(0,\s*0\)",
        )
        self.assertNotIn("bn::sprite_ptr", dialogue_renderer)
        self.assertNotIn("battle_ui_dialogue_upper_", source)
        self.assertNotRegex(
            source,
            r"map->(?:set_item|set_palette|remove_camera)"
            r"\([\s\S]{0,200}battle_ui_dialogue",
        )

    def test_scene_streams_rom_portrait_slots_instead_of_screenshot_layers(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'generated_battle_presentation_portrait_content.h',
            source,
        )
        self.assertIn(
            'battle_presentation_portrait_renderer.h',
            source,
        )
        self.assertIn("update_script_portraits(", source)
        self.assertIn("update_script_message_window(", source)
        self.assertIn(
            "battle_presentation_portrait_compressed_gfx",
            source,
        )
        self.assertIn("state.script.portraits", source)
        self.assertIn(
            "state.script.message_window_visible",
            source,
        )
        self.assertIn(
            'bn_sprite_items_battle_ui_message_panel.h',
            source,
        )
        self.assertIn(
            'bn_sprite_items_battle_ui_message_black_bar.h',
            source,
        )
        self.assertIn(
            'bn_sprite_items_battle_ui_dialogue_speaker_label.h',
            source,
        )
        script_glyphs = source[
            source.index("void render_script_glyphs("):
            source.index("struct battle_unit_sprite_state")
        ]
        self.assertIn("state.script.speaker", script_glyphs)
        self.assertIn("battle_unit_dialogue_name(", script_glyphs)
        self.assertIn(
            "battle_unit_dialogue_label_graphics_index(",
            script_glyphs,
        )
        self.assertIn(
            "battle_ui_dialogue_speaker_palette",
            script_glyphs,
        )
        self.assertIn(
            "battle_ui_dialogue_text_palette",
            script_glyphs,
        )
        self.assertRegex(
            script_glyphs,
            r"glyph\.row\s*\*\s*16\s*\+\s*48",
        )
        self.assertNotIn("scenario_41_tutorial_portraits", source)

    def test_deployment_telemetry_clears_script_fields(self):
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        start = source.index("void capture_deployment_telemetry(")
        end = source.index("void render_deployment_text(", start)
        function = source[start:end]
        for field in (
            "script_phase",
            "script_selector",
            "script_command_index",
            "script_text_address",
            "script_message_window_visible",
            "script_portrait_0_visible",
            "script_portrait_0_focused",
            "script_portrait_0_id",
            "script_portrait_0_expression",
            "script_portrait_0_motion",
            "script_portrait_1_visible",
            "script_portrait_1_focused",
            "script_portrait_1_id",
            "script_portrait_1_expression",
            "script_portrait_1_motion",
        ):
            self.assertIn(f"output.{field} = 0;", function)

    def test_runtime_telemetry_exports_structured_portrait_state(self):
        header = (
            ROOT / "butano-sequel/game/include/konoha/battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        source = (
            ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        for field in (
            "script_message_window_visible",
            "script_portrait_0_visible",
            "script_portrait_0_focused",
            "script_portrait_0_id",
            "script_portrait_0_expression",
            "script_portrait_0_motion",
            "script_portrait_1_visible",
            "script_portrait_1_focused",
            "script_portrait_1_id",
            "script_portrait_1_expression",
            "script_portrait_1_motion",
        ):
            self.assertIn(f"std::uint32_t {field} = 0;", header)
            self.assertIn(f"output.{field}", source)


if __name__ == "__main__":
    unittest.main()
