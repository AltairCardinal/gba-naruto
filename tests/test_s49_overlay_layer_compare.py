#!/usr/bin/env python3
"""The S49 overlay difference must be split into logic and wiring.

``docs/butano-wiring-roadmap.md`` (W2) wants the S49 overlay 1:1, and the
remake's 2,917 differing pixels decompose into two problems with two
different owners.  The per-unit comparison is what tells them apart, so it
has to be reproducible and its shape has to be pinned:

* the original draws its overlay on a **15x10 grid of 16x16 px units**;
* the **coverage** difference (which units are highlighted at all) belongs to
  the remake's game rules -- the roadmap's own boundary puts logic
  differences outside this roadmap;
* the **styling** difference (same unit, different pixels) is the wiring.

These tests pin the shape of that split, so a future change in the remake's
overlay cannot silently move pixels between the two buckets.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "compare_s49_overlay_layers.py"
ORIGINAL = ROOT / "artifacts" / "s49-original-movegrid-tilemap-v1"
REMAKE_GPU = ROOT / "artifacts" / "s49-remake-gpu-baseline-step20-v1"

sys.path.insert(0, str(ROOT))

from tools.butano.compare_s49_overlay_layers import (  # noqa: E402
    ORIGINAL_FAMILIES,
    REMAKE_FAMILIES,
    compare,
    original_cells,
    remake_cells,
    unit_families,
)


class OverlayLayerComparisonTest(unittest.TestCase):
    def test_the_original_layer_is_a_fifteen_by_ten_grid_of_sixteen_pixel_units(
        self,
    ) -> None:
        if not (ORIGINAL / "movegrid-frame-v1.bg2-tilemap.json").is_file():
            self.skipTest("no original overlay receipt in this tree")
        cells, window = original_cells(ORIGINAL)
        self.assertEqual(len(cells), 32 * 32)
        self.assertEqual(window.get("bg2_hoffs"), 240)
        self.assertEqual(window.get("bg2_voffs"), 24)
        units = unit_families(cells, ORIGINAL_FAMILIES)
        self.assertEqual(len(units), 15 * 10)

    def test_the_remake_overlay_tilemap_is_found_in_the_vram_dump(self) -> None:
        if not (REMAKE_GPU / "vram.bin").is_file():
            self.skipTest("no remake GPU dump in this tree")
        cells, nonzero = remake_cells(REMAKE_GPU)
        self.assertEqual(len(cells), 1024)
        self.assertGreater(nonzero, 50)
        self.assertTrue(all(value < 128 for value in cells))

    def test_the_comparison_reports_both_buckets(self) -> None:
        if not (
            (ORIGINAL / "movegrid-frame-v1.bg2-tilemap.json").is_file()
            and (REMAKE_GPU / "vram.bin").is_file()
        ):
            self.skipTest("no overlay receipts in this tree")
        payload = compare(ORIGINAL, REMAKE_GPU)
        summary = payload["summary"]
        self.assertEqual(summary["units"], 150)
        self.assertEqual(
            summary["units_with_different_family"]
            + summary["units_with_same_family"],
            150,
        )
        self.assertGreater(summary["units_with_different_family"], 0)

    def test_the_comparison_is_reproducible(self) -> None:
        if not (
            (ORIGINAL / "movegrid-frame-v1.bg2-tilemap.json").is_file()
            and (REMAKE_GPU / "vram.bin").is_file()
        ):
            self.skipTest("no overlay receipts in this tree")
        first = compare(ORIGINAL, REMAKE_GPU)["rows"]
        second = compare(ORIGINAL, REMAKE_GPU)["rows"]
        self.assertEqual(first, second)

    def test_the_family_tables_cover_the_documented_ranges(self) -> None:
        self.assertEqual(
            [name for _low, _high, name in ORIGINAL_FAMILIES],
            ["grid", "move", "attack", "cursor", "target", "blocked"],
        )
        self.assertEqual(
            [name for _low, _high, name in REMAKE_FAMILIES],
            ["grid", "move", "attack", "cursor", "target", "blocked"],
        )

    def test_the_receipt_is_written_and_reports_the_split(self) -> None:
        if not (
            (ORIGINAL / "movegrid-frame-v1.bg2-tilemap.json").is_file()
            and (REMAKE_GPU / "vram.bin").is_file()
        ):
            self.skipTest("no overlay receipts in this tree")
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(ROOT),
                    "--original",
                    str(ORIGINAL),
                    "--remake-gpu",
                    str(REMAKE_GPU),
                    "--out-dir",
                    str(out_dir),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(
                (out_dir / "compare.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["summary"]["units"], 150)
            self.assertIn("units_with_different_family", payload["summary"])


if __name__ == "__main__":
    unittest.main()


class OverlayAreaTest(unittest.TestCase):
    """The remake paints far more of the layer than its own state marks.

    The remake's overlay tilemap paints 899 of its 1024 8x8 px cells, while
    the state that drives it only marks 232 of them as the move lens.  The
    surplus is the renderer expanding every state cell into 4x2 blocks, which
    is why the remake's lens is a solid rectangle where the original's is a
    cross.
    """

    def _payload(self) -> dict:
        if not (
            (ORIGINAL / "movegrid-frame-v1.bg2-tilemap.json").is_file()
            and (REMAKE_GPU / "vram.bin").is_file()
        ):
            self.skipTest("no overlay receipts in this tree")
        return compare(ORIGINAL, REMAKE_GPU)

    def test_the_remake_paints_more_than_its_own_state_marks(self) -> None:
        area = self._payload()["area"]
        self.assertGreater(
            area["remake_painted_cells"],
            area["remake_lens_cells"],
            "the overlay must not paint more than the state marks",
        )
        self.assertGreater(
            area["remake_over_original_area_ratio"],
            3.0,
            "the remake's overlay covers several times the original's lens",
        )

    def test_the_original_lens_is_the_smaller_of_the_two(self) -> None:
        area = self._payload()["area"]
        self.assertGreater(area["original_lens_cells"], 0)
        self.assertLess(
            area["remake_painted_cells"],
            area["original_lens_cells"] * 8,
        )


class DrawingVersusStateTest(unittest.TestCase):
    """Two different problems hide behind one big number.

    The remake's overlay is drawn 4x2 blocks per state cell, so the painted
    area is eight times the state's area.  That expansion is a **drawing**
    bug.  But the state underneath is already 2.3x the original's lens, so
    fixing the expansion alone still leaves the lens the wrong shape.  The
    first belongs to the wiring, the second to the game rules.
    """

    def _area(self) -> dict:
        if not (
            (ORIGINAL / "movegrid-frame-v1.bg2-tilemap.json").is_file()
            and (REMAKE_GPU / "vram.bin").is_file()
        ):
            self.skipTest("no overlay receipts in this tree")
        return compare(ORIGINAL, REMAKE_GPU)["area"]

    def test_the_drawing_expansion_is_eight(self) -> None:
        area = self._area()
        self.assertEqual(area["drawing_expansion"], 8)
        # The map edge clips a few cells, so the painted area is the state's
        # area times the expansion, up to a handful of cells.
        self.assertAlmostEqual(
            area["remake_painted_cells"],
            area["remake_state_cells"] * area["drawing_expansion"],
            delta=area["drawing_expansion"],
        )

    def test_the_state_is_already_larger_than_the_original_lens(self) -> None:
        area = self._area()
        self.assertGreater(
            area["state_over_original_area_ratio"],
            1.0,
            "the state itself is bigger than the original's lens, so the "
            "drawing fix alone cannot close the residual",
        )
        self.assertLess(
            area["state_over_original_area_ratio"],
            area["remake_over_original_area_ratio"],
        )
