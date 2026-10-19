import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.butano.generate_battle_duel_components import (
    DUEL_BACKGROUND_PALETTE_OFFSET,
    DUEL_BACKGROUND_TILEMAP_OFFSET,
    DUEL_BACKGROUND_TILES_OFFSET,
    DUEL_HUD_EVIDENCE,
    extract_duel_background,
    extract_duel_hud_shell,
    generate,
)


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "rom" / "base.gba"


class BattleDuelComponentGeneratorTest(unittest.TestCase):
    def test_extracts_hash_bound_original_background_components(self):
        result = extract_duel_background(ROM.read_bytes())

        self.assertEqual(0x329C34, DUEL_BACKGROUND_TILES_OFFSET)
        self.assertEqual(0x32A854, DUEL_BACKGROUND_PALETTE_OFFSET)
        self.assertEqual(0x32A8F8, DUEL_BACKGROUND_TILEMAP_OFFSET)
        self.assertEqual(
            "c5463fdae80642349f275722801017ff3e23bdffa88190ca111a3184bafd38c1",
            hashlib.sha256(result["tiles"]).hexdigest(),
        )
        self.assertEqual(
            "3c86d041724735cc717fedffe8cca91ac9d717b7878c2296672e295eb12923e4",
            hashlib.sha256(result["palette"]).hexdigest(),
        )
        self.assertEqual(
            "5bfb7c60fb1aec2f55c04b733a50d68bd14f0c8618e7c0de69d00a7e08ab4367",
            hashlib.sha256(result["tilemap"]).hexdigest(),
        )
        self.assertEqual((256, 256), result["image"].size)
        self.assertEqual("P", result["image"].mode)

    def test_generated_asset_declares_rom_components_not_a_screenshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            manifest = generate(ROM, output)

            bmp = output / "battle_duel_forest.bmp"
            metadata = output / "battle_duel_forest.json"
            self.assertTrue(bmp.is_file())
            self.assertTrue(metadata.is_file())
            self.assertFalse(
                (output / "battle_duel_forest.manifest.json").exists()
            )
            with Image.open(bmp) as image:
                self.assertEqual((256, 256), image.size)
            metadata_text = metadata.read_text(encoding="utf-8")
            self.assertIn('"type": "regular_bg"', metadata_text)
            self.assertIn("0x08329C34", metadata_text)
            self.assertNotIn("screenshot", metadata_text.lower())
            self.assertEqual(
                "original-action-duel-components-v1",
                manifest["schema"],
            )

    def test_extracts_state_free_duel_hud_shell_from_original_bg3(self):
        result = extract_duel_hud_shell(DUEL_HUD_EVIDENCE)

        self.assertEqual((256, 256), result["background_image"].size)
        self.assertEqual("P", result["background_image"].mode)
        self.assertEqual(
            {
                "io.bin":
                    "bd341fe4ab656ae5efe75ca79fcaa88fac1b21d4adef7040bfff740a70e1a651",
                "pram.bin":
                    "871ca742605c8962eb7a58a230ae8610275dc9582b1967d74ed0c1e9840379ee",
                "vram.bin":
                    "42537d6c7d0c5858e099b0823aee94ba88105bd438ef9b106021d37dc128b4fc",
            },
            result["source_sha256"],
        )
        self.assertEqual(14, result["palette_bank"])
        self.assertGreater(result["cleared_dynamic_cells"], 0)
        self.assertEqual(
            0,
            result["background_image"].getpixel((255, 255)),
        )
        self.assertEqual(
            1,
            result["background_image"].getpixel((16, 16)),
        )

    def test_generated_assets_include_runtime_driven_duel_hud_background(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            for stale in (
                "battle_duel_title_panel.bmp",
                "battle_duel_title_panel.json",
                "battle_duel_status_panels.bmp",
                "battle_duel_status_panels.json",
            ):
                (output / stale).write_bytes(b"stale")
            manifest = generate(ROM, output)

            bitmap = output / "battle_duel_hud_shell.bmp"
            metadata = output / "battle_duel_hud_shell.json"
            self.assertTrue(bitmap.is_file())
            self.assertTrue(metadata.is_file())
            with Image.open(bitmap) as image:
                self.assertEqual((256, 256), image.size)
            metadata_text = metadata.read_text(encoding="utf-8")
            self.assertIn('"type": "regular_bg"', metadata_text)
            self.assertIn('"bpp_mode": "bpp_4"', metadata_text)
            self.assertIn("state_free_shell", metadata_text)
            for stale in (
                "battle_duel_title_panel.bmp",
                "battle_duel_title_panel.json",
                "battle_duel_status_panels.bmp",
                "battle_duel_status_panels.json",
            ):
                self.assertFalse((output / stale).exists())

            self.assertEqual(
                "original-s49-enemy-duel-bg3",
                manifest["hud_shell"]["source"],
            )


if __name__ == "__main__":
    unittest.main()
