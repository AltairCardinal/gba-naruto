import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoBattleCombinationRuntimeWiringTest(unittest.TestCase):
    def test_runtime_scene_exposes_combination_decision_and_staged_component(self):
        source = (
            ROOT
            / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "case battle_scene_phase::combination_decision:",
            source,
        )
        self.assertIn('return "COMBO?";', source)
        self.assertIn('"COMBO YES"', source)
        self.assertIn('"COMBO NO"', source)
        self.assertIn('"COMBO 1/2 CK-"', source)
        self.assertIn('"A:ADD B:CANCEL"', source)

    def test_controller_routes_combination_decision_through_player_flow(self):
        source = (
            ROOT
            / "butano-sequel/game/include/konoha/"
            "battle_scene_controller.h"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "_runtime.cycle_combination_decision(",
            source,
        )
        self.assertIn(
            "_runtime.confirm_combination_decision()",
            source,
        )
        self.assertIn(
            "_runtime.cancel_combination_decision()",
            source,
        )


if __name__ == "__main__":
    unittest.main()
