"""Scratch: measure the original's 「開始」 title ink.

Answers one question: what is the true extent of the original's title ink,
and how does it split over the five sprite pieces?

The title's ink is a set of four greys on top of the battlefield.  The tool
reports the ink's bounding box and the ink per row and per column, so the
pieces that carry no ink at all can be told from the pieces that do.

Usage:
    python tools/s49_v3_dialogue/measure_title_ink.py <original-frames-dir>
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

GREYS = {(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)}


def main() -> int:
    directory = pathlib.Path(sys.argv[1])
    files = sorted(directory.glob("*.png"))
    best = None
    for path in files:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            pixels = list(rgb.getdata())
        hits = [(index % rgb.width, index // rgb.width)
                for index, pixel in enumerate(pixels)
                if pixel in GREYS]
        if not hits:
            continue
        if best is None or len(hits) > len(best[1]):
            best = (path, hits)
    if best is None:
        print("no title ink found")
        return 1
    path, hits = best
    xs = [x for x, _ in hits]
    ys = [y for _, y in hits]
    print(f"frame: {path.name}")
    print(f"ink pixels: {len(hits)}")
    print(f"bbox: x {min(xs)}..{max(xs)}  y {min(ys)}..{max(ys)}")
    print(f"size: {max(xs) - min(xs) + 1} x {max(ys) - min(ys) + 1}")

    print("\nink per row (y: count):")
    rows = {}
    for _, y in hits:
        rows[y] = rows.get(y, 0) + 1
    for y in sorted(rows):
        print(f"  {y:>3}: {rows[y]:>4}")

    print("\nink per column (x: count), only the columns of the right half:")
    cols = {}
    for x, _ in hits:
        cols[x] = cols.get(x, 0) + 1
    for x in sorted(cols):
        if x >= 195:
            print(f"  {x:>3}: {cols[x]:>4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
