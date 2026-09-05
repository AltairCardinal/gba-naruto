from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-presentation-glyphs-v1"


class BattlePresentationRomRangeVerifierTests(unittest.TestCase):
    def test_current_artifact_binds_all_promoted_rom_ranges(self):
        from tools.verify_battle_presentation_rom_ranges import verify_artifact

        report = verify_artifact(ROOT, ARTIFACT)

        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(79, report["message_count"])
        self.assertEqual(1_148, report["message_bytes"])
        self.assertEqual(1_794, report["table_bytes"])
        self.assertEqual(32, report["palette_bytes"])

    def test_rejects_message_tamper_even_when_manifest_fields_are_rehashed(self):
        from tools.verify_battle_presentation_rom_ranges import verify_artifact

        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            shutil.copytree(ARTIFACT, artifact)
            manifest_path = artifact / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            message = manifest["messages"][0]
            message_path = artifact / message["raw_file"]
            raw = bytearray(message_path.read_bytes())
            raw[0] ^= 1
            message_path.write_bytes(raw)
            message["raw_hex"] = raw.hex()
            message["raw_sha256"] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            report = verify_artifact(ROOT, artifact)

        self.assertFalse(report["verified"])
        self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
