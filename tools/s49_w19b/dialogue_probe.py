#!/usr/bin/env python3
"""Measure the post-battle dialogue screen: truth vs the remake's BG layers.

The original's post-battle dialogue screen is three regular_bg layers:

    _bottom  forest + portrait
    _middle  empty
    _top     dialogue frame + text

This probe composites the three remake assets (later layers win where they are
not the "empty" colour) and compares the composite against the original's
truth frame, pixel by pixel.  It also reports the per-row profile of both
images so the geometry (which rows each layer occupies) can be checked
without eyeballing.

Usage:
    python tools/s49_w19b/dialogue_probe.py --truth <truth.png> \
        --graphics <graphics dir> --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image


def load_rgb(path: str) -> Image.Image:
    image = Image.open(path)
    return image.convert("RGB")


def row_profile(image: Image.Image, width: int = 240, height: int = 160):
    """Per-row count of pixels that are not the modal (background) colour."""
    pixels = image.load()
    counts = []
    for y in range(height):
        count = 0
        for x in range(width):
            r, g, b = pixels[x, y]
            if r + g + b > 24:
                count += 1
        counts.append(count)
    return counts


def diff_px(a: Image.Image, b: Image.Image) -> int:
    ap, bp = a.load(), b.load()
    total = 0
    for y in range(160):
        for x in range(240):
            if ap[x, y] != bp[x, y]:
                total += 1
    return total


def bbox_of_diff(a: Image.Image, b: Image.Image):
    ap, bp = a.load(), b.load()
    min_x, min_y, max_x, max_y = 240, 160, -1, -1
    for y in range(160):
        for x in range(240):
            if ap[x, y] != bp[x, y]:
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    if max_x < 0:
        return None
    return [min_x, min_y, max_x + 1, max_y + 1]


def composite(layers, width: int = 240, height: int = 160) -> Image.Image:
    """Stack BG layers; a later layer wins where it is not the empty colour."""
    out = Image.new("RGB", (width, height), (0, 0, 0))
    for layer in layers:
        pixels = layer.load()
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                if r + g + b > 24:
                    out.putpixel((x, y), (r, g, b))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pages", default="1")
    args = parser.parse_args()

    truth = load_rgb(args.truth)
    result = {"truth": args.truth,
              "truth_row_profile": row_profile(truth),
              "pages": {}}

    for page in args.pages.split(","):
        entry = {}
        for window in ("0,0", "8,48"):
            x, y = (int(v) for v in window.split(","))
            layers = []
            for name in ("bottom", "middle", "top"):
                path = os.path.join(args.graphics,
                                    "scenario_41_postbattle_dialogue_%s_%s.bmp"
                                    % (page, name))
                asset = load_rgb(path)
                layers.append(asset.crop((x, y, x + 240, y + 160)))
            composite_image = composite(layers)
            entry[window] = {
                "diff_px": diff_px(composite_image, truth),
                "diff_bbox": bbox_of_diff(composite_image, truth),
            }
            entry[window]["row_profile"] = row_profile(composite_image)
            entry[window]["layer_profile"] = {
                name: row_profile(layer) for name, layer in zip(
                    ("bottom", "middle", "top"), layers)}
        result["pages"][page] = entry

    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=1)
        handle.write("\n")
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
