from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleEffectObservedFramePhaseExporterTests(unittest.TestCase):
    def test_builds_exact_observed_group_denominators(self):
        exporter = importlib.import_module(
            "tools.export_battle_effect_observed_frame_phases"
        )
        coverage = exporter.build_coverage(ROOT)
        self.assertEqual(coverage["all_group_denominator"], 18)
        self.assertEqual(coverage["observed_group_denominator"], 5)
        self.assertEqual(coverage["phase_verified_group_count"], 10)
        self.assertEqual(
            coverage["phase_verified_group_ids"],
            [1, 2, 3, 4, 5, 11, 14, 16, 17, 18],
        )
        self.assertEqual(coverage["natural_delayed_extension_group_ids"], [3, 18])
        self.assertEqual(coverage["natural_confirmation_extension_group_ids"], [4])
        self.assertEqual(
            coverage["natural_ninja_tool_handler_extension_group_ids"], [16, 17]
        )
        self.assertEqual(
            coverage["production_pixel_ab_group_ids"],
            [1, 2, 3, 4, 5, 11, 13, 14, 15, 16, 17, 18],
        )
        self.assertEqual(coverage["production_pixel_ab_group_count"], 12)


if __name__ == "__main__":
    unittest.main()
