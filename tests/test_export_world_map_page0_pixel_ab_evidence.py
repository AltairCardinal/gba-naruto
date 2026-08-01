from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "artifacts/world-map-page0-pixel-ab-v1/raw"


class ExportWorldMapPage0PixelAbEvidenceTests(unittest.TestCase):
    def test_exports_natural_page0_single_pixel_chain(self):
        from tools.export_world_map_page0_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact"
            evidence = export_evidence(ROOT, RAW, output)

            self.assertEqual("world-map-page0-pixel-ab-runtime-v1", evidence["schema"])
            self.assertTrue(evidence["verified"])
            self.assertEqual(
                {
                    "EWRAM": [],
                    "IWRAM": [],
                    "IO": [],
                    "PRAM": [],
                    "VRAM": [31972],
                    "OAM": [],
                },
                evidence["runtime"]["memory_differences"],
            )
            self.assertEqual(
                [
                    {
                        "x": 116,
                        "y": 76,
                        "before_rgb": [189, 165, 107],
                        "after_rgb": [66, 33, 0],
                    }
                ],
                evidence["runtime"]["pixels"]["changes"],
            )
            self.assertEqual(806, evidence["runtime"]["common_overwrite_count"])
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

    def test_rejects_a_raw_audit_sentinel_mismatch_before_promotion(self):
        from tools.export_world_map_page0_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as temporary:
            copied_raw = Path(temporary) / "raw"
            shutil.copytree(RAW, copied_raw)
            sentinel_path = copied_raw / "candidate/sentinel.json"
            sentinel = json.loads(sentinel_path.read_text(encoding="utf-8"))
            sentinel["run_id"] = "tampered-before-promotion"
            sentinel_path.write_text(
                json.dumps(sentinel, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "audit/sentinel"):
                export_evidence(
                    ROOT,
                    copied_raw,
                    Path(temporary) / "artifact",
                )


if __name__ == "__main__":
    unittest.main()
