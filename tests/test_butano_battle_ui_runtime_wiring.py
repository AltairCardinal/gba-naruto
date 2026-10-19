import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
RUNTIME_HEADER = (
    ROOT / "butano-sequel/game/include/konoha/battle_runtime_scene.h"
)
RESOURCE_HEADER = (
    ROOT
    / "butano-sequel/game/include/konoha/"
    "battle_visual_resource_coordinator.h"
)
FLOW_HEADER = (
    ROOT / "butano-sequel/game/include/konoha/battle_player_action_flow.h"
)
UI_MODEL_HEADER = (
    ROOT / "butano-sequel/game/include/konoha/battle_ui_model.h"
)


class ButanoBattleUiRuntimeWiringTest(unittest.TestCase):
    def test_runtime_uses_dynamic_battle_ui_components(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn('#include "konoha/battle_ui_model.h"', source)
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_panel.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_status_panel.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_status_end.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_palette_items_'
            'battle_ui_map_hint_palette.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_bar.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_action_icon.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_dialog_panel.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_items_'
            'battle_ui_confirmation_cursor.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_large_dialog_panel.h"',
            source,
        )
        self.assertIn(
            '#include "bn_regular_bg_items_'
            'battle_ui_result_background.h"',
            source,
        )
        self.assertIn(
            '#include "bn_sprite_palette_items_'
            'battle_ui_result_total_palette.h"',
            source,
        )
        self.assertNotIn(
            '#include "bn_sprite_items_battle_ui_action_background.h"',
            source,
        )
        self.assertIn(
            '#include "konoha/battle_action_ui_map_projection.h"',
            source,
        )
        self.assertIn(
            '#include "konoha/battle_range_ui_style.h"',
            source,
        )
        self.assertIn("class battle_ui_runtime_renderer", source)
        self.assertRegex(
            source,
            re.compile(r"make_battle_ui_model\(\s*state"),
        )
        self.assertIn("ui_renderer.update(", source)
        self.assertIn("render_battle_ui_text(", source)
        self.assertIn("battle_unit_idle_visual_for(", source)
        self.assertIn("_update_result_participants(result);", source)
        visible_scene = source[
            source.index("run_visible_battle_scene("):
            source.index("\n}\n\nbattle_runtime_scene_exit run_battle_scene(")
        ]
        self.assertIn(
            "bn::sprite_text_generator result_text_generator(\n"
            "            battle_result_sprite_font)",
            visible_scene,
        )
        self.assertIn("battle_character_short_label(", source)
        self.assertIn("result_text_generator", source)
        self.assertIn("_add_dialog_panel();", source)
        self.assertIn("_add_large_dialog_panel();", source)
        self.assertIn(
            "generator.set_palette_item("
            "bn::sprite_items::battle_ui_panel.palette_item())",
            source,
        )
        self.assertRegex(
            source,
            re.compile(
                r"void _add_dialog_panel\(\).*?"
                r"_add_dialog_slice\(-32, 0\);.*?"
                r"_add_dialog_slice\(0, 1\);.*?"
                r"_add_dialog_slice\(32, 2\);",
                re.DOTALL,
            ),
        )
        self.assertIn('"可以吗？"', source)
        self.assertIn('"请选择人物面对的方向"', source)
        self.assertNotIn('"FACING  A OK  B BACK"', source)
        self.assertIn('"使用防御・回避系的"', source)
        self.assertIn('"术・忍具吗？"', source)
        self.assertNotIn('"USE DEFENSE?"', source)
        self.assertNotIn('"A NONE  B SELECT"', source)
        for label in (
            '"移动"',
            '"术・忍具"',
            '"直接攻击"',
            '"查克拉"',
            '"休息"',
            '"行动结束"',
        ):
            self.assertIn(label, source)
        self.assertIn(
            "const int menu_y = -8 - count * 8;",
            source,
        )
        command_text = source[
            source.index("void render_command_menu_text("):
            source.index("void render_action_menu_text(")
        ]
        self.assertRegex(
            command_text,
            re.compile(
                r"bn::sprite_items::battle_ui_command_cursor\s*"
                r"\.create_sprite\(\s*-108,\s*"
                r"menu_y \+ index \* 16\)"
            ),
        )
        self.assertNotIn('"→"', command_text)
        self.assertIn(
            "generator.generate(\n"
            "                -104,\n"
            "                menu_y + index * 16,\n"
            "                command_label(entry.type),",
            command_text,
        )
        self.assertIn(
            '#include "bn_sprite_items_battle_ui_command_cursor.h"',
            source,
        )
        self.assertNotIn(
            "_add_compact_command_menu();",
            source,
        )
        self.assertNotIn("_add_action_background();", source)
        self.assertIn("_add_action_icons(state);", source)
        self.assertIn(
            "battle_action_ui_page_start(",
            source,
        )
        self.assertIn(
            "battle_action_ui_category_icon(",
            source,
        )
        self.assertIn(
            "battle_action_ui_effect_icon(",
            source,
        )
        self.assertIn(
            "bn::sprite_items::battle_ui_action_icon",
            source,
        )
        self.assertIn("_begin_action_palette(", source)
        self.assertIn("_restore_action_palette();", source)
        self.assertIn(
            "static constexpr int range_palette_first_color = 224;",
            source,
        )
        self.assertIn(
            "static constexpr int action_palette_first_color = 240;",
            source,
        )
        self.assertIn("std::array<bn::color, 32>", source)
        self.assertIn("battle_action_ui_map_cell_for(", source)
        self.assertIn("battle_command_ui_map_cell_for(", source)
        self.assertIn("_populate_command_cells(", source)
        self.assertIn(
            "const bool command =",
            source,
        )
        self.assertIn(
            "battle_action_ui_original_pixel(",
            source,
        )
        self.assertIn("bn::color(12, 14, 11)", source)
        self.assertIn(
            "const bool panel = action || command;",
            source,
        )
        self.assertIn("panel ? 0 : 2", source)
        self.assertIn("set_blending_enabled(! panel)", source)
        self.assertIn(
            "battle_range_ui_storage_tile_count> _tiles",
            source,
        )
        self.assertIn("battle_range_ui_pixel_index(", source)
        self.assertIn(
            "state.move_overlay_rows[",
            source,
        )
        self.assertIn(
            "const bool in_move_range =",
            source,
        )
        self.assertIn(
            "state.blocked_overlay_rows[",
            source,
        )
        self.assertNotIn(
            "if(! in_move_range && ! in_range && ! legal_target)",
            source,
        )
        self.assertIn(
            "battle_range_ui_cell_kind(",
            source,
        )
        self.assertIn(
            "bn::blending::set_transparency_weights(",
            source,
        )
        self.assertIn(
            "battle_range_ui_blend_numerator",
            source,
        )
        self.assertNotIn("bn::fixed(0.75)", source)
        for label in (
            '"消耗查克拉"',
            '"攻击力"',
            '"距离"',
            '"范围"',
            '"成功率"',
            '"攻击对象受到的伤害"',
            '"START"',
            '"攻击指令"',
        ):
            self.assertIn(label, source)
        self.assertNotIn('"体攻"', source)
        self.assertIn('"体力"', source)
        for label in (
            '"本体"',
            '"待机"',
            '"能力"',
            '"查克拉"',
        ):
            self.assertIn(label, source)
        result_layer = source[
            source.index("case battle_ui_layer::result:"):
            source.index("case battle_ui_layer::level_up:")
        ]
        # Fixed result labels are part of the exact state-free BG3 panel.
        # Participant names and every score remain runtime projections.
        for result_label in (
            '"经验值"',
            '"任务分"',
            '"战斗分"',
            '"回合分"',
            '"合计"',
        ):
            self.assertNotIn(result_label, result_layer)
        self.assertIn(
            "bn_regular_bg_items_battle_ui_result_panel.h",
            source,
        )
        for obsolete_result_label in (
            '"BATTLE RESULT"',
            '"MISSION  "',
            '"BATTLE   "',
            '"ROUND    "',
            '"TOTAL    "',
            '"A NEXT"',
        ):
            self.assertNotIn(
                obsolete_result_label,
                result_layer,
            )
        self.assertIn("_add_result_background();", source)
        self.assertIn("_update_result_participants(", source)
        self.assertRegex(
            source,
            re.compile(
                r"battle_phase_uses_full_screen_result\(\s*"
                r"state\.phase\)\s*&&\s*map.*?"
                r"range_overlay\.reset\(\);.*?"
                r"map\.reset\(\);.*?"
                r"bn::core::update\(\);",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"cursor_visible\s*=.*?"
                r"battle_scene_phase::\s*command_selection",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"state\.target_confirmation_yes.*?"
                r"_add_confirmation_cursor",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"void _add_confirmation_cursor"
                r"\(bool confirmation_yes\).*?"
                r"battle_ui_confirmation_cursor.*?"
                r"confirmation_yes\s*\?\s*-24\s*:\s*-8",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"generator\.set_left_alignment\(\);.*?"
                r'generator\.generate\(\s*-32,\s*-40,\s*"可以吗？"',
                re.DOTALL,
            ),
        )
        confirmation = source[
            source.index("case battle_ui_layer::confirmation:"):
            source.index(
                "else if(state.phase ==",
                source.index("case battle_ui_layer::confirmation:"),
            )
        ]
        self.assertNotIn('"→"', confirmation)

    def test_ui_has_a_reserved_oam_budget(self):
        header = RUNTIME_HEADER.read_text(encoding="utf-8")
        self.assertIn("maximum_ui_sprites = 16", header)
        self.assertIn("ui_sprites", header)

    def test_scene_uses_one_resource_coordinator_for_palette_handoffs(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn(
            '#include "konoha/battle_visual_resource_coordinator.h"',
            source,
        )
        self.assertIn("resource_coordinator.transition_to(", source)
        self.assertIn("apply_visual_resource_transition(", source)
        self.assertNotIn("presentation_palette_handoff", source)

    def test_portrait_helpers_do_not_manage_map_resource_lifetimes(self):
        source = SCENE.read_text(encoding="utf-8")
        combat_helper = source[
            source.index("[[nodiscard]] bool update_combat_portrait("):
            source.index("void apply_visual_resource_transition(")
        ]
        self.assertNotIn("unit_sprites", combat_helper)
        self.assertNotIn("bn::core::update()", combat_helper)
        script_helper = source[
            source.index("void update_script_portraits("):
            source.index("[[nodiscard]] bool update_combat_portrait(")
        ]
        self.assertNotIn("unit_sprites", script_helper)
        self.assertNotIn("bn::core::update()", script_helper)

    def test_resource_contract_makes_map_ui_and_portraits_exclusive(self):
        header = RESOURCE_HEADER.read_text(encoding="utf-8")
        self.assertIn("battle_visual_resource_cohort", header)
        self.assertIn("commit_before_allocate", header)
        self.assertIn("map_ui", header)
        self.assertIn("map_cursor", header)
        self.assertIn("script_message_window", header)
        self.assertIn("combat_stage", header)
        self.assertIn("portrait", header)

    def test_cursor_is_owned_by_the_map_resource_cohort(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn(
            "bn::optional<bn::sprite_ptr> cursor_shadow",
            source,
        )
        self.assertIn("cursor_shadow.reset();", source)
        self.assertIn("cursor.reset();", source)
        self.assertIn("ensure_map_cursor(", source)

    def test_script_message_window_is_released_by_the_coordinator(self):
        source = SCENE.read_text(encoding="utf-8")
        coordinator = source[
            source.index("void apply_visual_resource_transition("):
            source.index("void ensure_map_cursor(")
        ]
        self.assertIn("message_window_renderer.reset();", coordinator)
        self.assertIn("combat_stage_renderer.reset();", coordinator)

    def test_resource_handoff_and_frame_end_do_not_double_commit(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            re.compile(
                r"visual_resources_committed\s*=\s*"
                r"resource_transition\.commit_before_allocate"
            ),
        )
        self.assertRegex(
            source,
            re.compile(
                r"if\(! visual_resources_committed\)\s*"
                r"\{\s*bn::core::update\(\);"
            ),
        )

    def test_command_snapshot_exposes_real_visible_entries(self):
        source = FLOW_HEADER.read_text(encoding="utf-8")
        self.assertIn("command_entries = {}", source)
        self.assertIn(
            "_state.command_entries[index] =",
            source,
        )

    def test_status_values_leave_room_for_dynamic_bars(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn("constexpr int status_value_x = 112;", source)

    def test_action_menu_text_separates_compact_details_from_full_height_actions(self):
        source = SCENE.read_text(encoding="utf-8")
        action = source[
            source.index("void render_action_menu_text("):
            source.index("void render_unit_cycle_hint(")
        ]
        for expected in (
            'const char* cost_label = "消耗查克拉";',
            'action_generator.generate(40, -48, "攻击力", sprites);',
            'action_generator.generate(40, -32, "距离", sprites);',
            'action_generator.generate(40, -16, "范围", sprites);',
            'action_generator.generate(40, 16, "成功率", sprites);',
            "battle_action_ui_page_start(",
            "constexpr int page_size = 4;",
            "const int row_y = -32 + row * 16;",
            "-112, row_y, entry_name, sprites);",
            "action_generator.generate(",
            "-112, 48, action_name, sprites);",
            '"攻击对象受到的伤害"',
            '56, 48, "攻击指令", sprites);',
            '96, 64, "返回", sprites);',
        ):
            self.assertIn(expected, action)
        self.assertNotIn('"START 攻击指令"', action)
        self.assertNotIn('"B 返回"', action)
        self.assertNotIn('"START", sprites', action)
        self.assertNotIn('"B", sprites', action)
        self.assertNotIn('"→", sprites', action)
        self.assertNotIn('"体力", sprites', action)
        self.assertNotIn('"查克拉", sprites', action)
        self.assertIn(
            "bn::sprite_items::battle_ui_action_cursor",
            action,
        )
        self.assertIn(
            "bn::sprite_items::battle_ui_action_start_hint",
            action,
        )
        self.assertIn(
            "bn::sprite_items::battle_ui_action_back_hint",
            action,
        )
        self.assertIn(
            "bn::sprite_items::battle_ui_action_actor_stats",
            action,
        )
        self.assertIn(
            ".create_sprite(-24, -64)",
            action,
        )
        self.assertIn(
            "battle_unit_identity(actor->character_id)",
            action,
        )
        self.assertIn(
            "action_generator.generate(40, -64, cost_label, sprites);",
            action,
        )
        self.assertRegex(
            action,
            re.compile(
                r"action_generator\.generate\(\s*72,\s*-32,"
            ),
        )
        self.assertRegex(
            action,
            re.compile(
                r"action_generator\.generate\(\s*72,\s*-16,"
            ),
        )
        self.assertRegex(
            action,
            re.compile(
                r"action_generator\.generate\(\s*72,\s*16,"
            ),
        )
        actor_block = action[
            action.index("if(actor)"):
            action.index("const int page_start")
        ]
        self.assertNotIn(
            "battle_ui_text_accent_palette",
            actor_block,
        )
        self.assertRegex(
            action,
            re.compile(
                r"action_generator\.set_palette_item\(\s*"
                r"bn::sprite_palette_items::\s*"
                r"battle_ui_text_warning_palette\);"
            ),
        )
        self.assertRegex(
            action,
            re.compile(
                r"generator\.generate\(\s*24,\s*-64,\s*"
                r"bn::to_string<8>\(actor->hp\)"
            ),
        )
        self.assertRegex(
            action,
            re.compile(
                r"generator\.generate\(\s*24,\s*-56,\s*"
                r"bn::to_string<4>\(actor->chakra\)"
            ),
        )
        self.assertIn('"消耗体力"', action)
        self.assertNotIn('"体攻"', action)

    def test_status_bars_match_original_order_and_spacing(self):
        source = SCENE.read_text(encoding="utf-8")
        status_panel = source[
            source.index("if(model.show_status_panel && status_unit)"):
            source.index("if(model.show_round_badge)")
        ]
        self.assertRegex(
            status_panel,
            re.compile(
                r"_add_bar\(\s*64,\s*60,\s*"
                r"status_unit->hp,\s*status_unit->max_hp,\s*2\)"
            ),
        )
        self.assertRegex(
            status_panel,
            re.compile(
                r"_add_bar\(\s*64,\s*68,\s*"
                r"status_unit->chakra,\s*"
                r"status_unit->max_chakra,\s*1\)"
            ),
        )
        status_text = source[
            source.index("void render_status_panel_text("):
            source.index("void render_round_badge_text(")
        ]
        for expected in (
            "generator.generate(-112, 64, identity, sprites);",
            'generator.generate(-16, 64, "待机", sprites);',
            'generator.generate(-48, 64, "本体", sprites);',
        ):
            self.assertIn(expected, status_text)
        self.assertIn(
            'generator.generate(16, 64, "能力", sprites);',
            status_text,
        )
        self.assertIn(
            'generator.generate(16, 72, "查克拉", sprites);',
            status_text,
        )
        self.assertRegex(
            status_text,
            re.compile(
                r"generator\.generate\(\s*status_value_x,\s*64,\s*"
                r"hp,\s*sprites\)"
            ),
        )
        self.assertRegex(
            status_text,
            re.compile(
                r"generator\.generate\(\s*status_value_x,\s*72,\s*"
                r"chakra,\s*sprites\)"
            ),
        )

    def test_unit_renderer_uses_move_preview_projection(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn(
            '#include "konoha/battle_map_visual_projection.h"',
            source,
        )
        self.assertIn(
            '#include "konoha/battle_ui_sprite_font.h"',
            source,
        )
        self.assertIn(
            '#include "konoha/battle_action_menu_sprite_font.h"',
            source,
        )
        self.assertIn("battle_ui_sprite_font", source)
        self.assertIn("battle_action_menu_sprite_font", source)
        self.assertNotIn(
            "combat_stage ? 2 : 1",
            source,
        )
        self.assertIn(
            "constexpr int combat_sprite_scale = 1;",
            source,
        )
        action_renderer = source[
            source.index("void render_action_menu_text("):
            source.index("void render_unit_cycle_hint(")
        ]
        self.assertIn(
            "battle_unit_identity(actor->character_id)",
            action_renderer,
        )
        self.assertIn(
            "bn::sprite_text_generator& action_generator",
            action_renderer,
        )
        self.assertIn("battle_range_overlay", source)
        self.assertIn("static constexpr int columns = 32;", source)
        self.assertIn("static constexpr int rows = 32;", source)
        self.assertIn("world_x(point) - camera.x()", source)
        self.assertIn("world_y(point) - camera.y()", source)
        self.assertNotIn("_bg->set_camera(camera)", source)
        self.assertIn("map_bg.palette()", source)
        self.assertIn("bn::bpp_mode::BPP_8", source)
        self.assertNotIn("_nearest_color(", source)
        self.assertIn("battle_range_ui_tile_index(", source)
        self.assertIn(
            "_begin_action_palette(",
            source,
        )
        self.assertIn("_begin_action_palette(map_bg.palette())", re.sub(r"\s+", " ", source))
        self.assertNotIn(
            "bn_bg_palette_items_battle_range_overlay_palette.h",
            source,
        )
        self.assertIn("update_range_overlay(", source)
        self.assertRegex(
            source,
            re.compile(
                r"battle_facing_indicator_graphics_index\(\s*"
                r"battle_map_cursor_facing\(\s*state\s*\),\s*"
                r"scene_frame\s*\)"
            ),
        )
        self.assertRegex(
            source,
            re.compile(r"battle_map_cursor_facing\(\s*state\s*\)"),
        )
        self.assertNotIn("cursor->set_rotation_angle(", source)
        self.assertIn("battle_map_visual_position(", source)
        unit_selection_case = source[
            source.index(
                "case battle_scene_phase::unit_selection:",
                source.index("case battle_ui_layer::map_status:"),
            ):
            source.index(
                "case battle_scene_phase::facing_selection:",
                source.index("case battle_ui_layer::map_status:"),
            )
        ]
        self.assertNotIn(
            "render_unit_cycle_hint(",
            unit_selection_case,
        )

    def test_story_glyphs_use_readable_uncropped_spacing(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn(
            '#include "konoha/battle_preparation_sprite_font.h"',
            source,
        )
        self.assertIn(
            "bn::sprite_text_generator story_text_generator("
            "\n            battle_preparation_sprite_font);",
            source,
        )
        self.assertRegex(
            source,
            re.compile(r"glyph\.column\s*\*\s*8"),
        )
        self.assertRegex(
            source,
            re.compile(r"glyph\.row\s*\*\s*16"),
        )
        glyph_renderer = source[
            source.index("void render_script_glyphs("):
            source.index("struct battle_unit_sprite_state")
        ]
        self.assertIn("story_text_generator", glyph_renderer)
        self.assertRegex(
            glyph_renderer,
            re.compile(
                r"story_text_generator\.generate\(\s*-100,\s*33,\s*"
                r"dialogue_name"
            ),
        )
        self.assertIn(
            "battle_unit_dialogue_name(",
            glyph_renderer,
        )
        self.assertRegex(
            glyph_renderer,
            re.compile(
                r"battle_presentation_glyphs\s*"
                r"\.create_sprite\(\s*-92\s*\+.*?"
                r"glyph\.row\s*\*\s*16\s*\+\s*48",
                re.DOTALL,
            ),
        )
        self.assertNotIn("affine_mat", glyph_renderer)
        self.assertNotIn("set_scale", glyph_renderer)

    def test_target_status_uses_a_dedicated_original_glyph_role(self):
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn(
            '#include "konoha/battle_target_status_sprite_font.h"',
            source,
        )
        self.assertIn(
            '#include "konoha/battle_target_metrics_sprite_font.h"',
            source,
        )
        self.assertIn(
            "bn::sprite_text_generator target_status_text_generator("
            "\n            battle_target_status_sprite_font);",
            source,
        )
        self.assertIn(
            "bn::sprite_text_generator target_metrics_text_generator("
            "\n            battle_target_metrics_sprite_font);",
            source,
        )
        target_status_renderer = source[
            source.index("void render_status_panel_text("):
            source.index("[[nodiscard]] const char* battle_character_short_label")
        ]
        self.assertIn(
            "bn::sprite_text_generator& target_status_generator",
            target_status_renderer,
        )
        self.assertIn(
            "bn::sprite_text_generator& target_metrics_generator",
            target_status_renderer,
        )
        expanded = target_status_renderer[
            target_status_renderer.index(
                "if(expanded_target_status)"
            ):
            target_status_renderer.index(
                "\n    generator.set_left_alignment()"
            )
        ]
        self.assertNotIn("detail_generator", expanded)
        self.assertGreaterEqual(
            expanded.count("target_status_generator.generate("),
            6,
        )
        self.assertGreaterEqual(
            expanded.count("target_metrics_generator.generate("),
            10,
        )

    def test_target_preview_keeps_range_and_uses_expanded_status_panel(self):
        source = SCENE.read_text(encoding="utf-8")
        overlay = source[
            source.index("class battle_range_overlay"):
            source.index("void update_range_overlay(")
        ]
        self.assertIn("target_preview", overlay)
        self.assertIn("target_confirmation", overlay)
        self.assertIn("_populate_target_status_cells()", overlay)
        self.assertIn(
            "battle_target_status_ui_map_cell_for(",
            overlay,
        )
        self.assertIn("_status_bg", overlay)
        self.assertIn("_status_map", overlay)

        renderer = source[
            source.index("class battle_ui_runtime_renderer"):
            source.index("class battle_range_overlay")
        ]
        self.assertIn(
            "const bool expanded_target_status =",
            renderer,
        )
        self.assertRegex(
            renderer,
            re.compile(
                r"if\(expanded_target_status\).*?"
                r"_add_bar\(\s*64,\s*44,"
                r".*?_add_bar\(\s*64,\s*52,"
                r".*?status_unit->max_chakra,\s*1,\s*3\)",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            renderer,
            re.compile(
                r"else\s*\{.*?"
                r"_add_bar\(\s*64,\s*60,"
                r".*?_add_bar\(\s*64,\s*68,",
                re.DOTALL,
            ),
        )

        status_text = source[
            source.index("void render_status_panel_text("):
            source.index("void render_round_badge_text(")
        ]
        for expected in (
            '"伤害"',
            '"成功率"',
            '"攻"',
            '"防"',
            '"快"',
            ".damage_per_hit",
            ".success_rate_percent",
            "unit->attack",
            "unit->defense",
            "unit->agility",
        ):
            self.assertIn(expected, status_text)
        expanded = status_text[
            status_text.index("if(expanded_target_status)"):
            status_text.index(
                "\n    generator.set_left_alignment();",
                status_text.index("if(expanded_target_status)"),
            )
        ]
        self.assertIn(
            "battle_ui_text_warning_palette",
            expanded,
        )
        self.assertIn(
            "battle_ui_panel\n                                .palette_item()",
            expanded,
        )
        self.assertNotIn(
            "battle_ui_text_accent_palette",
            expanded,
        )

    def test_status_hud_uses_bar_palette_and_phase_labels(self):
        source = SCENE.read_text(encoding="utf-8")
        renderer = source[
            source.index("class battle_ui_runtime_renderer"):
            source.index("class battle_range_overlay")
        ]
        status = source[
            source.index("void render_status_panel_text("):
            source.index("void render_round_badge_text(")
        ]

        self.assertIn(
            "bn::optional<bn::sprite_palette_ptr> _bar_palette",
            renderer,
        )
        self.assertIn(
            "bn::optional<bn::sprite_palette_ptr> "
            "_status_panel_palette",
            renderer,
        )
        self.assertRegex(
            renderer,
            re.compile(
                r"battle_ui_bar\s*\.palette_item\(\)"
                r"\s*\.create_palette\(\)"
            ),
        )
        self.assertIn("*_bar_palette", renderer)
        self.assertRegex(
            renderer,
            re.compile(
                r"battle_ui_status_panel\s*\.palette_item\(\)"
                r"\s*\.create_palette\(\)"
            ),
        )
        self.assertRegex(
            status,
            re.compile(
                r"battle_ui_status_end\s*"
                r"\.create_sprite\(\s*-8,\s*64\s*\)"
            ),
        )
        self.assertIn('"待机"', status)
        self.assertIn('"能力"', status)
        self.assertIn('"体力"', status)
        compact_status = status[
            status.index(
                "\n    generator.set_left_alignment();",
                status.index("if(expanded_target_status)"),
            ):
        ]
        self.assertNotIn(
            "battle_ui_text_warning_palette",
            compact_status,
        )
        self.assertNotIn('"体力"', compact_status)
        self.assertRegex(
            status,
            re.compile(
                r"generate\(\s*16,\s*64,\s*\"能力\""
            ),
        )
        self.assertRegex(
            status,
            re.compile(
                r"generate\(\s*16,\s*72,\s*\"查克拉\""
            ),
        )
        horizontal_panel = renderer[
            renderer.index("void _add_horizontal_panel("):
            renderer.index("void _add_dialog_panel(")
        ]
        for graphics_index, x in enumerate((-88, -24, 40, 104)):
            self.assertIn(
                f"_add_status_panel({x}, y, {graphics_index})",
                horizontal_panel,
            )
        self.assertNotIn("_add_panel(", horizontal_panel)

    def test_map_selection_uses_original_unit_cycle_hint_without_debug_prompts(self):
        source = SCENE.read_text(encoding="utf-8")
        renderer = source[
            source.index("void render_battle_ui_text("):
            source.index("void render_script_glyphs(")
        ]

        self.assertIn("void render_unit_cycle_hint(", source)
        self.assertIn('"SELECT人物"', source)
        hint = source[
            source.index("void render_unit_cycle_hint("):
            source.index("void render_battle_ui_text(")
        ]
        self.assertRegex(
            hint,
            re.compile(
                r"bn::sprite_palette_items::\s*"
                r"battle_ui_map_hint_palette"
            ),
        )
        self.assertRegex(
            hint,
            re.compile(
                r"bn::sprite_items::battle_ui_panel\s*"
                r"\.palette_item\(\)"
            ),
        )
        # The original entry/unit-selection frame has no top hint.  It is
        # shown only after entering move or target selection.
        self.assertEqual(
            renderer.count("render_unit_cycle_hint("),
            2,
        )
        for debug_prompt in (
            'bn::string<64> prompt = "MOVE "',
            'bn::string<64> prompt = "TARGET "',
            '"A CONFIRM  B BACK"',
            '"A SELECT UNIT"',
            '"D-PAD/L/R UNIT"',
        ):
            with self.subTest(debug_prompt=debug_prompt):
                self.assertNotIn(debug_prompt, renderer)

    def test_successful_input_clears_rejection_feedback(self):
        model = UI_MODEL_HEADER.read_text(encoding="utf-8")
        source = SCENE.read_text(encoding="utf-8")
        self.assertIn("battle_ui_rejection_latch", model)
        self.assertIn("if(input_success)", model)
        self.assertIn("rejection.update(", source)
        self.assertIn("rejection.visible", source)
        self.assertNotIn("int rejected_frames", source)


if __name__ == "__main__":
    unittest.main()
