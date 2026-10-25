#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Crop a region of a frame and scale it up, so small text widgets can be read.

Usage:
    python tools/s49_w25h1/crop_zoom.py --image <png> --box x0 y0 x1 y1 \
        --scale 4 --out <png>
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--box", nargs=4, type=int, required=True)
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    img = Image.open(args.image).convert("RGB")
    crop = img.crop(tuple(args.box))
    crop = crop.resize(
        (crop.width * args.scale, crop.height * args.scale), Image.NEAREST)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    crop.save(args.out)
    print(f"wrote {args.out} ({crop.width}x{crop.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
