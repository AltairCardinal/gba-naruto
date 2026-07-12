import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import (
    generate_data_table_a_patches,
    generate_data_table_b_patches,
    generate_menu_ui_patches,
    generate_tile_asset_patches,
)


ROOT = Path(__file__).resolve().parents[1]


class TextAndVisualTableIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_profile_text_table_has_all_forty_six_entries(self):
        bank = json.loads((ROOT / "sequel/content/data-table-a/bank.json").read_text())
        self.assertEqual((bank["table_offset"], bank["entry_count"], bank["entry_size"]),
                         (0x5A143C, 46, 4))
        self.assertEqual(bank["verification"], "code_verified")
        pointers = list(struct.unpack_from("<46I", self.rom, 0x5A143C))
        self.assertEqual([entry["text_ptr"] for entry in bank["entries"]], pointers)
        for pointer in pointers:
            offset = pointer - 0x08000000
            self.assertNotEqual(self.rom.find(b"\0", offset, 0x5A143C), -1)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x8A704)[0], 0x085A143C)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x8B214)[0], 0x085A143C)

    def test_battle_message_table_has_all_seventy_nine_entries(self):
        bank = json.loads((ROOT / "sequel/content/data-table-b/bank.json").read_text())
        self.assertEqual((bank["table_offset"], bank["entry_count"], bank["entry_size"]),
                         (0x5A2034, 79, 4))
        self.assertEqual(bank["verification"], "code_verified")
        pointers = list(struct.unpack_from("<79I", self.rom, 0x5A2034))
        self.assertEqual([entry["text_ptr"] for entry in bank["entries"]], pointers)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x98624)[0], 0x085A2034)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x99D58)[0], 0x085A2034)

    def test_visual_variant_matrix_uses_consumer_dimensions(self):
        bank = json.loads((ROOT / "sequel/content/menu-ui/bank.json").read_text())
        self.assertEqual((bank["table_offset"], bank["entry_count"], bank["entry_size"]),
                         (0x5A4DEC, 63, 0x28))
        self.assertEqual(bank["verification"], "code_verified")
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x96164)[0], 0x085A4DEC)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x9614C)[0], 0x085A4DE4)
        for record_index, entry in enumerate(bank["entries"]):
            values = struct.unpack_from("<10I", self.rom, 0x5A4DEC + record_index * 0x28)
            for variant in range(5):
                self.assertEqual(entry[f"gfx_ptr_{variant}"], values[variant * 2])
                self.assertEqual(entry[f"palette_ptr_{variant}"], values[variant * 2 + 1])
                if values[variant * 2]:
                    self.assertEqual(self.rom[values[variant * 2] - 0x08000000], 0x10)
        self.assertEqual(bank["special_variant_5"], {
            "gfx_ptr": struct.unpack_from("<I", self.rom, 0x5A4DE4)[0],
            "palette_ptr": struct.unpack_from("<I", self.rom, 0x5A4DE8)[0],
        })

    def test_battle_visual_descriptor_table_has_seventy_nine_records(self):
        bank = json.loads((ROOT / "sequel/content/tile-assets/bank.json").read_text())
        self.assertEqual((bank["table_offset"], bank["entry_count"], bank["entry_size"]),
                         (0x5A320C, 79, 0x44))
        self.assertEqual(bank["verification"], "code_verified")
        self.assertEqual(len(bank["entries"]), 79)
        self.assertEqual(sum(all(entry[f"word_{i:02d}"] == 0 for i in range(17))
                             for entry in bank["entries"]), 4)
        for literal in (0x87E30, 0x9851C, 0x98840, 0x98AF0, 0x98DB0,
                        0x98FC0, 0x99464, 0x99698, 0x99D10):
            self.assertEqual(struct.unpack_from("<I", self.rom, literal)[0], 0x085A320C)
        self.assertEqual(bank["entry_count"],
                         json.loads((ROOT / "sequel/content/data-table-b/bank.json").read_text())["entry_count"])

    def test_all_four_legacy_tail_shapes_are_diagnostic_only(self):
        cases = (
            ("rom_data_table_a", "data_ptr", 0x5A14A4, generate_data_table_a_patches,
             "db_data_table_a_unmapped"),
            ("rom_data_table_b", "data_ptr", 0x5A2120, generate_data_table_b_patches,
             "db_data_table_b_unmapped"),
            ("rom_menu_ui", "ui_ptr", 0x5A5774, generate_menu_ui_patches,
             "db_menu_ui_unmapped"),
            ("rom_tile_assets", "tile_ptr", 0x5A3218, generate_tile_asset_patches,
             "db_tile_asset_unmapped"),
        )
        for table, column, offset, generator, expected in cases:
            with self.subTest(table=table), tempfile.TemporaryDirectory() as tmp:
                db = Path(tmp) / "editor.db"
                conn = sqlite3.connect(db)
                conn.execute(f'CREATE TABLE "{table}" '
                             f'(_idx INTEGER, _rom_offset INTEGER, "{column}" INTEGER)')
                conn.execute(f'INSERT INTO "{table}" VALUES (0, ?, 0x0812F5B0)', (offset,))
                conn.commit(); conn.close()
                patches = generator(db)
                self.assertEqual(len(patches), 1)
                self.assertEqual(patches[0]["type"], expected)
                self.assertFalse(any(patch["type"] == "bytes" for patch in patches))


if __name__ == "__main__":
    unittest.main()
