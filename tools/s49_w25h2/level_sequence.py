#!/usr/bin/env python3
"""Segment a frame-by-frame capture into the black field's star levels.

Every frame's lit (non black) pixel count is matched against
``battle_black_field_star::visible_pixels``, so the capture is turned into a
level sequence.  The level sequence's run lengths give the transition's real
length in GBA frames -- which is what the "one beat late" question is about.

Usage::

    python tools/s49_w25h2/level_sequence.py --dir <frames dir>
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image

VISIBLE_PIXELS = (
    7925, 6561, 4677, 3705, 2109, 1477,
    917, 681, 305, 173, 77, 17,
    0,
    21, 81, 161, 280, 590, 744,
    1147, 1703, 2844, 3980, 5561, 7200,
    10624, 12149, 13449, 16007, 20225, 23106,
    25593, 25936, 27291, 29940, 31433, 32630,
)


def lit_pixels(path: pathlib.Path, threshold: int = 8) -> int:
    image = Image.open(path).convert("RGB")
    lit = 0
    for r, g, b in image.get_flattened_data():
        peak = r if r > g else g
        if b > peak:
            peak = b
        if peak > threshold:
            lit += 1
    return lit


def best_level(lit: int) -> tuple[int, int]:
    best = -1
    best_delta = None
    for level, visible in enumerate(VISIBLE_PIXELS):
        delta = abs(visible - lit)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = level
    return best, int(best_delta if best_delta is not None else 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=pathlib.Path, required=True)
    parser.add_argument("--pattern", default="frame-*.png")
    parser.add_argument("--threshold", type=int, default=8)
    parser.add_argument("--max-delta", type=int, default=1200)
    parser.add_argument("--min-lit", type=int, default=0,
                        help="ignore frames with fewer lit pixels than this")
    args = parser.parse_args()

    paths = sorted(args.dir.glob(args.pattern))
    if not paths:
        print(f"no frames in {args.dir}")
        return 1

    runs: list[tuple[str, int, int, int, int]] = []
    for path in paths:
        lit = lit_pixels(path, args.threshold)
        level, delta = best_level(lit)
        if delta > args.max_delta or lit < args.min_lit:
            name = "-"
        else:
            name = f"L{level:02d}"
        if runs and runs[-1][0] == name:
            first, count, last_level, last_lit, last_delta = runs[-1]
            runs[-1] = (first, count + 1, last_level, last_lit, last_delta)
        else:
            runs.append((name, 1, level, lit, delta))

    print(f"{'from':>10} {'to':>10} {'frames':>6}  level  lit     delta")
    for name, count, level, lit, delta in runs:
        print(f"{name:>10} {name:>10} {count:>6}  L{level:02d}  {lit:>6}  {delta:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
