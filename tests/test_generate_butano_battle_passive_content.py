import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKED_IN = (
    ROOT
    / "butano-sequel/game/include/konoha"
    / "generated_battle_passive_content.h"
)


class GenerateButanoBattlePassiveContentTest(unittest.TestCase):
    def test_loads_all_45_rom_bound_progression_records(self):
        from tools.generate_butano_battle_passive_content import (
            load_passive_content,
        )

        records = load_passive_content(ROOT)

        self.assertEqual(len(records), 45)
        self.assertEqual(
            [row["passive_id"] for row in records],
            list(range(45)),
        )
        self.assertEqual(
            records[9],
            {
                "passive_id": 9,
                "target_type": 0x0C,
                "reserved1": 0,
                "base_a": 10,
                "base_b": 0,
                "per_level_a": 5,
                "per_level_b": 0,
                "reserved_a": 0,
                "raw_hex": "0c000a000000050000000000",
            },
        )
        self.assertEqual(records[20]["target_type"], 0x19)
        self.assertEqual(records[20]["base_a"], 20)
        self.assertEqual(records[20]["per_level_a"], 5)
        self.assertEqual(records[35]["base_b"], 10)
        self.assertEqual(records[35]["per_level_b"], 5)

    def test_generator_is_deterministic_and_fixed_capacity(self):
        from tools.generate_butano_battle_passive_content import (
            generate_header,
            load_passive_content,
        )

        records = load_passive_content(ROOT)
        first = generate_header(records)
        second = generate_header(records)

        self.assertEqual(first, second)
        self.assertIn(
            "std::array<passive_definition, 45> passive_definitions",
            first,
        )
        self.assertIn(
            "passive_definition{ 9, 12, 0, 10, 0, 5, 0, 0 }",
            first,
        )

    def test_rejects_non_contiguous_or_raw_mismatched_content(self):
        from tools.generate_butano_battle_passive_content import (
            load_passive_content,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            levels = root / "sequel/content/levels"
            levels.mkdir(parents=True)
            (levels / "bank.json").write_text(
                '{"entry_count":45,"entry_size":12,"entries":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exactly 45"):
                load_passive_content(root)

    def test_checked_in_header_matches_generator(self):
        from tools.generate_butano_battle_passive_content import (
            generate_header,
            load_passive_content,
        )

        self.assertEqual(
            CHECKED_IN.read_text(encoding="utf-8"),
            generate_header(load_passive_content(ROOT)),
        )


if __name__ == "__main__":
    unittest.main()
