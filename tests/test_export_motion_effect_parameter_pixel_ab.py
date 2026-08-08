import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/motion-effect-parameter-pixel-ab-v1"


class ExportMotionEffectParameterPixelAbTests(unittest.TestCase):
    def test_promotes_the_natural_record_zero_y_offset_result(self):
        from tools.export_motion_effect_parameter_pixel_ab import EVIDENCE_SCHEMA

        evidence = json.loads((ARTIFACT / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["schema"], EVIDENCE_SCHEMA)
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["bank"]["historical_slug"], "palettes")
        self.assertEqual(evidence["bank"]["actual_identity"], "motion/effect parameters")
        self.assertEqual(evidence["edit"]["changed_rom_offsets"], [0x53EE9C])
        self.assertTrue(evidence["build"]["probe_free"])
        self.assertTrue(evidence["scope"]["natural_gameplay_route"])
        self.assertFalse(evidence["scope"]["all_records_runtime_verified"])
        self.assertFalse(evidence["scope"]["all_consumer_routes_runtime_verified"])
        self.assertEqual(evidence["runtime"]["task_slot"], 126)
        self.assertEqual(evidence["runtime"]["task_field_offset"], 6)
        self.assertEqual(evidence["runtime"]["task_y_values"], [64, 96])
        self.assertEqual(evidence["runtime"]["oam_index"], 0)
        self.assertEqual(evidence["runtime"]["oam_y_values"], [80, 112])
        self.assertEqual(evidence["runtime"]["pixel_change_count"], 286)
        self.assertEqual(evidence["runtime"]["pixel_change_bbox"], [54, 88, 72, 107])
        self.assertEqual(
            evidence["runtime"]["memory_differences"]["ack-post"],
            {
                "task-pool.bin": [0x1D8E],
                "shadow-oam.bin": [0],
                "hardware-oam.bin": [0],
            },
        )
        self.assertEqual(evidence["run_budget"], {"planned": 2, "actual": 2, "blind_retries": 0})
        self.assertTrue(all(run["pgid_clean"] for run in evidence["runs"]))


if __name__ == "__main__":
    unittest.main()
