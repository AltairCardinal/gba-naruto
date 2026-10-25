#!/usr/bin/env python3
"""Check the post-battle dialogue text against the remake's glyph set.

Stream U3 (wave 10).  The original's post-battle dialogue is transcribed from
the recorded frames; the remake draws dialogue with the Shift-JIS presentation
font (``battle_presentation_glyph_codes``, 862 codes extracted from the
original's own dialogue font).

This tool answers one yes/no question:

    *Can the remake's existing presentation font render the transcribed
     post-battle dialogue as-is, or does it need new glyphs?*

Usage::

    python tools/s49_u3_settlement/u3_dialogue_glyphs.py
"""

from __future__ import annotations

import pathlib
import re
import sys

GLYPH_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
    r"\konoha\generated_battle_presentation_glyph_content.h")

# The seven post-battle dialogue pages of S49 battle-14, transcribed from
# build/s49-victory-capture/w4/settlementA/frames.
DIALOGUE_PAGES = (
    ("鸣人", "「跟你説已經没事了吧！」"),
    ("木叶丸", "「嗚哇！別过来呀！！」"),
    ("小樱", "「没关系了啦，已经没有蜜蜂了！不要害怕了！！」"),
    ("木叶丸", "「嗚哇！！！」"),
    ("鸣人", "「木叶丸！！」"),
    ("佐助", "「喂，他跑到森林的深处了！」"),
    ("卡卡西", "「不好，看样子那家伙快不行了……你们快去把他追回来。」"),
)


def glyph_codes() -> set[int]:
    text = GLYPH_HEADER.read_text(encoding="utf-8")
    body = text.split("battle_presentation_glyph_codes = {{", 1)[1]
    body = body.split("}};", 1)[0]
    return {int(code, 16) for code in re.findall(r"0x([0-9A-Fa-f]{4})", body)}


def main() -> int:
    if not GLYPH_HEADER.is_file():
        print(f"ERR missing {GLYPH_HEADER}")
        return 2
    codes = glyph_codes()
    print(f"presentation glyphs: {len(codes)}")

    missing_total: set[int] = set()
    for speaker, line in DIALOGUE_PAGES:
        missing: list[str] = []
        for character in speaker + line:
            try:
                code = ord(character)
            except ValueError:
                continue
            if code > 0xFF and code not in codes:
                missing.append(character)
        missing_total.update(ord(c) for c in missing)
        print(f"  {speaker}: missing={''.join(missing) if missing else '(none)'}")
    print(f"TOTAL missing glyphs: {len(missing_total)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
