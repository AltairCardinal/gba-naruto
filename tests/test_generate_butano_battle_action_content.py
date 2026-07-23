import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoBattleActionContentGenerationTest(unittest.TestCase):
    def test_generates_all_rom_bound_active_actions_and_ninja_tools(self):
        from tools.generate_butano_battle_action_content import load_action_content

        content = load_action_content(ROOT)
        self.assertEqual(len(content["active_actions"]), 87)
        self.assertEqual(len(content["ninja_tools"]), 94)

        teleport = content["active_actions"][2]
        self.assertEqual(teleport["cost_kind"], 1)
        self.assertEqual(teleport["scalar_cost"], 1)
        self.assertEqual(teleport["effect_code"], 3)
        self.assertEqual(teleport["target_policy"], 4)

        lion_barrage = content["active_actions"][19]
        self.assertEqual(lion_barrage["cost_kind"], 2)
        self.assertEqual(lion_barrage["scalar_cost"], 80)
        self.assertEqual(lion_barrage["base_hit_count"], 3)

        tool = content["ninja_tools"][1]
        self.assertEqual(tool["cost_kind"], 5)
        self.assertEqual(tool["animation_family"], 1)
        self.assertEqual(tool["effect_code"], 1)
        self.assertEqual(tool["target_policy"], 2)
        self.assertNotIn("scalar_cost_from_source_tail", tool)

    def test_header_uses_orthogonal_action_definition_arrays(self):
        from tools.generate_butano_battle_action_content import generate_header

        header = generate_header(ROOT)
        self.assertIn("std::array<action_definition, 87> active_action_definitions", header)
        self.assertIn("std::array<action_definition, 94> ninja_tool_action_definitions", header)
        self.assertIn("action_cost_kind::current_hp", header)
        self.assertIn("target_policy_kind::empty_tile", header)
        self.assertIn("effect_descriptor", header)
        self.assertNotIn("screenshot", header.lower())


if __name__ == "__main__":
    unittest.main()
