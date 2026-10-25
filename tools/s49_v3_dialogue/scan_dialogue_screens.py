"""Scratch: find the dialogue screens of the original's battle entry.

Answers one question: how many distinct dialogue screens does the original
show at the battle entry, and what text does each one carry?

The input is the original's full battle capture (one PNG per GBA frame).  The
dialogue box of the original lives in the lower part of the screen; the text
of a screen is read out of the box's own band.  Two frames that show the same
screen share the same digest of that band.

Usage:
    python tools/s49_v3_dialogue/scan_dialogue_screens.py <frames-dir> [--from N] [--to N]
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("PIL is required", file=sys.stderr)
    raise


# The dialogue box of the original: the interior of the box, where the text
# is drawn.  The measured rows are 103..152 (stream Z3), and the text itself
# sits in the middle of that band.
TEXT_BAND = (16, 96, 224, 152)


def band_digest(path: pathlib.Path):
    with Image.open(path) as image:
        image = image.convert("RGB")
        crop = image.crop(TEXT_BAND)
        data = crop.tobytes()
    return hashlib.sha256(data).hexdigest(), crop.size


def band_pixels(path: pathlib.Path):
    with Image.open(path) as image:
        image = image.convert("RGB")
        crop = image.crop(TEXT_BAND)
        pixels = list(crop.getdata())
    # Count the pixels that are not the paper colour of the box.
    background = max(set(pixels), key=pixels.count)
    ink = sum(1 for pixel in pixels if pixel != background)
    return ink, background


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames")
    parser.add_argument("--from", dest="start", type=int, default=0)
    parser.add_argument("--to", dest="end", type=int, default=1 << 30)
    args = parser.parse_args()

    directory = pathlib.Path(args.frames)
    files = sorted(directory.glob("frame-*.png"))
    print(f"{len(files)} frames in {directory}")
    previous = None
    screen = 0
    for index, path in enumerate(files):
        if index < args.start:
            continue
        if index >= args.end:
            break
        digest, _ = band_digest(path)
        ink, _ = band_pixels(path)
        if digest != previous:
            screen += 1
            previous = digest
            print(f"screen {screen:>3}  frame {index:>6}  ink={ink:>6}  "
                  f"{digest[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
