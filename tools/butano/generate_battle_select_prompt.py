#!/usr/bin/env python3
"""Build the S49 map hint prompt as a 4bpp sprite cut from the original.

The original shows a small "SELECT詳細" in the top right corner of the
battlefield, and the remake drew it with the UI font instead, which is wrong
in every measurable way:

* the original's ink is 39x10 pixels, the remake's text is 57x14;
* the original's ASCII is narrow (six letters over 22 pixels) and its two CJK
  cells are 8x8, while the remake uses the 8x16 UI font;
* the original's ink is (247,255,222) with a (57,57,57) outline; the remake
  draws plain white.

The font atlases have neither a narrow ASCII nor the two characters 詳 and 細,
so the prompt cannot be assembled from text.  It is cut out of the original's
own frame instead, which makes it pixel exact by construction: the sprite
keeps the ink and its outline, and everything that belongs to the battlefield
is cut as transparent so the remake's own battlefield shows through.

The sprite is 48x16 and its top left corner sits at screen (192,12), which
puts the ink at the original's measured position, (193,13)-(232,23).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-17-A.png"
)
GRAPHICS = ROOT / "butano-sequel/graphics"
PROMPT_BMP = GRAPHICS / "battle_ui_select_prompt.bmp"
PROMPT_JSON = GRAPHICS / "battle_ui_select_prompt.json"
RECEIPT = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/select-prompt-receipt.json"
)

# The screen rectangle the prompt covers, and where it sits on the screen.
# The region is 48 pixels wide, which is not a sprite width Butano accepts,
# so it is cut into two 32x32 graphics of one asset: the left one holds
# columns 0..31 and the right one columns 32..47, both with the content in
# their top rows.
REGION_ORIGIN = (192, 12)
REGION_SIZE = (48, 16)
PIECE_SIZE = 32
PIECE_COUNT = 2

# The prompt's own colours: the ink and the outline it is drawn with.  The
# outline is what the ink always touches, and it is not one of the
# battlefield's colours.
INK = (247, 255, 222)
OUTLINE = (57, 57, 57)

TRANSPARENT = (198, 132, 255)


class PromptError(RuntimeError):
    """The prompt could not be rebuilt from the recorded original frame."""


def build_prompt(source: Image.Image) -> Image.Image:
    """Cut the prompt out of the original frame."""

    pixels = source.convert("RGB").load()
    left, top = REGION_ORIGIN
    width, height = REGION_SIZE
    if left + width > 240 or top + height > 160:
        raise PromptError("the sprite rectangle falls outside the frame")

    ink_pixels = 0
    outline_pixels = 0
    for y in range(top, top + height):
        for x in range(left, left + width):
            colour = pixels[x, y]
            if colour == INK:
                ink_pixels += 1
            elif colour == OUTLINE:
                outline_pixels += 1
    if ink_pixels == 0:
        raise PromptError("the frame has no prompt ink in the sprite area")

    palette = [TRANSPARENT, INK, OUTLINE]
    flat: list[int] = []
    for colour in palette:
        flat.extend(colour)
    strip = Image.new("P", (PIECE_SIZE, PIECE_SIZE * PIECE_COUNT), 0)
    strip.putpalette(flat)
    strip_pixels = strip.load()
    for y in range(top, top + height):
        for x in range(left, left + width):
            colour = pixels[x, y]
            if colour == INK:
                value = 1
            elif colour == OUTLINE:
                value = 2
            else:
                value = 0
            column = x - left
            piece = column // PIECE_SIZE
            strip_pixels[
                    column % PIECE_SIZE,
                    piece * PIECE_SIZE + (y - top),
            ] = value
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
    sprite = build_prompt(source)
    sprite.save(PROMPT_BMP, format="BMP", bits=4)
    PROMPT_JSON.write_text(
        json.dumps({"type": "sprite", "height": PIECE_SIZE}, indent=2) + "\n",
        encoding="utf-8",
    )
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(
            {
                "schema": "konoha.s49-select-prompt-asset.v1",
                "source": str(args.source.relative_to(ROOT)),
                "region_origin": list(REGION_ORIGIN),
                "region_size": list(REGION_SIZE),
                "piece_size": PIECE_SIZE,
                "piece_count": PIECE_COUNT,
                "ink": list(INK),
                "outline": list(OUTLINE),
                "outputs": {
                    "bmp": str(PROMPT_BMP.relative_to(ROOT)),
                    "json": str(PROMPT_JSON.relative_to(ROOT)),
                },
                "notes": (
                    "The prompt is cut from the original's own frame: the font "
                    "atlases have neither a narrow ASCII nor the two "
                    "characters 詳 and 細."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {PROMPT_BMP} ({sprite.size[0]}x{sprite.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
