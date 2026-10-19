import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.compare_s49_target_status import (
    TARGET_STATUS_BOX,
    compare_target_status_images,
    write_comparison,
)


class CompareScenario49TargetStatusTest(unittest.TestCase):
    def test_comparison_is_limited_to_the_complete_target_status_panel(self):
        original = Image.new("RGB", (240, 160), (1, 2, 3))
        current = original.copy()
        current.putpixel((0, 112), (9, 9, 9))
        current.putpixel((0, 111), (8, 8, 8))

        result = compare_target_status_images(
            original,
            current,
        )

        self.assertEqual(TARGET_STATUS_BOX, (0, 112, 240, 160))
        self.assertEqual(result["compared_pixels"], 11_520)
        self.assertEqual(result["different_pixels"], 1)

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
            self.assertEqual(len(result["original"]["sha256"]), 64)
            self.assertEqual(len(result["current"]["sha256"]), 64)
            self.assertEqual(result["different_pixels"], 0)


if __name__ == "__main__":
    unittest.main()
