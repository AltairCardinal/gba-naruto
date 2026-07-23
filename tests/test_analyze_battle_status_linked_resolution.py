import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusLinkedResolutionAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_linked_resolution import (
            build_status_linked_resolution_manifest,
        )

        return build_status_linked_resolution_manifest(ROOT / "rom/base.gba")

    def test_status_0x0e_recurses_into_the_shared_resolver_for_a_linked_unit(self):
        result = self._manifest()
        self.assertEqual(result["shared_resolver"], "0x08076A30")
        self.assertEqual(result["shared_resolver_end"], "0x08076CDE")
        self.assertEqual(result["status_code"], "0x0E")
        self.assertEqual(result["lookup_callsite"], "0x08076B48")
        self.assertEqual(result["recursive_callsite"], "0x08076B6C")
        self.assertEqual(result["linked_target_record_offset"], 4)

    def test_recursive_resolution_preserves_the_primary_event_and_uses_a_guard(self):
        result = self._manifest()
        self.assertEqual(
            result["recursive_arguments"],
            {
                "source": "original_source",
                "target": "active_status_record_plus_4_unit_slot",
                "action_type": "same_as_primary",
                "amount": "same_as_primary",
                "extra_arguments": [0, 0, 0, 1],
            },
        )
        self.assertEqual(result["recursion_guard_extra_argument_index"], 3)
        self.assertTrue(result["primary_target_still_resolves"])
        self.assertEqual(result["skipped_action_type"], "0x1F")

    def test_operational_semantics_do_not_invent_a_visible_gameplay_name(self):
        result = self._manifest()
        self.assertEqual(
            result["operational_semantics"],
            "linked_target_recursive_resolution_before_primary_target_damage",
        )
        self.assertIsNone(result["visible_gameplay_name"])


if __name__ == "__main__":
    unittest.main()
