import tempfile
import unittest
from pathlib import Path

from tools.butano.export_scenario_41_prebattle_reference import (
    export_prebattle_reference,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "menu-0": ROOT / "build/macos-prebattle-frame80-step2-20260715/frame80.png",
    "menu-1": ROOT / "build/scenario-41-prebattle-down-20260715/after-down.png",
    "menu-2": ROOT / "build/scenario-41-prebattle-down2-20260722/after-down2.png",
    "menu-3": ROOT / "build/scenario-41-prebattle-down3-20260722/after-down3.png",
    "confirmation-yes": ROOT / "build/scenario-41-prebattle-start-prompt-20260722/prompt.png",
    "confirmation-no": ROOT / "build/scenario-41-prebattle-start-no-20260722/no.png",
}


class Scenario41PrebattleReferenceTest(unittest.TestCase):
    def test_exports_six_hash_bound_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reference"
            manifest = export_prebattle_reference(SOURCES, output)
            self.assertEqual(list(manifest["boundaries"]), list(SOURCES))
            self.assertEqual(
                manifest["boundaries"]["menu-0"]["rgb_sha256"],
                "bf0ffd7484bc0d4c8e2f94af623b265f8f462a891133a0bccf67f757c849d035",
            )
            self.assertEqual(
                manifest["boundaries"]["confirmation-no"]["rgb_sha256"],
                "c49cbfd9c41b6782965246fc90df8b8ca33e13272c00fa6a83b115ffdd887b8f",
            )
            self.assertEqual(len(list((output / "screens").glob("*.png"))), 6)


if __name__ == "__main__":
    unittest.main()
