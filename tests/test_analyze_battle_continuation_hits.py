import unittest
from pathlib import Path

from tools.analyze_battle_continuation_hits import (
    build_battle_continuation_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class BattleContinuationHitAnalysisTest(unittest.TestCase):
    def test_original_rom_binds_category_roll_before_per_hit_resolution(self):
        result = build_battle_continuation_manifest(
            ROOT,
            ROOT / "rom/base.gba",
            ROOT / "notes/battle-continuation-hit-observations-20260725.json",
        )

        self.assertEqual(
            result["category_bindings"],
            {
                "current_chakra": {
                    "runtime_kind": 1,
                    "passive_target_type": 0x17,
                },
                "current_hp": {
                    "runtime_kind": 2,
                    "passive_target_type": 0x16,
                },
                "ninja_tool": {
                    "runtime_kind": 5,
                    "passive_target_type": 0x18,
                },
            },
        )
        self.assertEqual(
            result["eligible_effect_codes"],
            [0x01, 0x14, 0x15],
        )
        self.assertEqual(
            result["rng_order"],
            [
                "one continuation roll per unique action id when its passive exists",
                "increase every matching queued event base hit count by one on success",
                "ordinary base-hit roll for every generated hit",
                "critical roll for every landed hit when its passive exists",
                "ignore-defense roll for every landed hit when its passive exists",
            ],
        )
        self.assertEqual(
            result["runtime_sample"]["base_hit_count"],
            {"baseline": 1, "controlled_100_percent": 2},
        )
        self.assertEqual(
            result["runtime_sample"]["hit_flags"],
            {"baseline": [1], "controlled_100_percent": [1, 1]},
        )
        self.assertEqual(
            result["controlled_patch"],
            {
                "address": "0x02024325",
                "passive_id": 17,
                "before": 0xFF,
                "after": 19,
                "computed_chance_percent": 100,
            },
        )


if __name__ == "__main__":
    unittest.main()
