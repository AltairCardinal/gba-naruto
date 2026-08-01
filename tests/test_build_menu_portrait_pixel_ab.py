from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BuildMenuPortraitPixelAbTests(unittest.TestCase):
    def test_builds_one_pair_one_pixel_production_relocation(self):
        from tools.build_menu_portrait_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            manifest = build_pair(ROOT, output)

            self.assertEqual("menu-portrait-pixel-ab-build-v1", manifest["schema"])
            self.assertEqual(
                {
                    "portrait_id": 1,
                    "variant": 0,
                    "resource_id": 0,
                    "pair_pointer_offset": 0x5A4E14,
                    "canvas_xy": [40, 40],
                    "canvas_byte_offset": 3240,
                    "stream_byte_offset": 5184,
                    "before_index": 52,
                    "after_index": 14,
                },
                manifest["edit"],
            )
            self.assertEqual({"baseline", "candidate"}, set(manifest["variants"]))
            self.assertTrue(manifest["isolation"]["same_allocation_addresses"])
            self.assertTrue(manifest["isolation"]["same_redirect_pointers"])
            self.assertTrue(manifest["isolation"]["single_decoded_graphics_byte"])

            variants = manifest["variants"]
            roms = {}
            for variant, expected_graphics_size in (("baseline", 3306), ("candidate", 3306)):
                row = variants[variant]
                rom = (output / row["rom_path"]).read_bytes()
                roms[variant] = rom
                self.assertEqual(0x1000000, len(rom))
                self.assertEqual(row["rom_sha256"], _sha256(rom))
                self.assertEqual(4, len(row["patch_ledger"]))
                graphics, palette, gfx_redirect, palette_redirect = row["patch_ledger"]
                self.assertEqual((0xA80000, expected_graphics_size), (graphics["offset"], graphics["size"]))
                self.assertEqual((0xA80CEC, 128), (palette["offset"], palette["size"]))
                self.assertEqual((0x5A4E14, "0000a808"), (gfx_redirect["offset"], gfx_redirect["after_hex"]))
                self.assertEqual((0x5A4E18, "ec0ca808"), (palette_redirect["offset"], palette_redirect["after_hex"]))
                self.assertEqual(row["graphics_sha256"], _sha256(lz77_decompress(rom, 0xA80000)))

            baseline = lz77_decompress(roms["baseline"], 0xA80000)
            candidate = lz77_decompress(roms["candidate"], 0xA80000)
            differences = [
                index
                for index, pair in enumerate(zip(baseline, candidate))
                if pair[0] != pair[1]
            ]
            self.assertEqual([5184], differences)
            self.assertEqual(52, baseline[5184])
            self.assertEqual(14, candidate[5184])
            self.assertEqual(
                roms["baseline"][0x5A4E14:0x5A4E1C],
                roms["candidate"][0x5A4E14:0x5A4E1C],
            )

    def test_rejects_a_nonempty_output_directory(self):
        from tools.build_menu_portrait_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            output.mkdir()
            (output / "stale").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                build_pair(ROOT, output)


if __name__ == "__main__":
    unittest.main()
