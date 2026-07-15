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

    def test_function_pointer_wrapper_still_covers_declared_real_table(self):
        db = self.make_pointer_db(
            "rom_function_pointers", "func_ptr", 11, 0x53D5F4, 0x08001235
        )
        patches = generate_function_pointer_patches(db)
        self.assertEqual(len(patches), 11)
        self.assertTrue(all(p["type"] == "bytes" for p in patches))
        self.assertEqual(patches[0]["offset"], 0x53D5F4)
        self.assertEqual(patches[-1]["offset"], 0x53D61C)

    def test_corrected_partial_views_are_diagnostic_only(self):
        cases = [
            (generate_data_table_a_patches, "rom_data_table_a", "data_ptr", 20,
             0x5A14A4, "db_data_table_a_unmapped"),
            (generate_data_table_b_patches, "rom_data_table_b", "data_ptr", 20,
             0x5A2120, "db_data_table_b_unmapped"),
            (generate_menu_ui_patches, "rom_menu_ui", "ui_ptr", 20,
             0x5A5774, "db_menu_ui_unmapped"),
            (generate_resource_pointer_patches, "rom_resource_pointers", "resource_ptr", 20,
             0x596F0C, "db_resource_pointer_unmapped"),
            (generate_sprite_animation_patches, "rom_sprite_animations", "anim_ptr", 38,
             0x53F200, "db_sprite_animation_unmapped"),
            (generate_tile_asset_patches, "rom_tile_assets", "tile_ptr", 6,
             0x5A3218, "db_tile_asset_unmapped"),
        ]
        for generator, table, pointer_column, count, first, diagnostic_type in cases:
            with self.subTest(generator=generator.__name__):
                db = self.make_pointer_db(table, pointer_column, count, first, 0x08010000)
                patches = generator(db)
                self.assertEqual(len(patches), count)
                self.assertTrue(all(p["type"] == diagnostic_type for p in patches))
                self.assertFalse(any(p["type"] == "bytes" for p in patches))

    def make_pointer_db(
        self,
        table: str,
        pointer_column: str,
        count: int,
        table_offset: int,
        pointer: int,
    ) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = Path(tmp.name)
        conn = sqlite3.connect(path)
        conn.execute(
            f"CREATE TABLE {table} (_idx INTEGER PRIMARY KEY, "
            f"_rom_offset INTEGER NOT NULL, {pointer_column} INTEGER NOT NULL)"
        )
        rows = [
            (index, table_offset + index * 4, pointer)
            for index in range(count)
        ]
        conn.executemany(
            f"INSERT INTO {table} VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()
        self.addCleanup(path.unlink, missing_ok=True)
        return path


if __name__ == "__main__":
    unittest.main()
