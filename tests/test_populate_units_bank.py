#!/usr/bin/env python3
"""Regression tests for units bank population."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import populate_bank_json


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom" / "base.gba"


class PopulateUnitsBankTests(unittest.TestCase):
    def test_populate_units_uses_character_definition_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            bank_dir = temp_root / "sequel" / "content" / "units"
            bank_dir.mkdir(parents=True)
            shutil.copyfile(ROOT / "sequel" / "content" / "units" / "bank.json", bank_dir / "bank.json")

            with mock.patch.object(populate_bank_json, "ROOT", temp_root):
                populate_bank_json.populate_units(BASE_ROM.read_bytes())

            bank = json.loads((bank_dir / "bank.json").read_text(encoding="utf-8"))
            self.assertEqual(bank["table_offset_hex"], "0x54241C")
            self.assertEqual(bank["entry_count"], 63)
            self.assertEqual(bank["entry_size"], 0xB4)
            self.assertEqual(bank["verification"], "code_verified")
            self.assertNotIn("unit_id_table", bank)
            self.assertEqual(bank["entries"][1]["character_id"], 1)


if __name__ == "__main__":
    unittest.main()
