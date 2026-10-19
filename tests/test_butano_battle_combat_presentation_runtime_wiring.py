import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_runtime_scene.cpp"
)
PRESENTATION_HEADER = (
    ROOT
    / "butano-sequel"
    / "game"
    / "include"
    / "konoha"
    / "battle_combat_presentation.h"
)
RUNTIME_SCRIPT = (
    ROOT
    / "tools"
    / "butano"
    / "mgba_battle_09_character_actions.lua"
)


class BattleCombatPresentationRuntimeWiringTest(unittest.TestCase):
    def test_target_phases_telemetry_expose_the_preview_rejection(self):
        source = SOURCE.read_text(encoding="utf-8")
        normalized = " ".join(source.split())
        self.assertIn(
            "state.phase == battle_scene_phase:: target_selection || "
            "state.phase == battle_scene_phase:: target_preview || "
            "state.phase == battle_scene_phase:: target_confirmation ? "
            "state.player.target_preview.error : "
            "state.player.action_selection_error",
            normalized,
        )

    def test_battle_09_runtime_fixture_exposes_the_damage_bomb_route(self):
        source = SOURCE.read_text(encoding="utf-8")
        fixture = source.split(
            "battle_runtime_scene_exit run_battle_09_scene()",
            1,
        )[1].split(
            "battle_runtime_scene_exit run_battle_11_scene()",
            1,
        )[0]
        self.assertIn(
            "request.load_policy."
            "character_equipped_tools[2][0] = 49",
            " ".join(fixture.split()),
        )

    def test_opponent_bomb_tools_use_a_semantic_combat_transaction(self):
        header = PRESENTATION_HEADER.read_text(encoding="utf-8")
        classifier = header.split(
            "battle_combat_is_opponent_bomb_tool(",
            1,
        )[1].split(
            "namespace detail",
            1,
        )[0]
        normalized = " ".join(classifier.split())

        for token in (
            "animation_family == 5",
            "target_policy_kind::opponent_unit",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)
        for forbidden in (
            "action.id",
            "character_id",
            "battle_id",
            "screenshot",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, classifier)

        tool_routes = header.split(
            "make_tool_presentations()",
            1,
        )[1].split(
            "inline constexpr std::array<",
            1,
        )[0]
        normalized_routes = " ".join(tool_routes.split())
        self.assertIn(
            "battle_combat_is_opponent_bomb_tool(action)",
            normalized_routes,
        )
        self.assertIn(
            "battle_combat_presentation_kind:: bomb_tool",
            normalized_routes,
        )
        self.assertIn(
            "make_technique_presentation(",
            tool_routes,
        )

    def test_opponent_control_uses_a_semantic_combat_transaction(self):
        header = PRESENTATION_HEADER.read_text(encoding="utf-8")
        classifier = header.split(
            "battle_combat_is_opponent_control_technique(",
            1,
        )[1].split(
            "namespace detail",
            1,
        )[0]
        normalized = " ".join(classifier.split())

        for token in (
            "animation_family != 5",
            "target_policy_kind::opponent_unit",
            "action.effect.code == 14",
            "action.effect.code == 15",
            "action.effect.code == 63",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)
        for forbidden in (
            "action.id",
            "character_id",
            "battle_id",
            "screenshot",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, classifier)

        active_routes = header.split(
            "make_active_presentations()",
            1,
        )[1].split(
            "make_tool_presentations()",
            1,
        )[0]
        self.assertIn(
            "battle_combat_presentation_kind:: "
            "control_technique",
            " ".join(active_routes.split()),
        )
        self.assertIn(
            "make_technique_presentation(",
            active_routes,
        )

    def test_message_window_uses_opaque_original_style_panel_slices(self):
        source = SOURCE.read_text(encoding="utf-8")
        renderer_source = source.split(
            "class battle_presentation_message_window_runtime_renderer",
            1,
        )[1].split(
            "class battle_combat_stage_runtime_renderer",
            1,
        )[0]
        normalized = " ".join(renderer_source.split())

        for token in (
            "sprite.set_bg_priority(2)",
            "sprite.set_z_order(1000)",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)
        self.assertRegex(
            normalized,
            r"bn::sprite_items::\s*battle_ui_message_panel",
        )
        self.assertRegex(
            normalized,
            r"bn::sprite_items::\s*battle_ui_message_black_bar",
        )
        self.assertRegex(
            normalized,
            r"create_sprite\(\s*-90\s*\+\s*"
            r"static_cast<int>\(\s*index\)\s*\*\s*60,\s*48,\s*"
            r"static_cast<int>\(\s*index\)\)",
        )
        self.assertNotIn("set_blending_enabled(true)", renderer_source)
        self.assertNotIn("bn::blending::", renderer_source)

    def test_runtime_renders_combat_transaction_outside_the_map(self):
        source = SOURCE.read_text(encoding="utf-8")
        normalized = " ".join(source.split())

        for token in (
            '#include "konoha/battle_combat_presentation.h"',
            '#include "konoha/battle_actor_choreography.h"',
            "class battle_combat_stage_runtime_renderer",
            "combat.map_visible()",
            "presentation.combat().title_visible()",
            "combat.movie_visible()",
            "update_combat_portrait",
            "battle_combat_presentation_resource:: "
            "action_16_fire_movie_components",
            "combat.effect_visible()",
            "combat.actor_visible()",
            "battle_actor_choreography_for(",
            "choreography.screen_anchor_x",
            "choreography.visible",
            "combat.target_visible()",
            "combat.hud_visible()",
            '#include "bn_regular_bg_items_battle_duel_forest.h"',
            '#include "bn_regular_bg_items_battle_duel_hud_shell.h"',
            '#include "bn_sprite_items_battle_ui_bar.h"',
            '#include "konoha/battle_duel_status_sprite_font.h"',
            '#include "konoha/generated_battle_action_05_effect_content.h"',
            '#include "konoha/generated_battle_action_05_effect_items.h"',
            '#include "konoha/generated_battle_action_05_dust_effect_content.h"',
            '#include "konoha/generated_battle_action_05_dust_effect_items.h"',
            '#include "konoha/generated_battle_action_16_fire_effect_content.h"',
            '#include "konoha/generated_battle_action_16_fire_effect_items.h"',
            '#include "konoha/generated_battle_ninja_tool_bomb_projectile_content.h"',
            '#include "konoha/generated_battle_ninja_tool_bomb_projectile_items.h"',
            '#include "konoha/generated_battle_ninja_tool_bomb_smoke_content.h"',
            '#include "konoha/generated_battle_ninja_tool_bomb_smoke_items.h"',
            '#include "konoha/generated_battle_action_16_movie_runtime_content.h"',
            '#include "bn_regular_bg_items_battle_action_16_movie_actor.h"',
            '#include "bn_regular_bg_items_battle_action_16_movie_fire.h"',
            '#include "bn_regular_bg_items_battle_action_16_movie_streaks.h"',
            '#include "bn_regular_bg_items_battle_action_16_movie_dialogue.h"',
            '#include "bn_regular_bg_items_battle_action_16_cutin_portrait.h"',
            '#include "bn_regular_bg_items_battle_action_16_cutin_dialogue.h"',
            '#include "bn_rect_window.h"',
            '#include "bn_window.h"',
            '#include "bn_sprite_items_battle_action_16_movie_title_0.h"',
            "battle_duel_forest .create_bg(8, 80)",
            "map->set_position(8, 80)",
            "bn::optional<bn::regular_bg_ptr>& map",
            "_release_background_before_bpp_transition(",
            "map.reset()",
            "bn::core::update()",
            "battle_action_16_movie_streaks .create_bg(8, 48)",
            "_duel_background_bound",
            "_update_action_16_movie",
            "_update_action_16_cutin",
            "action_16_fire_cutin_components",
            "_cutin_portrait_bg",
            "_cutin_dialogue_bg",
            "136 - portrait_scroll",
            "_cutin_palette = _cutin_dialogue_bg->palette()",
            "battle_action_16_cutin_palette",
            "_cutin_palette->set_color(",
            "cutin_fade_window.set_boundaries( -48, -120, 32, 120)",
            "bn::window::outside().set_show_blending( false)",
            "bn::window::outside().set_show_blending( "
            "_previous_outside_window_blending)",
            "_cutin_portrait_bg ->set_blending_top_enabled(",
            "bn::blending::set_white_fade_color()",
            "bn::blending::set_fade_alpha(",
            "battle_action_16_movie_fire_palettes",
            "battle_action_16_movie_blend_top_weights",
            "battle_action_16_movie_blend_bottom_weights",
            "_movie_palette = map->palette()",
            "_movie_fire_bg->set_palette(*_movie_palette)",
            "_movie_palette->set_color(",
            "_movie_fire_bg->set_blending_top_enabled(",
            "_movie_actor_bg->set_blending_bottom_enabled(",
            "streaks.set_blending_bottom_enabled(",
            "bn::blending::set_transparency_weights(",
            "append_combatant_hp",
            "_update_duel_hud(",
            "_duel_hud_background",
            "_duel_bar_sprites",
            "battle_duel_hud_shell",
            "_duel_hp_track_tiles",
            "_duel_hp_fill_tiles",
            "_duel_chakra_track_tiles",
            "_duel_chakra_fill_tiles",
            "_duel_bar_palette",
            "combat.displayed_actor_hp()",
            "combat.displayed_target_hp()",
            "player->chakra",
            "enemy->chakra",
            "action_generator.generate( -104, -64, action, sprites)",
            "bn::sprite_text_generator& action_generator",
            "bn::sprite_items:: battle_ui_panel .palette_item()",
            "combat.title_visible() || combat.movie_visible() || "
            "combat.hud_visible()",
            "action_generator.generate( -104, 48, player_name, sprites)",
            "action_generator.generate( 16, 48, enemy_name, sprites)",
            "combat_sprite_scale",
            "sprite->set_scale(",
            "current_impact_index()",
            "battle_combat_presentation_resource:: action_05_hit_sequence",
            "_update_effect_sequence(",
            "battle_action_05_dust_sequence",
            "battle_action_05_dust_sprite_items",
            "battle_action_05_hit_sequence",
            "battle_action_16_fire_hit_sequence",
            "battle_action_16_fire_hit_sprite_items",
            "ninja_tool_bomb_projectile_sequence",
            "battle_ninja_tool_bomb_projectile_sequence",
            "battle_ninja_tool_bomb_projectile_sprite_items",
            "ninja_tool_bomb_smoke_sequence",
            "battle_ninja_tool_bomb_smoke_sequence",
            "battle_ninja_tool_bomb_smoke_sprite_items",
            "component.semi_transparent",
            "sprite->set_blending_enabled(",
            "items[ component.asset_index]",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)

    def test_duel_hud_uses_role_specific_text_and_two_live_resource_bars(self):
        source = SOURCE.read_text(encoding="utf-8")
        normalized = " ".join(source.split())
        render = source.split("void render_text(", 1)[1].split(
            "void render_command_menu_text(", 1
        )[0]
        value_renderer = source.split(
            "void render_duel_resource_value(", 1
        )[1].split("void render_text(", 1)[0]
        renderer = source.split(
            "class battle_combat_stage_runtime_renderer", 1
        )[1].split("void capture_deployment_telemetry(", 1)[0]

        self.assertIn(
            "bn::sprite_text_generator duel_status_text_generator( "
            "battle_duel_status_sprite_font)",
            normalized,
        )
        self.assertIn(
            "bn::sprite_text_generator& duel_status_generator",
            render,
        )
        self.assertRegex(
            render,
            r"action_generator\.generate\(\s*-104,\s*48,\s*"
            r"player_name",
        )
        self.assertRegex(
            render,
            r"action_generator\.generate\(\s*16,\s*48,\s*enemy_name",
        )
        self.assertIn(
            "generator.generate(",
            value_renderer,
        )
        self.assertNotIn(
            "generator.generate(\n                        112, 56",
            render,
        )
        self.assertIn(
            "std::array<bn::optional<bn::sprite_ptr>, 8> "
            "_duel_bar_sprites",
            " ".join(renderer.split()),
        )
        for call in (
            "_update_duel_bar( 0, player_bar_x, 60, player_hp",
            "_update_duel_bar( 2, player_bar_x, 68, player ? "
            "player->chakra : 0",
            "_update_duel_bar( 4, 32, 60, enemy_hp",
            "_update_duel_bar( 6, 32, 68, enemy ? enemy->chakra : 0",
        ):
            with self.subTest(call=call):
                self.assertIn(call, " ".join(renderer.split()))
        self.assertNotIn(
            'output += "HP ";',
            source[
                source.index("void append_combatant_hp("):
                source.index("class battle_ui_runtime_renderer")
            ],
        )
        duel_text_source = source.split(
            "void render_text(",
            1,
        )[1].split(
            "void render_training_text(",
            1,
        )[0]
        self.assertIn(
            "action_generator.set_palette_item( "
            "bn::sprite_items:: battle_ui_panel .palette_item())",
            " ".join(duel_text_source.split()),
        )
        self.assertNotIn(
            "\n            generator.generate(\n"
            "                    -104,\n"
            "                    -64,\n"
            "                    action,",
            duel_text_source,
        )
        self.assertNotIn(
            "bn_sprite_items_battle_duel_title_panel",
            source,
        )
        self.assertNotIn(
            "bn_sprite_items_battle_duel_status_panels",
            source,
        )
        renderer_source = source.split(
            "class battle_combat_stage_runtime_renderer",
            1,
        )[1].split(
            "void update_script_message_window",
            1,
        )[0]
        self.assertNotIn("_divider_sprites", renderer_source)
        self.assertNotIn("_divider_tiles", renderer_source)
        self.assertNotIn("0x44444444U", renderer_source)
        self.assertNotIn("_write_backdrop_tiles", renderer_source)
        self.assertNotIn("_backdrop_tiles", renderer_source)
        self.assertNotIn("const int streak =", renderer_source)
        self.assertIn(
            "std::array< bn::optional<bn::sprite_ptr>, "
            "battle_effect_maximum_components> "
            "_action_effect_sprites",
            " ".join(renderer_source.split()),
        )
        self.assertNotIn("scenario_41_attack_frame_", renderer_source)
        self.assertNotIn("_write_fire_tiles", renderer_source)
        self.assertNotIn("_fire_tiles", renderer_source)
        self.assertNotIn("_fire_sprites", renderer_source)
        self.assertNotIn(
            "map.set_item( bn::regular_bg_items:: "
            "battle_action_16_cutin_dialogue)",
            " ".join(renderer_source.split()),
        )
        cutin_update = renderer_source.split(
            "void _update_action_16_cutin",
            1,
        )[1].split(
            "void _release_action_16_movie_resources",
            1,
        )[0]
        self.assertNotIn(
            "bn::bg_palettes::set_fade",
            cutin_update,
        )

    def test_runtime_distinguishes_single_actor_and_versus_stages(self):
        source = SOURCE.read_text(encoding="utf-8")
        renderer_source = source.split(
            "class battle_combat_stage_runtime_renderer",
            1,
        )[1].split(
            "void update_script_message_window",
            1,
        )[0]
        normalized_renderer = " ".join(renderer_source.split())
        render_text_source = source.split(
            "void render_text(",
            1,
        )[1].split(
            "void render_training_text(",
            1,
        )[0]
        normalized_text = " ".join(render_text_source.split())
        unit_sprite_source = source.split(
            "void update_unit_sprites(",
            1,
        )[1].split(
            "void update_cursor_sprites(",
            1,
        )[0]
        normalized_unit_sprites = " ".join(
            unit_sprite_source.split()
        )

        self.assertNotIn("_divider_sprites", normalized_renderer)
        self.assertIn(
            "combat.single_actor_stage()",
            normalized_text,
        )
        self.assertIn(
            "combat.single_actor_stage()",
            normalized_unit_sprites,
        )
        self.assertNotIn(
            "combat.duel_stage_visible() && ! original_action_16",
            normalized_renderer,
        )

    def test_map_cannot_accept_controls_during_combat_transaction(self):
        source = SOURCE.read_text(encoding="utf-8")
        normalized = " ".join(source.split())
        self.assertIn(
            "map_controls_enabled()",
            normalized,
        )

    def test_combat_stage_releases_obj_vram_before_map_units_rebind(self):
        source = SOURCE.read_text(encoding="utf-8")
        renderer_source = source.split(
            "class battle_combat_stage_runtime_renderer",
            1,
        )[1].split(
            "void update_script_message_window",
            1,
        )[0]
        normalized = " ".join(renderer_source.split())

        self.assertIn("void _release_resources()", normalized)
        for token in (
            "sprite.reset();",
            "_duel_background_bound = false;",
            "_duel_hp_track_tiles.reset();",
            "_duel_hp_fill_tiles.reset();",
            "_duel_chakra_track_tiles.reset();",
            "_duel_chakra_fill_tiles.reset();",
            "_duel_bar_palette.reset();",
            "_duel_hud_background.reset();",
            "_movie_actor_bg.reset();",
            "_movie_fire_bg.reset();",
            "_movie_dialogue_bg.reset();",
            "_movie_title_sprites",
            "bn::core::update();",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)

    def test_sasuke_fire_route_captures_each_combat_stage(self):
        source = RUNTIME_SCRIPT.read_text(encoding="utf-8")
        for token in (
            "MGBA_B09_ACTION_EXECUTE_SASUKE_FIRE",
            "sasuke-fire-duel.png",
            "sasuke-fire-title.png",
            "COMBAT_RESOURCE_ACTION_16_MOVIE = 1",
            "COMBAT_RESOURCE_ACTION_16_HIT = 5",
            "COMBAT_RESOURCE_ACTION_16_CUTIN = 6",
            "sasuke-fire-cutin-slide.png",
            "sasuke-fire-cutin-fade.png",
            "due_frame = 111",
            "sasuke-fire-movie-actor.png",
            "sasuke-fire-movie-reference.png",
            "sasuke-fire-movie-expanded.png",
            "sasuke-fire-impact-00.png",
            "sasuke-fire-impact-04.png",
            "sasuke-fire-impact-08.png",
            "sasuke-fire-impact-12.png",
            "sasuke-fire-impact-15.png",
            "presentation_combat_stage",
            "COMBAT_STAGE_DUEL_SETUP",
            "COMBAT_STAGE_TECHNIQUE_TITLE",
            "COMBAT_STAGE_ACTION_MOVIE",
            "COMBAT_STAGE_IMPACT",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        impact_capture = re.search(
            r'key = "sasuke-fire-impact-00".*?'
            r'stage = COMBAT_STAGE_IMPACT,.*?'
            r'due_frame = (\d+),',
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(impact_capture)
        self.assertEqual(impact_capture.group(1), "50")
        self.assertNotIn("sasuke-fire-impact.png", source)
        self.assertNotIn("sasuke_fire_presentation_start_frame", source)

    def test_sasuke_action_05_route_captures_original_component_frames(self):
        source = RUNTIME_SCRIPT.read_text(encoding="utf-8")
        for token in (
            "MGBA_B09_ACTION_EXECUTE_SASUKE_ACTION_05",
            "ACTION_05 = 5",
            "COMBAT_RESOURCE_ACTION_05_HIT = 3",
            "sasuke-action-05-impact-00.png",
            "sasuke-action-05-impact-04.png",
            "sasuke-action-05-impact-08.png",
            "sasuke-action-05-impact-12.png",
            "sasuke-action-05-impact-15.png",
            "telemetry.presentation_combat_resource ==",
            "COMBAT_RESOURCE_ACTION_05_HIT",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
