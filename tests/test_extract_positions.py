#!/usr/bin/env python3
"""Tests for the ROM-backed battle-position extractor."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.extract_positions import (
    BATTLE_EXPERIENCE_OFFSET,
    GROUP_COUNT,
    GROUP_STRIDE,
    POSITION_TABLE_FILE,
    RECORD_COUNT,
    RECORD_STRIDE,
    UNIT_STRIDE,
    VARIANT_COUNT,
    VARIANT_STRIDE,
    X_OFFSET,
    Y_OFFSET,
    extract_positions,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom" / "base.gba"


class ExtractPositionsTests(unittest.TestCase):
    def test_static_trace_constants_are_encoded(self):
        self.assertEqual(POSITION_TABLE_FILE, 0x5461C4)
        self.assertEqual(GROUP_STRIDE, 0x1AAC)
        self.assertEqual(VARIANT_STRIDE, 0x08E4)
        self.assertEqual(RECORD_STRIDE, 0x00B8)
        self.assertEqual(X_OFFSET, 2)
        self.assertEqual(Y_OFFSET, 3)
        self.assertEqual(BATTLE_EXPERIENCE_OFFSET, 0x0C)
        self.assertEqual(UNIT_STRIDE, 0x01D4)

    def test_extracts_known_group_one_variant_zero_coordinates(self):
        bank = extract_positions(BASE_ROM.read_bytes())
        entry = next(
            item for item in bank["entries"]
            if item["group_id"] == 1
            and item["variant_id"] == 0
            and item["record_id"] == 0
        )
        self.assertEqual(entry["rom_offset"], 0x547C74)
        self.assertEqual((entry["x"], entry["y"]), (10, 9))
        self.assertEqual(entry["selector"], 1)
        self.assertTrue(entry["active"])

    def test_extracts_rom_carried_battle_experience(self):
        bank = extract_positions(BASE_ROM.read_bytes())
        naruto = next(
            item for item in bank["entries"]
            if item["group_id"] == 41
            and item["variant_id"] == 0
            and item["record_id"] == 0
        )
        konohamaru = next(
            item for item in bank["entries"]
            if item["group_id"] == 41
            and item["variant_id"] == 0
            and item["record_id"] == 1
        )
        cats = [
            item for item in bank["entries"]
            if item["group_id"] == 9
            and item["variant_id"] == 0
            and item["active"]
            and item["affiliation"] == 1
        ]
        self.assertEqual(naruto["battle_experience"], 0)
        self.assertEqual(konohamaru["battle_experience"], 50)
        self.assertEqual([item["battle_experience"] for item in cats], [30] * 5)

    def test_extracts_fixed_unit_runtime_configuration(self):
        bank = extract_positions(BASE_ROM.read_bytes())
        naruto = next(
            item for item in bank["entries"]
            if item["group_id"] == 10
            and item["variant_id"] == 0
            and item["record_id"] == 2
        )

        self.assertEqual(naruto["selector"], 1)
        self.assertEqual(naruto["level"], 20)
        self.assertEqual(naruto["unit_parameter"], 1)
        self.assertEqual(
            naruto["primary_action_slots"][:3],
            [
                {
                    "action": 1,
                    "state": 2,
                    "unlock_level": 0,
                    "reserved": 0,
                },
                {
                    "action": 2,
                    "state": 2,
                    "unlock_level": 0,
                    "reserved": 0,
                },
                {
                    "action": 5,
                    "state": 2,
                    "unlock_level": 0,
                    "reserved": 0,
                },
            ],
        )
        self.assertEqual(
            naruto["secondary_action_slots"][:3],
            [
                {
                    "action": 6,
                    "state": 1,
                    "unlock_level": 0,
                    "reserved": 0,
                },
                {
                    "action": 5,
                    "state": 3,
                    "unlock_level": 0,
                    "reserved": 0,
                },
                {
                    "action": 2,
                    "state": 2,
                    "unlock_level": 0,
                    "reserved": 0,
                },
            ],
        )
        self.assertEqual(
            naruto["equipped_tools"],
            [1, 19, 41, 41, 41, 0, 0, 0, 0],
        )

    def test_extracts_complete_matrix_without_aliasing_variants(self):
        bank = extract_positions(BASE_ROM.read_bytes())
        self.assertEqual(len(bank["entries"]), GROUP_COUNT * VARIANT_COUNT * RECORD_COUNT)
        offsets = [item["rom_offset"] for item in bank["entries"]]
        self.assertEqual(len(offsets), len(set(offsets)))

    def test_cli_writes_bank_compatible_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "bank.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "extract_positions.py"),
                 str(BASE_ROM), "--bank", str(output)],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            bank = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(bank["table_offset_hex"], "0x5461C4")
            self.assertEqual(bank["entry_count"], GROUP_COUNT * VARIANT_COUNT * RECORD_COUNT)
            self.assertEqual(bank["wram_unit_array"]["stride"], UNIT_STRIDE)
            self.assertEqual(bank["verification"], "static_verified")


if __name__ == "__main__":
    unittest.main()
