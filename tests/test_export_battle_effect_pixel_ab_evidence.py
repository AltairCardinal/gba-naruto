from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-11-cross-shuriken.json"
ARTIFACT = ROOT / "artifacts/battle-effect-group11-pixel-ab-v1"
GROUP14_PROFILE = ROOT / "sequel/content/battle-effect-pixel-ab/group-14-fire-action.json"
GROUP14_ARTIFACT = ROOT / "artifacts/battle-effect-group14-pixel-ab-v1"


class ExportBattleEffectPixelAbEvidenceTests(unittest.TestCase):
    def test_active_action_uses_distinct_natural_route_scope(self):
        from tools import export_battle_effect_pixel_ab_evidence as exporter

        self.assertEqual(
            exporter._selector_scope({"kind": "active_action"}),
            {
                "natural_active_action_route": True,
                "production_relocation_route": True,
                "single_group_single_frame_single_pixel": True,
                "all_18_effect_groups_runtime_verified": False,
                "all_group_frames_runtime_verified": False,
                "full_affine_blend_timing_audio_equivalence": False,
                "physical_gba_verified": False,
            },
        )

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

    def test_reexports_group14_active_action_single_pixel_chain(self):
        from tools.export_battle_effect_pixel_ab_evidence import export_evidence

        with tempfile.TemporaryDirectory() as tmp:
            evidence = export_evidence(
                ROOT,
                GROUP14_PROFILE,
                GROUP14_ARTIFACT / "raw",
                Path(tmp) / "artifact",
            )

        self.assertEqual(
            evidence["binding"],
            {
                "active_action_id": 16,
                "encoded_action_id": 16,
                "sequence_id": 16,
                "group_id": 14,
            },
        )
        self.assertEqual(evidence["runtime"]["memory_differences"]["VRAM"], [0x1243A])
        self.assertEqual(
            evidence["runtime"]["pixels"]["changes"],
            [
                {
                    "x": 173,
                    "y": 54,
                    "before_rgb": [255, 165, 49],
                    "after_rgb": [255, 239, 107],
                }
            ],
        )
        self.assertTrue(evidence["scope"]["natural_active_action_route"])

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
