#!/usr/bin/env python3
"""TDD contracts for the combined CFG proven-roots v17 packet."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v17-20260901"
CODE_RANGES = [
    [0x091676, 0x091848], [0x0918F4, 0x0919BE], [0x0919C8, 0x091AA4],
    [0x091AB0, 0x091B0A], [0x091B14, 0x091B3C], [0x091B40, 0x091BB8],
    [0x091BBC, 0x091C2E], [0x091C38, 0x091D14], [0x091D2C, 0x091D7C],
    [0x091D88, 0x091E5A], [0x091E7C, 0x091EA4], [0x091EA8, 0x091F2E],
    [0x091F3C, 0x091FD8],
]
LITERAL_RANGES = [
    [0x091848, 0x0918F4], [0x0919C0, 0x0919C8], [0x091AA4, 0x091AB0],
    [0x091B0C, 0x091B14], [0x091B3C, 0x091B40], [0x091BB8, 0x091BBC],
    [0x091C30, 0x091C38], [0x091D14, 0x091D2C], [0x091D7C, 0x091D88],
    [0x091E5C, 0x091E7C], [0x091EA4, 0x091EA8], [0x091F30, 0x091F3C],
    [0x091FD8, 0x091FE0],
]
GAPS = [[0x0919BE, 0x0919C0], [0x091B0A, 0x091B0C], [0x091C2E, 0x091C30], [0x091E5A, 0x091E5C], [0x091F2E, 0x091F30]]


class CfgProvenRootsV17ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_cfg_proven_roots_v17 as exporter
        from tools import verify_rom_cfg_proven_roots_v17 as verifier
        cls.exporter = exporter
        cls.verifier = verifier
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_payload_freezes_root_producers_and_exact_local_projection(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v17", payload["schema"])
        self.assertEqual(0x0914D8, payload["root"]["file_offset"])
        self.assertEqual([0x08F9E6, 0x08F9F0], [row["file_offset"] for row in payload["root"]["accepted_producers"]])
        self.assertEqual(CODE_RANGES, payload["promotion"]["code_ranges"])
        self.assertEqual(LITERAL_RANGES, payload["promotion"]["literal_ranges"])
        self.assertEqual(GAPS, payload["promotion"]["preserved_unknown_gaps"])
        self.assertEqual(2092, payload["promotion"]["code_bytes"])
        self.assertEqual(308, payload["promotion"]["literal_bytes"])
        self.assertEqual(2400, payload["promotion"]["promotion_bytes"])
        self.assertEqual(10, payload["promotion"]["preserved_unknown_bytes"])

    def test_metrics_and_failure_closed_scope_are_frozen(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        local = payload["target_local_denominator"]
        self.assertEqual(950, local["instruction_count"])
        self.assertEqual(177, local["basic_block_count"])
        self.assertEqual(74, local["baseline_call_edge_count"])
        self.assertEqual([[0x091FD6, "indirect_pc_target"]], local["frontiers"])
        self.assertEqual(77, local["unique_literal_word_count"])
        self.assertFalse(payload["scope"]["natural_runtime_reachability"])
        self.assertFalse(payload["scope"]["alignment_gap_classification"])

    def test_producer_and_gap_mutations_fail_closed(self) -> None:
        bad = bytearray(self.rom)
        bad[0x08F9E6] ^= 1
        with self.assertRaises(ValueError):
            self.exporter.build_payload(ROOT, bytes(bad))
        payload = self.exporter.build_payload(ROOT)
        promoted = payload["promotion"]["union_ranges"]
        for gap_start, gap_end in GAPS:
            self.assertFalse(any(start < gap_end and gap_start < end for start, end in promoted))

    def test_atomic_artifact_passes_independent_verifier(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            manifest = self.exporter.export(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            report = self.verifier.verify_root(ROOT, output)
            self.assertTrue(report["verified"])
            self.assertEqual(2400, report["promotion_bytes"])


if __name__ == "__main__":
    unittest.main()
