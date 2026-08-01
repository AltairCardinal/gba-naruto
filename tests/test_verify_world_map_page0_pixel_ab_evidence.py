from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/world-map-page0-pixel-ab-v1"


class VerifyWorldMapPage0PixelAbEvidenceTests(unittest.TestCase):
    def test_verifies_promoted_artifact(self):
        from tools.verify_world_map_page0_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual([], result["errors"])

    def test_rejects_resigned_semantic_and_raw_state_tampering(self):
        from tools.verify_world_map_page0_pixel_ab_evidence import verify_evidence

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            evidence_path = copied / "runtime-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["runtime"]["pixels"]["changes"][0]["after_rgb"] = [0, 0, 0]
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            manifest["payload_sha256"] = digest
            manifest["files"]["runtime-evidence.json"] = digest
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(verify_evidence(ROOT, copied)["verified"])

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            state = copied / "raw/candidate/frame80.ss9"
            payload = bytearray(state.read_bytes())
            payload[-20] ^= 1
            state.write_bytes(payload)
            self.assertFalse(verify_evidence(ROOT, copied)["verified"])


if __name__ == "__main__":
    unittest.main()
