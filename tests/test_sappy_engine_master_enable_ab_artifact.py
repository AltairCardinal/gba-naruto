from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/sappy-engine-master-enable-ab-v1"


class SappyEngineMasterEnableAbArtifactTests(unittest.TestCase):
    def test_promoted_artifact_verifies(self):
        from tools.verify_sappy_engine_master_enable_ab import verify_artifact

        result = verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_raw_archive_reexports_byte_for_byte(self):
        from tools.export_sappy_engine_master_enable_ab import export_artifact

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            with tarfile.open(ARTIFACT / "raw.tar", "r") as archive:
                archive.extractall(source, filter="data")
            output = Path(temporary) / "artifact"
            export_artifact(ROOT, source, output)
            for name in (
                "baseline.png",
                "candidate.png",
                "evidence.json",
                "manifest.json",
                "raw.tar",
            ):
                self.assertEqual(
                    hashlib.sha256((ARTIFACT / name).read_bytes()).hexdigest(),
                    hashlib.sha256((output / name).read_bytes()).hexdigest(),
                    name,
                )

    def test_rejects_resigned_hardware_gate_tampering(self):
        from tools.verify_sappy_engine_master_enable_ab import verify_artifact

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime_effect"]["candidate_exit_soundcnt_x"] = "0x0080"
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_artifact(ROOT, copied)["verified"])

    def test_default_verification_requires_the_bound_mgba_binary(self):
        from tools import verify_sappy_engine_master_enable_ab as verifier

        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing-mgba"
            with mock.patch.object(verifier, "BINARY_PATH", missing):
                self.assertFalse(
                    verifier.verify_artifact(ROOT, ARTIFACT)["verified"]
                )


if __name__ == "__main__":
    unittest.main()
