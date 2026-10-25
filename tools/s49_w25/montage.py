#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a side-by-side + diff montage for a list of (original, remake) frame pairs.

Usage:
    python tools/s49_w25/montage.py --original <dir> --remake <dir> \
        --pairs step-00-base:step-04-A step-01-A:step-05-A ... --out <png>

Each pair renders three tiles side by side: original | remake | abs-diff heat map.
Tiles are downscaled by --scale (default 2) so a whole strip fits one screen.
The diff tile marks differing pixels red on top of a dimmed grayscale base.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

TILE = 240


def load(directory: Path, stem: str) -> Image.Image:
    path = directory / f"{stem}.png"
    if not path.exists():
        raise SystemExit(f"missing frame: {path}")
    return Image.open(path).convert("RGB")


def diff_tile(a: Image.Image, b: Image.Image) -> tuple[Image.Image, int]:
    if a.size != b.size:
        b = b.resize(a.size)
    pa, pb = a.load(), b.load()
    w, h = a.size
    out = Image.new("RGB", (w, h), (0, 0, 0))
    po = out.load()
    count = 0
    for y in range(h):
        for x in range(w):
            r1, g1, b1 = pa[x, y]
            r2, g2, b2 = pb[x, y]
            if (r1, g1, b1) != (r2, g2, b2):
                count += 1
                po[x, y] = (255, 0, 0)
            else:
                v = (r1 * 30 + g1 * 59 + b1 * 11) // 100
                po[x, y] = (v // 3, v // 3, v // 3)
    return out, count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", required=True)
    ap.add_argument("--remake", required=True)
    ap.add_argument("--pairs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--columns", type=int, default=1)
    args = ap.parse_args()

    original = Path(args.original)
    remake = Path(args.remake)
    rows = []
    for pair in args.pairs:
        o_stem, r_stem = pair.split(":")
        a = load(original, o_stem)
        b = load(remake, r_stem)
        d, count = diff_tile(a, b)
        rows.append((o_stem, r_stem, a, b, d, count))

    tw = TILE
    th = TILE
    label_h = 16
    cols = args.columns
    row_count = (len(rows) + cols - 1) // cols
    canvas = Image.new("RGB", (tw * 3 * cols, (th + label_h) * row_count), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    for idx, (o_stem, r_stem, a, b, d, count) in enumerate(rows):
        cx = (idx % cols) * tw * 3
        cy = (idx // cols) * (th + label_h)
        for k, (img, name) in enumerate(((a, f"orig {o_stem}"), (b, f"remake {r_stem}"), (d, f"diff {count}px"))):
            small = img.resize((tw, th), Image.LANCZOS)
            canvas.paste(small, (cx + k * tw, cy + label_h))
            draw.text((cx + k * tw + 2, cy + 2), name, fill=(255, 255, 0))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print(f"wrote {out} ({canvas.size[0]}x{canvas.size[1]})")
    for o_stem, r_stem, _a, _b, _d, count in rows:
        print(f"  {o_stem:>14}  vs  {r_stem:<14}  diff={count} px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
