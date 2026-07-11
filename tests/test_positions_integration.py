#!/usr/bin/env python3
"""Integration tests for ROM-backed positions import and write-back."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_unit_position_patches
from tools.extract_positions import RECORD_STRIDE, record_offset


ROOT = Path(__file__).resolve().parents[1]
BASE_ROM = ROOT / "rom" / "base.gba"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "web-editor" / "backend"))
import rom_models  # type: ignore  # noqa: E402
from tools import build_mod  # noqa: E402


class PositionsIntegrationTests(unittest.TestCase):
    def test_positions_is_generic_extractable_structure(self):
        self.assertIn("positions", rom_models.EXTRACTABLE)

    def test_build_syncs_rom_mirror_before_generating_patches(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as temp:
            db_path = Path(temp.name)
            summary = build_mod.sync_rom_mirrors(db_path)
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM rom_positions").fetchone()[0]
            conn.close()
        self.assertEqual(summary["positions"], 1728)
        self.assertEqual(count, 1728)

    def test_populate_rom_tables_imports_all_positions_with_raw_bytes(self):
        conn = sqlite3.connect(":memory:")
        rom_models.init_rom_tables(conn)
        summary = rom_models.populate_rom_tables(conn, ["positions"])
        self.assertEqual(summary["positions"], 1728)
        count, first_offset, raw_hex = conn.execute(
            "SELECT COUNT(*), MIN(_rom_offset), raw_hex FROM rom_positions "
            "WHERE _idx = 0"
        ).fetchone()
        self.assertEqual(count, 1)
        self.assertEqual(first_offset, 0x5461C8)
        self.assertEqual(len(bytes.fromhex(raw_hex)), RECORD_STRIDE)

    def make_positions_db(self, rows: list[tuple[int, int, str]]) -> Path:
        temp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp.close()
        path = Path(temp.name)
        self.addCleanup(path.unlink, missing_ok=True)
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE rom_positions ("
            "_idx INTEGER PRIMARY KEY, _rom_offset INTEGER, raw_hex TEXT)"
        )
        conn.executemany("INSERT INTO rom_positions VALUES (?, ?, ?)", rows)
        conn.commit()
        conn.close()
        return path

    def test_generator_writes_complete_record_to_its_real_rom_offset(self):
        raw = bytes(range(RECORD_STRIDE))
        offset = record_offset(0, 1, 0)
        patch = generate_unit_position_patches(
            self.make_positions_db([(12, offset, raw.hex())])
        )[0]
        self.assertEqual(patch["type"], "bytes")
        self.assertEqual(patch["offset"], offset)
        self.assertEqual(patch["length"], RECORD_STRIDE)
        self.assertEqual(bytes.fromhex(patch["after_hex"]), raw)
        self.assertEqual(patch["db_table"], "rom_positions")

    def test_generator_rejects_wrong_index_offset_and_out_of_range_record(self):
        raw = bytes(RECORD_STRIDE).hex()
        cases = [
            (0, 0x5461C9, raw, "offset"),
            (0, 0x53D914, raw, "outside positions matrix"),
            (0, 0x5461C8, "00", "184 bytes"),
        ]
        for idx, offset, payload, message in cases:
            with self.subTest(offset=offset, message=message):
                patch = generate_unit_position_patches(
                    self.make_positions_db([(idx, offset, payload)])
                )[0]
                self.assertEqual(patch["type"], "db_unit_position_error")
                self.assertIn(message, patch["error"])

    def test_repository_bank_preserves_every_record_byte(self):
        bank = json.loads(
            (ROOT / "sequel/content/positions/bank.json").read_text(encoding="utf-8")
        )
        rom = BASE_ROM.read_bytes()
        for entry in bank["entries"]:
            offset = entry["_raw_offset"]
            self.assertEqual(
                bytes.fromhex(entry["raw_hex"]), rom[offset : offset + RECORD_STRIDE]
            )


if __name__ == "__main__":
    unittest.main()
