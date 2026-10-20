#!/usr/bin/env python3
"""The S49 round banner assets must keep matching the original frame.

The banner is the screen the original shows between the enemy's turn and the
player's first command:

    回合    1
    玩家  的行动

One asset carries it: `battle_ui_turn_banner_panel.bmp`, a 32x192 sprite
strip holding the 80x48 panel as six 32x32 pieces.  The panel is bigger than
any 4bpp sprite, so it cannot be one object, and the words are baked into the
pixels rather than drawn as text -- the fonts have no 回合 / 的行动 at the
right height, and baking them makes the banner pixel exact by construction.

The cut is pinned to the original's own banner frame, so the geometry and
every pixel are checked against that frame rather than against a hand written
constant.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GRAPHICS = ROOT / "butano-sequel/graphics"
SOURCE = (
    ROOT / "artifacts/s49-original-ui-reference-v1/screens/turn-banner-0.png"
)
PANEL = GRAPHICS / "battle_ui_turn_banner_panel.bmp"
PANEL_JSON = GRAPHICS / "battle_ui_turn_banner_panel.json"
RECEIPT = (
    ROOT
    / "artifacts/s49-original-ui-reference-v1/turn-banner-receipt.json"
)

TRANSPARENT = (198, 132, 255)
CREAM = (231, 247, 214)

# Measured on the original frame: the panel's own pixels run from (72,40) to
# (151,87).  Row 88 and below are the battlefield's dithered grass, which is
# why an earlier 50 row reading was wrong by two rows.
PANEL_BOX = (72, 40, 152, 90)
# The panel is 50 rows tall.  Its bottom two rows are a dithered edge, where
# the panel's highlight colour alternates with the dithered grass of the
# battlefield; the grass pixels are not part of the panel and stay
# transparent, so the remake's own battlefield shows through them.
DITHERED_ROWS = (88, 90)
BACKGROUND_ROWS = (90, 100)
PIECE_SIZE = 32
PIECE_ORIGINS = (
    (72, 40),
    (104, 40),
    (136, 40),
    (72, 72),
    (104, 72),
    (136, 72),
)


class TurnBannerAssets(unittest.TestCase):
    def setUp(self):
        if not SOURCE.is_file():
            self.skipTest("the original banner frame is unavailable")
        self.source = Image.open(SOURCE).convert("RGB")
        self.source_pixels = self.source.load()
        # A colour that also occurs in the rows below the panel belongs to the
        # battlefield, not to the panel.
        left, _, right, _ = PANEL_BOX
        self.background = {
            self.source_pixels[x, y]
            for y in range(*BACKGROUND_ROWS)
            for x in range(left, right)
        }

    def test_the_source_frame_is_the_original_banner(self):
        """Guard against the source being replaced by something else."""

        pixels = self.source_pixels
        # The cream canvas of the banner, and the green frame outside it.
        self.assertEqual(pixels[110, 60], CREAM)
        self.assertNotEqual(pixels[74, 64], CREAM)

    def test_the_panel_is_a_strip_of_six_square_pieces(self):
        with Image.open(PANEL) as image:
            self.assertEqual(image.mode, "P")
            self.assertEqual(
                image.size,
                (PIECE_SIZE, PIECE_SIZE * len(PIECE_ORIGINS)),
            )

    def test_every_panel_pixel_comes_from_the_original_frame(self):
        with Image.open(PANEL) as image:
            pixels = image.convert("RGB").load()
        left, top, right, bottom = PANEL_BOX
        for index, (piece_x, piece_y) in enumerate(PIECE_ORIGINS):
            for row in range(PIECE_SIZE):
                for column in range(PIECE_SIZE):
                    source_x = piece_x + column
                    source_y = piece_y + row
                    colour = pixels[column, index * PIECE_SIZE + row]
                    inside = (
                        left <= source_x < right
                        and top <= source_y < bottom
                    )
                    source_colour = self.source_pixels[source_x, source_y]
                    if inside and source_colour not in self.background:
                        self.assertEqual(
                            colour,
                            source_colour,
                            f"panel pixel ({source_x},{source_y}) does not "
                            f"match the original frame",
                        )
                    else:
                        # Either outside the panel, or a dithered edge hole
                        # that belongs to the battlefield.
                        self.assertEqual(
                            colour,
                            TRANSPARENT,
                            f"panel pixel ({source_x},{source_y}) is not part "
                            f"of the panel and must be transparent",
                        )

    def test_the_banner_keeps_its_words(self):
        """The words are baked in, so the ink must survive the cut."""

        with Image.open(PANEL) as image:
            pixels = image.convert("RGB").load()

        def strip_pixel(screen_x: int, screen_y: int):
            for index, (piece_x, piece_y) in enumerate(PIECE_ORIGINS):
                if (
                    piece_x <= screen_x < piece_x + PIECE_SIZE
                    and piece_y <= screen_y < piece_y + PIECE_SIZE
                ):
                    return pixels[
                        screen_x - piece_x,
                        index * PIECE_SIZE + screen_y - piece_y,
                    ]
            raise AssertionError(
                f"({screen_x},{screen_y}) is not covered by any piece"
            )

        # 「回合」 on the first line and 「的行动」 on the second one.
        for cell_x, cell_y in ((88, 48), (96, 48), (112, 64), (128, 64)):
            inked = False
            for y in range(cell_y, cell_y + 16):
                for x in range(cell_x, cell_x + 8):
                    if strip_pixel(x, y) != CREAM:
                        inked = True
            self.assertTrue(
                inked,
                f"the banner lost its ink at ({cell_x},{cell_y})",
            )

    def test_the_sidecar_declares_a_sprite_strip(self):
        self.assertEqual(
            json.loads(PANEL_JSON.read_text(encoding="utf-8")),
            {"type": "sprite", "height": PIECE_SIZE},
        )

    def test_the_receipt_records_the_measured_geometry(self):
        if not RECEIPT.is_file():
            self.skipTest("the banner receipt is not written")
        payload = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "konoha.s49-turn-banner-assets.v2")
        self.assertEqual(tuple(payload["panel_box"]), PANEL_BOX)
        self.assertEqual(payload["piece_size"], PIECE_SIZE)
        self.assertEqual(
            tuple(tuple(origin) for origin in payload["piece_origins"]),
            PIECE_ORIGINS,
        )


if __name__ == "__main__":
    unittest.main()
