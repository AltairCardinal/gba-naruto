#!/usr/bin/env python3
"""Contract tests for the immutable v13 promotion-bundle verifier."""

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


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-cfg-proven-roots-v13"
WRAPPER = ROOT / "tools/verify_rom_cfg_proven_roots_v13_bundle.py"
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v13-bundle-20260829"


def _product():
    try:
        from tools import verify_rom_cfg_proven_roots_v13_bundle as bundle
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v13 immutable bundle verifier is absent") from error
    return bundle


class CfgProvenRootsV13BundleVerifierTests(unittest.TestCase):
    def test_current_accepted_bundle_rebuilds_legacy_contract_without_live_coverage(self):
        bundle = _product()
        report = bundle.verify_bundle(ROOT, ARTIFACT)

        self.assertEqual(
            "rom-cfg-proven-roots-v13-bundle-verification-v1", report["schema"]
        )
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertEqual("rom-cfg-proven-roots-v13", report["artifact_schema"])
        self.assertEqual("accepted", report["artifact_status"])
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertTrue(report["legacy_control_flow_rebuilt"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertEqual(392, report["promotion_bytes"])
        self.assertEqual(6, report["promotion_range_count"])
        self.assertEqual(312, report["promotion_code_bytes"])
        self.assertEqual(80, report["promotion_literal_bytes"])
        self.assertEqual(4, report["hole_bytes"])
        self.assertEqual(237, report["source_decoded_instruction_count"])
        self.assertEqual(40, report["source_decoded_basic_block_count"])
        self.assertEqual(508, report["source_reachable_instruction_bytes"])
        self.assertEqual(0, report["source_frontier_count"])
        self.assertEqual(153, report["target_decoded_instruction_count"])
        self.assertEqual(25, report["target_decoded_basic_block_count"])
        self.assertEqual(312, report["target_reachable_instruction_bytes"])
        self.assertEqual(1, report["target_frontier_count"])
        self.assertEqual(
            [[414_568, "indirect_pc_target"]], report["target_frontiers"]
        )
        self.assertEqual(164, report["target_instruction_internal_edge_count"])
        self.assertEqual(36, report["target_block_internal_edge_count"])
        self.assertEqual(21, report["target_literal_reference_count"])
        self.assertEqual(20, report["target_unique_literal_word_count"])
        self.assertEqual(
            "589dd8e1536b2b6d0cc3997f31c5841204593f64ce491d6c0647ca7230f8e133",
            report["manifest_sha256"],
        )
        self.assertEqual(
            "45b83aeb6e91249ebd5adefdb086c438b14c666e79aab780f7072a929343cb5b",
            report["payload_sha256"],
        )
        self.assertEqual(
            "a687af7750e9a177b47883f1b540d555bd4c666d92865d56e521f85174c869a7",
            report["legacy_verifier_sha256"],
        )
        self.assertEqual(
            "09f8682f0e4bab0db4108820c4034abf45e345e05f9e7bd9c4111cc2054114c0",
            report["promotion_range_vector_sha256"],
        )
        self.assertEqual(
            "d7449f4feb51fa169d011c0692d2009090633aa8cf7968064bd36063be491e40",
            report["promotion_packed_sha256"],
        )

    def test_artifact_mutations_and_foreign_files_fail_closed(self):
        bundle = _product()
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bundle-test-", dir=EXPERIMENT) as raw:
            temporary = Path(raw)
            for index, name in enumerate(
                ("manifest.json", "rom-cfg-proven-roots-v13.json")
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
        payload = json.loads(
            (ARTIFACT / "rom-cfg-proven-roots-v13.json").read_text(
                encoding="utf-8"
            )
        )
        dependency_hashes = payload["implementation"][
            "runtime_dependency_sha256"
        ]
        with mock.patch.object(bundle, "LEGACY_VERIFIER_SHA256", "0" * 64), mock.patch.object(
            bundle,
            "_load_legacy",
            side_effect=AssertionError("untrusted legacy verifier was loaded"),
        ):
            with self.assertRaisesRegex(ValueError, "legacy verifier identity"):
                bundle._load_anchored_legacy(ROOT, dependency_hashes)

    def test_dynamic_loader_executes_the_anchored_bytes_not_the_live_path(self):
        bundle = _product()
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="loader-test-", dir=EXPERIMENT) as raw:
            path = Path(raw) / "legacy.py"
            path.write_text("ANCHOR = 'unverified-path'\n", encoding="utf-8")
            module = bundle._load_legacy(path, b"ANCHOR = 'verified-bytes'\n")
            self.assertEqual("verified-bytes", module.ANCHOR)

    def test_runtime_dependencies_are_anchored_before_legacy_dynamic_load(self):
        bundle = _product()
        payload = json.loads(
            (ARTIFACT / "rom-cfg-proven-roots-v13.json").read_text(
                encoding="utf-8"
            )
        )
        dependency_hashes = payload["implementation"][
            "runtime_dependency_sha256"
        ]
        order: list[str] = []

        def anchor(root, expected):
            self.assertEqual(ROOT.resolve(), Path(root).resolve())
            self.assertEqual(dependency_hashes, expected)
            order.append("anchor")

        def load(path, source):
            self.assertEqual(bundle.LEGACY_VERIFIER_SHA256, hashlib.sha256(source).hexdigest())
            order.append("load")
            return object()

        with mock.patch.object(
            bundle, "_anchor_runtime_dependencies", side_effect=anchor
        ), mock.patch.object(bundle, "_load_legacy", side_effect=load):
            bundle._load_anchored_legacy(ROOT, dependency_hashes)

        self.assertEqual(["anchor", "load", "anchor"], order)

    def test_runtime_dependency_identity_uses_wrapper_hashlib_and_fails_closed(self):
        bundle = _product()
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="dependency-anchor-test-", dir=EXPERIMENT
        ) as raw:
            temporary = Path(raw)
            dependency = temporary / "dependency.py"
            trusted = b"VALUE = 'trusted'\n"
            dependency.write_bytes(b"VALUE = 'tampered'\n")
            relative = dependency.relative_to(temporary).as_posix()
            with self.assertRaisesRegex(ValueError, "runtime dependency identity"):
                bundle._anchor_runtime_dependencies(
                    temporary,
                    {relative: hashlib.sha256(trusted).hexdigest()},
                )

    def test_wrapper_avoids_live_coverage_and_cli_is_stable(self):
        _product()
        source = WRAPPER.read_text(encoding="utf-8")
        imports: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_cfg_proven_roots_v13" in name for name in imports))
        self.assertNotIn("sequel/rom-byte-coverage.json", source)
        command = [
            sys.executable,
            "-I",
            "-S",
            "tools/verify_rom_cfg_proven_roots_v13_bundle.py",
            "--root",
            ".",
            "--artifact-dir",
            "artifacts/rom-cfg-proven-roots-v13",
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
                "tools/verify_rom_cfg_proven_roots_v13_bundle.py",
                "--root",
                ".",
                "--artifact-dir",
                "artifacts/rom-cfg-proven-roots-v13",
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
