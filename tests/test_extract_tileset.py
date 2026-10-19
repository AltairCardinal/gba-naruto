import struct
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

from extract_tileset import (
    analyze_map_resource_semantics,
    extract_entry,
    lz77_decompress,
    read_map_entries,
)


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
        self.assertEqual(entry['bg_palette_ptr'], 0x11AD5C)
        self.assertEqual(entry['primary_layout_ptr'], 0x11AE00)
        self.assertIsNone(entry['alternate_layout_ptr'])
        self.assertEqual(entry['metatile_attributes_ptr'], 0x11AFF4)
        self.assertEqual(entry['collision_grid_ptr'], 0x11B498)

        bank = json.loads((ROOT / 'sequel/content/maps/bank.json').read_text())
        self.assertEqual(bank['verification'], 'runtime_verified')
        self.assertEqual(bank['runtime_sample']['map_id'], 41)
        self.assertTrue(all(bank['runtime_sample']['resource_checks'].values()))

    def test_map_40_palette_comes_from_loader_field_plus_8(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = extract_entry(
                self.rom, read_map_entries(self.rom)[40], Path(tmp),
                use_palette=True, scale=1,
            )
            self.assertIn('bg_palette_ptr', result['palette_source'])
            self.assertIn('384 bytes', result['palette_source'])

    def test_map_40_resource_sizes_match_loader_destinations(self):
        analysis = analyze_map_resource_semantics(self.rom, read_map_entries(self.rom)[40])
        self.assertEqual(analysis['coarse_grid_cells'], 198)
        self.assertEqual(analysis['tile_gfx'], {
            'header_offset': 4, 'decompressed_size': 12288,
            'destination': '0x06000000 + buffer_index*0x4000',
        })
        self.assertEqual(analysis['bg_palette'], {
            'header_offset': 8, 'decompressed_size': 384,
            'destination': '0x05000000',
        })
        self.assertEqual(analysis['primary_layout'], {
            'header_offset': 12, 'decompressed_size': 792,
            'destination': '0x0201BE2C', 'bytes_per_coarse_cell': 4,
        })
        self.assertIsNone(analysis['alternate_layout'])
        self.assertEqual(analysis['metatile_attributes']['destination'], '0x0201DE2C')
        self.assertEqual(analysis['metatile_attributes']['decompressed_size'], 1376)
        self.assertEqual(analysis['collision_grid'], {
            'header_offset': 24, 'decompressed_size': 396,
            'destination': '0x02021E2C', 'bytes_per_coarse_cell': 2,
        })

    def test_every_layout_and_collision_stream_matches_coarse_grid(self):
        for entry in read_map_entries(self.rom):
            analysis = analyze_map_resource_semantics(self.rom, entry)
            cells = analysis['coarse_grid_cells']
            self.assertEqual(analysis['primary_layout']['decompressed_size'], cells * 4)
            if analysis['alternate_layout'] is not None:
                self.assertEqual(analysis['alternate_layout']['decompressed_size'], cells * 4)
            self.assertEqual(analysis['collision_grid']['decompressed_size'], cells * 2)

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
