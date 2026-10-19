import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoBattleArenaRosterWiringTests(unittest.TestCase):
    def test_runtime_applies_arena_roster_before_deployment_and_scene_load(self):
        header = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "battle_runtime_scene.h"
        ).read_text(encoding="utf-8")
        source = (
            ROOT
            / "butano-sequel"
            / "game"
            / "src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "const battle_arena_match_roster* arena_roster",
            header,
        )
        start = source.index(
            "battle_runtime_scene_exit run_battle_scene("
        )
        function = source[start:]
        apply_policy = function.index(
            "apply_battle_arena_scene_policy("
        )
        visible_scene = function.index(
            "run_visible_battle_scene(config)"
        )
        self.assertLess(apply_policy, visible_scene)
        self.assertIn(
            "battle_arena_roster_error::none",
            function[apply_policy:visible_scene],
        )

    def test_battle_32_fixture_builds_two_real_rosters_not_raw_placeholders(self):
        source = (
            ROOT
            / "butano-sequel"
            / "game"
            / "src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        start = source.index(
            "run_battle_32_arena_fixture_scene()"
        )
        function = source[start:]

        self.assertIn(
            "battle_arena_match_roster roster",
            function,
        )
        self.assertIn("roster.player[0]", function)
        self.assertIn("roster.opponent[0]", function)
        self.assertIn("request.arena_roster = &roster", function)
        self.assertNotIn(
            "request.load_policy.placeholder_characters",
            function,
        )


if __name__ == "__main__":
    unittest.main()
