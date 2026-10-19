import json
import tempfile
import unittest
from pathlib import Path

from tools.import_dialogue_var import import_dialogue_variable

ROOT = Path(__file__).resolve().parent.parent


class DialogueVariableImportTest(unittest.TestCase):
    def fixture(self, text):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        bank = {
            "entries": [{"id": "x", "offset": 0x100, "text_rom_offset": 0x100,
                         "table_offset": 0x80, "max_bytes": 4,
                         "expected_hex": "41424344", "encoding": "cp932"}]}
        content = {"entries": [{"id": "x", "text": text}]}
        bp, cp = root/'bank.json', root/'content.json'
        bp.write_text(json.dumps(bank)); cp.write_text(json.dumps(content))
        rom = bytearray(b'\x00' * 0x300)
        rom[0x80:0x84] = (0x08000100).to_bytes(4, 'little')
        rom[0x100:0x104] = b'ABCD'
        rom[0x200:0x300] = b'\xFF' * 0x100
        return bp, cp, bytes(rom)

    def test_long_text_allocates_aligned_data_and_redirects_pointer(self):
        bp, cp, rom = self.fixture('ABCDE')
        patches = import_dialogue_variable(bp, cp, 0x200, 0x300, rom=rom)
        self.assertEqual([p['type'] for p in patches], ['bytes', 'pointer_redirect'])
        self.assertEqual(patches[0]['offset'], 0x200)
        self.assertEqual(bytes.fromhex(patches[0]['after_hex']), b'ABCDE\x00')
        self.assertEqual(patches[1]['expected_pointer_hex'], '00010008')
        self.assertEqual(patches[1]['new_pointer_hex'], '00020008')

    def test_short_text_stays_in_place(self):
        bp, cp, rom = self.fixture('XY')
        patches = import_dialogue_variable(bp, cp, 0x200, 0x300, rom=rom)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]['offset'], 0x100)
        self.assertEqual(patches[0]['after_hex'], '58590000')

    def test_pointer_mismatch_non_ff_space_and_overflow_are_rejected(self):
        bp, cp, rom = self.fixture('ABCDE')
        bad_pointer = bytearray(rom); bad_pointer[0x80] ^= 1
        with self.assertRaisesRegex(ValueError, 'base pointer mismatch'):
            import_dialogue_variable(bp, cp, 0x200, 0x300, rom=bytes(bad_pointer))
        bad_space = bytearray(rom); bad_space[0x250] = 0
        with self.assertRaisesRegex(ValueError, 'not entirely 0xFF'):
            import_dialogue_variable(bp, cp, 0x200, 0x300, rom=bytes(bad_space))
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            import_dialogue_variable(bp, cp, 0x200, 0x205, rom=rom)


if __name__ == '__main__':
    unittest.main()
