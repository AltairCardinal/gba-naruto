#!/usr/bin/env python3
"""Tests for the ROM-backed character-definition extractor."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.extract_character_definitions import (
    CHARACTER_DEFINITION_COUNT,
    CHARACTER_DEFINITION_STRIDE,
    CHARACTER_DEFINITIONS_END,
    CHARACTER_DEFINITIONS_FILE,
    NEXT_GROWTH_TABLE_FILE,
    POST_TABLE_GAP_SIZE,
    WRAM_TEMPLATE_COUNT,
    WRAM_TEMPLATE_POOL,
    WRAM_TEMPLATE_STRIDE,
    WRAM_UNIT_ARRAY,
    WRAM_UNIT_STRIDE,
    extract_character_definitions,
    record_offset,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom" / "base.gba"


class ExtractCharacterDefinitionsTests(unittest.TestCase):
    def test_static_trace_constants_are_encoded(self):
        self.assertEqual(CHARACTER_DEFINITIONS_FILE, 0x54241C)
        self.assertEqual(CHARACTER_DEFINITION_COUNT, 63)
        self.assertEqual(CHARACTER_DEFINITION_STRIDE, 0x00B4)
        self.assertEqual(CHARACTER_DEFINITIONS_END, 0x545068)
        self.assertEqual(NEXT_GROWTH_TABLE_FILE, 0x545068)
        self.assertEqual(POST_TABLE_GAP_SIZE, 0)
        self.assertEqual(WRAM_TEMPLATE_POOL, 0x02022E34)
        self.assertEqual(WRAM_TEMPLATE_COUNT, 24)
        self.assertEqual(WRAM_TEMPLATE_STRIDE, 0x00BC)
        self.assertEqual(WRAM_UNIT_ARRAY, 0x020240C0)
        self.assertEqual(WRAM_UNIT_STRIDE, 0x01D4)

    def test_extracts_complete_table_with_expected_boundaries(self):
        bank = extract_character_definitions(BASE_ROM.read_bytes())
        self.assertEqual(bank["entry_count"], CHARACTER_DEFINITION_COUNT)
        self.assertEqual(len(bank["entries"]), CHARACTER_DEFINITION_COUNT)
        self.assertEqual(bank["table_offset"], CHARACTER_DEFINITIONS_FILE)
        self.assertEqual(bank["table_offset_hex"], "0x54241C")
        self.assertEqual(bank["format"]["table_end"], CHARACTER_DEFINITIONS_END)
        self.assertEqual(bank["format"]["next_growth_table"], NEXT_GROWTH_TABLE_FILE)
        self.assertEqual(bank["format"]["post_table_gap_size"], POST_TABLE_GAP_SIZE)
        self.assertEqual(bank["format"]["post_table_gap_hex"], "")
        self.assertEqual(bank["format"]["post_table_zero_prefix"], 0)

    def test_record_offsets_are_unique_and_lossless(self):
        rom = BASE_ROM.read_bytes()
        bank = extract_character_definitions(rom)
        offsets = [entry["rom_offset"] for entry in bank["entries"]]
        self.assertEqual(len(offsets), len(set(offsets)))
        for entry in bank["entries"]:
            character_id = entry["character_id"]
            expected = record_offset(character_id)
            self.assertEqual(entry["rom_offset"], expected)
            self.assertEqual(entry["raw_hex"], rom[expected:expected + CHARACTER_DEFINITION_STRIDE].hex())

    def test_known_records_match_baseline_bytes(self):
        bank = extract_character_definitions(BASE_ROM.read_bytes())
        samples = {entry["character_id"]: entry for entry in bank["entries"]}
        self.assertEqual(samples[0]["rom_offset"], 0x54241C)
        self.assertEqual(samples[0]["raw_hex"][:32], "00000000000000000000000000000000")
        self.assertFalse(samples[0]["active"])
        self.assertEqual(samples[1]["rom_offset"], 0x5424D0)
        self.assertEqual(samples[1]["raw_hex"][:32], "010e0d08030505000f00500002010000")
        self.assertEqual(samples[40]["rom_offset"], 0x54403C)
        self.assertEqual(samples[40]["raw_hex"][:32], "010f0a0a0300000000004b0055010000")
        self.assertEqual(samples[62]["rom_offset"], 0x544FB4)
        self.assertEqual(samples[62]["raw_hex"][:32], "011405280306030005000a0001030000")

    def test_loader_derived_fields_and_slot_arrays_are_exposed(self):
        entry = extract_character_definitions(BASE_ROM.read_bytes())["entries"][1]
        self.assertEqual(entry["active_flag"], 1)
        self.assertEqual(entry["template_02_base"], 14)
        self.assertEqual(entry["template_0a_base"], 15)
        self.assertEqual(entry["template_0e_base"], 80)
        self.assertEqual(len(entry["primary_slots"]), 15)
        self.assertEqual(len(entry["secondary_slots"]), 24)
        self.assertEqual(entry["primary_slots"][0], {
            "slot": 0, "id": 2, "initial_state": 1, "unlock_level": 0, "reserved": 0,
        })

    def test_cli_writes_bank_compatible_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bank.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "extract_character_definitions.py"),
                    str(BASE_ROM),
                    "--bank",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            bank = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(bank["table_offset_hex"], "0x54241C")
            self.assertEqual(bank["entry_count"], CHARACTER_DEFINITION_COUNT)
            self.assertEqual(bank["entry_size"], CHARACTER_DEFINITION_STRIDE)
            self.assertEqual(bank["verification"], "runtime_verified")
            self.assertEqual(bank["entries"][1]["character_id"], 1)


if __name__ == "__main__":
    unittest.main()
