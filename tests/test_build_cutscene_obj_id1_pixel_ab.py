from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildCutsceneObjId1PixelAbTests(unittest.TestCase):
    def test_builds_one_id1_graphics_pixel_with_stable_bundle_topology(self):
        from tools.build_cutscene_obj_id1_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "build"
            manifest = build_pair(ROOT, output)

            self.assertEqual(
                "cutscene-obj-id1-pixel-ab-build-v1", manifest["schema"]
            )
            self.assertEqual(
                {
                    "resource_id": 1,
                    "frame_id": 0,
                    "graphics_byte_offset": 82,
                    "tile_id": 2,
                    "tile_pixel_xy": [4, 4],
                    "frame_pixel_xy": [20, 4],
                    "before_byte": 0x11,
                    "after_byte": 0x12,
                    "before_index": 1,
                    "after_index": 2,
                    "screen_xy": [60, 52],
                },
                manifest["edit"],
            )
            self.assertEqual(
                [82], manifest["isolation"]["decoded_graphics_offsets"]
            )
            self.assertTrue(manifest["isolation"]["same_patch_topology"])
            self.assertTrue(manifest["isolation"]["same_allocation_offsets"])
            self.assertTrue(manifest["isolation"]["same_redirect_pointers"])
            self.assertEqual(
                manifest["variants"]["baseline"]["encoded_graphics_size"],
                manifest["variants"]["candidate"]["encoded_graphics_size"],
            )
            self.assertEqual(
                0x1000000, manifest["variants"]["baseline"]["rom_size"]
            )
            self.assertEqual(
                0x1000000, manifest["variants"]["candidate"]["rom_size"]
            )

    def test_rejects_a_nonempty_output_directory(self):
        from tools.build_cutscene_obj_id1_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "build"
            output.mkdir()
            (output / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                build_pair(ROOT, output)


if __name__ == "__main__":
    unittest.main()
