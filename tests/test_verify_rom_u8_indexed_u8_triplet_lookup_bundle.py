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

from tools import verify_rom_u8_indexed_u8_triplet_lookup as legacy
from tools import verify_rom_u8_indexed_u8_triplet_lookup_bundle as bundle_verifier


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-u8-indexed-u8-triplet-lookup-v1"
MANIFEST_NAME = "manifest.json"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class U8TripletLookupBundleVerifierTests(unittest.TestCase):
    def test_legacy_live_coupled_verify_fails_but_wrapper_verifies(self) -> None:
        self.assertFalse(legacy.verify_artifact(ROOT, ARTIFACT)["verified"])
        with mock.patch.object(
            legacy,
            "_read_live_coverage",
            side_effect=AssertionError("bundle must not read live coverage"),
        ) as read_live, mock.patch.object(
            legacy,
            "analyze_live_coverage",
            side_effect=AssertionError("bundle must not analyze live coverage"),
        ) as analyze_live:
            report = bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)
        self.assertTrue(report["verified"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertFalse(read_live.called)
        self.assertFalse(analyze_live.called)

    def test_report_contract_and_isolated_cli(self) -> None:
        report = bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)
        manifest = json.loads((ARTIFACT / MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(
            "rom-u8-indexed-u8-triplet-lookup-bundle-verification-v1",
            report["schema"],
        )
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertEqual("accepted", report["artifact_status"])
        self.assertEqual(19, report["promotion_bytes"])
        self.assertEqual(2, report["promotion_claim_count"])
        self.assertEqual(2, report["promotion_range_count"])
        self.assertEqual(134, report["consumer_instruction_count"])
        self.assertEqual(28, report["consumer_block_count"])
        self.assertEqual(0, report["consumer_frontier_count"])
        self.assertEqual(5, report["table_record_count"])
        self.assertEqual(manifest["verification"]["report"], report["legacy_report"])
        self.assertEqual(
            _sha((ROOT / "tools/verify_rom_u8_indexed_u8_triplet_lookup.py").read_bytes()),
            report["legacy_verifier_sha256"],
        )
        self.assertEqual(
            _sha(
                (
                    ROOT
                    / "tools/verify_rom_u8_indexed_u8_triplet_lookup_bundle.py"
                ).read_bytes()
            ),
            report["bundle_verifier_sha256"],
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "tools/verify_rom_u8_indexed_u8_triplet_lookup_bundle.py",
                "--root",
                ".",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["verified"])

    def test_rejects_every_frozen_file_mutation(self) -> None:
        mutations = {
            MANIFEST_NAME: lambda raw: _canonical(
                {**json.loads(raw), "artifact_status": "candidate"}
            ),
            legacy.JSON_NAME: lambda raw: _canonical(
                {
                    **json.loads(raw),
                    "scope": {
                        **json.loads(raw)["scope"],
                        "natural_runtime_reachability_complete": True,
                    },
                }
            ),
            legacy.BIN_NAME: lambda raw: bytes([raw[0] ^ 1]) + raw[1:],
        }
        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active/rom-u8-indexed-u8-triplet-lookup"
        ) as temporary:
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    target = Path(temporary) / name.replace(".", "-")
                    shutil.copytree(ARTIFACT, target)
                    path = target / name
                    path.write_bytes(mutate(path.read_bytes()))
                    with self.assertRaisesRegex(
                        ValueError, "artifact|manifest|payload|bundle|status"
                    ):
                        bundle_verifier.verify_artifact_bundle(ROOT, target)

    def test_rejects_symlinks_foreign_files_and_exporter_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            link = Path(temporary) / "artifact-link"
            link.symlink_to(ARTIFACT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink|artifact"):
                bundle_verifier.verify_artifact_bundle(ROOT, link)

        with tempfile.TemporaryDirectory(
            dir=ROOT / "build/experiments/active/rom-u8-indexed-u8-triplet-lookup"
        ) as temporary:
            target = Path(temporary) / "foreign"
            shutil.copytree(ARTIFACT, target)
            (target / "unexpected.bin").write_bytes(b"foreign")
            with self.assertRaisesRegex(ValueError, "denominator|artifact"):
                bundle_verifier.verify_artifact_bundle(ROOT, target)

        source = (
            ROOT / "tools/verify_rom_u8_indexed_u8_triplet_lookup_bundle.py"
        ).read_text(encoding="utf-8")
        imports: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any(
                name.endswith("export_rom_u8_indexed_u8_triplet_lookup")
                for name in imports
            ),
            imports,
        )


if __name__ == "__main__":
    unittest.main()
