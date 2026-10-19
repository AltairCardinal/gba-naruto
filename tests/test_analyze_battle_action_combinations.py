import unittest
from pathlib import Path

from tools.analyze_battle_action_combinations import (
    analyze_battle_action_combinations,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleActionCombinationAnalysisTest(unittest.TestCase):
    def test_original_rom_binds_special_recipes_and_generic_fallback(self):
        result = analyze_battle_action_combinations(
            ROOT / "rom/base.gba"
        )

        self.assertEqual(
            result["recipes"],
            [
                {
                    "first_action_id": 9,
                    "second_action_id": 8,
                    "result_action_id": 10,
                },
                {
                    "first_action_id": 9,
                    "second_action_id": 5,
                    "result_action_id": 11,
                },
                {
                    "first_action_id": 12,
                    "second_action_id": 12,
                    "result_action_id": 13,
                },
                {
                    "first_action_id": 16,
                    "second_action_id": 16,
                    "result_action_id": 17,
                },
                {
                    "first_action_id": 16,
                    "second_action_id": "ninja_tool_1_through_17",
                    "result_action_id": 18,
                },
            ],
        )
        self.assertEqual(result["component_count_gate"], 2)
        self.assertEqual(
            result["matched_recipe_behavior"],
            "replace two selected components with one derived action",
        )
        self.assertEqual(
            result["unmatched_pair_behavior"],
            "preserve both selected components and initialize both action events",
        )
        self.assertEqual(
            result["encoded_ninja_tool_range"],
            ["0x81", "0x91"],
        )
        self.assertEqual(
            result["table_address"],
            "0x0853DFB0",
        )
        self.assertEqual(
            result["table_literal_address"],
            "0x08075C0C",
        )
        self.assertEqual(
            result["ai_forced_follow"]["action_id"],
            9,
        )
        self.assertEqual(
            result["ai_forced_follow"][
                "action_template_halfword"
            ],
            "0x1008",
        )
        self.assertEqual(
            result["ai_forced_follow"][
                "combination_flag_mask"
            ],
            "0x1800",
        )
        self.assertEqual(
            result["ai_forced_follow"][
                "forced_second_component_mask"
            ],
            "0x1000",
        )
        self.assertEqual(
            result["ai_forced_follow"][
                "planner_to_candidate_enumerator_call"
            ],
            {
                "callsite": "0x080855C6",
                "target": "0x08083040",
            },
        )
        self.assertEqual(
            result["ai_forced_follow"][
                "candidate_to_component_enumerator_call"
            ],
            {
                "callsite": "0x080831B6",
                "target": "0x08082354",
            },
        )
        self.assertEqual(
            result["ai_combination_policies"],
            {
                "optional_follow_action_ids": [12, 16],
                "forced_follow_action_ids": [9, 14, 25, 29],
                "combination_flag_mask": "0x1800",
                "optional_follow_mask": "0x0800",
                "forced_follow_mask": "0x1000",
                "optional_behavior": (
                    "return the single-component candidate first, "
                    "then retain the follow cursor so later calls "
                    "enumerate two-component candidates"
                ),
                "forced_behavior": (
                    "skip the single-component candidate and loop "
                    "immediately until a second component is selected"
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
