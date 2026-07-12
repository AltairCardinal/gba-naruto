import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FunctionPointerConsumerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.bank = json.loads((ROOT / "sequel/content/function-pointers/bank.json").read_text())

    def test_sentinel_table_and_consumer_are_recorded(self):
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x53D5F0)[0], 0xFFFFFFFF)
        pointers = [struct.unpack_from("<I", self.rom, 0x53D5F4 + index * 4)[0] for index in range(11)]
        self.assertEqual(pointers, [entry["func_ptr"] for entry in self.bank["entries"]])
        self.assertEqual(self.rom[0x61DD4:0x61DDE].hex(), "094ba000c01800680860")
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x61DFC)[0], 0x0853D5F0)
        self.assertEqual(self.bank["verification"], "code_verified")
        self.assertEqual(self.bank["consumer"]["callback_load"], "0x08061DD4..0x08061DDC")

    def test_wrappers_encode_one_based_callback_ids(self):
        for index, entry in enumerate(self.bank["entries"], 1):
            target = (entry["func_ptr"] - 0x08000000) & ~1
            self.assertEqual(self.rom[target:target + 4], bytes((0x00, 0xB5, index, 0x20)))


if __name__ == "__main__":
    unittest.main()
