#!/usr/bin/env python3
from __future__ import annotations

import struct
import unittest

from tools.extract_character_growth import (
    ENTRY_COUNT,
    ENTRY_SIZE,
    NEXT_TABLE_OFFSET,
    SPECIAL_GROWTH_RECORDS,
    TABLE_END,
    TABLE_OFFSET,
    build_bank,
)


class CharacterGrowthExtractionTests(unittest.TestCase):
    def fixture_rom(self) -> bytes:
        rom = bytearray(TABLE_END)
        for index in range(ENTRY_COUNT):
            struct.pack_into("<8H", rom, TABLE_OFFSET + index * ENTRY_SIZE, *(index * 10 + n for n in range(8)))
        return bytes(rom)

    def test_table_boundary_meets_next_known_table(self):
        self.assertEqual(NEXT_TABLE_OFFSET, TABLE_END)

    def test_extracts_all_63_character_records_losslessly(self):
        bank = build_bank(self.fixture_rom())
        self.assertEqual(TABLE_OFFSET, bank["table_offset"])
        self.assertEqual(ENTRY_COUNT, len(bank["entries"]))
        self.assertEqual(ENTRY_SIZE * 2, len(bank["entries"][62]["raw_hex"]))
        self.assertEqual(TABLE_OFFSET + 62 * ENTRY_SIZE, bank["entries"][62]["_raw_offset"])

    def test_records_special_runtime_aliases(self):
        bank = build_bank(self.fixture_rom())
        for character_id, record_id in SPECIAL_GROWTH_RECORDS.items():
            self.assertIn(character_id, bank["entries"][record_id]["also_used_by_character_ids"])

    def test_records_player_visible_growth_names(self):
        bank = build_bank(self.fixture_rom())
        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(fields[0]["player_label"], "max_hp")
        self.assertEqual(fields[4]["player_label"], "attack_power")
        self.assertEqual(fields[6]["player_label"], "defense_power")
        self.assertEqual(fields[8]["player_label"], "agility")
        self.assertEqual(fields[10]["player_label"], "movement")
        self.assertNotIn("player_label", fields[2])
        self.assertNotIn("player_label", fields[12])


if __name__ == "__main__":
    unittest.main()
