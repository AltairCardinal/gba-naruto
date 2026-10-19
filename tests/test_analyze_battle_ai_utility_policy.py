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

    def test_map_distance_is_the_rom_topology_model_not_plain_manhattan(self):
        result = self._manifest()
        self.assertEqual(
            result["target_index"]["distance_model"],
            {
                "function": "0x08083AF4",
                "end": "0x0808400C",
                "sha256": (
                    "2be28ff4cdeaed7cd8e95ccdeaf48ae0204fcd62c0a4605f1e6f9036b6562374"
                ),
                "record_table": "0x0853F888",
                "record_table_sha256": (
                    "30aa5a8171c5091947f01e57eb2fdc041946d4c5b42ed19a741db66197c86621"
                ),
                "map_count": 47,
                "records_per_map": 8,
                "record_size": 16,
                "record_type_counts": {
                    "0": 320,
                    "1": 18,
                    "2": 33,
                    "3": 1,
                    "4": 1,
                    "5": 2,
                    "6": 1,
                },
                "record_kinds": {
                    "0": "finish_with_manhattan_segment",
                    "1": "vertical_barrier_with_passage_breakpoints",
                    "2": "horizontal_barrier_with_passage_breakpoints",
                    "3": "map_5_fixed_transition_adjustment",
                    "4": "map_23_signed_distance_lookup",
                    "5": "map_24_dual_entrance_distance_lookup",
                    "6": "map_17_and_37_fixed_transition_adjustment",
                },
                "map_23_lookup": "0x08541008",
                "map_23_lookup_size": 255,
                "map_24_lookup": "0x08541107",
                "map_24_lookup_size": 221,
                "fallback": "direct Manhattan when the first record is type 0",
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
        self.assertEqual(
            policy["common_weight_fields"],
            [
                {"offset": f"0x{offset * 4:02X}", "value": value}
                for offset, value in enumerate(
                    [
                        1000,
                        3000,
                        6000,
                        2500,
                        7000,
                        500,
                        8000,
                        5000,
                        2000,
                        8000,
                        3000,
                        1700,
                        800,
                        800,
                        1300,
                        1000,
                        800,
                        3600,
                        4200,
                        2000,
                        1000,
                        1000,
                        1000,
                        800,
                        0,
                        6000,
                        900,
                        3000,
                        100,
                        6000,
                        8000,
                        3000,
                        5000,
                        7000,
                    ]
                )
            ],
        )
        self.assertTrue(
            result["configuration"]["config_0_common_weights_all_zero"]
        )
        self.assertEqual(
            result["configuration"]["configs_sharing_standard_common_weights"],
            [1, 2, 3, 4, 5, 6, 7],
        )

    def test_actor_projection_uses_two_mutually_exclusive_components(self):
        result = self._manifest()
        self.assertEqual(
            result["scorer"]["actor_projection_utility"],
            {
                "candidate_pool": "0x020240C0",
                "baseline_pool": "0x0202F564",
                "base_bias": "weight[0x00] + weight[0x0C]",
                "hp_gain": (
                    "weight[0x04] * (candidate_hp - baseline_hp) "
                    "/ candidate_max_hp"
                ),
                "hp_retention": (
                    "weight[0x10] * candidate_hp / baseline_hp"
                ),
                "chakra_gain": (
                    "weight[0x08] * (candidate_chakra - baseline_chakra) "
                    "/ candidate_max_chakra"
                ),
                "chakra_retention": (
                    "weight[0x14] * candidate_chakra / baseline_chakra"
                ),
                "branching": (
                    "choose gain when candidate is strictly greater; "
                    "otherwise choose retention"
                ),
                "component_count_increment": 2,
            },
        )

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

    def test_actor_penalty_includes_conditional_restore_event(self):
        result = self._manifest()
        self.assertEqual(
            result["scorer"]["actor_penalty"],
            {
                "weight_offsets": ["0x84", "0x1C"],
                "application": (
                    "subtract once from the component sum before integer division"
                ),
                "component_count_increment": 0,
                "duplicate_status_events": {
                    "0x12": "actor already has status 0x12",
                    "0x0D": "actor already has status 0x0D",
                },
                "restore_event_0x11": {
                    "actor_fields": {
                        "current_hp": "unit+0x0C u16",
                        "maximum_hp": "unit+0x0E u16",
                        "current_chakra": "unit+0x07 u8",
                        "maximum_chakra": "unit+0x08 u8",
                        "x": "unit+0xC4 u8",
                        "y": "unit+0xC5 u8",
                    },
                    "candidate_field": "0x02002880",
                    "map_width": "u8(0x0201BE2A)",
                    "threat_bit": "0x01",
                    "penalize_when": (
                        "(current_hp > floor(maximum_hp / 2) and "
                        "current_chakra > floor(maximum_chakra / 2)) "
                        "or candidate_field[y * map_width + x] & 1"
                    ),
                },
            },
        )

    def test_effect_seven_gets_only_the_proven_safe_position_bonus(self):
        result = self._manifest()
        self.assertEqual(
            result["scorer"]["effect_7_safe_position_bonus"],
            {
                "constant": 8000,
                "event_selection": "first queued event only",
                "requirements": [
                    "no scenario rule kind 1 through 5 was processed",
                    "selected action index is not 0xFF",
                    "first queued event low 6 bits equal 0x07",
                    "selected position candidate-field threat bit 0 is clear",
                ],
                "position_source": {
                    "event[0x15] == 0": "event[0x02], event[0x03]",
                    "event[0x15] != 0": "actor[0xC4], actor[0xC5]",
                },
                "candidate_field": "0x02002880",
                "map_width": "u8(0x0201BE2A)",
                "threat_bit": "0x01",
                "component_count_increment": 0,
            },
        )

    def test_selected_runtime_descriptor_classifies_action_components(self):
        result = self._manifest()
        self.assertEqual(
            result["scorer"]["selected_action_utility"],
            {
                "descriptor_table": "0x02030D29",
                "descriptor_stride": 16,
                "kind_offset": 0,
                "effect_halfword_offset": 1,
                "kind_1": {
                    "bias_weight_offset": "0x18",
                    "extra_component": "aggregated_damage_utility",
                    "component_count_increment": 2,
                },
                "kind_4": {
                    "bias_weight_offset": "0x20",
                    "component_count_increment": 1,
                },
                "kind_5": {
                    "bias_weight_offset": "0x1C",
                    "effect_low_3_weight_offsets": {
                        "0": "0x84",
                        "1": "0x74",
                        "2": "0x78",
                        "3": "0x7C",
                        "4": "0x80",
                        "5": "0x74",
                        "6": None,
                        "7": None,
                    },
                    "component_count_increment": 2,
                },
                "other_selected_kind": {
                    "bias_weight_offset": None,
                    "component_count_increment": 1,
                },
                "no_selected_action": {
                    "candidate_kind_source": "0x0202D262[candidate_index]",
                    "candidate_kind_2_or_3_weight_offset": "0x24",
                    "other_candidate_kind_weight_offset": "0x28",
                    "component_count_increment": 1,
                },
            },
        )

    def test_resource_commands_are_candidate_kinds_two_and_three(self):
        result = self._manifest()
        self.assertEqual(
            result["candidate_executor"],
            {
                "function": "0x080829CC",
                "end": "0x08083040",
                "sha256": (
                    "eaef7cf8e1e03d7b4bd6679ce20e16a"
                    "93f5794ddfe9b97f9a786dbaa9e6fdb7b"
                ),
                "append_function": "0x08082040",
                "append_function_end": "0x080820A6",
                "append_function_sha256": (
                    "0d081b0ff74444e057215a6cf2d775d25"
                    "fc6bdd9ceabc35900c2f603167c9e7b"
                ),
                "candidate_index": "u8(0x0202D261) - 1",
                "candidate_kind_array": "0x0202D262",
                "kinds": {
                    "1": "move",
                    "2": "replenish_chakra",
                    "3": "rest",
                    "4": "selected_action",
                },
            },
        )

    def test_target_selector_banks_are_single_components_gated_by_effect_low_3(self):
        result = self._manifest()
        self.assertEqual(
            result["scorer"]["target_selector_utility"],
            {
                "effect_low_3_source": (
                    "(selected_runtime_descriptor_halfword_at_plus_1 "
                    "& 0x0700) >> 8"
                ),
                "opposite_affiliation": {
                    "bank": "0x02030E83",
                    "enabled_effect_low_3": [2, 3],
                    "weight_offsets": [
                        "0x2C",
                        "0x30",
                        "0x34",
                        "0x38",
                        "0x3C",
                        "0x40",
                        "0x44",
                    ],
                    "aggregation": (
                        "for each selector add its weight at most once when any "
                        "eligible queued event targets the indexed unit"
                    ),
                    "component_count_increment": 1,
                },
                "same_affiliation": {
                    "bank": "0x02030E7C",
                    "enabled_effect_low_3": [1, 3, 5],
                    "weight_offsets": [
                        "0x48",
                        "0x4C",
                        "0x50",
                        "0x54",
                        "0x58",
                        "0x5C",
                        "0x60",
                    ],
                    "aggregation": (
                        "for each selector add its weight at most once when any "
                        "eligible queued event targets the indexed unit"
                    ),
                    "component_count_increment": 1,
                },
            },
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

    def test_custom_rule_components_join_the_integer_mean(self):
        result = self._manifest()
        self.assertEqual(
            result["scorer"]["scenario_rule_components"],
            {
                "recognized_kinds": [1, 2, 3, 4, 5],
                "kind_1": {
                    "components": [
                        "average opponent-progress utility",
                        "candidate-field safe-position utility",
                    ],
                    "component_count_increment": 2,
                },
                "kind_2": {
                    "component": (
                        "parameter-character progress plus matching "
                        "damage-event bonus"
                    ),
                    "component_count_increment": 1,
                },
                "kind_3": {
                    "component": "matching queued-event action bonus",
                    "component_count_increment": 1,
                },
                "kind_4": {
                    "component": "matching tile-class and side bonus",
                    "component_count_increment": 1,
                },
                "kind_5": {
                    "component": "eligible queued-event family bonus",
                    "component_count_increment": 1,
                },
                "zero_value_rule_component": (
                    "recognized rule kinds still increment the denominator "
                    "when their component value is zero"
                ),
                "combiner": (
                    "add rule component sums and counts before the final "
                    "integer mean"
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
