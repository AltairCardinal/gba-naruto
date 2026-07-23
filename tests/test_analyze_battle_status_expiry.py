#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from tools.analyze_battle_status_expiry import build_status_expiry_manifest


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-status-expiry-observations-20260723.json"


class BattleStatusExpiryTests(unittest.TestCase):
    def _manifest(self):
        return build_status_expiry_manifest(ROOT, ROOT / "rom/base.gba", OBSERVATIONS)

    def test_side_end_ticks_every_active_status_before_side_toggle(self):
        result = self._manifest()
        self.assertEqual(result["controller_state"], "0x1100")
        self.assertEqual(result["status_tick"], "0x0806C308")
        self.assertEqual(result["unit_slots"], [1, 12])
        self.assertEqual(result["status_slots_per_unit"], 16)
        self.assertEqual(result["status_stride"], 8)
        self.assertEqual(result["code_offset"], "unit+0xD4")
        self.assertEqual(result["duration_offset"], "unit+0xD6")
        self.assertTrue(result["tick_occurs_before_side_toggle"])

    def test_duration_one_expires_but_duration_two_is_retained(self):
        result = self._manifest()
        self.assertEqual(
            result["runtime_samples"],
            [
                {
                    "initial_duration": 1,
                    "side": [0, 1],
                    "status_code": [1, 0],
                    "duration": [1, 0],
                    "removed_at_zero": True,
                },
                {
                    "initial_duration": 2,
                    "side": [0, 1],
                    "status_code": [1, 1],
                    "duration": [2, 1],
                    "removed_at_zero": False,
                },
            ],
        )

    def test_controlled_patches_only_touch_code_and_duration(self):
        result = self._manifest()
        self.assertEqual(
            result["controlled_patch_offsets"],
            ["unit+0xD4", "unit+0xD6"],
        )


if __name__ == "__main__":
    unittest.main()
