#!/usr/bin/env python3
"""Measure the task-menu screen: truth vs the remake's BG layers.

The original's task menu is the world map with two text panels drawn on top.
The remake ships both pieces as regular_bg layers:

    scenario_41_postbattle_bg   the world map
    scenario_41_postbattle_ui   the two text panels

This probe composites them (the ui layer wins where it is not the empty
colour) and reports the pixel difference against the original's truth frame,
plus a per-region breakdown so that the leftover (cursor, marker, ...) can be
located.

Usage:
    python tools/s49_w19b/taskmenu_probe.py --truth <truth.png> \
        --graphics <graphics dir> --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image


def load_rgb(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def is_empty(rgb) -> bool:
    return sum(rgb) <= 24


def composite(layers, width: int = 240, height: int = 160) -> Image.Image:
    out = Image.new("RGB", (width, height), (0, 0, 0))
    for layer in layers:
        pixels = layer.load()
        for y in range(height):
            for x in range(width):
                if not is_empty(pixels[x, y]):
                    out.putpixel((x, y), pixels[x, y])
    return out


def diff_map(a: Image.Image, b: Image.Image):
    ap, bp = a.load(), b.load()
    total = 0
    min_x, min_y, max_x, max_y = 240, 160, -1, -1
    rows = [0] * 160
    cols = [0] * 240
    for y in range(160):
        for x in range(240):
            if ap[x, y] != bp[x, y]:
                total += 1
                rows[y] += 1
                cols[x] += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
    bbox = None if max_x < 0 else [min_x, min_y, max_x + 1, max_y + 1]
    return {"diff_px": total, "diff_bbox": bbox, "row_diff": rows,
            "col_diff": cols}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    truth = load_rgb(args.truth)
    result = {"truth": args.truth, "variants": {}}

    for window in ("0,0", "8,48"):
        x, y = (int(v) for v in window.split(","))
        layers = []
        for name in ("postbattle_bg", "postbattle_ui"):
            path = os.path.join(args.graphics,
                                "scenario_41_%s.bmp" % name)
            asset = load_rgb(path)
            layers.append(asset.crop((x, y, x + 240, y + 160)))
        image = composite(layers)
        image.save(os.path.join(os.path.dirname(args.out),
                                "taskmenu-composite@%s.png" % window))
        result["variants"][window] = diff_map(image, truth)

    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=1)
        handle.write("\n")
    for window, data in result["variants"].items():
        print("%s -> diff %d bbox %s" % (window, data["diff_px"],
                                         data["diff_bbox"]))
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
