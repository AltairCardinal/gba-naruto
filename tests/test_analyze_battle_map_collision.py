import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.analyze_battle_map_collision import analyze_collision_runtime


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom" / "base.gba"


class AnalyzeBattleMapCollisionTest(unittest.TestCase):
    def test_pins_terrain_classes_traversal_targets_and_runtime_occupancy(self):
        result = analyze_collision_runtime(ROM)

        self.assertEqual(
            result["rom"]["sha256"],
            "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b",
        )
        self.assertEqual(len(result["maps"]), 47)
        row = result["maps"][41]
        self.assertEqual((row["width"], row["height"], row["cell_count"]), (9, 22, 198))
        self.assertEqual(row["low_nibble_values"], [0, 1, 3, 7, 15])
        self.assertEqual(
            result["terrain"]["classes"],
            {
                "normal": 0,
                "passive_0x1A": 1,
                "passive_0x1C": 3,
                "passive_0x1B": 7,
                "blocked": 15,
            },
        )
        self.assertEqual(
            result["terrain"]["traversal_limit_targets"],
            {"1": "0x1A", "3": "0x1C", "7": "0x1B"},
        )
        self.assertEqual(result["terrain"]["fully_closed"], 15)
        self.assertEqual(
            result["occupancy"],
            {
                "unit_slot_shift": 11,
                "unit_slot_mask": "0x7800",
                "side_shift": 15,
                "side_mask": "0x8000",
                "terrain_mask": "0x000F",
            },
        )

    def test_scenario_41_and_43_share_exact_collision_content(self):
        result = analyze_collision_runtime(ROM)

        self.assertEqual(result["maps"][41]["sha256"], result["maps"][43]["sha256"])
        self.assertEqual(result["maps"][41]["low_nibble_counts"], result["maps"][43]["low_nibble_counts"])
        self.assertEqual(result["consumer"]["function"], "0x080698B4")
        self.assertEqual(result["consumer"]["terrain_class_switch"], "0x08069B54")

    def test_cli_writes_the_same_json_document(self):
        expected = analyze_collision_runtime(ROM)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "collision.json"
            completed = subprocess.run(
                [
                    "/usr/bin/python3",
                    str(ROOT / "tools" / "analyze_battle_map_collision.py"),
                    str(ROM),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                expected,
            )


if __name__ == "__main__":
    unittest.main()
