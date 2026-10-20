#!/usr/bin/env python3
"""The command menu's 查克拉 label must use the full-height glyph tiles.

S49's original ROM draws 查克拉 at two different heights:

* the command menu (frame 18, row 2) draws it full height, 16 rows of ink;
* the status HUD draws the same three characters as 8-row compact glyphs.

The remake has one shared `battle_ui_font` atlas cell, and the status HUD
already matches the original there pixel for pixel, so that cell has to stay
compact.  The full-height tiles the command menu needs are already in the
action-menu atlas, byte for byte identical to the original's command menu, so
the label is drawn with the action-menu font instead of adding a third atlas.

Two independent checks keep this from regressing:

* `test_action_menu_atlas_holds_the_full_height_chakra_tiles` reads the tiles
  straight out of the shipped atlas and compares them with the original frame,
  so the gate holds even if the recorded captures are gone;
* `test_command_menu_draws_chakra_with_the_action_menu_font` pins the font
  choice in the scene source, and the capture-based gate demands zero
  differing pixels in the command-menu text panel.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / "butano-sequel/game/src/battle_runtime_scene.cpp"
GRAPHICS = ROOT / "butano-sequel/graphics"
RUN = ROOT / "artifacts/s49-fidelity-20261019-v1"
ORIGINAL = RUN / "walk-original-a24"
REMAKE = RUN / "walk-remake-dd-a30-chakrafix"

UI_FONT_HEADER = ROOT / "butano-sequel/game/include/konoha/battle_ui_sprite_font.h"
ACTION_FONT_HEADER = (
    ROOT
    / "butano-sequel/game/include/konoha/"
    "battle_action_menu_sprite_font.h"
)

ASCII_GLYPH_COUNT = 94
GLYPH_WIDTH = 8
GLYPH_HEIGHT = 16

# The command menu text starts at screen x=16 and the rows are 16 pixels
# apart, so 查克拉 occupies (16,56)-(40,72) in the original frame.
CHAKRA_CELLS = (("查", 16), ("克", 24), ("拉", 32))
CHAKRA_TOP = 56

# The panel text region of the command menu.
COMMAND_MENU_TEXT_BOX = (4, 20, 48, 108)


def _differing_pixels(image) -> int:
    """Count non-zero pixels of an "L" image without deprecated APIs."""

    histogram = image.histogram()
    return image.size[0] * image.size[1] - histogram[0]


def captures_available() -> bool:
    return (
        (ORIGINAL / "step-18-A.png").is_file()
        and (REMAKE / "step-18-A.png").is_file()
    )


def _utf8_characters(path: Path, name: str) -> list[str]:
    header = path.read_text(encoding="utf-8")
    match = re.search(
        rf"{name}_utf8_characters\[\]\s*=\s*\{{(.*?)\}};", header, re.DOTALL
    )
    if not match:
        raise AssertionError(f"{name} not found in {path}")
    return [
        value.encode().decode("unicode_escape") if "\\u" in value else value
        for value in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    ]


def _generator():
    import sys

    sys.path.insert(0, str(ROOT))
    from tools import generate_butano_battle_identity_content as generator

    return generator


def _original_indices() -> list[list[int]]:
    """Return the palette indices the original command menu draws 查克拉 with."""

    generator = _generator()
    background = generator.ORIGINAL_UI_BACKGROUND_COLOR
    shadow = set(generator.ORIGINAL_UI_SHADOW_COLORS)
    midtone = set(generator.ORIGINAL_UI_MIDTONE_COLORS)

    def index(color):
        if color == background:
            return 0
        if color in shadow:
            return generator.ORIGINAL_UI_SHADOW_INDEX
        if color in midtone:
            return generator.ORIGINAL_UI_MIDTONE_INDEX
        return generator.ORIGINAL_UI_FOREGROUND_INDEX

    frame = Image.open(ORIGINAL / "step-18-A.png").convert("RGB")
    pixels = frame.load()
    cells = []
    for _, left in CHAKRA_CELLS:
        cells.append(
            [
                index(pixels[left + x, CHAKRA_TOP + y])
                for y in range(GLYPH_HEIGHT)
                for x in range(GLYPH_WIDTH)
            ]
        )
    return cells


class CommandMenuChakraGlyphs(unittest.TestCase):
    def setUp(self):
        self.characters = _utf8_characters(UI_FONT_HEADER, "battle_ui_font")
        self.action_characters = _utf8_characters(
            ACTION_FONT_HEADER, "battle_action_menu_font"
        )

    def test_both_fonts_use_the_same_character_order(self):
        self.assertEqual(
            self.characters,
            self.action_characters,
            "the two atlases must be indexed by the same character list",
        )

    def test_action_menu_atlas_holds_the_full_height_chakra_tiles(self):
        atlas = Image.open(
            GRAPHICS / "battle_action_menu_font.bmp"
        ).convert("P")
        pixels = atlas.load()
        expected = _original_indices()
        for (character, _), wanted in zip(CHAKRA_CELLS, expected):
            with self.subTest(character=character):
                index = self.characters.index(character)
                top = (ASCII_GLYPH_COUNT + index) * GLYPH_HEIGHT
                actual = [
                    pixels[x, top + y]
                    for y in range(GLYPH_HEIGHT)
                    for x in range(GLYPH_WIDTH)
                ]
                self.assertEqual(
                    actual,
                    wanted,
                    f"{character} in the action-menu atlas is not the "
                    f"full-height tile the original command menu draws",
                )

    def test_shared_ui_cell_stays_compact_for_the_status_hud(self):
        """The shared cell must keep matching the verified status HUD."""

        atlas = Image.open(GRAPHICS / "battle_ui_font.bmp").convert("P")
        pixels = atlas.load()
        for character, _ in CHAKRA_CELLS:
            with self.subTest(character=character):
                index = self.characters.index(character)
                top = (ASCII_GLYPH_COUNT + index) * GLYPH_HEIGHT
                rows = [
                    row
                    for row in range(GLYPH_HEIGHT)
                    if any(
                        pixels[x, top + row] != 0 for x in range(GLYPH_WIDTH)
                    )
                ]
                self.assertLess(
                    len(rows),
                    GLYPH_HEIGHT,
                    f"{character} must stay a compact glyph in the shared UI "
                    f"atlas, not a full-height one",
                )
                self.assertLessEqual(
                    len(rows),
                    8,
                    f"{character} must stay an 8-row compact glyph in the "
                    f"shared UI atlas",
                )

    def test_command_menu_draws_chakra_with_the_action_menu_font(self):
        source = SCENE.read_text(encoding="utf-8")
        match = re.search(
            r"^void render_command_menu_text\(.*?^\}", source,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match, "render_command_menu_text not found")
        body = match.group(0)
        self.assertIn(
            "action_generator", body,
            "render_command_menu_text must be able to draw one label with the "
            "action-menu font",
        )
        self.assertRegex(
            body,
            r"battle_command_type::replenish_chakra\s*\?\s*action_generator",
            "the chakra label must be the one drawn with the action-menu font",
        )


@unittest.skipUnless(
    captures_available(), "recorded S49 captures are not available"
)
class CommandMenuChakraPixels(unittest.TestCase):
    def test_command_menu_text_matches_the_original(self):
        original = Image.open(ORIGINAL / "step-18-A.png").convert("RGB")
        remake = Image.open(REMAKE / "step-18-A.png").convert("RGB")
        difference = ImageChops.difference(original, remake).convert("L")
        cell = difference.crop(COMMAND_MENU_TEXT_BOX)
        differing = _differing_pixels(cell)
        self.assertEqual(
            differing,
            0,
            "the command menu text panel still differs from the original",
        )


if __name__ == "__main__":
    unittest.main()
