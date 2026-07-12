import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_tileset import lz77_decompress, read_map_entries  # noqa: E402
from verify_map_resource_buffers import verify_map_resource_buffers  # noqa: E402


class VerifyMapResourceBuffersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = (ROOT / "rom/base.gba").read_bytes()
        cls.entry = read_map_entries(cls.rom)[40]

    def build_buffers(self):
        ewram = bytearray(0x40000)
        palette_ram = bytearray(0x400)
        vram = bytearray(0x18000)

        def unpack(name):
            return lz77_decompress(self.rom, self.entry[name])

        ewram[0x1BE2C:0x1BE2C + len(unpack("primary_layout_ptr"))] = unpack("primary_layout_ptr")
        ewram[0x1DE2C:0x1DE2C + len(unpack("metatile_attributes_ptr"))] = unpack("metatile_attributes_ptr")
        ewram[0x21E2C:0x21E2C + len(unpack("collision_grid_ptr"))] = unpack("collision_grid_ptr")
        ewram[0x22E2D] = 0
        palette = unpack("bg_palette_ptr")
        palette_ram[:len(palette)] = palette
        gfx = unpack("tile_gfx_ptr")
        vram[:len(gfx)] = gfx
        return bytes(ewram), bytes(palette_ram), bytes(vram)

    def test_row_40_buffers_match_every_loaded_resource(self):
        result = verify_map_resource_buffers(self.rom, 40, *self.build_buffers())
        self.assertTrue(result["verified"])
        self.assertEqual(result["checks"], {
            "tile_gfx": True,
            "bg_palette": True,
            "primary_layout": True,
            "alternate_layout_skipped": True,
            "metatile_attributes": True,
            "collision_grid": True,
        })

    def test_corrupt_collision_byte_is_rejected(self):
        ewram, palette_ram, vram = self.build_buffers()
        damaged = bytearray(ewram)
        damaged[0x21E2C] ^= 1
        result = verify_map_resource_buffers(self.rom, 40, bytes(damaged), palette_ram, vram)
        self.assertFalse(result["verified"])
        self.assertFalse(result["checks"]["collision_grid"])


if __name__ == "__main__":
    unittest.main()
