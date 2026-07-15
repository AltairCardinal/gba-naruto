import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_map_event_patches


ROOT = Path(__file__).resolve().parents[1]


class MapEventIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads((ROOT / "sequel/content/map-events/bank.json").read_text())

    def test_bank_is_full_256_handler_pair_table(self):
        self.assertEqual(self.bank["table_offset"], 0x53E698)
        self.assertEqual(self.bank["entry_count"], 256)
        self.assertEqual(self.bank["entry_size"], 8)
        self.assertEqual(self.bank["verification"], "code_verified")
        for index, entry in enumerate(self.bank["entries"]):
            pair = struct.unpack_from("<II", self.rom, 0x53E698 + index * 8)
            self.assertEqual((entry["primary_handler_ptr"],
                              entry["secondary_handler_ptr"]), pair)
            for pointer in pair:
                self.assertTrue(pointer == 0 or (0x08000001 <= pointer <= 0x085FFFFF and pointer & 1))

    def test_consumer_indexes_both_halves_with_runtime_state_byte(self):
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x7FA38)[0], 0x0853E698)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x7FA3C)[0], 0x0853E69C)
        self.assertEqual(self.rom[0x7F934:0x7F94E].hex(),
                         "4049ee20c00048440078c00040180168002902d048461cf0e3fb")
        self.assertEqual(self.rom[0x7F94E:0x7F968].hex(),
                         "ee20c00048440078c000384a80180168002902d048461cf0d6fb")

    def test_legacy_47_map_rows_are_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "editor.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE rom_map_events "
                "(_idx INTEGER, _rom_offset INTEGER, handler_ptr INTEGER)"
            )
            conn.execute(
                "INSERT INTO rom_map_events VALUES (0, 0x53EB08, 0x0807EAF9)"
            )
            conn.commit()
            conn.close()
            patches = generate_map_event_patches(db)
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0]["type"], "db_map_event_unmapped")
            self.assertFalse(any(patch["type"] == "bytes" for patch in patches))


if __name__ == "__main__":
    unittest.main()
