import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.compare_s49_target_confirmation import (
    CONFIRMATION_BOX,
    compare_target_confirmation_images,
    write_comparison,
)


class CompareScenario49TargetConfirmationTest(unittest.TestCase):
    def test_comparison_is_limited_to_the_opaque_confirmation_box(self):
        original = Image.new("RGB", (240, 160), (1, 2, 3))
        current = original.copy()
        current.putpixel((80, 24), (9, 9, 9))
        current.putpixel((79, 24), (8, 8, 8))

        result = compare_target_confirmation_images(
            original,
            current,
        )

        self.assertEqual(CONFIRMATION_BOX, (80, 24, 160, 88))
        self.assertEqual(result["compared_pixels"], 5_120)
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
