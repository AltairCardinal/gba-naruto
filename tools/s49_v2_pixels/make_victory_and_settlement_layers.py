#!/usr/bin/env python3
"""Build the remake's victory and settlement screen layers.

What this script does
---------------------
The original's 「勝利」 screen and its settlement screen are static pictures of
the original ROM's own output.  The remake draws both of them as one regular
BG layer each, exactly like the settlement plate and the three level up
layers that were already shipped that way.

Both layers are rebuilt here from the original's own capture
(``build/s49-victory-capture/w4/settlement-truth/``), which is the same source
the shipped settlement plate was made from:

* ``graphics/scenario_41_victory_bg.bmp``      the original's 「勝利」 screen;
* ``graphics/battle_ui_result_plate.bmp``     the original's settlement
  screen without the dynamic content (the numbers and the character
  sprites), with the two static tab headers the original shows in its tab
  bar (「佐助」「小桜」) baked in, exactly like the first two headers
  (「経験値」「鳴人」) that were already baked.

Two facts about Butano's regular BGs drive the layout
------------------------------------------------------
* a regular BG item has to be 256x256 (the graphics tool rejects any other
  size), and
* Butano places a regular BG's *centre* on the given position, so the
  layer's 240x160 content has to sit in the BG's columns 0..239 and rows
  0..159 and the layer has to be created at ``(8, 48)``: that is the
  position that puts the BG's column 0 and its row 0 on the screen's top
  left corner.

Before this script the plate's content sat in the BG's columns 0..239 but
the layer was created at ``(0, 0)``, which put the BG's column 8 and its
row 48 on the screen's top left corner: the settlement screen was drawn 8
columns right and 48 rows too high, and the lower half of the screen was
the transparent filler.

Usage::

    python tools/s49_v2_pixels/make_victory_and_settlement_layers.py
"""

from __future__ import annotations

import pathlib
import sys
from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[2]
G = pathlib.Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")
TRUTH = REPO / "build" / "s49-victory-capture" / "w4" / "settlement-truth"

SCREEN_W = 240
SCREEN_H = 160
CANVAS = 256
OFFSET_X = 0

#: The tab headers of the original's settlement screen that the plate did
#: not have: 「佐助」 (tab 3) and 「小桜」 (tab 4).
TAB_HEADERS = ((150, 170, 6, 25), (206, 226, 6, 25))


def fail(message: str) -> int:
    print("error: " + message, file=sys.stderr)
    return 1


def palette_map(palette: list[int]) -> dict[tuple[int, int, int], int]:
    mapping: dict[tuple[int, int, int], int] = {}
    for index in range(256):
        entry = tuple(palette[index * 3:index * 3 + 3])
        mapping.setdefault(entry, index)
    return mapping


def build_settlement_plate(truth_settlement: Image.Image) -> int:
    """Rebuild the settlement plate from the shipped plate's own palette."""
    plate = Image.open(G / "battle_ui_result_plate.bmp")
    if plate.mode != "P":
        return fail("the settlement plate is not a palettised image")
    palette = plate.getpalette()
    index_of = palette_map(palette)
    old_pixels = [list(plate.getdata())]
    # The file is rewritten below, so the reader has to let go of it first.
    plate.close()

    canvas = Image.new("P", (CANVAS, CANVAS), 0)
    pixels = canvas.load()
    for y in range(SCREEN_H):
        for x in range(SCREEN_W):
            # The source image is CANVAS pixels wide, not SCREEN_W.
            pixels[x + OFFSET_X, y] = old_pixels[0][y * CANVAS + x]

    truth_pixels = truth_settlement.load()
    missing = set()
    pasted = 0
    for x0, x1, y0, y1 in TAB_HEADERS:
        for y in range(y0, y1):
            for x in range(x0, x1):
                colour = truth_pixels[x, y]
                index = index_of.get(colour)
                if index is None:
                    missing.add(colour)
                    continue
                if pixels[x + OFFSET_X, y] == index:
                    continue
                pixels[x + OFFSET_X, y] = index
                pasted += 1
    if missing:
        print("note: %d colours of the tab headers are not in the plate's "
              "palette: %s" % (len(missing), sorted(missing)[:6]),
              file=sys.stderr)
        return fail("the tab header colours do not fit the plate's palette")
    canvas.putpalette(palette)
    canvas.save(G / "battle_ui_result_plate.bmp")
    print("wrote the settlement plate (%d tab header pixels)" % pasted)
    return 0


def build_victory_screen(truth_victory: Image.Image) -> int:
    """Write the original's 「勝利」 screen as a regular BG layer."""
    colours = truth_victory.getcolors(maxcolors=1 << 20)
    print("the victory screen has %d distinct colours" % len(colours))
    if len(colours) > 255:
        return fail("the victory screen needs more than 255 visible colours")
    used = {colour for _, colour in colours}
    transparent = None
    for candidate in ((255, 0, 255), (0, 255, 0), (0, 255, 255)):
        if candidate not in used:
            transparent = candidate
            break
    if transparent is None:
        return fail("no free colour for the transparent palette entry")

    index_of = {transparent: 0}
    new_palette = list(transparent)
    for _, colour in sorted(colours, key=lambda item: (-item[0], item[1])):
        if colour in index_of:
            continue
        index_of[colour] = len(new_palette) // 3
        new_palette.extend(colour)
    while len(new_palette) < 768:
        new_palette.append(0)

    source = truth_victory.load()
    victory = Image.new("P", (CANVAS, CANVAS), 0)
    pixels = victory.load()
    for y in range(SCREEN_H):
        for x in range(SCREEN_W):
            pixels[x + OFFSET_X, y] = index_of[source[x, y]]
    victory.putpalette(new_palette)
    victory.save(G / "scenario_41_victory_bg.bmp")
    print("wrote the victory screen (%d palette entries, transparent %s)"
          % (len(new_palette) // 3, transparent))
    return 0


def main() -> int:
    truth_settlement = Image.open(
        TRUTH / "02-settlement-exp-power-turns.png").convert("RGB")
    truth_victory = Image.open(
        TRUTH / "01-victory.png").convert("RGB")
    status = build_settlement_plate(truth_settlement)
    if status:
        return status
    return build_victory_screen(truth_victory)


if __name__ == "__main__":
    raise SystemExit(main())
