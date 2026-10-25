#!/usr/bin/env python3
"""W24-G3: change one entry of a 4bpp BMP palette *table* at byte level.

PIL cannot write 4 bit per pixel BMPs, so re-saving `battle_ui_result_total_palette.bmp`
through PIL silently turns it into an 8bpp BMP and butano's loader rejects it.
A BMP's colour table is a plain array of BGRA quads right behind the 40 byte
DIB header, so the entry can be patched in place without touching the pixels.

Usage:
  python tools/s49_w24g3/patch_palette_entry.py --bmp <file> --index 1 \
      --rgb 231 99 66 [--expect-bpp 4]
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image


def read_header(data: bytes) -> dict:
    off = struct.unpack_from("<I", data, 10)[0]
    dib = struct.unpack_from("<I", data, 14)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    planes, bpp = struct.unpack_from("<HH", data, 26)
    entries = struct.unpack_from("<I", data, 46)[0]
    return {"data_offset": off, "dib": dib, "w": w, "h": h, "bpp": bpp,
            "palette_entries": entries}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bmp", required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--rgb", type=int, nargs=3, required=True)
    ap.add_argument("--expect-bpp", type=int, default=None)
    args = ap.parse_args()

    path = Path(args.bmp)
    data = bytearray(path.read_bytes())
    head = read_header(bytes(data))
    print("before:", head)
    if args.expect_bpp is not None and head["bpp"] != args.expect_bpp:
        raise SystemExit(f"expected {args.expect_bpp}bpp, found {head['bpp']}bpp")

    table = 14 + head["dib"]
    entry = table + args.index * 4
    old = tuple(data[entry:entry + 4])
    r, g, b = args.rgb
    data[entry + 0] = b
    data[entry + 1] = g
    data[entry + 2] = r
    data[entry + 3] = 0
    print(f"palette entry {args.index}: BGRA {old} -> {tuple(data[entry:entry + 4])}")

    with open(path, "r+b") as fh:
        fh.write(bytes(data))
        fh.truncate()

    head2 = read_header(bytes(data))
    print("after :", head2)
    pal = Image.open(path).getpalette()
    print("read back:", list(pal[args.index * 3:args.index * 3 + 3]))


if __name__ == "__main__":
    main()
