import struct
import unittest

from tools.extract_audio_command_table import ENTRY_COUNT, TABLE_OFFSET, build_bank


class AudioCommandTableExtractionTests(unittest.TestCase):
    def test_extracts_100_pointer_entries_and_labels(self):
        target = TABLE_OFFSET + ENTRY_COUNT * 4
        rom = bytearray(target + ENTRY_COUNT * 8)
        for index in range(ENTRY_COUNT):
            label_offset = target + index * 8
            struct.pack_into("<I", rom, TABLE_OFFSET + index * 4, 0x08000000 + label_offset)
            rom[label_offset:label_offset + 3] = b"A\0\0"
        bank = build_bank(bytes(rom))
        self.assertEqual("code_verified", bank["verification"])
        self.assertEqual(100, len(bank["entries"]))
        self.assertEqual(0x80, bank["entries"][0]["command_id"])
        self.assertEqual("A", bank["entries"][0]["diagnostic_cp932"])


if __name__ == "__main__":
    unittest.main()
