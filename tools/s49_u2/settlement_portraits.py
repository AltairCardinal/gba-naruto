#!/usr/bin/env python3
"""Settlement screen portraits: can the 1 898 px be closed, and how?

    python tools/s49_u2/settlement_portraits.py \
        --truth build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
        --remake build/s49-u2/chain/shots \
        --out build/s49-u2/portraits.json

What it answers
---------------
The wave 16 stream V2 left the settlement screen with two residuals:

* **1 898 px** -- the three participants.  The original draws ~28x52 chibi
  portraits, the remake draws 16x16 avatars.
* **684 px** -- the four numeric rows.  The layout is already pixel exact;
  only the *values* differ (the remake's battle was poked, so every
  participant shows the same numbers).

V2 concluded that the portraits **cannot** be closed with sprites: the
original uses 22..25 colours per portrait, so 4bpp (16 colours) is out, and
three 8bpp sprites would need three separate 256 colour OBJ palettes while
the hardware has one.

This tool measures the numbers that decide the trade-off:

1. the exact pixel bbox of every participant region (original vs remake);
2. the number of **distinct colours** each original portrait uses;
3. the **quantisation error** of a 4bpp (16 colour) version of every
   portrait -- i.e. how many pixels a 4bpp sprite would still get wrong;
4. the colour budget of the settlement plate (the regular BG layer), which
   is an 8bpp layer: a portrait could live in the BG's own 256 colour
   palette instead of the OBJ palette banks.

Everything is read-only: the original's exported truth PNG and the remake's
own captured shots.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter

from PIL import Image


def load(path: pathlib.Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def difference_mask(truth: Image.Image, remake: Image.Image) -> list[tuple[int, int]]:
    """The pixels the two screens disagree on."""
    truth_pixels = truth.load()
    remake_pixels = remake.load()
    width = min(truth.width, remake.width)
    height = min(truth.height, remake.height)
    rows: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            if truth_pixels[x, y] != remake_pixels[x, y]:
                rows.append((x, y))
    return rows


def band_report(truth: Image.Image,
                remake: Image.Image,
                band_height: int = 8) -> list[dict]:
    """The difference count per horizontal band (rows 49..100 are the portraits)."""
    rows = difference_mask(truth, remake)
    counter = Counter(y // band_height for _x, y in rows)
    return [{"row_band": band,
             "rows": [band * band_height, band * band_height + band_height - 1],
             "diff_px": counter.get(band, 0)}
            for band in sorted(set(counter) | {b for b in
                                              range(truth.height // band_height)})]


def region_report(truth: Image.Image,
                  remake: Image.Image,
                  regions: list[tuple[int, int, int, int]]) -> list[dict]:
    """Per participant region: colours, quantisation error, bbox."""
    truth_pixels = truth.load()
    remake_pixels = remake.load()
    out = []
    for index, (x0, y0, x1, y1) in enumerate(regions):
        original = [truth_pixels[x, y]
                    for y in range(y0, y1)
                    for x in range(x0, x1)]
        remake_colours = Counter(
            remake_pixels[x, y]
            for y in range(y0, y1)
            for x in range(x0, x1))
        counter = Counter(original)
        distinct = len(counter)
        # The 16 colour palette a 4bpp sprite would have to use: the 15 most
        # frequent colours plus the most frequent colour that is *not* one of
        # them (the 16th slot); a dithered sprite keeps a 16th colour.
        palette = [colour for colour, _count in counter.most_common(16)]
        error = 0
        for colour, count in counter.items():
            if colour not in palette:
                # the nearest palette entry (Euclidean in RGB)
                best = min(
                    palette,
                    key=lambda candidate: (
                        (candidate[0] - colour[0]) ** 2 +
                        (candidate[1] - colour[1]) ** 2 +
                        (candidate[2] - colour[2]) ** 2))
                error += count
        differing = sum(
            1
            for y in range(y0, y1)
            for x in range(x0, x1)
            if truth_pixels[x, y] != remake_pixels[x, y])
        out.append({
            "index": index,
            "box": [x0, y0, x1, y1],
            "size": [x1 - x0, y1 - y0],
            "original_pixels": len(original),
            "original_distinct_colours": distinct,
            "original_top_colours": counter.most_common(6),
            "remake_distinct_colours": len(remake_colours),
            "remake_top_colours": remake_colours.most_common(6),
            "diff_px_vs_remake": differing,
            "pixels_needing_a_colour_outside_a_16_slot_palette": error,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", type=pathlib.Path, required=True)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=None)
    args = parser.parse_args()

    truth = load(args.truth)
    remake_path = args.remake
    if remake_path.is_dir():
        candidates = sorted(remake_path.glob("page-*result*.png"))
        if not candidates:
            candidates = sorted(remake_path.glob("page-*.png"))
        if not candidates:
            raise SystemExit(f"ERR no settlement shot in {remake_path}")
        remake_path = candidates[0]
    remake = load(remake_path)

    rows = difference_mask(truth, remake)
    bands = band_report(truth, remake)

    # The three participant columns of the settlement screen (the original's
    # portraits sit under the tab bar's columns 2, 3 and 4; the measured
    # difference columns are 84..235, the portraits 49..97).
    regions = [
        (84, 44, 120, 102),
        (140, 44, 176, 102),
        (194, 44, 236, 102),
    ]
    document = {
        "schema": "konoha.s49-u2.settlement-portraits/1",
        "truth": str(args.truth),
        "remake": str(remake_path),
        "screen": [truth.width, truth.height],
        "total_diff_px": len(rows),
        "diff_bands": bands,
        "regions": region_report(truth, remake, regions),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(document, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
    print(f"truth   {args.truth} {truth.width}x{truth.height}")
    print(f"remake  {remake_path} {remake.width}x{remake.height}")
    print(f"total diff px: {len(rows)}")
    for band in bands:
        if band["diff_px"]:
            print(f"  rows {band['rows']}: {band['diff_px']} px")
    for row in document["regions"]:
        print(f"  region {row['index']} {row['size']} "
              f"original colours {row['original_distinct_colours']} "
              f"remake colours {row['remake_distinct_colours']} "
              f"diff {row['diff_px_vs_remake']} px "
              f"outside-16-palette {row['pixels_needing_a_colour_outside_a_16_slot_palette']} px")
    if args.out:
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
