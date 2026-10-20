#!/usr/bin/env python3
"""Search a whole walk for a character, by its own idle artwork.

The remake's S49 command menu shows 佐助 where the original shows 木叶丸.  The
question that decides whether this is "wrong character" or "wrong place" is
whether 木叶丸 appears anywhere in the remake's walk at all, so the character's
own art is matched against every frame instead of a single one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

GRAPHICS = ROOT / "butano-sequel/graphics"

# character id -> idle artwork
CHARACTERS = {1: "漩涡鸣人", 2: "宇智波佐助", 3: "春野樱", 30: "木叶丸", 55: "蜜蜂"}


def idle_mask(character: int, frame: int = 0) -> set[tuple[int, int]]:
    path = GRAPHICS / f"battle_unit_{character:02d}_slot_0_part_0_shape_32x64.bmp"
    if not path.is_file():
        return set()
    with Image.open(path) as source:
        image = source.convert("P")
        pixels = image.load()
        width, height = image.size
        if (frame + 1) * 64 > height:
            return set()
        return {
            (x, y)
            for y in range(64)
            for x in range(width)
            if pixels[x, frame * 64 + y] != 0
        }


def best_hit(image: Image.Image, mask: set[tuple[int, int]]) -> float:
    """Best fraction of the character's ink that lands on non-grass pixels."""

    pixels = image.load()
    if not mask:
        return 0.0
    width, height = image.size
    xs = [point[0] for point in mask]
    ys = [point[1] for point in mask]
    best = 0.0
    for oy in range(0, height - 64 + 1, 2):
        for ox in range(0, width - 32 + 1, 2):
            hit = 0
            for x, y in mask:
                px, py = ox + x, oy + y
                if 0 <= px < width and 0 <= py < height:
                    colour = pixels[px, py]
                    # the character's own art is saturated or very dark; grass is not
                    if colour[1] > 120 and colour[2] < 120 or max(colour) < 60:
                        hit += 1
            if hit / len(mask) > best:
                best = hit / len(mask)
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--walk", type=Path, required=True)
    parser.add_argument(
        "--character", type=int, default=30, help="character id to look for"
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    mask = idle_mask(args.character)
    if not mask:
        print(f"character {args.character} has no idle art")
        return 1
    print(
        f"looking for character {args.character} "
        f"({CHARACTERS.get(args.character, '?')}) with {len(mask)} ink pixels "
        f"in {args.walk}"
    )
    for path in sorted(args.walk.glob("step-*.png")):
        image = Image.open(path).convert("RGB")
        score = best_hit(image, mask)
        if score >= args.threshold:
            print(f"  {path.name}: hit {score:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
