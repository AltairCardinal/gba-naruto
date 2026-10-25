#!/usr/bin/env python3
"""Render the header strip of every stable screen of the original's chain.

Stream U3 (wave 10).  The settlement chain's per-screen text (level-up
headers, dialogue pages) is the content the remake has to reproduce, so the
headers are rendered one by one for an exact transcription.

Usage::

    python tools/s49_u3_settlement/u3_render_headers.py \
        --stable build/s49-u3-settlement/stable-screens.json \
        --frames build/s49-victory-capture/w4/settlementA/frames \
        --out build/s49-u3-settlement/headers
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
    parser.add_argument("--from", dest="first", type=int, default=1)
    parser.add_argument("--to", dest="last", type=int, default=0)
    args = parser.parse_args(argv)

    document = json.loads(args.stable.read_text(encoding="utf-8"))
    screens = document["stable_screens"]
    last = args.last or len(screens)
    args.out.mkdir(parents=True, exist_ok=True)

    for index, screen in enumerate(screens):
        number = index + 1
        if number < args.first or number > last:
            continue
        source = args.frames / screen["file"]
        with Image.open(source) as image:
            rgb = image.convert("RGB")
            rgb.crop((0, 0, 240, 20)).resize((240 * 4, 20 * 4),
                                             Image.LANCZOS).save(
                args.out / f"h{number:02d}-f{screen['start']}.png")
        print(f"#{number:02d} f{screen['start']}..{screen['end']} {screen['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
