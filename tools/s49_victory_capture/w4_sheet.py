#!/usr/bin/env python3
"""Build a labelled contact sheet from a directory of frames.

Used by stream W4 to review a whole route at once instead of opening the
frames one by one.  Every cell carries the frame's file name, so the sheet
can be read back against the route that produced it.
"""

from __future__ import annotations

import argparse
import pathlib

from PIL import Image, ImageDraw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--pattern", default="*.png")
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--label-height", type=int, default=10)
    parser.add_argument("--every", type=int, default=1,
                        help="take every Nth frame")
    parser.add_argument("--start", type=int, default=0,
                        help="index of the first frame to take")
    parser.add_argument("--count", type=int, default=0,
                        help="how many frames to take (0 = all)")
    args = parser.parse_args(argv)

    paths = sorted(args.frames.glob(args.pattern))
    if not paths:
        raise SystemExit(f"no frames matching {args.pattern} in {args.frames}")
    paths = paths[args.start::args.every]
    if args.count:
        paths = paths[:args.count]

    first = Image.open(paths[0])
    width = int(first.width * args.scale)
    height = int(first.height * args.scale)
    label = args.label_height
    rows = (len(paths) + args.columns - 1) // args.columns
    sheet = Image.new("RGB", (args.columns * width, rows * (height + label)),
                      (16, 16, 16))
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        row, column = divmod(index, args.columns)
        x = column * width
        y = row * (height + label)
        image = Image.open(path).convert("RGB")
        if args.scale != 1.0:
            image = image.resize((width, height), Image.NEAREST)
        sheet.paste(image, (x, y))
        draw.text((x + 2, y + height + 1), path.stem[-22:], fill=(220, 220, 220))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"{len(paths)} frames -> {args.out} ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
