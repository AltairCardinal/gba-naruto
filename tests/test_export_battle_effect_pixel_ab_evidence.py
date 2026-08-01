from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-11-cross-shuriken.json"
ARTIFACT = ROOT / "artifacts/battle-effect-group11-pixel-ab-v1"


class ExportBattleEffectPixelAbEvidenceTests(unittest.TestCase):
    def test_reexports_group11_natural_single_pixel_chain(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "artifact"
            evidence = export_evidence(ROOT, PROFILE, ARTIFACT / "raw", output)

            self.assertTrue(evidence["verified"])
            self.assertEqual(
                evidence["runtime"]["memory_differences"],
                {
                    "EWRAM": [],
                    "IWRAM": [],
                    "IO": [],
                    "PRAM": [],
                    "VRAM": [0x12C16],
                    "OAM": [],
                },
            )
            self.assertEqual(
                evidence["runtime"]["pixels"]["changes"],
                [
                    {
                        "x": 172,
                        "y": 61,
                        "before_rgb": [255, 255, 255],
                        "after_rgb": [255, 214, 181],
                    }
                ],
            )
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["schema"], "git-artifact-promotion-v1")
            self.assertEqual(manifest["artifact_status"], "accepted")
            self.assertEqual(manifest["verifier"]["exit_code"], 0)
            self.assertEqual(
                manifest["verifier"]["result"],
                {"errors": [], "verified": True},
            )

    def test_rejects_resigned_runtime_tool_provenance(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            shutil.copytree(ARTIFACT / "raw", raw)
            for variant in ("baseline", "candidate"):
                for name in ("audit.json", "sentinel.json"):
                    path = raw / variant / name
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload["replay_script_sha256"] = "0" * 64
                    path.write_text(
                        json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
            with self.assertRaisesRegex(ValueError, "runtime provenance"):
                export_evidence(ROOT, PROFILE, raw, Path(tmp) / "output")


if __name__ == "__main__":
    unittest.main()
