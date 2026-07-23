import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleAiStatusPolicyAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_ai_status_policy import build_ai_status_policy_manifest

        return build_ai_status_policy_manifest(ROOT / "rom/base.gba")

    def test_status_aware_scorer_is_hash_bound(self):
        result = self._manifest()
        self.assertEqual(result["scorer"], "0x08084274")
        self.assertEqual(result["scorer_end"], "0x08085154")
        self.assertEqual(result["status_lookup_count"], 15)

    def test_event_contributions_are_suppressed_by_explicit_target_status_groups(self):
        result = self._manifest()
        self.assertEqual(
            result["target_status_group_policies"],
            [
                {
                    "event_selector": "low_6_in_[0x3F,0x0F,0x0E]_or_raw_bit_0x80",
                    "target_status_any": ["0x3F", "0x3E", "0x3D", "0x0F", "0x11"],
                    "effect": "skip_matching_event_score_contribution",
                },
                {
                    "event_selector": "raw_bit_0x40",
                    "target_status_any": ["0x1F", "0x21", "0x23"],
                    "effect": "skip_matching_event_score_contribution",
                },
            ],
        )

    def test_same_family_target_status_filters_are_not_collapsed_into_one_flag(self):
        result = self._manifest()
        self.assertEqual(
            result["target_same_family_policies"],
            [
                {"event_low_6": ["0x1E", "0x26"], "target_status": "0x1E"},
                {"event_low_6": ["0x20", "0x26"], "target_status": "0x20"},
                {"event_low_6": ["0x22", "0x26"], "target_status": "0x22"},
                {"event_low_6": ["0x24"], "target_status": "0x24"},
                {"event_low_6": ["0x26"], "target_status": "0x1B"},
            ],
        )

    def test_actor_status_pairs_apply_a_score_penalty_without_inventing_names(self):
        result = self._manifest()
        self.assertEqual(
            result["actor_event_status_penalties"],
            [
                {"queued_event_low_6": "0x12", "actor_status": "0x12"},
                {"queued_event_low_6": "0x0D", "actor_status": "0x0D"},
            ],
        )
        self.assertEqual(
            result["actor_penalty_operation"],
            "subtract_weight_fields_0x84_and_0x1c_from_candidate_score",
        )
        self.assertFalse(result["proves_visible_status_names"])


if __name__ == "__main__":
    unittest.main()
