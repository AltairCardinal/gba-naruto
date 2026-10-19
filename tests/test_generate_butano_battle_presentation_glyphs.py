#!/usr/bin/env python3
"""Tests for ROM-derived battle-presentation glyph assets."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class GenerateButanoBattlePresentationGlyphTests(unittest.TestCase):
    def test_all_presentation_codes_resolve_through_the_rom_font_table(self):
        from tools.generate_butano_battle_presentation_glyphs import (
            load_battle_presentation_glyphs,
        )

        content = load_battle_presentation_glyphs(ROOT)
        self.assertEqual(len(content["codes"]), 862)
        self.assertEqual(content["codes"][0], 0x8140)
        self.assertEqual(len(content["tile_addresses"]), 862)
        self.assertEqual(len(content["pixels"]), 862 * 8 * 16)
        self.assertEqual(set(content["pixels"]), {0, 5, 10, 15})
        self.assertTrue(all(
            0x08000000 <= address < 0x08600000
            for address in content["tile_addresses"]
        ))

    def test_generated_bitmap_is_one_8x16_frame_per_original_code(self):
        from tools.generate_butano_battle_presentation_glyphs import (
            generate_outputs,
        )

        with tempfile.TemporaryDirectory() as directory:
            outputs = generate_outputs(ROOT, Path(directory))
            with Image.open(outputs["bitmap"]) as image:
                self.assertEqual(image.size, (8, 862 * 16))
                self.assertEqual(image.mode, "P")
                self.assertEqual(
                    sorted(set(image.get_flattened_data())),
                    [0, 5, 10, 15],
                )
            self.assertEqual(
                outputs["metadata"].read_text(encoding="utf-8"),
                '{\n  "type": "sprite",\n  "height": 16\n}\n',
            )

    def test_generated_lookup_header_is_deterministic(self):
        from tools.generate_butano_battle_presentation_glyphs import (
            generate_header,
            load_battle_presentation_glyphs,
        )

        content = load_battle_presentation_glyphs(ROOT)
        first = generate_header(content)
        second = generate_header(content)
        self.assertEqual(first, second)
        self.assertIn(
            "std::array<std::uint16_t, 862>", first
        )
        self.assertIn("battle_presentation_glyph_index", first)


if __name__ == "__main__":
    unittest.main()
