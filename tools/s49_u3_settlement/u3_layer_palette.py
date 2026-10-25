#!/usr/bin/env python3
"""Inspect the palette and index layout of the candidate settlement layers.

Stream U3 (wave 10).  S4 replaces the remake's settlement screen art with the
1:1 ``scenario_41_result_*`` layers.  Before recommending the swap, the
layers' **palette layout** has to be known: are they opaque, or is index 0 the
transparent colour (Butano's ``bpp_8`` background convention)?

This tool answers one yes/no question per layer:

    *Is the layer's index 0 transparent, and what does the layer look like
     when index 0 is treated as transparent?*

Usage::

    python tools/s49_u3_settlement/u3_layer_palette.py
"""

from __future__ import annotations

import pathlib
from collections import Counter

from PIL import Image

GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")

LAYERS = (
    "battle_ui_result_background.bmp",
    "battle_ui_result_panel.bmp",
    "scenario_41_result_bottom.bmp",
    "scenario_41_result_middle.bmp",
    "scenario_41_result_top.bmp",
)


def main() -> int:
    for name in LAYERS:
        path = GRAPHICS / name
        if not path.is_file():
            print(f"MISSING {name}")
            continue
        with Image.open(path) as image:
            paletted = image.convert("P")
            indices = Counter(paletted.getdata())
            palette = paletted.getpalette() or []
        total = sum(indices.values())
        zero = indices.get(0, 0)
        print(f"{name}")
        print(f"  distinct indices: {len(indices)}  index0: {zero}/{total} "
              f"({100 * zero / total:.1f}%)")
        print(f"  palette[0] = {tuple(palette[:3])}  "
              f"palette[1] = {tuple(palette[3:6])}")
        print(f"  top indices: {indices.most_common(4)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
