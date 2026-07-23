import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.butano.analyze_scenario_41_gpu import analyze_boundary, decode_gpu


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "artifacts/scenario-41-reference-v1"


class Scenario41GpuAnalysisTests(unittest.TestCase):
    def test_decodes_display_layers_windows_blend_and_active_oam(self):
        io = bytearray(0x400)
        oam = bytearray(0x400)
        for offset in range(0, len(oam), 8):
            struct.pack_into("<H", oam, offset, 0x0200)

        struct.pack_into("<H", io, 0x00, 0 | (1 << 8) | (1 << 10) | (1 << 12) | (1 << 13))
        struct.pack_into("<H", io, 0x08, 1 | (2 << 2) | (1 << 7) | (3 << 8) | (1 << 14))
        struct.pack_into("<H", io, 0x0C, 2 | (1 << 2) | (7 << 8) | (2 << 14))
        struct.pack_into("<HH", io, 0x10, 17, 29)
        struct.pack_into("<HH", io, 0x20, 0x0100, 0xFF00)
        struct.pack_into("<HHHH", io, 0x40, 0x0A64, 0, 0x1496, 0)
        struct.pack_into("<HH", io, 0x48, 0x1234, 0x5678)
        struct.pack_into("<HHH", io, 0x50, 0x0C41, 0x080C, 7)

        struct.pack_into("<HHH", oam, 0, 20, 12 | (1 << 12) | (1 << 14), 33 | (2 << 10) | (5 << 12))
        struct.pack_into("<HHH", oam, 8, 40 | (1 << 8) | (1 << 14), 300 | (3 << 9) | (2 << 14), 9)

        decoded = decode_gpu(bytes(io), bytes(oam))

        self.assertEqual(decoded["display"]["mode"], 0)
        self.assertEqual(decoded["display"]["enabled_backgrounds"], [0, 2])
        self.assertTrue(decoded["display"]["obj_enabled"])
        self.assertTrue(decoded["display"]["windows"]["win0_enabled"])
        bg0 = decoded["backgrounds"]["0"]
        self.assertEqual(bg0["priority"], 1)
        self.assertEqual(bg0["character_base"], "0x06008000")
        self.assertEqual(bg0["screen_base"], "0x06001800")
        self.assertEqual(bg0["dimensions"], [512, 256])
        self.assertEqual(bg0["scroll"], {"x": 17, "y": 29})
        self.assertEqual(decoded["windows"]["win0"], {"left": 10, "right": 100, "top": 20, "bottom": 150})
        self.assertEqual(decoded["blend"]["eva"], 12)
        self.assertEqual(decoded["blend"]["evb"], 8)
        self.assertEqual(decoded["blend"]["evy"], 7)

        self.assertEqual(len(decoded["objects"]), 2)
        first = decoded["objects"][0]
        self.assertEqual(first["position"], {"x": 12, "y": 20, "raw_x": 12, "raw_y": 20})
        self.assertEqual(first["dimensions"], [16, 16])
        self.assertEqual(first["tile_index"], 33)
        self.assertEqual(first["priority"], 2)
        self.assertEqual(first["palette_bank"], 5)
        self.assertTrue(first["horizontal_flip"])
        second = decoded["objects"][1]
        self.assertTrue(second["affine"])
        self.assertEqual(second["affine_parameter_index"], 3)
        self.assertEqual(second["dimensions"], [32, 16])
        self.assertEqual(second["position"]["x"], -212)

    def test_rejects_reserved_display_mode_and_wrong_region_sizes(self):
        io = bytearray(0x400)
        oam = bytes(0x400)
        struct.pack_into("<H", io, 0, 6)
        with self.assertRaisesRegex(ValueError, "display mode"):
            decode_gpu(bytes(io), oam)
        with self.assertRaisesRegex(ValueError, "I/O region"):
            decode_gpu(bytes(4), oam)
        with self.assertRaisesRegex(ValueError, "OAM region"):
            decode_gpu(bytes(0x400), bytes(4))

    def test_analyzes_real_reference_deterministically(self):
        boundary = REFERENCE / "first-turn-technique-menu"
        first = analyze_boundary(boundary)
        second = analyze_boundary(boundary)

        self.assertEqual(first, second)
        self.assertEqual(
            first["screen"]["rgb_pixels_sha256"],
            "17644dae174acd0e26b9b004f3e8a03b9fd9a43b523cb3dff40f978b4f9b6eef",
        )
        self.assertTrue(first["display"]["enabled_backgrounds"])
        self.assertTrue(first["objects"])
        self.assertEqual(
            json.dumps(first, indent=2, sort_keys=True),
            json.dumps(second, indent=2, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
