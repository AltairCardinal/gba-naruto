import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_font_patches, generate_resource_pointer_patches


ROOT = Path(__file__).resolve().parents[1]


class RemainingStaticIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()

    def test_false_font_bank_is_empty_tombstone(self):
        bank = json.loads((ROOT / "sequel/content/fonts/bank.json").read_text())
        self.assertEqual(bank["verification"], "disproved")
        self.assertEqual(bank["entry_count"], 0)
        self.assertEqual(bank["entries"], [])
        self.assertTrue(bank["do_not_write"])
        self.assertEqual(bank["superseded_by"],
                         "notes/dialogue-font-table-discovery-20260703.md")
        self.assertGreater(0x53E5B4 + 256, 0x53E698)

    def test_levels_slug_is_forty_five_effect_progression_records(self):
        bank = json.loads((ROOT / "sequel/content/levels/bank.json").read_text())
        self.assertEqual(bank["table_offset"], 0x5459C8)
        self.assertEqual(bank["entry_count"], 45)
        self.assertEqual(bank["entry_size"], 12)
        self.assertEqual(bank["verification"], "code_verified")
        for index, entry in enumerate(bank["entries"]):
            self.assertEqual(
                (entry["target_type"], entry["reserved1"], entry["base_a"],
                 entry["base_b"], entry["per_level_a"], entry["per_level_b"],
                 entry["reserved_a"]),
                struct.unpack_from("<BBHHHHH", self.rom, 0x5459C8 + index * 12),
            )
        for literal in (0x6D708, 0x6D7B0, 0x6DB44, 0x6DC74, 0x6DE00, 0x93304):
            self.assertEqual(struct.unpack_from("<I", self.rom, literal)[0], 0x085459C8)
        self.assertEqual(0x5459C8 + 45 * 12, 0x545BE4)

    def test_resource_pointer_slug_is_five_four_pointer_descriptors(self):
        bank = json.loads((ROOT / "sequel/content/resource-pointers/bank.json").read_text())
        self.assertEqual(bank["entry_count"], 5)
        self.assertEqual(bank["entry_size"], 16)
        self.assertEqual(bank["verification"], "code_verified")
        for index, entry in enumerate(bank["entries"]):
            self.assertEqual(tuple(entry[f"resource_ptr_{i}"] for i in range(4)),
                             struct.unpack_from("<4I", self.rom, 0x596F0C + index * 16))
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x7B278)[0], 0x08596F0C)
        self.assertEqual(self.rom[0x7B220:0x7B228].hex(), "154800210091141c")

    def test_legacy_font_and_resource_rows_are_diagnostic_only(self):
        cases = (
            ("rom_fonts", "char_width", 0x53E5B4, generate_font_patches,
             "db_font_unmapped"),
            ("rom_resource_pointers", "resource_ptr", 0x596F0C,
             generate_resource_pointer_patches, "db_resource_pointer_unmapped"),
        )
        for table, column, offset, generator, expected in cases:
            with self.subTest(table=table), tempfile.TemporaryDirectory() as tmp:
                db = Path(tmp) / "editor.db"
                conn = sqlite3.connect(db)
                conn.execute(
                    f'CREATE TABLE "{table}" '
                    f'(_idx INTEGER, _rom_offset INTEGER, "{column}" INTEGER)'
                )
                conn.execute(f'INSERT INTO "{table}" VALUES (0, ?, 1)', (offset,))
                conn.commit()
                conn.close()
                patches = generator(db)
                self.assertEqual(len(patches), 1)
                self.assertEqual(patches[0]["type"], expected)
                self.assertFalse(any(patch["type"] == "bytes" for patch in patches))


if __name__ == "__main__":
    unittest.main()
