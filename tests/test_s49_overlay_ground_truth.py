#!/usr/bin/env python3
"""The remake's overlay must approach the original's, unit by unit.

The original's BG2 dump says which family every 16x16 px unit of the visible
window carries -- that is the **ground truth**, and it does not depend on the
remake at all.  Writing it down turns "the remake's move-range rules have to
match the original's" from a design task into a pass/fail task.

The gate is a **ratchet**: the gap (how many units disagree) may only shrink.
Shrinking it is the logic work; growing it means a change made the overlay
worse, and the gate says so.

These tests pin:

* the ground truth is reproducible from the original's dump alone;
* the measured gap agrees with the receipt;
* the gap never exceeds the recorded baseline.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "butano" / "compare_s49_overlay_layers.py"
COMPARE = ROOT / "artifacts" / "s49-overlay-layer-compare-v1" / "compare.json"
EXPECTED = ROOT / "artifacts" / "s49-overlay-layer-compare-v1" / "expected_units.json"
ORIGINAL = ROOT / "artifacts" / "s49-original-movegrid-tilemap-v1"
REMAKE_GPU = ROOT / "artifacts" / "s49-remake-gpu-baseline-step20-v1"

sys.path.insert(0, str(ROOT))

from tools.butano.compare_s49_overlay_layers import (  # noqa: E402
    compare,
    expected_units,
)


class OverlayGroundTruthTest(unittest.TestCase):
    def _skip_without_receipts(self) -> None:
        if not (
            EXPECTED.is_file()
            and COMPARE.is_file()
            and (ORIGINAL / "movegrid-frame-v1.bg2-tilemap.json").is_file()
            and (REMAKE_GPU / "vram.bin").is_file()
        ):
            self.skipTest("no overlay receipts in this tree")

    def test_the_ground_truth_is_reproducible_from_the_original_alone(self) -> None:
        self._skip_without_receipts()
        recorded = json.loads(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(
            recorded["units"],
            expected_units(ORIGINAL),
            "the ground truth must come from the original's own dump, "
            "not from the remake",
        )

    def test_the_measured_gap_agrees_with_the_receipt(self) -> None:
        self._skip_without_receipts()
        receipt = json.loads(COMPARE.read_text(encoding="utf-8"))
        fresh = compare(ORIGINAL, REMAKE_GPU)
        self.assertEqual(
            fresh["summary"]["units_with_different_family"],
            receipt["summary"]["units_with_different_family"],
        )
        self.assertEqual(fresh["summary"]["units"], receipt["summary"]["units"])

    def test_the_gap_is_recorded_as_a_ratchet(self) -> None:
        """The gap may only shrink; growing it is a regression."""
        self._skip_without_receipts()
        receipt = json.loads(COMPARE.read_text(encoding="utf-8"))
        gap = receipt["summary"]["units_with_different_family"]
        baseline = receipt["summary"].get("baseline_units_with_different_family")
        if baseline is None:
            # First run: record the baseline.
            receipt["summary"]["baseline_units_with_different_family"] = gap
            COMPARE.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return
        self.assertLessEqual(
            gap,
            baseline,
            f"the overlay gap grew from {baseline} to {gap} units",
        )

    def test_the_emit_mode_writes_the_same_ground_truth(self) -> None:
        self._skip_without_receipts()
        with __import__("tempfile").TemporaryDirectory() as tmp:
            out = Path(tmp) / "expected.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(ROOT),
                    "--out-dir",
                    str(Path(tmp) / "out"),
                    "--emit-expected",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(
                written["units"],
                json.loads(EXPECTED.read_text(encoding="utf-8"))["units"],
            )


if __name__ == "__main__":
    unittest.main()
