import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.analyze_original_effect_sequence import (
    ACTION_05_HIT_PALETTE_OFFSET,
    ACTION_05_HIT_TILES_OFFSET,
    analyze_effect_sequence,
)


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom" / "base.gba"
TRACE = (
    ROOT
    / "build"
    / "original-action-presentation-trace-20260726-08"
)
TRACE_BOMB = (
    ROOT
    / "build"
    / "battle-presentation-original-probes-20260727-15"
    / "tool49-component-trace"
)


class OriginalEffectSequenceAnalyzerTest(unittest.TestCase):
    def test_decodes_semitransparent_bomb_smoke_components(self):
        result = analyze_effect_sequence(
            ROM,
            TRACE_BOMB,
            first_frame=147,
            last_frame=274,
            base_tile=472,
            tile_count=304,
            palette_bank=7,
            tiles_address=0x08340AF8,
            palette_address=0x08341FA8,
            include_semi_transparent=True,
        )

        self.assertEqual(148, result["active_frame_start"])
        self.assertEqual(258, result["active_frame_end"])
        self.assertEqual(111, result["active_frame_count"])
        self.assertEqual(14, result["maximum_components"])
        self.assertTrue(result["resources"]["tiles"]["all_vram_matches"])
        self.assertTrue(result["resources"]["palette"]["all_pram_matches"])
        self.assertEqual(
            "eb9589427babaaa4d746b365cf1ea3083a5accd5cc408d53ac9c83131fb82475",
            result["resources"]["tiles"]["sha256"],
        )
        self.assertEqual(
            "70c511e326da6ce384f358d0dfe798d71dd44f181f6bcaa693e77aa456f5422e",
            result["resources"]["palette"]["sha256"],
        )

        frames = {
            frame["original_frame"]: frame
            for frame in result["frames"]
        }
        self.assertTrue(
            frames[150]["components"][0]["semi_transparent"]
        )
    def test_decodes_action_05_as_compound_oam_frames(self):
        result = analyze_effect_sequence(
            ROM,
            TRACE,
            first_frame=146,
            last_frame=180,
            base_tile=288,
            tile_count=120,
            palette_bank=5,
        )

        self.assertEqual(0x342938, ACTION_05_HIT_TILES_OFFSET)
        self.assertEqual(0x342DC8, ACTION_05_HIT_PALETTE_OFFSET)
        self.assertEqual(
            "6628fdc3365f8d6f16b134797be5f9a1c7cb48662ffeeea634ace058c659bb32",
            result["resources"]["tiles"]["sha256"],
        )
        self.assertEqual(
            "c00b7ea1d6748f60c387c12d2083da584a65a7e654e61a95bdfe25d1a803dc61",
            result["resources"]["palette"]["sha256"],
        )
        self.assertTrue(result["resources"]["tiles"]["all_vram_matches"])
        self.assertTrue(result["resources"]["palette"]["all_pram_matches"])

        frames = {
            frame["original_frame"]: frame
            for frame in result["frames"]
        }
        self.assertEqual([], frames[146]["components"])
        self.assertEqual(1, len(frames[148]["components"]))
        self.assertEqual(
            {
                "x": 160,
                "y": 48,
                "width": 32,
                "height": 32,
                "tile_offset": 0,
                "palette_bank": 5,
                "priority": 2,
                "horizontal_flip": False,
                "vertical_flip": False,
            },
            frames[148]["components"][0],
        )
        self.assertEqual(8, len(frames[152]["components"]))
        self.assertEqual(8, result["maximum_components"])
        self.assertEqual(148, result["active_frame_start"])
        self.assertEqual(163, result["active_frame_end"])
        self.assertEqual(16, result["active_frame_count"])
        self.assertEqual(
            hashlib.sha256(
                (TRACE / "gpu-frame-0154-oam.bin").read_bytes()
            ).hexdigest(),
            frames[154]["oam_sha256"],
        )

    def test_writes_hash_bound_manifest_without_screenshot_pixels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "action-05-hit.json"
            result = analyze_effect_sequence(
                ROM,
                TRACE,
                first_frame=146,
                last_frame=180,
                base_tile=288,
                tile_count=120,
                palette_bank=5,
                output_path=manifest,
            )

            self.assertTrue(manifest.is_file())
            text = manifest.read_text(encoding="utf-8")
            self.assertIn('"schema": "original-oam-effect-sequence-v1"', text)
            self.assertIn('"trace_sha256"', text)
            self.assertNotIn(".png", text.lower())
            self.assertEqual(
                "original-oam-effect-sequence-v1",
                result["schema"],
            )

    def test_accepts_rom_resource_addresses_instead_of_action_specific_constants(
        self,
    ):
        result = analyze_effect_sequence(
            ROM,
            TRACE,
            first_frame=148,
            last_frame=148,
            base_tile=288,
            tile_count=120,
            palette_bank=5,
            tiles_address=0x08342938,
            palette_address=0x08342DC8,
        )

        self.assertEqual(
            "0x08342938",
            result["resources"]["tiles"]["address"],
        )
        self.assertEqual(
            "0x08342DC8",
            result["resources"]["palette"]["address"],
        )


if __name__ == "__main__":
    unittest.main()
