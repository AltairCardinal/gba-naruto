#!/usr/bin/env python3
"""Measure the three settlement portraits on the result screen.

The original draws the three participants as 8bpp OBJ sprites.  The remake
draws them as 4bpp sprites, so the portraits are both the wrong size and the
wrong colour depth.  This probe reports, for the truth frame and for a remake
capture:

  * the bounding box of each portrait,
  * the number of distinct colours it uses,
  * how many pixels differ.

Usage:
    python tools/s49_w19b/result_portraits_probe.py --truth <png> \
        --remake <png> --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image


def load_rgb(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def region(image: Image.Image, x0, y0, x1, y1):
    pixels = image.load()
    box = [999, 999, -1, -1]
    colors = set()
    count = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            rgb = pixels[x, y]
            # the result screen's portrait strip sits on a grey gradient;
            # anything that differs strongly from it is portrait content.
            if abs(rgb[0] - rgb[1]) < 12 and abs(rgb[1] - rgb[2]) < 12:
                continue
            colors.add(rgb)
            count += 1
            box[0] = min(box[0], x)
            box[1] = min(box[1], y)
            box[2] = max(box[2], x)
            box[3] = max(box[3], y)
    if box[2] < 0:
        return None
    return {"bbox": [box[0], box[1], box[2] + 1, box[3] + 1],
            "colors": len(colors), "px": count,
            "color_list": sorted(colors)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--row0", type=int, default=40)
    parser.add_argument("--row1", type=int, default=100)
    args = parser.parse_args()

    truth = load_rgb(args.truth)
    remake = load_rgb(args.remake)

    # three columns, centred on the original's portrait positions
    columns = [(20, 60), (100, 140), (180, 220)]
    result = {"truth": args.truth, "remake": args.remake, "portraits": {}}
    for index, (x0, x1) in enumerate(columns):
        entry = {
            "truth": region(truth, x0, args.row0, x1, args.row1),
            "remake": region(remake, x0, args.row0, x1, args.row1),
        }
        if entry["truth"] and entry["remake"]:
            tp, rp = truth.load(), remake.load()
            diff = 0
            for y in range(args.row0, args.row1):
                for x in range(x0, x1):
                    if tp[x, y] != rp[x, y]:
                        diff += 1
            entry["diff_px"] = diff
        result["portraits"]["portrait_%d" % index] = entry

    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=1)
        handle.write("\n")
    for name, entry in result["portraits"].items():
        print(name, json.dumps(entry, ensure_ascii=False))
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
