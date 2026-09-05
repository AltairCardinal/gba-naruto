#!/usr/bin/env python3
"""Failure-closed tests for the independent CFG proven-roots v16 verifier."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v16-sol-20260901"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class CfgProvenRootsV16VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_cfg_proven_roots_v16 as exporter
        from tools import verify_rom_cfg_proven_roots_v16 as verifier
        cls.exporter, cls.verifier = exporter, verifier

    def _artifact(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_cfg_proven_roots_v16(ROOT, output)
        return output

    def test_report_exposes_exact_public_contract(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            report = self.verifier.verify_rom_cfg_proven_roots_v16(ROOT, self._artifact(Path(raw)))
        self.assertTrue(report["verified"])
        self.assertEqual(15, report["root_count"])
        self.assertEqual(19, report["accepted_producer_count"])
        self.assertEqual(2, report["rejected_nonproof_match_count"])
        self.assertEqual(369, report["decoded_instruction_count"])
        self.assertEqual(778, report["reachable_instruction_bytes"])
        self.assertEqual(0, report["decode_reject_count"])
        self.assertEqual(18, report["baseline_cross_edge_count"])
        self.assertEqual(778, report["promoted_from_unknown_bytes"])

    def test_payload_and_manifest_mutations_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._artifact(Path(raw))
            payload_path = artifact / "rom-cfg-proven-roots-v16.json"
            manifest_path = artifact / "manifest.json"
            original_payload, original_manifest = payload_path.read_bytes(), manifest_path.read_bytes()
            payload = json.loads(original_payload)
            payload["traversal"]["summary"]["decoded_instruction_count"] = 372
            payload_path.write_bytes(_canonical(payload))
            manifest = json.loads(original_manifest)
            manifest["files"][payload_path.name] = {
                "size": payload_path.stat().st_size,
                "sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
            }
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v16(ROOT, artifact)["verified"])
            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            manifest = json.loads(original_manifest)
            manifest["artifact_status"] = "candidate"
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v16(ROOT, artifact)["verified"])

    def test_missing_foreign_and_rejected_match_promotion_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v16(ROOT, parent / "missing")["verified"])
            artifact = self._artifact(parent)
            payload_path = artifact / "rom-cfg-proven-roots-v16.json"
            manifest_path = artifact / "manifest.json"
            payload = json.loads(payload_path.read_bytes())
            payload["rejected_nonproof_matches"][0]["promoted"] = True
            payload_path.write_bytes(_canonical(payload))
            manifest = json.loads(manifest_path.read_bytes())
            manifest["files"][payload_path.name] = {
                "size": payload_path.stat().st_size,
                "sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
            }
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v16(ROOT, artifact)["verified"])


if __name__ == "__main__":
    unittest.main()
