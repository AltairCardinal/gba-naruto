import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleConditionInterpreterAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_condition_interpreter import build_condition_manifest

        return build_condition_manifest(ROOT / "rom/base.gba")

    def test_fixed_record_layout_and_dispatch_are_closed(self):
        result = self._manifest()
        self.assertEqual(result["interpreter"], "0x080777FC")
        self.assertEqual(result["record_base"], "0x08594758")
        self.assertEqual(result["battle_count"], 47)
        self.assertEqual(result["record_end"], "0x08596CCC")
        self.assertEqual(result["battle_stride"], 0xCC)
        self.assertEqual(result["variant_count"], 3)
        self.assertEqual(result["variant_stride"], 0x44)
        self.assertEqual(result["header_size"], 4)
        self.assertEqual(result["predicates_per_group"], 4)
        self.assertEqual(result["predicate_stride"], 8)
        self.assertEqual(result["dispatch_types"], list(range(1, 10)))
        self.assertEqual(result["observed_record_types"], [1, 2, 3, 6, 7, 8, 9])

    def test_record_bank_includes_late_story_battles(self):
        result = self._manifest()
        self.assertEqual(
            result["samples"]["battle_44_variant_0"]["win"][0],
            {"type": 6, "arg0": 0, "arg1": 0, "script": "0x080098B6"},
        )

    def test_battle_9_and_15_records_parse_without_ui_inference(self):
        result = self._manifest()
        self.assertEqual(
            result["samples"]["battle_9_variant_0"]["win"][0],
            {"type": 1, "arg0": 1, "arg1": 0, "script": "0x0800848C"},
        )
        self.assertEqual(
            result["samples"]["battle_9_variant_0"]["lose"][0],
            {"type": 1, "arg0": 0, "arg1": 0, "script": "0x0800849F"},
        )
        self.assertEqual(
            result["samples"]["battle_15_variant_0"]["win"][:2],
            [
                {"type": 1, "arg0": 1, "arg1": 0, "script": "0x0800873A"},
                {"type": 2, "arg0": 0, "arg1": 30, "script": "0x0800873A"},
            ],
        )
        self.assertEqual(
            result["samples"]["battle_15_variant_0"]["lose"][:2],
            [
                {"type": 1, "arg0": 0, "arg1": 0, "script": "0x08008753"},
                {"type": 3, "arg0": 0, "arg1": 30, "script": "0x08008770"},
            ],
        )

    def test_outcome_precedence_preserves_ordered_slot_semantics(self):
        result = self._manifest()
        self.assertEqual(
            result["outcome_precedence"],
            {
                "neither_matches": 0,
                "only_win_matches": 1,
                "only_loss_matches": 2,
                "lower_first_match_index_wins": True,
                "same_first_match_index": 5,
            },
        )
        self.assertEqual(result["closed_semantics"]["type_1"], "no_valid_unit_for_affiliation")
        self.assertEqual(result["closed_semantics"]["type_3"], "no_valid_unit_for_character_and_affiliation")

    def test_used_condition_handlers_expose_operational_semantics(self):
        result = self._manifest()
        self.assertEqual(
            result["record_type_usage"],
            {"1": 155, "2": 11, "3": 18, "6": 8, "7": 16, "8": 16, "9": 6},
        )
        self.assertEqual(result["closed_semantics"]["type_2"], "round_limit_reached_at_round_boundary")
        self.assertEqual(
            result["closed_semantics"]["type_6"],
            "indexed_battlefield_object_slot_is_inactive",
        )
        self.assertEqual(
            result["closed_semantics"]["type_7"],
            "round_limit_selected_side_current_hp_sum_greater_than_opponent",
        )
        self.assertEqual(
            result["closed_semantics"]["type_8"],
            "round_limit_selected_side_valid_unit_count_greater_than_opponent",
        )
        self.assertEqual(
            result["closed_semantics"]["type_9"],
            "round_limit_selected_side_resolved_object_counter_greater_than_opponent",
        )
        self.assertEqual(
            result["operational_addresses"],
            {
                "round_limit": "0x0202680A",
                "round_index": "0x0202680C",
                "battlefield_object_table": "0x02026604",
                "battlefield_object_stride": 0x10,
                "battlefield_object_count": 32,
                "resolved_object_side_counter_base": "0x02026BC0",
                "unit_pool": "0x020240C0",
                "unit_stride": 0x1D4,
                "current_hp_offset": 0x0C,
            },
        )
        self.assertEqual(
            result["battlefield_object_lifecycle"],
            {
                "allocate": "0x08081024",
                "free": "0x08081084",
                "type_9_counter_writer": "0x08081984",
                "active_type_offset": 0,
                "x_offset": 1,
                "y_offset": 2,
                "behavior_offset": 6,
                "counter_writer_behavior": 9,
                "counter_increment": 1,
                "counter_side_source": "resolving_unit_affiliation_bit",
            },
        )

    def test_result_five_has_a_distinct_caller_presentation_path(self):
        result = self._manifest()
        self.assertEqual(result["caller"], "0x0807305C")
        self.assertEqual(result["presentation_function"], "0x08072EDC")
        self.assertEqual(result["result_to_presentation_id"], {"1": 1, "2": 2, "5": 3})
        self.assertTrue(result["result_5_ends_battle"])


if __name__ == "__main__":
    unittest.main()
