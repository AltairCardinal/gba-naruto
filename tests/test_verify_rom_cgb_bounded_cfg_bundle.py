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

from tools import verify_rom_cgb_bounded_cfg_bundle as bundle_verifier


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "artifacts/rom-cgb-helper-bounded-cfg-v1"
CGBSOUND = ROOT / "artifacts/rom-cgbsound-bounded-cfg-v1"
WRAPPER = ROOT / "tools/verify_rom_cgb_bounded_cfg_bundle.py"


class CgbBoundedCfgBundleVerifierTests(unittest.TestCase):
    def test_current_accepted_bundles_verify_without_live_coverage(self) -> None:
        report = bundle_verifier.verify_bundles(ROOT, HELPER, CGBSOUND)

        self.assertEqual(
            "rom-cgb-bounded-cfg-bundle-verification-v1", report["schema"]
        )
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertEqual(2, report["artifact_count"])
        self.assertEqual(1_264, report["promotion_bytes"])
        self.assertEqual(28, report["promotion_claim_count"])
        self.assertTrue(report["artifact_bundles_verified"])
        self.assertTrue(report["legacy_receipts_verified"])
        self.assertFalse(report["live_coverage_verified"])

        helper = report["artifacts"]["rom-cgb-helper-bounded-cfg-v1"]
        self.assertEqual(180, helper["promotion_bytes"])
        self.assertEqual(9, helper["promotion_claim_count"])
        self.assertEqual(164, helper["code_bytes"])
        self.assertEqual(16, helper["literal_bytes"])
        self.assertEqual(0, helper["frontier_count"])
        self.assertEqual(
            "8a53b3ee982799583e08ef852fb2cac9771f856e77ed104cc2814cfd1e7ef6d1",
            helper["manifest_sha256"],
        )
        self.assertEqual(
            "d09f828511215b59fe8b60ba4bcf7e63fca48fc36d4c105e75175fa3b11179f3",
            helper["legacy_verifier_sha256"],
        )

        cgbsound = report["artifacts"]["rom-cgbsound-bounded-cfg-v1"]
        self.assertEqual(1_084, cgbsound["promotion_bytes"])
        self.assertEqual(19, cgbsound["promotion_claim_count"])
        self.assertEqual(1_008, cgbsound["code_bytes"])
        self.assertEqual(76, cgbsound["literal_bytes"])
        self.assertEqual(0, cgbsound["frontier_count"])
        self.assertEqual(
            "4248c0fed46682d06918ac124d3c861a60c12117023a773190ff831840963b6e",
            cgbsound["manifest_sha256"],
        )
        self.assertEqual(
            "6af3510f319c58cdb9cf70c115f6a1b2b3ffc0b4fb331f247604dbdb8e637961",
            cgbsound["legacy_verifier_sha256"],
        )

    def test_every_frozen_artifact_file_mutation_is_rejected(self) -> None:
        active = ROOT / "build/experiments/active"
        with tempfile.TemporaryDirectory(prefix="cgb-bundle-test-", dir=active) as raw:
            temporary = Path(raw)
            cases = [
                (HELPER, "manifest.json"),
                (HELPER, "rom-cgb-helper-bounded-cfg.json"),
                (HELPER, "rom-cgb-helper-bounded-cfg.bin"),
                (CGBSOUND, "manifest.json"),
                (CGBSOUND, "rom-cgbsound-bounded-cfg.json"),
                (CGBSOUND, "rom-cgbsound-bounded-cfg.bin"),
            ]
            for index, (source, target_name) in enumerate(cases):
                with self.subTest(artifact=source.name, file=target_name):
                    target_root = temporary / f"{index}-{source.name}"
                    shutil.copytree(source, target_root)
                    path = target_root / target_name
                    raw_bytes = path.read_bytes()
                    path.write_bytes(bytes([raw_bytes[0] ^ 1]) + raw_bytes[1:])
                    helper = target_root if source == HELPER else HELPER
                    cgbsound = target_root if source == CGBSOUND else CGBSOUND
                    with self.assertRaisesRegex(
                        ValueError,
                        "identity|canonical|artifact|manifest|payload|binary",
                    ):
                        bundle_verifier.verify_bundles(ROOT, helper, cgbsound)

    def test_legacy_hash_is_checked_before_subprocess_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cgb-wrapper-root-") as raw:
            root = Path(raw).resolve()
            (root / "tools").mkdir()
            (root / "artifacts").mkdir()
            for name in (
                "verify_rom_cgb_helper_bounded_cfg.py",
                "verify_rom_cgbsound_bounded_cfg.py",
                WRAPPER.name,
            ):
                shutil.copy2(ROOT / "tools" / name, root / "tools" / name)
            helper = root / "artifacts" / HELPER.name
            cgbsound = root / "artifacts" / CGBSOUND.name
            shutil.copytree(HELPER, helper)
            shutil.copytree(CGBSOUND, cgbsound)
            legacy = root / "tools/verify_rom_cgb_helper_bounded_cfg.py"
            legacy.write_bytes(legacy.read_bytes() + b"\n# mutation\n")

            with mock.patch.object(
                bundle_verifier.subprocess,
                "run",
                side_effect=AssertionError("mutated legacy verifier was executed"),
            ):
                with self.assertRaisesRegex(ValueError, "legacy verifier identity"):
                    bundle_verifier.verify_bundles(root, helper, cgbsound)

    def test_wrapper_has_no_exporter_import_and_cli_is_stable(self) -> None:
        imports: list[str] = []
        source = WRAPPER.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any("export_rom_cgb" in name for name in imports), imports
        )
        self.assertNotIn("rom-byte-coverage.json", source)

        command = [
            sys.executable,
            "-I",
            "-S",
            "tools/verify_rom_cgb_bounded_cfg_bundle.py",
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
