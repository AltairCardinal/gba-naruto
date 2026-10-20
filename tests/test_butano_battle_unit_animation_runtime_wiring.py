import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "butano-sequel" / "game" / "src" / "battle_runtime_scene.cpp"
MAKEFILE = ROOT / "butano-sequel" / "Makefile"


class ButanoBattleUnitAnimationRuntimeWiringTest(unittest.TestCase):
    def test_runtime_uses_rom_timeline_and_component_sprites(self):
        source = RUNTIME.read_text(encoding="utf-8")
        start = source.index("void update_unit_sprites(")
        end = source.index(
            "\nvoid capture_deployment_telemetry(", start
        )
        function = source[start:end]

        self.assertIn("battle_unit_sprite_state", source)
        self.assertIn("bn_sprite_palette_ptr.h", source)
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

    def test_the_selected_unit_keeps_the_unit_art_palette(self):
        """The original never paints a cyan outline on the selected unit.

        The remake used to overwrite palette entry 15 of the selected unit
        with RGB5 (0,23,23), which paints a teal outline the original does
        not have: the 25 frames of the original S49 walk contain zero pixels
        of that colour, and the one place the original does show it is the
        battle entry, where it is already gone four frames later.  The gate
        used to pin the presence of that override, which pinned a behaviour
        the original does not have, so it now pins the absence.
        """

        source = RUNTIME.read_text(encoding="utf-8")
        start = source.index("void update_unit_sprites(")
        end = source.index(
            "\nvoid capture_deployment_telemetry(", start
        )
        function = source[start:end]

        self.assertNotIn("battle_unit_selected_palette_color", source)
        self.assertNotIn("selected_palette", source)
        self.assertNotIn("palette_selected", source)
        self.assertNotIn("sprite_palette_ptr::create_new(", function)
        self.assertNotIn("set_color(", function)
        # The greyscale palette of the unit that is not acting is still
        # applied, and the unit that is acting keeps the art's own palette.
        self.assertIn("dimmed_unit_palette()", function)
        self.assertIn("item->palette_item()", function)
        self.assertIn("state.selected_unit == unit.id", function)

    def test_runtime_reserves_enough_depth_sort_layers(self):
        source = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn(
            "BN_CFG_SPRITES_MAX_SORT_LAYERS=32",
            source,
        )


if __name__ == "__main__":
    unittest.main()
