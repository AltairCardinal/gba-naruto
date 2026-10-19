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


class ButanoBattleArenaStackLifetimeTests(unittest.TestCase):
    def test_scene_config_and_arena_roster_do_not_live_on_iwram_stack(self):
        source = RUNTIME.read_text(encoding="utf-8")
        run_start = source.index(
            "battle_runtime_scene_exit run_battle_scene("
        )
        arena_start = source.index(
            "run_battle_32_arena_fixture_scene()"
        )
        run_function = source[run_start:arena_start]
        arena_function = source[arena_start:]

        self.assertIn(
            "BN_DATA_EWRAM static\n"
            "            battle_runtime_scene_config config;",
            run_function,
        )
        self.assertIn("config = {};", run_function)
        self.assertIn(
            "BN_DATA_EWRAM static\n"
            "            battle_arena_match_roster roster;",
            arena_function,
        )
        self.assertIn("roster = {};", arena_function)


if __name__ == "__main__":
    unittest.main()
