#!/usr/bin/env python3
"""TDD contracts for the target-local CFG proven-roots v18 packet."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v18-20260901"
CODE_RANGES = [[0x091070, 0x0910B4], [0x0910BC, 0x0910CE], [0x0910D0, 0x091110], [0x091114, 0x091236], [0x091254, 0x09133A], [0x091350, 0x0913B0], [0x0913BC, 0x091438], [0x091440, 0x0914CA], [0x0914D8, 0x09163E]]
LITERAL_RANGES = [[0x09106C, 0x091070], [0x0910B4, 0x0910BC], [0x091110, 0x091114], [0x091238, 0x091254], [0x09133C, 0x091350], [0x0913B0, 0x0913BC], [0x091438, 0x091440], [0x0914CC, 0x0914D8]]
GAPS = [[0x0910CE, 0x0910D0], [0x091236, 0x091238], [0x09133A, 0x09133C], [0x0914CA, 0x0914CC]]


class CfgProvenRootsV18ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_cfg_proven_roots_v18 as exporter
        from tools import verify_rom_cfg_proven_roots_v18 as verifier
        cls.exporter = exporter
        cls.verifier = verifier
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_payload_freezes_roots_producers_and_projection(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v18", payload["schema"])
        self.assertEqual([0x0910D0, 0x0914D8], [row["file_offset"] for row in payload["roots"]])
        self.assertEqual([0x091E82, 0x091F1C, 0x08F9E6, 0x08F9F0], [row["file_offset"] for row in payload["accepted_producers"]])
        self.assertEqual(CODE_RANGES, payload["promotion"]["code_ranges"])
        self.assertEqual(LITERAL_RANGES, payload["promotion"]["literal_ranges"])
        self.assertEqual(GAPS, payload["promotion"]["preserved_unknown_gaps"])
        self.assertEqual((1386, 96, 1482, 8), tuple(payload["promotion"][key] for key in ("code_bytes", "literal_bytes", "promotion_bytes", "preserved_unknown_bytes")))

    def test_failure_closed_scope_and_mutations(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        self.assertEqual([[0x0910CC, "indirect_pc_target"], [0x0914C8, "indirect_pc_target"]], payload["target_local_denominator"]["frontiers"])
        self.assertFalse(payload["scope"]["target_outside_subtree_classification"])
        bad = bytearray(self.rom)
        bad[0x091E82] ^= 1
        with self.assertRaises(ValueError):
            self.exporter.build_payload(ROOT, bytes(bad))

    def test_atomic_artifact_passes_independent_verifier(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            self.exporter.export(ROOT, output)
            report = self.verifier.verify_root(ROOT, output)
            self.assertTrue(report["verified"])
            self.assertEqual(1482, report["promotion_bytes"])


if __name__ == "__main__":
    unittest.main()
