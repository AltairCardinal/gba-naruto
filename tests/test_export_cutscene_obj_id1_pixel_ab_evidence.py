from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/cutscene-obj-id1-pixel-ab-v1"
RAW = ARTIFACT / "raw"


class ExportCutsceneObjId1PixelAbEvidenceTests(unittest.TestCase):
    def test_exports_natural_victory_single_pixel_chain(self):
        from tools.export_cutscene_obj_id1_pixel_ab_evidence import export_evidence

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
                    "VRAM": [0x16052],
                    "OAM": [],
                },
                evidence["runtime"]["memory_differences"],
            )
            self.assertEqual(
                [
                    {
                        "x": 60,
                        "y": 52,
                        "before_rgb": [255, 255, 255],
                        "after_rgb": [181, 181, 181],
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
        from tools.export_cutscene_obj_id1_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "raw"
            shutil.copytree(RAW, copied)
            state = copied / "candidate/frame512.ss9"
            payload = bytearray(state.read_bytes())
            payload[-20] ^= 1
            state.write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "runtime provenance"):
                export_evidence(ROOT, copied, Path(temporary) / "artifact")


if __name__ == "__main__":
    unittest.main()
