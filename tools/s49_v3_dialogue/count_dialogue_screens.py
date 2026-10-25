"""Scratch: count the dialogue screens of a capture.

Answers one question: how many distinct dialogue screens does a capture show,
and at which frames?

A dialogue screen is a state of the dialogue box: the text band of the box is
hashed, and every change of the hash starts a new screen.  Frames whose band
is empty (no text at all) are reported separately.

Usage:
    python tools/s49_v3_dialogue/count_dialogue_screens.py <frames-dir> [--prefix step]
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib

from PIL import Image

# The interior of the dialogue box, where the text and the speaker label sit.
TEXT_BAND = (8, 103, 232, 150)


def analyse(directory: pathlib.Path, pattern: str):
    files = sorted(directory.glob(pattern))
    previous = None
    screens = []
    for path in files:
        with Image.open(path) as image:
            crop = image.convert("RGB").crop(TEXT_BAND)
            data = crop.tobytes()
            pixels = list(crop.getdata())
        digest = hashlib.sha256(data).hexdigest()
        counts = {}
        for pixel in pixels:
            counts[pixel] = counts.get(pixel, 0) + 1
        background = max(counts, key=counts.get)
        ink = sum(1 for pixel in pixels if pixel != background)
        if digest != previous:
            screens.append((path.stem, ink, digest[:12]))
            previous = digest
    return screens


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames")
    parser.add_argument("--pattern", default="*.png")
    args = parser.parse_args()
    directory = pathlib.Path(args.frames)
    screens = analyse(directory, args.pattern)
    print(f"{directory}  {len(screens)} screens")
    for name, ink, digest in screens:
        print(f"  {name:<24} ink={ink:>6}  {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
