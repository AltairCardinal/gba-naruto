import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.butano.render_scenario_41_gpu import render_boundary, render_mode0


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "artifacts/scenario-41-reference-v1"


def color(red: int, green: int, blue: int) -> int:
    return red | (green << 5) | (blue << 10)


class Scenario41GpuRenderTests(unittest.TestCase):
    def test_renders_text_background_and_1d_object_pixels(self):
        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        for offset in range(0, len(oam), 8):
            struct.pack_into("<H", oam, offset, 0x0200)

        struct.pack_into("<H", io, 0x00, (1 << 6) | (1 << 8) | (1 << 12))
        struct.pack_into("<H", io, 0x08, 1 << 8)
        struct.pack_into("<H", pram, 0, color(0, 0, 0))
        struct.pack_into("<H", pram, 2, color(31, 0, 0))
        struct.pack_into("<H", pram, 0x200 + 2, color(0, 31, 0))
        struct.pack_into("<H", pram, 0x200 + (16 + 1) * 2, color(0, 0, 31))
        vram[0:32] = bytes([0x11] * 32)
        struct.pack_into("<H", vram, 0x800, 0)
        vram[0x10000:0x10020] = bytes([0x11] * 32)
        struct.pack_into("<HHH", oam, 10 * 8, 0, 0, 0)
        struct.pack_into("<HHH", oam, 11 * 8, 0, 0, 1 << 12)

        rgb = render_mode0(bytes(io), bytes(pram), bytes(oam), bytes(vram))

        self.assertEqual(len(rgb), 240 * 160 * 3)
        self.assertEqual(rgb[0:3], bytes((0, 255, 0)))
        self.assertEqual(rgb[(8 * 3):(8 * 3 + 3)], bytes((255, 0, 0)))

    def test_blends_the_rgb8_palette_values_used_by_mgba_screenshots(self):
        io = bytearray(0x400)
        pram = bytearray(0x400)
        oam = bytearray(0x400)
        vram = bytearray(0x18000)
        for offset in range(0, len(oam), 8):
            struct.pack_into("<H", oam, offset, 0x0200)
        struct.pack_into("<H", io, 0x00, (1 << 8) | (1 << 10))
        struct.pack_into("<H", io, 0x08, 1 | (2 << 8))
        struct.pack_into("<H", io, 0x0C, (1 << 2) | (3 << 8))
        struct.pack_into("<H", io, 0x50, (1 << 6) | (1 << 2) | (1 << 8))
        struct.pack_into("<H", io, 0x52, 10 | (10 << 8))
        struct.pack_into("<H", pram, 17 * 2, color(10, 0, 0))
        struct.pack_into("<H", pram, 33 * 2, color(31, 0, 0))
        vram[0:32] = bytes([0x11] * 32)
        vram[0x4000:0x4020] = bytes([0x11] * 32)
        struct.pack_into("<H", vram, 2 * 0x800, 1 << 12)
        struct.pack_into("<H", vram, 3 * 0x800, 2 << 12)

        rgb = render_mode0(bytes(io), bytes(pram), bytes(oam), bytes(vram))

        self.assertEqual(rgb[0:3], bytes((210, 0, 0)))

    def test_reconstructs_all_six_golden_frames(self):
        manifest = json.loads((REFERENCE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["boundaries"]), 6)
        for name, boundary in manifest["boundaries"].items():
            with self.subTest(boundary=name):
                rgb = render_boundary(REFERENCE / name)
                self.assertEqual(
                    hashlib.sha256(rgb).hexdigest(),
                    boundary["screen"]["rgb_pixels_sha256"],
                )


if __name__ == "__main__":
    unittest.main()
