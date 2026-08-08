from pathlib import Path
import json
import tempfile
import unittest

from tools.build_tile_asset_descriptor_pixel_ab import build_pair


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/tile-assets/descriptor-02-palette-pointer-pixel-ab.json"


class BuildTileAssetDescriptorPixelAbTests(unittest.TestCase):
    def test_builds_an_isolated_descriptor_palette_pointer_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build"
            manifest = build_pair(ROOT, PROFILE, output)
            self.assertEqual(manifest["schema"], "tile-asset-descriptor-pixel-ab-build-v1")
            self.assertEqual(manifest["descriptor_id"], 2)
            self.assertEqual(manifest["consumer_id"], 3)
            self.assertEqual(manifest["input_mode"], "zero-input-active-state")
            self.assertEqual(manifest["inputs"], [])
            self.assertEqual(
                manifest["edit"]["changed_rom_offsets"], [0x5A32A8, 0x5A32A9]
            )
            self.assertEqual(manifest["edit"]["before_bytes"], "28b23408")
            self.assertEqual(manifest["edit"]["after_bytes"], "749e3408")
            baseline = (output / manifest["variants"]["baseline"]["rom_path"]).read_bytes()
            candidate = (output / manifest["variants"]["candidate"]["rom_path"]).read_bytes()
            changed = [
                index
                for index, (before, after) in enumerate(zip(baseline, candidate, strict=True))
                if before != after
            ]
            self.assertEqual(changed, [0x5A32A8, 0x5A32A9])
            on_disk = json.loads((output / "build-manifest.json").read_text())
            self.assertEqual(on_disk, manifest)


if __name__ == "__main__":
    unittest.main()
