#!/usr/bin/env python3
"""Montage / diff-map builder for the F3 lane."""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import load_rgb  # noqa: E402


def montage(paths, labels, scale=2, out=None, gap=4, crop=None):
    frames = []
    for path in paths:
        image = load_rgb(path)
        if crop:
            image = image.crop(crop)
        frames.append(image.resize((image.size[0] * scale, image.size[1] * scale),
                                   Image.NEAREST))
    w = frames[0].size[0]
    h = frames[0].size[1]
    canvas = Image.new("RGB", (w * len(frames) + gap * (len(frames) - 1),
                               h + 14), (32, 32, 32))
    draw = ImageDraw.Draw(canvas)
    for index, frame in enumerate(frames):
        x = index * (w + gap)
        canvas.paste(frame, (x, 14))
        draw.text((x + 2, 2), labels[index], fill=(255, 255, 255))
    if out:
        canvas.save(out)
        print(f"wrote {out}  ({canvas.size[0]}x{canvas.size[1]})")
    return canvas


def diff_map(a_path, b_path, out, scale=2, field=128):
    a = load_rgb(a_path)
    b = load_rgb(b_path)
    apx, bpx = a.load(), b.load()
    width, height = a.size
    out_image = Image.new("RGB", (width, height), (0, 0, 0))
    opx = out_image.load()
    total = 0
    for y in range(height):
        for x in range(width):
            if apx[x, y] == bpx[x, y]:
                opx[x, y] = (40, 40, 40)
            else:
                total += 1
                opx[x, y] = (255, 0, 0) if y < field else (0, 160, 255)
    out_image = out_image.resize((width * scale, height * scale), Image.NEAREST)
    out_image.save(out)
    print(f"wrote {out}  differing={total}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["montage", "diff"])
    parser.add_argument("--a", required=True)
    parser.add_argument("--b")
    parser.add_argument("--out", required=True)
    parser.add_argument("--labels", default="")
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--crop", default="", help="x0,y0,x1,y1")
    args = parser.parse_args()
    crop = None
    if args.crop:
        crop = tuple(int(v) for v in args.crop.split(","))
    if args.mode == "montage":
        paths = args.a.split(";")
        labels = args.labels.split(";") if args.labels else list(paths)
        montage(paths, labels, args.scale, args.out, crop=crop)
    else:
        diff_map(args.a, args.b, args.out, args.scale)
    return 0


if __name__ == "__main__":
    sys.exit(main())
