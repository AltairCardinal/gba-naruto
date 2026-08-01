from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "artifacts/menu-portrait-pixel-ab-v1/raw"


class ExportMenuPortraitPixelAbEvidenceTests(unittest.TestCase):
    def test_exports_natural_single_pixel_runtime_chain(self):
        from tools.export_menu_portrait_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            evidence = export_evidence(ROOT, RAW, output)

            self.assertTrue(evidence["verified"])
            self.assertEqual("menu-portrait-pixel-ab-runtime-v1", evidence["schema"])
            self.assertEqual(
                {
                    "EWRAM": [15552],
                    "IWRAM": [32668],
                    "IO": [],
                    "PRAM": [],
                    "VRAM": [70720],
                    "OAM": [],
                },
                evidence["runtime"]["memory_differences"],
            )
            self.assertEqual(
                {
                    "count": 1,
                    "bbox": [56, 48, 56, 48],
                    "baseline_rgb_sha256": "aada62ba20f1629f42db886114b96fd17c05c73cb7ee58f137628913747a22bc",
                    "candidate_rgb_sha256": "c7901c9532dd0c05a77b2110b1a70d9555b2e70225fa82737e47da9feff446f0",
                    "changes": [
                        {
                            "x": 56,
                            "y": 48,
                            "before_rgb": [239, 189, 165],
                            "after_rgb": [222, 222, 82],
                        }
                    ],
                },
                evidence["runtime"]["pixels"],
            )
            self.assertEqual(52, evidence["runtime"]["baseline_vram_byte"])
            self.assertEqual(55, evidence["runtime"]["candidate_vram_byte"])
            self.assertEqual(52, evidence["runtime"]["baseline_ewram_byte"])
            self.assertEqual(55, evidence["runtime"]["candidate_ewram_byte"])
            self.assertTrue(evidence["scope"]["natural_show_portrait_load"])
            self.assertTrue(evidence["scope"]["production_relocation_route"])
            self.assertFalse(evidence["scope"]["all_311_portraits_runtime_verified"])
            self.assertTrue((output / "manifest.json").is_file())
            self.assertTrue((output / "runtime-evidence.json").is_file())
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual("accepted", manifest["artifact_status"])
            self.assertEqual(0, manifest["verifier"]["exit_code"])
            self.assertEqual(
                {
                    path.relative_to(output).as_posix()
                    for path in output.rglob("*")
                    if path.is_file() and path.name != "manifest.json"
                },
                set(manifest["files"]),
            )
            self.assertTrue((output / "raw/build-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
