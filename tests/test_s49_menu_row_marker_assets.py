#!/usr/bin/env python3
"""The menu row markers must use the tiles the original ROM actually draws.

S49's two left-hand list menus both mark the selected row with an 8x16 arrow,
and the remake picked the wrong tile for each of them.  Read off recorded
frames of the original ROM (the only ground truth that survives):

* command menu (step-18 row 0, step-20 row 2) — sprite box (8,24) / (8,48),
  art occupying rows 6..9, i.e. a short four-row arrow;
* action menu (step-21 row 0) — sprite box (0,40), art occupying rows 4..11,
  i.e. a tall eight-row arrow.

In this project those two silhouettes are `battle_ui_action_cursor` (short) and
`battle_ui_confirmation_cursor` (tall).  The remake drew
`battle_ui_command_cursor` (tall) in the command menu and
`battle_ui_action_cursor` (short) in the action menu, so both menus shipped the
wrong shape.

Two independent checks keep this from regressing:

* `test_menu_draws_the_tile_the_original_draws` pins the asset each render
  function uses, read straight out of the scene source, so the gate survives the
  loss of the recorded captures.
* the capture-based gates diff the marker cell of both menus against the
  original frame and demand zero differing pixels.
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
REMAKE = RUN / "walk-remake-dd-a30-markerfix3"

# The four palette colours every menu row marker is drawn with.  They live in
# `PREPARATION_CURSOR_PALETTE`, which is shared by the marker tiles.
MARKER_COLORS = {
    (181, 189, 165): "A",
    (247, 255, 222): "B",
    (115, 123, 107): "C",
    (57, 57, 57): "D",
}

# Silhouettes read off the original frames, as rows of A/B/C/D with '.' for any
# pixel that is not one of the four marker colours.
ORIGINAL_ACTION_MENU_MARKER = (
    "........",
    "........",
    "........",
    "........",
    "AAA.....",
    "ABBAA...",
    "ABBBBA..",
    "CABBBBA.",
    "ABBBBAC.",
    "CBBAAC..",
    "CAACD...",
    "DCD.....",
    "........",
    "........",
    "........",
    "........",
)
ORIGINAL_COMMAND_MENU_MARKER = (
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "ABBBA...",
    "CBAAAAC.",
    "DCCCCCD.",
    "DDDDD...",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
)

# Tile name -> silhouette, so the expected asset can be named without trusting
# the project's own naming of "command" / "action".
TILES = {
    "battle_ui_action_cursor": ORIGINAL_COMMAND_MENU_MARKER,
    "battle_ui_confirmation_cursor": ORIGINAL_ACTION_MENU_MARKER,
}

# original step -> remake step -> expected marker art -> marker box top-left
MENUS = (
    (18, 18, ORIGINAL_COMMAND_MENU_MARKER, (8, 24)),
    (20, 20, ORIGINAL_COMMAND_MENU_MARKER, (8, 48)),
    (21, 21, ORIGINAL_ACTION_MENU_MARKER, (0, 40)),
)


def captures_available() -> bool:
    return all(
        (ORIGINAL / f"step-{original:02d}-A.png").is_file()
        and (REMAKE / f"step-{remake:02d}-A.png").is_file()
        for original, remake, _, _ in MENUS
    )


def marker_rows(image: Image.Image, box: tuple[int, int]) -> list[str]:
    """Return the marker silhouette at `box` using only the marker palette."""

    pixels = image.convert("RGB").load()
    return [
        "".join(
            MARKER_COLORS.get(pixels[box[0] + dx, box[1] + dy], ".")
            for dx in range(8)
        )
        for dy in range(16)
    ]


def render_function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^void {name}\(.*?^\}}", source, re.MULTILINE | re.DOTALL
    )
    if not match:
        raise AssertionError(f"{name} not found in {SCENE}")
    return match.group(0)


class MenuRowMarkerAssets(unittest.TestCase):
    def test_marker_tiles_have_the_silhouettes_the_original_draws(self) -> None:
        for tile, silhouette in TILES.items():
            with self.subTest(tile=tile):
                image = Image.open(GRAPHICS / f"{tile}.bmp").convert("RGB")
                self.assertEqual(image.size, (8, 16), tile)
                rows = marker_rows(image, (0, 0))
                self.assertEqual(
                    list(silhouette),
                    rows,
                    f"{tile} does not match the tile the original draws",
                )

    def test_menu_draws_the_tile_the_original_draws(self) -> None:
        source = SCENE.read_text(encoding="utf-8")
        cases = (
            ("render_command_menu_text", "battle_ui_action_cursor"),
            ("render_action_menu_text", "battle_ui_confirmation_cursor"),
        )
        for function, expected in cases:
            with self.subTest(function=function):
                body = render_function_body(source, function)
                used = re.findall(
                    r"bn::sprite_items::(battle_ui_\w*cursor)\b", body
                )
                self.assertEqual(
                    used,
                    [expected],
                    f"{function} must draw {expected}, got {used}",
                )

    def test_the_two_menus_do_not_share_a_tile(self) -> None:
        """Guards against a 'fix' that makes both menus render the same art."""

        self.assertNotEqual(
            ORIGINAL_COMMAND_MENU_MARKER, ORIGINAL_ACTION_MENU_MARKER
        )
        for silhouette, rows in (
            (ORIGINAL_COMMAND_MENU_MARKER, 4),
            (ORIGINAL_ACTION_MENU_MARKER, 8),
        ):
            with self.subTest(rows=rows):
                painted = [row for row in silhouette if set(row) != {"."}]
                self.assertEqual(len(painted), rows)
                self.assertEqual(
                    max(len(row.rstrip(".")) for row in silhouette), 7
                )


@unittest.skipUnless(
    captures_available(), "recorded S49 captures are not available"
)
class MenuRowMarkerPixels(unittest.TestCase):
    def assert_same(self, original_step: int, remake_step: int, box, art) -> None:
        original = Image.open(ORIGINAL / f"step-{original_step:02d}-A.png")
        remake = Image.open(REMAKE / f"step-{remake_step:02d}-A.png")
        difference = ImageChops.difference(
            original.convert("RGB"), remake.convert("RGB")
        ).convert("L")
        cell = (
            box[0],
            box[1],
            box[0] + 8,
            box[1] + 16,
        )
        differing = sum(
            1
            for value in difference.crop(cell).get_flattened_data()
            if value > 0
        )
        self.assertEqual(
            differing,
            0,
            f"marker cell {cell} differs between original step "
            f"{original_step:02d} and remake step {remake_step:02d}",
        )
        self.assertEqual(
            marker_rows(original, box),
            list(art),
            "the original frame no longer shows the recorded marker",
        )

    def test_command_menu_marker_matches(self) -> None:
        self.assert_same(18, 18, (8, 24), ORIGINAL_COMMAND_MENU_MARKER)

    def test_command_menu_marker_matches_on_a_lower_row(self) -> None:
        self.assert_same(20, 20, (8, 48), ORIGINAL_COMMAND_MENU_MARKER)

    def test_action_menu_marker_matches(self) -> None:
        self.assert_same(21, 21, (0, 40), ORIGINAL_ACTION_MENU_MARKER)


if __name__ == "__main__":
    unittest.main()
