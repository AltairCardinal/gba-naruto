#!/usr/bin/env python3
"""Contract tests for the immutable v12 promotion-bundle verifier."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-cfg-proven-roots-v12"
WRAPPER = ROOT / "tools/verify_rom_cfg_proven_roots_v12_bundle.py"
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v12-bundle-20260829"


def _product():
    try:
        from tools import verify_rom_cfg_proven_roots_v12_bundle as bundle
    except ModuleNotFoundError as error:
        raise AssertionError("v12 immutable bundle verifier is absent") from error
    return bundle


class CfgProvenRootsV12BundleVerifierTests(unittest.TestCase):
    def test_current_accepted_bundle_rebuilds_legacy_contract_without_live_coverage(self):
        bundle = _product()
        report = bundle.verify_bundle(ROOT, ARTIFACT)

        self.assertEqual(
            "rom-cfg-proven-roots-v12-bundle-verification-v1", report["schema"]
        )
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertEqual("rom-cfg-proven-roots-v12", report["artifact_schema"])
        self.assertEqual("accepted", report["artifact_status"])
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertTrue(report["legacy_control_flow_rebuilt"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertEqual(500, report["promotion_bytes"])
        self.assertEqual(8, report["promotion_range_count"])
        self.assertEqual(372, report["promotion_code_bytes"])
        self.assertEqual(128, report["promotion_literal_bytes"])
        self.assertEqual(4, report["hole_bytes"])
        self.assertEqual(237, report["source_decoded_instruction_count"])
        self.assertEqual(40, report["source_decoded_basic_block_count"])
        self.assertEqual(508, report["source_reachable_instruction_bytes"])
        self.assertEqual(0, report["source_frontier_count"])
        self.assertEqual(182, report["target_decoded_instruction_count"])
        self.assertEqual(35, report["target_decoded_basic_block_count"])
        self.assertEqual(372, report["target_reachable_instruction_bytes"])
        self.assertEqual(0, report["target_frontier_count"])
        self.assertEqual(35, report["target_literal_reference_count"])
        self.assertEqual(32, report["target_unique_literal_word_count"])
        self.assertEqual(
            "bf88e08f4eed6b53e1debef709c2ef13fb891c11e9c172485e494eef57954677",
            report["manifest_sha256"],
        )
        self.assertEqual(
            "fd9df8f3d93de1df5aa7e725040f27f854d08e8203d6cada51db829ddcd9bcee",
            report["payload_sha256"],
        )
        self.assertEqual(
            "1043291dfb16b90ef025242b976a4bf89a6a0173a0ac4904fc3534d625acbede",
            report["legacy_verifier_sha256"],
        )
        self.assertEqual(
            "b2b985dee623ffe0c5e3139112d2021bffd3ea0dbd32f8ad90c9fe91b14928cd",
            report["promotion_range_vector_sha256"],
        )
        self.assertEqual(
            "a8043f37679964db642c2d743812d5aab93a7193016d3ffd14d805b9105cf8e8",
            report["promotion_packed_sha256"],
        )

    def test_artifact_mutations_and_foreign_files_fail_closed(self):
        bundle = _product()
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bundle-test-", dir=EXPERIMENT) as raw:
            temporary = Path(raw)
            for index, name in enumerate(
                ("manifest.json", "rom-cfg-proven-roots-v12.json")
            ):
                with self.subTest(file=name):
                    target = temporary / str(index)
                    shutil.copytree(ARTIFACT, target)
                    path = target / name
                    contents = path.read_bytes()
                    path.write_bytes(bytes([contents[0] ^ 1]) + contents[1:])
                    with self.assertRaisesRegex(
                        ValueError, "identity|canonical|artifact|manifest|payload"
                    ):
                        bundle.verify_bundle(ROOT, target)
            foreign = temporary / "foreign"
            shutil.copytree(ARTIFACT, foreign)
            (foreign / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "file set"):
                bundle.verify_bundle(ROOT, foreign)

    def test_legacy_verifier_identity_is_checked_before_dynamic_load(self):
        bundle = _product()
        with mock.patch.object(bundle, "LEGACY_VERIFIER_SHA256", "0" * 64), mock.patch.object(
            bundle,
            "_load_legacy",
            side_effect=AssertionError("untrusted legacy verifier was loaded"),
        ):
            with self.assertRaisesRegex(ValueError, "legacy verifier identity"):
                bundle._load_anchored_legacy(ROOT)

    def test_dynamic_loader_executes_the_anchored_bytes_not_the_live_path(self):
        bundle = _product()
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="loader-test-", dir=EXPERIMENT) as raw:
            path = Path(raw) / "legacy.py"
            path.write_text("ANCHOR = 'unverified-path'\n", encoding="utf-8")
            module = bundle._load_legacy(path, b"ANCHOR = 'verified-bytes'\n")
            self.assertEqual("verified-bytes", module.ANCHOR)

    def test_wrapper_avoids_live_coverage_and_cli_is_stable(self):
        _product()
        source = WRAPPER.read_text(encoding="utf-8")
        imports: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_cfg_proven_roots_v12" in name for name in imports))
        self.assertNotIn("sequel/rom-byte-coverage.json", source)
        command = [
            sys.executable,
            "-I",
            "-S",
            "tools/verify_rom_cfg_proven_roots_v12_bundle.py",
            "--root",
            ".",
            "--artifact-dir",
            "artifacts/rom-cfg-proven-roots-v12",
        ]
        first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        second = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

        unsafe = subprocess.run(
            [
                sys.executable,
                "-S",
                "tools/verify_rom_cfg_proven_roots_v12_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v12",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, unsafe.returncode, unsafe.stdout + unsafe.stderr)
        unsafe_report = json.loads(unsafe.stdout)
        self.assertFalse(unsafe_report["verified"])
        self.assertRegex(unsafe_report["errors"][0], "isolated|preloaded")


if __name__ == "__main__":
    unittest.main()
