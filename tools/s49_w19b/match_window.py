#!/usr/bin/env python3
"""Find which window of a regular_bg map a captured remake frame shows.

The remake's settlement renderer creates its screen-sized regular_bg layers at
a fixed position.  This probe takes one captured remake frame plus one or
more candidate assets and reports, for every candidate scroll offset, how
many pixels of the capture are explained by that asset.

Usage:
    python tools/s49_w19b/match_window.py --capture <png> --out <json> \
        --asset name=path.bmp [--asset ...]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image


def load_rgb(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def non_black_mask(image: Image.Image, width: int = 240, height: int = 160):
    pixels = image.load()
    mask = []
    for y in range(height):
        row = []
        for x in range(width):
            r, g, b = pixels[x, y]
            row.append(1 if r + g + b > 24 else 0)
        mask.append(row)
    return mask


def diff_px(a: Image.Image, b: Image.Image) -> int:
    ap, bp = a.load(), b.load()
    total = 0
    for y in range(160):
        for x in range(240):
            if ap[x, y] != bp[x, y]:
                total += 1
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--asset", action="append", default=[])
    args = parser.parse_args()

    capture = load_rgb(args.capture)
    mask = non_black_mask(capture)
    lit = sum(sum(row) for row in mask)

    result = {"capture": args.capture, "capture_lit_px": lit, "candidates": {}}
    for spec in args.asset:
        name, _, path = spec.partition("=")
        asset = load_rgb(path)
        best = None
        for y in range(0, 97):
            for x in range(0, 17):
                if x + 240 > 256 or y + 160 > 256:
                    continue
                window = asset.crop((x, y, x + 240, y + 160))
                pixels = window.load()
                agree = 0
                for row in range(160):
                    for col in range(240):
                        r, g, b = pixels[col, row]
                        asset_lit = 1 if r + g + b > 24 else 0
                        if asset_lit == mask[row][col]:
                            agree += 1
                score = agree
                if best is None or score > best[0]:
                    best = (score, x, y)
        result["candidates"][name] = {
            "best_window": [best[1], best[2]],
            "best_agree_px": best[0],
            "lit_fraction": round(best[0] / (240 * 160), 4),
        }

    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=1)
        handle.write("\n")
    for name, data in result["candidates"].items():
        print("%s -> window %s agree %d (%.1f%%)"
              % (name, data["best_window"], data["best_agree_px"],
                 100 * data["lit_fraction"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
