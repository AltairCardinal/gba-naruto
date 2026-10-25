#!/usr/bin/env python3
"""Wave 21 / C4 -- palette-independent cross check of the "the move grid is on
screen" measurement.

The mint cell colour used by ``detect_presentation.py`` was read off the
**original's** frames, so it cannot, by itself, prove anything about the
**remake** (the two sides use different palettes and different blends).

This tool closes that hole: it takes the **remake's own** palette
(``battle_range_ui_style.h``), blends every palette colour with **every
background colour that actually occurs in the frame** at the product's blend
factors, and counts the rendered results.  The overlay can only be on screen
if one of those rendered colours is present.

Result (measured):

* the original's dense frames ``f052 / f060 / f070 / f077`` (the overlay
  window) **do** hit;
* the original's ``f048`` / ``f078`` (just before / just after) do **not**;
* **none** of the original's 25 settled beats hits;
* **none** of the remake's 30 settled beats hits -- including the remake's
  ``step-26-A`` whose VRAM *does* carry the move range.

Usage
-----
    python tools/s49_w21c4/blend_cross_check.py
"""

from __future__ import annotations

import os
import pathlib
import sys
from collections import Counter

from PIL import Image

REPO = pathlib.Path(__file__).resolve().parents[2]
REMAKE = REPO / "build" / "w20-e3" / "capture-remake"
ORIGINAL = REPO / "build" / "s49-package-w18" / "work" / "s49-report" / "capture-original"
DENSE = REPO / "build" / "w20-e3" / "dense" / "step-20-to-21"

BLEND_DEN = 16

# the remake's own overlay palette (``battle_range_ui_style.h``)
PALETTE = {
    "grid": (66, 107, 140),
    "move_primary": (24, 206, 255),
    "move_secondary": (8, 107, 172),
    "attack_primary": (255, 59, 0),
    "cursor_primary": (255, 189, 0),
    "target_primary": (172, 206, 0),
}


def report(path: pathlib.Path, label: str) -> None:
    with Image.open(path) as image:
        counts = Counter(image.convert("RGB").getdata())
    hits: Counter = Counter()
    for background, _n in counts.items():
        for name, colour in PALETTE.items():
            for blend in range(1, BLEND_DEN):
                candidate = tuple(
                    (blend * colour[i] + (BLEND_DEN - blend) * background[i]) // BLEND_DEN
                    for i in range(3))
                n = counts.get(candidate, 0)
                if n and n < 400:
                    hits[f"{name}@{blend}/{background}"] += n
    print(f"  {label:24s} {hits.most_common(6)}")


def main() -> int:
    print("=== remake settled beats ===")
    for name in sorted(os.listdir(REMAKE)):
        if name.endswith(".png") and ("-A" in name or "base" in name):
            report(REMAKE / name, name)
    print()
    print("=== original settled beats ===")
    for name in sorted(os.listdir(ORIGINAL)):
        if name.endswith(".png"):
            report(ORIGINAL / name, name)
    print()
    print("=== original dense transient (the grid on screen) ===")
    for frame in ("f048", "f052", "f060", "f070", "f077", "f078"):
        report(DENSE / f"{frame}.png", frame)
    return 0


if __name__ == "__main__":
    sys.exit(main())
