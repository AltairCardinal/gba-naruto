#!/usr/bin/env python3
"""The original's unit-outline colour counter, pinned as ground truth.

The original rewrites palette entry 15 of a unit's palette bank every frame.
Round 26 closed the two questions the ROM analysis alone could not answer, by
reading the hardware while the original ROM runs:

* the counter starts at **0** and is **not** reset when a battle starts -- it
  counts from power-on, so the outline colour's *phase* depends on the
  absolute frame count;
* it advances **exactly +1 per frame**, so the triangle wave has a **64
  frame** period (16 levels up, 16 levels down, selected by bit 4).

This gate pins the exported receipt and the answers, and -- most importantly
-- re-checks the model against the recorded PRAM samples: the value the
model predicts for the outline colour must equal the value the hardware
actually shows, sample after sample.  A wrong waveform cannot pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "tools/butano/export_s49_outline_counter.py"
OUT_DIR = ROOT / "artifacts/s49-outline-triangle-counter-20261021-v1"
COUNTER = OUT_DIR / "counter.json"
MANIFEST = OUT_DIR / "manifest.json"

PINNED_INITIAL_VALUE = 0
PINNED_ADVANCE_PER_FRAME = 1
PINNED_PERIOD_FRAMES = 64
PINNED_BATTLE14_PHASE = 44
PINNED_MISMATCHES = 0


def _counter() -> dict:
    if not COUNTER.is_file():
        raise unittest.SkipTest(f"missing receipt: {COUNTER}")
    return json.loads(COUNTER.read_text(encoding="utf-8"))


class OutlineCounterTest(unittest.TestCase):
    """The counter's behaviour must stay pinned and self-consistent."""

    def test_the_exporter_check_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(EXPORTER), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"exporter --check failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_the_answers_are_pinned(self) -> None:
        answers = _counter()["answers"]
        self.assertEqual(answers["initial_value"], PINNED_INITIAL_VALUE)
        self.assertEqual(answers["advance_per_frame"], PINNED_ADVANCE_PER_FRAME)
        self.assertEqual(
            answers["triangle_period_frames"], PINNED_PERIOD_FRAMES
        )
        self.assertEqual(
            answers["battle14_entry_phase_mod_64"], PINNED_BATTLE14_PHASE
        )
        self.assertEqual(
            answers["live_model_mismatches"], PINNED_MISMATCHES
        )

    def test_the_power_on_probe_shows_a_counter_that_starts_at_zero(self) -> None:
        probe = _counter()["probes"]["power-on"]
        self.assertEqual(probe["first_counter"], 0)
        self.assertEqual(probe["counter_deltas"], {"0": 299})

    def test_the_battle_probe_advances_by_one_per_frame(self) -> None:
        probe = _counter()["probes"]["checkpoint-14-entry"]
        self.assertEqual(probe["counter_deltas"], {"1": 199})
        self.assertEqual(probe["counter_mod_64"], PINNED_BATTLE14_PHASE)

    def test_the_model_predicts_every_recorded_outline_colour(self) -> None:
        counter = _counter()
        for name, probe in counter["probes"].items():
            for sample in probe["first_samples"]:
                self.assertTrue(
                    sample["matches"],
                    f"{name} frame {sample['frame']}: "
                    f"model {sample['model_v']} vs observed {sample['observed_v']}",
                )

    def test_the_waveform_is_a_64_frame_triangle(self) -> None:
        """Rising half, then falling half, then rising again."""
        probe = _counter()["probes"]["checkpoint-14-entry"]
        values = [sample["observed_v"] for sample in probe["first_samples"]]
        self.assertEqual(values[:4], [25, 27, 29, 31])
        self.assertEqual(values[4:8], [31, 29, 27, 25])
        self.assertEqual(values[8:12], [23, 21, 19, 17])

    def test_the_manifest_lists_every_probe_receipt(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for probe in ("power-on", "checkpoint-14-entry", "postbattle-task-menu"):
            key = (
                "artifacts/s49-outline-triangle-counter-20261021-v1/probe/"
                f"{probe}/samples.jsonl"
            )
            self.assertIn(key, manifest["inputs"])
            self.assertIn("sha256", manifest["inputs"][key])


if __name__ == "__main__":
    unittest.main()
