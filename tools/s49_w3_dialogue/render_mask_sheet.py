"""W3: render the original's reveal mask as a contact sheet.

For every capture of the dense walk the probe computes the mask (black on
screen, not black in the settled capture) and draws it white on black.
The sheet makes the shard structure of the entry transition visible at a
glance, which is what the sprite budget has to reproduce.
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image, ImageDraw

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 160
BLACK_LEVEL = 24
SCALE = 2


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def mask_of(pixels, settled):
    image = Image.new("L", (SCREEN_WIDTH, SCREEN_HEIGHT))
    out = image.load()
    for y in range(SCREEN_HEIGHT):
        for x in range(SCREEN_WIDTH):
            if (max(pixels[x, y]) < BLACK_LEVEL
                    and max(settled[x, y]) >= BLACK_LEVEL):
                out[x, y] = 255
    return image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--settled", type=int, default=276)
    parser.add_argument("--first", type=int, default=259)
    parser.add_argument("--last", type=int, default=274)
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    src = pathlib.Path(args.src)
    settled = load(src, args.settled, args.width).load()

    cells = []
    for index in range(args.first, args.last + 1):
        image = load(src, index, args.width)
        if image is None:
            break
        mask = mask_of(image.load(), settled)
        drawn = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), (0, 0, 0))
        drawn.paste(Image.new("RGB", mask.size, (255, 255, 255)), (0, 0), mask)
        cells.append((index, drawn))

    if not cells:
        return 1
    columns = 4
    rows = (len(cells) + columns - 1) // columns
    pad = 6
    sheet = Image.new(
        "RGB",
        (columns * (SCREEN_WIDTH * SCALE + pad) + pad,
         rows * (SCREEN_HEIGHT * SCALE + pad + 12) + pad),
        (40, 40, 40))
    pen = ImageDraw.Draw(sheet)
    for slot, (index, drawn) in enumerate(cells):
        cx = (slot % columns) * (SCREEN_WIDTH * SCALE + pad) + pad
        cy = (slot // columns) * (SCREEN_HEIGHT * SCALE + pad + 12) + pad
        sheet.paste(drawn.resize((SCREEN_WIDTH * SCALE,
                                   SCREEN_HEIGHT * SCALE),
                                  Image.NEAREST), (cx, cy))
        pen.text((cx, cy - 11), f"capture {index:04d}", fill=(255, 255, 0))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"wrote {out} ({len(cells)} captures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
