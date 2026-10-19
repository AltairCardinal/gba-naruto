"""Unsupported ISA encodings must fail at the decoding boundary."""
import unittest
from tools import rom_small_cfg_wrappers_producer as producer


class DecodeGates(unittest.TestCase):
    def test_reserved_condition_is_not_a_direct_producer(self):
        self.assertEqual(producer.scan_producers(bytes.fromhex('00de00df00000000'), [4, 6]), [])

    def test_unsupported_and_undefined_encodings_raise_value_error(self):
        for value in (0xB100, 0xB650, 0xBA00, 0xDE00, 0xB400, 0xBC00):
            with self.subTest(halfword=hex(value)):
                with self.assertRaises(ValueError):
                    producer._decode_instruction(value.to_bytes(2, 'little'), 0, 2)

    def test_real_linear_instruction_families_remain_supported(self):
        for value in (0xB500, 0x0600, 0x4904, 0x0D80, 0x31C4, 0x1840, 0x6800, 0xBC01):
            with self.subTest(halfword=hex(value)):
                self.assertEqual(producer._decode_instruction(value.to_bytes(2, 'little'), 0, 2),
                                 (2, 'linear', None, None))


if __name__ == '__main__':
    unittest.main()
