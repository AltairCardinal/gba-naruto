import json
import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_rom_expansion_profile import verify_profile


class RomExpansionProfileVerifierTests(unittest.TestCase):
    def test_verifies_static_layout_probe_rebuild_and_runtime_savestate(self):
        result = verify_profile(
            ROOT,
            ROOT / "artifacts/rom-expansion-profile-v1/manifest.json",
        )
        self.assertEqual([], result["errors"])
        self.assertEqual(0x4258474D, result["savestate_scratch"])
        self.assertEqual(0x1000000, result["target_rom_size"])
        self.assertEqual("0x085CCC80", result["snapshot_restore_pc"])
        self.assertEqual(0x4258474D, result["snapshot_restore_scratch"])
        self.assertEqual(
            "88709b8a66a3cb916f1364e975ae7c58a60d779c51fc80784db5b3a24db721d5",
            result["rebuilt_probe_sha256"],
        )

    def test_rejects_rehashed_semantic_claim_tampering(self):
        source = ROOT / "artifacts/rom-expansion-profile-v1"
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact = Path(temp_dir) / "rom-expansion-profile-v1"
            shutil.copytree(source, artifact)
            profile_path = artifact / "profile.json"
            profile = json.loads(
                profile_path.read_text(
                    encoding="utf-8"
                )
            )
            profile["runtime_probe"]["first_frame_scratch"] = "0x00000000"
            profile_path.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8"
            )
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            profile_digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
            manifest["payload_sha256"] = profile_digest
            manifest["files"]["profile.json"] = profile_digest
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = verify_profile(ROOT, manifest_path)
        self.assertTrue(
            any("first_frame_scratch" in error for error in result["errors"]),
            result,
        )


if __name__ == "__main__":
    unittest.main()
