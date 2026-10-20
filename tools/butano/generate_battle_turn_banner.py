#!/usr/bin/env python3
"""Build the S49 round banner as a strip of 4bpp sprite pieces.

The original ROM shows a round banner between the enemy's turn and the
player's first command:

    回合    1
    玩家  的行动

It is the screen the remake never drew (difference D4), and it is also one
of the two reasons the two walks disagree about animation phase: the original
spends two more button presses before the command menu, so every idle cycle is
further along by the time the menu opens.

The banner is cut out of the original's own frame rather than rebuilt:

* `battle_ui_turn_banner_panel.bmp` is a 32x192 sprite strip holding the
  80x50 panel as six 32x32 pieces, with the words already baked in.  The
  panel is 80 pixels wide and 50 tall, which no single 4bpp sprite can hold
  (the widest 4bpp shape is 64x32), so it is cut into a 3x2 grid of pieces
  and the two narrow edges keep their transparent padding.
* Baking the words into the pixels is deliberate.  The earlier plan drew the
  panel as a regular BG and the words as text, which needs a full screen BG
  (the panel cannot be an object, it is bigger than any sprite) and needs
  glyphs for 回合 / 1 / 的行动 that no font atlas has at the right height.
  Cutting the finished banner out of the original's frame sidesteps both: the
  result is pixel exact by construction.

The panel's lower edge is a dither: the original alternates the panel's own
colours with the dithered grass of the battlefield, so the edge has holes.
Those holes are not part of the panel, and they are cut as transparent so the
remake's own battlefield shows through them exactly the way the original's
does.  The colours that belong to the battlefield are recognised by looking
at the rows right below the panel: a colour that also occurs there is
battlefield, everything else belongs to the panel.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.generate_butano_battle_identity_content import (  # noqa: E402
    ORIGINAL_UI_BACKGROUND_COLOR,
)

SOURCE = (
    ROOT
    / "artifacts/s49-original-ui-reference-v1/screens/turn-banner-0.png"
)
GRAPHICS = ROOT / "butano-sequel/graphics"
PANEL_BMP = GRAPHICS / "battle_ui_turn_banner_panel.bmp"
PANEL_JSON = GRAPHICS / "battle_ui_turn_banner_panel.json"
RECEIPT = (
    ROOT
    / "artifacts/s49-original-ui-reference-v1/turn-banner-receipt.json"
)

# The panel's own pixels, measured on the original frame: the outer frame
# starts at (72,40) and the panel is 50 rows tall.  Its bottom two rows are a
# dithered edge, where the panel's own colours alternate with the dithered
# grass of the battlefield.
PANEL_BOX = (72, 40, 152, 90)

# The rows right below the panel.  A colour that occurs there belongs to the
# battlefield, not to the panel.
BACKGROUND_ROWS = (90, 100)

# The panel is cut into a 3x2 grid of 32x32 pieces.  The right column and the
# bottom row keep their transparent padding, because the panel is 80 wide and
# 50 tall.
PIECE_SIZE = 32
PIECE_ORIGINS = (
    (72, 40),
    (104, 40),
    (136, 40),
    (72, 72),
    (104, 72),
    (136, 72),
)


class BannerError(RuntimeError):
    """The banner could not be rebuilt from the recorded original frame."""


def _ui_palette() -> list[tuple[int, int, int]]:
    """The shared UI panel palette, so the banner matches every other panel."""

    with Image.open(GRAPHICS / "battle_ui_result_panel.bmp") as reference:
        flat = reference.getpalette()
    return [
        tuple(flat[index * 3:index * 3 + 3]) for index in range(16)
    ]


def _background_colours(source: Image.Image) -> set[tuple[int, int, int]]:
    """The colours of the battlefield right below the panel."""

    pixels = source.convert("RGB").load()
    left, _, right, _ = PANEL_BOX
    colours: set[tuple[int, int, int]] = set()
    for y in range(*BACKGROUND_ROWS):
        for x in range(left, right):
            colours.add(pixels[x, y])
    return colours


def _panel_colours(
    source: Image.Image,
) -> tuple[list[tuple[int, int, int]], dict[tuple[int, int, int], int]]:
    """Build the sprite palette and map every colour the panel owns onto it.

    The UI panel palette holds the panel's frame colours.  The dithered edge
    adds colours the UI palette does not have (the panel's highlight and the
    shade it takes where it meets the grass), and the panel does not use
    several UI palette entries, so those free slots take the new colours.
    """

    palette = _ui_palette()
    pixels = source.convert("RGB").load()
    left, top, right, bottom = PANEL_BOX
    background = _background_colours(source)

    owned: set[tuple[int, int, int]] = set()
    for y in range(top, bottom):
        for x in range(left, right):
            colour = pixels[x, y]
            if colour not in background:
                owned.add(colour)

    used = {
        index
        for index, colour in enumerate(palette)
        if colour in owned and index != 0
    }
    free = [
        index
        for index in range(1, len(palette))
        if index not in used
    ]
    result: dict[tuple[int, int, int], int] = {}
    for colour in sorted(owned):
        if colour in palette:
            result[colour] = palette.index(colour)
            continue
        if not free:
            raise BannerError(
                f"the panel needs more than {len(palette)} colours"
            )
        index = free.pop(0)
        palette[index] = colour
        result[colour] = index
    return palette, result


def build_panel(source: Image.Image) -> Image.Image:
    """Cut the banner out of the original frame into a strip of sprite pieces.

    The cut fails loudly when the panel contains a colour that the shared UI
    palette does not hold: a silent nearest-colour match would bake a wrong
    pixel into the panel and the difference would only show up as a few
    unexpected pixels in a later screen comparison.
    """

    palette, index_of = _panel_colours(source)
    left, top, right, bottom = PANEL_BOX
    background = _background_colours(source)
    pixels = source.convert("RGB").load()

    unmapped: list[tuple[int, int, tuple[int, int, int]]] = []
    for y in range(top, bottom):
        for x in range(left, right):
            colour = pixels[x, y]
            if colour in background:
                continue
            if colour not in index_of:
                unmapped.append((x, y, colour))
    if unmapped:
        raise BannerError(
            f"the panel holds {len(unmapped)} colours outside the UI "
            f"palette, first at {unmapped[0]}"
        )
    if palette[0] == ORIGINAL_UI_BACKGROUND_COLOR:
        raise BannerError("palette index 0 is not the transparent colour")

    strip = Image.new("P", (PIECE_SIZE, PIECE_SIZE * len(PIECE_ORIGINS)), 0)
    flat_palette: list[int] = []
    for colour in palette:
        flat_palette.extend(colour)
    strip.putpalette(flat_palette)
    strip_pixels = strip.load()
    for index, (piece_x, piece_y) in enumerate(PIECE_ORIGINS):
        for row in range(PIECE_SIZE):
            for column in range(PIECE_SIZE):
                source_x = piece_x + column
                source_y = piece_y + row
                if not (
                    left <= source_x < right and top <= source_y < bottom
                ):
                    strip_pixels[column, index * PIECE_SIZE + row] = 0
                    continue
                colour = pixels[source_x, source_y]
                if colour in background:
                    # A dithered hole that belongs to the battlefield.
                    strip_pixels[column, index * PIECE_SIZE + row] = 0
                    continue
                strip_pixels[column, index * PIECE_SIZE + row] = index_of[
                    colour
                ]
    return strip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args()
    if not args.source.is_file():
        print(f"error: missing {args.source}", file=sys.stderr)
        return 1
    with Image.open(args.source) as raw:
        source = raw.convert("RGB")
    GRAPHICS.mkdir(parents=True, exist_ok=True)
    panel = build_panel(source)
    panel.save(PANEL_BMP, format="BMP", bits=4)
    PANEL_JSON.write_text(
        json.dumps({"type": "sprite", "height": PIECE_SIZE}, indent=2) + "\n",
        encoding="utf-8",
    )
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(
            {
                "schema": "konoha.s49-turn-banner-assets.v2",
                "source": str(args.source.relative_to(ROOT)),
                "panel_box": list(PANEL_BOX),
                "piece_size": PIECE_SIZE,
                "piece_origins": [list(origin) for origin in PIECE_ORIGINS],
                "outputs": {
                    "panel_bmp": str(PANEL_BMP.relative_to(ROOT)),
                    "panel_json": str(PANEL_JSON.relative_to(ROOT)),
                },
                "notes": (
                    "The words are baked into the pixels, so no font atlas is "
                    "needed and the banner is pixel exact by construction.  "
                    "The bottom two rows are a dither: the colours that also "
                    "occur in the rows below the panel belong to the "
                    "battlefield and are cut as transparent."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {PANEL_BMP} ({panel.size[0]}x{panel.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
