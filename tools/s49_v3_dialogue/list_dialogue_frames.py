"""Scratch: list the dialogue screens of a capture with their text ink.

Answers one question: which frames of a capture show a dialogue box, and
which of them carry text?

The dialogue box of the original lives in the lower part of the screen; its
interior is the paper colour.  A frame that shows the box has a large run of
paper coloured pixels in the band; a frame that shows text on top of it has
ink in the middle of the box.

Usage:
    python tools/s49_v3_dialogue/list_dialogue_frames.py <frames-dir> [--glob pattern]
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

BOX_BAND = (8, 103, 232, 150)
TEXT_ROWS = (118, 140)


def analyse(path: pathlib.Path):
    with Image.open(path) as image:
        crop = image.convert("RGB").crop(BOX_BAND)
        width, height = crop.size
        pixels = list(crop.getdata())
    counts = {}
    for pixel in pixels:
        counts[pixel] = counts.get(pixel, 0) + 1
    background = max(counts, key=counts.get)
    ink = sum(1 for pixel in pixels if pixel != background)
    # The text rows of the box, where the line itself lives.
    top = TEXT_ROWS[0] - BOX_BAND[1]
    bottom = TEXT_ROWS[1] - BOX_BAND[1]
    text_ink = 0
    for y in range(top, min(bottom, height)):
        for x in range(width):
            if pixels[y * width + x] != background:
                text_ink += 1
    return ink, text_ink, background


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames")
    parser.add_argument("--glob", default="*.png")
    args = parser.parse_args()
    directory = pathlib.Path(args.frames)
    files = sorted(directory.glob(args.glob))
    print(f"{directory}  {len(files)} frames")
    for path in files:
        ink, text_ink, background = analyse(path)
        flag = "TEXT" if text_ink > 30 else ("box " if ink > 500 else "     ")
        print(f"  {path.stem:<22} ink={ink:>6} text={text_ink:>6} {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
