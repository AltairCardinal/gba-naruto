#!/usr/bin/env python3
"""Build a contact sheet from a directory of captured frames.

Used to eyeball a whole phase sequence in one image (the frames of the
original battle-14 entry performance, the frames around a black field, ...).

Usage::

    python tools/s49_blackfade/contact_sheet.py \
        --frames build/s49-report/capture-original --pattern "step-*.png" \
        --out build/s49-blackfade/contact-entry.png
"""

from __future__ import annotations

import argparse
import pathlib

from PIL import Image, ImageDraw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--pattern", default="*.png")
    parser.add_argument("--out", required=True)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--start-index", type=int, default=0,
                        help="skip the first N frames")
    parser.add_argument("--count", type=int, default=0,
                        help="use only the next N frames (0 = all)")
    args = parser.parse_args(argv)

    directory = pathlib.Path(args.frames)
    paths = sorted(directory.glob(args.pattern))
    if not paths:
        raise SystemExit(f"no frames in {directory} matching {args.pattern}")
    paths = paths[args.start_index:]
    if args.count:
        paths = paths[:args.count]

    images = [Image.open(path).convert("RGB") for path in paths]
    width, height = images[0].size
    width = int(width * args.scale)
    height = int(height * args.scale)
    label_height = 12
    columns = args.columns
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * (height + label_height)),
                      (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    for index, (path, image) in enumerate(zip(paths, images)):
        if args.scale != 1.0:
            image = image.resize((width, height), Image.NEAREST)
        x = (index % columns) * width
        y = (index // columns) * (height + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 2, y + height + 1), path.stem, fill=(255, 255, 255))
    sheet.save(pathlib.Path(args.out))
    print(f"{len(images)} frames -> {args.out} ({sheet.size[0]}x{sheet.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
