from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildWorldMapPage0PixelAbTests(unittest.TestCase):
    def test_builds_one_page0_graphics_pixel_production_relocation(self):
        from tools.build_world_map_page0_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "build"
            manifest = build_pair(ROOT, output)

            self.assertEqual("world-map-page0-pixel-ab-build-v1", manifest["schema"])
            self.assertEqual(
                {
                    "page_id": 0,
                    "resource_type": "graphics",
                    "table_pointer_offset": 0x5A8014,
                    "canvas_xy": [116, 76],
                    "tile_id": 243,
                    "graphics_byte_offset": 15588,
                    "before_index": 112,
                    "after_index": 137,
                },
                manifest["edit"],
            )
            self.assertEqual(
                [15588], manifest["isolation"]["decoded_graphics_offsets"]
            )
            baseline = manifest["variants"]["baseline"]
            candidate = manifest["variants"]["candidate"]
            self.assertEqual(0xB71000, baseline["patch_ledger"][0]["offset"])
            self.assertEqual(0xB71000, candidate["patch_ledger"][0]["offset"])
            self.assertEqual(0x5A8014, baseline["patch_ledger"][1]["offset"])
            self.assertEqual(0x08B71000, baseline["patch_ledger"][1]["new_pointer"])
            self.assertEqual(
                baseline["patch_ledger"][1]["after_hex"],
                candidate["patch_ledger"][1]["after_hex"],
            )
            self.assertEqual(0x1000000, baseline["rom_size"])
            self.assertEqual(0x1000000, candidate["rom_size"])

    def test_rejects_a_nonempty_output_directory(self):
        from tools.build_world_map_page0_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "build"
            output.mkdir()
            (output / "keep.txt").write_text("do not overwrite", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                build_pair(ROOT, output)


if __name__ == "__main__":
    unittest.main()
