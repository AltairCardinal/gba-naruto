"""
Brute-force locator for the original S49 「請準備...」 window.

The window is a 96x32 block of pixels that the original draws over the
battle field.  Its screen position is *measured*, not inferred: the asset
produced by wave 23 / F2 is pasted onto every candidate position of every
captured frame and the pixel differences are counted.

Only the standard library plus Pillow is used (no numpy in this checkout).
All per-pixel work stays inside Pillow's C loops so a full 240x160 sweep
over every frame is a few seconds.

Usage:
    python tools/s49_w25h3/fit_window.py \
        --asset build/w23-f2/assets/battle_ui_prepare_box.bmp \
        --frames build/s49-package-w22/work/s49-report/capture-original \
        --out build/w25-h3/fit-original.json
"""

import argparse
import json
import os

from PIL import Image, ImageChops

NONZERO = bytes(1 if value else 0 for value in range(256))


def load_rgb(path):
    with Image.open(path) as image:
        return image.convert("RGB")


def diff_count(frame, asset, x, y):
    """Number of pixels that differ between frame and asset at (x, y)."""
    aw, ah = asset.size
    if x < 0 or y < 0 or x + aw > frame.size[0] or y + ah > frame.size[1]:
        return None
    crop = frame.crop((x, y, x + aw, y + ah))
    diff = ImageChops.difference(crop, asset)
    if diff.getbbox() is None:
        return 0
    red, green, blue = diff.split()
    mask = ImageChops.lighter(
        ImageChops.lighter(red.point(NONZERO), green.point(NONZERO)),
        blue.point(NONZERO))
    return sum(mask.histogram()[1:])


def fit_frame(frame, asset, limit=4):
    fw, fh = frame.size
    aw, ah = asset.size
    results = []
    for y in range(0, fh - ah + 1):
        for x in range(0, fw - aw + 1):
            count = diff_count(frame, asset, x, y)
            if count is None:
                continue
            results.append((count, x, y))
    results.sort()
    return results[:limit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--prefix", default="step-")
    args = parser.parse_args()

    asset = load_rgb(args.asset)
    names = sorted(
        name for name in os.listdir(args.frames)
        if name.startswith(args.prefix) and name.endswith(".png")
    )
    report = {"asset": args.asset, "asset_size": list(asset.size), "frames": {}}
    for name in names:
        frame = load_rgb(os.path.join(args.frames, name))
        best = fit_frame(frame, asset)
        report["frames"][name] = [
            {"diff_px": count, "x": x, "y": y} for count, x, y in best
        ]
        top = best[0] if best else None
        print("%-16s %s" % (
            name,
            "best diff=%s at (%s,%s)" % (top[0], top[1], top[2]) if top else "none",
        ))
        sys.stdout.flush()
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("wrote", args.out)


if __name__ == "__main__":
    import sys
    main()
