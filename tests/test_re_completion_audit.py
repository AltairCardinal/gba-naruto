#!/usr/bin/env python3
"""Integration tests for bank-to-base-ROM byte fidelity auditing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_re_completion import audit_bank


class ReCompletionAuditTests(unittest.TestCase):
    def test_non_contiguous_entries_use_explicit_rom_offsets_and_numeric_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bank = root / "sequel/content/positions/bank.json"
            bank.parent.mkdir(parents=True)
            bank.write_text(json.dumps({
                "table_offset": 4,
                "table_offset_hex": "0x4",
                "entry_size": 4,
                "entry_count": 2,
                "format": {"fields": {
                    "x": {"offset": 0, "size": 1},
                    "value": {"offset": 1, "size": 2},
                }},
                "entries": [
                    {"rom_offset": 4, "x": 7, "value": 0x1234},
                    {"rom_offset": 12, "x": 9, "value": 0x5678},
                ],
                "verification": "static_verified",
            }), encoding="utf-8")
            rom = bytes.fromhex("00000000 07341200 00000000 09785600")
            result = audit_bank(root, bank, {}, rom)

        self.assertTrue(result["checks"]["rom_fidelity"], result["issues"])
        self.assertEqual(result["rom_fidelity_fields_checked"], 4)


if __name__ == "__main__":
    unittest.main()
