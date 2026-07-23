import tempfile
import unittest
from pathlib import Path

from tools.butano.generate_scenario_41_attack_animation_assets import (
    _alpha_split_frame,
    generate_attack_animation_assets,
)
from tests.test_butano_scenario_41_assets import bmp_contract


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "artifacts" / "scenario-41-attack-animation-v1"


class Scenario41AttackAssetsTest(unittest.TestCase):
    def test_alpha_split_recomposes_first_four_frames_exactly(self):
        manifest = __import__("json").loads(
            (REFERENCE / "manifest.json").read_text(encoding="utf-8")
        )
        for frame, filename in enumerate(manifest["timeline"][:4]):
            source = REFERENCE / "frames" / filename
            palette, bottom, middle, top = _alpha_split_frame(source)
            self.assertLessEqual(len(palette), 256)
            expected = __import__("PIL.Image", fromlist=["Image"]).open(source).convert("RGB")
            for y in range(160):
                for x in range(240):
                    offset = y * 256 + x
                    if top[offset]:
                        actual = palette[top[offset]]
                    else:
                        first = palette[middle[offset]]
                        second = palette[bottom[offset]]
                        actual = tuple(
                            min(255, (first[channel] * 10 + second[channel] * 10) // 16)
                            for channel in range(3)
                        )
                    self.assertEqual(actual, expected.getpixel((x, y)), (frame, x, y))

    def test_generates_deduplicated_bgs_and_264_frame_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            graphics = root / "graphics"
            header = root / "scenario_41_attack_animation_frames.h"
            result = generate_attack_animation_assets(REFERENCE, graphics, header)
            self.assertEqual(result["unique_frames"], 160)
            self.assertEqual(result["timeline_frames"], 264)
            self.assertEqual(result["palette_items"], 80)
            self.assertEqual(result["fade_frames"], 14)
            self.assertEqual(result["alpha_frames"], 4)
            self.assertEqual(result["alpha_items"], 12)
            self.assertEqual(result["alpha_palettes"], 4)
            self.assertEqual(len(list(graphics.glob("scenario_41_attack_frame_*.bmp"))), 160)
            self.assertEqual(len(list(graphics.glob("scenario_41_attack_palette_*.bmp"))), 80)
            self.assertEqual(
                sum(
                    len(list(graphics.glob(f"scenario_41_attack_alpha_*_{layer}.bmp")))
                    for layer in ("bottom", "middle", "top")
                ),
                12,
            )
            self.assertEqual(
                len(list(graphics.glob("scenario_41_attack_alpha_*_palette.bmp"))), 4
            )
            self.assertEqual(len(list(graphics.glob("*.json"))), 256)
            alpha_metadata = (
                graphics / "scenario_41_attack_alpha_0_middle.json"
            ).read_text(encoding="utf-8")
            self.assertIn(
                '"palette_item":"scenario_41_attack_alpha_0_palette"',
                alpha_metadata,
            )
            self.assertEqual(
                bmp_contract(graphics / "scenario_41_attack_palette_000.bmp"),
                (8, 8, 8),
            )
            self.assertEqual(
                bmp_contract(graphics / "scenario_41_attack_frame_000.bmp"),
                (256, 256, 8),
            )
            text = header.read_text(encoding="utf-8")
            self.assertIn("scenario_41_attack_frame_000", text)
            self.assertIn("scenario_41_attack_frame_159", text)
            self.assertIn("std::array<const bn::regular_bg_item*, 264>", text)
            self.assertIn("std::array<const bn::bg_palette_item*, 264>", text)
            self.assertIn("scenario_41_attack_animation_palettes", text)
            self.assertIn("scenario_41_attack_animation_dark_fade", text)
            self.assertIn("scenario_41_attack_alpha_bottom", text)
            self.assertIn("scenario_41_attack_alpha_middle", text)
            self.assertIn("scenario_41_attack_alpha_top", text)
            self.assertIn("15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2", text)
            for frame_item in range(160):
                metadata = (
                    graphics / f"scenario_41_attack_frame_{frame_item:03d}.json"
                ).read_text(encoding="utf-8")
                self.assertIn('"palette_item":"scenario_41_attack_palette_', metadata)


if __name__ == "__main__":
    unittest.main()
