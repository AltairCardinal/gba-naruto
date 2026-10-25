#!/usr/bin/env python3
"""When does the original show the 「開始」 title, and does the remake reach it?

Answers one question: the original's deployment screen shows the title on one
beat; the remake has to reach the same beat for the title to appear there.
The title's own pixels are four greys, so the beat is found by counting them
in the region the original's title occupies; the deployment text ("... DEPLOY
/ START / READY") is counted in the top left corner, where the runtime draws
it, to tell the beats apart.

Usage::

    python tools/s49_v3_dialogue/scan_title_beat.py \\
        build/s49-pairing/walk5/dense-original \\
        build/s49-pairing/walk5/dense-remake
"""

from __future__ import annotations

import argparse
import pathlib

from PIL import Image

GREYS = {(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)}

# The region the original's title occupies.
TITLE = (41, 42, 226, 125)
# The region the runtime draws the deployment text in.
TEXT = (0, 0, 70, 40)


def greys(image: Image.Image, box) -> int:
    crop = image.convert("RGB").crop(box)
    return sum(1 for pixel in crop.getdata() if pixel in GREYS)


def scan(directory: pathlib.Path) -> list[tuple[str, int, int]]:
    rows = []
    for path in sorted(directory.glob("*.png")):
        with Image.open(path) as image:
            rows.append((path.stem, greys(image, TITLE), greys(image, TEXT)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+")
    args = parser.parse_args()
    for directory in args.directories:
        path = pathlib.Path(directory)
        rows = scan(path)
        print(f"{path}  {len(rows)} frames")
        peak = max(row[1] for row in rows)
        beat = [row for row in rows if row[1] >= peak * 0.8]
        print(f"  title peak {peak}, frames above 80% of the peak: {len(beat)}")
        if beat:
            print(f"  first {beat[0][0]} (title {beat[0][1]}, text {beat[0][2]}), "
                  f"last {beat[-1][0]} (title {beat[-1][1]}, text {beat[-1][2]})")
        for name, title, text in rows:
            if title >= peak * 0.5:
                print(f"    {name:<24} title {title:>6}  text {text:>6}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
