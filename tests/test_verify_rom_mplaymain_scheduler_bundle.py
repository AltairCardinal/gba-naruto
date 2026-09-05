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

from tools import verify_rom_mplaymain_scheduler as legacy
from tools import verify_rom_mplaymain_scheduler_bundle as bundle_verifier


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-mplaymain-scheduler-v1"
MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "rom-mplaymain-scheduler.json"
BUNDLE_NAME = "rom-mplaymain-scheduler.bin"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class MPlayMainSchedulerBundleVerifierTests(unittest.TestCase):
    def test_live_coverage_helper_is_not_used(self) -> None:
        with mock.patch.object(
            legacy,
            "_coverage",
            side_effect=AssertionError("bundle must not read live coverage"),
        ) as coverage:
            report = bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)

        self.assertTrue(report["verified"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertFalse(coverage.called)

    def test_report_contract_and_accepted_legacy_receipt(self) -> None:
        report = bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)
        manifest = json.loads((ARTIFACT / MANIFEST_NAME).read_text(encoding="utf-8"))

        self.assertEqual(
            "rom-mplaymain-scheduler-bundle-verification-v1", report["schema"]
        )
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertEqual("rom-mplaymain-scheduler-v1", report["artifact_schema"])
        self.assertEqual("accepted", report["artifact_status"])
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertEqual(legacy.ROM_SHA256, report["rom_sha256"])
        self.assertEqual(612, report["promotion_bytes"])
        self.assertEqual(2, report["promotion_claim_count"])
        self.assertEqual(2, report["promotion_range_count"])
        self.assertEqual(2, report["unclassified_historical_bytes"])
        self.assertEqual(289, report["summary"]["instruction_count"])
        self.assertEqual(81, report["summary"]["block_count"])
        self.assertEqual(117, report["summary"]["internal_edge_count"])
        self.assertEqual(12, report["summary"]["external_edge_count"])
        self.assertEqual(
            manifest["verification"],
            {
                "status": "verified",
                "contract_ok": True,
                "schema": legacy.VERIFY_SCHEMA,
                "summary": report["legacy_report"]["summary"],
            },
        )
        self.assertEqual(
            _sha((ROOT / "tools/verify_rom_mplaymain_scheduler.py").read_bytes()),
            report["legacy_verifier_sha256"],
        )
        self.assertEqual(
            _sha(
                (ROOT / "tools/verify_rom_mplaymain_scheduler_bundle.py").read_bytes()
            ),
            report["bundle_verifier_sha256"],
        )

    def test_rejects_payload_bundle_and_manifest_mutations(self) -> None:
        mutations = {
            MANIFEST_NAME: lambda raw: _canonical(
                {**json.loads(raw), "artifact_status": "candidate"}
            ),
            PAYLOAD_NAME: lambda raw: _canonical(
                {
                    **json.loads(raw),
                    "summary": {
                        **json.loads(raw)["summary"],
                        "instruction_count": 290,
                    },
                }
            ),
            BUNDLE_NAME: lambda raw: bytes([raw[0] ^ 1]) + raw[1:],
        }
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as temporary:
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    target = Path(temporary) / name.replace(".", "-")
                    shutil.copytree(ARTIFACT, target)
                    path = target / name
                    path.write_bytes(mutate(path.read_bytes()))
                    with self.assertRaisesRegex(
                        ValueError,
                        "artifact|manifest|payload|binary|receipt|status|summary",
                    ):
                        bundle_verifier.verify_artifact_bundle(ROOT, target)

    def test_rejects_foreign_file_and_nonaccepted_artifact(self) -> None:
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as temporary:
            foreign = Path(temporary) / "foreign"
            shutil.copytree(ARTIFACT, foreign)
            (foreign / "unexpected.bin").write_bytes(b"foreign")
            with self.assertRaisesRegex(ValueError, "foreign|artifact|file"):
                bundle_verifier.verify_artifact_bundle(ROOT, foreign)

            candidate = Path(temporary) / "candidate"
            shutil.copytree(ARTIFACT, candidate)
            manifest_path = candidate / MANIFEST_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifact_status"] = "candidate"
            manifest_path.write_bytes(_canonical(manifest))
            with self.assertRaisesRegex(
                ValueError, "accepted|candidate|status|receipt"
            ):
                bundle_verifier.verify_artifact_bundle(ROOT, candidate)

    def test_rejects_legacy_verifier_hash_drift(self) -> None:
        required = (
            Path("rom/base.gba"),
            Path("tools/verify_rom_mplaymain_scheduler.py"),
            Path("tools/verify_rom_mplaymain_scheduler_bundle.py"),
            Path("tools/export_rom_mplaymain_scheduler.py"),
            Path("tests/test_export_rom_mplaymain_scheduler.py"),
            Path("artifacts/rom-boot-thumb-handoff-cfg-v1/rom-boot-thumb-handoff-cfg.json"),
            Path("artifacts/rom-boot-thumb-handoff-cfg-v1/manifest.json"),
            Path("tools/verify_rom_boot_thumb_handoff_cfg.py"),
        )
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active"
        ) as temporary:
            clone = Path(temporary) / "clone"
            for relative in required:
                destination = clone / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            shutil.copytree(ARTIFACT, clone / ARTIFACT.relative_to(ROOT))

            verifier = clone / "tools/verify_rom_mplaymain_scheduler.py"
            verifier.write_bytes(verifier.read_bytes() + b"\n# hash drift\n")
            with self.assertRaisesRegex(ValueError, "implementation|verifier|receipt"):
                bundle_verifier.verify_artifact_bundle(
                    clone, clone / ARTIFACT.relative_to(ROOT)
                )

    def test_wrapper_does_not_import_exporter_and_cli_report_is_stable(self) -> None:
        source = (
            ROOT / "tools/verify_rom_mplaymain_scheduler_bundle.py"
        ).read_text(encoding="utf-8")
        imports: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any(name.endswith("export_rom_mplaymain_scheduler") for name in imports),
            imports,
        )

        command = [
            sys.executable,
            "-I",
            "-S",
            "tools/verify_rom_mplaymain_scheduler_bundle.py",
            "--root",
            ".",
        ]
        first = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, check=False
        )
        second = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, check=False
        )
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))


if __name__ == "__main__":
    unittest.main()
