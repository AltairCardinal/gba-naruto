#!/usr/bin/env python3
"""Regression tests for character-stats table verification."""

from __future__ import annotations

import unittest

from tools.verify_character_stats_records import TABLE_SPECS, validate_bank


def fixture_bank(table: str) -> dict:
    spec = TABLE_SPECS[table]
    fields = [
        {"offset": index * 2, "size": 2, "name": name, "type": "u16"}
        for index, name in enumerate(spec["fields"])
    ]
    entries = []
    for index in range(spec["entry_count"]):
        values = [0] * 8
        values[spec["fields"].index("template_0e_growth")] = 1500
        values[spec["fields"].index("template_02_growth")] = 100
        values[spec["fields"].index("template_03_growth")] = 100
        entry = {"_raw_offset": spec["offset"] + index * spec["entry_size"]}
        for name, value in zip(spec["fields"], values):
            entry[name] = value
            entry[f"{name}_hex"] = value.to_bytes(2, "little").hex()
        entries.append(entry)
    return {
        "table_offset": spec["offset"],
        "entry_count": spec["entry_count"],
        "entry_size": spec["entry_size"],
        "entry_format": {"fields": fields},
        "entries": entries,
    }


def fixture_rom(bank: dict, table: str) -> bytes:
    spec = TABLE_SPECS[table]
    rom = bytearray(spec["offset"] + spec["entry_count"] * spec["entry_size"])
    for entry in bank["entries"]:
        offset = entry["_raw_offset"]
        for index, name in enumerate(spec["fields"]):
            rom[offset + index * 2:offset + index * 2 + 2] = entry[name].to_bytes(
                2, "little"
            )
    return bytes(rom)


class CharacterStatsVerificationTests(unittest.TestCase):
    def test_validate_bank_accepts_primary_table(self):
        bank = fixture_bank("character-stats")
        report = validate_bank(bank, TABLE_SPECS["character-stats"], fixture_rom(bank, "character-stats"))

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(63, report["entry_count"])

    def test_validate_bank_rejects_field_order_mismatch(self):
        bank = fixture_bank("character-stats")
        bank["entry_format"]["fields"][0]["name"] = "char_type"

        report = validate_bank(bank, TABLE_SPECS["character-stats"])

        self.assertFalse(report["ok"])
        self.assertIn("field order mismatch", "\n".join(report["issues"]))

    def test_validate_bank_rejects_rom_mismatch(self):
        bank = fixture_bank("character-stats")
        rom = bytearray(fixture_rom(bank, "character-stats"))
        rom[TABLE_SPECS["character-stats"]["offset"] + 2] ^= 0xFF

        report = validate_bank(bank, TABLE_SPECS["character-stats"], bytes(rom))

        self.assertFalse(report["ok"])
        self.assertIn("mismatch", "\n".join(report["issues"]))


if __name__ == "__main__":
    unittest.main()
