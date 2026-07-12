import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from tools.build_db_patches import generate_battle_encounter_patches


ROOT = Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000


class BattleEncounterIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads(
            (ROOT / "sequel/content/battle-encounters/bank.json").read_text()
        )

    def test_bank_is_twenty_four_visual_resource_descriptors(self):
        self.assertEqual(self.bank["table_offset"], 0x54229C)
        self.assertEqual(self.bank["entry_count"], 24)
        self.assertEqual(self.bank["entry_size"], 0x10)
        self.assertEqual(self.bank["verification"], "code_verified")
        for index, entry in enumerate(self.bank["entries"]):
            values = struct.unpack_from("<IIII", self.rom, 0x54229C + index * 0x10)
            self.assertEqual(
                (entry["gfx_lz_ptr"], entry["palette_lz_ptr"],
                 entry["tilemap_lz_ptr"], entry["config_id"]),
                values,
            )
            for pointer in values[:3]:
                self.assertEqual(self.rom[pointer - ROM_BASE], 0x10)

    def test_consumer_indexes_descriptor_and_loads_all_three_streams(self):
        # Literal pool identities used by the loop in 0x08087DDC..0x08087EB8.
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x87E24)[0], 0x0854229C)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x87E2C)[0], 0x085422A8)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x87EF8)[0], 0x085422A4)
        self.assertEqual(struct.unpack_from("<III", self.rom, 0x87EF0),
                         (0x0600E800, 0x050001E0, 0x085422A4))
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x87EFC)[0], 0x06001800)
        self.assertEqual(self.rom[0x87EAC:0x87EB0].hex(), "172f03d1")

    def test_story_opcode_reaches_the_resource_loader(self):
        self.assertEqual(self.rom[0x8FA2C:0x8FA32].hex(), "faf736fe5be7")
        self.assertEqual(self.rom[0x8A69C:0x8A6A4].hex(), "00b5fdf7fdfa0020")

    def test_legacy_encounter_rows_are_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "editor.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE rom_battle_encounters "
                "(_idx INTEGER, _rom_offset INTEGER, entry INTEGER)"
            )
            conn.execute(
                "INSERT INTO rom_battle_encounters VALUES (0, 0x542384, ?)",
                (0x08138F74,),
            )
            conn.commit()
            conn.close()
            patches = generate_battle_encounter_patches(db)
            self.assertEqual(len(patches), 1)
            self.assertEqual(patches[0]["type"], "db_battle_encounter_unmapped")
            self.assertFalse(any(patch["type"] == "bytes" for patch in patches))


if __name__ == "__main__":
    unittest.main()
