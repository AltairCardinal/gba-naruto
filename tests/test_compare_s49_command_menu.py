import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.compare_s49_command_menu import (
    COMMAND_ARROW_BOX,
    COMMAND_LABEL_BOXES,
    command_shell_coordinates,
    compare_command_menu_images,
    write_comparison,
)


class CompareScenario49CommandMenuTest(unittest.TestCase):
    def test_shell_mask_only_covers_original_static_panel_structure(self):
        coordinates = command_shell_coordinates()

        self.assertEqual(len(coordinates), 1_152)
        self.assertIn((8, 40), coordinates)
        self.assertIn((55, 87), coordinates)
        self.assertIn((48, 56), coordinates)
        self.assertNotIn((8, 48), coordinates)
        self.assertNotIn((16, 48), coordinates)
        self.assertNotIn((47, 79), coordinates)
        self.assertNotIn((56, 40), coordinates)

    def test_comparison_counts_shell_labels_and_selection_arrow(self):
        original = Image.new("RGB", (240, 160), (1, 2, 3))
        current = original.copy()
        current.putpixel((8, 40), (9, 9, 9))
        current.putpixel(
            COMMAND_LABEL_BOXES[0][:2],
            (8, 8, 8),
        )
        current.putpixel(
            COMMAND_ARROW_BOX[:2],
            (7, 7, 7),
        )

        result = compare_command_menu_images(original, current)

        self.assertEqual(result["shell"]["compared_pixels"], 1_152)
        self.assertEqual(result["shell"]["different_pixels"], 1)
        self.assertEqual(len(result["labels"]), 2)
        self.assertEqual(result["labels"][0]["different_pixels"], 1)
        self.assertEqual(result["labels"][1]["different_pixels"], 0)
        self.assertEqual(result["selection_arrow"]["different_pixels"], 1)

    def test_write_comparison_persists_hash_bound_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_path = root / "original.png"
            current_path = root / "current.png"
            output_path = root / "comparison.json"
            Image.new("RGB", (240, 160), (1, 2, 3)).save(
                original_path
            )
            Image.new("RGB", (240, 160), (1, 2, 3)).save(
                current_path
            )

            result = write_comparison(
                original_path,
                current_path,
                output_path,
            )

            self.assertTrue(output_path.is_file())
            self.assertEqual(
                result["original"]["path"],
                str(original_path),
            )
            self.assertEqual(
                result["current"]["path"],
                str(current_path),
            )
            self.assertEqual(len(result["current"]["sha256"]), 64)
            self.assertEqual(result["shell"]["different_pixels"], 0)


if __name__ == "__main__":
    unittest.main()
