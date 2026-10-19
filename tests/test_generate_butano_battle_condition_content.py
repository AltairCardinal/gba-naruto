import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattleConditionContentTest(unittest.TestCase):
    def test_loads_all_rom_bound_battles_and_variants(self):
        from tools.generate_butano_battle_condition_content import (
            load_condition_content,
        )

        battles = load_condition_content(ROOT)
        self.assertEqual(len(battles), 47)
        self.assertTrue(all(len(variants) == 3 for variants in battles))
        self.assertEqual(
            battles[9][0]["win"][0],
            {"type": 1, "arg0": 1, "arg1": 0, "script_address": 0x0800848C},
        )
        self.assertEqual(
            battles[15][0]["lose"][1],
            {"type": 3, "arg0": 0, "arg1": 30, "script_address": 0x08008770},
        )
        self.assertEqual(
            battles[44][0]["win"][0],
            {"type": 6, "arg0": 0, "arg1": 0, "script_address": 0x080098B6},
        )

    def test_checked_in_header_matches_deterministic_generator(self):
        from tools.generate_butano_battle_condition_content import generate_header

        generated = generate_header(ROOT)
        checked_in = (
            ROOT
            / "butano-sequel"
            / "game"
            / "include"
            / "konoha"
            / "generated_battle_condition_content.h"
        ).read_text(encoding="utf-8")
        self.assertEqual(checked_in, generated)
        self.assertIn(
            "std::array<std::array<battle_condition_variant, 3>, 47>",
            generated,
        )
        self.assertIn("battle_condition_type::object_slot_inactive", generated)
        self.assertIn("0x080098B6U", generated)


if __name__ == "__main__":
    unittest.main()
