"""Scratch: does a capture show the 「開始」 title?

Answers one question: in which frames of a capture is the title's screen box
(41, 42) to (205, 112) covered by the title's ink?

The title's ink is a set of four greys; the box's background is the
battlefield.  The probe counts the pixels of the box that are one of the four
greys, which is what the title's brush stroke and its outline are made of.

Usage:
    python tools/s49_v3_dialogue/probe_title_region.py <frames-dir> [--glob pattern]
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

REGION = (41, 42, 205, 112)
GREYS = {(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames")
    parser.add_argument("--glob", default="*.png")
    args = parser.parse_args()
    directory = pathlib.Path(args.frames)
    files = sorted(directory.glob(args.glob))
    print(f"{directory}  {len(files)} frames")
    best = []
    for path in files:
        with Image.open(path) as image:
            crop = image.convert("RGB").crop(REGION)
            pixels = list(crop.getdata())
        hits = sum(1 for pixel in pixels if pixel in GREYS)
        best.append((hits, path.stem))
    best.sort(reverse=True)
    for hits, name in best[:20]:
        print(f"  {name:<24} title_greys={hits}")
    print(f"  median={sorted(h for h, _ in best)[len(best) // 2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
