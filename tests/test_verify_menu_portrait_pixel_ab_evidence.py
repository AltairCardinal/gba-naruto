from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/menu-portrait-pixel-ab-v1"


class VerifyMenuPortraitPixelAbEvidenceTests(unittest.TestCase):
    def test_hashes_every_independent_verifier_dependency(self):
        from tools.verify_menu_portrait_pixel_ab_evidence import IMPLEMENTATION_PATHS

        for path in (
            "tools/verify_menu_portrait_writeback_audit.py",
            "tools/build_mod.py",
            "tools/image_resource_regions.py",
            "tools/patch_safety.py",
            "tools/rom_layout.py",
        ):
            with self.subTest(path=path):
                self.assertIn(path, IMPLEMENTATION_PATHS)

    def test_verifies_committed_artifact(self):
        from tools.verify_menu_portrait_pixel_ab_evidence import verify_evidence

        result = verify_evidence(ROOT, ARTIFACT)
        self.assertTrue(result["verified"], result["errors"])
        self.assertEqual([], result["errors"])

    def test_rejects_resigned_semantic_and_raw_state_tampering(self):
        from tools.verify_menu_portrait_pixel_ab_evidence import verify_evidence

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
            import hashlib

            manifest["files"]["runtime-evidence.json"] = hashlib.sha256(
                evidence_path.read_bytes()
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = verify_evidence(ROOT, copied)
            self.assertFalse(result["verified"])

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, copied)
            state = copied / "raw/candidate/frame80.ss9"
            payload = bytearray(state.read_bytes())
            payload[-20] ^= 1
            state.write_bytes(payload)
            result = verify_evidence(ROOT, copied)
            self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main()
