import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusStagePolicyAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_stage_policy import (
            build_status_stage_policy_manifest,
        )

        return build_status_stage_policy_manifest(
            ROOT / "rom/base.gba",
            ROOT / "sequel/content/battle-config/action-identities.json",
        )

    def test_status_0x13_is_the_shared_eight_gates_stage(self):
        result = self._manifest()
        self.assertEqual(result["status_code"], "0x13")
        self.assertEqual(result["domain_identity"], "eight_gates_stage")
        self.assertEqual(result["record_parameter_offset"], 6)
        self.assertEqual(result["eligibility_parameter_width"], "u16")
        self.assertEqual(result["action_jump_table"], "0x0806FF30")
        self.assertEqual(
            [row["action_id"] for row in result["action_policies"]],
            list(range(43, 50)),
        )
        self.assertEqual(
            [row["display_name"] for row in result["action_policies"]],
            [
                "第一　开门　开",
                "第二　休门　开",
                "第三　生门　开",
                "第四　伤门　开",
                "第五　杜门　开",
                "表莲华",
                "里莲华",
            ],
        )

    def test_gate_opening_actions_follow_an_ordered_stage_machine(self):
        result = self._manifest()
        policies = {row["action_id"]: row for row in result["action_policies"]}
        self.assertEqual(policies[43]["allowed_when"], "status_absent")
        self.assertEqual(policies[43]["disabled_reason_codes"], {"present": 9})
        for action_id, required_stage, low_reason, high_reason in (
            (44, 1, 10, 11),
            (45, 2, 12, 13),
            (46, 3, 14, 15),
            (47, 4, 16, 17),
        ):
            self.assertEqual(
                policies[action_id]["allowed_when"],
                f"status_present_and_parameter_eq_{required_stage}",
            )
            self.assertEqual(
                policies[action_id]["disabled_reason_codes"],
                {"missing_or_lower": low_reason, "higher": high_reason},
            )

    def test_lotus_actions_use_the_same_stage_without_duplicate_ui_state(self):
        result = self._manifest()
        policies = {row["action_id"]: row for row in result["action_policies"]}
        self.assertEqual(
            policies[48]["allowed_when"],
            "status_present_and_parameter_le_2",
        )
        self.assertEqual(
            policies[48]["disabled_reason_codes"],
            {"missing": 18, "above_2": 19},
        )
        self.assertEqual(
            policies[49]["allowed_when"],
            "status_present_and_parameter_gt_2",
        )
        self.assertEqual(
            policies[49]["disabled_reason_codes"],
            {"missing_or_at_most_2": 20},
        )
        self.assertEqual(result["defense_effect_type_low_6"], "0x14")
        self.assertEqual(result["defense_lookup_callsite"], "0x0807112A")
        self.assertEqual(result["defense_numeric_writer_callsite"], "0x08071152")
        self.assertEqual(
            result["defense_presentation"],
            "render_status_parameter_as_effect_0x14_numeric_value",
        )
        self.assertEqual(
            result["implementation_requirement"],
            "one_typed_status_instance_drives_eligibility_hit_count_and_presentation",
        )
        self.assertIsNone(result["visible_status_name"])

    def test_gate_actions_produce_and_replace_the_shared_stage_status(self):
        result = self._manifest()
        producers = result["stage_producers"]
        self.assertEqual(
            [row["action_id"] for row in producers],
            [43, 44, 45, 46, 47],
        )
        self.assertEqual([row["effect_type_low_6"] for row in producers], [19] * 5)
        self.assertEqual([row["stage_value"] for row in producers], [1, 2, 3, 4, 5])
        self.assertEqual([row["duration_turns"] for row in producers], [0] * 5)
        self.assertEqual(
            [row["raw_resource_cost_value"] for row in producers],
            [10, 20, 30, 40, 50],
        )
        self.assertEqual(result["producer_event_builder"], "0x080754A8")
        self.assertEqual(result["producer_resolver_branch"], "0x08077532")
        self.assertEqual(result["producer_upsert_callsite"], "0x0807758A")
        self.assertEqual(
            result["producer_dataflow"],
            "template_byte_0x04_to_event_amount_to_status_record_u16_0x06",
        )
        self.assertEqual(
            result["stage_update_policy"],
            "ordinary_status_0x13_replaces_previous_stage_record",
        )


if __name__ == "__main__":
    unittest.main()
