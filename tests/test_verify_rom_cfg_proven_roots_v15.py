#!/usr/bin/env python3
"""Contract tests for the independent CFG proven-roots v15 verifier."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v15-implementation-20260830"
PAYLOAD_NAME = "rom-cfg-proven-roots-v15.json"


def _products():
    try:
        from tools import export_rom_cfg_proven_roots_v15 as exporter
        from tools import verify_rom_cfg_proven_roots_v15 as verifier
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v15 product modules are absent") from error
    return exporter, verifier


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


class CfgProvenRootsV15VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()

    def _make_artifact(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_cfg_proven_roots_v15(ROOT, output)
        return output

    def test_report_exposes_exact_metrics_and_rejected_root(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            report = self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, self._make_artifact(Path(raw)))
        self.assertTrue(report["verified"])
        self.assertEqual("rom-cfg-proven-roots-v15-verification-v1", report["schema"])
        self.assertEqual(4, report["target_root_count"])
        self.assertEqual([0x09A3E0, 0x0611F4, 0x0618FC, 0x08B6F0], report["target_roots"])
        self.assertEqual([0x09C0F4], report["rejected_roots"])
        self.assertEqual(5, report["producer_count"])
        self.assertEqual(197, report["target_decoded_instruction_count"])
        self.assertEqual(31, report["target_decoded_basic_block_count"])
        self.assertEqual(398, report["target_reachable_instruction_bytes"])
        self.assertEqual(3, report["target_frontier_count"])
        self.assertEqual([[0x061274, "indirect_pc_target"], [0x061934, "indirect_pc_target"], [0x08B798, "indirect_pc_target"]], report["target_frontiers"])
        self.assertEqual(2, report["target_external_call_edge_count"])
        self.assertEqual(52, report["target_literal_bytes"])
        self.assertEqual(450, report["promotion_bytes"])
        self.assertEqual(386, report["hole_bytes"])
        self.assertEqual(10, report["promotion_range_count"])
        self.assertEqual(10, report["semantic_promotion_range_count"])
        self.assertEqual(7, report["promotion_union_range_count"])
        self.assertTrue(report["nonclaims"])
        self.assertTrue(all(value is False for value in report["nonclaims"].values()))

    def test_mutated_payload_manifest_and_raw_rom_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            artifact = self._make_artifact(parent)
            payload_path = artifact / PAYLOAD_NAME
            manifest_path = artifact / "manifest.json"
            original_payload = payload_path.read_bytes()
            original_manifest = manifest_path.read_bytes()

            payload = json.loads(original_payload)
            payload["promotion"]["promotion_bytes"] = 449
            payload_path.write_bytes(_canonical(payload))
            manifest = json.loads(original_manifest)
            manifest["files"][PAYLOAD_NAME] = {
                "size": payload_path.stat().st_size,
                "sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
            }
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, artifact)["verified"])

            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            manifest = json.loads(original_manifest)
            manifest["artifact_status"] = "candidate"
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, artifact)["verified"])

            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            mutated_rom = parent / "mutated.gba"
            rom = bytearray((ROOT / "rom/base.gba").read_bytes())
            rom[0x0611F4] ^= 1
            mutated_rom.write_bytes(rom)
            original_safe_file = self.verifier._safe_file

            def substitute(root: Path, path: Path) -> Path:
                if Path(path) == self.verifier.ROM_PATH:
                    return mutated_rom
                return original_safe_file(root, path)

            with mock.patch.object(self.verifier, "_safe_file", side_effect=substitute):
                self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, artifact)["verified"])

    def test_upstream_mutation_and_exact_rejection_vector_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            artifact = self._make_artifact(parent)
            payload_path = artifact / PAYLOAD_NAME
            original_payload = payload_path.read_bytes()
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["rejected_targets"][0]["root"] = 0x09C0F6
            payload_path.write_bytes(_canonical(payload))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, artifact)["verified"])
            payload_path.write_bytes(original_payload)

            upstream = ROOT / "artifacts/rom-cfg-proven-roots-v12/rom-cfg-proven-roots-v12.json"
            original_safe_file = self.verifier._safe_file
            mutated_upstream = parent / upstream.name
            upstream_bytes = bytearray(upstream.read_bytes())
            upstream_bytes[0] ^= 1
            mutated_upstream.write_bytes(upstream_bytes)

            def substitute(root: Path, path: Path) -> Path:
                if Path(path).as_posix() == upstream.relative_to(ROOT).as_posix():
                    return mutated_upstream
                return original_safe_file(root, path)

            with mock.patch.object(self.verifier, "_safe_file", side_effect=substitute):
                report = self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, artifact)
            self.assertFalse(report["verified"])

    def test_missing_symlink_foreign_and_copied_receipt_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, parent / "missing")["verified"])
            real = parent / "real"
            real.mkdir()
            linked = parent / "linked"
            linked.symlink_to(real, target_is_directory=True)
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, linked)["verified"])
            artifact = self._make_artifact(parent / "source")
            copied = parent / "copied"
            shutil.copytree(artifact, copied)
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, copied)["verified"])
            foreign = parent / "foreign"
            shutil.copytree(artifact, foreign)
            (foreign / "foreign.txt").write_text("foreign", encoding="utf-8")
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, foreign)["verified"])

    def test_copied_artifact_with_both_receipt_paths_rebound_fails_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            artifact = self._make_artifact(parent / "source")
            copied = parent / "rebound"
            shutil.copytree(artifact, copied)
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            rebound_path = copied.relative_to(ROOT).as_posix()
            manifest["producer"]["command"][-1] = rebound_path
            manifest["verifier"]["command"][-1] = rebound_path
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(self.verifier.verify_rom_cfg_proven_roots_v15(ROOT, copied)["verified"])


if __name__ == "__main__":
    unittest.main()
