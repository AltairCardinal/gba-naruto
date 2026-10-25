#!/usr/bin/env python3
"""Which outline shades does a capture show?

The original ROM rewrites the unit's OBJ palette index 15 -- the one pixel
outline -- on every frame, so the outline colour of the unit changes from
frame to frame.  The remake used to hold it still at the darkest shade,
which is the mechanism behind the identical walk frames.

This script lists the distinct outline shades (RGB shapes of the form
(0, g, g)) that appear in the unit's own pixel region of every captured
frame, and converts the 8 bit green back into the ROM's 5 bit value.

Usage::

    python tools/s49_idle_outline_colours.py
    python tools/s49_idle_outline_colours.py --dir <capture> --glob 'frame-*.png'
"""

from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

from PIL import Image

DEFAULT_ORIGINAL = Path(
    r"D:\Github\gba-naruto\build\s49-report\capture-original")
DEFAULT_REMAKE = Path(
    r"D:\Github\gba-naruto\build\s49-report\capture-remake")
REGION = (112, 24, 144, 88)


def to_five_bit(green: int) -> int | None:
    """The ROM's 5 bit green of an 8 bit green, or None."""
    for value in range(1, 32, 2):
        if (value << 3) | (value >> 2) == green:
            return value
    return None


def outline_shades(path: Path) -> list[tuple[int, int]]:
    """The (8 bit green, 5 bit green) outline shades of one frame."""
    with Image.open(path) as image:
        crop = image.convert("RGB").crop(REGION)
    counter = Counter(
        colour for colour in crop.getdata()
        if colour[0] == 0 and colour[1] == colour[2] and colour[1] > 0)
    shades = []
    for colour, _count in counter.most_common():
        eight_bit = colour[1]
        five_bit = to_five_bit(eight_bit)
        if five_bit is not None:
            shades.append((eight_bit, five_bit))
    return sorted(shades)


def table(folder: Path, label: str, pattern: str) -> None:
    print(f"=== {label} ===")
    seen: set[int] = set()
    for name in sorted(n for n in os.listdir(folder)
                       if n.endswith(".png")):
        shades = outline_shades(Path(folder) / name)
        seen.update(five for _eight, five in shades)
        rendered = [five for _eight, five in shades]
        print(f"  {name:<22} outline shades (5 bit): {rendered}")
    print(f"  distinct 5 bit shades over the capture: {sorted(seen)}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=DEFAULT_ORIGINAL)
    parser.add_argument("--remake", type=Path, default=DEFAULT_REMAKE)
    parser.add_argument("--dir", type=Path,
                        help="check one directory instead of the two sides")
    parser.add_argument("--glob", default="step-*.png")
    args = parser.parse_args()

    if args.dir:
        table(args.dir, str(args.dir), args.glob)
        return 0
    table(args.original, "ORIGINAL", args.glob)
    table(args.remake, "REMAKE", args.glob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
