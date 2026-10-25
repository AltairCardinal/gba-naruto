#!/usr/bin/env python3
"""Fit the background that carries the original's ``請準備...`` window.

Everything about the original's display state is measured, because the saved
registers do not describe the captured frame:

* the window's colours are all in **PRAM palette bank 14**,
* its tiles live in **character base block 0**, **4bpp**,
* the scroll offset is **not** a multiple of 8 (a screen-aligned 8x8 block of
  the panel therefore straddles two tiles), so the offset has to be fitted.

The fit is done by building the whole map image once per background and then
sliding it over the ground-truth frame, comparing **only the window
rectangle**.

Usage::

    python tools/s49_w23f2/fit_window.py --state <a.ss9> --raw <gt.raw> \
        --box <x0,y0,x1,y1> --out <json>
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
    IO_BASE, IO_LENGTH, PRAM_BASE, PRAM_LENGTH, VRAM_BASE, VRAM_LENGTH,
    decode_bg, io_info, load,
)
from find_bg import SCREEN_SIZES  # noqa: E402
from scan_bg import build_map  # noqa: E402

SCREEN_W = 240
SCREEN_H = 160


def diff_in_box(left, right, box) -> int:
    from PIL import ImageChops

    delta = ImageChops.difference(left.crop(box), right.crop(box))
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(mask.histogram()[1:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--box", required=True)
    parser.add_argument("--layers", default="0,1,2,3")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    from PIL import Image

    raw = pathlib.Path(args.raw).read_bytes()
    truth = Image.frombytes("RGBA", (SCREEN_W, SCREEN_H), raw).convert("RGB")
    box = tuple(int(value) for value in args.box.split(","))

    state = load(pathlib.Path(args.state))
    io = io_info(state.read_memory(IO_BASE, IO_LENGTH))
    pram = state.read_memory(PRAM_BASE, PRAM_LENGTH)
    vram = state.read_memory(VRAM_BASE, VRAM_LENGTH)

    results = []
    for index in (int(value) for value in args.layers.split(",")):
        bg = decode_bg(io["bg_cnt"][index])
        for size in SCREEN_SIZES:
            name, width, height, _ = size
            image = build_map(vram, pram, bg, size, 0, False)
            best = None
            for vofs in range(0, height * 8 - SCREEN_H + 1):
                for hofs in range(0, width * 8 - SCREEN_W + 1):
                    count = diff_in_box(
                        image.crop((hofs, vofs, hofs + SCREEN_W, vofs + SCREEN_H)),
                        truth, box)
                    if best is None or count < best[0]:
                        best = (count, hofs, vofs)
            results.append({"layer": index, "size": name, "diff_px": best[0],
                            "hofs": best[1], "vofs": best[2]})
            print(f"bg{index} {name}: best {best[0]} px at ({best[1]},{best[2]})",
                  flush=True)
    results.sort(key=lambda row: row["diff_px"])
    print("BEST:", json.dumps(results[:5], indent=1))
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
