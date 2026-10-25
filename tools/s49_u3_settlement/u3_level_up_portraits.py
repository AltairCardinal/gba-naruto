#!/usr/bin/env python3
"""Identify the original's per-person level-up screens by their portrait.

Stream U3 (wave 10).  The original's level-up stage shows one screen per
character (plus a second page per character).  The truth image names written
by wave 8 are *not* reliable, so this tool identifies each stable level-up
screen by **hashing its portrait region** -- the portrait is the character's
face, so two screens of the same character hash the same.

It answers one yes/no question:

    *How many distinct characters does the original's level-up stage show,
     and in what order?*

Usage::

    python tools/s49_u3_settlement/u3_level_up_portraits.py \
        --stable build/s49-u3-settlement/stable-screens.json \
        --frames build/s49-victory-capture/w4/settlementA/frames
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from PIL import Image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable", type=pathlib.Path, required=True)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=6)
    args = parser.parse_args(argv)

    document = json.loads(args.stable.read_text(encoding="utf-8"))
    screens = document["stable_screens"]

    seen: dict[str, int] = {}
    for index, screen in enumerate(screens):
        number = index + 1
        if number < args.first or number > args.last:
            continue
        source = args.frames / screen["file"]
        with Image.open(source) as image:
            portrait = image.convert("RGB").crop((16, 24, 112, 120))
        digest = hashlib.sha256(portrait.tobytes()).hexdigest()
        character = seen.setdefault(digest, len(seen) + 1)
        print(f"#{number:02d} f{screen['start']:>6}..{screen['end']:<6} "
              f"portrait#{character} {digest[:16]} {screen['file']}")
    print(f"distinct portraits: {len(seen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
