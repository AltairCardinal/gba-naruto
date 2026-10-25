#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Locate the deployment text overlays in a captured remake frame.

The deployment overlay draws four strings: "<title> DEPLOY", "UNIT n/m",
"<name> PLAYER" and "A:OK B:BACK".  The judgment bench only counts the field
area, which is the top 128 rows of the 240x160 screen
(`tools/s49_fidelity_report/paths.py` => FIELD_AREA = (0, 0, 240, 128)), so
"which of those four strings is actually inside the field area?" decides
whether a fix can move the bench number at all.

This script counts near-white pixels per row of a frame and prints the row
profile, so the text bands can be read off directly.

Usage:
    python tools/s49_w25/text_row_profile.py <frame.png> [more frames...]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def profile(path: Path) -> None:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    print(f"=== {path}  ({w}x{h}) ===")
    for y in range(h):
        bright = 0
        for x in range(w):
            r, g, b = px[x, y]
            if r > 190 and g > 190 and b > 190:
                bright += 1
        if bright:
            flag = "  <== inside FIELD (y<128)" if y < 128 else "  (hud area, NOT counted)"
            print(f"  row {y:3d}: {bright:3d} near-white px{flag}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    for arg in sys.argv[1:]:
        profile(Path(arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
