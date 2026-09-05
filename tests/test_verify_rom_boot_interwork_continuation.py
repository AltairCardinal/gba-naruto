from __future__ import annotations

import ast
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RomBootInterworkContinuationVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tools import export_rom_boot_interwork_continuation as exporter
        from tools import verify_rom_boot_interwork_continuation as verifier

        cls.exporter = exporter
        cls.verifier = verifier

    def test_independent_verifier_does_not_import_product_exporter(self) -> None:
        source = (ROOT / "tools/verify_rom_boot_interwork_continuation.py").read_text()
        imports = [
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        self.assertFalse(
            any(
                "export_rom_boot_interwork_continuation" in ast.unparse(node)
                for node in imports
            )
        )

    def test_raw_rebuild_accepts_frozen_payload(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        report = self.verifier.verify_payload(ROOT, payload)

        self.assertTrue(report["verified"])
        self.assertEqual(report["promotion_bytes"], 94)
        self.assertEqual(report["literal_binding_count"], 5)
        self.assertEqual(report["callee_frontier_count"], 0)
        self.assertEqual(report["callee_return_offsets"], [0x03A4, 0x03B8])

    def test_payload_mutation_is_rejected(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        mutated = copy.deepcopy(payload)
        mutated["promotion"]["promotion_bytes"] = 96

        report = self.verifier.verify_payload(ROOT, mutated)
        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])

    def test_official_artifact_identity_is_exposed(self) -> None:
        payload = self.exporter.build_payload(ROOT)
        official = payload["official_boot_interwork_artifact"]

        self.assertEqual(
            official["manifest_sha256"],
            "f2673837955194f35daab4f9fb7c0b2fe2dd5967231fcd6d982d0cacb9f749be",
        )
        self.assertEqual(
            official["payload_sha256"],
            "2f78132647235ca1c9fd155b950ff4128e4b01ca10d0fa0ae0fcfa4fdd37e30d",
        )
        self.assertEqual(
            official["verifier_sha256"],
            "66d34dc56f837e09c22fcebdd58e2e67b132c133ea7402e8d50f7e187d54984b",
        )

    def test_accepted_receipt_and_canonical_json_are_failure_closed(self) -> None:
        experiment = ROOT / "build/experiments/active/boot-interwork-continuation-luna-20260901"
        with tempfile.TemporaryDirectory(dir=experiment) as generated, tempfile.TemporaryDirectory() as raw:
            source = Path(generated) / "candidate"
            self.exporter.export_artifact(ROOT, source)
            target = Path(raw) / "candidate"
            shutil.copytree(source, target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["producer"]["command"][-1] = "artifacts/wrong"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_artifact(ROOT, target)["verified"])

            shutil.rmtree(target)
            shutil.copytree(source, target)
            payload_path = target / "rom-boot-interwork-continuation.json"
            payload = json.loads(payload_path.read_text())
            payload_path.write_text(json.dumps(payload, separators=(",", ":")))
            manifest = json.loads((target / "manifest.json").read_text())
            encoded = payload_path.read_bytes()
            import hashlib
            manifest["files"][payload_path.name] = {"size": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}
            (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            self.assertFalse(self.verifier.verify_artifact(ROOT, target)["verified"])


if __name__ == "__main__":
    unittest.main()
