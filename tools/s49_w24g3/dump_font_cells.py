#!/usr/bin/env python3
"""W24-G3: dump the `battle_result_font.bmp` atlas cells for the ASCII digits.

Butano's sprite font puts ASCII glyphs first: graphics_index = char - '!'.
So '0' -> cell 15, '2' -> cell 17, '3' -> cell 18, '5' -> cell 20.
A cell is 8 pixels wide and 16 pixels tall, stacked down the atlas.

Usage:
  python tools/s49_w24g3/dump_font_cells.py [--out build/w24-g3]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
ATLAS = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\battle_result_font.bmp")

CELL_W = 8
CELL_H = 16


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "build/w24-g3"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    im = Image.open(ATLAS).convert("P")
    im = Image.open(ATLAS)
    w, h = im.size
    pal = im.getpalette()
    px = im.load()
    cells = h // CELL_H

    used = Counter(im.getdata())
    palette = {
        idx: list(pal[idx * 3:idx * 3 + 3]) for idx in sorted(used)
    }

    print(f"atlas {w}x{h}  cells={cells}  distinct indices={sorted(used)}")
    for idx in sorted(used):
        print(f"  index {idx} -> {palette[idx]}  count {used[idx]}")

    def dump(index: int, ch: str | None = None) -> list[str]:
        art = []
        print(f"--- cell {index}" + (f" ('{ch}')" if ch else ""))
        for y in range(CELL_H):
            row = ""
            for x in range(CELL_W):
                row += str(px[x, index * CELL_H + y])
            art.append(row)
            print(f"   {row}")
        return art

    wanted = {15: "0", 17: "2", 18: "3", 20: "5"}
    out = {"palette": palette, "atlas_size": [w, h], "cells": {}}
    for index, ch in wanted.items():
        out["cells"][ch] = {"index": index, "art": dump(index, ch)}

    # Which indices are used by the digit cells only?  (those are the ones a
    # recolour may touch.)
    digit_indices = Counter()
    for index in wanted:
        for y in range(CELL_H):
            for x in range(CELL_W):
                digit_indices[px[x, index * CELL_H + y]] += 1
    out["digit_cell_indices"] = dict(digit_indices)
    print("\ndigit cells use indices:", dict(digit_indices))

    with open(out_dir / "font-cells.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"written: {out_dir / 'font-cells.json'}")


if __name__ == "__main__":
    main()
