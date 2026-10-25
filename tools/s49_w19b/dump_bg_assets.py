#!/usr/bin/env python3
"""Dump the remake's 8bpp regular_bg assets to PNG (read-only on the assets).

The remake's graphics folder ships 256x256 8bpp bitmaps that the runtime shows
through a GBA regular_bg.  A 240x160 screen can only show a 240x160 window of
the 256x256 map, so *where* the window is matters:

    centered  ->  bg position (8, 48)   ->  shows map rows  48..207, cols   8..247
    top-left  ->  bg position (0, 0)    ->  shows map rows   0..159, cols   0..239

This tool renders both windows so the two can be compared against the
original's truth frames by eye.

Usage:
    python tools/s49_w19b/dump_bg_assets.py --graphics <dir> --out <dir> \
        --asset scenario_41_postbattle_dialogue_1_bottom ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image


def load_asset(path: str) -> Image.Image:
    """Load a remake 8bpp BMP and return it as an RGB image."""
    image = Image.open(path)
    if image.mode != "P":
        image = image.convert("P")
    return image.convert("RGB")


def window(image: Image.Image, x: int, y: int, width: int = 240, height: int = 160
           ) -> Image.Image:
    """Crop the (x, y)-positioned screen window out of a regular_bg map."""
    return image.crop((x, y, x + width, y + height))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--asset", action="append", default=[])
    parser.add_argument("--window", action="append", default=[],
                        help="name=x,y pairs to crop; default 0,0 and 8,48")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    windows = [(0, 0), (8, 48)]
    for spec in args.window:
        name, _, coords = spec.partition("=")
        x, _, y = coords.partition(",")
        windows.append((int(x), int(y)))

    assets = args.asset
    if not assets:
        assets = sorted(
            name[:-4] for name in os.listdir(args.graphics)
            if name.endswith(".bmp"))

    manifest = []
    for asset in assets:
        path = os.path.join(args.graphics, asset + ".bmp")
        if not os.path.exists(path):
            print("missing: " + path, file=sys.stderr)
            continue
        image = load_asset(path)
        entry = {"asset": asset, "size": list(image.size), "windows": {}}
        for (x, y) in windows:
            cropped = window(image, x, y)
            out_name = "%s@%d,%d.png" % (asset, x, y)
            cropped.save(os.path.join(args.out, out_name))
            entry["windows"]["%d,%d" % (x, y)] = out_name
        manifest.append(entry)

    with open(os.path.join(args.out, "manifest.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=1)
        handle.write("\n")
    print("dumped %d assets -> %s" % (len(manifest), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
