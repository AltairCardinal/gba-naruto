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

    def test_font_width_bank_is_the_proved_table_not_the_legacy_window(self):
        """2026-10-22 merge: the font-width table got its real base.

        The old claim was "there is no font bank" -- the candidate base
        0x53E5B4 has no native reader.  The consumer scan then found the
        real table 30 bytes earlier at 0x53E596 (256 one-byte widths,
        unique native reader 0x0807F0FC), and the bank now carries it.
        The legacy base 0x53E5B4 is still refused by the writer.
        """
        bank = json.loads((ROOT / "sequel/content/fonts/bank.json").read_text())
        self.assertEqual(bank["table_offset"], 0x53E596)
        self.assertEqual(bank["entry_count"], 256)
        self.assertEqual(bank["entry_size"], 1)
        self.assertEqual(bank["verification"], "code_verified")
        for index, entry in enumerate(bank["entries"]):
            self.assertEqual(
                entry["char_width"], self.rom[0x53E596 + index])
        # The legacy base stays on record as a zero-reader window.
        from tools import table_registry
        self.assertIn("0x53e5b4", table_registry.CONFLICTS)
        self.assertEqual(
            "repoint", table_registry.CONFLICTS["0x53e5b4"]["verdict"])
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
        """Legacy rows must never become ROM bytes.

        2026-10-22 merge: the font writer now targets the proved base
        0x53E596, so a row still pointing at the legacy 0x53E5B4 is
        rejected by the writer's own ``_rom_offset`` guard and reported as
        ``db_font_error`` instead of the old ``db_font_unmapped`` marker.
        The invariant that matters -- **no ROM byte is written to a
        falsified base** -- is asserted for both cases.
        """
        cases = (
            ("rom_fonts", "char_width", 0x53E5B4, generate_font_patches,
             "db_font_error"),
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
