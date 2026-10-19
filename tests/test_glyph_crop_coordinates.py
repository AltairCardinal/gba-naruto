#!/usr/bin/env python3
"""The glyph crop table must actually point at the glyph it claims to crop.

`SCENARIO_41_ORIGINAL_GLYPH_SOURCES` hardcodes an ``(left, top)`` for 100 CJK
glyphs and crops the cell out of a recorded original-game screenshot.  Nothing
downstream re-reads those screenshots, so a coordinate that is one 8-pixel slot
off silently ships the wrong glyph into the ROM: S49 rendered 木叶丸 as 打木叶
because 木/叶/丸 were one slot early on the menu title line of
``menu-0.png``.

The expected coordinates below were read off the restored source image, glyph by
glyph.  Entries whose source image is gone are deliberately absent from the
table below rather than guessed, and `test_entries_without_a_verified_source`
records that gap so it cannot be quietly forgotten.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

MENU_0 = "artifacts/scenario-41-prebattle-reference-v1/screens/menu-0.png"

# Characters read off menu-0.png at (left, top).  The menu title line is an
# exact 8-pixel grid reading 使(88) 劲(96) 打(104) 木(112) 叶(120) 丸(128)
# 吧(136) ！(144).
VERIFIED: dict[str, tuple[int, int]] = {
    # title line — the shipped table was one whole slot early for all of these
    "木": (112, 8),
    "叶": (120, 8),
    "丸": (128, 8),
    "吧": (136, 8),
    "！": (144, 8),
    # instruction lines — these were already correct and must stay correct
    "练": (24, 40),
    "习": (32, 40),
    "。": (40, 40),
    "用": (8, 56),
    "「": (16, 56),
    "者": (32, 56),
    "组": (40, 56),
    "拳": (56, 56),
    "」": (64, 56),
    "队": (80, 56),
    "伍": (88, 56),
    "·": (96, 56),
    "装": (104, 56),
    "备": (112, 56),
    "不": (8, 72),
    "使": (24, 72),
    "和": (56, 72),
    "看": (88, 72),
    "地": (96, 72),
    "图": (104, 72),
    "开": (80, 88),
    "始": (88, 88),
    "储": (80, 104),
    "存": (88, 104),
}

# Characters the shipped table sources from menu-0.png but which do not exist
# anywhere in that image, so no correct coordinate could be read off it.
NEEDS_OTHER_SOURCE = ("援", "助", "脱", "为", "胜")

S49_COMMAND_MENU = (
    "artifacts/s49-original-ui-reference-v1/screens/command-menu-0.png"
)
# Characters read off the S49 command menu.  The shipped table pointed them at a
# scenario-41 screenshot whose crops sat four pixels left of the glyph, which cut
# the panel's vertical border into the tile: 移 and 休 came out as sixteen rows
# of solid ink, which is the black bar S49 drew beside 移動 and 休息.
VERIFIED_COMMAND_MENU: dict[str, tuple[int, int]] = {
    "移": (16, 24),
    "休": (16, 72),
    "息": (24, 72),
}
# 查克拉 is the counter-example to "one glyph, one size".  The original status
# HUD draws 查/克/拉 as 8-row compact glyphs and the remake matches it there
# pixel for pixel; the S49 command menu draws the same three full height.  One
# shared atlas cell cannot be both, so the shared cell stays compact and the
# full-height command-menu rendering is a separate, still-missing atlas.
COMPACT_IN_STATUS_HUD = ("查", "克", "拉")


def _generator():
    import sys

    sys.path.insert(0, str(ROOT))
    from tools import generate_butano_battle_identity_content as generator

    return generator


class GlyphCropCoordinatesTest(unittest.TestCase):
    def setUp(self):
        self.sources = _generator().SCENARIO_41_ORIGINAL_GLYPH_SOURCES

    def test_menu_zero_source_is_restored(self):
        self.assertTrue(
            (ROOT / MENU_0).is_file(),
            f"{MENU_0} is required to verify the glyph crop table")

    def test_verified_characters_are_cropped_from_their_real_slot(self):
        wrong = {}
        for character, expected in VERIFIED.items():
            declared = self.sources.get(character)
            if declared is None:
                wrong[character] = (None, expected)
                continue
            _, left, top = declared
            if (left, top) != expected:
                wrong[character] = ((left, top), expected)
        self.assertEqual(
            wrong, {},
            "glyph crops point one 8-pixel slot off, which ships the wrong glyph")

    def test_verified_characters_still_come_from_menu_zero(self):
        moved = {
            character: self.sources[character][0]
            for character in VERIFIED
            if character in self.sources and self.sources[character][0] != MENU_0
        }
        self.assertEqual(moved, {}, "a verified crop no longer uses the image it was read off")

    def test_entries_without_a_verified_source_are_still_flagged(self):
        """The gap must stay visible: these three claim menu-0 but are not in it."""
        for character in NEEDS_OTHER_SOURCE:
            with self.subTest(character=character):
                declared = self.sources.get(character)
                self.assertIsNotNone(declared, f"{character} disappeared from the table")
                self.assertNotIn(
                    character, VERIFIED,
                    f"{character} was given a verified coordinate without one being read off an image")


class S49CommandMenuCropCoordinatesTest(unittest.TestCase):
    """移/休/息/查/克/拉 must crop from the S49 command menu at read-off slots."""

    def setUp(self):
        self.generator = _generator()
        self.sources = self.generator.SCENARIO_41_ORIGINAL_GLYPH_SOURCES

    def test_command_menu_source_is_committed(self):
        self.assertTrue(
            (ROOT / S49_COMMAND_MENU).is_file(),
            f"{S49_COMMAND_MENU} is required to verify these crops")

    def test_coordinates_match_the_slots_read_off_the_frame(self):
        wrong = {}
        for character, expected in VERIFIED_COMMAND_MENU.items():
            declared = self.sources.get(character)
            if declared is None:
                wrong[character] = (None, expected)
                continue
            source, left, top = declared
            if source != S49_COMMAND_MENU:
                wrong[character] = (source, S49_COMMAND_MENU)
            elif (left, top) != expected:
                wrong[character] = ((left, top), expected)
        self.assertEqual(wrong, {}, "S49 command-menu crops point at the wrong slot")

    def test_chakra_stays_compact_for_the_status_hud(self):
        """The shared cell must keep matching the verified status HUD.

        Widening this cell to the full-height command-menu glyph breaks every
        frame that shows the chakra label in the status bar, which the remake
        already matches the original on.
        """
        compact = self.generator.SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS
        for character in COMPACT_IN_STATUS_HUD:
            with self.subTest(character=character):
                self.assertIn(
                    character, compact,
                    f"{character} must stay an 8-row compact glyph")


class ShippedAtlasMatchesTheSourceTest(unittest.TestCase):
    """The shipped atlas tiles must hold the glyphs the corrected table names.

    This is the emulator-free half of the gate: it regenerates the reference
    atlas from the corrected table and compares each affected tile against the
    built ``battle_ui_font.bmp``, so a regenerated-but-wrong atlas cannot pass.
    Comparison is on palette indices, because the generator recolours every crop
    into a four-colour palette before it lands in the atlas.
    """

    def setUp(self):
        from tools.butano.repatch_battle_ui_font_glyphs import (
            build_reference_atlas,
            characters_with_available_sources,
        )

        self.atlas = ROOT / "butano-sequel/graphics/battle_ui_font.bmp"
        if not self.atlas.is_file():
            self.skipTest("the battle UI font atlas is not present")
        with Image.open(self.atlas) as image:
            self.atlas_image = image.copy()
        self.reference = build_reference_atlas(characters_with_available_sources())
        self.characters = _generator().load_identity_content(ROOT)["utf8_characters"]
        self.sources = _generator().SCENARIO_41_ORIGINAL_GLYPH_SOURCES

    def test_affected_tiles_hold_the_correct_glyph(self):
        wrong = []
        for character in list(VERIFIED) + list(VERIFIED_COMMAND_MENU):
            if character not in self.sources:
                wrong.append((character, "missing from the table"))
                continue
            index = self.characters.index(character)
            offset = (94 + index) * 16
            expected = self.reference.crop((0, offset, 8, offset + 16)).tobytes()
            actual = self.atlas_image.crop((0, offset, 8, offset + 16)).tobytes()
            if expected != actual:
                wrong.append((character, 94 + index))
        self.assertEqual(wrong, [], f"atlas tiles hold the wrong glyph: {wrong}")

    def test_the_name_characters_are_not_shifted(self):
        """木/叶/丸 must be distinct tiles, not the same cell three times."""
        tiles = []
        for character in ("木", "叶", "丸"):
            index = self.characters.index(character)
            offset = (94 + index) * 16
            tiles.append(self.atlas_image.crop((0, offset, 8, offset + 16)).tobytes())
        self.assertEqual(len(set(tiles)), 3,
                         "木/叶/丸 share a tile, which renders them as one glyph")


if __name__ == "__main__":
    unittest.main()
