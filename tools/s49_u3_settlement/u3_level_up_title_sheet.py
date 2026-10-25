#!/usr/bin/env python3
"""Render the remake's level-up title sprite sheet, one frame per row.

Stream U3 (wave 10).  S3 changes the level-up screen from one screen to a
**per-person** sequence, so the remake's own title art has to be checked: how
many (character, page) pairs does ``battle_ui_level_up_title`` actually
carry?

This tool answers one yes/no question:

    *How many title frames does the remake's level-up title art carry, and
     what does each say?*

Usage::

    python tools/s49_u3_settlement/u3_level_up_title_sheet.py
"""

from __future__ import annotations

import pathlib

from PIL import Image

GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")
OUT = pathlib.Path(r"D:\Github\gba-naruto\build\s49-u3-settlement")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with Image.open(GRAPHICS / "battle_ui_level_up_title.bmp") as image:
        rgb = image.convert("RGB")
    width, height = rgb.size
    frame_height = 64
    frames = height // frame_height
    print(f"title sheet: {width}x{height} -> {frames} frames of 64px")

    for index in range(frames):
        tile = rgb.crop((0, index * frame_height, width,
                          (index + 1) * frame_height))
        tile = tile.resize((width * 4, frame_height * 4), Image.LANCZOS)
        tile.save(OUT / f"title-frame-{index:02d}.png")
    print(f"wrote {frames} frames to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
