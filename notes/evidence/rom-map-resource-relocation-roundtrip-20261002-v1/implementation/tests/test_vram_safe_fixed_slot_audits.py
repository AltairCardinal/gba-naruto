from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VramSafeFixedSlotAuditTests(unittest.TestCase):
    def test_menu_portrait_overflow_is_reported_instead_of_raising(self):
        from tools.export_menu_portrait_writeback_audit import _build_payload

        payload = _build_payload(ROOT)

        self.assertEqual(74, payload["summary"]["resource_count"])
        self.assertEqual(74, payload["summary"]["original_roundtrip_fit_count"])
        self.assertEqual(37, payload["summary"]["single_pixel_mutation_fit_count"])
        self.assertFalse(
            payload["scope"]["single_pixel_mutation_capacity_complete"]
        )
        overflow = [
            row for row in payload["resources"]
            if not row["single_pixel_mutation_fit"]
        ]
        self.assertEqual(37, len(overflow))
        self.assertTrue(
            all(row["fixed_slot_patch_sha256"] is None for row in overflow)
        )
        self.assertTrue(
            all(not row["fixed_slot_decode_verified"] for row in overflow)
        )

    def test_map_capacity_uses_vram_safe_encoding(self):
        from tools.export_map_resource_writeback_audit import _build_payload

        summary = _build_payload(ROOT)["summary"]

        self.assertEqual(70, summary["mutation_fit_all_alias_content_count"])
        self.assertEqual(91, summary["mutation_fit_slot_count"])

    def test_battle_effect_capacity_uses_vram_safe_encoding(self):
        from tools.export_battle_effect_resource_writeback_audit import (
            _build_payload,
        )

        summary = _build_payload(ROOT)["summary"]

        self.assertEqual(23, summary["mutation_fit_all_alias_content_count"])
        self.assertEqual(24, summary["mutation_fit_slot_count"])
        self.assertEqual(24, summary["mutation_fit_logical_reference_count"])

    def test_bg_capacity_uses_vram_safe_encoding(self):
        from tools.export_bg_resource_writeback_audit import _build_payload

        summary = _build_payload(ROOT)["summary"]

        self.assertEqual(10, summary["mutation_fit_all_alias_content_count"])
        self.assertEqual(10, summary["mutation_fit_slot_count"])
        self.assertEqual(10, summary["mutation_fit_logical_reference_count"])


if __name__ == "__main__":
    unittest.main()
