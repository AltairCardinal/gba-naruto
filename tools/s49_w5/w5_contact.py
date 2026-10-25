#!/usr/bin/env python3
"""W5 -- build labelled contact sheets and pixel diff maps for the two walks.

Why this tool exists
--------------------
The offset profile says the remake's A-key walk drifts one press behind the
original between original step 9 and step 10.  Numbers alone cannot say *what*
the extra press was; the answer has to be read off the pictures.  This tool
puts the two walks side by side (labelled) and renders the per-pixel diff of a
chosen pair as a picture plus a row/column band profile, so that "the banner
text is identical, only the battlefield underneath scrolled" can be stated as
a measurement instead of a guess.

Usage
-----
    # contact sheet
    python tools/s49_w5/w5_contact.py sheet \
        --original build/.../capture-original --remake build/.../capture-remake \
        --frames original:08 original:09 original:10 original:11 \
                 remake:12   remake:13   remake:14   remake:15 \
        --cols 4 --out build/s49-wave18/w5/sheet.png

    # diff map + band profile
    python tools/s49_w5/w5_contact.py diff \
        --original build/.../capture-original --remake build/.../capture-remake \
        --left original:09 --right original:10 \
        --out build/s49-wave18/w5/diff-09-10.png
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageChops, ImageDraw  # noqa: E402

from s49_fidelity_report.pixels import load_rgb  # noqa: E402

SCREEN = (240, 160)
LABEL_H = 14


def resolve(side_dir: str, side: str, index: int) -> str:
    directory = side_dir if side == "original" else remake_dir
    for name in sorted(os.listdir(directory)):
        if not (name.startswith("step-") and name.endswith(".png")):
            continue
        stem = name[len("step-"):-len(".png")]
        if stem.split("-")[0] == "{:02d}".format(index):
            return os.path.join(directory, name)
    raise SystemExit("no frame for {} step {:02d}".format(side, index))


def resolve_spec(spec: str, original_dir: str) -> str:
    """'original:09' | 'remake:13' | 'file:<path>'."""
    if spec.startswith("file:"):
        return spec[len("file:"):]
    side, index = spec.split(":")
    return resolve(original_dir, side, int(index))


def band_profile(mask: Image.Image, size: int = 16) -> list[tuple[int, int, int]]:
    """(band_index, y0, differing_pixel_count) over horizontal bands."""
    width, height = mask.size
    out = []
    for top in range(0, height, size):
        count = 0
        for row in range(top, min(top + size, height)):
            count += sum(1 for value in mask.crop((0, row, width, row + 1)).getdata() if value)
        out.append((top // size, top, count))
    return out


def main() -> int:
    global remake_dir
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sheet = sub.add_parser("sheet")
    sheet.add_argument("--original", required=True)
    sheet.add_argument("--remake", required=True)
    sheet.add_argument("--frames", nargs="+", required=True)
    sheet.add_argument("--cols", type=int, default=4)
    sheet.add_argument("--crop", default=None,
                       help="x0,y0,x1,y1 crop box (default: whole screen)")
    sheet.add_argument("--zoom", type=int, default=1)
    sheet.add_argument("--out", required=True)

    diff = sub.add_parser("diff")
    diff.add_argument("--original", required=True)
    diff.add_argument("--remake", required=True)
    diff.add_argument("--left", required=True)
    diff.add_argument("--right", required=True)
    diff.add_argument("--out", required=True)

    args = parser.parse_args()
    remake_dir = args.remake

    if args.command == "sheet":
        if args.crop:
            box = tuple(int(v) for v in args.crop.split(","))
        else:
            box = (0, 0) + SCREEN
        tile_w = (box[2] - box[0]) * args.zoom
        tile_h = (box[3] - box[1]) * args.zoom
        tiles = []
        for spec in args.frames:
            path = resolve_spec(spec, args.original)
            image = load_rgb(path).crop(box)
            if args.zoom != 1:
                image = image.resize((tile_w, tile_h), Image.NEAREST)
            tiles.append((spec, image))

        cols = max(1, args.cols)
        rows = (len(tiles) + cols - 1) // cols
        sheet_image = Image.new("RGB", (cols * tile_w, rows * (tile_h + LABEL_H)),
                                (24, 24, 32))
        draw = ImageDraw.Draw(sheet_image)
        for position, (spec, image) in enumerate(tiles):
            x = (position % cols) * tile_w
            y = (position // cols) * (tile_h + LABEL_H)
            sheet_image.paste(image, (x, y + LABEL_H))
            draw.text((x + 3, y + 3), spec, fill=(255, 230, 120))
            draw.rectangle([x, y + LABEL_H, x + tile_w - 1, y + LABEL_H + tile_h - 1],
                           outline=(90, 90, 110))
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        sheet_image.save(args.out)
        print("wrote", args.out, sheet_image.size)
        return 0

    # --- diff ---------------------------------------------------------
    left_spec = args.left.split(":")
    right_spec = args.right.split(":")
    left_path = resolve(args.original if left_spec[0] == "original" else args.remake,
                        left_spec[0], int(left_spec[1]))
    right_path = resolve(args.original if right_spec[0] == "original" else args.remake,
                         right_spec[0], int(right_spec[1]))
    left = load_rgb(left_path)
    right = load_rgb(right_path)
    delta = ImageChops.difference(left, right)
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    differing = sum(mask.histogram()[1:])
    print("left :", left_path)
    print("right:", right_path)
    print("differing pixels (full 240x160):", differing)

    # where do the differences live?
    print("\nhorizontal bands (16 px tall): band  y0   differing px")
    for band, y0, count in band_profile(mask):
        if count:
            print("  band {:>2}  y={:>3}   {:>6}".format(band, y0, count))

    # diff map: magenta where different, dimmed base where same
    base = Image.blend(left.convert("RGB"), Image.new("RGB", SCREEN, (0, 0, 0)), 0.55)
    overlay = Image.new("RGB", SCREEN, (255, 0, 255))
    base.paste(overlay, (0, 0), mask.point(lambda v: 255 if v else 0))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    base.save(args.out)
    print("\nwrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
