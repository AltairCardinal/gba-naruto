import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BattleStatusStorageAnalysisTest(unittest.TestCase):
    def _manifest(self):
        from tools.analyze_battle_status_storage import build_status_storage_manifest

        return build_status_storage_manifest(ROOT / "rom/base.gba")

    def test_unit_owns_active_and_removed_status_record_banks(self):
        result = self._manifest()
        self.assertEqual(result["unit_pool"], "0x020240C0")
        self.assertEqual(result["unit_stride"], 0x1D4)
        self.assertEqual(result["active_bank_offset"], 0xD4)
        self.assertEqual(result["removed_event_bank_offset"], 0x154)
        self.assertEqual(result["records_per_bank"], 16)
        self.assertEqual(result["record_stride"], 8)
        self.assertEqual(
            result["record_fields"],
            {
                "0x00": "status_code_with_flags",
                "0x01": "raw_parameter_1",
                "0x02": "duration_ticks",
                "0x03": "raw_parameter_3_low5",
                "0x04": "raw_parameter_4",
                "0x05": "unwritten_by_upsert",
                "0x06": "raw_parameter_6_u16",
            },
        )

    def test_lookup_masks_stored_flags_and_returns_first_matching_slot(self):
        result = self._manifest()
        self.assertEqual(result["lookup"], "0x0806C160")
        self.assertEqual(result["lookup_code_mask"], 0x3F)
        self.assertEqual(result["not_found"], 0xFF)
        self.assertEqual(result["lookup_policy"], "first_active_slot_matching_low_6_code_bits")

    def test_removal_mode_distinguishes_expiry_event_from_direct_consumption(self):
        result = self._manifest()
        self.assertEqual(result["remove"], "0x0806C1A4")
        self.assertEqual(
            result["remove_modes"],
            {
                "0": "clear_active_record_without_removed_event_copy",
                "nonzero": "copy_full_record_to_first_free_removed_event_slot_if_available_then_clear_active_code",
            },
        )

    def test_upsert_replacement_and_duration_encoding_are_explicit(self):
        result = self._manifest()
        self.assertEqual(result["upsert"], "0x0806C204")
        self.assertEqual(result["duration_encoding"], "(raw_duration_low_7_bits * 2) as u8")
        self.assertEqual(result["ordinary_code_policy"], "replace_first_existing_low_6_code_match")
        self.assertEqual(
            result["code_0x3f_policy"],
            "replace_only_when_existing_duration_is_nonzero_and_less_than_new_duration",
        )
        self.assertEqual(result["full_bank_result"], 0xFF)


if __name__ == "__main__":
    unittest.main()
