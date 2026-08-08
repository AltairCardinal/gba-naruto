from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import tarfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/cutscene-obj-id1-primary-ptr-ab-v1"


class CutsceneObjPrimaryPtrAbArtifactTests(unittest.TestCase):
    def test_promoted_artifact_verifies(self):
        from tools.verify_cutscene_obj_primary_ptr_ab import verify_artifact

        result = verify_artifact(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])

    def test_rejects_resigned_pixel_count_tampering(self):
        from tools.verify_cutscene_obj_primary_ptr_ab import verify_artifact

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["pixels"]["changed_pixel_count"] = 1
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

    def test_raw_archive_reexports_the_artifact_byte_for_byte(self):
        from tools.export_cutscene_obj_primary_ptr_ab import export_artifact

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


if __name__ == "__main__":
    unittest.main()
