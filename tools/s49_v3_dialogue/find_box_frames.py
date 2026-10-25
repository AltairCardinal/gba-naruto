"""Scratch: find the frames of a capture that show the dialogue box.

Answers one question: in which frames of a capture is the dialogue box on
screen, and does it carry text?

The box's paper colour of the original is (231, 247, 214); a frame that shows
the box has a large share of that colour in the box band.  The text of a line
lives in rows 118..140 of the band.

Usage:
    python tools/s49_v3_dialogue/find_box_frames.py <frames-dir> [--glob pattern]
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

BOX_BAND = (8, 103, 232, 150)
PAPER = (231, 247, 214)
TEXT_ROWS = (118, 140)


def analyse(path: pathlib.Path):
    with Image.open(path) as image:
        crop = image.convert("RGB").crop(BOX_BAND)
        width, height = crop.size
        pixels = list(crop.getdata())
    paper = sum(1 for pixel in pixels if pixel == PAPER)
    counts = {}
    for pixel in pixels:
        counts[pixel] = counts.get(pixel, 0) + 1
    background = max(counts, key=counts.get)
    top = TEXT_ROWS[0] - BOX_BAND[1]
    bottom = TEXT_ROWS[1] - BOX_BAND[1]
    text_ink = 0
    for y in range(top, min(bottom, height)):
        for x in range(width):
            if pixels[y * width + x] != background:
                text_ink += 1
    return paper / len(pixels), text_ink


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames")
    parser.add_argument("--glob", default="*.png")
    args = parser.parse_args()
    directory = pathlib.Path(args.frames)
    files = sorted(directory.glob(args.glob))
    print(f"{directory}  {len(files)} frames")
    shown = 0
    for path in files:
        paper, text_ink = analyse(path)
        if paper > 0.5:
            shown += 1
            flag = "TEXT" if text_ink > 30 else "box "
            print(f"  {path.stem:<22} paper={paper:.3f} text={text_ink:>6} {flag}")
    print(f"  -> {shown} frames show the box")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
