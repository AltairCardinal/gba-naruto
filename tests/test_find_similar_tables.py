import unittest

from tools.find_similar_tables import is_rom_ptr


class FindSimilarTablesTests(unittest.TestCase):
    def test_recognizes_only_addresses_inside_the_mapped_rom(self):
        self.assertTrue(is_rom_ptr(0x08000000, 0x100))
        self.assertTrue(is_rom_ptr(0x080000FF, 0x100))
        self.assertFalse(is_rom_ptr(0x07FFFFFF, 0x100))
        self.assertFalse(is_rom_ptr(0x08000100, 0x100))


if __name__ == "__main__":
    unittest.main()
