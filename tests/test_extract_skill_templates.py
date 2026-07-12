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

        fields = {field["offset"]: field for field in bank["entry_format"]["fields"]}
        self.assertEqual(fields[0]["initializer_destination"], 1)
        self.assertIsNone(fields[1]["initializer_destination"])
        for offset in range(2, 10):
            self.assertEqual(fields[offset]["initializer_destination"], offset)
        self.assertEqual(fields[10]["separate_consumer"], "0x0808FF7C")
        self.assertEqual(fields[11]["separate_consumer"], "0x0808FF88")


if __name__ == "__main__":
    unittest.main()
