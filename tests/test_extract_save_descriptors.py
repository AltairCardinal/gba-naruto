import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from extract_save_descriptors import build_bank


class SaveDescriptorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = build_bank((ROOT / "rom/base.gba").read_bytes())

    def test_second_word_is_length_and_offsets_are_cumulative(self):
        entries = self.bank["entries"]
        self.assertEqual(entries[0]["payload_length"], 4732)
        self.assertEqual(entries[1]["sram_record_offset"], 4752)
        self.assertEqual(entries[3]["sram_record_offset"], 9544)
        self.assertEqual(entries[9]["sram_record_offset"], 21936)

    def test_wrapper_groups_cover_variable_length_records(self):
        lengths = [entry["payload_length"] for entry in self.bank["entries"][3:10]]
        self.assertEqual(lengths, [4732, 20, 8, 24, 6084, 1404, 512])
        self.assertEqual(self.bank["verification"], "code_verified")


if __name__ == "__main__":
    unittest.main()
