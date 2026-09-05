#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM = (ROOT / "rom/base.gba").read_bytes()


class SchedulerCallbackLifecycleGateTests(unittest.TestCase):
    def _verify(self, rom: bytes = ROM) -> dict:
        from tools.verify_rom_scheduler_callback_lifecycle_gate import (
            verify_scheduler_callback_lifecycle_gate,
        )

        return verify_scheduler_callback_lifecycle_gate(ROOT, rom=rom)

    def test_fixed_gate_closes_two_callbacks_but_keeps_candidate_unknown(self):
        report = self._verify()

        self.assertTrue(report["verified"], report)
        self.assertEqual([], report["errors"])
        self.assertEqual(
            "rom-scheduler-callback-lifecycle-gate-v1", report["schema"]
        )
        self.assertEqual(
            {
                "candidate_range": [0x59EAE0, 0x59F560],
                "candidate_bytes": 2688,
                "bytes_promoted": 0,
                "promotion_eligible": False,
                "lifecycle_closed": False,
                "coverage_action": "keep_unknown",
                "blocking_callback": "0x0808F654",
            },
            report["decision"],
        )

        callbacks = report["callbacks"]
        self.assertEqual(
            "open_computed_or_indirect_entry",
            callbacks["0x0808F654"]["lifecycle_status"],
        )
        self.assertEqual(
            "registration_dispatch_return_closed",
            callbacks["0x0808F73C"]["lifecycle_status"],
        )
        self.assertEqual(
            "registration_dispatch_return_closed",
            callbacks["0x0808EF2C"]["lifecycle_status"],
        )
        self.assertEqual([], callbacks["0x0808F654"]["pointer_occurrences"])
        self.assertEqual([], callbacks["0x0808F654"]["direct_branch_callsites"])
        self.assertEqual(
            [0x6107C, 0x859B4],
            callbacks["0x0808F73C"]["pointer_occurrences"],
        )
        self.assertEqual(
            [0x8F204], callbacks["0x0808EF2C"]["pointer_occurrences"]
        )

    def test_direct_registration_and_consumer_denominators_are_exact(self):
        report = self._verify()

        registrations = report["scheduler_dispatch"]["direct_registrations"]
        self.assertEqual(8, len(registrations))
        self.assertEqual(
            [
                (0x6106C, 1, "0x0808F73D"),
                (0x61D4E, 0, "0x08061D71"),
                (0x6EAC4, 2, "0x0806E959"),
                (0x7AAE0, 4, "0x0807A34D"),
                (0x8599A, 1, "0x0808F73D"),
                (0x85A08, 5, "0x0808584D"),
                (0x8C1E0, 2, "0x0808C175"),
                (0x8F1CE, 2, "0x0808EF2D"),
            ],
            [
                (item["callsite"], item["slot"], item["callback_thumb"])
                for item in registrations
            ],
        )
        self.assertEqual(
            ["0x0808F73D", "0x0808F73D"],
            report["scheduler_dispatch"]["slot_histories"]["1"],
        )
        self.assertEqual(
            ["0x0806E959", "0x0808C175", "0x0808EF2D"],
            report["scheduler_dispatch"]["slot_histories"]["2"],
        )
        self.assertEqual(
            [0x8F644, 0x8F9C0],
            report["consumer_paths"]["0x0808A0F0"]["direct_callsites"],
        )
        self.assertEqual(
            [0x8F668],
            report["consumer_paths"]["0x0808F618"]["direct_callsites"],
        )
        self.assertEqual(
            [0x8F7CE],
            report["consumer_paths"]["0x0808F9C0"]["direct_callsites"],
        )

    def test_pointer_and_registration_denominators_fail_closed(self):
        extra_pointer = bytearray(ROM)
        extra_pointer[0x1000 : 0x1004] = (0x0808F655).to_bytes(4, "little")
        report = self._verify(bytes(extra_pointer))
        self.assertFalse(report["verified"], report)
        self.assertTrue(
            any("0x0808F654 pointer denominator changed" in error for error in report["errors"]),
            report,
        )

        changed_registration = bytearray(ROM)
        changed_registration[0x6106C] ^= 1
        report = self._verify(bytes(changed_registration))
        self.assertFalse(report["verified"], report)
        self.assertTrue(
            any("registration wrapper callsite denominator changed" in error for error in report["errors"]),
            report,
        )

        changed_dispatch = bytearray(ROM)
        changed_dispatch[0x61C68] ^= 1
        report = self._verify(bytes(changed_dispatch))
        self.assertFalse(report["verified"], report)
        self.assertTrue(
            any("dispatch_common_and_literals raw window changed" in error for error in report["errors"]),
            report,
        )

        changed_counterexample = bytearray(ROM)
        changed_counterexample[0x3EFEE] ^= 1
        report = self._verify(bytes(changed_counterexample))
        self.assertFalse(report["verified"], report)
        self.assertTrue(
            any("scenario 50 state+0x16 writer changed" in error for error in report["errors"]),
            report,
        )

    def test_candidate_counterexample_and_cli_report_are_frozen(self):
        report = self._verify()
        self.assertEqual(
            {
                "scenario": 50,
                "scenario_range": [0x3EE81, 0x3EFF4],
                "state_16": 31,
                "state_19": 30,
                "lookup_value": 90,
                "combined_index": 120,
                "claimed_safe_max": 111,
                "disproves_local_safe_bound": True,
            },
            report["counterexample"],
        )
        self.assertFalse(report["scope"]["natural_runtime_oob_proven"])
        self.assertFalse(report["scope"]["computed_producer_denominator_complete"])
        self.assertFalse(report["scope"]["candidate_record_count_proven"])

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/verify_rom_scheduler_callback_lifecycle_gate.py",
                    "--root",
                    ".",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertEqual(report, json.loads(output.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
