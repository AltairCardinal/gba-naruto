#!/usr/bin/env python3
"""Test whether the original's postbattle word IDs resolve in its dialogue bank.

Stream U3 (wave 10).  The remake's reward table already carries the
original's per-battle post-battle **word IDs** (``battle_reward_definition::
postbattle_words``), but nothing consumes them.  If those IDs address the
original's dialogue text region, the post-battle dialogue text can be derived
from the ROM instead of transcribed from frames.

This tool answers one yes/no question:

    *Do S49 battle-14's postbattle word IDs address entries of the original's
     dialogue bank?*

Usage::

    python tools/s49_u3_settlement/u3_postbattle_words.py
"""

from __future__ import annotations

import json
import pathlib

REVERSE_BANK = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-reverse\sequel\content\text"
    r"\dialogue-bank-full.json")

# S49 battle-14 -> reward record 39 -> postbattle_words.
TARGET_WORDS = (4608, 10240, 2561, 3073, 3585, 3841)


def main() -> int:
    bank = json.loads(REVERSE_BANK.read_text(encoding="utf-8"))
    by_offset = {entry.get("text_offset"): entry for entry in bank}

    print(f"dialogue bank entries: {len(bank)}")
    print(f"postbattle word ids : {list(TARGET_WORDS)}")
    for word in TARGET_WORDS:
        entry = by_offset.get(word)
        if entry is None:
            print(f"  {word:>6}: no entry with that text_offset")
            continue
        print(f"  {word:>6}: slot={entry['slot']!r} "
              f"text_ja={entry['text_ja']!r}")

    offsets = sorted(key for key in by_offset if key is not None)
    print(f"bank text_offset range: {offsets[0]}..{offsets[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
