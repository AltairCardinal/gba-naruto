import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.compare_s49_prebattle import (
    compare_full_screen_images,
    write_prebattle_comparison,
)


class CompareScenario49PrebattleTest(unittest.TestCase):
    def test_full_screen_comparison_reports_exact_difference_bbox(self):
        original = Image.new("RGB", (240, 160), (1, 2, 3))
        current = original.copy()
        current.putpixel((81, 57), (9, 9, 9))

        result = compare_full_screen_images(original, current)

        self.assertEqual(result["total_pixels"], 38_400)
        self.assertEqual(result["equal_pixels"], 38_399)
        self.assertEqual(result["different_pixels"], 1)
        self.assertEqual(
            result["difference_bbox"],
            [81, 57, 82, 58],
        )

    def test_writer_hash_binds_root_and_confirmation_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for name in (
                "original-root",
                "current-root",
                "original-confirmation",
                "current-confirmation",
            ):
                path = root / f"{name}.png"
                Image.new("RGB", (240, 160), (1, 2, 3)).save(path)
                paths[name] = path
            output = root / "comparison.json"

            result = write_prebattle_comparison(
                original_root=paths["original-root"],
                current_root=paths["current-root"],
                original_confirmation=paths[
                    "original-confirmation"
                ],
                current_confirmation=paths[
                    "current-confirmation"
                ],
                output_path=output,
            )

            self.assertEqual(set(result), {"root", "confirmation"})
            self.assertEqual(
                result["root"]["different_pixels"],
                0,
            )
            self.assertEqual(
                result["confirmation"]["different_pixels"],
                0,
            )
            self.assertEqual(
                len(result["root"]["original_sha256"]),
                64,
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                result,
            )


if __name__ == "__main__":
    unittest.main()
