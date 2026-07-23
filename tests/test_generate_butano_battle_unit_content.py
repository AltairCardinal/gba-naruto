import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButanoBattleUnitContentGenerationTest(unittest.TestCase):
    def test_loads_all_character_stats_and_action_slots(self):
        from tools.generate_butano_battle_unit_content import load_unit_content

        units = load_unit_content(ROOT)
        self.assertEqual(len(units), 63)
        naruto = units[1]
        self.assertEqual(
            {key: naruto[key] for key in (
                "attack", "defense", "agility", "movement", "ninja_tool_capacity",
                "chakra_capacity", "hand_seals", "max_hp",
            )},
            {
                "attack": 14,
                "defense": 13,
                "agility": 8,
                "movement": 3,
                "ninja_tool_capacity": 5,
                "chakra_capacity": 5,
                "hand_seals": 15,
                "max_hp": 80,
            },
        )
        self.assertEqual(
            [slot["action_id"] for slot in naruto["primary_slots"] if slot["action_id"]],
            [2, 3, 4, 5, 6, 7, 8, 9],
        )
        self.assertEqual(len(naruto["primary_slots"]), 15)
        self.assertEqual(len(naruto["secondary_slots"]), 24)

        scenario_enemy = units[30]
        self.assertEqual(scenario_enemy["max_hp"], 10)
        self.assertEqual(scenario_enemy["attack"], 6)
        self.assertEqual(scenario_enemy["defense"], 6)
        self.assertEqual(scenario_enemy["agility"], 6)
        self.assertIn(5, [slot["action_id"] for slot in scenario_enemy["primary_slots"]])

    def test_generates_fixed_capacity_cpp_unit_table(self):
        from tools.generate_butano_battle_unit_content import generate_header

        header = generate_header(ROOT)
        self.assertIn("std::array<unit_definition, 63> unit_definitions", header)
        self.assertIn("std::array<action_slot_definition, 15>", header)
        self.assertIn("std::array<action_slot_definition, 24>", header)


if __name__ == "__main__":
    unittest.main()
