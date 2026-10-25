"""Scratch: magnified strip of a text band across a frame range."""
from __future__ import annotations

import pathlib
import sys

from PIL import Image


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    first = int(sys.argv[2])
    last = int(sys.argv[3])
    out = pathlib.Path(sys.argv[4])
    left = int(sys.argv[5]) if len(sys.argv) > 5 else 20
    right = int(sys.argv[6]) if len(sys.argv) > 6 else 80
    top = int(sys.argv[7]) if len(sys.argv) > 7 else 116
    bottom = int(sys.argv[8]) if len(sys.argv) > 8 else 140
    scale = int(sys.argv[9]) if len(sys.argv) > 9 else 4
    strips = []
    for index in range(first, last + 1):
        png = None
        for suffix in ("in", "beat", "base"):
            candidate = src / f"step-{index:04d}-{suffix}.png"
            if candidate.exists():
                png = candidate
                break
        if png is None:
            continue
        with Image.open(png) as handle:
            strip = handle.convert("RGB").crop((left, top, right, bottom))
        strips.append((index, strip))
    if not strips:
        print("no frames")
        return 1
    width = (right - left) * scale
    height = (bottom - top) * scale
    sheet = Image.new("RGB", (width, height * len(strips)), (255, 0, 255))
    for row, (index, strip) in enumerate(strips):
        sheet.paste(strip.resize((width, height), Image.NEAREST),
                    (0, row * height))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"{out} frames={len(strips)} first={strips[0][0]} last={strips[-1][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
