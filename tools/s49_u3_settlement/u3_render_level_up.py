#!/usr/bin/env python3
"""Render the original's four level-up screens at high magnification.

Stream U3 (wave 10).  The per-person level-up screens are the S3 content
source; the headers name the character and the rows list the stat deltas, so
the transcription has to be exact.

Usage::

    python tools/s49_u3_settlement/u3_render_level_up.py
"""

from __future__ import annotations

import pathlib

from PIL import Image

TRUTH = pathlib.Path(
    r"D:\Github\gba-naruto\build\s49-victory-capture\w4\settlement-truth")
OUT = pathlib.Path(r"D:\Github\gba-naruto\build\s49-u3-settlement")

NAMES = (
    "03-levelup-naruto.png",
    "04-levelup-konohamaru.png",
    "05-levelup-sasuke.png",
    "06-levelup-sakura.png",
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        source = TRUTH / name
        if not source.is_file():
            print(f"MISSING {source}")
            continue
        with Image.open(source) as image:
            rgb = image.convert("RGB")
            # header strip (the sentence) at 4x
            rgb.crop((0, 0, 240, 22)).resize((240 * 4, 22 * 4),
                                             Image.LANCZOS).save(
                OUT / f"lu-header-{name}")
            # stat rows at 4x
            rgb.crop((140, 24, 240, 160)).resize((100 * 4, 136 * 4),
                                                 Image.LANCZOS).save(
                OUT / f"lu-rows-{name}")
        print("ok", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
