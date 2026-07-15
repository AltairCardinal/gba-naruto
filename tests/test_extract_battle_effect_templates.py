import unittest

from tools.extract_battle_effect_templates import ENTRY_COUNT, ENTRY_SIZE, TABLE_OFFSET, build_bank


class BattleEffectTemplateExtractionTests(unittest.TestCase):
    def test_extracts_lossless_byte_level_records(self):
        rom = bytearray(TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE)
        for index in range(ENTRY_COUNT):
            start = TABLE_OFFSET + index * ENTRY_SIZE
            rom[start:start + ENTRY_SIZE] = bytes((index + n) & 0xFF for n in range(ENTRY_SIZE))
        bank = build_bank(bytes(rom))
        self.assertEqual("runtime_verified", bank["verification"])
        self.assertEqual(ENTRY_COUNT, len(bank["entries"]))
        self.assertEqual(bytes(rom[TABLE_OFFSET:TABLE_OFFSET + ENTRY_SIZE]).hex(), bank["entries"][0]["raw_hex"])
        self.assertEqual(int.from_bytes(rom[TABLE_OFFSET + 14:TABLE_OFFSET + 16], "little"), bank["entries"][0]["per_level_growth"])


if __name__ == "__main__":
    unittest.main()
