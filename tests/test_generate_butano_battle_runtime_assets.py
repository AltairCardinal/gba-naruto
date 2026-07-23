import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.generate_butano_battle_runtime_assets import generate


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattleRuntimeAssetsTest(unittest.TestCase):
    def test_generates_clean_map_and_independent_enemy_sprite(self):
        source = ROOT / "butano-sequel" / "graphics" / "scenario_41_map.bmp"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            clean_map = output / "scenario_41_clean_map.bmp"
            enemy = output / "scenario_41_enemy.bmp"
            clean_json = output / "scenario_41_clean_map.json"
            enemy_json = output / "scenario_41_enemy.json"
            generate(source, clean_map, enemy, clean_json, enemy_json)

            with Image.open(source) as original, Image.open(clean_map) as clean:
                self.assertEqual(clean.size, original.size)
                allowed = {(x, y) for x in range(96, 128) for y in range(128, 160)}
                allowed.update(
                    (x, y) for x in range(160, 192) for y in range(128, 160)
                )
                changed = {
                    (x, y)
                    for y in range(original.height)
                    for x in range(original.width)
                    if original.getpixel((x, y)) != clean.getpixel((x, y))
                }
                self.assertTrue(changed)
                self.assertTrue(changed <= allowed)

            with Image.open(enemy) as sprite:
                self.assertEqual(sprite.size, (32, 32))
                self.assertEqual(sprite.mode, "P")
                self.assertEqual(sprite.getpixel((31, 0)), 0)
                opaque = sum(pixel != 0 for pixel in sprite.get_flattened_data())
                self.assertGreater(opaque, 300)
                self.assertLess(opaque, 900)

            self.assertEqual(
                json.loads(clean_json.read_text(encoding="utf-8")),
                {"type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256},
            )
            self.assertEqual(
                json.loads(enemy_json.read_text(encoding="utf-8")),
                {"type": "sprite", "height": 32, "bpp_mode": "bpp_8"},
            )


if __name__ == "__main__":
    unittest.main()
