#!/usr/bin/env python3
"""Contract tests for the independent CFG proven-roots v13 verifier."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


def _products():
    try:
        import tools.export_rom_cfg_proven_roots_v13 as exporter
        import tools.verify_rom_cfg_proven_roots_v13 as verifier
    except ModuleNotFoundError as error:
        raise AssertionError("v13 product modules are absent") from error
    return exporter, verifier


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v13-red-20260829"
ARTIFACT = ROOT / "artifacts/rom-cfg-proven-roots-v13"
PAYLOAD_NAME = "rom-cfg-proven-roots-v13.json"
FRONTIERS = [[414_568, "indirect_pc_target"]]
HOLES = [
    {
        "range": [414_430, 414_432],
        "raw_hex": "0000",
        "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    },
    {
        "range": [414_570, 414_572],
        "raw_hex": "0000",
        "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    },
]


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


class CfgProvenRootsV13VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.verifier = _products()

    def _make_artifact(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_cfg_proven_roots_v13(ROOT, output)
        return output

    def test_official_artifact_is_independently_verified(self) -> None:
        report = self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, ARTIFACT)
        self.assertEqual(self.verifier.EXPECTED_REPORT, report)

    def test_report_exposes_exact_frontier_edges_holes_and_nonclaims(self) -> None:
        report = self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, ARTIFACT)
        self.assertTrue(report["verified"])
        self.assertEqual(1, report["target_frontier_count"])
        self.assertEqual(FRONTIERS, report["target_frontiers"])
        self.assertEqual(164, report["target_instruction_internal_edge_count"])
        self.assertEqual(36, report["target_block_internal_edge_count"])
        self.assertEqual(3, report["target_external_call_edge_count"])
        self.assertEqual(6, report["promotion_range_count"])
        self.assertEqual(392, report["promotion_bytes"])
        self.assertEqual(4, report["hole_bytes"])
        self.assertEqual(4, report["unclassified_hole_bytes"])
        self.assertEqual(HOLES, report["holes"])
        self.assertTrue(report["nonclaims"])
        self.assertTrue(all(value is False for value in report["nonclaims"].values()))
        self.assertNotIn("structured_return", report)

    def test_payload_publishes_unresolved_frontier_without_structured_return(self) -> None:
        payload = json.loads((ARTIFACT / PAYLOAD_NAME).read_text())
        target = payload["target"]
        self.assertEqual(FRONTIERS, target["frontiers"])
        self.assertEqual(HOLES, target["holes"])
        self.assertNotIn("structured_return", target)
        self.assertFalse(payload["scope"]["structured_return_proven"])
        self.assertFalse(payload["scope"]["global_indirect_target_denominator_complete"])

    def test_payload_manifest_status_and_raw_rom_mutations_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._make_artifact(Path(raw))
            payload_path = artifact / PAYLOAD_NAME
            manifest_path = artifact / "manifest.json"
            original_payload = payload_path.read_bytes()
            original_manifest = manifest_path.read_bytes()

            payload = json.loads(original_payload)
            payload["promotion"]["promotion_bytes"] = 391
            payload_path.write_bytes(_canonical(payload))
            manifest = json.loads(original_manifest)
            manifest["files"][PAYLOAD_NAME] = {
                "size": payload_path.stat().st_size,
                "sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
            }
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(
                self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, artifact)[
                    "verified"
                ]
            )

            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            manifest = json.loads(original_manifest)
            manifest["artifact_status"] = "candidate"
            manifest_path.write_bytes(_canonical(manifest))
            self.assertFalse(
                self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, artifact)[
                    "verified"
                ]
            )

            payload_path.write_bytes(original_payload)
            manifest_path.write_bytes(original_manifest)
            mutated_rom = Path(raw) / "mutated.gba"
            rom = bytearray((ROOT / "rom/base.gba").read_bytes())
            rom[414_200] ^= 1
            mutated_rom.write_bytes(rom)
            original_safe_file = self.verifier._safe_file

            def substitute_rom(root: Path, path: Path) -> Path:
                if Path(path) == self.verifier.ROM_PATH:
                    return mutated_rom
                return original_safe_file(root, path)

            with mock.patch.object(
                self.verifier, "_safe_file", side_effect=substitute_rom
            ):
                self.assertFalse(
                    self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, artifact)[
                        "verified"
                    ]
                )

    def test_missing_symlink_and_foreign_artifact_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            parent = Path(raw)
            self.assertFalse(
                self.verifier.verify_rom_cfg_proven_roots_v13(
                    ROOT, parent / "missing"
                )["verified"]
            )
            real = parent / "real"
            real.mkdir()
            linked = parent / "linked"
            linked.symlink_to(real, target_is_directory=True)
            self.assertFalse(
                self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, linked)[
                    "verified"
                ]
            )
            foreign = parent / "foreign"
            foreign.mkdir()
            (foreign / "foreign.txt").write_text("foreign")
            self.assertFalse(
                self.verifier.verify_rom_cfg_proven_roots_v13(ROOT, foreign)[
                    "verified"
                ]
            )

    def test_receipt_path_must_match_the_actual_artifact_directory(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            copied = Path(raw) / "copied"
            shutil.copytree(ARTIFACT, copied)
            frozen_implementation = json.loads(
                (ARTIFACT / PAYLOAD_NAME).read_text()
            )["implementation"]
            with mock.patch.object(
                self.verifier,
                "_implementation",
                return_value=frozen_implementation,
            ):
                report = self.verifier.verify_rom_cfg_proven_roots_v13(
                    ROOT, copied
                )
            self.assertFalse(report["verified"])
            self.assertRegex(report["errors"][0], "receipt.*path|actual artifact")

    def test_verifier_has_no_exporter_import_and_cli_is_isolated(self) -> None:
        source_path = Path(self.verifier.__file__)
        tree = ast.parse(source_path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any("export_rom_cfg_proven_roots_v13" in name for name in imports)
        )

        ordinary = subprocess.run(
            [sys.executable, str(source_path), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, ordinary.returncode)
        self.assertIn("requires Python -I -S", ordinary.stdout + ordinary.stderr)

        command = [
            sys.executable,
            "-I",
            "-S",
            str(source_path),
            "--root",
            str(ROOT),
            "--artifact-dir",
            str(ARTIFACT),
        ]
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(self.verifier.EXPECTED_REPORT, json.loads(completed.stdout))


if __name__ == "__main__":
    unittest.main()
