#!/usr/bin/env python3
"""Regression tests for battle-config table verification."""

from __future__ import annotations

import unittest

from tools.verify_battle_config_records import (
    EXPECTED_ENTRY_SIZE,
    EXPECTED_FIELDS,
    EXPECTED_FIELD_NAMES,
    EXPECTED_TABLE_OFFSET,
    validate_bank,
)


def fixture_bank() -> dict:
    fields = [{"offset": offset, "size": size, "name": name} for name, offset, size in EXPECTED_FIELDS]
    entries = []
    for index in range(32):
        values = [0] * len(EXPECTED_FIELDS) if index == 0 else [index & 0xFF] * 14 + [0x1234]
        entry = {"_raw_offset": EXPECTED_TABLE_OFFSET + index * EXPECTED_ENTRY_SIZE}
        for (name, _offset, size), value in zip(EXPECTED_FIELDS, values):
            entry[name] = value
            entry[f"{name}_hex"] = value.to_bytes(size, "little").hex()
        entries.append(entry)
    return {
        "table_offset": EXPECTED_TABLE_OFFSET,
        "entry_count": 32,
        "entry_size": EXPECTED_ENTRY_SIZE,
        "entry_format": {"fields": fields},
        "entries": entries,
    }


def fixture_rom(bank: dict) -> bytes:
    rom = bytearray(EXPECTED_TABLE_OFFSET + 32 * EXPECTED_ENTRY_SIZE)
    for entry in bank["entries"]:
        offset = entry["_raw_offset"]
        for name, field_offset, size in EXPECTED_FIELDS:
            rom[offset + field_offset:offset + field_offset + size] = entry[name].to_bytes(size, "little")
    return bytes(rom)


class BattleConfigVerificationTests(unittest.TestCase):
    def test_validate_bank_accepts_matching_effect_template_table(self):
        bank = fixture_bank()
        report = validate_bank(bank, fixture_rom(bank))

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(32, report["entry_count"])
        self.assertEqual(EXPECTED_ENTRY_SIZE, report["entry_size"])

    def test_validate_bank_rejects_rom_mismatch(self):
        bank = fixture_bank()
        rom = bytearray(fixture_rom(bank))
        rom[EXPECTED_TABLE_OFFSET + EXPECTED_ENTRY_SIZE + 2] ^= 0xFF

        report = validate_bank(bank, bytes(rom))

        self.assertFalse(report["ok"])
        self.assertIn("mismatch", "\n".join(report["issues"]))

    def test_validate_bank_rejects_non_null_entry_zero(self):
        bank = fixture_bank()
        bank["entries"][0]["byte_00"] = 1
        bank["entries"][0]["byte_00_hex"] = "01"

        report = validate_bank(bank, fixture_rom(fixture_bank()))

        self.assertFalse(report["ok"])
        self.assertIn("entry 0", "\n".join(report["issues"]))


if __name__ == "__main__":
    unittest.main()
