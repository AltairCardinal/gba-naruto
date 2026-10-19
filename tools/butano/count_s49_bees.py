#!/usr/bin/env python3
"""Count the bees the original has on the field and the remake does not.

S49 is "protect 木叶丸 from the bees", yet the remake's move-range screen shows
no bees at all, and the original's shows two.  The same screen also shows a
different character standing in the middle: 木叶丸 in the original, 佐助 in the
remake.

Both facts are measured here by template matching rather than by eye.  The bee
is cut out of the original's own frame and searched for in both frames, so the
count cannot drift with the scenery.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]

ORIGINAL_FRAME = (
    ROOT / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-16-A.png"
)
REMAKE_FRAME = (
    ROOT
    / "artifacts/s49-fidelity-20261019-v1/walk-remake-dd-a30-chakrafix/step-19-A.png"
)

# The upper-left bee in the original's move-range screen, and the lower-left
# one, as read off the recorded frame.
BEE_BOXES = ((44, 8, 62, 30), (12, 120, 30, 142))


def _crop(image: Image.Image, box) -> Image.Image:
    return image.convert("RGB").crop(box)


def _distinctive(pixel) -> bool:
    """True for the bee's own pixels: near-white wings or near-black body.

    The grass and the rocks never reach either end of the range, so only these
    pixels are scored; that keeps a coincidence in the scenery from counting as
    a bee.
    """

    red, green, blue = pixel
    if red > 225 and green > 225 and blue > 225:
        return True
    return red < 60 and green < 60 and blue < 60


def _match_score(haystack: Image.Image, needle: Image.Image) -> int:
    """Count the needle's distinctive pixels that appear in the haystack."""

    hay = haystack.load()
    pin = needle.load()
    width, height = needle.size
    best = 0
    for oy in range(0, haystack.size[1] - height + 1):
        for ox in range(0, haystack.size[0] - width + 1):
            score = 0
            for y in range(height):
                for x in range(width):
                    if not _distinctive(pin[x, y]):
                        continue
                    a = pin[x, y]
                    b = hay[ox + x, oy + y]
                    if abs(a[0] - b[0]) < 24 and abs(a[1] - b[1]) < 24 and abs(a[2] - b[2]) < 24:
                        score += 1
            if score > best:
                best = score
    return best


def _samples(needle: Image.Image) -> int:
    pin = needle.load()
    return sum(
        1
        for y in range(needle.size[1])
        for x in range(needle.size[0])
        if _distinctive(pin[x, y])
    )


def main() -> int:
    if not ORIGINAL_FRAME.is_file() or not REMAKE_FRAME.is_file():
        print("the recorded walks are unavailable")
        return 1
    original = Image.open(ORIGINAL_FRAME)
    remake = Image.open(REMAKE_FRAME)
    for index, box in enumerate(BEE_BOXES):
        needle = _crop(original, box)
        total = _samples(needle)
        in_original = _match_score(original, needle)
        in_remake = _match_score(remake, needle)
        print(
            f"bee {index}: original {in_original}/{total} matching samples, "
            f"remake {in_remake}/{total}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
