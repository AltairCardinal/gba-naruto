#!/usr/bin/env python3
"""Render the post-battle dialogue text at 8x for exact transcription.

Stream U3 (wave 10).  S1's content is the post-battle dialogue, and it has
to be transcribed **exactly** -- it is authored into a header as text.

This tool crops the text box of every stable post-battle screen and scales it
up so each glyph can be read, writing one PNG per page.

Usage::

    python tools/s49_u3_settlement/u3_dialogue_zoom.py \
        --stable build/s49-u3-settlement/stable-screens.json \
        --frames build/s49-victory-capture/w4/settlementA/frames \
        --out build/s49-u3-settlement/dialogue-zoom
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable", type=pathlib.Path, required=True)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--first", type=int, default=21)
    parser.add_argument("--last", type=int, default=27)
    args = parser.parse_args(argv)

    document = json.loads(args.stable.read_text(encoding="utf-8"))
    screens = document["stable_screens"]
    args.out.mkdir(parents=True, exist_ok=True)

    for index, screen in enumerate(screens):
        number = index + 1
        if number < args.first or number > args.last:
            continue
        source = args.frames / screen["file"]
        with Image.open(source) as image:
            rgb = image.convert("RGB")
            # Two halves so each stays legible when scaled 8x.
            rgb.crop((6, 96, 130, 150)).resize((124 * 8, 54 * 8),
                                                Image.LANCZOS).save(
                args.out / f"p{number:02d}-left.png")
            rgb.crop((6, 118, 234, 150)).resize((228 * 6, 32 * 6),
                                                Image.LANCZOS).save(
                args.out / f"p{number:02d}-right.png")
        print(f"#{number:02d} f{screen['start']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
