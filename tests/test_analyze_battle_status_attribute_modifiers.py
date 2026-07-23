import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusAttributeModifierAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_attribute_modifiers import (
            build_status_attribute_modifier_manifest,
        )

        return build_status_attribute_modifier_manifest(
            ROOT / "rom/base.gba",
            ROOT / "sequel/content/battle-config/action-identities.json",
        )

    def test_reducer_rebuilds_stats_from_original_identity_then_scans_active_statuses(self):
        result = self._manifest()
        self.assertEqual(result["attribute_reducer"], "0x0806D1EC")
        self.assertEqual(result["active_status_slots"], 16)
        self.assertEqual(result["status_code_range"], ["0x12", "0x25"])
        self.assertEqual(result["status_potency_record_offset"], 6)
        self.assertEqual(result["status_potency_width"], "u16")
        self.assertEqual(result["recompute_base_identity"], "unit_original_character_id_0xBC")
        self.assertEqual(result["recompute_scan_order"], "active_status_slot_order_0_to_15")
        self.assertEqual(result["percentage_base"], "current_value_at_each_status_step")
        self.assertEqual(result["post_pass_hp_rule"], "clamp_current_hp_to_recomputed_max_hp")

    def test_status_codes_map_to_typed_attribute_operations(self):
        result = self._manifest()
        self.assertEqual(
            result["modifier_policies"],
            {
                "0x12": {"attribute": "attack", "operation": "percent_increase", "cap": 99},
                "0x1B": {"attribute": "max_hp", "operation": "percent_increase", "cap": 999},
                "0x1E": {"attribute": "attack", "operation": "percent_increase", "cap": 99},
                "0x1F": {"attribute": "attack", "operation": "percent_decrease", "floor": 0},
                "0x20": {"attribute": "defense", "operation": "percent_increase", "cap": 99},
                "0x21": {"attribute": "defense", "operation": "percent_decrease", "floor": 0},
                "0x22": {"attribute": "agility", "operation": "percent_increase", "cap": 99},
                "0x23": {"attribute": "agility", "operation": "percent_decrease", "floor": 0},
                "0x24": {"attribute": "movement", "operation": "absolute_increase", "cap": 9},
                "0x25": {"attribute": "movement", "operation": "absolute_decrease", "floor": 0},
            },
        )

    def test_producer_templates_cover_active_actions_and_ninja_tools(self):
        result = self._manifest()
        active = {(row["action_id"], row["status_code"]) for row in result["active_action_producers"]}
        self.assertEqual(
            active,
            {
                (14, "0x1E"),
                (25, "0x1E"),
                (29, "0x1E"),
                (31, "0x21"),
                (37, "0x12"),
                (38, "0x12"),
            },
        )
        tools = {(row["tool_id"], row["status_code"]) for row in result["ninja_tool_producers"]}
        self.assertEqual(
            tools,
            {
                *((tool_id, "0x1F") for tool_id in range(55, 58)),
                *((tool_id, "0x21") for tool_id in range(58, 61)),
                *((tool_id, "0x23") for tool_id in range(61, 64)),
                *((tool_id, "0x25") for tool_id in range(64, 67)),
                *((tool_id, "0x1E") for tool_id in range(79, 82)),
                *((tool_id, "0x20") for tool_id in range(82, 85)),
                *((tool_id, "0x22") for tool_id in range(85, 88)),
                *((tool_id, "0x24") for tool_id in range(88, 91)),
                *((tool_id, "0x26") for tool_id in range(91, 94)),
            },
        )

    def test_effect_0x26_builds_four_statuses_and_adjusts_current_hp_once(self):
        result = self._manifest()
        self.assertEqual(result["compound_effect_type"], "0x26")
        self.assertEqual(
            result["compound_status_codes"],
            ["0x1E", "0x20", "0x22", "0x1B"],
        )
        self.assertEqual(result["compound_shared_fields"], ["target", "potency", "duration", "source"])
        self.assertEqual(
            result["compound_hp_apply_rule"],
            "increase_current_hp_by_positive_max_hp_delta_else_clamp_to_new_max",
        )

    def test_side_end_removal_recomputes_all_units_before_side_toggle(self):
        result = self._manifest()
        self.assertEqual(result["side_end_tick_callsite"], "0x0807367C")
        self.assertEqual(result["side_end_removed_event_callsite"], "0x08073680")
        self.assertEqual(result["side_end_recompute_callsite"], "0x08073684")
        self.assertEqual(result["recompute_all_units"], "0x0806D440")
        self.assertEqual(result["positive_duration_policy"], "expire_then_recompute_without_modifier")
        self.assertEqual(result["zero_duration_policy"], "retained_by_generic_tick")
        self.assertEqual(
            result["implementation_requirement"],
            "typed_ordered_attribute_modifiers_not_eager_permanent_stat_mutations",
        )


if __name__ == "__main__":
    unittest.main()
