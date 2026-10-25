#!/usr/bin/env python3
"""Brute-force the background configuration that reproduces a frame.

The original's saved ``BGxCNT`` / ``BGxHOFS`` words do not describe the
captured frame (see ``find_bg.py``'s docstring), so the configuration is
**measured**: for every background layer, every screen size, every character
base and both colour modes, the whole map image is built once and then slid
over the ground truth frame.

Usage::

    python tools/s49_w23f2/scan_bg.py --state <a.ss9> --raw <gt.raw> [--out <json>]
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
    bg_palette, bg_palette_256, decode_bg, io_info, load, tile_pixels,
)
from find_bg import SCREEN_SIZES, tilemap_for  # noqa: E402

SCREEN_W = 240
SCREEN_H = 160


def build_map(vram: bytes, pram: bytes, bg: dict, size: tuple,
              char_base_block: int, color_mode_256: bool):
    """The whole map image of one background (width*8 by height*8)."""
    from PIL import Image

    name, width, height, _ = size
    entries = tilemap_for(vram, bg, size)
    char_base = char_base_block * 0x10000
    palette = bg_palette_256(pram) if color_mode_256 else None
    bank_cache: dict[int, list] = {}
    tile_cache: dict[int, list] = {}
    image = Image.new("RGB", (width * 8, height * 8), (0, 0, 0))
    pixels = image.load()
    for map_y in range(height):
        for map_x in range(width):
            entry = entries[map_y * width + map_x]
            tile = entry & 0x3FF
            bank = (entry >> 12) & 0xF
            if color_mode_256:
                colors = palette
            else:
                if bank not in bank_cache:
                    bank_cache[bank] = bg_palette(pram, bank)
                colors = bank_cache[bank]
            if tile not in tile_cache:
                tile_cache[tile] = tile_pixels(vram, char_base, tile,
                                               color_mode_256)
            pixels_of_tile = tile_cache[tile]
            for py in range(8):
                for px in range(8):
                    index = pixels_of_tile[py][px]
                    if index == 0:
                        continue
                    x = map_x * 8 + px
                    y = map_y * 8 + py
                    pixels[x, y] = colors[index]
    return image


def diff_pixels(left, right) -> int:
    from PIL import ImageChops

    delta = ImageChops.difference(left, right)
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(mask.histogram()[1:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--step", type=int, default=8,
                        help="coarse scroll step for the first pass")
    args = parser.parse_args()

    from PIL import Image

    raw = pathlib.Path(args.raw).read_bytes()
    truth = Image.frombytes("RGBA", (SCREEN_W, SCREEN_H), raw).convert("RGB")

    state = load(pathlib.Path(args.state))
    io = io_info(state.read_memory(IO_BASE, IO_LENGTH))
    pram = state.read_memory(PRAM_BASE, PRAM_LENGTH)
    vram = state.read_memory(VRAM_BASE, VRAM_LENGTH)

    results = []
    for index in range(4):
        bg = decode_bg(io["bg_cnt"][index])
        for size in SCREEN_SIZES:
            name, width, height, _ = size
            for char_base_block in range(4):
                for color_mode_256 in (False, True):
                    image = build_map(vram, pram, bg, size, char_base_block,
                                      color_mode_256)
                    best = None
                    for vofs in range(0, max(1, height * 8 - SCREEN_H + 1),
                                      args.step):
                        for hofs in range(0, max(1, width * 8 - SCREEN_W + 1),
                                          args.step):
                            count = diff_pixels(
                                image.crop((hofs, vofs,
                                            hofs + SCREEN_W, vofs + SCREEN_H)),
                                truth)
                            if best is None or count < best[0]:
                                best = (count, hofs, vofs)
                    results.append({
                        "layer": index, "size": name,
                        "char_base_block": char_base_block,
                        "color_mode_256": color_mode_256,
                        "diff_px": best[0], "hofs": best[1], "vofs": best[2],
                    })
                    print(f"bg{index} {name} cb={char_base_block} "
                          f"c256={int(color_mode_256)} -> {best[0]} px "
                          f"at ({best[1]},{best[2]})", flush=True)
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
