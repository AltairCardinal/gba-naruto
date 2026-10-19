"""Tests for generated battle-result C++ content."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.generate_butano_battle_result_content import (
    generate_header,
    load_battle_result_content,
)


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattleResultContentTests(unittest.TestCase):
    def test_loads_complete_runtime_verified_tables(self):
        content = load_battle_result_content(ROOT)
        self.assertEqual(len(content["rewards"]), 112)
        self.assertEqual(len(content["thresholds"]), 63)
        self.assertEqual(len(content["growth"]), 63)
        self.assertEqual(len(content["mapping"]), 48)
        self.assertEqual(content["mapping"][41], 104)
        self.assertEqual(content["growth"][1]["template_0e_growth"], 1450)

    def test_generated_header_is_stable_and_fixed_capacity(self):
        content = load_battle_result_content(ROOT)
        first = generate_header(content)
        second = generate_header(content)
        self.assertEqual(first, second)
        self.assertIn(
            "std::array<battle_reward_definition, 112>", first
        )
        self.assertIn(
            "std::array<experience_threshold_definition, 63>", first
        )
        self.assertIn(
            "std::array<character_growth_definition, 63>", first
        )


if __name__ == "__main__":
    unittest.main()
