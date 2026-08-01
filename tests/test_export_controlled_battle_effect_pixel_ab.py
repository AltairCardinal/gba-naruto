from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group18-controlled-pixel-ab-v1"


class ExportControlledBattleEffectPixelAbTests(unittest.TestCase):
    def test_promoted_evidence_keeps_controlled_and_natural_scopes_distinct(self):
        from tools import export_controlled_battle_effect_pixel_ab as exporter

        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["schema"], exporter.EVIDENCE_SCHEMA)
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["scope"]["execution_mode"], "controlled-direct-spawn")
        self.assertFalse(evidence["scope"]["natural_gameplay_route"])
        self.assertEqual(evidence["scope"]["production_natural_pixel_ab"], "5/18")
        self.assertFalse(evidence["scope"]["mgba_capture_pixel_ab"])
        self.assertEqual(
            evidence["runtime"]["pixel_render_source"],
            "offline-mode0-from-ack-savestate",
        )
        self.assertEqual(
            evidence["runtime"]["mgba_capture_pngs"],
            {
                "baseline_sha256": "a9938b03f35e3fcc9150c6d5864d462bad542b42f9f60bdee3f89595087df431",
                "candidate_sha256": "a9938b03f35e3fcc9150c6d5864d462bad542b42f9f60bdee3f89595087df431",
                "byte_equal": True,
                "used_for_pixel_ab": False,
            },
        )
        for run in evidence["runs"]:
            self.assertEqual(
                run["phase_transaction"]["addresses"],
                ["0x08063328", "0x08061126", "0x080612AA"],
            )
            self.assertEqual(run["phase_transaction"]["pending"], [0, 1, 0])
            self.assertTrue(
                run["phase_transaction"]["renderer_shadow_differs_from_old_hardware"]
            )
            self.assertTrue(
                run["phase_transaction"]["submit_hardware_unchanged"]
            )
            self.assertTrue(
                run["phase_transaction"]["ack_hardware_equals_renderer_shadow"]
            )

        manifest = json.loads(
            (ARTIFACT / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            "tools/verify_battle_effect_direct_spawn_runtime.py",
            manifest["repository_files"],
        )
        self.assertIn(
            "tools/verify_menu_portrait_writeback_audit.py",
            manifest["repository_files"],
        )
        self.assertEqual(
            manifest["verifier"],
            {
                "command": [
                    "python3",
                    "tools/verify_controlled_battle_effect_pixel_ab.py",
                    "--root",
                    ".",
                    "--artifact",
                    "artifacts/battle-effect-group18-controlled-pixel-ab-v1",
                ],
                "exit_code": 0,
            },
        )
        self.assertEqual(
            evidence["runtime"]["memory_differences"],
            {
                "EWRAM": [],
                "IWRAM": [],
                "IO": [],
                "PRAM": [],
                "VRAM": [0x160CA],
                "OAM": [],
            },
        )
        self.assertEqual(
            evidence["runtime"]["pixel_changes"],
            [
                {
                    "x": 124,
                    "y": 43,
                    "before_rgb": [181, 181, 181],
                    "after_rgb": [231, 231, 231],
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
