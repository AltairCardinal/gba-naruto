import unittest

from tools.extract_skill_templates import ENTRY_COUNT, ENTRY_SIZE, TABLE_END, TABLE_OFFSET, build_bank


class SkillTemplateExtractionTests(unittest.TestCase):
    def test_boundaries_and_lossless_records(self):
        self.assertEqual(94, ENTRY_COUNT)
        self.assertEqual(TABLE_END, TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE)
        rom = bytearray(TABLE_END)
        for index in range(ENTRY_COUNT):
            start = TABLE_OFFSET + index * ENTRY_SIZE
            rom[start:start + ENTRY_SIZE] = bytes((index + n) & 0xFF for n in range(ENTRY_SIZE))
        bank = build_bank(bytes(rom))
        self.assertEqual("code_verified", bank["verification"])
        self.assertEqual(bytes(rom[TABLE_OFFSET:TABLE_OFFSET + 16]).hex(), bank["entries"][0]["raw_hex"])
        self.assertEqual(TABLE_END - ENTRY_SIZE, bank["entries"][-1]["_raw_offset"])


if __name__ == "__main__":
    unittest.main()
