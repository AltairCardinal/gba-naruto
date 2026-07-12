import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

from extract_tileset import extract_entry, lz77_decompress, read_map_entries


class ExtractTilesetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / 'rom/base.gba').read_bytes()

    def test_map_40_header_matches_runtime_dimensions_and_bank(self):
        entries = read_map_entries(self.rom)
        self.assertEqual(len(entries), 47)
        entry = entries[40]
        self.assertEqual((entry['width_tiles'], entry['height_tiles']), (36, 44))
        self.assertEqual(entry['tile_gfx_ptr'], 0x118620)
        self.assertEqual(entry['palette_ptr'], 0x11AFF4)

    def test_lz77_rejects_non_lz_pointer(self):
        with self.assertRaises(ValueError):
            lz77_decompress(b'\x00' * 8, 0)

    def test_map_40_exports_valid_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = extract_entry(self.rom, read_map_entries(self.rom)[40], Path(tmp), use_palette=False, scale=1)
            png = Path(result['png']).read_bytes()
            self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
            width, height = struct.unpack('>II', png[16:24])
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            self.assertGreater(result['num_tiles'], 0)
            self.assertEqual(len(result['tile_data_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
