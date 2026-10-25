"""Scratch: search the whole screen for the title's ink.

Answers one question: does the remake draw the 「開始」 title at all, and if
so, where?

The title's ink is a set of four greys.  The probe reports, per frame, the
bounding box of the greys and the number of grey pixels, so a title that is
drawn off the screen edge shows up as ink in the bottom rows.

Usage:
    python tools/s49_v3_dialogue/probe_title_anywhere.py <frames-dir> [--glob pattern]
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

GREYS = {(33, 33, 33), (107, 107, 107), (181, 181, 181), (255, 255, 255)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames")
    parser.add_argument("--glob", default="*.png")
    args = parser.parse_args()
    directory = pathlib.Path(args.frames)
    files = sorted(directory.glob(args.glob))
    print(f"{directory}  {len(files)} frames")
    rows = []
    for path in files:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            pixels = list(rgb.getdata())
        hits = [(index % rgb.width, index // rgb.width)
                for index, pixel in enumerate(pixels)
                if pixel in GREYS]
        if not hits:
            rows.append((0, path.stem, None))
            continue
        xs = [x for x, _ in hits]
        ys = [y for _, y in hits]
        rows.append((len(hits), path.stem,
                     (min(xs), min(ys), max(xs), max(ys))))
    rows.sort(reverse=True)
    for count, name, bbox in rows[:12]:
        print(f"  {name:<24} greys={count:>6} bbox={bbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
