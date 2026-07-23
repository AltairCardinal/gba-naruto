import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "notes/battle-hit-modifier-observations-20260723.json"


class BattleHitModifierAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_hit_modifiers import build_hit_modifier_manifest

        return build_hit_modifier_manifest(ROOT, ROOT / "rom/base.gba", OBSERVATIONS)

    def test_static_probability_pipeline_is_ordered_and_flag_based(self):
        result = self._manifest()
        self.assertEqual(result["hit_generator"], "0x08076034")
        self.assertEqual(
            result["critical"],
            {
                "passive_target_type": "0x0C",
                "chance": "min(100, passive_value + 10)",
                "rng_percent": "(rng_value * 100) >> 15",
                "success_condition": "rng_percent < chance",
                "flag": 2,
            },
        )
        self.assertEqual(
            result["ignore_defense"],
            {
                "passive_target_type": "0x19",
                "chance": "passive_value",
                "rng_percent": "(rng_value * 100) >> 15",
                "success_condition": "rng_percent < chance",
                "flag_or_mask": 4,
            },
        )
        self.assertEqual(
            result["rng_order"],
            ["base_hit", "critical_if_passive_present", "ignore_defense_if_passive_present"],
        )

    def test_controlled_100_percent_modifiers_select_exact_damage_candidates(self):
        result = self._manifest()
        self.assertEqual(
            result["runtime_samples"],
            [
                {
                    "id": "natural_baseline",
                    "hit_flags": [0, 1, 1],
                    "target_hp": [49, 31],
                    "total_damage": 18,
                    "candidate_per_landed_hit": 9,
                },
                {
                    "id": "critical_100_percent",
                    "hit_flags": [2, 2, 2],
                    "target_hp": [49, 10],
                    "total_damage": 39,
                    "candidate_per_landed_hit": 13,
                },
                {
                    "id": "ignore_defense_100_percent",
                    "hit_flags": [5, 5, 5],
                    "target_hp": [49, 16],
                    "total_damage": 33,
                    "candidate_per_landed_hit": 11,
                },
            ],
        )

    def test_each_controlled_setup_changes_only_one_passive_level_byte(self):
        result = self._manifest()
        self.assertEqual(
            result["controlled_patches"],
            [
                {
                    "id": "critical_100_percent",
                    "address": "0x02024305",
                    "before": 255,
                    "after": 17,
                    "record_id": 9,
                },
                {
                    "id": "ignore_defense_100_percent",
                    "address": "0x02024331",
                    "before": 255,
                    "after": 17,
                    "record_id": 20,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
