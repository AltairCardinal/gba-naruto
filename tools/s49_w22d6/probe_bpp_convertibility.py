#!/usr/bin/env python3
"""Measure whether a GBA regular-BG image can be re-exported as 4bpp losslessly.

The original ROM renders its battle map on **4bpp** BG layers (proved by
`probe_bg_bpp.py`).  A 4bpp background draws every 8x8 tile from **one**
16-entry palette bank, but a background may use **up to 16 banks** (16 palette
slots = the whole of palette RAM).  So an image is 4bpp-representable without
losing a single colour exactly when **every 8x8 tile of the image uses at most
16 distinct colours**: each tile then needs a bank of its own, and the banks
may be reused across tiles.

This tool reports, for a BMP:

* how many 8x8 tiles use more than 16 colours (=> 4bpp would need to merge /
  dither them),
* how many distinct banks a bank assignment would need,
* the colour count of the whole image.

It also runs the actual quantisation so the *cost* of a 16-colour global
palette can be compared with the black-frame budget.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

from PIL import Image


def analyse(path: pathlib.Path) -> dict[str, object]:
    image = Image.open(path)
    if image.mode != "P":
        image = image.convert("P", palette=Image.ADAPTIVE, colors=256)
    palette = image.getpalette()
    colors = [
        tuple(palette[i : i + 3]) for i in range(0, len(palette) - 2, 3)
    ]
    pixels = list(image.getdata())
    width, height = image.size

    over_16 = 0
    max_colors = 0
    hist: Counter[int] = Counter()
    for by in range(0, height - 7, 8):
        for bx in range(0, width - 7, 8):
            distinct = set()
            for y in range(by, by + 8):
                row = y * width
                for x in range(bx, bx + 8):
                    distinct.add(pixels[row + x])
            hist[len(distinct)] += 1
            max_colors = max(max_colors, len(distinct))
            if len(distinct) > 16:
                over_16 += 1

    total_tiles = sum(hist.values())
    used = set(pixels)
    return {
        "path": str(path),
        "size": [width, height],
        "distinct_colors": len(used),
        "tiles_total": total_tiles,
        "tiles_over_16_colors": over_16,
        "tiles_over_16_ratio": round(over_16 / total_tiles, 4) if total_tiles else None,
        "max_colors_in_one_tile": max_colors,
        "tile_color_histogram": dict(sorted(hist.items())),
    }


def quantise_cost(path: pathlib.Path, colors: int, dither: bool) -> dict[str, object]:
    """Global N-colour palette: how many pixels change, and by how much."""
    image = Image.open(path)
    if image.mode != "P":
        image = image.convert("P", palette=Image.ADAPTIVE, colors=256)
    rgb = image.convert("RGB")
    source = list(rgb.getdata())

    method = Image.Quantize.MEDIANCUT
    if dither:
        q = image.convert("RGB").quantize(colors=colors, method=method, dither=Image.Dither.FLOYDSTEINBERG)
    else:
        q = image.convert("RGB").quantize(colors=colors, method=method, dither=Image.Dither.NONE)
    target = list(q.convert("RGB").getdata())

    changed = 0
    total_error = 0
    max_error = 0
    worst = 0
    for (r0, g0, b0), (r1, g1, b1) in zip(source, target):
        err = abs(r0 - r1) + abs(g0 - g1) + abs(b0 - b1)
        if err:
            changed += 1
            total_error += err
            max_error = max(max_error, err)
            worst = max(worst, max(abs(r0 - r1), abs(g0 - g1), abs(b0 - b1)))
    total = len(source)
    return {
        "colors": colors,
        "dither": dither,
        "pixels_total": total,
        "pixels_changed": changed,
        "pixels_changed_pct": round(100.0 * changed / total, 3),
        "mean_abs_error_over_changed_px": round(total_error / changed, 2) if changed else 0.0,
        "max_abs_error_sum_rgb": max_error,
        "max_abs_error_single_channel": worst,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    result: dict[str, object] = {}
    for raw_path in args.images:
        path = pathlib.Path(raw_path)
        entry = analyse(path)
        entry["quantise_16_global"] = quantise_cost(path, 16, dither=False)
        entry["quantise_16_dithered"] = quantise_cost(path, 16, dither=True)
        result[path.name] = entry

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
