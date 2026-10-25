#!/usr/bin/env python3
"""Identify the black-field star level of a captured frame.

The star mask cuts a four pointed hole out of a full screen black mask.  The
hole's area is the star level's signature: ``battle_black_field_star::
visible_pixels`` holds the number of pixels every one of the 37 levels leaves
visible, measured on the original's own frames.

So the lit (non black) pixel count of a captured frame names the level, and the
level names the position inside the transition.  That is how the "one beat
late" claim is measured instead of guessed.

Usage::

    python tools/s49_w25h2/star_level.py --dir <capture dir> [--prefix step]
    python tools/s49_w25h2/star_level.py --dir <capture dir> --reference orig
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[2]

# battle_black_field_star::visible_pixels (37 levels, measured on the
# original's own frames).
VISIBLE_PIXELS = (
    7925, 6561, 4677, 3705, 2109, 1477,
    917, 681, 305, 173, 77, 17,
    0,
    21, 81, 161, 280, 590, 744,
    1147, 1703, 2844, 3980, 5561, 7200,
    10624, 12149, 13449, 16007, 20225, 23106,
    25593, 25936, 27291, 29940, 31433, 32630,
)

# The level's phase inside the transition.
FADE_OUT_LEVELS = 12
BLACK_LEVEL = 12
FADE_IN_LEVELS = 12
GROWTH_LEVELS = 12
LEVEL_COUNT = 37

# One level is two GBA frames (one scene frame).
GBA_PER_LEVEL = 2


def lit_pixels(path: pathlib.Path, threshold: int = 8) -> tuple[int, int]:
    """Return (lit pixels, total pixels) of a frame."""
    image = Image.open(path).convert("RGB")
    data = image.get_flattened_data()
    lit = 0
    for r, g, b in data:
        peak = r if r > g else g
        if b > peak:
            peak = b
        if peak > threshold:
            lit += 1
    return lit, len(data)


def best_level(lit: int) -> tuple[int, int]:
    """Return (level, absolute difference) of the level that fits best."""
    best = -1
    best_delta = None
    for level, visible in enumerate(VISIBLE_PIXELS):
        delta = abs(visible - lit)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = level
    return best, int(best_delta if best_delta is not None else 0)


def phase_of(level: int) -> str:
    if level < 0:
        return "no mask"
    if level < FADE_OUT_LEVELS:
        return f"fade-out level {level}"
    if level == BLACK_LEVEL:
        return "black hold"
    if level < BLACK_LEVEL + 1 + FADE_IN_LEVELS:
        return f"fade-in level {level - BLACK_LEVEL - 1}"
    return f"growth level {level - BLACK_LEVEL - 1 - FADE_IN_LEVELS}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=pathlib.Path, required=True)
    parser.add_argument("--pattern", default="step-*.png")
    parser.add_argument("--threshold", type=int, default=8)
    args = parser.parse_args()

    paths = sorted(args.dir.glob(args.pattern))
    if not paths:
        print(f"no frames in {args.dir}")
        return 1
    print(f"{'frame':<20} {'lit':>7} {'level':>5} {'delta':>6}  phase")
    for path in paths:
        lit, total = lit_pixels(path, args.threshold)
        level, delta = best_level(lit)
        print(f"{path.name:<20} {lit:>7} {level:>5} {delta:>6}  "
              f"{phase_of(level)}  ({100.0 * lit / total:.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
