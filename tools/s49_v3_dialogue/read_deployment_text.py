"""Scratch: read the deployment screen's own text out of a frame.

Answers one question: does the remake's deployment screen reach the
``start_confirmation`` phase (the phase the 「開始」 title belongs to)?

The deployment screen prints "… DEPLOY" and "UNIT n/N" while a unit is still
being placed, and "START" once every unit is placed.  The title replaces that
text, so a frame with the title shows no deployment text at all.

Usage:
    python tools/s49_v3_dialogue/read_deployment_text.py <frame.png> ...
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

# The deployment screen's text sits in the top left of the screen.
REGION = (0, 0, 96, 24)


def main() -> int:
    for argument in sys.argv[1:]:
        path = pathlib.Path(argument)
        with Image.open(path) as image:
            crop = image.convert("RGB").crop(REGION)
            pixels = list(crop.getdata())
        counts = {}
        for pixel in pixels:
            counts[pixel] = counts.get(pixel, 0) + 1
        background = max(counts, key=counts.get)
        ink = sum(1 for pixel in pixels if pixel != background)
        print(f"{path.name:<24} ink={ink:>5}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
