#!/usr/bin/env python3
"""Cut the original ROM's dialogue advance icon out of a recorded frame.

The original draws a small spiral shell at the bottom-right of the dialogue box
while a line is still advancing; the remake drew nothing there, which was the
only remaining difference on all three opening dialogue lines (62 pixels).

The icon is 14x9 pixels with four colours, which is not tile aligned, so it is
padded into a 16x16 GBA cell and given its own four-colour palette.  The source
is a recorded original frame and its hash is pinned in the manifest so a
replacement capture cannot silently change what ships.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
GRAPHICS = ROOT / "butano-sequel/graphics"

# Measured off walk-original-a24/step-11-A.png; the same box appears on every
# opening dialogue line, and the remake was blank there.
ICON_BOX = (217, 139, 231, 148)
CELL = 16

# Icon pixels in scan order, top left to bottom right.  Index 0 is the dialogue
# box background, which must stay transparent so the box shows through.
COLORS = {
    (231, 247, 214): 0,  # dialogue box background -> transparent
    (57, 57, 57): 1,     # ink
    (115, 123, 107): 2,  # midtone
    (181, 189, 165): 3,  # highlight
}


class IconError(RuntimeError):
    """The icon could not be cut as declared."""


def cut_icon(source: Path) -> Image.Image:
    """Return the icon cropped from ``source`` at the measured box."""
    with Image.open(source) as image:
        frame = image.convert("RGB")
    crop = frame.crop(ICON_BOX)
    unexpected = {color for color in crop.get_flattened_data() if color not in COLORS}
    if unexpected:
        raise IconError(f"unexpected icon colours: {sorted(unexpected)}")
    return crop


def to_cell(crop: Image.Image) -> Image.Image:
    """Pad the crop into a tile-aligned cell and index it with ``COLORS``."""
    cell = Image.new("P", (CELL, CELL), 0)
    cell.putpalette(
        [channel for color in COLORS for channel in color])
    indexed = Image.new("P", (CELL, CELL), 0)
    indexed.putpalette([channel for color in COLORS for channel in color])
    for y in range(crop.size[1]):
        for x in range(crop.size[0]):
            color = crop.getpixel((x, y))
            if COLORS[color] != 0:
                indexed.putpixel((x, y), COLORS[color])
    cell.paste(indexed)
    return cell


def write_palette_bmp(path: Path) -> None:
    # Butano expects exactly sixteen palette entries; padding past that makes the
    # build fail with "unpack requires a buffer of 1024 bytes".
    channels = [channel for color in COLORS for channel in color]
    channels += [0] * (16 * 3 - len(channels))
    image = Image.new("P", (8, 8))
    image.putpalette(channels)
    image.putdata([index % len(COLORS) for index in range(64)])
    image.save(path, format="BMP", bits=4)
    path.with_suffix(".json").write_text(
        json.dumps({"type": "sprite_palette"}, indent=2) + "\n", encoding="utf-8")


def generate(source: Path) -> dict[str, object]:
    source = Path(source).resolve()
    crop = cut_icon(source)
    cell = to_cell(crop)
    icon_path = GRAPHICS / "battle_ui_dialogue_advance_icon.bmp"
    palette_path = GRAPHICS / "battle_ui_dialogue_advance_palette.bmp"
    cell.save(icon_path, format="BMP", bits=4)
    icon_path.with_suffix(".json").write_text(
        json.dumps({"type": "sprite", "height": CELL}, indent=2) + "\n",
        encoding="utf-8")
    write_palette_bmp(palette_path)
    return {
        "schema": "konoha.dialogue-advance-icon.v1",
        "source": str(source.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "icon_box": list(ICON_BOX),
        "icon_size": [ICON_BOX[2] - ICON_BOX[0], ICON_BOX[3] - ICON_BOX[1]],
        "cell": CELL,
        "colors": {str(color): index for color, index in COLORS.items()},
        "icon_bitmap": str(icon_path.relative_to(ROOT)),
        "icon_sha256": hashlib.sha256(icon_path.read_bytes()).hexdigest(),
        "palette_bitmap": str(palette_path.relative_to(ROOT)),
        "palette_sha256": hashlib.sha256(palette_path.read_bytes()).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = generate(args.source)
    except (IconError, OSError, ValueError) as error:
        print(f"generate_dialogue_advance_icon: {error}")
        return 2
    if args.report:
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
