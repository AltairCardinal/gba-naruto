#!/usr/bin/env python3
"""Which of the remake's two fonts can render the transcribed dialogue?

Stream U3 (wave 10).  The post-battle dialogue is new text that the remake has
to draw.  The remake has **two** candidate fonts:

* ``battle_result_font`` — the settlement screen's own UTF-8 sprite font
  (401 glyphs, ``battle_result_sprite_font.h``);
* the presentation font — the original's own Shift-JIS dialogue font
  (862 codes, ``generated_battle_presentation_glyph_content.h``).

This tool checks the transcribed dialogue against **both**, so the wiring note
says exactly which font has to grow and by how much.

Usage::

    python tools/s49_u3_settlement/u3_font_gap.py
"""

from __future__ import annotations

import pathlib
import re

INCLUDE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha")
RESULT_FONT = INCLUDE / "battle_result_sprite_font.h"
PRESENTATION_FONT = (
    INCLUDE / "generated_battle_presentation_glyph_content.h")

DIALOGUE = (
    "跟你説已經没事了吧！",
    "嗚哇！別过来呀！！",
    "没关系了啦，已经没有蜜蜂了！不要害怕了！！",
    "嗚哇！！！",
    "木叶丸！！",
    "喂，他跑到森林的深处了！",
    "不好，看样子那家伙快不行了……你们快去把他追回来。",
)

LEVEL_UP = (
    "漩涡鸣人的LV升到6级了",
    "螺旋丸的现在可以修炼了",
    "宁智波佐助的LV升到5级了",
    "动作训练班可以修炼了",
    "春野樱的LV升到6级了",
    "忍者知识现在可以修炼了",
)


def result_font_characters() -> set[str]:
    text = RESULT_FONT.read_text(encoding="utf-8")
    head = text.split("battle_result_font_character_widths")[0]
    return {item for item in re.findall(r'"([^"]*)"', head) if len(item) == 1}


def presentation_font_codes() -> set[int]:
    text = PRESENTATION_FONT.read_text(encoding="utf-8")
    body = text.split("battle_presentation_glyph_codes = {{", 1)[1]
    body = body.split("}};", 1)[0]
    return {int(code, 16) for code in re.findall(r"0x([0-9A-Fa-f]{4})", body)}


def main() -> int:
    lines = (*DIALOGUE, *LEVEL_UP)

    characters = result_font_characters()
    missing = sorted({c for line in lines for c in line if c not in characters})
    print(f"battle_result_font (UTF-8, {len(characters)} glyphs)")
    print(f"  missing characters: {len(missing)}")
    if missing:
        print(f"  {''.join(missing)}")

    codes = presentation_font_codes()
    missing_codes: set[int] = set()
    encoded = 0
    for line in lines:
        for character in line:
            data = character.encode("cp932", errors="replace")
            if len(data) == 1:
                continue
            encoded += 1
            code = (data[0] << 8) | data[1]
            if code not in codes:
                missing_codes.add(code)
    print(f"\npresentation font (Shift-JIS, {len(codes)} codes)")
    print(f"  encoded multi-byte characters: {encoded}")
    print(f"  missing codes: {len(missing_codes)}")
    for code in sorted(missing_codes):
        try:
            character = bytes([code >> 8, code & 0xFF]).decode("cp932")
        except UnicodeDecodeError:
            character = "?"
        print(f"    0x{code:04X} = {character!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
