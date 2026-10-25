#!/usr/bin/env python3
"""Render a contact sheet of the original's settlement chain.

Stream U3 (wave 10).  The chain's true structure (how many screens, in what
order) is the ground truth the remake's chain has to match, so the stable
screens are laid out in one page for a single look.

Usage::

    python tools/s49_u3_settlement/u3_chain_sheet.py \
        --stable build/s49-u3-settlement/stable-screens.json \
        --frames build/s49-victory-capture/w4/settlementA/frames \
        --out build/s49-u3-settlement/chain-sheet.png
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image, ImageDraw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable", type=pathlib.Path, required=True)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--scale", type=int, default=2)
    args = parser.parse_args(argv)

    document = json.loads(args.stable.read_text(encoding="utf-8"))
    screens = document["stable_screens"]

    width = 240 * args.scale
    height = 160 * args.scale
    label = 18
    columns = args.columns
    rows = (len(screens) + columns - 1) // columns

    sheet = Image.new("RGB", (columns * width, rows * (height + label)),
                      (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for index, screen in enumerate(screens):
        source = args.frames / screen["file"]
        with Image.open(source) as image:
            tile = image.convert("RGB").resize((width, height), Image.LANCZOS)
        x = (index % columns) * width
        y = (index // columns) * (height + label)
        sheet.paste(tile, (x, y))
        draw.text((x + 3, y + height + 3),
                  f"#{index + 1} f{screen['start']}", fill=(255, 255, 255))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"{len(screens)} screens -> {args.out} ({sheet.size[0]}x{sheet.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
