#!/usr/bin/env python3
"""Extract the original's ``請準備...`` window and measure what it buys.

Wave 23 / F2.  The original's battle transition shows a **96x32 px**
rounded-rectangle box with a woven green frame, a yellow-green hairline and a
cream panel that carries the single line 「請準備...」.

Everything in this script is **measured**, not assumed:

* the frame is the probe's own ``rawshot`` of the original's ``step-20-A``
  savestate (``load`` + one frame), which was verified to differ from the
  walk's PNG by only 51 px (all on the moving unit),
* the window's rectangle is found by its **palette** -- every pixel of the
  box is one of the eight colours of PRAM palette bank 14,
* the box is cut out of that frame, so the asset carries the original's own
  pixels (no re-drawing, no re-typing of the glyphs),
* the asset is then pasted into the **remake's** ``step-24-A`` frame at the
  same screen position and the judgment-bench residual is measured before and
  after.

Usage::

    python tools/s49_w23f2/extract_prepare_box.py \
        --state  build/.../capture-original/step-20-A.ss9 \
        --raw    build/w23-f2/probe/gt-f1.raw \
        --original build/.../capture-original/step-20-A.png \
        --remake   build/.../capture-remake-v4/step-24-A.png \
        --out-dir  build/w23-f2/assets
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "s49_w23f2"))

from gba_frame import (  # noqa: E402
    IO_BASE, IO_LENGTH, PRAM_BASE, PRAM_LENGTH, bg_palette, load,
)

SCREEN_W = 240
SCREEN_H = 160
BATTLEFIELD_H = 128


def window_palette(pram: bytes, bank: int) -> set:
    """The colours of one PRAM palette bank, as RGB tuples."""
    return set(bg_palette(pram, bank))


def find_box(pixels, palette, region) -> tuple[int, int, int, int]:
    """The bounding box of the palette's colours inside ``region``."""
    x0, y0, x1, y1 = region
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pixels[x, y] in palette:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise SystemExit("ERR no window pixels found")
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def diff_pixels(left, right, box=None) -> int:
    from PIL import ImageChops

    if box:
        left = left.crop(box)
        right = right.crop(box)
    delta = ImageChops.difference(left, right)
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(mask.histogram()[1:])


def write_bmp8(path: pathlib.Path, pixels: list[list[int]],
               palette: list[tuple[int, int, int]]) -> None:
    """An 8-bit indexed BMP with a 16-entry palette.

    That is exactly the shape of Butano's own battle UI assets (for example
    ``graphics/battle_ui_turn_banner_panel.bmp``: ``bits=8``, ``clrused=16``,
    118-byte data offset), so the asset drops into the remake unchanged.
    """
    import struct

    height = len(pixels)
    width = len(pixels[0]) if height else 0
    row_size = (width + 3) // 4 * 4
    image_size = row_size * height
    palette_size = 64
    data_offset = 54 + palette_size
    file_size = data_offset + image_size
    header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, data_offset)
    header += struct.pack("<IiiHHIIiiII", 40, width, height, 1, 8, 0,
                           image_size, 2835, 2835, 16, 16)
    flat = bytearray()
    for index in range(16):
        red, green, blue = (palette[index] if index < len(palette)
                            else (0, 0, 0))
        flat += bytes((blue, green, red, 0))
    body = bytearray()
    for row in reversed(pixels):
        body += bytes(row)
        body += bytes(row_size - width)
    path.write_bytes(header + bytes(flat) + bytes(body))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--bank", type=int, default=14)
    parser.add_argument("--region", default="40,30,200,100")
    args = parser.parse_args()

    from PIL import Image

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    state = load(pathlib.Path(args.state))
    pram = state.read_memory(PRAM_BASE, PRAM_LENGTH)

    raw = pathlib.Path(args.raw).read_bytes()
    truth = Image.frombytes("RGBA", (SCREEN_W, SCREEN_H), raw).convert("RGB")
    truth_pixels = truth.load()

    palette = window_palette(pram, args.bank)
    region = tuple(int(value) for value in args.region.split(","))
    box = find_box(truth_pixels, palette, region)
    print("window box:", box, "size", (box[2] - box[0], box[3] - box[1]))

    asset = truth.crop(box)
    width, height = asset.size

    # Which of the palette's colours does the asset actually use?
    used = sorted({asset.getpixel((x, y))
                   for y in range(height) for x in range(width)})
    outside = [colour for colour in used if colour not in palette]
    print("asset colours:", len(used), "outside the bank:", len(outside))
    for colour in used:
        print("   ", colour)

    # ---- the asset: an 8-bit indexed BMP plus the sidecar ------------------
    # The pixel values are the **original's own PRAM palette bank 14 indices**
    # and the palette is that bank verbatim, so the asset carries the original's
    # colours without any re-mapping.
    from gba_frame import bg_palette as _bg_palette

    bank_palette = _bg_palette(pram, args.bank)
    index_of = {colour: index for index, colour in enumerate(bank_palette)}
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            colour = asset.getpixel((x, y))
            if colour not in index_of:
                raise SystemExit(f"ERR colour {colour} is not in bank {args.bank}")
            row.append(index_of[colour])
        rows.append(row)

    bmp_path = out_dir / "battle_ui_prepare_box.bmp"
    write_bmp8(bmp_path, rows, bank_palette)
    json_path = out_dir / "battle_ui_prepare_box.json"
    json_path.write_text(json.dumps({
        "type": "sprite",
        "height": height,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # read the written BMP back and prove it is the same picture
    reread = Image.open(bmp_path).convert("RGB")
    readback_diff = diff_pixels(reread, asset)
    print("wrote", bmp_path, reread.size, reread.mode,
          "readback diff:", readback_diff, "px")
    print("wrote", json_path)

    # ---- verification ------------------------------------------------------
    original = Image.open(args.original).convert("RGB")
    remake = Image.open(args.remake).convert("RGB")

    pasted = remake.copy()
    pasted.paste(asset, (box[0], box[1]))
    field = (0, 0, SCREEN_W, BATTLEFIELD_H)
    before_field = diff_pixels(remake, original, field)
    after_field = diff_pixels(pasted, original, field)
    before_full = diff_pixels(remake, original)
    after_full = diff_pixels(pasted, original)

    # the asset pasted back into the original must be a no-op
    roundtrip = original.copy()
    roundtrip.paste(asset, (box[0], box[1]))
    roundtrip_diff = diff_pixels(roundtrip, original)

    report = {
        "window_box": list(box),
        "window_size": [width, height],
        "palette_bank": args.bank,
        "asset_colours": [list(colour) for colour in used],
        "colours_outside_the_bank": len(outside),
        "assets": {
            "bmp": str(bmp_path),
            "json": str(json_path),
        },
        "verification": {
            "asset_readback_diff_px": readback_diff,
            "asset_pasted_back_into_the_original_diff_px": roundtrip_diff,
            "remake_vs_original_before_field_px": before_field,
            "remake_vs_original_after_field_px": after_field,
            "remake_vs_original_before_full_px": before_full,
            "remake_vs_original_after_full_px": after_full,
            "window_area_px": width * height,
        },
    }
    report_path = out_dir / "prepare-box-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps(report["verification"], indent=1))
    print("->", report_path)

    # a contact sheet for the human reader
    sheet = Image.new("RGB", (SCREEN_W, SCREEN_H * 3), (0, 0, 0))
    sheet.paste(truth, (0, 0))
    sheet.paste(remake, (0, SCREEN_H))
    sheet.paste(pasted, (0, SCREEN_H * 2))
    sheet.save(out_dir / "prepare-box-contact-sheet.png")
    print("->", out_dir / "prepare-box-contact-sheet.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
