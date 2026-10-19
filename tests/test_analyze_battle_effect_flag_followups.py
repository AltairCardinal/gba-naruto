import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleEffectFlagFollowupAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_effect_flag_followups import (
            build_effect_flag_followup_manifest,
        )

        return build_effect_flag_followup_manifest(ROOT / "rom/base.gba")

    def test_flag_followup_handler_and_queue_gate_are_hash_bound(self):
        result = self._manifest()
        self.assertEqual(result["handler"], "0x080768D8")
        self.assertEqual(result["queue_callsite"], "0x0807766C")
        self.assertEqual(
            result["handler_sha256"],
            "eea2a918515d8c367ac0f464c5a33092cd1da83963708282e93dba020bef84b4",
        )
        self.assertEqual(
            result["queue_gate_sha256"],
            "8c0638a3f11746e5ec72fed04f9edfc1635c20ef17e7de5f777b91ee46c92f14",
        )
        self.assertEqual(result["requires_effective_hit"], True)
        self.assertEqual(result["target_policy_gate"], "0x0200")
        self.assertEqual(
            result["applies_after_lethal_resolution"],
            True,
        )
        self.assertEqual(
            result["post_handler_gate"],
            "0x0807764E..0x0807766C",
        )

    def test_flag_0x80_creates_one_turn_status_0x3f(self):
        result = self._manifest()
        self.assertEqual(
            result["followups"]["0x80"],
            {
                "status_codes": ["0x3F"],
                "duration_turns": 1,
                "value_u16": 0,
                "reaction_state": "0x30",
            },
        )
        self.assertEqual(result["active_action_producers"]["0x80"], [8, 10, 60])

    def test_flag_0x40_creates_three_ten_percent_debuffs(self):
        result = self._manifest()
        self.assertEqual(
            result["followups"]["0x40"],
            {
                "status_codes": ["0x1F", "0x21", "0x23"],
                "duration_turns": 3,
                "value_u16": 10,
                "reaction_state": None,
            },
        )
        self.assertEqual(
            result["ninja_tool_producers"]["0x40"],
            [11, 12, 13, 25, 26, 27, 43, 44, 45, 70, 71, 72],
        )

    def test_status_parameter_mapping_is_explicit(self):
        result = self._manifest()
        self.assertEqual(
            result["status_parameter_mapping"],
            {
                "raw_parameter_1": "queued_event_potency",
                "raw_parameter_4": "queued_event_source_unit",
                "duration": "handler_constant",
                "value_u16": "handler_constant",
            },
        )


if __name__ == "__main__":
    unittest.main()
