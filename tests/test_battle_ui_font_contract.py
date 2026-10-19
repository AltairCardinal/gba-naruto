#!/usr/bin/env python3
"""The battle UI font atlas is built from screenshots; those inputs are the contract.

`tools/generate_butano_battle_identity_content.py` does not draw the CJK glyphs
from a font file: for 100 of them it crops an 8x16 cell out of a recorded
original-game screenshot at a hardcoded ``(left, top)``, and it replaces 10
ASCII cells the same way.  The generated `battle_ui_font.bmp` and
`battle_ui_sprite_font.h` are therefore only as correct as those coordinates,
and the whole pipeline becomes unreproducible the moment one of the source
screenshots is cleaned up — which happened: ten of them are currently absent
from the work tree.

This gate fails closed on that state instead of letting a stale atlas be
treated as verified.  It also pins Butano's own font contract, which the
header satisfies only because the counts happen to line up:

    minimum_graphics (94) + characters  ==  atlas tiles
    1 + minimum_graphics + characters   ==  width entries
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

# bn::sprite_font::minimum_graphics — the ASCII block that must precede the
# UTF-8 characters in the tile set.
BUTANO_MINIMUM_GRAPHICS = 94
GLYPH_WIDTH = 8
GLYPH_HEIGHT = 16


def _generator():
    import sys

    sys.path.insert(0, str(ROOT))
    from tools import generate_butano_battle_identity_content as generator

    return generator


def _parse_header(path: Path) -> tuple[list[str], list[int]]:
    text = path.read_text(encoding="utf-8")
    characters = text.split("battle_ui_font_utf8_characters[] = {", 1)[1]
    characters = re.sub(r"//.*", "", characters).split("\n};", 1)[0]
    widths = text.split("battle_ui_font_character_widths[] = {", 1)[1]
    widths = re.sub(r"//.*", "", widths).split("\n};", 1)[0]
    names = [token.strip().strip('"') for token in characters.split(",") if token.strip()]
    values = [int(token.strip()) for token in widths.split(",") if token.strip()]
    return names, values


class ScreenshotInputsExistTest(unittest.TestCase):
    """Every glyph crop the generator declares must still be on disk."""

    def test_ascii_override_screenshots_exist(self):
        generator = _generator()
        missing = sorted({
            source for source, _, _ in
            generator.ORIGINAL_UI_ASCII_GLYPH_SOURCES.values()
            if not (ROOT / source).is_file()
        })
        self.assertEqual(missing, [], "ASCII glyph override screenshots are gone")

    def test_cjk_glyph_screenshots_exist(self):
        generator = _generator()
        missing = sorted({
            source for source, _, _ in
            generator.SCENARIO_41_ORIGINAL_GLYPH_SOURCES.values()
            if not (ROOT / source).is_file()
        })
        self.assertEqual(
            missing, [],
            "CJK glyph source screenshots are gone; the atlas cannot be rebuilt")


class FontHeaderContractTest(unittest.TestCase):
    """The generated header must satisfy bn::sprite_font's own assertions."""

    def setUp(self):
        self.path = ROOT / "butano-sequel/game/include/konoha/battle_ui_sprite_font.h"
        self.characters, self.widths = _parse_header(self.path)

    def test_no_duplicate_characters(self):
        duplicates = sorted({
            character for character in self.characters
            if self.characters.count(character) > 1
        })
        self.assertEqual(duplicates, [], "duplicated characters break the map")

    def test_width_count_matches_butano_contract(self):
        expected = 1 + BUTANO_MINIMUM_GRAPHICS + len(self.characters)
        self.assertEqual(
            len(self.widths), expected,
            "bn::sprite_font requires 1 + minimum_graphics + characters widths")

    def test_atlas_tile_count_matches_butano_contract(self):
        bitmap = ROOT / "butano-sequel/graphics/battle_ui_font.bmp"
        with Image.open(bitmap) as image:
            tiles = image.size[1] // GLYPH_HEIGHT
        self.assertEqual(
            tiles, BUTANO_MINIMUM_GRAPHICS + len(self.characters),
            "atlas must hold the ASCII block followed by every character")


class FontCoordinatesAreDenseTest(unittest.TestCase):
    """Coordinate tables must not silently run past their source image."""

    def test_glyph_crops_stay_inside_their_source_image(self):
        generator = _generator()
        overflow = []
        for character, (source, left, top) in \
                generator.SCENARIO_41_ORIGINAL_GLYPH_SOURCES.items():
            path = ROOT / source
            if not path.is_file():
                continue
            with Image.open(path) as image:
                width, height = image.size
            if left + GLYPH_WIDTH > width or top + GLYPH_HEIGHT > height:
                overflow.append((character, source, left, top, width, height))
        self.assertEqual(overflow, [], "glyph crop coordinates fall outside the source")


if __name__ == "__main__":
    unittest.main()
