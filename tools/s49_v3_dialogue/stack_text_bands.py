"""Scratch: stack the dialogue text regions of several frames into one image.

Answers one question: which dialogue screen does each frame show, and does the
remake show the same text as the original at the same moment?

The crop is the interior of the dialogue box (the rows 103..152 of the
240x160 screen), the speaker label included.  The crops are stacked
vertically with a separator so that one picture shows the whole sequence.

Usage:
    python tools/s49_v3_dialogue/stack_text_bands.py --out out.png frame1 frame2 ...
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

REGION = (4, 100, 236, 140)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("frames", nargs="+")
    args = parser.parse_args()

    crops = []
    for argument in args.frames:
        path = pathlib.Path(argument)
        with Image.open(path) as image:
            crops.append((path.stem, image.convert("RGB").crop(REGION)))
    width = max(crop.size[0] for _, crop in crops)
    height = sum(crop.size[1] + 4 for _, crop in crops)
    sheet = Image.new("RGB", (width, height), (255, 0, 255))
    offset = 0
    for name, crop in crops:
        sheet.paste(crop, (0, offset))
        offset += crop.size[1] + 4
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet = sheet.resize((width * 2, height * 2), Image.NEAREST)
    sheet.save(out)
    print(f"{out}  {sheet.size[0]}x{sheet.size[1]}  frames={len(crops)}")
    for name, _ in crops:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
