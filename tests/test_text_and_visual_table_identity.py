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
        self.assertEqual(bank["verification"], "runtime_verified")
        self.assertEqual(bank["runtime_sample"]["character_id"], 0)
        self.assertEqual(bank["runtime_sample"]["control_text_ptr"], 0x0859F988)
        self.assertEqual(bank["runtime_sample"]["variant_text_ptr"], 0x0859FDE8)
        pointers = list(struct.unpack_from("<46I", self.rom, 0x5A143C))
        self.assertEqual([entry["text_ptr"] for entry in bank["entries"]], pointers)
        for pointer in pointers:
            offset = pointer - 0x08000000
            self.assertNotEqual(self.rom.find(b"\0", offset, 0x5A143C), -1)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x8A704)[0], 0x085A143C)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x8B214)[0], 0x085A143C)

    def test_battle_message_table_has_all_seventy_nine_pointer_entries(self):
        """2026-10-22 merge: the table has 90 slots, 79 of which are pointers.

        The consumer scan re-based this table from the legacy 0x5A2120 (59
        entries late) to the real 0x5A2034 and extended it to 90 u32 slots.
        79 of those slots hold a ROM pointer; the remaining 11 are other
        u32 values.  The pointer rows are still the 79 the old assertion
        pinned, so the "seventy-nine" contract survives the re-base.
        """
        bank = json.loads((ROOT / "sequel/content/data-table-b/bank.json").read_text())
        self.assertEqual((bank["table_offset"], bank["entry_count"], bank["entry_size"]),
                         (0x5A2034, 90, 4))
        self.assertEqual(bank["verification"], "code_verified")
        pointer_entries = [entry for entry in bank["entries"]
                           if entry.get("rom_ptr")
                           and 0x08000000 <= entry["rom_ptr"] <= 0x09000000]
        self.assertEqual(len(pointer_entries), 79)
        raw = struct.unpack_from("<90I", self.rom, 0x5A2034)
        for entry in pointer_entries:
            self.assertEqual(entry["rom_ptr"], raw[entry["_index"]])
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x98624)[0], 0x085A2034)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x99D58)[0], 0x085A2034)

    def test_visual_variant_matrix_uses_consumer_dimensions(self):
        bank = json.loads((ROOT / "sequel/content/menu-ui/bank.json").read_text())
        self.assertEqual((bank["table_offset"], bank["entry_count"], bank["entry_size"]),
                         (0x5A4DEC, 63, 0x28))
        self.assertEqual(bank["verification"], "runtime_verified")
        self.assertEqual(bank["runtime_sample"]["record_id"], 7)
        self.assertEqual(bank["runtime_sample"]["variant"], 0)
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
        # 2026-10-22 merge: the data-table-b re-base extended that table to
        # 90 slots, so the old cross-table equality with this one (79 == 79)
        # no longer holds -- and it never meant anything: the two tables
        # have unrelated structures.  Each table is asserted on its own.

    def test_all_four_legacy_tail_shapes_are_diagnostic_only(self):
        # 2026-10-22 merge: the writers now target the **adjudicated** bases
        # (0x5A143C / 0x5A2034 / 0x5A4DEC / 0x5A320C), so a row still on a
        # legacy base is rejected by the writer's own stale-offset / missing
        # column guard and reported through the uniform
        # ``db_pointer_table_error`` code.  The invariant is unchanged:
        # **no ROM byte is written to a falsified base**.
        cases = (
            ("rom_data_table_a", "data_ptr", 0x5A14A4, generate_data_table_a_patches,
             "db_pointer_table_error"),
            ("rom_data_table_b", "data_ptr", 0x5A2120, generate_data_table_b_patches,
             "db_pointer_table_error"),
            ("rom_menu_ui", "ui_ptr", 0x5A5774, generate_menu_ui_patches,
             "db_pointer_table_error"),
            ("rom_tile_assets", "tile_ptr", 0x5A3218, generate_tile_asset_patches,
             "db_pointer_table_error"),
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
