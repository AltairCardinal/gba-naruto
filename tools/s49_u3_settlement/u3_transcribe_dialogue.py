#!/usr/bin/env python3
"""Transcribe the original's S49 post-battle dialogue pages from the frames.

Stream U3 (wave 10).  The post-battle dialogue is one of the two chain
segments the remake is missing (S1).  The text has to come from the
original's own frames, and the frames are the only source that has it (the
reverse line's dialogue bank does **not** contain these lines: see
``u3_find_dialogue_bytes.py``, 0 hits).

This tool crops the dialogue box of every stable post-battle screen at 6x so
the lines can be transcribed by eye, and records the speaker label's colour so
the speaker can be identified.

Usage::

    python tools/s49_u3_settlement/u3_transcribe_dialogue.py \
        --stable build/s49-u3-settlement/stable-screens.json \
        --frames build/s49-victory-capture/w4/settlementA/frames \
        --out build/s49-u3-settlement/dialogue
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
            # The speaker label sits at the left of the text box; the body
            # text is under it.  Crop both and scale for transcription.
            rgb.crop((6, 96, 234, 152)).resize((228 * 6, 56 * 6),
                                               Image.LANCZOS).save(
                args.out / f"dlg-{number:02d}-f{screen['start']}.png")
        print(f"#{number:02d} f{screen['start']}..{screen['end']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
