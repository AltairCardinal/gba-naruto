#!/usr/bin/env python3
"""Check which glyphs the remake's result sprite font already carries.

Stream U3 (wave 10).  The post-battle dialogue text is read from the
original's frames; the remake draws the settlement screens with
``battle_result_font`` (a sprite font over ``battle_result_font.bmp``).
This tool answers one yes/no question:

    *Can the remake's existing result font render the post-battle dialogue
     and the level-up headers, or does the font need new glyphs?*

Usage::

    python tools/s49_u3_settlement/u3_font_coverage.py
"""

from __future__ import annotations

import pathlib
import re
import sys

FONT_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include"
    r"\konoha\battle_result_sprite_font.h")

# The seven post-battle dialogue pages of S49 battle-14, transcribed from
# build/s49-victory-capture/w4/settlementA/frames (see the U3 report).
DIALOGUE_PAGES = (
    ("鸣人", "跟你説已經没事了吧！"),
    ("木叶丸", "嗚哇！別过来呀！！"),
    ("小樱", "没关系了啦，已经没有蜜蜂了！不要害怕了！！"),
    ("木叶丸", "嗚哇！！！"),
    ("鸣人", "木叶丸！！"),
    ("佐助", "喂，他跑到森林的深处了！"),
    ("卡卡西", "不好，看样子那家伙快不行了……你们快去把他追回来。"),
)

# The level-up screen headers / rows of the original.
LEVEL_UP_TEXT = (
    "漩涡鸣人的升到级了宁智波佐助木叶丸动作训练现在可以修炼"
    "体力查克拉攻防敏捷移动忍具数第页"
)


def font_characters() -> str:
    text = FONT_HEADER.read_text(encoding="utf-8")
    head = text.split("battle_result_font_character_widths")[0]
    quoted = re.findall(r'"([^"]*)"', head)
    return "".join(item for item in quoted if len(item) == 1)


def main() -> int:
    if not FONT_HEADER.is_file():
        print(f"ERR missing {FONT_HEADER}")
        return 2
    available = font_characters()
    print(f"result font glyphs: {len(available)}")

    missing_total: set[str] = set()
    for speaker, line in DIALOGUE_PAGES:
        missing = sorted({c for c in speaker + line if c not in available})
        missing_total.update(missing)
        print(f"  {speaker:>4}  missing={''.join(missing) if missing else '(none)'}")

    missing_level = sorted({c for c in LEVEL_UP_TEXT if c not in available})
    print(f"level-up text missing: {''.join(missing_level) if missing_level else '(none)'}")
    print(f"TOTAL missing glyphs: {len(missing_total) + len(missing_level)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
