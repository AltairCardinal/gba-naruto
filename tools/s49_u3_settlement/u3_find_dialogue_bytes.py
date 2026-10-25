#!/usr/bin/env python3
"""Find the original's post-battle dialogue bytes in the reverse dialogue bank.

Stream U3 (wave 10).  The remake stores dialogue as the original's raw byte
codes (``battle_presentation_text``) and renders them through the original's
own font (``battle_presentation_glyph_codes``).  To author the post-battle
dialogue the remake needs the **byte codes** of the transcribed text, not
just a Unicode string.

This tool searches the reverse line's (read-only) dialogue bank for the
post-battle lines, decoding every entry as both cp932 and gbk, and reports
the entries that match the lines read from the original's frames.

This tool answers one yes/no question:

    *Do the original's post-battle dialogue bytes exist in the reverse line's
     dialogue bank, and what are they?*

Usage::

    python tools/s49_u3_settlement/u3_find_dialogue_bytes.py
"""

from __future__ import annotations

import json
import pathlib

REVERSE_BANK = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-reverse\sequel\content\text"
    r"\dialogue-bank-full.json")

# The post-battle lines, read from the original's frames.
LINES = (
    "跟你說已經沒事了吧",
    "嗚哇",
    "別過來呀",
    "沒關係了啦",
    "已經沒有蜜蜂了",
    "不要害怕了",
    "他跑到森林的深處了",
    "他跑",
    "看樣子那家伙快不行了",
    "你們快去把他追回來",
)


def decode(raw: bytes, codec: str) -> str:
    try:
        return raw.decode(codec, errors="replace")
    except LookupError:
        return ""


def main() -> int:
    bank = json.loads(REVERSE_BANK.read_text(encoding="utf-8"))
    print(f"bank entries: {len(bank)}")

    hits = 0
    for entry in bank:
        raw = bytes.fromhex(entry.get("raw_hex", ""))
        for codec in ("gbk", "cp932", "big5"):
            text = decode(raw, codec)
            for line in LINES:
                if line in text:
                    hits += 1
                    print(f"  [{codec}] idx={entry['idx']} "
                          f"slot={entry['slot']}")
                    print(f"      {text!r}")
                    print(f"      raw={entry['raw_hex'][:120]}")
    print(f"hits: {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
