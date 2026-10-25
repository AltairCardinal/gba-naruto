#!/usr/bin/env python3
"""Find the original's ``請準備...`` window tiles inside VRAM.

The saved display registers do not describe the captured frame (see
``find_bg.py``), so the window is located **from the pixels**:

* the window's colours are read out of the ground-truth frame; they all live
  in one PRAM palette bank (measured: bank 14 for the ``請準備...`` box),
* every **8-pixel-aligned** block of the window is matched against every
  (character base, colour mode, tile index) in VRAM rendered with that bank,
* the matching tile is then located in the tilemaps, which gives the window's
  map position -- and therefore the scroll offset.

Usage::

    python tools/s49_w23f2/find_window_tiles.py --state <a.ss9> --raw <gt.raw> \
        --box <x0,y0,x1,y1> [--bank 14] --out <json>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "s49_w23f2"))

from gba_frame import (  # noqa: E402
    IO_BASE, IO_LENGTH, PRAM_BASE, PRAM_LENGTH, VRAM_BASE, VRAM_LENGTH,
    bg_palette, bg_palette_256, decode_bg, io_info, load, tile_pixels,
)

SCREEN_W = 240
SCREEN_H = 160


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--box", required=True)
    parser.add_argument("--bank", type=int, default=14)
    parser.add_argument("--min-coverage", type=int, default=40)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    from PIL import Image

    raw = pathlib.Path(args.raw).read_bytes()
    truth = Image.frombytes("RGBA", (SCREEN_W, SCREEN_H), raw).convert("RGB")
    pixels = truth.load()

    x0, y0, x1, y1 = (int(value) for value in args.box.split(","))
    counts = Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            counts[pixels[x, y]] += 1
    print(f"window box {(x0, y0, x1, y1)} size {x1 - x0}x{y1 - y0}")
    for colour, count in counts.most_common(8):
        print("   ", colour, count)

    state = load(pathlib.Path(args.state))
    io = io_info(state.read_memory(IO_BASE, IO_LENGTH))
    pram = state.read_memory(PRAM_BASE, PRAM_LENGTH)
    vram = state.read_memory(VRAM_BASE, VRAM_LENGTH)

    palette = bg_palette(pram, args.bank)
    linear = bg_palette_256(pram)

    # Pre-render every tile of every character base once, in all four
    # flip combinations (the game stores tiles pre-flipped and sets the flip
    # bits in the tilemap entry, so a block can match a mirrored tile).
    tile_sets = {}
    for char_base_block in range(4):
        for color_mode_256 in (False, True):
            base = [tile_pixels(vram, char_base_block * 0x10000, tile,
                                color_mode_256)
                    for tile in range(1024)]
            variants = []
            for tile_px in base:
                for hflip in (False, True):
                    for vflip in (False, True):
                        variants.append((
                            tile_px,
                            [[tile_px[7 - y][7 - x] if hflip and vflip else
                              (tile_px[7 - y][x] if vflip else
                               (tile_px[y][7 - x] if hflip else tile_px[y][x]))
                              for x in range(8)] for y in range(8)],
                        ))
            tile_sets[(char_base_block, color_mode_256)] = variants

    results = []
    for by in range(y0 - y0 % 8 + 8, y1, 8):
        for bx in range(x0 - x0 % 8 + 8, x1, 8):
            target = [pixels[bx + (index % 8), by + (index // 8)]
                      for index in range(64)]
            for (char_base_block, color_mode_256), variants in tile_sets.items():
                colors = linear if color_mode_256 else palette
                for variant_index, (flat, _flipped) in enumerate(variants):
                    covered = 0
                    score = 0
                    for index in range(64):
                        value = flat[index // 8][index % 8]
                        if value == 0:
                            continue
                        covered += 1
                        if colors[value] == target[index]:
                            score += 1
                    if covered >= args.min_coverage and score == covered:
                        results.append({
                            "screen_block": [bx, by],
                            "char_base_block": char_base_block,
                            "color_mode_256": color_mode_256,
                            "tile": variant_index // 4,
                            "hflip": bool(variant_index % 4 in (1, 2)),
                            "vflip": bool(variant_index % 4 in (2, 3)),
                            "covered": covered,
                        })
    print("matches:", len(results))
    for row in results[:40]:
        print("   ", row)

    # Where does each matching tile sit in the tilemaps?
    document = {"box": [x0, y0, x1, y1], "bank": args.bank, "matches": results,
                "positions": {}}
    for index in range(4):
        bg = decode_bg(io["bg_cnt"][index])
        base = bg["screen_base_block"] * 0x800
        raw_map = vram[base:base + 0x800]
        entries = [raw_map[i] | (raw_map[i + 1] << 8) for i in range(0, 0x800, 2)]
        for row in results:
            key = (row["char_base_block"], row["color_mode_256"], row["tile"])
            spots = [(i % 32, i // 32) for i in range(1024)
                     if (entries[i] & 0x3FF) == row["tile"]]
            if spots:
                document["positions"].setdefault(str(key), {})[f"bg{index}"] = spots
    for key, value in document["positions"].items():
        print(key, "->", {name: spots[:6] for name, spots in value.items()})

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
