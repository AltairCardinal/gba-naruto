#!/usr/bin/env python3
"""Find which background layer + screen size + scroll reproduces a frame.

Wave 23 / F2 needs the original's ``請準備...`` window, which is a **background**
layer (the unit is drawn on top of it, as an object).  The original's saved
``BGxCNT`` / ``BGxHOFS`` words cannot be trusted:

* the probe's *live* IO read answers every register from ``0x10`` upwards with
  the constant filler ``0x4338`` (AGENTS.md rule 13), and
* the ``.ss9`` file's IO block carries values that do not describe the frame
  that was captured (``DISPCNT`` reads ``0x1940``, which would enable **no**
  background at all, yet the captured frame is full of map).

So the configuration is **measured**: every background layer is rendered for
every screen size at every scroll offset and compared with the ground-truth
frame (the probe's own ``rawshot`` of the same savestate).

Usage::

    python tools/s49_w23f2/find_bg.py --state <a.ss9> --raw <gt.raw> [--out <dir>]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "s49_w23f2"))

from gba_frame import (  # noqa: E402
    IO_BASE, IO_LENGTH, PRAM_BASE, PRAM_LENGTH, VRAM_BASE, VRAM_LENGTH,
    bg_palette, bg_palette_256, decode_bg, io_info, load, tile_pixels,
)

SCREEN_W = 240
SCREEN_H = 160

# (name, width in tiles, height in tiles, block order)
SCREEN_SIZES = (
    ("256x256", 32, 32, (0,)),
    ("512x256", 64, 32, (0, 1)),
    ("256x512", 32, 64, (0, 1)),
    ("512x512", 64, 64, (0, 1, 2, 3)),
    ("512x512b", 64, 64, (0, 2, 1, 3)),
)


def tilemap_for(vram: bytes, bg: dict, size: tuple) -> list[int]:
    """The tilemap of one background for one screen size."""
    name, width, height, order = size
    base = bg["screen_base_block"] * 0x800
    out = [0] * (width * height)
    half = width // 2
    for block_index, block in enumerate(order):
        offset = base + block * 0x800
        raw = vram[offset:offset + 0x800]
        for index in range(1024):
            entry = raw[index * 2] | (raw[index * 2 + 1] << 8)
            if name in ("512x256", "512x512", "512x512b"):
                col = (index % 32) + (block_index % 2) * 32
                row = (index // 32) + (block_index // 2) * 32
            else:
                col = index % 32
                row = (index // 32) + block_index * 32
            if col < width and row < height:
                out[row * width + col] = entry
    return out


def render_map(vram: bytes, pram: bytes, bg: dict, size: tuple,
               hofs: int, vofs: int, char_base_block: int | None = None,
               color_mode_256: bool | None = None):
    """Render one background at one scroll offset; returns a PIL image."""
    from PIL import Image

    name, width, height, _ = size
    entries = tilemap_for(vram, bg, size)
    if char_base_block is None:
        char_base_block = bg["char_base_block"]
    if color_mode_256 is None:
        color_mode_256 = bg["color_mode_256"]
    char_base = char_base_block * 0x10000
    palette = (bg_palette_256(pram) if color_mode_256 else None)
    tile_cache: dict[int, list] = {}
    bank_cache: dict[int, list] = {}
    image = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
    pixels = image.load()
    for screen_y in range(SCREEN_H):
        for screen_x in range(SCREEN_W):
            map_x = (screen_x + hofs) // 8
            map_y = (screen_y + vofs) // 8
            if map_x >= width or map_y >= height:
                continue
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
                tile_cache[tile] = tile_pixels(vram, char_base, tile, color_mode_256)
            index = tile_cache[tile][(screen_y + vofs) % 8][(screen_x + hofs) % 8]
            if index == 0:
                continue
            pixels[screen_x, screen_y] = colors[index]
    return image


def sample_points(step: int = 8) -> list[tuple[int, int]]:
    return [(x, y) for y in range(4, SCREEN_H, step)
            for x in range(4, SCREEN_W, step)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--raw", required=True, help="ground truth rawshot RGBA")
    parser.add_argument("--out", default="")
    parser.add_argument("--full", action="store_true",
                        help="also brute force every scroll offset")
    args = parser.parse_args()

    from PIL import Image

    raw = pathlib.Path(args.raw).read_bytes()
    truth = Image.frombytes("RGBA", (SCREEN_W, SCREEN_H), raw).convert("RGB")
    truth_pixels = truth.load()

    state = load(pathlib.Path(args.state))
    io = io_info(state.read_memory(IO_BASE, IO_LENGTH))
    pram = state.read_memory(PRAM_BASE, PRAM_LENGTH)
    vram = state.read_memory(VRAM_BASE, VRAM_LENGTH)

    points = sample_points(6)
    best = []
    for index in range(4):
        bg = decode_bg(io["bg_cnt"][index])
        for size in SCREEN_SIZES:
            for char_base_block in range(4):
                for color_mode_256 in (False, True):
                    for hofs, vofs in [(0, 0), (240, 24), (184, 40), (77, 124),
                                       (200, 31), (56, 136), (152, 144)]:
                        image = render_map(vram, pram, bg, size, hofs, vofs,
                                           char_base_block, color_mode_256)
                        pixels = image.load()
                        same = sum(1 for x, y in points
                                   if pixels[x, y] == truth_pixels[x, y])
                        best.append((same, index, size[0], char_base_block,
                                     int(color_mode_256), hofs, vofs))
    best.sort(reverse=True)
    print("top candidates (same sample pixels of %d):" % len(points))
    for row in best[:10]:
        print("   ", row)

    if args.full:
        print("brute forcing every scroll offset for the best layer/size ...")
        index, size_name = best[0][1], best[0][2]
        size = next(s for s in SCREEN_SIZES if s[0] == size_name)
        bg = decode_bg(io["bg_cnt"][index])
        hits = []
        width, height = size[1], size[2]
        for vofs in range(height - 128 if height > 128 else 1):
            for hofs in range(width - 224 if width > 224 else 1):
                image = render_map(vram, pram, bg, size, hofs, vofs)
                pixels = image.load()
                same = sum(1 for x, y in points
                           if pixels[x, y] == truth_pixels[x, y])
                if same > len(points) * 0.8:
                    hits.append((same, hofs, vofs))
        hits.sort(reverse=True)
        print("hits:", hits[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
