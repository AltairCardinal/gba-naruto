import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROM_BASE = 0x08000000


class CutsceneVisualResourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads(
            (ROOT / "sequel/content/cutscene-scripts/bank.json").read_text()
        )

    def test_bank_is_eight_resource_pairs_not_sixteen_scripts(self):
        self.assertEqual(self.bank["entry_count"], 8)
        self.assertEqual(self.bank["entry_size"], 8)
        self.assertEqual(self.bank["verification"], "code_verified")
        self.assertEqual(len(self.bank["entries"]), 8)
        for index, entry in enumerate(self.bank["entries"]):
            offset = 0x53DF70 + index * 8
            first, second = struct.unpack_from("<II", self.rom, offset)
            self.assertEqual(entry["primary_ptr"], first)
            self.assertEqual(entry["secondary_ptr"], second)
            self.assertEqual(entry["pair_kind"],
                             "compressed_gfx_palette" if index < 4 else "sprite_definition_animation")

        for entry in self.bank["entries"][:4]:
            for field in ("primary_ptr", "secondary_ptr"):
                target = entry[field] - ROM_BASE
                self.assertEqual(self.rom[target], 0x10)

    def test_code_indexes_both_four_record_tables(self):
        # 0x08072F0C indexes ID*8 from 0x0853DF70, decompressing +0 and +4.
        self.assertEqual(
            self.rom[0x72F0C:0x72F26].hex(),
            "0b4c4046c500281900680a4929f0e6f804342d192868084929f0",
        )
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x72F3C)[0], 0x0853DF70)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x72F40)[0], 0x06016000)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x72F44)[0], 0x05000380)

        # The same routine passes the second four-pair table to the sprite task
        # allocator, whose 0x08062668 path indexes it with ID*8.
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x72FC8)[0], 0x0853DF90)
        self.assertEqual(
            self.rom[0x62668:0x62676].hex(),
            "f800009940180168e16140682062",
        )

    def test_all_direct_callers_supply_only_ids_zero_through_three(self):
        expected = {
            0x73100: "0120fff7ecfe",
            0x7314A: "0220fff7c7fe",
            0x73196: "0320fff7a1fe",
            0x7363A: "0020fff74ffc",
        }
        for call_offset, instruction_hex in expected.items():
            self.assertEqual(self.rom[call_offset - 2:call_offset + 4].hex(), instruction_hex)


if __name__ == "__main__":
    unittest.main()
