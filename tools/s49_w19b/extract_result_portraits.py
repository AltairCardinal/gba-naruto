#!/usr/bin/env python3
"""Re-author the result screen's three portraits from the original's truth frame.

The original draws the three participants as sprites on the result screen.  The
remake draws its own 4bpp sprites, and they use **the same colours** but a
**different drawing**: the original's figures are taller and narrower, so the
whole silhouette differs (1 898 px on the result screen).

The truth frame *is* the original's screen, and the result screen's portrait
strip has a background that is **one flat colour per row**, so the sprites can
be recovered exactly:

    * a pixel that equals its row's background colour is transparent,
    * every other pixel is an opaque sprite pixel.

The recovered pixels are placed back into the remake's existing 32x64 4bpp
canvases, keeping the existing palette (index 0 = transparent, indices 1..15
= the portrait's own colours), so the runtime needs no change at all.

Usage:
    python tools/s49_w19b/extract_result_portraits.py \
        --truth <result screen png> --capture <remake capture png> \
        --graphics <graphics dir> --out <dir>
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

from PIL import Image


NAMES = ["naruto", "sasuke", "sakura"]


def load_rgb(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def row_background(image: Image.Image, width: int = 240) -> dict:
    """The result screen's strip background is one flat colour per row."""
    pixels = image.load()
    background = {}
    for y in range(image.size[1]):
        counter = collections.Counter(pixels[x, y] for x in range(width))
        background[y] = counter.most_common(1)[0][0]
    return background


def column_clusters(image: Image.Image, background: dict,
                    row0: int, row1: int):
    """Column clusters of the portrait strip (three separated figures)."""
    pixels = image.load()
    occupied = []
    for x in range(240):
        count = 0
        for y in range(row0, row1):
            if pixels[x, y] != background[y]:
                count += 1
        occupied.append(count)
    clusters = []
    start = None
    for x in range(240):
        if occupied[x] > 0:
            if start is None:
                start = x
        else:
            if start is not None:
                clusters.append([start, x])
                start = None
    if start is not None:
        clusters.append([start, 240])
    # merge clusters separated by a one pixel gap
    merged = []
    for cluster in clusters:
        if merged and cluster[0] - merged[-1][1] <= 2:
            merged[-1][1] = cluster[1]
        else:
            merged.append(cluster)
    return [c for c in merged if c[1] - c[0] >= 4]


def best_offset(sprite_pixels, own, capture_pixels, columns, row0, row1):
    """Find where the sprite's canvas lands on screen."""
    best = None
    for oy in range(row0 - 63, row1 - 1):
        for ox in range(columns[0] - 31, columns[1] - 1):
            agree = 0
            total = 0
            for y in range(64):
                for x in range(32):
                    if sprite_pixels[y][x] not in own:
                        continue
                    sx, sy = x + ox, y + oy
                    if not (0 <= sx < 240 and 0 <= sy < 160):
                        continue
                    total += 1
                    if capture_pixels[sx, sy] == sprite_pixels[y][x]:
                        agree += 1
            if total < 100:
                continue
            score = agree - (total - agree)
            if best is None or score > best[0]:
                best = (score, ox, oy, agree, total)
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--row0", type=int, default=40)
    parser.add_argument("--row1", type=int, default=105)
    args = parser.parse_args()

    truth = load_rgb(args.truth)
    capture = load_rgb(args.capture)
    background = row_background(truth)
    tp, cp = truth.load(), capture.load()
    clusters = column_clusters(truth, background, args.row0, args.row1)
    if len(clusters) != 3:
        raise SystemExit("expected three portrait columns, got %r" % clusters)
    os.makedirs(args.out, exist_ok=True)

    report = {"truth": args.truth, "capture": args.capture,
              "clusters": clusters, "portraits": {}}
    for index, name in enumerate(NAMES):
        path = os.path.join(args.graphics, "battle_ui_result_%s.bmp" % name)
        sprite = Image.open(path)
        palette = sprite.getpalette()
        colors = [tuple(palette[i * 3:i * 3 + 3]) for i in range(16)]
        own = set(colors[1:])
        color_index = {color: i for i, color in enumerate(colors)}
        pixels = sprite.load()
        canvas_rgb = [[colors[pixels[x, y]] for x in range(32)]
                      for y in range(64)]

        columns = clusters[index]
        found = best_offset(canvas_rgb, own, cp, columns, args.row0, args.row1)
        if found is None:
            raise SystemExit("%s: could not locate the sprite on screen" % name)
        _, offset_x, offset_y, agree, total = found

        # recover the original's own pixels inside this portrait's column window
        recovered = {}
        for y in range(args.row0, args.row1):
            for x in range(columns[0], columns[1]):
                if tp[x, y] == background[y]:
                    continue
                recovered[(x, y)] = tp[x, y]

        new_pixels = [[0] * 32 for _ in range(64)]
        placed = 0
        for (x, y), color in recovered.items():
            cx = x - offset_x
            cy = y - offset_y
            if not (0 <= cx < 32 and 0 <= cy < 64):
                raise SystemExit(
                    "%s: recovered pixel (%d,%d) falls outside the canvas"
                    % (name, cx, cy))
            if color not in color_index:
                raise SystemExit(
                    "%s: colour %s is not in the sprite palette" % (name, color))
            new_pixels[cy][cx] = color_index[color]
            placed += 1

        out = Image.new("P", (32, 64))
        out.putpalette(palette)
        out_pixels = out.load()
        for cy in range(64):
            for cx in range(32):
                out_pixels[cx, cy] = new_pixels[cy][cx]
        out_path = os.path.join(args.out, "battle_ui_result_%s.bmp" % name)
        out.save(out_path)

        report["portraits"][name] = {
            "columns": columns,
            "canvas_to_screen_offset": [offset_x, offset_y],
            "match_agree": agree,
            "match_total": total,
            "recovered_px": placed,
        }
        print("%-8s columns=%s offset=(%d,%d) match=%d/%d placed=%d"
              % (name, columns, offset_x, offset_y, agree, total, placed))

    with open(os.path.join(args.out, "portrait-report.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=1)
        handle.write("\n")
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
