#!/usr/bin/env python3
"""Contract tests for the independent CFG proven-roots v14 verifier."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v14-red-20260830"
ARTIFACT = ROOT / "artifacts/rom-cfg-proven-roots-v14"
PAYLOAD_NAME = "rom-cfg-proven-roots-v14.json"


def _products():
    try:
        from tools import export_rom_cfg_proven_roots_v14 as exporter
        from tools import verify_rom_cfg_proven_roots_v14 as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v14 product modules are absent") from error
    return exporter, verifier


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


class CfgProvenRootsV14VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()

    def _make_artifact(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_cfg_proven_roots_v14(ROOT, output)
        return output

    def test_official_artifact_is_independently_verified(self) -> None:
        self.assertEqual(
            self.verifier.EXPECTED_REPORT,
            self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, ARTIFACT),
        )

    def test_report_exposes_exact_dual_root_metrics_and_nonclaims(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            report = self.verifier.verify_rom_cfg_proven_roots_v14(
                ROOT, self._make_artifact(Path(raw))
            )
        self.assertTrue(report["verified"])
        self.assertEqual(2, report["target_root_count"])
        self.assertEqual(5, report["producer_count"])
        self.assertEqual(60, report["target_decoded_instruction_count"])
        self.assertEqual(10, report["target_decoded_basic_block_count"])
        self.assertEqual(120, report["target_reachable_instruction_bytes"])
        self.assertEqual(2, report["target_frontier_count"])
        self.assertEqual(
            [[402_686, "indirect_pc_target"], [402_758, "indirect_pc_target"]],
            report["target_frontiers"],
        )
        self.assertEqual(64, report["target_instruction_internal_edge_count"])
        self.assertEqual(14, report["target_block_internal_edge_count"])
        self.assertEqual(10, report["target_literal_reference_count"])
        self.assertEqual(10, report["target_unique_literal_word_count"])
        self.assertEqual(40, report["target_literal_bytes"])
        self.assertEqual(160, report["promotion_bytes"])
        self.assertEqual(0, report["hole_bytes"])
        self.assertTrue(report["nonclaims"])
        self.assertTrue(all(value is False for value in report["nonclaims"].values()))

    def test_payload_manifest_status_and_raw_rom_mutations_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            artifact = self._make_artifact(parent)
            payload_path = artifact / PAYLOAD_NAME
            manifest_path = artifact / "manifest.json"
            original_payload = payload_path.read_bytes()
            original_manifest = manifest_path.read_bytes()
            payload = json.loads(original_payload)
            payload["promotion"]["promotion_bytes"] = 159
            payload_path.write_bytes(_canonical(payload))
            manifest = json.loads(original_manifest)
            manifest["files"][PAYLOAD_NAME] = {
                "size": payload_path.stat().st_size,
                "sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
            }
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, artifact)["verified"])
            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            manifest = json.loads(original_manifest)
            manifest["artifact_status"] = "candidate"
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, artifact)["verified"])

            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            mutated_rom = parent / "mutated.gba"
            rom = bytearray((ROOT / "rom/base.gba").read_bytes())
            rom[402_624] ^= 1
            mutated_rom.write_bytes(rom)
            original_safe_file = self.verifier._safe_file

            def substitute(root: Path, path: Path) -> Path:
                if Path(path) == self.verifier.ROM_PATH:
                    return mutated_rom
                return original_safe_file(root, path)

            with mock.patch.object(self.verifier, "_safe_file", side_effect=substitute):
                self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, artifact)["verified"])

    def test_missing_symlink_foreign_and_copied_receipt_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, parent / "missing")["verified"])
            real = parent / "real"
            real.mkdir()
            linked = parent / "linked"
            linked.symlink_to(real, target_is_directory=True)
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, linked)["verified"])
            artifact = self._make_artifact(parent / "source")
            copied = parent / "copied"
            shutil.copytree(artifact, copied)
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v14(ROOT, copied)["verified"])


if __name__ == "__main__":
    unittest.main()
