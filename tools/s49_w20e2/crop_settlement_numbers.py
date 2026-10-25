#!/usr/bin/env python3
"""W20-E2: crop the settlement screen's number block for a close read.

The settlement screen is 240x160.  The four number rows live in the lower
half; the crop keeps the row labels and the three columns so the digits can
be read directly.
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image


def main() -> int:
    source = pathlib.Path(sys.argv[1])
    target = pathlib.Path(sys.argv[2])
    image = Image.open(source).convert("RGB")
    print("size:", image.size)
    crop = image.crop((0, 100, 240, 160)).resize((240 * 3, 60 * 3), Image.NEAREST)
    target.parent.mkdir(parents=True, exist_ok=True)
    crop.save(target)
    print("->", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
