import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.generate_battle_action_16_movie import generate


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom" / "base.gba"
TRACE = (
    ROOT
    / "build"
    / "original-fire-presentation-trace-20260726-99"
)
CUTIN_TRACE = (
    ROOT
    / "build"
    / "original-fire-presentation-trace-20260726-98"
)


class BattleAction16MovieGeneratorTest(unittest.TestCase):
    def test_generates_layered_movie_components_without_screenshots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            manifest_path = output / "manifest.json"
            runtime_header_path = (
                output
                / "generated_battle_action_16_movie_runtime_content.h"
            )
            cutin_palette_header_path = (
                output
                / "bn_bg_palette_items_"
                "battle_action_16_cutin_shared_palette.h"
            )

            result = generate(
                ROM,
                TRACE,
                output,
                cutin_trace_dir=CUTIN_TRACE,
                manifest_path=manifest_path,
                runtime_header_path=runtime_header_path,
                cutin_palette_header_path=(
                    cutin_palette_header_path
                ),
            )

            self.assertEqual(
                "butano-original-action-16-movie-components-v1",
                result["schema"],
            )
            self.assertEqual(360, result["reference_frame"])
            self.assertEqual(4, len(result["backgrounds"]))
            self.assertEqual(3, len(result["title_sprites"]))
            self.assertEqual(2, len(result["cutin_backgrounds"]))
            self.assertEqual(
                "85067c2668849bb5e486323ed27bf74c7ed797eca533234ec3a5682ec4d38995",
                result["cutin_rom_resources"]["portrait_tiles"][
                    "sha256"
                ],
            )
            self.assertEqual(
                "982514213960e6cfbdf74c15d2fe2b32b525c8e7d0db0ba2e77076856f1c6290",
                result["cutin_rom_resources"]["portrait_tilemap"][
                    "sha256"
                ],
            )
            self.assertEqual(
                "e6a298bb50adddb4fb1020899f19a56704130182965a3442d8b4550b6789caeb",
                result["cutin_rom_resources"]["portrait_palette"][
                    "sha256"
                ],
            )
            self.assertEqual(
                [311, 437],
                result["runtime_timeline"]["original_frames"],
            )
            self.assertEqual(
                127,
                result["runtime_timeline"]["frame_count"],
            )
            self.assertEqual(
                {"top": 13, "bottom": 3},
                result["runtime_timeline"]["anchors"]["360"][
                    "blend_weights"
                ],
            )
            self.assertEqual(
                {"top": 15, "bottom": 1},
                result["runtime_timeline"]["anchors"]["400"][
                    "blend_weights"
                ],
            )
            self.assertEqual(
                "f210a464888b67b87682e742f02f84fc0881e44d03140ea7a3706a8bf6c81d83",
                result["rom_resources"]["streak_tiles"]["sha256"],
            )
            self.assertEqual(
                "e67674f79db1fde3169d3a6a395c0d5850a8eca55d23ae27351719314e2cd311",
                result["rom_resources"]["actor_fire_tiles_0"]["sha256"],
            )
            self.assertEqual(
                "efaa5d242654c6c6cffb7b2d2fae5588e8fd8974334f6fef1620f1f97b4d037e",
                result["rom_resources"]["actor_fire_tiles_1"]["sha256"],
            )

            for stem in (
                "battle_action_16_movie_actor",
                "battle_action_16_movie_fire",
                "battle_action_16_movie_streaks",
                "battle_action_16_movie_dialogue",
            ):
                with Image.open(output / f"{stem}.bmp") as image:
                    self.assertEqual((256, 256), image.size)
                    self.assertEqual("P", image.mode)
                metadata = (output / f"{stem}.json").read_text(
                    encoding="utf-8"
                )
                self.assertIn('"type": "regular_bg"', metadata)
                self.assertIn('"bpp_mode": "bpp_8"', metadata)

            for stem, expected_size in (
                (
                    "battle_action_16_cutin_portrait",
                    (512, 256),
                ),
                (
                    "battle_action_16_cutin_dialogue",
                    (256, 256),
                ),
            ):
                with Image.open(output / f"{stem}.bmp") as image:
                    self.assertEqual(expected_size, image.size)
                    self.assertEqual("P", image.mode)
                    if stem.endswith("portrait"):
                        pixels = image.tobytes()
                        for row in range(160):
                            self.assertEqual(
                                bytes(256),
                                pixels[
                                    row * image.width + 256 :
                                    row * image.width + 512
                                ],
                            )
                metadata = (output / f"{stem}.json").read_text(
                    encoding="utf-8"
                )
                self.assertIn('"type": "regular_bg"', metadata)
                self.assertIn('"bpp_mode": "bpp_8"', metadata)
                self.assertIn(
                    '"palette_item": '
                    '"battle_action_16_cutin_shared_palette"',
                    metadata,
                )

            cutin_palette = result["cutin_shared_palette"]
            color_count = cutin_palette["color_count"]
            self.assertEqual(256, color_count)
            self.assertEqual(255, cutin_palette["anchor_row"])
            self.assertIn(193, cutin_palette["source_indices"])
            self.assertIn(251, cutin_palette["source_indices"])
            self.assertEqual(
                256,
                len(cutin_palette["bgr555_colors"]),
            )
            self.assertLessEqual(
                max(cutin_palette["bgr555_colors"]),
                0x7FFF,
            )
            self.assertEqual(
                {
                    "window_left": 0,
                    "window_top": 32,
                    "window_right": 240,
                    "window_bottom": 112,
                    "blend_control": 0x00B7,
                    "window_inside": 0x3F3F,
                    "window_outside": 0x3F1F,
                    "fade_steps": 6,
                },
                result["cutin_fade_contract"],
            )
            cutin_images = []
            for stem in (
                "battle_action_16_cutin_portrait",
                "battle_action_16_cutin_dialogue",
            ):
                with Image.open(output / f"{stem}.bmp") as image:
                    image.load()
                    pixels = list(image.tobytes())
                    self.assertLess(max(pixels), color_count)
                    anchor_offset = (
                        cutin_palette["anchor_row"] * image.width
                    )
                    self.assertEqual(
                        list(range(color_count)),
                        pixels[
                            anchor_offset :
                            anchor_offset + color_count
                        ],
                    )
                    cutin_images.append(image.copy())
            self.assertEqual(
                cutin_images[0].getpalette(),
                cutin_images[1].getpalette(),
            )

            for index in range(3):
                stem = f"battle_action_16_movie_title_{index}"
                with Image.open(output / f"{stem}.bmp") as image:
                    self.assertEqual((32, 32), image.size)
                    self.assertEqual("P", image.mode)
                metadata = (output / f"{stem}.json").read_text(
                    encoding="utf-8"
                )
                self.assertIn('"type": "sprite"', metadata)
                self.assertIn('"height": 32', metadata)

            manifest_text = manifest_path.read_text(encoding="utf-8")
            self.assertNotIn(".png", manifest_text.lower())
            self.assertNotIn("screenshot", manifest_text.lower())
            runtime_header = runtime_header_path.read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "battle_action_16_movie_fire_palettes",
                runtime_header,
            )
            self.assertIn(
                "battle_action_16_movie_blend_top_weights",
                runtime_header,
            )
            self.assertIn(
                "battle_action_16_movie_blend_bottom_weights",
                runtime_header,
            )
            self.assertIn(
                "battle_action_16_cutin_palette",
                runtime_header,
            )
            cutin_palette_header = (
                cutin_palette_header_path.read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn(
                "battle_action_16_cutin_shared_palette",
                cutin_palette_header,
            )
            self.assertIn(
                "battle_action_16_cutin_palette",
                cutin_palette_header,
            )


if __name__ == "__main__":
    unittest.main()
