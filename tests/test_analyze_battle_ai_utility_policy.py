import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleAiUtilityPolicyAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_ai_utility_policy import (
            build_ai_utility_policy_manifest,
        )

        return build_ai_utility_policy_manifest(ROOT / "rom/base.gba")

    def test_target_index_and_scorer_are_hash_bound(self):
        result = self._manifest()
        self.assertEqual(result["target_index"]["function"], "0x0808400C")
        self.assertEqual(result["target_index"]["end"], "0x08084266")
        self.assertEqual(result["scorer"]["function"], "0x08084274")
        self.assertEqual(result["scorer"]["end"], "0x08085154")
        self.assertEqual(result["configuration"]["table"], "0x0853F348")
        self.assertEqual(result["configuration"]["record_count"], 8)
        self.assertEqual(result["configuration"]["record_size"], 0xA8)

    def test_each_affiliation_gets_seven_strict_minimum_target_selectors(self):
        result = self._manifest()
        self.assertEqual(
            result["target_index"]["selectors"],
            [
                {
                    "index": 0,
                    "metric": "floor(current_hp * 1000 / max_hp)",
                    "comparison": "strictly_lower",
                },
                {"index": 1, "metric": "max_hp", "comparison": "strictly_lower"},
                {"index": 2, "metric": "attack", "comparison": "strictly_lower"},
                {"index": 3, "metric": "defense", "comparison": "strictly_lower"},
                {"index": 4, "metric": "agility", "comparison": "strictly_lower"},
                {"index": 5, "metric": "movement", "comparison": "strictly_lower"},
                {
                    "index": 6,
                    "metric": "map_distance(actor, candidate)",
                    "comparison": "strictly_lower",
                },
            ],
        )
        self.assertEqual(result["target_index"]["scan_order"], "unit_slots_1_through_12")
        self.assertEqual(result["target_index"]["tie_break"], "first_scanned_unit")
        self.assertEqual(
            result["target_index"]["banks"],
            {
                "same_affiliation": "0x02030E7C",
                "opposite_affiliation": "0x02030E83",
            },
        )

    def test_standard_policy_uses_separate_hostile_and_friendly_target_weights(self):
        result = self._manifest()
        policy = result["configuration"]["standard_policy"]
        self.assertEqual(
            policy["hostile_target_selector_weights"],
            [1700, 800, 800, 1300, 1000, 800, 3600],
        )
        self.assertEqual(
            policy["friendly_target_selector_weights"],
            [4200, 2000, 1000, 1000, 1000, 800, 0],
        )
        self.assertEqual(policy["damage_weight"], 6000)
        self.assertEqual(policy["success_rate_weight"], 900)
        self.assertEqual(policy["target_coverage_weight"], 3000)
        self.assertEqual(policy["range_usage_weight"], 100)

    def test_damage_events_are_aggregated_before_scoring(self):
        result = self._manifest()
        self.assertEqual(
            result["scorer"]["damage_utility"],
            {
                "event_low_6": ["0x01", "0x14", "0x15"],
                "per_event_amount": "signed_u16(event+0x18) * event[0x12]",
                "aggregation": "sum_by_target_then_select_largest_total",
                "damage_fraction": "min(total_damage, target_current_hp) / target_current_hp",
                "success_component": "max(event[0x10]) / 100",
                "coverage_component": "distinct_targets / active_opposite_affiliation_units",
                "range_component": "max_map_distance / actor_max_action_range",
            },
        )
        self.assertEqual(result["scorer"]["component_combiner"], "integer_mean")
        self.assertEqual(
            result["scorer"]["final_random_term"], "(rng_value * 10) >> 15"
        )

    def test_custom_rules_are_typed_data_not_scripted_turns(self):
        result = self._manifest()
        self.assertEqual(
            result["configuration"]["custom_rule_layout"],
            {
                "slot_count": 4,
                "first_offset": "0x88",
                "stride": 8,
                "kind_offset": 0,
                "parameter_offset": 1,
                "weight_offset": 4,
            },
        )
        self.assertEqual(
            result["configuration"]["active_custom_rules"],
            [
                {
                    "config_id": 2,
                    "slot": 0,
                    "kind": 1,
                    "parameter": 0,
                    "weight": 10000,
                },
                {
                    "config_id": 3,
                    "slot": 0,
                    "kind": 2,
                    "parameter": 0x1F,
                    "weight": 10000,
                },
                {
                    "config_id": 3,
                    "slot": 1,
                    "kind": 3,
                    "parameter": 0x4A,
                    "weight": 10000,
                },
                {
                    "config_id": 3,
                    "slot": 2,
                    "kind": 3,
                    "parameter": 0x4B,
                    "weight": 10000,
                },
                {
                    "config_id": 4,
                    "slot": 0,
                    "kind": 2,
                    "parameter": 0x1E,
                    "weight": 10000,
                },
                {
                    "config_id": 5,
                    "slot": 0,
                    "kind": 5,
                    "parameter": 0,
                    "weight": 10000,
                },
                {
                    "config_id": 6,
                    "slot": 0,
                    "kind": 5,
                    "parameter": 0,
                    "weight": 10000,
                },
                {
                    "config_id": 7,
                    "slot": 0,
                    "kind": 4,
                    "parameter": 0,
                    "weight": 10000,
                },
            ],
        )
        self.assertEqual(
            [row["kind"] for row in result["configuration"]["custom_rule_semantics"]],
            [1, 2, 3, 4, 5],
        )


if __name__ == "__main__":
    unittest.main()
