import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoCampaignScenePolicyWiringTests(unittest.TestCase):
    def test_runtime_projects_campaign_party_and_equipment_before_scene_load(self):
        source = (
            ROOT
            / "butano-sequel"
            / "game"
            / "src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        start = source.index(
            "battle_runtime_scene_exit run_battle_scene("
        )
        function = source[start:]
        apply_policy = function.index(
            "apply_battle_campaign_scene_policy("
        )
        visible_scene = function.index(
            "run_visible_battle_scene(config)"
        )
        self.assertLess(apply_policy, visible_scene)
        self.assertIn(
            "battle_campaign_error::none",
            function[apply_policy:visible_scene],
        )

    def test_campaign_battle_uses_saved_equipment_not_scene_fixture_tools(self):
        runtime = (
            ROOT
            / "butano-sequel"
            / "game"
            / "src"
            / "battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        start = runtime.index(
            "battle_runtime_scene_exit run_battle_41_scene(\n"
            "        battle_campaign_state& campaign)"
        )
        end = runtime.index(
            "\nbattle_runtime_scene_exit run_battle_09_scene()",
            start,
        )
        campaign_overload = runtime[start:end]
        self.assertNotIn(
            "character_equipped_tools",
            campaign_overload,
        )

        main = (
            ROOT / "butano-sequel" / "src" / "main.cpp"
        ).read_text(encoding="utf-8")
        self.assertRegex(
            main,
            r"campaign_checkpoint\.characters\[1\]"
            r"\.equipped_tools\s*=\s*"
            r"\{\s*67,\s*11,\s*37,?\s*\};",
        )


if __name__ == "__main__":
    unittest.main()
