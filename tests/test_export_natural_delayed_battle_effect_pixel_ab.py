from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group03-natural-pixel-ab-v1"


class ExportNaturalDelayedBattleEffectPixelAbTests(unittest.TestCase):
    def test_promotes_natural_group3_single_pixel_evidence(self):
        from tools import export_natural_delayed_battle_effect_pixel_ab as exporter

        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["schema"], exporter.EVIDENCE_SCHEMA)
        self.assertTrue(evidence["verified"])
        self.assertTrue(evidence["scope"]["natural_gameplay_route"])
        self.assertTrue(evidence["scope"]["production_resource_relocation"])
        self.assertEqual(evidence["scope"]["production_natural_pixel_ab"], "6/18")
        self.assertEqual(evidence["runtime"]["memory_differences"]["VRAM"], [0x124CF])
        self.assertEqual(
            evidence["runtime"]["pixel_changes"],
            [{
                "x": 70,
                "y": 91,
                "before_rgb": [247, 115, 0],
                "after_rgb": [115, 107, 99],
            }],
        )
        self.assertTrue(evidence["runtime"]["full_source_palette_equal"])
        for run in evidence["runs"]:
            self.assertEqual(run["phase_transaction"]["frames"], [67, 67, 68])
            self.assertEqual(run["phase_transaction"]["pending"], [0, 1, 0])
            self.assertTrue(run["phase_transaction"]["ack_hardware_equals_renderer_shadow"])


if __name__ == "__main__":
    unittest.main()
