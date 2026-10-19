import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.compare_s49_action_menu import (
    ACTION_STATE_VALUE_BOXES,
    ACTION_HOMOLOGOUS_REGION_BOXES,
    ACTION_HOMOLOGOUS_REGION_LABELS,
    ACTION_ICON_BOXES,
    action_shell_coordinates,
    compare_action_menu_images,
    write_comparison,
)


class CompareScenario49ActionMenuTest(unittest.TestCase):
    def test_shell_mask_only_covers_original_static_panel_structure(self):
        coordinates = action_shell_coordinates()

        self.assertEqual(len(coordinates), 12_992)
        self.assertIn((0, 0), coordinates)
        self.assertIn((143, 31), coordinates)
        self.assertIn((144, 40), coordinates)
        self.assertIn((239, 159), coordinates)
        self.assertNotIn((8, 8), coordinates)
        self.assertNotIn((152, 8), coordinates)
        self.assertNotIn((8, 40), coordinates)
        self.assertNotIn((8, 120), coordinates)
        self.assertNotIn((0, 40), coordinates)
        self.assertNotIn((136, 13), coordinates)
        self.assertNotIn((232, 136), coordinates)

    def test_comparison_counts_shell_and_each_action_icon(self):
        original = Image.new("RGB", (240, 160), (1, 2, 3))
        current = original.copy()
        current.putpixel((0, 0), (9, 9, 9))
        first_icon = ACTION_ICON_BOXES[0]
        current.putpixel((first_icon[0], first_icon[1]), (8, 8, 8))

        result = compare_action_menu_images(original, current)

        self.assertEqual(result["shell"]["compared_pixels"], 12_992)
        self.assertEqual(result["shell"]["different_pixels"], 1)
        self.assertEqual(len(result["icons"]), 8)
        self.assertEqual(result["icons"][0]["different_pixels"], 1)
        self.assertTrue(
            all(
                icon["different_pixels"] == 0
                for icon in result["icons"][1:]
            )
        )
        self.assertEqual(
            len(result["homologous_regions"]),
            len(ACTION_HOMOLOGOUS_REGION_BOXES),
        )
        self.assertEqual(
            [
                region["label"]
                for region in result["homologous_regions"]
            ],
            list(ACTION_HOMOLOGOUS_REGION_LABELS),
        )
        self.assertTrue(
            all(
                region["different_pixels"] == 0
                for region in result["homologous_regions"]
            )
        )

    def test_homologous_region_difference_is_reported_separately(self):
        original = Image.new("RGB", (240, 160), (1, 2, 3))
        current = original.copy()
        first_box = ACTION_HOMOLOGOUS_REGION_BOXES[0]
        current.putpixel(
            (first_box[0], first_box[1]),
            (9, 9, 9),
        )

        result = compare_action_menu_images(original, current)

        self.assertEqual(
            result["homologous_regions"][0][
                "different_pixels"
            ],
            1,
        )
        self.assertEqual(
            sum(
                region["different_pixels"]
                for region in result["homologous_regions"][1:]
            ),
            0,
        )

    def test_state_normalized_screen_only_excludes_dynamic_actor_hp(self):
        original = Image.new("RGB", (240, 160), (1, 2, 3))
        current = original.copy()
        hp_box = ACTION_STATE_VALUE_BOXES["actor-hp"]
        current.putpixel((hp_box[0], hp_box[1]), (9, 9, 9))
        current.putpixel((0, 0), (8, 8, 8))

        result = compare_action_menu_images(original, current)

        self.assertEqual(
            result["state_normalized_screen"][
                "excluded_regions"
            ],
            {"actor-hp": list(hp_box)},
        )
        self.assertEqual(
            result["state_normalized_screen"][
                "compared_pixels"
            ],
            38_400 - 24 * 8,
        )
        self.assertEqual(
            result["state_normalized_screen"][
                "different_pixels"
            ],
            1,
        )

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
            self.assertEqual(
                len(result["original"]["sha256"]),
                64,
            )
            self.assertEqual(
                result["shell"]["different_pixels"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
