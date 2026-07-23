import os
import subprocess
import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tools" / "butano" / "toolchain.lock"


class ButanoBuildTest(unittest.TestCase):
    def test_active_battle_is_component_rendered_instead_of_state_screenshots(self):
        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_41_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("bn_regular_bg_items_scenario_41_clean_map.h", scene)
        self.assertIn("bn_sprite_items_scenario_41_enemy.h", scene)
        self.assertIn("state.konoha_maru.position", scene)
        self.assertIn("render_battle_overlay", scene)
        self.assertNotIn("konoha/scenario_41_combat_layers.h", scene)
        self.assertNotIn("scenario_41_combat_layers_for", scene)

        clean_map = ROOT / "butano-sequel" / "graphics" / "scenario_41_clean_map.bmp"
        enemy = ROOT / "butano-sequel" / "graphics" / "scenario_41_enemy.bmp"
        self.assertTrue(clean_map.is_file())
        self.assertTrue(enemy.is_file())

        from PIL import Image

        with Image.open(clean_map) as image:
            self.assertEqual(image.size, (512, 512))
        with Image.open(enemy) as image:
            self.assertEqual(image.size, (32, 32))
            self.assertEqual(image.getpixel((31, 0)), 0)

    def test_scenario_41_uses_generated_action_domain_instead_of_fixed_damage_ability(self):
        definition = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_definition.h"
        ).read_text(encoding="utf-8")
        battle = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_battle.h"
        ).read_text(encoding="utf-8")
        self.assertIn("konoha/generated_battle_action_content.h", definition)
        self.assertIn("scenario_41_combo_action", definition)
        self.assertIn("scenario_41_player_actions", definition)
        self.assertIn("scenario_41_enemy_actions", definition)
        self.assertIn("materialize_action_loadout", definition)
        self.assertNotIn("effect_node_kind::damage, 80", definition)
        self.assertIn("battle_action_resolver::resolve_draft", battle)
        self.assertNotIn("ability_resolver::resolve_draft", battle)
        self.assertIn("konoha/generated_battle_unit_content.h", battle)
        self.assertIn("instantiate_unit(unit_definitions[1]", battle)
        self.assertIn("instantiate_unit(unit_definitions[30]", battle)

    def test_battle_scene_obeys_presentation_and_domain_input_contract(self):
        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_41_scene.cpp"
        ).read_text(encoding="utf-8")
        battle = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_battle.h"
        ).read_text(encoding="utf-8")

        self.assertIn("before.phase == battle_phase::intro", scene)
        self.assertIn(
            "before.presentation_mode_value == presentation_mode::automatic", scene
        )
        self.assertIn("const bool intro_visible", scene)
        self.assertIn("state.presentation != loaded_presentation", scene)
        self.assertIn("bn::keypad::l_pressed()", scene)
        self.assertIn("bn::keypad::r_pressed()", scene)
        self.assertIn("command_kind::cycle_previous_unit", scene)
        self.assertIn("command_kind::cycle_next_unit", scene)
        self.assertNotIn("_state.konoha_maru.position = {", battle)

    def test_benchmark_rom_wiring_is_declared(self):
        makefile = (ROOT / "butano-sequel" / "Makefile").read_text(encoding="utf-8")
        main = (ROOT / "butano-sequel" / "src" / "main.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("benchmark/src", makefile)
        self.assertIn("benchmark/include", makefile)
        self.assertIn("konoha_bench/self_test.h", main)
        self.assertIn("konoha_bench::run_self_tests()", main)

    def test_scenario_41_rom_wiring_is_declared(self):
        makefile = (ROOT / "butano-sequel" / "Makefile").read_text(encoding="utf-8")
        main = (ROOT / "butano-sequel" / "src" / "main.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("game/src", makefile)
        self.assertIn("game/include", makefile)
        self.assertIn("graphics", makefile)
        self.assertIn("konoha/scenario_41_scene.h", main)
        self.assertIn("konoha::run_scenario_41_scene()", main)

        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_41_scene.cpp"
        ).read_text(encoding="utf-8")
        extended_layers = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_extended_layers.h"
        )
        self.assertTrue(extended_layers.is_file())
        attack_frames = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "scenario_41_attack_animation_frames.h"
        )
        self.assertTrue(attack_frames.is_file())
        self.assertIn(
            "std::array<const bn::regular_bg_item*, 264>",
            attack_frames.read_text(encoding="utf-8"),
        )
        extended_text = extended_layers.read_text(encoding="utf-8")
        self.assertIn("scenario_41_result_bottom", extended_text)
        self.assertIn("scenario_41_level_up_2_top", extended_text)
        for index in range(1, 12):
            self.assertIn(f"scenario_41_postbattle_dialogue_{index}_bottom", extended_text)
        self.assertIn("konoha/scenario_41_extended_layers.h", scene)
        self.assertIn("konoha/scenario_41_attack_animation_frames.h", scene)
        self.assertIn("scenario_41_extended_layers", scene)
        self.assertNotIn("konoha/scenario_41_combat_layers.h", scene)
        self.assertNotIn("scenario_41_combat_layers_for", scene)
        self.assertIn("before.phase == battle_phase::combat_animation", scene)
        self.assertIn("state.animation_frame != loaded_animation_frame", scene)
        self.assertIn("scenario_41_attack_animation_frames[state.animation_frame]", scene)
        self.assertIn("scenario_41_attack_animation_dark_fade[state.animation_frame]", scene)
        self.assertIn("bn::blending::set_black_fade_color()", scene)
        self.assertIn("bn::blending::set_fade_alpha", scene)
        self.assertIn("map->set_blending_enabled(true);", scene)
        self.assertIn("if(state.animation_frame < 4)", scene)
        self.assertIn("scenario_41_attack_alpha_bottom[state.animation_frame]", scene)
        self.assertIn("scenario_41_attack_alpha_middle[state.animation_frame]", scene)
        self.assertIn("scenario_41_attack_alpha_top[state.animation_frame]", scene)
        self.assertGreaterEqual(scene.count("animation_visible"), 4)
        self.assertIn("konoha/scenario_41_prebattle_frames.h", scene)
        self.assertIn("scenario_41_prebattle_menu_frames[state.menu_index]", scene)
        self.assertIn(
            "scenario_41_prebattle_confirmation_frames[state.confirmation_index]", scene
        )
        self.assertIn("konoha/scenario_41_presenter.h", scene)
        self.assertIn("present_scenario_41", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_clean_map.h", scene)
        self.assertIn("bn_sprite_items_scenario_41_naruto.h", scene)
        self.assertIn("bn_sprite_items_scenario_41_cursor.h", scene)
        self.assertIn("bn_sprite_items_scenario_41_cursor_shadow.h", scene)
        self.assertIn("bn_sprite_items_scenario_41_select_label.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_tutorial_bg.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_tutorial_portraits.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_tutorial_ui.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_victory_bg.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_victory_actor.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_victory_title.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_postbattle_bg.h", scene)
        self.assertIn("bn_regular_bg_items_scenario_41_postbattle_ui.h", scene)
        self.assertIn("bn_sprite_items_scenario_41_enemy.h", scene)
        self.assertIn("render_battle_overlay", scene)
        self.assertIn("hud->set_visible", scene)
        self.assertIn("select_label.set_visible", scene)
        self.assertIn("state.phase == battle_phase::facing_select", scene)
        self.assertIn("state.phase == battle_phase::technique_menu", scene)
        self.assertIn("map.reset()", scene)
        self.assertIn("move_overlay.reset()", scene)
        self.assertIn("hud.reset()", scene)
        self.assertIn("int loaded_page = battle.snapshot().dialogue_page;", scene)
        self.assertIn("state.dialogue_page != loaded_page", scene)
        self.assertIn("bn::optional<bn::regular_bg_ptr>", scene)
        self.assertIn("cursor_shadow.set_z_order(1)", scene)
        self.assertIn("naruto.set_z_order(0)", scene)
        self.assertLess(
            scene.index("scenario_41_cursor_shadow.create_sprite"),
            scene.index("scenario_41_naruto.create_sprite"),
        )
        self.assertIn("bn::blending::set_transparency_weights(0.625, 0.625)", scene)
        self.assertNotIn("scenario_41_units.create_sprite", scene)
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
                self.assertIn(keypad_call, scene)
        self.assertNotIn("battle.reachable_points()", scene)
        self.assertIn("constexpr int cell_width = 32;", scene)
        self.assertIn("constexpr int cell_height = 16;", scene)
        self.assertIn("constexpr int map_center_x = 256;", scene)
        self.assertNotIn("constexpr int cell_size = 16;", scene)
        self.assertNotIn("for(int y = 0; y < 22; ++y)", scene)
        self.assertNotIn("|| feedback_frames == 0", scene)

    def test_original_ui_sound_cues_are_wired_for_maxmod(self):
        makefile = (ROOT / "butano-sequel" / "Makefile").read_text(encoding="utf-8")
        scene = (
            ROOT / "butano-sequel" / "game" / "src" / "scenario_41_scene.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("AUDIO           :=  audio", makefile)
        self.assertIn("AUDIOBACKEND    :=  maxmod", makefile)
        self.assertIn("bn_sound_items.h", scene)
        for cue in (102, 103, 104, 105):
            path = ROOT / "butano-sequel" / "audio" / f"sound_{cue}.wav"
            with self.subTest(cue=cue):
                self.assertTrue(path.is_file())
                with wave.open(str(path), "rb") as stream:
                    self.assertEqual(stream.getnchannels(), 1)
                    self.assertEqual(stream.getsampwidth(), 1)
                    self.assertEqual(stream.getframerate(), 22050)
                self.assertIn(
                    f"play_audio_item(bn::sound_items::sound_{cue})", scene
                )

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
            8 * 1024 * 1024,
            "Maxmod-safe mono music must keep the ROM inside the 8 MiB compatibility boundary",
        )
        self.assertEqual(data[0xA0:0xAC].rstrip(b"\0"), b"KONOHA BASE")
        self.assertEqual(data[0xAC:0xB0], b"KNBT")
        elf = (ROOT / "butano-sequel" / "butano-sequel.elf").read_bytes()
        self.assertIn(b"run_self_tests", elf)
        self.assertIn(b"run_scenario_41_scene", elf)
        for symbol in (
            b"scenario_41_prebattle_menu_0",
            b"scenario_41_attack_frame_159",
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


if __name__ == "__main__":
    unittest.main()
