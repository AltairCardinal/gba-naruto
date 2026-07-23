import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusParticipantConsumptionAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_participant_consumption import (
            build_status_participant_consumption_manifest,
        )

        return build_status_participant_consumption_manifest(ROOT / "rom/base.gba")

    def test_status_0x0d_is_consumed_from_both_normal_event_participants(self):
        result = self._manifest()
        self.assertEqual(result["resolver_queue"], "0x08076CE0")
        self.assertEqual(result["status_code"], "0x0D")
        self.assertEqual(
            result["lookup_callsites"],
            {"source": "0x08076DC4", "target": "0x08076DDC"},
        )
        self.assertEqual(
            result["remove_callsites"],
            {"source": "0x08076DD4", "target": "0x08076DEC"},
        )
        self.assertEqual(result["removal_mode"], 0)

    def test_reaction_events_do_not_consume_status_0x0d(self):
        result = self._manifest()
        self.assertEqual(
            result["skipped_event_type_low_6_values"],
            ["0x04", "0x09", "0x0A", "0x10", "0x16", "0x19"],
        )
        self.assertEqual(result["skipped_family"], "known_reaction_event_codes")

    def test_target_consumption_also_clears_one_unit_state_bit_without_naming_it(self):
        result = self._manifest()
        self.assertEqual(result["target_unit_state_word_offset"], 0xC0)
        self.assertEqual(result["target_unit_state_and_mask"], "0xFFFFFEFF")
        self.assertEqual(result["target_unit_state_cleared_bits"], "0x00000100")
        self.assertIsNone(result["visible_gameplay_name"])


if __name__ == "__main__":
    unittest.main()
