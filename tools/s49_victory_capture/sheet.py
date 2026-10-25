#!/usr/bin/env python3
"""Build a labelled contact sheet from a directory of PNG frames.

Stream K uses this to look at a whole route at once (and to publish the
"which frame is which" evidence in the report) without opening dozens of
images one by one.

Usage::

    python tools/s49_victory_capture/sheet.py --dir build/s49-victory-capture/run/frames \
        --out build/s49-victory-capture/run/sheet.png --columns 6 --scale 2
"""

from __future__ import annotations

import argparse
import pathlib

from PIL import Image, ImageDraw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="directory with *.png")
    parser.add_argument("--out", required=True, help="output PNG")
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--pattern", default="*.png")
    parser.add_argument("--label-height", type=int, default=14)
    args = parser.parse_args(argv)

    paths = sorted(pathlib.Path(args.dir).glob(args.pattern))
    if not paths:
        raise SystemExit(f"no PNG files in {args.dir}")

    first = Image.open(paths[0])
    width, height = first.size
    cell_w = width * args.scale
    cell_h = height * args.scale + args.label_height
    columns = max(1, args.columns)
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)

    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB").resize(
            (cell_w, height * args.scale), Image.NEAREST)
        x = (index % columns) * cell_w
        y = (index // columns) * cell_h
        sheet.paste(image, (x, y))
        draw.text((x + 2, y + height * args.scale + 1), path.stem,
                  fill=(255, 255, 0))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"wrote {out} ({len(paths)} frames, {columns}x{rows})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
