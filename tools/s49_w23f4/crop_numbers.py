#!/usr/bin/env python3
"""W23-F4: crop the settlement screen's number area out of two PNGs.

The settlement screen differs from the original's truth only inside the
number area (rows 106-153, columns 88-235), so cropping that area makes the
remaining difference readable by eye.

Usage:
    python tools/s49_w23f4/crop_numbers.py \
        --truth build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
        --remake build/w23-f4/run/shots/page-001-result.png \
        --out-dir build/w23-f4/numbers
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image

BOX = (84, 100, 240, 158)   # the number area of the settlement screen
SCALE = 4


def crop(source: pathlib.Path, target: pathlib.Path, box=BOX, scale=SCALE) -> None:
    image = Image.open(source).convert("RGB").crop(box)
    image = image.resize((image.width * scale, image.height * scale),
                         Image.NEAREST)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", required=True, type=pathlib.Path)
    parser.add_argument("--remake", required=True, type=pathlib.Path)
    parser.add_argument("--out-dir", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)

    crop(args.truth, args.out_dir / "numbers-truth.png")
    crop(args.remake, args.out_dir / "numbers-remake.png")
    print(f"wrote {args.out_dir}/numbers-truth.png and numbers-remake.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
