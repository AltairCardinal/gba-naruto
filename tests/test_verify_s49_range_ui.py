"""Original-ROM contracts for scenario-49's dynamic range UI."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VerifyS49RangeUiTest(unittest.TestCase):
    def test_original_gpu_cells_match_runtime_range_style(self) -> None:
        from tools.butano.verify_s49_range_ui import verify_range_ui

        report = verify_range_ui(ROOT)
        self.assertEqual(3072, report["cell_pixels"]["compared"])
        self.assertEqual(0, report["cell_pixels"]["different"])
        self.assertEqual(11, report["palette_entries"]["compared"])
        self.assertEqual(0, report["palette_entries"]["different"])
        self.assertEqual("0x0202", report["original_bg2"]["control"])
        self.assertEqual([10, 10], report["original_bg2"]["blend_weights"])
        self.assertTrue(report["runtime_contract"]["blocked_rows"])
        self.assertEqual(6, report["runtime_contract"]["cell_kind_count"])

    def test_cli_persists_the_comparison_manifest(self) -> None:
        from tools.butano.verify_s49_range_ui import main

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "range-ui.json"
            self.assertEqual(
                0,
                main(
                    [
                        "--root",
                        str(ROOT),
                        "--output",
                        str(output),
                    ]
                ),
            )
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
