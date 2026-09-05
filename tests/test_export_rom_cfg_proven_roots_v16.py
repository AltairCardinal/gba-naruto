#!/usr/bin/env python3
"""TDD contracts for the frozen CFG proven-roots v16 exporter."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v16-sol-20260901"
ROOTS = [
    0x08BF78, 0x068D20, 0x0986B0, 0x06188C, 0x061290,
    0x097110, 0x09C0F4, 0x06154C, 0x09AE14, 0x09AE28,
    0x061538, 0x09C44C, 0x06128C, 0x061150, 0x061F24,
]


def _products():
    from tools import export_rom_cfg_proven_roots_v16 as exporter
    from tools import verify_rom_cfg_proven_roots_v16 as verifier
    return exporter, verifier


class CfgProvenRootsV16ExporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_payload_closes_frozen_denominators_and_metrics(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v16_payload(ROOT)
        self.assertEqual("rom-cfg-proven-roots-v16", payload["schema"])
        self.assertEqual(ROOTS, payload["roots"])
        self.assertEqual(19, len(payload["accepted_producers"]))
        self.assertEqual(2, len(payload["rejected_nonproof_matches"]))
        self.assertEqual(
            [[0x0610C6, 0x09C0F4], [0x09ACD2, 0x09AE28]],
            [[row["file_offset"], row["target_file_offset"]] for row in payload["rejected_nonproof_matches"]],
        )
        summary = payload["traversal"]["summary"]
        self.assertEqual(369, summary["decoded_instruction_count"])
        self.assertEqual(778, summary["reachable_instruction_bytes"])
        self.assertEqual(70, summary["decoded_basic_block_count"])
        self.assertEqual(0, summary["decode_reject_count"])
        self.assertEqual(18, summary["baseline_cross_edge_count"])
        self.assertEqual(778, payload["promotion"]["promoted_from_unknown_bytes"])
        self.assertEqual(778, payload["promotion"]["promotion_bytes"])

    def test_baseline_identity_and_unknown_accounting_are_frozen(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v16_payload(ROOT)
        baseline = payload["coverage_baseline"]
        self.assertEqual(6144296, baseline["classified_bytes"])
        self.assertEqual(147160, baseline["unknown_bytes"])
        self.assertEqual(6291456, baseline["classified_bytes"] + baseline["unknown_bytes"])
        self.assertEqual(147160, payload["promotion"]["baseline_unknown_bytes"])
        self.assertEqual(146382, payload["promotion"]["remaining_unknown_bytes"])
        self.assertEqual(
            payload["promotion"]["baseline_unknown_bytes"],
            payload["promotion"]["remaining_unknown_bytes"] + payload["promotion"]["promoted_from_unknown_bytes"],
        )
        raw = (ROOT / "sequel/rom-byte-coverage.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), baseline["sha256"])
        self.assertTrue(all(row["coverage_owner_class"] != "unknown" for row in payload["accepted_producers"]))
        self.assertTrue(all(row["coverage_owner_class"] == "unknown" for row in payload["rejected_nonproof_matches"]))

    def test_soft_reset_is_terminal_before_its_literal_pool(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v16_payload(ROOT)
        ranges = payload["promotion"]["ranges"]
        self.assertFalse(any(start < 0x09C110 and 0x09C108 < end for start, end in ranges))
        self.assertEqual(369, payload["traversal"]["summary"]["decoded_instruction_count"])
        self.assertEqual(778, payload["traversal"]["summary"]["reachable_instruction_bytes"])

    def test_export_is_atomic_and_independently_verified(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            output = Path(raw) / "candidate"
            manifest = self.exporter.export_rom_cfg_proven_roots_v16(ROOT, output)
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(
                self.verifier.EXPECTED_REPORT,
                self.verifier.verify_rom_cfg_proven_roots_v16(ROOT, output),
            )
            self.assertEqual(
                {"manifest.json", "rom-cfg-proven-roots-v16.json"},
                {path.name for path in output.iterdir()},
            )

    def test_artifact_identity_binds_all_product_and_test_hashes(self) -> None:
        payload = self.exporter.build_cfg_proven_roots_v16_payload(ROOT)
        expected = {
            "contract": "tools/rom_cfg_proven_roots_v16_contract.py",
            "exporter": "tools/export_rom_cfg_proven_roots_v16.py",
            "verifier": "tools/verify_rom_cfg_proven_roots_v16.py",
            "test_exporter": "tests/test_export_rom_cfg_proven_roots_v16.py",
            "test_verifier": "tests/test_verify_rom_cfg_proven_roots_v16.py",
        }
        self.assertEqual(expected, payload["implementation"]["paths"])
        for name, relative in expected.items():
            digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(digest, payload["implementation"][f"{name}_sha256"])

    def test_independent_verifier_does_not_import_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_cfg_proven_roots_v16.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any("export_rom_cfg_proven_roots_v16" in ast.unparse(node) for node in imports))
        self.assertNotIn("cfg-root-scan-20260901", source)


if __name__ == "__main__":
    unittest.main()
