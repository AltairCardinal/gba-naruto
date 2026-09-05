#!/usr/bin/env python3
"""Contract tests for the independent CFG proven-roots v12 verifier."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

def _products():
    try:
        import tools.export_rom_cfg_proven_roots_v12 as exporter
        import tools.verify_rom_cfg_proven_roots_v12 as verifier
    except ModuleNotFoundError as error:
        raise AssertionError("v12 product modules are absent") from error
    return exporter, verifier


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v12-20260829"
ARTIFACT = ROOT / "artifacts/rom-cfg-proven-roots-v12"
PAYLOAD_NAME = "rom-cfg-proven-roots-v12.json"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


class CfgProvenRootsV12VerifierTests(unittest.TestCase):
    def _make_artifact(self, parent: Path) -> Path:
        exporter, _ = _products()
        output = parent / "candidate"
        exporter.export_rom_cfg_proven_roots_v12(ROOT, output)
        return output

    def test_official_artifact_is_independently_verified(self) -> None:
        _, verifier = _products()
        report = verifier.verify_rom_cfg_proven_roots_v12(ROOT, ARTIFACT)
        self.assertEqual(verifier.EXPECTED_REPORT, report)

    def test_payload_manifest_and_raw_rom_mutations_fail_closed(self) -> None:
        _, verifier = _products()
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._make_artifact(Path(raw))
            payload_path = artifact / PAYLOAD_NAME
            manifest_path = artifact / "manifest.json"
            original_payload = payload_path.read_bytes()
            original_manifest = manifest_path.read_bytes()
            payload = json.loads(original_payload)
            payload["promotion"]["promotion_bytes"] = 499
            payload_path.write_bytes(_canonical(payload))
            manifest = json.loads(original_manifest)
            manifest["files"][PAYLOAD_NAME]["size"] = payload_path.stat().st_size
            manifest["files"][PAYLOAD_NAME]["sha256"] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(verifier.verify_rom_cfg_proven_roots_v12(ROOT, artifact)["verified"])
            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            manifest = json.loads(original_manifest)
            manifest["artifact_status"] = "candidate"
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(verifier.verify_rom_cfg_proven_roots_v12(ROOT, artifact)["verified"])

    def test_missing_symlink_and_foreign_artifact_fail_closed(self) -> None:
        _, verifier = _products()
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            self.assertFalse(verifier.verify_rom_cfg_proven_roots_v12(ROOT, parent / "missing")["verified"])
            real = parent / "real"
            real.mkdir()
            linked = parent / "linked"
            linked.symlink_to(real, target_is_directory=True)
            self.assertFalse(verifier.verify_rom_cfg_proven_roots_v12(ROOT, linked)["verified"])
            foreign = parent / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("foreign")
            self.assertFalse(verifier.verify_rom_cfg_proven_roots_v12(ROOT, foreign)["verified"])

    def test_verifier_has_no_exporter_import_and_cli_isolated(self) -> None:
        _, verifier = _products()
        source_path = Path(verifier.__file__)
        tree = ast.parse(source_path.read_text())
        forbidden = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                forbidden.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                forbidden.append(node.module)
        self.assertFalse(any("export_rom_cfg_proven_roots_v12" in name for name in forbidden))
        command = [sys.executable, "-I", "-S", str(source_path), "--root", str(ROOT), "--artifact-dir", str(ARTIFACT)]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(verifier.EXPECTED_REPORT, json.loads(completed.stdout))

    def test_report_exposes_nonclaims_and_exact_two_holes(self) -> None:
        _, verifier = _products()
        report = verifier.verify_rom_cfg_proven_roots_v12(ROOT, ARTIFACT)
        self.assertTrue(report["verified"])
        self.assertEqual(500, report["promotion_bytes"])
        self.assertEqual(8, report["promotion_range_count"])
        self.assertEqual(4, report["hole_bytes"])
        self.assertEqual([[410818, 410820], [410890, 410892]], report["holes"])
        self.assertTrue(report["nonclaims"])
        self.assertTrue(all(value is False for value in report["nonclaims"].values()))


if __name__ == "__main__":
    unittest.main()
