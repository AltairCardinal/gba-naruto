#!/usr/bin/env python3
"""Author the post-battle dialogue page layers from the original's frames.

The original's post-battle dialogue screen is three regular_bg layers:

    _bottom  forest + the speaker portraits   (screen rows  8..87)
    _middle  empty
    _top     the dialogue frame and its text   (screen rows 96..159)

The remake's graphics folder ships three such layers per page, but they hold
the wrong pages (the one called `dialogue_1` draws Kakashi on the right while
the original's first page draws Naruto on the left), and the runtime never
referenced them at all: it draws the task menu's map instead.

This tool writes the **merged** page (the whole 240x160 screen of one original
dialogue page) into a 256x256 8bpp regular_bg map, which is the format every
regular_bg asset in this project uses:

    * the page's pixels go to rows 0..159, columns 0..239 of the map,
    * the rest of the map is left black,
    * the palette keeps the original's own colour order, with a second black
      entry (index 1) so that the page's black pixels are *opaque* black and do
      not fall through to the hardware's transparent palette entry 0.

Usage:
    python tools/s49_w19b/author_dialogue_pages.py \
        --orig-pages <dir> --out <dir> --pages 1,2,3,4,5,6,7
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys

from PIL import Image


def load_rgb(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def build_palette(page: Image.Image):
    """The page's colours in the order they first appear, black first."""
    colors = []
    seen = {}
    for pixel in page.get_flattened_data():
        if pixel not in seen:
            seen[pixel] = len(colors)
            colors.append(pixel)
    # index 0 stays the outside-the-page black; the page's own black gets 1
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orig-pages", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pages", default="1,2,3,4,5,6,7")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    manifest = []
    wanted = [int(value) for value in args.pages.split(",")]

    # the original's pages were captured as page<N>-frame<NNNNN>.png
    available = {}
    for name in sorted(os.listdir(args.orig_pages)):
        if name.startswith("page") and name.endswith(".png"):
            number = int(name.split("-")[0][4:])
            available.setdefault(number, name)

    for number in wanted:
        if number not in available:
            raise SystemExit("no capture for original page %d" % number)
        source = os.path.join(args.orig_pages, available[number])
        page = load_rgb(source)
        palette, index = build_palette(page)

        out = Image.new("P", (256, 256))
        out.putpalette([component for color in palette
                        for component in color] +
                       [0] * (256 * 3 - len(palette) * 3))
        pixels = out.load()
        page_pixels = page.load()
        for y in range(160):
            for x in range(240):
                pixels[x, y] = index[page_pixels[x, y]]

        name = "scenario_41_postbattle_dialogue_page_%d.bmp" % number
        path = os.path.join(args.out, name)
        out.save(path)
        with open(os.path.join(args.out, name[:-4] + ".json"), "w",
                  encoding="utf-8", newline="\n") as handle:
            json.dump({"type": "regular_bg", "bpp_mode": "bpp_8",
                       "colors_count": 256}, handle, indent=1)
            handle.write("\n")

        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        manifest.append({"asset": name, "source": available[number],
                         "colors": len(palette), "sha256": digest})
        print("%s <- %s  colors=%d  sha256=%s"
              % (name, available[number], len(palette), digest[:16]))

    with open(os.path.join(args.out, "dialogue-assets.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=1)
        handle.write("\n")
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
