import tempfile
import unittest
from pathlib import Path

from tools.generate_butano_battle_scenario_content import (
    generate_header,
    load_scenario_content,
)


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattleScenarioContentTest(unittest.TestCase):
    def test_loads_all_rom_backed_maps_and_formations(self):
        scenarios = load_scenario_content(ROOT)

        self.assertEqual(len(scenarios), 47)
        self.assertEqual(
            (scenarios[41]["grid_width"], scenarios[41]["grid_height"]),
            (9, 22),
        )
        self.assertEqual(
            [
                (
                    row["selector"],
                    row["side"],
                    row["x"],
                    row["y"],
                    row["battle_experience"],
                )
                for row in scenarios[41]["variants"][0]
                if row["enabled"]
            ],
            [(1, 0, 4, 10, 0), (30, 1, 4, 4, 50)],
        )
        self.assertEqual(
            sum(row["enabled"] for row in scenarios[15]["variants"][0]),
            9,
        )
        self.assertEqual(
            scenarios[32]["variants"][0][0]["selector_kind"],
            "deployment_placeholder",
        )

    def test_preserves_fixed_record_runtime_configuration(self):
        scenarios = load_scenario_content(ROOT)
        enemy_naruto = scenarios[10]["variants"][0][2]

        self.assertEqual(enemy_naruto["selector"], 1)
        self.assertEqual(enemy_naruto["runtime_config"]["level"], 20)
        self.assertEqual(enemy_naruto["runtime_config"]["unit_parameter"], 1)
        self.assertEqual(
            enemy_naruto["runtime_config"]["primary_action_slots"][:3],
            [
                {
                    "action": 1,
                    "state": 2,
                    "unlock_level": 0,
                    "reserved": 0,
                },
                {
                    "action": 2,
                    "state": 2,
                    "unlock_level": 0,
                    "reserved": 0,
                },
                {
                    "action": 5,
                    "state": 2,
                    "unlock_level": 0,
                    "reserved": 0,
                },
            ],
        )
        self.assertEqual(
            enemy_naruto["runtime_config"]["equipped_tools"],
            [1, 19, 41, 41, 41, 0, 0, 0, 0],
        )
        self.assertTrue(
            enemy_naruto["runtime_config"]["embedded_character_config"]
        )

    def test_deployment_placeholder_keeps_roster_owned_configuration(self):
        scenarios = load_scenario_content(ROOT)
        placeholder = scenarios[32]["variants"][0][0]

        self.assertEqual(
            placeholder["selector_kind"],
            "deployment_placeholder",
        )
        self.assertFalse(
            placeholder["runtime_config"]["embedded_character_config"]
        )

    def test_rejects_selector_outside_fixed_and_placeholder_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            maps = root / "sequel" / "content" / "maps"
            positions = root / "sequel" / "content" / "positions"
            maps.mkdir(parents=True)
            positions.mkdir(parents=True)
            (maps / "bank.json").write_text(
                '{"entry_count":1,"entries":[{"_index":0,"width":36,'
                '"height":44,"flags":1}]}',
                encoding="utf-8",
            )
            entries = []
            for variant in range(3):
                for record in range(12):
                    entries.append(
                        {
                            "group_id": 0,
                            "variant_id": variant,
                            "record_id": record,
                            "selector": 100 if variant == 0 and record == 0 else 0,
                            "affiliation": 0,
                            "x": 0,
                            "y": 0,
                            "parameter": 0,
                            "battle_experience": 0,
                            "active": variant == 0 and record == 0,
                        }
                    )
            import json

            (positions / "bank.json").write_text(
                json.dumps({"entries": entries}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unsupported selector"):
                load_scenario_content(root)

    def test_generated_header_is_stable_and_has_fixed_capacity(self):
        scenarios = load_scenario_content(ROOT)
        first = generate_header(scenarios)
        second = generate_header(scenarios)

        self.assertEqual(first, second)
        self.assertIn("battle_scenario_definitions", first)
        self.assertIn("std::array<battle_scenario_definition, 47>", first)
        self.assertIn("scenario_selector_kind::deployment_placeholder", first)
        self.assertIn("battle_scenario_unit_runtime_config{", first)


if __name__ == "__main__":
    unittest.main()
