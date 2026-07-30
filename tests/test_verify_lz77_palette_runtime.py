import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.verify_lz77_palette_runtime import verify


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/lz77-palette-runtime-v1"


class VerifyLz77PaletteRuntimeTests(unittest.TestCase):
    def test_tracked_artifact_verifies(self):
        report = verify(ROOT, ARTIFACT)
        self.assertTrue(report["verified"])
        self.assertEqual(report["entry_count"], 2)
        self.assertEqual(report["palette_bindings_promoted"], 0)

    def test_hash_inventory_rejects_tampered_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory)
            (artifact / "evidence.json").write_bytes(
                (ARTIFACT / "evidence.json").read_bytes() + b" "
            )
            manifest = json.loads((ARTIFACT / "manifest.json").read_text())
            manifest["files"] = {
                "evidence.json": manifest["files"]["evidence.json"]
            }
            (artifact / "manifest.json").write_text(json.dumps(manifest))
            report = verify(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertTrue(any("hash" in error for error in report["errors"]))

    def test_semantic_provenance_rejects_resigned_mismatched_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / ARTIFACT.name
            shutil.copytree(ARTIFACT, artifact)

            evidence_path = artifact / "evidence.json"
            evidence = json.loads(evidence_path.read_text())
            entry = evidence["entries"][0]
            audit_path = artifact / entry["audit"]
            audit = json.loads(audit_path.read_text())
            audit["route"] = "profile-browser-init"
            audit_path.write_text(json.dumps(audit, indent=2) + "\n")
            entry["audit_sha256"] = hashlib.sha256(audit_path.read_bytes()).hexdigest()
            evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")

            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["files"][entry["audit"]] = entry["audit_sha256"]
            evidence_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            manifest["files"]["evidence.json"] = evidence_hash
            manifest["payload_sha256"] = evidence_hash
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

            report = verify(ROOT, artifact)
            self.assertFalse(report["verified"])
            self.assertIn(
                "0x0812D2F0: audit route mismatch",
                report["errors"],
            )


if __name__ == "__main__":
    unittest.main()
