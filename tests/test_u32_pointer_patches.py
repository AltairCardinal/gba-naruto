#!/usr/bin/env python3
"""Unit tests for safe, game-effective indexed u32 pointer patches."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import (
    _generate_u32_pointer_table_patches,
    generate_data_table_a_patches,
    generate_data_table_b_patches,
    generate_function_pointer_patches,
    generate_menu_ui_patches,
    generate_resource_pointer_patches,
    generate_sprite_animation_patches,
    generate_tile_asset_patches,
)


class U32PointerPatchTests(unittest.TestCase):
    def make_db(self, rows: list[tuple[int, int, int]]) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = Path(tmp.name)
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE rom_test (_idx INTEGER PRIMARY KEY, "
            "_rom_offset INTEGER NOT NULL, ptr INTEGER NOT NULL)"
        )
        conn.executemany("INSERT INTO rom_test VALUES (?, ?, ?)", rows)
        conn.commit()
        conn.close()
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def generate(self, db: Path, kind: str = "thumb", count: int = 3):
        return _generate_u32_pointer_table_patches(
            db, table="rom_test", index_column="_idx", pointer_column="ptr",
            table_offset=0x100, entry_count=count, pointer_kind=kind,
        )

    def test_valid_thumb_pointer_writes_real_table_slot(self):
        patches = self.generate(self.make_db([(1, 0x104, 0x08001235)]))
        self.assertEqual(patches[0]["type"], "bytes")
        self.assertEqual(patches[0]["offset"], 0x104)
        self.assertEqual(patches[0]["after_hex"], "35120008")

    def test_rejects_index_outside_declared_table(self):
        patch = self.generate(self.make_db([(3, 0x10C, 0x08001235)]))[0]
        self.assertEqual(patch["type"], "db_pointer_table_error")
        self.assertIn("outside", patch["error"])

    def test_rejects_stale_imported_rom_offset(self):
        patch = self.generate(self.make_db([(1, 0x204, 0x08001235)]))[0]
        self.assertEqual(patch["type"], "db_pointer_table_error")
        self.assertIn("stale _rom_offset", patch["error"])

    def test_rejects_pointer_outside_48_mbit_rom(self):
        for pointer in (0x07FFFFFF, 0x08600001):
            with self.subTest(pointer=pointer):
                patch = self.generate(self.make_db([(0, 0x100, pointer)]))[0]
                self.assertEqual(patch["type"], "db_pointer_table_error")
                self.assertIn("outside 48 Mbit", patch["error"])

    def test_thumb_and_data_low_bit_rules(self):
        thumb = self.generate(self.make_db([(0, 0x100, 0x08001234)]), "thumb")[0]
        data = self.generate(self.make_db([(0, 0x100, 0x08001235)]), "data")[0]
        self.assertIn("bit 0 clear", thumb["error"])
        self.assertIn("bit 0 set", data["error"])

    def test_byte_stream_pointer_may_be_odd(self):
        patch = self.generate(
            self.make_db([(0, 0x100, 0x0853650F)]), "rom"
        )[0]
        self.assertEqual(patch["type"], "bytes")

    def test_second_batch_wrappers_cover_declared_real_tables(self):
        db = Path(__file__).resolve().parents[1] / "sequel/editor.db"
        cases = [
            (generate_data_table_a_patches, 20, 0x5A14A4, 0x5A14F0),
            (generate_data_table_b_patches, 20, 0x5A2120, 0x5A216C),
            (generate_function_pointer_patches, 11, 0x53D5F4, 0x53D61C),
            (generate_menu_ui_patches, 20, 0x5A5774, 0x5A57C0),
            (generate_resource_pointer_patches, 20, 0x596F0C, 0x596F58),
            (generate_sprite_animation_patches, 38, 0x53F200, 0x53F294),
            (generate_tile_asset_patches, 6, 0x5A3218, 0x5A322C),
        ]
        for generator, count, first, last in cases:
            with self.subTest(generator=generator.__name__):
                patches = generator(db)
                self.assertEqual(len(patches), count)
                self.assertTrue(all(p["type"] == "bytes" for p in patches))
                self.assertEqual(patches[0]["offset"], first)
                self.assertEqual(patches[-1]["offset"], last)


if __name__ == "__main__":
    unittest.main()
