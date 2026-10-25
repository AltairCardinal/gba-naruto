"""Per-frame residuals of a judgement-bench report + the z-order pixel proof.

The z-order proof: inside the window rectangle the remake frame must be
**bit-identical to the original's own window asset** (wave 23 / F2).  If the
remake showed a single unit pixel there, the window would be behind the
characters instead of over them.

Usage:
    python tools/s49_w25h3/check_window.py \
        --report build/w25-h3/report.json \
        --original build/w25-h3/work/capture-original \
        --remake build/w25-h3/work/capture-remake \
        --asset build/w23-f2/assets/battle_ui_prepare_box.bmp \
        --orig-step step-20-A.png --remake-step step-24-A.png
"""

import argparse
import json
import os

from PIL import Image, ImageChops


def load_rgb(path):
    with Image.open(path) as image:
        return image.convert("RGB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--asset", required=True)
    parser.add_argument("--orig-step", default="step-20-A.png")
    parser.add_argument("--remake-step", default="step-24-A.png")
    parser.add_argument("--rect", default="72,48,96,32")
    args = parser.parse_args()

    with open(args.report, encoding="utf-8") as handle:
        report = json.load(handle)
    print("=== per-frame field residual (judgement bench) ===")
    for frame in report["frames"]:
        print("%-16s field=%-6s full=%-6s %s" % (
            frame["original"],
            frame["field_residual_px"],
            frame["full_residual_px"],
            frame["best_match"],
        ))
    print("summary field_residual sum =",
          report["summary"]["field_residual"]["sum"])

    x0, y0, w, h = [int(v) for v in args.rect.split(",")]
    asset = load_rgb(args.asset)
    orig = load_rgb(os.path.join(args.original, args.orig_step))
    remake = load_rgb(os.path.join(args.remake, args.remake_step))
    box = (x0, y0, x0 + w, y0 + h)

    orig_crop = orig.crop(box)
    remake_crop = remake.crop(box)
    asset_crop = asset.crop((0, 0, w, h))

    diff_orig = ImageChops.difference(orig_crop, asset_crop)
    diff_remake = ImageChops.difference(remake_crop, asset_crop)
    print()
    print("window rect", box)
    print("original  vs asset : diff bbox =", diff_orig.getbbox())
    print("remake    vs asset : diff bbox =", diff_remake.getbbox())

    mismatching = sum(
        1 for px in remake_crop.getdata() if px != asset_crop.getpixel((0, 0))
        and False)
    # per-pixel comparison
    bad = 0
    for y in range(h):
        for x in range(w):
            if remake_crop.getpixel((x, y)) != asset_crop.getpixel((x, y)):
                bad += 1
    print("remake pixels inside the rect that are NOT the window: %d / %d"
          % (bad, w * h))
    if bad:
        for y in range(h):
            row = "".join(
                "X" if remake_crop.getpixel((x, y)) != asset_crop.getpixel((x, y))
                else "." for x in range(w))
            print("  y=%2d %s" % (y + y0, row))


if __name__ == "__main__":
    main()
