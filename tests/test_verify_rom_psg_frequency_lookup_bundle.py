from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from tools import audit_rom_byte_coverage as coverage_auditor
from tools import verify_rom_psg_frequency_lookup as legacy
from tools import verify_rom_psg_frequency_lookup_bundle as bundle_verifier


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/rom-psg-frequency-lookup-v1"
MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "rom-psg-frequency-lookup.json"
BINARY_NAME = "rom-psg-frequency-lookup.bin"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class PsgFrequencyLookupBundleVerifierTests(unittest.TestCase):
    def test_frozen_bundle_verifies_after_later_triplet_coverage_promotion(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "coverage|post|claim|identity"):
            legacy.verify_artifact(ROOT, ARTIFACT)

        with mock.patch.object(
            legacy,
            "analyze_live_coverage",
            side_effect=AssertionError(
                "bundle verification must not inspect live coverage"
            ),
        ), mock.patch.object(
            legacy,
            "_read_live_coverage",
            side_effect=AssertionError("bundle verification must not read live coverage"),
        ):
            report = bundle_verifier.verify_artifact_bundle(ROOT, ARTIFACT)

        manifest = json.loads((ARTIFACT / MANIFEST_NAME).read_bytes())
        self.assertEqual(
            "rom-psg-frequency-lookup-bundle-verification-v1",
            report["schema"],
        )
        self.assertTrue(report["verified"])
        self.assertEqual([], report["errors"])
        self.assertTrue(report["artifact_bundle_verified"])
        self.assertTrue(report["legacy_receipt_verified"])
        self.assertFalse(report["live_coverage_verified"])
        self.assertEqual("rom-psg-frequency-lookup-v1", report["artifact_schema"])
        self.assertEqual("accepted", report["artifact_status"])
        self.assertEqual(226, report["promotion_bytes"])
        self.assertEqual(5, report["promotion_claim_count"])
        self.assertEqual(5, report["promotion_range_count"])
        self.assertEqual(0, report["producer_count"])
        self.assertEqual(77, report["consumer_instruction_count"])
        self.assertEqual(12, report["consumer_block_count"])
        self.assertEqual(0, report["consumer_frontier_count"])
        self.assertEqual(
            manifest["verification"]["report"], report["legacy_report"]
        )
        self.assertEqual(
            _sha((ROOT / "tools/verify_rom_psg_frequency_lookup.py").read_bytes()),
            report["legacy_verifier_sha256"],
        )
        self.assertEqual(
            _sha(
                (
                    ROOT / "tools/verify_rom_psg_frequency_lookup_bundle.py"
                ).read_bytes()
            ),
            report["bundle_verifier_sha256"],
        )

    def test_bundle_verifier_rejects_every_frozen_file_mutation(self) -> None:
        mutations = {
            MANIFEST_NAME: lambda raw: _canonical(
                {**json.loads(raw), "artifact_status": "candidate"}
            ),
            PAYLOAD_NAME: lambda raw: _canonical(
                {
                    **json.loads(raw),
                    "scope": {
                        **json.loads(raw)["scope"],
                        "natural_runtime_reachability_complete": True,
                    },
                }
            ),
            BINARY_NAME: lambda raw: bytes([raw[0] ^ 1]) + raw[1:],
        }
        with tempfile.TemporaryDirectory() as temporary:
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    target = Path(temporary) / name.replace(".", "-")
                    shutil.copytree(ARTIFACT, target)
                    path = target / name
                    path.write_bytes(mutate(path.read_bytes()))
                    with self.assertRaisesRegex(
                        ValueError,
                        "artifact|manifest|payload|binary|receipt|status",
                    ):
                        bundle_verifier.verify_artifact_bundle(ROOT, target)

    def test_bundle_verifier_is_independent_of_exporter_and_rejects_symlinks(
        self,
    ) -> None:
        source = (
            ROOT / "tools/verify_rom_psg_frequency_lookup_bundle.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(
            any(name.endswith("export_rom_psg_frequency_lookup") for name in imports),
            imports,
        )

        with tempfile.TemporaryDirectory() as temporary:
            link = Path(temporary) / "artifact-link"
            link.symlink_to(ARTIFACT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink|artifact|directory"):
                bundle_verifier.verify_artifact_bundle(ROOT, link)

    def test_coverage_helper_uses_bundle_verifier_after_later_promotions(
        self,
    ) -> None:
        rom = (ROOT / "rom/base.gba").read_bytes()
        coverage = json.loads(
            (ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8")
        )
        baseline = [
            claim
            for claim in coverage["claims"]
            if claim.get("promotion_batch") != "rom-psg-frequency-lookup-v1"
        ]
        with mock.patch.object(
            coverage_auditor,
            "verify_rom_psg_frequency_lookup",
            side_effect=AssertionError(
                "coverage helper must not invoke the live-coupled legacy verifier"
            ),
        ):
            claims = coverage_auditor._psg_frequency_lookup_claims(
                ROOT, rom, baseline
            )
        self.assertEqual(5, len(claims))
        self.assertEqual(
            "rom-psg-frequency-lookup-v1",
            {claim["promotion_batch"] for claim in claims}.pop(),
        )


if __name__ == "__main__":
    unittest.main()
