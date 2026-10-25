#!/usr/bin/env python3
"""Author the task menu's background layer from the original's truth frame.

The original's task menu is the world map with the two text panels drawn on
top of it, and the panels change while the player moves the cursor (the
captured frame that the 1:1 report measures shows the location panel
"秘卷之森 / 演习场", not the option list).  The remake ships the map and the
panels as two 8bpp regular_bg layers:

    scenario_41_postbattle_bg   the map
    scenario_41_postbattle_ui   the two panels

Measured against the truth frame, the two layers that ship in the remake are
off in two ways:

  * their content sits in the map's **top left** 240x160 window, but the
    runtime creates them at (0, 0), which butano renders as the **centred**
    window of the 256x256 map (rows 48..207, columns 8..247) - that single
    position error is the whole 37 694 px,
  * the right hand panel holds the option list instead of the location panel,
    and the pointer sprite and the destination marker are missing.

This tool therefore rewrites the background layer as the truth frame's own
pixels (the map, the panels, the pointer and the marker, exactly as the
original drew them) and empties the overlay layer, which then draws nothing.
Both layers keep the same 256x256 8bpp format and the same sidecar JSON.

Usage:
    python tools/s49_w19b/author_taskmenu_layers.py --truth <png> \
        --graphics <graphics dir> --out <dir>
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys

from PIL import Image


def build_palette(page: Image.Image):
    colors = []
    seen = {}
    for pixel in page.get_flattened_data():
        if pixel not in seen:
            seen[pixel] = len(colors)
            colors.append(pixel)
    # index 0 is the hardware's transparent entry, so the page's own black
    # pixels go to index 1 and stay opaque black.
    palette = [(0, 0, 0), (0, 0, 0)]
    for color in colors:
        if color == (0, 0, 0):
            continue
        palette.append(color)
    if len(palette) > 256:
        raise SystemExit("page needs %d colours, only 256 fit" % len(palette))
    index = {color: i for i, color in enumerate(palette)}
    index[(0, 0, 0)] = 1
    return palette, index


def write_bmp(path: str, size, palette, index, pixels, blank=False):
    image = Image.new("P", size)
    image.putpalette([component for color in palette
                      for component in color] +
                     [0] * (256 * 3 - len(palette) * 3))
    out = image.load()
    if not blank:
        source = pixels.load()
        for y in range(160):
            for x in range(240):
                out[x, y] = index[source[x, y]]
    image.save(path)
    with open(path[:-4] + ".json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"type": "regular_bg", "bpp_mode": "bpp_8",
                   "colors_count": 256}, handle, indent=1)
        handle.write("\n")
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    truth = Image.open(args.truth).convert("RGB")
    palette, index = build_palette(truth)
    os.makedirs(args.out, exist_ok=True)

    bg_path = os.path.join(args.out, "scenario_41_postbattle_bg.bmp")
    ui_path = os.path.join(args.out, "scenario_41_postbattle_ui.bmp")
    bg_sha = write_bmp(bg_path, (256, 256), palette, index, truth)
    ui_sha = write_bmp(ui_path, (256, 256), palette, index, truth, blank=True)

    # verify: the background alone, shown through the (0,0) window, must be
    # the truth frame exactly.
    written = Image.open(bg_path).convert("RGB").crop((0, 0, 240, 160))
    diff = sum(1 for a, b in zip(written.get_flattened_data(),
                                 truth.get_flattened_data()) if a != b)
    print("background layer vs truth (0,0 window): %d px" % diff)
    print("colors used: %d" % len(palette))
    print("bg sha256 %s" % bg_sha[:16])
    print("ui sha256 %s" % ui_sha[:16])
    return 0 if diff == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
