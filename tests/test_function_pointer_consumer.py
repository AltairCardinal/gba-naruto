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
        """2026-10-22 merge: the table is framed as 13 slots now.

        The bank used to store the 11 code pointers only (from 0x53D5F4).
        The consumer scan then framed the whole table as 13 u32 slots
        starting at the sentinel base 0x53D5F0: slots 0 and 12 are
        0xFFFFFFFF sentinels and slots 1..11 are the code pointers.
        The runtime evidence below is unchanged -- it was always taken
        against the sentinel base.
        """
        self.assertEqual(self.bank["table_offset"], 0x53D5F0)
        self.assertEqual(self.bank["entry_count"], 13)
        self.assertEqual(self.bank["entry_size"], 4)
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x53D5F0)[0], 0xFFFFFFFF)
        # slot 12 is the trailing sentinel (0x53D5F0 + 12*4); the table
        # ends at 0x53D5F0 + 13*4 = 0x53D624
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x53D620)[0], 0xFFFFFFFF)
        slots = [struct.unpack_from("<I", self.rom, 0x53D5F0 + index * 4)[0]
                 for index in range(13)]
        self.assertEqual(slots, [entry["slot_value"] for entry in self.bank["entries"]])
        self.assertEqual(self.rom[0x61DD4:0x61DDE].hex(), "094ba000c01800680860")
        self.assertEqual(struct.unpack_from("<I", self.rom, 0x61DFC)[0], 0x0853D5F0)
        self.assertEqual(self.bank["verification"], "runtime_verified")
        self.assertIn("natural cold-load profile route hit callback ID 2", self.bank["verification_method"])
        evidence = json.loads(
            (ROOT / "artifacts/runtime-checkpoints/function-pointer-runtime-evidence.json").read_text()
        )
        self.assertEqual(evidence["control"]["callback_2_entry"], "0x0853D5F8")
        self.assertEqual(evidence["control"]["callback_2_selected_pointer"], "0x08061C99")
        self.assertEqual(evidence["single_factor_patch"]["size"], 4)
        self.assertEqual(self.bank["consumer"]["callback_load"], "0x08061DD4..0x08061DDC")

    def test_wrappers_encode_one_based_callback_ids(self):
        for index, entry in enumerate(self.bank["entries"][1:12], 1):
            target = (entry["slot_value"] - 0x08000000) & ~1
            self.assertEqual(self.rom[target:target + 4], bytes((0x00, 0xB5, index, 0x20)))


if __name__ == "__main__":
    unittest.main()
