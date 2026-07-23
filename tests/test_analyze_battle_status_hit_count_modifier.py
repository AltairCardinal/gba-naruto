import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusHitCountModifierAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_hit_count_modifier import (
            build_status_hit_count_modifier_manifest,
        )

        return build_status_hit_count_modifier_manifest(ROOT / "rom/base.gba")

    def test_status_0x13_record_parameter_increases_queued_hit_count(self):
        result = self._manifest()
        self.assertEqual(result["event_builder"], "0x080754A8")
        self.assertEqual(result["status_code"], "0x13")
        self.assertEqual(result["effect_type_low_6"], "0x14")
        self.assertEqual(result["builder_lookup_callsite"], "0x08075654")
        self.assertEqual(result["modifier_record_offset"], 6)
        self.assertEqual(result["modifier_width"], "low_u8_of_stored_u16")
        self.assertEqual(
            result["queued_hit_count_operation"],
            "template_hit_count_plus_shared_modifier_accumulator",
        )
        self.assertEqual(result["queued_hit_count_event_offset"], 0x12)

    def test_the_paired_resolution_branch_removes_status_with_an_expiry_event(self):
        result = self._manifest()
        self.assertEqual(result["shared_resolver_callsite"], "0x08077470")
        self.assertEqual(result["post_resolution_lookup_callsite"], "0x08077488")
        self.assertEqual(result["post_resolution_remove_callsite"], "0x08077496")
        self.assertEqual(result["post_resolution_removal_mode"], 1)
        self.assertTrue(result["post_resolution_emits_removed_status_event_if_capacity"])

    def test_missing_status_is_a_content_invariant_not_an_out_of_bounds_contract(self):
        result = self._manifest()
        self.assertFalse(result["builder_checks_not_found_before_record_read"])
        self.assertEqual(
            result["implementation_requirement"],
            "effect_type_0x14_requires_status_0x13_or_content_validation_fails",
        )
        self.assertIsNone(result["visible_gameplay_name"])


if __name__ == "__main__":
    unittest.main()
