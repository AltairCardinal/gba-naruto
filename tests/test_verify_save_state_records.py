#!/usr/bin/env python3
"""Regression tests for save-state table and SRAM record verification."""

from __future__ import annotations

import unittest

from tools.verify_save_state_records import (
    real_sram_offset,
    save_checksum,
    validate_bank,
    validate_sram_dump,
)


def fixture_bank() -> dict:
    return {
        "table_offset": 0x20,
        "entry_count": 2,
        "unique_field_count": 1,
        "entry_size": 8,
        "data_size_per_entry": 20,
        "data_format": {
            "data_bytes": 19,
            "checksum_bytes": 1,
        },
        "entries": [
            {
                "_raw_offset": 0x20,
                "ewram_buffer": 0x02026804,
                "sram_offset_field": 0x8,
            },
            {
                "_raw_offset": 0x28,
                "ewram_buffer": 0x02026804,
                "sram_offset_field": 0x8,
            },
        ],
        "unique_save_fields": [
            {
                "sram_offset": "0x001C",
                "ewram_buffer": "0x02026804",
            }
        ],
    }


class SaveStateVerificationTests(unittest.TestCase):
    def test_checksum_is_not_sum_masked(self):
        data = bytes(range(19))
        self.assertEqual((~sum(data)) & 0xFF, save_checksum(data))
        self.assertNotEqual(sum(data) & 0xFF, save_checksum(data))

    def test_real_sram_offset_adds_handler_delta(self):
        self.assertEqual(0x1C, real_sram_offset(0x8))
        self.assertEqual(0x1290, real_sram_offset(0x127C))

    def test_validate_bank_checks_rom_table_and_unique_fields(self):
        bank = fixture_bank()
        rom = bytearray(0x40)
        rom[0x20:0x28] = (0x02026804).to_bytes(4, "little") + (0x8).to_bytes(4, "little")
        rom[0x28:0x30] = (0x02026804).to_bytes(4, "little") + (0x8).to_bytes(4, "little")

        report = validate_bank(bank, bytes(rom))

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(2, report["entry_count"])
        self.assertEqual(1, report["unique_entry_count"])

    def test_validate_bank_reports_rom_mismatch(self):
        bank = fixture_bank()
        rom = bytearray(0x40)
        rom[0x20:0x28] = (0x02026804).to_bytes(4, "little") + (0x8).to_bytes(4, "little")
        rom[0x28:0x30] = (0x020240AC).to_bytes(4, "little") + (0x14).to_bytes(4, "little")

        report = validate_bank(bank, bytes(rom))

        self.assertFalse(report["ok"])
        self.assertIn("ROM mismatch", report["issues"][0])

    def test_validate_sram_dump_checks_each_unique_record_checksum(self):
        bank = fixture_bank()
        sram = bytearray(0x10000)
        payload = bytes(range(19))
        sram[0x1C:0x30] = payload + bytes([save_checksum(payload)])

        report = validate_sram_dump(bank, bytes(sram))

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual("0x001C", report["records"][0]["sram_offset"])

    def test_validate_sram_dump_rejects_bad_checksum(self):
        bank = fixture_bank()
        sram = bytearray(0x10000)
        sram[0x1C:0x30] = bytes(range(19)) + b"\x00"

        report = validate_sram_dump(bank, bytes(sram))

        self.assertFalse(report["ok"])
        self.assertIn("checksum mismatch", report["issues"][0])


if __name__ == "__main__":
    unittest.main()
