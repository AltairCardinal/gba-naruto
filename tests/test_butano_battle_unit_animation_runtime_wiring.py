import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "butano-sequel" / "game" / "src" / "battle_runtime_scene.cpp"
MAKEFILE = ROOT / "butano-sequel" / "Makefile"


class ButanoBattleUnitAnimationRuntimeWiringTest(unittest.TestCase):
    def test_runtime_uses_rom_timeline_and_component_sprites(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn(
            "constexpr bn::color battle_unit_selected_palette_color(\n"
            "        0, 23, 23);",
            source,
        )
        start = source.index("void update_unit_sprites(")
        end = source.index(
            "\nvoid capture_deployment_telemetry(", start
        )
        function = source[start:end]

        self.assertIn("battle_unit_sprite_state", source)
        self.assertIn("bn_sprite_palette_ptr.h", source)
        self.assertIn("selected_palette", function)
        self.assertIn(
            "bn::sprite_palette_ptr::create_new(",
            function,
        )
        self.assertIn(
            "state.selected_unit == unit.id",
            function,
        )
        self.assertIn(
            "set_color(\n"
            "                        15,\n"
            "                        battle_unit_selected_palette_color)",
            function,
        )
        self.assertIn("sprite->set_palette(", function)
        self.assertIn("battle_unit_visual_slot_for", function)
        self.assertIn("battle_unit_visual_animation::frame_at", function)
        self.assertIn(
            "battle_unit_visual_animation::idle_phase_offset("
            "\n                                unit.id)",
            source,
        )
        self.assertIn("battle_unit_visual_max_components", function)
        self.assertIn("set_item(*item, graphics_index)", function)
        self.assertIn("set_horizontal_flip", function)
        self.assertIn("battle_map_unit_z_order(", function)
        self.assertIn("sprite->set_z_order(", function)
        self.assertNotIn("battle_unit_idle_visual_for", function)
        self.assertIn("presentation_target", function)
        self.assertIn("presentation.affects(unit.id)", source)
        self.assertIn("event.impact_count", source)
        self.assertIn(
            "return_start_frame(",
            source,
        )
        self.assertIn(
            "settle_start_frame(",
            source,
        )
        self.assertNotIn(
            "result.elapsed_frames = action_frame - 72",
            source,
        )
        self.assertNotIn(
            "result.elapsed_frames = action_frame - 84",
            source,
        )
        self.assertIn(
            'presentation_busy ? "RESOLVING" :',
            source,
        )
        self.assertNotIn("render_unit_labels", source)

        deployment_start = source.index(
            "run_deployment_confirmation("
        )
        deployment_end = source.index(
            "\n[[nodiscard]] battle_runtime_scene_exit",
            deployment_start,
        )
        deployment = source[deployment_start:deployment_end]
        self.assertIn("update_unit_sprites(", deployment)
        self.assertNotIn("battle_unit_idle_visual_for", deployment)

    def test_runtime_reserves_enough_depth_sort_layers(self):
        source = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn(
            "BN_CFG_SPRITES_MAX_SORT_LAYERS=32",
            source,
        )


if __name__ == "__main__":
    unittest.main()
