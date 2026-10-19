import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    ROOT
    / "butano-sequel"
    / "game"
    / "src"
    / "battle_runtime_scene.cpp"
)


class ButanoBattleSceneResourceLifetimeTests(unittest.TestCase):
    def test_previous_scene_sprite_caches_are_released_before_deployment(self):
        source = RUNTIME.read_text(encoding="utf-8")
        start = source.index(
            "run_visible_battle_scene("
        )
        end = source.index(
            "\n}\n\n}\n\nbattle_runtime_scene_exit run_battle_scene(",
            start,
        )
        function = source[start:end]
        deployment = function.index(
            "run_deployment_confirmation("
        )

        for release in (
            "unit_sprites = {};",
            "battlefield_object_expiry_sprite = bn::nullopt;",
            "text_sprites.clear();",
            "script_glyph_sprites.clear();",
        ):
            self.assertLess(
                function.index(release),
                deployment,
                f"{release} must release the previous scene before deployment",
            )

        release_start = function.index(
            "unit_sprites = {};"
        )
        self.assertIn(
            "bn::core::update();",
            function[release_start:deployment],
        )

    def test_script_portraits_reclaim_unit_tiles_before_allocation(self):
        source = RUNTIME.read_text(encoding="utf-8")
        start = source.index(
            "void update_script_portraits("
        )
        end = source.index(
            "\n}\n\nstruct battle_unit_visual_sample",
            start,
        )
        function = source[start:end]

        release = function.index("unit.reset();")
        reclaim = function.index("bn::core::update();")
        allocate = function.index("renderer.update(")
        self.assertIn(
            "released_unit_resources",
            function,
        )
        self.assertLess(release, reclaim)
        self.assertLess(reclaim, allocate)

    def test_script_and_map_visual_cohorts_are_reclaimed_at_the_mode_boundary(
        self,
    ):
        source = RUNTIME.read_text(encoding="utf-8")
        start = source.index("run_visible_battle_scene(")
        loop = source[
            source.index("while(true)", start):
            source.index(
                "\n    }\n}\n\n}",
                source.index("while(true)", start),
            )
        ]
        transition = loop[
            loop.index("const bool script_visuals_visible"):
            loop.index(
                "update_script_message_window(",
                loop.index("const bool script_visuals_visible"),
            )
        ]

        self.assertRegex(
            transition,
            r"script_visuals_visible\s*!=\s*"
            r"script_visuals_active",
        )
        for release in (
            "portrait_renderer.reset();",
            "unit.reset();",
            "text_sprites.clear();",
            "script_glyph_sprites.clear();",
        ):
            self.assertIn(release, transition)
        self.assertIn("bn::core::update();", transition)
        self.assertLess(
            transition.index("portrait_renderer.reset();"),
            transition.index("bn::core::update();"),
        )
        self.assertLess(
            transition.index("script_glyph_sprites.clear();"),
            transition.index("bn::core::update();"),
        )


if __name__ == "__main__":
    unittest.main()
