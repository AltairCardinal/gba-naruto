#!/usr/bin/env python3
"""Contract tests for the immutable v15 promotion-bundle verifier."""

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
EXPERIMENT = ROOT / "build/experiments/active/cfg-proven-roots-v15-implementation-20260830"
WRAPPER = ROOT / "tools/verify_rom_cfg_proven_roots_v15_bundle.py"
CONTRACT = json.loads(
    (ROOT / "build/experiments/active/cfg-proven-roots-v15-preflight-20260830/CONTRACT.json")
    .read_text(encoding="utf-8")
)
_MISSING = object()


def _json_pointer(value: object, pointer: str) -> object:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise AssertionError(f"invalid JSON Pointer: {pointer}")
    current: object = value
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(token, _MISSING)
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            current = current[index] if index < len(current) else _MISSING
        else:
            return _MISSING
    return current


def _products():
    try:
        from tools import export_rom_cfg_proven_roots_v15 as exporter
        from tools import verify_rom_cfg_proven_roots_v15_bundle as bundle
    except (ImportError, ModuleNotFoundError) as error:
        raise AssertionError("v15 bundle product modules are absent") from error
    return exporter, bundle


class CfgProvenRootsV15BundleVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.exporter, cls.bundle = _products()

    def _make_artifact(self, parent: Path) -> Path:
        output = parent / "candidate"
        self.exporter.export_rom_cfg_proven_roots_v15(ROOT, output)
        return output

    def test_current_candidate_bundle_rebuilds_without_live_coverage(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._make_artifact(Path(raw))
            report = self.bundle.verify_bundle(ROOT, artifact)
        self.assertEqual("rom-cfg-proven-roots-v15-bundle-verification-v1", report["schema"])
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertEqual("rom-cfg-proven-roots-v15", report["artifact_schema"])
        self.assertEqual("accepted", report["artifact_status"])
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertTrue(report["legacy_control_flow_rebuilt"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertEqual(450, report["promotion_bytes"])
        self.assertEqual(10, report["promotion_range_count"])
        self.assertEqual(398, report["promotion_code_bytes"])
        self.assertEqual(52, report["promotion_literal_bytes"])
        self.assertEqual(386, report["hole_bytes"])
        self.assertEqual(4, report["target_root_count"])
        self.assertEqual([0x09C0F4], report["rejected_roots"])
        self.assertEqual(5, report["producer_count"])
        assertions = CONTRACT["integration"]["proof"]["bundle_contract_assertions"]
        for pointer, expected in assertions.items():
            with self.subTest(pointer=pointer):
                actual = _json_pointer(report, pointer)
                self.assertIsNot(actual, _MISSING, pointer)
                self.assertEqual(expected, actual, pointer)

    def test_artifact_mutations_and_foreign_files_fail_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bundle-test-", dir=EXPERIMENT) as raw:
            temporary = Path(raw)
            for index, name in enumerate(("manifest.json", "rom-cfg-proven-roots-v15.json")):
                target = temporary / str(index)
                shutil.copytree(self._make_artifact(temporary / f"source-{index}"), target)
                path = target / name
                contents = path.read_bytes()
                path.write_bytes(bytes([contents[0] ^ 1]) + contents[1:])
                with self.subTest(file=name), self.assertRaisesRegex(ValueError, "identity|canonical|artifact|manifest|payload"):
                    self.bundle.verify_bundle(ROOT, target)
            foreign = temporary / "foreign"
            shutil.copytree(self._make_artifact(temporary / "source-foreign"), foreign)
            (foreign / "foreign.txt").write_text("foreign", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "file set"):
                self.bundle.verify_bundle(ROOT, foreign)

    def test_copied_artifact_with_both_receipt_paths_rebound_fails_closed(self) -> None:
        EXPERIMENT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bundle-rebind-test-", dir=EXPERIMENT) as raw:
            parent = Path(raw)
            artifact = self._make_artifact(parent / "source")
            copied = parent / "rebound"
            shutil.copytree(artifact, copied)
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            rebound_path = copied.relative_to(ROOT).as_posix()
            manifest["producer"]["command"][-1] = rebound_path
            manifest["verifier"]["command"][-1] = rebound_path
            manifest_path.write_bytes(
                (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
            )
            with self.assertRaisesRegex(ValueError, "artifact|path|receipt"):
                self.bundle.verify_bundle(ROOT, copied)

    def test_verifier_identity_is_checked_before_dynamic_load(self) -> None:
        bundle = self.bundle
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._make_artifact(Path(raw))
            payload = json.loads((artifact / "rom-cfg-proven-roots-v15.json").read_text(encoding="utf-8"))
            dependencies = payload["implementation"]["runtime_dependency_sha256"]
            with mock.patch.object(bundle, "LEGACY_VERIFIER_SHA256", "0" * 64), mock.patch.object(
                bundle, "_load_legacy", side_effect=AssertionError("untrusted verifier was loaded")
            ):
                with self.assertRaisesRegex(ValueError, "legacy verifier identity"):
                    bundle._load_anchored_legacy(ROOT, dependencies)

    def test_dynamic_loader_executes_anchored_bytes_not_live_path(self) -> None:
        bundle = self.bundle
        with tempfile.TemporaryDirectory(prefix="loader-test-", dir=EXPERIMENT) as raw:
            path = Path(raw) / "legacy.py"
            path.write_text("ANCHOR = 'unverified-path'\n", encoding="utf-8")
            module = bundle._load_legacy(path, b"ANCHOR = 'verified-bytes'\n")
            self.assertEqual("verified-bytes", module.ANCHOR)

    def test_dependencies_are_anchored_before_and_after_dynamic_load(self) -> None:
        bundle = self.bundle
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._make_artifact(Path(raw))
            payload = json.loads((artifact / "rom-cfg-proven-roots-v15.json").read_text(encoding="utf-8"))
            dependencies = payload["implementation"]["runtime_dependency_sha256"]
            order: list[str] = []

            def anchor(root, expected):
                self.assertEqual(ROOT.resolve(), Path(root).resolve())
                self.assertEqual(dependencies, expected)
                order.append("anchor")

            def load(path, source):
                self.assertEqual(bundle.LEGACY_VERIFIER_SHA256, hashlib.sha256(source).hexdigest())
                order.append("load")
                return object()

            with mock.patch.object(bundle, "_anchor_runtime_dependencies", side_effect=anchor), mock.patch.object(bundle, "_load_legacy", side_effect=load):
                bundle._load_anchored_legacy(ROOT, dependencies)
            self.assertEqual(["anchor", "load", "anchor"], order)

    def test_dependency_identity_uses_wrapper_hashlib_and_fails_closed(self) -> None:
        bundle = self.bundle
        with tempfile.TemporaryDirectory(prefix="dependency-anchor-test-", dir=EXPERIMENT) as raw:
            temporary = Path(raw)
            dependency = temporary / "dependency.py"
            trusted = b"VALUE = 'trusted'\n"
            dependency.write_bytes(b"VALUE = 'tampered'\n")
            relative = dependency.relative_to(temporary).as_posix()
            with self.assertRaisesRegex(ValueError, "runtime dependency identity"):
                bundle._anchor_runtime_dependencies(temporary, {relative: hashlib.sha256(trusted).hexdigest()})

    def test_wrapper_avoids_live_coverage_exporter_import_and_cli_is_stable(self) -> None:
        _products()
        source = WRAPPER.read_text(encoding="utf-8")
        imports: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("export_rom_cfg_proven_roots_v15" in name for name in imports))
        self.assertNotIn("sequel/rom-byte-coverage.json", source)
        with tempfile.TemporaryDirectory(dir=EXPERIMENT) as raw:
            artifact = self._make_artifact(Path(raw))
            command = [
                sys.executable, "-I", "-S", "tools/verify_rom_cfg_proven_roots_v15_bundle.py",
                "--root", ".", "--artifact-dir", str(artifact.relative_to(ROOT)),
            ]
            first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            second = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
            unsafe = subprocess.run(
                [sys.executable, "-S", "tools/verify_rom_cfg_proven_roots_v15_bundle.py", "--root", ".", "--artifact-dir", str(artifact.relative_to(ROOT))],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertNotEqual(0, unsafe.returncode, unsafe.stdout + unsafe.stderr)
            unsafe_report = json.loads(unsafe.stdout)
            self.assertFalse(unsafe_report["verified"])
            self.assertRegex(unsafe_report["errors"][0], "isolated|preloaded", unsafe.stdout + unsafe.stderr)


if __name__ == "__main__":
    unittest.main()
