#!/usr/bin/env python3
"""W23-F4: count the differing pixels between two PNGs inside a box.

Used to separate the settlement screen's **numbers** (rows 110-152, columns
95-232) from its **frame** (rows 106-108 and the inner border line), so the
receipt can state which part of the screen still differs.

Usage:
    python tools/s49_w23f4/diff_box.py --a truth.png --b remake.png \
        --box 95 110 232 152 --out build/w23-f4/box-diff.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from PIL import Image, ImageChops


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", required=True, type=pathlib.Path)
    parser.add_argument("--b", required=True, type=pathlib.Path)
    parser.add_argument("--box", nargs=4, type=int, required=True,
                        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args(argv)

    left, top, right, bottom = args.box
    first = Image.open(args.a).convert("RGB").crop((left, top, right, bottom))
    second = Image.open(args.b).convert("RGB").crop((left, top, right, bottom))
    diff = ImageChops.difference(first, second)
    bands = diff.getbbox()
    pixels = sum(1 for pixel in diff.getdata() if pixel != (0, 0, 0))
    result = {
        "a": str(args.a), "b": str(args.b),
        "box": [left, top, right, bottom],
        "diff_px": pixels,
        "bbox": list(bands) if bands else None,
        "size": list(first.size),
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
