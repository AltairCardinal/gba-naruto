import tempfile
import unittest
from pathlib import Path

from tools.butano.generate_scenario_41_prebattle_assets import (
    generate_prebattle_assets,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "artifacts/scenario-41-prebattle-reference-v1"


class Scenario41PrebattleAssetsTest(unittest.TestCase):
    def test_generates_six_shared_palette_screens_and_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            graphics = root / "graphics"
            header = root / "scenario_41_prebattle_frames.h"
            result = generate_prebattle_assets(REFERENCE, graphics, header)
            self.assertEqual(result, {"screens": 6, "colors": 17})
            self.assertEqual(len(list(graphics.glob("scenario_41_prebattle_*.bmp"))), 7)
            self.assertEqual(len(list(graphics.glob("scenario_41_prebattle_*.json"))), 7)
            metadata = (graphics / "scenario_41_prebattle_menu_0.json").read_text()
            self.assertIn('"palette_item":"scenario_41_prebattle_palette"', metadata)
            text = header.read_text(encoding="utf-8")
            self.assertIn("scenario_41_prebattle_menu_frames", text)
            self.assertIn("scenario_41_prebattle_confirmation_frames", text)


if __name__ == "__main__":
    unittest.main()
