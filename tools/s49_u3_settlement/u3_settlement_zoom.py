#!/usr/bin/env python3
"""Zoom the original's settlement screen to count its participant columns.

Stream U3 (wave 10).  S3 (per-person level-up) depends on how many people the
original's settlement screen lists, so the header strip and the number block
are rendered at 4x.

Usage::

    python tools/s49_u3_settlement/u3_settlement_zoom.py
"""

from __future__ import annotations

import pathlib

from PIL import Image

TRUTH = pathlib.Path(
    r"D:\Github\gba-naruto\build\s49-victory-capture\w4\settlement-truth")
OUT = pathlib.Path(r"D:\Github\gba-naruto\build\s49-u3-settlement")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    source = TRUTH / "02-settlement-exp-power-turns.png"
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        print("settlement truth size:", rgb.size)
        rgb.crop((0, 0, 240, 40)).resize((240 * 4, 40 * 4),
                                          Image.LANCZOS).save(
            OUT / "settlement-header.png")
        rgb.crop((0, 100, 240, 160)).resize((240 * 4, 60 * 4),
                                            Image.LANCZOS).save(
            OUT / "settlement-numbers.png")
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
