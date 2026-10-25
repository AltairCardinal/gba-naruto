"""Scratch: print the dialogue band of a frame as ASCII art.

Answers one question: what does the dialogue box of this frame actually say,
and where exactly does the text sit?

The band is the interior of the dialogue box (rows 96..152 of the 240x160
screen).  Every pixel that differs from the paper colour of the box is
printed as '#', so the speaker label, the text line and the advance icon all
show up.

Usage:
    python tools/s49_v3_dialogue/render_text_band.py <png> [<png> ...]
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

BAND = (0, 96, 240, 156)


def render(path: pathlib.Path) -> None:
    with Image.open(path) as image:
        image = image.convert("RGB")
        crop = image.crop(BAND)
        pixels = list(crop.getdata())
        width, height = crop.size
        counts = {}
        for pixel in pixels:
            counts[pixel] = counts.get(pixel, 0) + 1
        background = max(counts, key=counts.get)
        print(f"{path.name}  background={background}  band={width}x{height}")
        for y in range(height):
            row = []
            for x in range(width):
                pixel = pixels[y * width + x]
                row.append("#" if pixel != background else ".")
            print(f"{96 + y:>3} " + "".join(row))
        print()


def main() -> int:
    for argument in sys.argv[1:]:
        render(pathlib.Path(argument))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
