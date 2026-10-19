import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RESULT_EVIDENCE = (
    ROOT / "artifacts/original-s49-result-gpu-20260730-323"
)


class ButanoBattleResultOriginalUiTest(unittest.TestCase):
    def test_result_assets_are_split_into_original_stage_and_panel_layers(self):
        from tools.butano.generate_battle_ui_assets import (
            _result_background_pixels,
            _result_panel_pixels,
        )

        stage = _result_background_pixels()
        panel = _result_panel_pixels()
        self.assertEqual(len(stage), 256 * 256)
        self.assertEqual(len(panel), 256 * 256)

        # Butano's centered 256x256 regular BG viewport starts at (8, 48).
        # The stage owns the original 73-pixel gray gradient; the panel
        # remains transparent between its header and score box.
        for screen_y in range(32, 105):
            for screen_x in range(240):
                index = (screen_y + 48) * 256 + screen_x + 8
                self.assertNotEqual(stage[index], 0)
        self.assertEqual(panel[(80 + 48) * 256 + 120 + 8], 0)

        # Runtime names and values are deliberately absent from the panel
        # asset.  Fixed labels and exact woven borders remain state-free.
        for screen_y in range(8, 24):
            for screen_x in (
                *range(96, 112),
                *range(152, 168),
                *range(208, 224),
            ):
                self.assertEqual(
                    panel[(screen_y + 48) * 256 + screen_x + 8],
                    panel[
                        (screen_y + 48) * 256
                        + 88
                        + screen_x % 8
                        + 8
                    ],
                )

    def test_result_large_font_uses_full_height_original_glyphs(self):
        from tools.generate_butano_battle_identity_content import (
            ASCII_GLYPH_COUNT,
            RESULT_LARGE_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_result_font_bitmap,
            load_identity_content,
        )

        bitmap = generate_result_font_bitmap(ROOT)
        characters = load_identity_content(ROOT)["utf8_characters"]
        for character in "经验值鸣人佐助小樱合计":
            source_path, left, top = RESULT_LARGE_GLYPH_SOURCES[character]
            with self.subTest(character=character):
                with Image.open(ROOT / source_path) as source:
                    expected = source.convert("RGB").crop(
                        (left, top, left + 8, top + UI_GLYPH_HEIGHT)
                    )
                glyph_index = ASCII_GLYPH_COUNT + characters.index(character)
                actual = bitmap.crop(
                    (
                        0,
                        glyph_index * UI_GLYPH_HEIGHT,
                        8,
                        (glyph_index + 1) * UI_GLYPH_HEIGHT,
                    )
                )
                self.assertGreater(
                    sum(
                        pixel != 0
                        for pixel in actual.crop((0, 8, 8, 16))
                        .get_flattened_data()
                    ),
                    0,
                )
                self.assertEqual(actual.size, expected.size)

        for digit in "0235":
            glyph_top = (
                ord(digit) - ord("!")
            ) * UI_GLYPH_HEIGHT
            self.assertGreater(
                sum(
                    pixel != 0
                    for pixel in bitmap.crop(
                        (0, glyph_top + 8, 8, glyph_top + 16)
                    ).get_flattened_data()
                ),
                0,
            )

    def test_result_compact_font_uses_result_page_digits(self):
        from tools.generate_butano_battle_identity_content import (
            RESULT_COMPACT_ASCII_GLYPH_SOURCES,
            UI_GLYPH_HEIGHT,
            generate_result_compact_font_bitmap,
        )

        bitmap = generate_result_compact_font_bitmap(ROOT)
        for digit in "01257":
            source_path, left, top = (
                RESULT_COMPACT_ASCII_GLYPH_SOURCES[digit]
            )
            with self.subTest(digit=digit):
                with Image.open(ROOT / source_path) as source:
                    source.crop(
                        (left, top, left + 8, top + 8)
                    )
                glyph_top = (
                    ord(digit) - ord("!")
                ) * UI_GLYPH_HEIGHT
                glyph = bitmap.crop(
                    (0, glyph_top, 8, glyph_top + 16)
                )
                self.assertGreater(
                    sum(
                        pixel != 0
                        for pixel in glyph.crop(
                            (0, 0, 8, 8)
                        ).get_flattened_data()
                    ),
                    0,
                )
                self.assertEqual(
                    sum(
                        pixel != 0
                        for pixel in glyph.crop(
                            (0, 8, 8, 16)
                        ).get_flattened_data()
                    ),
                    0,
                )

    def test_result_participant_assets_use_original_result_oam(self):
        from tools.butano.generate_battle_ui_assets import (
            _result_participant_palette,
            _result_participant_pixels,
        )

        expected = (
            (2, 0, 0),
            (1, 64, 1),
            (0, 128, 2),
        )
        for oam_index, tile_index, palette_bank in expected:
            with self.subTest(oam_index=oam_index):
                pixels = _result_participant_pixels(oam_index)
                palette = _result_participant_palette(oam_index)
                self.assertEqual(len(pixels), 32 * 64)
                self.assertEqual(len(palette), 16)
                self.assertGreater(sum(pixel != 0 for pixel in pixels), 0)
                oam = (RESULT_EVIDENCE / "oam.bin").read_bytes()
                attr2 = int.from_bytes(
                    oam[oam_index * 8 + 4:oam_index * 8 + 6],
                    "little",
                )
                self.assertEqual(attr2 & 0x3FF, tile_index)
                self.assertEqual(attr2 >> 12, palette_bank)

    def test_runtime_projects_all_participants_and_all_score_columns(self):
        source = (
            ROOT
            / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        header = (
            ROOT
            / "butano-sequel/game/include/konoha"
            / "battle_result_sprite_font.h"
        )

        self.assertTrue(header.is_file())
        self.assertIn(
            '#include "konoha/battle_result_sprite_font.h"',
            source,
        )
        self.assertIn(
            "bn::sprite_text_generator result_text_generator(\n"
            "            battle_result_sprite_font);",
            source,
        )
        self.assertIn(
            "bn::sprite_text_generator result_compact_text_generator(\n"
            "            battle_result_compact_sprite_font);",
            source,
        )
        for item in (
            "battle_ui_result_naruto",
            "battle_ui_result_sasuke",
            "battle_ui_result_sakura",
        ):
            self.assertIn(item, source)
        self.assertIn("participant_x[index], -8", source)
        self.assertIn("_result_participants.clear();", source)
        self.assertIn(
            "for(std::size_t index = 0;\n"
            "                    index < result.participant_count &&\n"
            "                    index < 3;",
            source,
        )
        self.assertNotIn(
            "const battle_result_participant& participant =\n"
            "                    result.participants[\n"
            "                            participant_index];",
            source,
        )
        for field in (
            "mission_experience",
            "battle_experience",
            "round_bonus_experience",
            "total_experience",
        ):
            self.assertIn(f".{field}", source)

    def test_runtime_places_compact_score_rows_at_original_y(self):
        source = (
            ROOT
            / "butano-sequel/game/src/battle_runtime_scene.cpp"
        ).read_text(encoding="utf-8")
        for field, y in (
            ("mission_experience", 40),
            ("battle_experience", 48),
            ("round_bonus_experience", 56),
        ):
            with self.subTest(field=field):
                self.assertRegex(
                    source,
                    rf"result_compact_text_generator\.generate\("
                    rf"\s*participant_value_x\[index\],"
                    rf"\s*{y},\s*bn::to_string<8>\("
                    rf"\s*participant\s*\.{field}\)",
                )

    def test_authoritative_result_evidence_is_complete(self):
        for name, size in (
            ("io.bin", 0x400),
            ("pram.bin", 0x400),
            ("oam.bin", 0x400),
            ("vram.bin", 0x18000),
        ):
            self.assertEqual((RESULT_EVIDENCE / name).stat().st_size, size)
        with Image.open(RESULT_EVIDENCE / "frame.png") as frame:
            self.assertEqual(frame.size, (240, 160))


if __name__ == "__main__":
    unittest.main()
