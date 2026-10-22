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
    generate_map_sprite_patches,
    generate_menu_ui_patches,
    generate_palette_patches,
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

    def make_editor_db(self) -> Path:
        """A synthetic editor.db with the real tables and the real bases.

        ``sequel/editor.db`` is gitignored, so the wrappers must be tested
        against a database built here.  Every ``_rom_offset`` is the address
        the wrapper is supposed to write, which is exactly what the wrappers
        cross-check before they emit a patch.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        path = Path(tmp.name)
        conn = sqlite3.connect(path)
        # (table, column, base, count, stride, pointer)
        #
        # The bases are the **adjudicated** ones (the legacy bases were
        # skewed windows): see notes/evidence/legacy-rebase-final-20261021.md.
        # The column names come from the banks' `entry_format.fields`.
        tables = [
            ("rom_data_table_a", "rom_ptr", 0x5A143C, 46, 4, 0x0812F000),
            ("rom_data_table_b", "rom_ptr", 0x5A2034, 90, 4, 0x0812F100),
            ("rom_function_pointers", "slot_value", 0x53D5F0, 13, 4, 0x08001235),
            ("rom_menu_ui", "expr0_ptr_0", 0x5A4DEC, 63, 40, 0x0812F200),
            ("rom_tile_assets", "tile_ptr_0", 0x5A320C, 79, 68, 0x0812F300),
            ("rom_map_sprites", "sprite_ptr", 0x53F140, 86, 4, 0x0812F400),
            ("rom_palettes", "palette_ptr", 0x53F138, 88, 4, 0x0812F500),
            ("rom_resource_pointers", "resource_ptr", 0x596F0C, 20, 4, 0x0812F600),
        ]
        for table, column, base, count, stride, pointer in tables:
            conn.execute(
                f'CREATE TABLE "{table}" (_idx INTEGER PRIMARY KEY, '
                f'_rom_offset INTEGER NOT NULL, "{column}" INTEGER NOT NULL)'
            )
            conn.executemany(
                f'INSERT INTO "{table}" VALUES (?, ?, ?)',
                [(i, base + i * stride, pointer + i * stride)
                 for i in range(count)],
            )
        # the sprite action table: 16-byte records, four pointer columns
        conn.execute(
            "CREATE TABLE rom_sprite_animations (_idx INTEGER PRIMARY KEY, "
            "_rom_offset INTEGER NOT NULL, frames_ptr INTEGER, "
            "animations_ptr INTEGER, gfx_ptr INTEGER, palette_ptr INTEGER)"
        )
        conn.executemany(
            "INSERT INTO rom_sprite_animations VALUES (?, ?, ?, ?, ?, ?)",
            [(i, 0x596CCC + i * 16, 0x0812F700, 0x0812F800,
              0x0812F900, 0x0812FA00) for i in range(2)],
        )
        conn.commit()
        conn.close()
        self.addCleanup(path.unlink, missing_ok=True)
        return path

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
        """Each wrapper must write to the table the repo actually proved.

        The old version of this test read ``sequel/editor.db`` -- a file that
        is gitignored, so on a clean checkout it asserted nothing at all
        (7 failing subtests) and, worse, it pinned the **falsified**
        address ``0x53F200`` for the sprite animations.  The tables are now
        built synthetically so the assertion runs everywhere, and the
        addresses come from the adjudicated bases.
        """
        db = self.make_editor_db()
        cases = [
            (generate_data_table_a_patches, "rom_data_table_a", 46,
             0x5A143C, 0x5A143C + 45 * 4, "data"),
            (generate_data_table_b_patches, "rom_data_table_b", 90,
             0x5A2034, 0x5A2034 + 89 * 4, "data"),
            (generate_function_pointer_patches, "rom_function_pointers", 13,
             0x53D5F0, 0x53D5F0 + 12 * 4, "raw"),
            # the portrait table: 40-byte rows, the written pointer is the
            # first expression slot of the row
            (generate_menu_ui_patches, "rom_menu_ui", 63,
             0x5A4DEC, 0x5A4DEC + 62 * 40, "data"),
            # the tile-asset table: 68-byte records, the written pointer is
            # the record's +0x0C field
            (generate_tile_asset_patches, "rom_tile_assets", 79,
             0x5A320C + 12, 0x5A320C + 78 * 68 + 12, "data"),
            # adjudicated base: 0x53F1DC is item 39 of the array at 0x53F140
            (generate_map_sprite_patches, "rom_map_sprites", 86,
             0x53F140, 0x53F140 + 85 * 4, "data"),
        ]
        for generator, table, count, first, last, kind in cases:
            with self.subTest(generator=generator.__name__):
                patches = generator(db)
                self.assertEqual(len(patches), count)
                self.assertTrue(all(p["type"] == "bytes" for p in patches))
                self.assertEqual(patches[0]["offset"], first)
                self.assertEqual(patches[-1]["offset"], last)
                self.assertEqual(patches[0]["db_table"], table)

    def test_sprite_animation_wrapper_writes_the_real_action_table(self):
        """The sprite action table is 0x596CCC with a 16-byte stride."""
        db = self.make_editor_db()
        patches = generate_sprite_animation_patches(db)
        self.assertEqual(len(patches), 8)          # 2 rows x 4 pointer columns
        self.assertEqual(patches[0]["offset"], 0x596CCC)
        self.assertEqual(patches[-1]["offset"], 0x596CCC + 16 + 12)
        self.assertNotIn(0x53F200, {p["offset"] for p in patches})

    def test_falsified_alias_writers_refuse_instead_of_corrupting(self):
        """0x53F138 and 0x596F0C are windows, not table bases."""
        db = self.make_editor_db()
        for generator, marker in (
            (generate_palette_patches, "db_palette_unmapped"),
            (generate_resource_pointer_patches, "db_resource_pointer_unmapped"),
        ):
            with self.subTest(generator=generator.__name__):
                patches = generator(db)
                self.assertTrue(patches)
                self.assertTrue(all(p["type"] == marker for p in patches))
                self.assertNotIn("bytes", {p["type"] for p in patches})


if __name__ == "__main__":
    unittest.main()
