from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.extract_tileset import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BuildBattleEffectGroup5PixelAbTests(unittest.TestCase):
    def test_builds_one_group5_pixel_with_stable_relocation_topology(self):
        from tools.build_battle_effect_group5_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            manifest = build_pair(ROOT, output)

            self.assertEqual(
                "battle-effect-group5-pixel-ab-build-v1", manifest["schema"]
            )
            self.assertEqual(
                {
                    "group_id": 5,
                    "sequence_id": 6,
                    "frame_id": 1,
                    "graphics_byte_offset": 0x200,
                    "tile_id": 16,
                    "tile_pixel_xy": [0, 0],
                    "frame_pixel_xy": [0, 0],
                    "before_byte": 0x02,
                    "after_byte": 0x04,
                    "before_index": 2,
                    "after_index": 4,
                    "screen_xy": [160, 48],
                },
                manifest["edit"],
            )
            self.assertEqual([0x200], manifest["isolation"]["decoded_offsets"])
            self.assertTrue(manifest["isolation"]["same_patch_topology"])
            self.assertTrue(manifest["isolation"]["same_allocation_offsets"])
            self.assertTrue(manifest["isolation"]["same_redirect_pointers"])

            variants = manifest["variants"]
            roms = {}
            for variant in ("baseline", "candidate"):
                row = variants[variant]
                rom = (output / row["rom_path"]).read_bytes()
                roms[variant] = rom
                self.assertEqual(0x1000000, len(rom))
                self.assertEqual(row["rom_sha256"], _sha256(rom))
                self.assertEqual(2, len(row["patch_ledger"]))
                allocation, redirect = row["patch_ledger"]
                self.assertEqual((0xB40000, 1165), (allocation["offset"], allocation["size"]))
                self.assertEqual(0x599144, redirect["offset"])
                self.assertEqual("0000b408", redirect["after_hex"])
                self.assertEqual(
                    row["graphics_sha256"],
                    _sha256(lz77_decompress(rom, allocation["offset"])),
                )

            baseline = lz77_decompress(roms["baseline"], 0xB40000)
            candidate = lz77_decompress(roms["candidate"], 0xB40000)
            differences = [
                index
                for index, pair in enumerate(zip(baseline, candidate))
                if pair[0] != pair[1]
            ]
            self.assertEqual([0x200], differences)
            self.assertEqual(0x02, baseline[0x200])
            self.assertEqual(0x04, candidate[0x200])

    def test_rejects_a_nonempty_output_directory(self):
        from tools.build_battle_effect_group5_pixel_ab import build_pair

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pair"
            output.mkdir()
            (output / "stale").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                build_pair(ROOT, output)


if __name__ == "__main__":
    unittest.main()
