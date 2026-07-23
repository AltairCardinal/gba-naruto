import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusTransformationAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_transformation import (
            build_status_transformation_manifest,
        )

        return build_status_transformation_manifest(
            ROOT / "rom/base.gba",
            ROOT / "sequel/content/battle-config/action-identities.json",
        )

    def test_action_4_produces_status_0x05_as_an_identity_override(self):
        result = self._manifest()
        self.assertEqual(result["action_id"], 4)
        self.assertEqual(result["display_name"], "变化术")
        self.assertEqual(result["status_code"], "0x05")
        self.assertEqual(result["template_effect_type_low_6"], "0x05")
        self.assertEqual(result["template_duration_turns"], 3)
        self.assertEqual(result["stored_duration_ticks"], 6)
        self.assertEqual(result["apply_resolver_branch"], "0x0807711A")
        self.assertEqual(result["identity_copy_helper"], "0x0806C0A8")
        self.assertEqual(
            result["identity_copy_operation"],
            "source_character_id_equals_target_character_id",
        )
        self.assertFalse(result["copies_full_unit_record"])

    def test_status_record_keeps_the_linked_target_and_restore_uses_original_identity(self):
        result = self._manifest()
        self.assertEqual(result["linked_target_record_offset"], 4)
        self.assertEqual(result["linked_target_source"], "queued_event_target_unit_slot")
        self.assertEqual(result["restore_helper"], "0x0806C0D4")
        self.assertEqual(result["original_character_id_offset"], 0xBC)
        self.assertEqual(result["restore_refresh_mode"], 0)
        self.assertEqual(result["identity_copy_refresh_mode"], 8)

    def test_defeat_cleanup_restores_then_removes_with_an_event(self):
        result = self._manifest()
        self.assertEqual(result["cleanup_event_type_low_6"], "0x0B")
        self.assertEqual(result["cleanup_resolver_branch"], "0x08077214")
        self.assertEqual(result["cleanup_restore_callsite"], "0x0807723E")
        self.assertEqual(result["cleanup_lookup_callsite"], "0x0807725A")
        self.assertEqual(result["cleanup_remove_callsite"], "0x08077268")
        self.assertEqual(result["cleanup_removal_mode"], 1)
        self.assertEqual(result["eligibility_lookup_callsite"], "0x0806A41E")
        self.assertEqual(result["eligibility_tile_category"], "0x0200")
        self.assertEqual(result["eligibility_status_missing_result"], 0)
        self.assertTrue(result["eligibility_requires_linked_opposite_affiliation"])
        self.assertTrue(result["eligibility_rejects_linked_unit_equal_actor"])
        self.assertEqual(result["eligibility_cleanup_event_type_low_6"], "0x0B")
        self.assertEqual(result["eligibility_cleanup_event_result"], 0)
        self.assertEqual(
            result["eligibility_allowed_path"],
            "preserve_incoming_nonzero_result",
        )
        self.assertEqual(result["side_end_status_tick_callsite"], "0x0807367C")
        self.assertEqual(result["side_end_removed_event_callsite"], "0x08073680")
        self.assertEqual(result["removed_event_processor"], "0x0806C40C")
        self.assertEqual(result["removed_status_0x05_dispatch"], "0x0806C568")
        self.assertEqual(result["natural_expiry_restore_callsite"], "0x0806C5A6")
        self.assertEqual(
            result["natural_expiry_restore_semantics"],
            "duration_zero_copies_record_then_status_0x05_removed_event_restores_identity",
        )
        self.assertEqual(
            result["implementation_requirement"],
            "identity_override_is_domain_state_not_a_sprite_swap",
        )


if __name__ == "__main__":
    unittest.main()
