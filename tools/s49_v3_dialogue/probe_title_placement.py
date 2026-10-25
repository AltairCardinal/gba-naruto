"""Scratch: is the title drawn at the wrong place?

Answers one question: does the remake draw the 「開始」 title, and if so, where?

The runtime places the title's five sprites with Butano coordinates, but it
computed them as *screen* coordinates.  The title therefore lands at the
Butano position plus the screen centre, that is 120 pixels to the right and
80 pixels below where it belongs.

The probe counts the title's four greys in three regions:

  * ``should``  the region the original's title occupies,
  * ``shifted`` the region the mis-placed title lands in,
  * ``frame``   the whole screen.

Usage:
    python tools/s49_v3_dialogue/probe_title_placement.py <frames-dir> [--glob pattern]
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

GREYS = {(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)}

# The original's title region, measured from the original's own frames.
SHOULD = (41, 42, 226, 125)
# Where the mis-placed title lands: the screen centre is added to the
# Butano position, so the whole title moves by (120, 80).
SHIFTED = (41 + 120, 42 + 80, 226 + 120, 125 + 80)


def count(image: Image.Image, box) -> int:
    crop = image.convert("RGB").crop(box)
    return sum(1 for pixel in crop.getdata() if pixel in GREYS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames")
    parser.add_argument("--glob", default="*.png")
    args = parser.parse_args()
    directory = pathlib.Path(args.frames)
    files = sorted(directory.glob(args.glob))
    print(f"{directory}  {len(files)} frames")
    print("  frame                    should  shifted   frame")
    best = []
    for path in files:
        with Image.open(path) as image:
            should = count(image, SHOULD)
            shifted = count(image, SHIFTED)
            whole = count(image, (0, 0, 240, 160))
        best.append((whole, should, shifted, path.stem))
    best.sort(reverse=True)
    for whole, should, shifted, name in best[:14]:
        print(f"  {name:<24} {should:>6} {shifted:>8} {whole:>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
