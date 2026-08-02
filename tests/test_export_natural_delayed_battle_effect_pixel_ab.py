from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/battle-effect-group03-natural-pixel-ab-v1"


class ExportNaturalDelayedBattleEffectPixelAbTests(unittest.TestCase):
    def test_derives_group18_runtime_contract_from_profile_and_phase(self):
        from tools import export_natural_delayed_battle_effect_pixel_ab as exporter

        profile = json.loads(
            (
                ROOT
                / "sequel/content/battle-effect-natural-pixel-ab/"
                "group-18-tool67-zero-event-expiry.json"
            ).read_text(encoding="utf-8")
        )
        phase = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-frame-phase-group18-natural-sequence-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        contract = exporter.runtime_contract(profile, phase)
        self.assertEqual(contract["group_id"], 18)
        self.assertEqual(contract["sequence_id"], 7)
        self.assertEqual(contract["definition"], 0x0834819C)
        self.assertEqual(contract["animation"], 0x083481DC)
        self.assertEqual(contract["task_slot"], 114)
        self.assertEqual(contract["tile_base"], 768)
        self.assertEqual(contract["palette_bank"], 12)
        self.assertEqual(contract["graphics_address"], 0x06016000)
        self.assertEqual(contract["palette_address"], 0x05000380)
        self.assertEqual(contract["oam_index"], 6)
        self.assertEqual(contract["vram_difference_offset"], 0x160CA)
        self.assertTrue(contract["renderer_shadow_change"])
        self.assertEqual(contract["submission_counts"], [0, 0, 1])

    def test_derives_group18_explicit_input_contract(self):
        from tools import export_natural_delayed_battle_effect_pixel_ab as exporter

        profile = json.loads(
            (
                ROOT
                / "sequel/content/battle-effect-natural-pixel-ab/"
                "group-18-tool67-zero-event-expiry.json"
            ).read_text(encoding="utf-8")
        )
        phase = json.loads(
            (
                ROOT
                / "artifacts/battle-effect-frame-phase-group18-natural-sequence-v1/manifest.json"
            ).read_text(encoding="utf-8")
        )
        contract = exporter.input_contract(profile, phase)
        self.assertEqual(contract["mode"], "explicit-input-sequence")
        self.assertEqual(len(contract["events"]), 17)
        self.assertEqual(contract["events"][0]["down_frame"], 18)
        self.assertEqual(contract["events"][-1]["up_frame"], 3442)
        self.assertEqual(contract["capture_frame"], 4520)
        self.assertEqual(contract["timeout_frames"], 5000)

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
