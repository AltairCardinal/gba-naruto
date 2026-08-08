from pathlib import Path
import json
import tempfile
import unittest

from tools.build_map_sprites_definition_pixel_ab import build_pair


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "sequel/content/map-sprites/definition-id01-pixel-ab.json"


class BuildMapSpritesDefinitionPixelAbTests(unittest.TestCase):
    def test_builds_an_isolated_definition_pointer_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build"
            manifest = build_pair(ROOT, PROFILE, output)
            self.assertEqual(manifest["schema"], "map-sprites-definition-pixel-ab-build-v1")
            self.assertEqual(manifest["entry_id"], 1)
            self.assertEqual(manifest["donor_entry_id"], 37)
            self.assertFalse(manifest["natural_gameplay_route"])
            self.assertTrue(manifest["controlled_task_materialization"])
            self.assertEqual(manifest["inputs"], [])
            self.assertEqual(manifest["edit"]["changed_rom_offsets"], [0x53F148, 0x53F149])
            self.assertEqual(manifest["edit"]["before_bytes"], "d8f51208")
            self.assertEqual(manifest["edit"]["after_bytes"], "ccf71208")
            baseline = (output / manifest["variants"]["baseline"]["rom_path"]).read_bytes()
            candidate = (output / manifest["variants"]["candidate"]["rom_path"]).read_bytes()
            changed = [
                index
                for index, pair in enumerate(zip(baseline, candidate, strict=True))
                if pair[0] != pair[1]
            ]
            self.assertEqual(changed, [0x53F148, 0x53F149])
            self.assertEqual(json.loads((output / "build-manifest.json").read_text()), manifest)


if __name__ == "__main__":
    unittest.main()
