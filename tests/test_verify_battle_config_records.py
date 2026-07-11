#!/usr/bin/env python3
"""Regression tests for battle-config table verification."""

from __future__ import annotations

import unittest

from tools.verify_battle_config_records import (
    EXPECTED_ENTRY_SIZE,
    EXPECTED_FIELD_NAMES,
    EXPECTED_TABLE_OFFSET,
    validate_bank,
)


def fixture_bank() -> dict:
    fields = [
        {"offset": index * 2, "size": 2, "name": name, "type": "u16"}
        for index, name in enumerate(EXPECTED_FIELD_NAMES)
    ]
    entries = []
    for index in range(32):
        values = [0] * 8 if index == 0 else [index, 2, 3, 4, 5, 6, 7, 8]
        entry = {"_raw_offset": EXPECTED_TABLE_OFFSET + index * EXPECTED_ENTRY_SIZE}
        for name, value in zip(EXPECTED_FIELD_NAMES, values):
            entry[name] = value
            entry[f"{name}_hex"] = value.to_bytes(2, "little").hex()
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
        for index, name in enumerate(EXPECTED_FIELD_NAMES):
            rom[offset + index * 2:offset + index * 2 + 2] = entry[name].to_bytes(
                2, "little"
            )
    return bytes(rom)


class BattleConfigVerificationTests(unittest.TestCase):
    def test_validate_bank_accepts_matching_u16_table(self):
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
        bank["entries"][0]["config_id"] = 1
        bank["entries"][0]["config_id_hex"] = "0100"

        report = validate_bank(bank, fixture_rom(fixture_bank()))

        self.assertFalse(report["ok"])
        self.assertIn("entry 0", "\n".join(report["issues"]))


if __name__ == "__main__":
    unittest.main()
