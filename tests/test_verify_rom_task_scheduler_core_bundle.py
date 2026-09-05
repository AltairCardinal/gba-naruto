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

from tools import verify_rom_task_scheduler_core as legacy
from tools import verify_rom_task_scheduler_core_bundle as bundle_verifier


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-task-scheduler-core-v1"
PAYLOAD_NAME = "rom-task-scheduler-core.json"
BUNDLE_NAME = "rom-task-scheduler-core.bin"
MANIFEST_NAME = "manifest.json"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class TaskSchedulerCoreBundleVerifierTests(unittest.TestCase):
    def test_legacy_live_coupled_verify_fails_but_wrapper_verifies(self) -> None:
        legacy_report = legacy.verify_artifact(ROOT, ARTIFACT)
        self.assertFalse(legacy_report["verified"])

        with mock.patch.object(
            legacy,
            "_coverage_state",
            side_effect=AssertionError("wrapper must not inspect live coverage"),
        ) as coverage_state, mock.patch.object(
            legacy,
            "_load_coverage",
            side_effect=AssertionError("wrapper must not load live coverage"),
        ) as load_coverage:
            report = bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)

        self.assertTrue(report["verified"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertFalse(coverage_state.called)
        self.assertFalse(load_coverage.called)

    def test_wrapper_restores_legacy_coverage_helpers(self) -> None:
        original_state = legacy._coverage_state
        original_load = legacy._load_coverage
        bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)
        self.assertIs(original_state, legacy._coverage_state)
        self.assertIs(original_load, legacy._load_coverage)

    def test_report_contract_and_accepted_legacy_receipt(self) -> None:
        report = bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)
        manifest = json.loads((ARTIFACT / MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(
            "rom-task-scheduler-core-bundle-verification-v1", report["schema"]
        )
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertEqual("rom-task-scheduler-core-v1", report["artifact_schema"])
        self.assertEqual("accepted", report["artifact_status"])
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertEqual(legacy.ROM_SHA256, report["rom_sha256"])
        self.assertEqual(308, report["promotion_bytes"])
        self.assertEqual(7, report["promotion_claim_count"])
        self.assertEqual(7, report["promotion_range_count"])
        self.assertEqual(6, report["unclassified_historical_bytes"])
        self.assertEqual(manifest["verification"]["report"], report["legacy_report"])
        self.assertEqual(
            _sha((ROOT / "tools/verify_rom_task_scheduler_core.py").read_bytes()),
            report["legacy_verifier_sha256"],
        )
        self.assertEqual(
            _sha((ROOT / "tools/verify_rom_task_scheduler_core_bundle.py").read_bytes()),
            report["bundle_verifier_sha256"],
        )

    def test_rejects_mutation_of_each_frozen_file(self) -> None:
        mutations = {
            MANIFEST_NAME: lambda raw: _canonical(
                {**json.loads(raw), "artifact_status": "candidate"}
            ),
            PAYLOAD_NAME: lambda raw: _canonical(
                {
                    **json.loads(raw),
                    "scope": {
                        **json.loads(raw)["scope"],
                        "natural_runtime_reachable": True,
                    },
                }
            ),
            BUNDLE_NAME: lambda raw: bytes([raw[0] ^ 1]) + raw[1:],
        }
        with tempfile.TemporaryDirectory() as temporary:
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    target = Path(temporary) / name.replace(".", "-")
                    shutil.copytree(ARTIFACT, target)
                    path = target / name
                    path.write_bytes(mutate(path.read_bytes()))
                    with self.assertRaisesRegex(
                        ValueError, "artifact|manifest|payload|binary|receipt|status"
                    ):
                        bundle_verifier.verify_artifact_bundle(ROOT, target)

    def test_rejects_symlink_and_foreign_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            link = Path(temporary) / "artifact-link"
            link.symlink_to(ARTIFACT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink|artifact|directory"):
                bundle_verifier.verify_artifact_bundle(ROOT, link)

            foreign = Path(temporary) / "foreign"
            shutil.copytree(ARTIFACT, foreign)
            (foreign / "unexpected.bin").write_bytes(b"foreign")
            with self.assertRaisesRegex(ValueError, "foreign|artifact"):
                bundle_verifier.verify_artifact_bundle(ROOT, foreign)

    def test_rejects_symlink_member_for_each_frozen_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            for name in (MANIFEST_NAME, PAYLOAD_NAME, BUNDLE_NAME):
                with self.subTest(name=name):
                    target = Path(temporary) / name.replace(".", "-")
                    shutil.copytree(ARTIFACT, target)
                    path = target / name
                    replacement = target / (name + ".target")
                    path.rename(replacement)
                    path.symlink_to(replacement.name)
                    with self.assertRaisesRegex(ValueError, "symlink|foreign|artifact"):
                        bundle_verifier.verify_artifact_bundle(ROOT, target)

    def test_wrapper_has_no_exporter_import(self) -> None:
        source = (ROOT / "tools/verify_rom_task_scheduler_core_bundle.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any(name.endswith("export_rom_task_scheduler_core") for name in imports),
            imports,
        )

    def test_cli_runs_isolated_with_default_artifact_dir(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "tools/verify_rom_task_scheduler_core_bundle.py",
                "--root",
                ".",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["verified"])
        self.assertEqual(
            "rom-task-scheduler-core-bundle-verification-v1", report["schema"]
        )


if __name__ == "__main__":
    unittest.main()
