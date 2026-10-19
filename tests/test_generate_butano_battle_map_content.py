import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.generate_butano_battle_map_content import generate_header, load_map_content


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattleMapContentTest(unittest.TestCase):
    def test_loads_all_rom_collision_cells_without_flattening_partial_masks(self):
        maps = load_map_content(ROOT)

        self.assertEqual(len(maps), 47)
        self.assertEqual(sum(len(row["cells"]) for row in maps), 12151)
        row = maps[41]
        self.assertEqual((row["battle_id"], row["width"], row["height"]), (41, 9, 22))
        self.assertEqual(len(row["cells"]), 198)
        self.assertEqual(row["cells"][0], 15)
        self.assertEqual(row["cells"][8 * 9 + 3], 7)
        self.assertEqual(row["cells"][8 * 9 + 5], 3)
        self.assertEqual(row["cells"][13 * 9 + 1], 1)
        self.assertEqual(row["cells"], maps[43]["cells"])
        self.assertEqual(len(row["distance_records"]), 8)
        self.assertEqual(
            maps[16]["distance_records"][0],
            bytes.fromhex("02090104000001010701080000000000"),
        )
        self.assertEqual(
            maps[23]["distance_records"][0],
            bytes.fromhex("04000000000000000000000000000000"),
        )
        record_types = {
            record[0]
            for row in maps
            for record in row["distance_records"]
        }
        self.assertEqual(record_types, set(range(7)))

    def test_generated_header_is_deterministic_and_fixed_capacity(self):
        maps = load_map_content(ROOT)

        first = generate_header(maps)
        second = generate_header(maps)

        self.assertEqual(first, second)
        self.assertIn("std::array<battle_map_definition, 47>", first)
        self.assertIn("std::array<battle_map_cell, 12151>", first)
        self.assertIn("std::array<battle_map_distance_record, 376>", first)
        self.assertIn("battle_map_definition{ 41, 9, 22,", first)
        self.assertIn("battle_map_cell{ 0x0007 }", first)
        self.assertIn(
            "battle_map_distance_record{ "
            "{ 0x02, 0x09, 0x01, 0x04, 0x00, 0x00, 0x01, 0x01, "
            "0x07, 0x01, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00 } }",
            first,
        )

    def test_cli_regenerates_the_checked_in_header(self):
        expected = generate_header(load_map_content(ROOT))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "generated_battle_map_content.h"
            completed = subprocess.run(
                [
                    "/usr/bin/python3",
                    str(ROOT / "tools" / "generate_butano_battle_map_content.py"),
                    "--root",
                    str(ROOT),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
