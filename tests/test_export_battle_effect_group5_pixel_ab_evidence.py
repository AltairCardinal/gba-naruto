from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group5-pixel-ab-v1"
RAW = ARTIFACT / "raw"


class ExportBattleEffectGroup5PixelAbEvidenceTests(unittest.TestCase):
    def test_exports_natural_attack_single_pixel_chain(self):
        from tools.export_battle_effect_group5_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            evidence = export_evidence(ROOT, RAW, output)

            self.assertTrue(evidence["verified"])
            self.assertEqual(
                {
                    "EWRAM": [],
                    "IWRAM": [],
                    "IO": [],
                    "PRAM": [],
                    "VRAM": [0x12600],
                    "OAM": [],
                },
                evidence["runtime"]["memory_differences"],
            )
            self.assertEqual(
                [
                    {
                        "x": 160,
                        "y": 48,
                        "before_rgb": [255, 222, 198],
                        "after_rgb": [189, 123, 115],
                    }
                ],
                evidence["runtime"]["pixels"]["changes"],
            )
            self.assertTrue(evidence["runtime"]["renderer_exact"])
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual("accepted", manifest["artifact_status"])

    def test_rejects_raw_state_tampering(self):
        from tools.export_battle_effect_group5_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "raw"
            shutil.copytree(RAW, copied)
            state = copied / "candidate/frame150.ss9"
            payload = bytearray(state.read_bytes())
            payload[-20] ^= 1
            state.write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "runtime provenance"):
                export_evidence(ROOT, copied, Path(temporary) / "artifact")


if __name__ == "__main__":
    unittest.main()
