#!/usr/bin/env python3
"""Generate fixed battle identity catalogs and the Butano UTF-8 sprite font."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit_butano_reverse_provenance import provenance_block

PROVENANCE = provenance_block(
    sources=(
        (
            "rom-fixed-consumer-text-inventory-v1",
            "560464a6fed43de1a77c6339362dc2ef28534a7374ff976df572d05a9bad6b94",
        ),
    ),
    roms=(
        (
            0x599280,
            252,
            "68e8c6fc03c6a321ef701611aea372dd88e22aa16bd795706ec6e8ddb6946a1d",
        ),
        (
            0x59937C,
            348,
            "72c9247c5660a892890fb85da8606d9d47a3d15e01d06aee53dff7f5189145ac",
        ),
        (
            0x5A7C50,
            376,
            "403cb842a3018e1da6fcbd8cbca9bb55f554cc17065499c76c7214088f932d65",
        ),
    ),
)

# The sprite font headers are a remake side reconstruction, not a ROM byte
# derivative: the glyph bitmaps are cropped from original screenshots or
# rendered with a system font, the character widths come from Butano's own
# sprite font metrics and the character list is the deduplicated set of the
# identity display names that ``generated_battle_identity_content.h``
# declares.  The header therefore consumes no ROM byte region at all.
FONT_PROVENANCE = provenance_block(
    not_applicable=(
        "the sprite font is a remake side reconstruction, not a ROM byte "
        "derivative: the glyph bitmaps in butano-sequel/graphics are cropped "
        "from original screenshots, rendered with a system font or taken from "
        "Butano's own common font atlas, the character widths come from "
        "Butano's own sprite font metrics, and the character list is the "
        "deduplicated set of the characters of the identity display names "
        "that generated_battle_identity_content.h declares plus the original "
        "scenario 41 ui text",
    ),
    no_rom_region=True,
)

# The products this generator writes.  The provenance auditor reads this
# registry to learn the product set; it never guesses the set from a file
# name pattern.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/"
    "generated_battle_identity_content.h",
    "butano-sequel/game/include/konoha/"
    "battle_identity_sprite_font.h",
    "butano-sequel/game/include/konoha/battle_ui_sprite_font.h",
    "butano-sequel/game/include/konoha/"
    "battle_result_sprite_font.h",
    "butano-sequel/game/include/konoha/"
    "battle_result_compact_sprite_font.h",
    "butano-sequel/game/include/konoha/"
    "battle_action_menu_sprite_font.h",
    "butano-sequel/game/include/konoha/"
    "battle_preparation_sprite_font.h",
    "butano-sequel/game/include/konoha/"
    "battle_target_status_sprite_font.h",
    "butano-sequel/game/include/konoha/"
    "battle_target_metrics_sprite_font.h",
    "butano-sequel/game/include/konoha/"
    "battle_duel_status_sprite_font.h",
)


UNIT_COUNT = 63
ACTION_COUNT = 87
NINJA_TOOL_COUNT = 94
ASCII_GLYPH_COUNT = 94
ASCII_WIDTH_COUNT = ASCII_GLYPH_COUNT + 1
GLYPH_SIZE = 16
FONT_SIZE = 14
UI_GLYPH_WIDTH = 8
UI_GLYPH_HEIGHT = 16
UI_FONT_SIZE = 14
UI_FALLBACK_FONT_SIZE = 8
FONT_FACE_INDEX = 2
FOREGROUND_INDEX = 14
VALID_CONFIDENCES = {
    "runtime_visual_exact",
    "runtime_visual_ambiguous",
    "guide_address_correlated",
}
DEFAULT_FONT_PATH = Path("/System/Library/Fonts/PingFang.ttc")
RESULT_LARGE_SOURCE = (
    "artifacts/original-s49-result-gpu-20260730-323/frame.png"
)
RESULT_LARGE_GLYPH_SOURCES = {
    "经": (RESULT_LARGE_SOURCE, 24, 8),
    "验": (RESULT_LARGE_SOURCE, 32, 8),
    "值": (RESULT_LARGE_SOURCE, 40, 8),
    "鸣": (RESULT_LARGE_SOURCE, 96, 8),
    "人": (RESULT_LARGE_SOURCE, 104, 8),
    "佐": (RESULT_LARGE_SOURCE, 152, 8),
    "助": (RESULT_LARGE_SOURCE, 160, 8),
    "小": (RESULT_LARGE_SOURCE, 208, 8),
    "樱": (RESULT_LARGE_SOURCE, 216, 8),
    "合": (RESULT_LARGE_SOURCE, 24, 136),
    "计": (RESULT_LARGE_SOURCE, 32, 136),
}
RESULT_LARGE_ASCII_GLYPH_SOURCES = {
    "0": (RESULT_LARGE_SOURCE, 112, 136),
    "2": (RESULT_LARGE_SOURCE, 208, 136),
    "3": (RESULT_LARGE_SOURCE, 96, 136),
    "5": (RESULT_LARGE_SOURCE, 104, 136),
}
RESULT_COMPACT_ASCII_GLYPH_SOURCES = {
    "0": (RESULT_LARGE_SOURCE, 112, 120),
    "1": (RESULT_LARGE_SOURCE, 96, 112),
    "2": (RESULT_LARGE_SOURCE, 104, 112),
    "5": (RESULT_LARGE_SOURCE, 112, 112),
    "7": (RESULT_LARGE_SOURCE, 104, 128),
}
SCENARIO_41_UI_TEXT = (
    "开始任务吗是否可以援助木叶丸吧队伍·装备"
    "查看地图储存角色忍具卸下强化返回预览确定"
    "！？→攻击练习。用「忍者组合拳」"
    "不能使用忍术和忍具脱离为胜战斗败"
    "移动直接攻击查克拉休息行动结束本体待机体力"
    "消耗距离范围成功率对象受到的伤害指令数量进间"
    "请选择人物面对的方向使用防御・回避系的术・忍具吗"
    "经验值任务分战斗分回合分合计小"
    "伤害成功率攻防快"
    "保护木叶丸不被蜜蜂攻击受擅自到处跑，"
    "可以通过行动影响他同时把所有的都赶走"
    "傀儡人偶不会所以不要让去接近危险品敌打倒"
    "都赶走任务就算结束"
    "钢石毒草"
)
S49_COMMAND_MENU_SOURCE = (
    "artifacts/s49-original-ui-reference-v1/screens/command-menu-0.png"
)
SCENARIO_41_ORIGINAL_GLYPH_SOURCES = {
    "经": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        24,
        8,
    ),
    "验": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        32,
        8,
    ),
    "值": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        40,
        8,
    ),
    "分": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        24,
        112,
    ),
    "计": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        16,
        136,
    ),
    "援": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        88,
        8,
    ),
    "助": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        96,
        8,
    ),
    "木": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        112,
        8,
    ),
    "叶": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        120,
        8,
    ),
    "丸": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        128,
        8,
    ),
    "吧": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        136,
        8,
    ),
    "队": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        80,
        56,
    ),
    "伍": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        88,
        56,
    ),
    "·": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        96,
        56,
    ),
    "装": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        104,
        56,
    ),
    "备": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        112,
        56,
    ),
    # S49 original frame 18 renders 查克拉 as full-height 16-row glyphs in the
    # command menu, so it is cropped from the S49 command menu, not from the
    # scenario-41 prebattle screen.
    "查": (
        S49_COMMAND_MENU_SOURCE,
        16,
        56,
    ),
    "看": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        88,
        72,
    ),
    "地": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        96,
        72,
    ),
    "图": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        104,
        72,
    ),
    "开": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        80,
        88,
    ),
    "始": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        88,
        88,
    ),
    "任": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        8,
        112,
    ),
    "务": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        16,
        112,
    ),
    "储": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        80,
        104,
    ),
    "存": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        88,
        104,
    ),
    "吗": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/confirmation-yes.png",
        80,
        72,
    ),
    "是": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/confirmation-yes.png",
        168,
        72,
    ),
    "否": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/confirmation-yes.png",
        168,
        88,
    ),
    "可": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__"
        "attack-confirmation.png",
        88,
        32,
    ),
    "以": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__"
        "attack-confirmation.png",
        96,
        32,
    ),
    "！": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        144,
        8,
    ),
    "？": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/confirmation-yes.png",
        88,
        72,
    ),
    "→": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/confirmation-yes.png",
        160,
        72,
    ),
    "攻": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        8,
        40,
    ),
    "击": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        16,
        40,
    ),
    "练": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        24,
        40,
    ),
    "习": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        32,
        40,
    ),
    "。": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        40,
        40,
    ),
    "用": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        8,
        56,
    ),
    "「": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        16,
        56,
    ),
    "忍": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        24,
        56,
    ),
    "者": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        32,
        56,
    ),
    "组": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        40,
        56,
    ),
    "合": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        8,
        136,
    ),
    "拳": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        56,
        56,
    ),
    "」": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        64,
        56,
    ),
    "不": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        8,
        72,
    ),
    "能": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        16,
        72,
    ),
    "使": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        24,
        72,
    ),
    "术": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        48,
        72,
    ),
    "和": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        56,
        72,
    ),
    "具": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        72,
        72,
    ),
    "脱": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        40,
        104,
    ),
    "离": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        48,
        104,
    ),
    "为": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        56,
        104,
    ),
    "胜": (
        "artifacts/scenario-41-prebattle-reference-v1/"
        "screens/menu-0.png",
        64,
        104,
    ),
    "移": (
        S49_COMMAND_MENU_SOURCE,
        16,
        24,
    ),
    "动": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-0.png",
        20,
        24,
    ),
    "克": (
        S49_COMMAND_MENU_SOURCE,
        24,
        56,
    ),
    "拉": (
        S49_COMMAND_MENU_SOURCE,
        32,
        56,
    ),
    "休": (
        S49_COMMAND_MENU_SOURCE,
        16,
        72,
    ),
    "息": (
        S49_COMMAND_MENU_SOURCE,
        24,
        72,
    ),
    "行": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-0.png",
        12,
        88,
    ),
    "结": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-0.png",
        28,
        88,
    ),
    "束": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-0.png",
        36,
        88,
    ),
    "漩": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        8,
        136,
    ),
    "涡": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        16,
        136,
    ),
    "鸣": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        24,
        136,
    ),
    "人": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        32,
        136,
    ),
    "本": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        72,
        136,
    ),
    "体": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        80,
        136,
    ),
    "待": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        104,
        136,
    ),
    "机": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        112,
        136,
    ),
    "力": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__action-menu-1.png",
        144,
        136,
    ),
    "请": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        8,
        136,
    ),
    "选": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        16,
        136,
    ),
    "择": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        24,
        136,
    ),
    "物": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        40,
        136,
    ),
    "面": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        48,
        136,
    ),
    "对": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        56,
        136,
    ),
    "的": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        64,
        136,
    ),
    "方": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        72,
        136,
    ),
    "向": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-reference-v1__first-movedone-facing.png",
        80,
        136,
    ),
    "防": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__defense-confirmation.png",
        88,
        32,
    ),
    "御": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__defense-confirmation.png",
        96,
        32,
    ),
    "回": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        8,
        128,
    ),
    "战": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        8,
        120,
    ),
    "斗": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-extended-reference-v1__result.png",
        16,
        120,
    ),
    "避": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__defense-confirmation.png",
        120,
        32,
    ),
    "系": (
        "artifacts/scenario-41-screenshot-comparison-20260729-01/"
        "original/scenario-41-combat-reference-v1__defense-confirmation.png",
        128,
        32,
    ),
}
STATUS_HUD_SOURCE = (
    "artifacts/runtime-checkpoints/"
    "scenario-49-battle-14-entry.ss9"
)
PREPARATION_BASE_GLYPH_SOURCES = dict(
    SCENARIO_41_ORIGINAL_GLYPH_SOURCES
)
SCENARIO_41_ORIGINAL_GLYPH_SOURCES.update(
    {
        "能": (STATUS_HUD_SOURCE, 136, 136),
        "力": (STATUS_HUD_SOURCE, 144, 136),
        # 查克拉 stays an 8-row compact glyph here: the original status HUD draws
        # it at half height, and the remake matched the original there exactly.
        # The S49 command menu draws the same three characters full height, so
        # those six glyphs need a second, full-height atlas rather than a change
        # to this shared cell.  See notes/s49-fidelity-handover-20261019.md.
        "查": (STATUS_HUD_SOURCE, 136, 144),
        "克": (STATUS_HUD_SOURCE, 144, 144),
        "拉": (STATUS_HUD_SOURCE, 152, 144),
    }
)
ACTION_MENU_SOURCE = (
    "artifacts/scenario-41-screenshot-comparison-20260729-01/"
    "original/scenario-41-reference-v1__"
    "first-turn-technique-menu.png"
)
SCENARIO_41_ORIGINAL_GLYPH_SOURCES.update(
    {
        "消": (ACTION_MENU_SOURCE, 160, 8),
        "耗": (ACTION_MENU_SOURCE, 168, 8),
        "攻": (ACTION_MENU_SOURCE, 160, 24),
        "击": (ACTION_MENU_SOURCE, 168, 24),
        "距": (ACTION_MENU_SOURCE, 160, 40),
        "离": (ACTION_MENU_SOURCE, 168, 40),
        "范": (ACTION_MENU_SOURCE, 160, 56),
        "围": (ACTION_MENU_SOURCE, 168, 56),
        "成": (ACTION_MENU_SOURCE, 160, 88),
        "功": (ACTION_MENU_SOURCE, 168, 88),
        "率": (ACTION_MENU_SOURCE, 176, 88),
    }
)
SCENARIO_49_ACTION_MENU_SOURCE = (
    "artifacts/scenario-49-battle-14-original-ui-boundaries-v1/"
    "turn4-skill-menu/frame.png"
)
ACTION_MENU_ORIGINAL_GLYPH_SOURCES: dict[
    str, tuple[str, int, int]
] = {}
for _text, _left, _top in (
    ("瞬身术", 8, 40),
    ("影分身术", 8, 56),
    ("忍者组合拳", 8, 72),
    ("十字手里剑", 8, 88),
    ("用查克拉的力量进行瞬间移动", 8, 136),
    ("攻击指令", 176, 120),
    ("返回", 216, 136),
):
    for _index, _character in enumerate(_text):
        ACTION_MENU_ORIGINAL_GLYPH_SOURCES.setdefault(
            _character,
            (
                SCENARIO_49_ACTION_MENU_SOURCE,
                _left + _index * UI_GLYPH_WIDTH,
                _top,
            ),
        )
for _text, _source, _left, _top in (
    (
        "漩涡鸣人",
        SCENARIO_49_ACTION_MENU_SOURCE,
        16,
        8,
    ),
    (
        "消耗查克拉",
        SCENARIO_49_ACTION_MENU_SOURCE,
        160,
        8,
    ),
    ("距离", SCENARIO_49_ACTION_MENU_SOURCE, 160, 40),
    ("范围", SCENARIO_49_ACTION_MENU_SOURCE, 160, 56),
    ("成功率", SCENARIO_49_ACTION_MENU_SOURCE, 160, 88),
    ("攻击力", ACTION_MENU_SOURCE, 160, 24),
):
    for _index, _character in enumerate(_text):
        ACTION_MENU_ORIGINAL_GLYPH_SOURCES.setdefault(
            _character,
            (
                _source,
                _left + _index * UI_GLYPH_WIDTH,
                _top,
            ),
        )
DUEL_TITLE_SOURCE = (
    "artifacts/original-s49-real-enemy-turn-20260730-188/"
    "frame-400.png"
)
ACTION_MENU_ORIGINAL_GLYPH_SOURCES.update(
    {
        "蜂": (DUEL_TITLE_SOURCE, 16, 8),
        "刺": (DUEL_TITLE_SOURCE, 24, 8),
    }
)
ACTION_MENU_ASCII_GLYPH_SOURCES = {
    "0": (ACTION_MENU_SOURCE, 208, 24),
    "1": (SCENARIO_49_ACTION_MENU_SOURCE, 224, 8),
    "3": (SCENARIO_49_ACTION_MENU_SOURCE, 192, 40),
    "8": (ACTION_MENU_SOURCE, 208, 88),
    "9": (ACTION_MENU_SOURCE, 200, 88),
    "X": (ACTION_MENU_SOURCE, 216, 24),
    "%": (SCENARIO_49_ACTION_MENU_SOURCE, 216, 88),
}
COMMAND_MENU_SOURCE = (
    "artifacts/scenario-49-battle-14-original-ui-boundaries-v1/"
    "turn4-command-menu/frame.png"
)
SCENARIO_41_ORIGINAL_GLYPH_SOURCES.update(
    {
        "术": (COMMAND_MENU_SOURCE, 16, 48),
        "・": (COMMAND_MENU_SOURCE, 24, 48),
        "忍": (COMMAND_MENU_SOURCE, 32, 48),
        "具": (COMMAND_MENU_SOURCE, 40, 48),
        "行": (COMMAND_MENU_SOURCE, 16, 64),
        "动": (COMMAND_MENU_SOURCE, 24, 64),
        "结": (COMMAND_MENU_SOURCE, 32, 64),
        "束": (COMMAND_MENU_SOURCE, 40, 64),
    }
)
ORIGINAL_UI_ASCII_GLYPH_SOURCES = {
    "0": (
        "artifacts/runtime-checkpoints/"
        "scenario-46-battle-start.ss9",
        216,
        136,
    ),
    "1": (
        "artifacts/runtime-checkpoints/"
        "scenario-46-battle-start.ss9",
        208,
        136,
    ),
    "2": (
        "artifacts/runtime-checkpoints/"
        "scenario-50-battle-15-entry.ss9",
        224,
        136,
    ),
    "3": (STATUS_HUD_SOURCE, 216, 136),
    "4": (
        "artifacts/runtime-checkpoints/"
        "scenario-50-battle-15-round3-frontline-assembled.ss9",
        224,
        136,
    ),
    "5": (STATUS_HUD_SOURCE, 224, 144),
    "6": (
        "artifacts/runtime-checkpoints/"
        "scenario-47-battle-13-turn4-player.ss9",
        224,
        136,
    ),
    "7": (
        "artifacts/runtime-checkpoints/"
        "scenario-50-battle-15-round8-objective28-frontblock.ss9",
        224,
        136,
    ),
    "8": (STATUS_HUD_SOURCE, 224, 136),
    "9": (
        "artifacts/runtime-checkpoints/"
        "scenario-46-battle-start.ss9",
        224,
        136,
    ),
}
DUEL_STATUS_SOURCE = (
    "artifacts/original-s49-real-enemy-turn-20260730-188/"
    "frame-400.png"
)
DUEL_STATUS_ASCII_GLYPH_SOURCES = {
    "0": (DUEL_STATUS_SOURCE, 192, 144),
    "1": (DUEL_STATUS_SOURCE, 88, 136),
    "2": (DUEL_STATUS_SOURCE, 184, 136),
    "3": (DUEL_STATUS_SOURCE, 96, 136),
    "4": ORIGINAL_UI_ASCII_GLYPH_SOURCES["4"],
    "5": (DUEL_STATUS_SOURCE, 192, 136),
    "6": ORIGINAL_UI_ASCII_GLYPH_SOURCES["6"],
    "7": ORIGINAL_UI_ASCII_GLYPH_SOURCES["7"],
    "8": (DUEL_STATUS_SOURCE, 64, 136),
    "9": ORIGINAL_UI_ASCII_GLYPH_SOURCES["9"],
    "/": (DUEL_STATUS_SOURCE, 80, 136),
}
SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS = frozenset(
    {
        "任",
        "务",
        "战",
        "斗",
        "回",
        "合",
        "分",
        "计",
        "能",
        "力",
        "查",
        "克",
        "拉",
        "消",
        "耗",
        "攻",
        "击",
        "距",
        "离",
        "范",
        "围",
        "成",
        "功",
        "率",
    }
)
ORIGINAL_UI_BACKGROUND_COLOR = (231, 247, 214)
ORIGINAL_UI_SHADOW_COLORS = {
    (173, 181, 156),
    (189, 173, 222),
    (231, 173, 140),
}
ORIGINAL_UI_MIDTONE_COLORS = {
    (115, 123, 107),
    (148, 99, 239),
}
ORIGINAL_UI_FOREGROUND_INDEX = 2
ORIGINAL_UI_SHADOW_INDEX = 5
ORIGINAL_UI_MIDTONE_INDEX = 15
PREPARATION_ORIGINAL_GLYPH_LINES = (
    (
        "保护木叶丸不被傀儡人偶攻击！",
        "artifacts/runtime-checkpoints/"
        "scenario-49-battle-14-postbattle-task-menu.ss9",
        64,
        8,
    ),
    (
        "保护木叶丸不受傀儡人偶攻击。",
        "artifacts/runtime-checkpoints/"
        "scenario-49-battle-14-postbattle-task-menu.ss9",
        8,
        40,
    ),
    (
        "木叶丸不会攻击，",
        "artifacts/runtime-checkpoints/"
        "scenario-49-battle-14-postbattle-task-menu.ss9",
        8,
        56,
    ),
    (
        "所以不要让他去接近危险品。",
        "artifacts/runtime-checkpoints/"
        "scenario-49-battle-14-postbattle-task-menu.ss9",
        8,
        72,
    ),
    (
        "保护木叶丸的同时",
        "artifacts/runtime-checkpoints/"
        "scenario-49-battle-14-postbattle-task-menu.ss9",
        8,
        104,
    ),
    (
        "把所有的傀儡人偶都赶走任务就算结束",
        "artifacts/runtime-checkpoints/"
        "scenario-49-battle-14-postbattle-task-menu.ss9",
        8,
        120,
    ),
    # 佐助 comes from the opening dialogue's speaker label.  Column projection
    # on that frame gives an exact 8-pixel grid: 佐 at x=24, 助 at x=32, both on
    # the y=104 cell row (ink y105-118).  Without this entry the two characters
    # fall through to the truetype fallback, which renders them blank on this
    # machine, and the dialogue label came out as 巨助.
    (
        "佐助",
        "artifacts/s49-fidelity-20261019-v1/"
        "walk-original-a24/step-13-A.png",
        24,
        104,
    ),
)
PREPARATION_ORIGINAL_GLYPH_SOURCES: dict[
    str, tuple[str, int, int]
] = {}
for (
    preparation_line,
    preparation_source,
    preparation_left,
    preparation_top,
) in PREPARATION_ORIGINAL_GLYPH_LINES:
    for preparation_index, preparation_character in enumerate(
        preparation_line
    ):
        PREPARATION_ORIGINAL_GLYPH_SOURCES.setdefault(
            preparation_character,
            (
                preparation_source,
                preparation_left +
                preparation_index * UI_GLYPH_WIDTH,
                preparation_top,
            ),
        )
PREPARATION_BEE_MISSION_SOURCE = (
    "artifacts/original-s49-task-menu-sequence-20260730-106/"
    "frame-00.png"
)
for (
    preparation_line,
    preparation_left,
    preparation_top,
) in (
    ("擅自到处跑", 32, 56),
    ("通过行动", 40, 72),
):
    for preparation_index, preparation_character in enumerate(
        preparation_line
    ):
        PREPARATION_ORIGINAL_GLYPH_SOURCES[
            preparation_character
        ] = (
            PREPARATION_BEE_MISSION_SOURCE,
            preparation_left +
            preparation_index * UI_GLYPH_WIDTH,
            preparation_top,
        )

TARGET_STATUS_SOURCE = (
    "artifacts/scenario-49-battle-14-original-ui-boundaries-v1/"
    "turn4-target-up-a-01/step-02-A.png"
)
TARGET_STATUS_GLYPH_SOURCES = {
    "蜜": (TARGET_STATUS_SOURCE, 8, 120),
    "蜂": (TARGET_STATUS_SOURCE, 16, 120),
    "待": (TARGET_STATUS_SOURCE, 104, 120),
    "机": (TARGET_STATUS_SOURCE, 112, 120),
    "体": (TARGET_STATUS_SOURCE, 136, 120),
    "力": (TARGET_STATUS_SOURCE, 144, 120),
    "查": (TARGET_STATUS_SOURCE, 136, 128),
    "克": (TARGET_STATUS_SOURCE, 144, 128),
    "拉": (TARGET_STATUS_SOURCE, 152, 128),
    "伤": (TARGET_STATUS_SOURCE, 8, 136),
    "害": (TARGET_STATUS_SOURCE, 16, 136),
    "成": (TARGET_STATUS_SOURCE, 80, 136),
    "功": (TARGET_STATUS_SOURCE, 88, 136),
    "率": (TARGET_STATUS_SOURCE, 96, 136),
    "攻": (TARGET_STATUS_SOURCE, 144, 136),
    "防": (TARGET_STATUS_SOURCE, 176, 136),
    "快": (TARGET_STATUS_SOURCE, 208, 136),
}
for target_status_character, target_status_source in (
    TARGET_STATUS_GLYPH_SOURCES.items()
):
    if target_status_character not in PREPARATION_BASE_GLYPH_SOURCES:
        PREPARATION_ORIGINAL_GLYPH_SOURCES[
            target_status_character
        ] = target_status_source
TARGET_STATUS_ASCII_GLYPH_SOURCES = {
    "0": (TARGET_STATUS_SOURCE, 224, 128),
    "1": (TARGET_STATUS_SOURCE, 56, 136),
    "2": (TARGET_STATUS_SOURCE, 216, 120),
    "4": (TARGET_STATUS_SOURCE, 160, 136),
    "5": (TARGET_STATUS_SOURCE, 224, 120),
    "6": (TARGET_STATUS_SOURCE, 64, 136),
    "9": (TARGET_STATUS_SOURCE, 112, 136),
    "%": (TARGET_STATUS_SOURCE, 128, 136),
}
TARGET_METRICS_ASCII_GLYPH_SOURCES = {
    **TARGET_STATUS_ASCII_GLYPH_SOURCES,
    "2": (TARGET_STATUS_SOURCE, 216, 136),
}


def _load_entries(
    path: Path,
    id_key: str,
    expected_count: int,
) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) != expected_count:
        raise ValueError(
            f"{path} must contain {expected_count} identity entries"
        )

    result: list[dict[str, object]] = []
    for expected_id, entry in enumerate(entries):
        if entry.get(id_key) != expected_id:
            raise ValueError(
                f"{path} identity IDs must be ordered at {expected_id}"
            )
        display_name = entry.get("display_name")
        if not isinstance(display_name, str) or not display_name:
            raise ValueError(f"{path} identity {expected_id} has no name")
        dialogue_name = entry.get("dialogue_name", display_name)
        if not isinstance(dialogue_name, str) or not dialogue_name:
            raise ValueError(
                f"{path} identity {expected_id} has no dialogue name"
            )
        dialogue_label_frame = entry.get("dialogue_label_frame", -1)
        if (
            not isinstance(dialogue_label_frame, int)
            or not -1 <= dialogue_label_frame <= 127
        ):
            raise ValueError(
                f"{path} identity {expected_id} has invalid dialogue label"
            )
        confidence = entry.get("confidence")
        if confidence not in VALID_CONFIDENCES:
            raise ValueError(
                f"{path} identity {expected_id} has invalid confidence"
            )
        raw_hex = entry.get("name_raw_hex")
        if not isinstance(raw_hex, str) or not raw_hex:
            raise ValueError(
                f"{path} identity {expected_id} has no raw provenance"
            )
        try:
            raw_name = bytes.fromhex(raw_hex)
        except ValueError as error:
            raise ValueError(
                f"{path} identity {expected_id} has invalid raw provenance"
            ) from error
        if len(raw_name) % 2:
            raise ValueError(
                f"{path} identity {expected_id} raw provenance is truncated"
            )
        result.append(
            {
                "id": expected_id,
                "display_name": display_name,
                "dialogue_name": dialogue_name,
                "dialogue_label_frame": dialogue_label_frame,
                "exact": confidence == "runtime_visual_exact",
            }
        )
    return result


def load_identity_content(root: Path | str) -> dict[str, object]:
    """Load and validate battle unit, active-action, and ninja-tool identities."""

    root = Path(root)
    units = _load_entries(
        root / "sequel/content/units/unit-identities.json",
        "unit_id",
        UNIT_COUNT,
    )
    actions = _load_entries(
        root / "sequel/content/battle-config/action-identities.json",
        "action_id",
        ACTION_COUNT,
    )
    tools_path = (
        root
        / "sequel/content/battle-config/ninja-tool-identities.json"
    )
    tools_payload = json.loads(tools_path.read_text(encoding="utf-8"))
    tool_entries = tools_payload.get("entries")
    if (
        not isinstance(tool_entries, list)
        or len(tool_entries) != NINJA_TOOL_COUNT
    ):
        raise ValueError(
            f"{tools_path} must contain {NINJA_TOOL_COUNT} identity entries"
        )
    catalog_path = root / "notes/battle-content-catalog-20260723.json"
    catalog_payload = json.loads(
        catalog_path.read_text(encoding="utf-8")
    )
    catalog_tools = catalog_payload.get("ninja_tools")
    if (
        not isinstance(catalog_tools, list)
        or len(catalog_tools) != NINJA_TOOL_COUNT
    ):
        raise ValueError(
            f"{catalog_path} must contain {NINJA_TOOL_COUNT} ninja tools"
        )
    tools: list[dict[str, object]] = []
    for expected_id, (entry, catalog_entry) in enumerate(
        zip(tool_entries, catalog_tools, strict=True)
    ):
        if (
            entry.get("tool_id") != expected_id
            or catalog_entry.get("action_id") != expected_id
        ):
            raise ValueError(
                "ninja-tool identity IDs must be ordered at "
                f"{expected_id}"
            )
        display_name = entry.get("display_name")
        confidence = entry.get("confidence")
        if not isinstance(display_name, str) or not display_name:
            raise ValueError(
                f"ninja-tool identity {expected_id} has no name"
            )
        if confidence not in VALID_CONFIDENCES:
            raise ValueError(
                f"ninja-tool identity {expected_id} has invalid confidence"
            )
        name_record = catalog_entry.get("name")
        raw_hex = (
            name_record.get("raw_hex")
            if isinstance(name_record, dict)
            else None
        )
        if not isinstance(raw_hex, str) or not raw_hex:
            raise ValueError(
                f"ninja-tool identity {expected_id} has no ROM provenance"
            )
        tools.append(
            {
                "id": expected_id,
                "display_name": display_name,
                "exact": confidence == "runtime_visual_exact",
            }
        )

    utf8_characters: list[str] = []
    seen: set[str] = set()
    for entry in units + actions + tools:
        for character in (
            str(entry["display_name"]) +
            str(entry.get("dialogue_name", ""))
        ):
            if (
                not 32 <= ord(character) <= 126
                and character not in seen
            ):
                seen.add(character)
                utf8_characters.append(character)
    for character in SCENARIO_41_UI_TEXT:
        if (
            not 32 <= ord(character) <= 126
            and character not in seen
        ):
            seen.add(character)
            utf8_characters.append(character)

    return {
        "units": units,
        "actions": actions,
        "tools": tools,
        "utf8_characters": utf8_characters,
    }


def _cpp_identity_rows(entries: list[dict[str, object]]) -> str:
    rows = []
    for entry in entries:
        name = str(entry["display_name"]).replace("\\", "\\\\").replace(
            '"', '\\"'
        )
        exact = "true" if entry["exact"] else "false"
        rows.append(
            f'    battle_identity_record{{ "{name}", {exact} }},'
        )
    return "\n".join(rows)


def _cpp_dialogue_name_rows(entries: list[dict[str, object]]) -> str:
    rows = []
    for entry in entries:
        name = str(entry["dialogue_name"]).replace("\\", "\\\\").replace(
            '"', '\\"'
        )
        rows.append(f'    "{name}",')
    return "\n".join(rows)


def _cpp_dialogue_label_frame_rows(
    entries: list[dict[str, object]],
) -> str:
    return "\n".join(
        f'    {int(entry["dialogue_label_frame"])},'
        for entry in entries
    )


def generate_content_header(root: Path | str) -> str:
    content = load_identity_content(root)
    unit_rows = _cpp_identity_rows(content["units"])
    dialogue_name_rows = _cpp_dialogue_name_rows(content["units"])
    dialogue_label_frame_rows = _cpp_dialogue_label_frame_rows(
        content["units"]
    )
    action_rows = _cpp_identity_rows(content["actions"])
    tool_rows = _cpp_identity_rows(content["tools"])
    return f"""// Generated by tools/generate_butano_battle_identity_content.py. Do not edit.
{PROVENANCE}
#ifndef KONOHA_GENERATED_BATTLE_IDENTITY_CONTENT_H
#define KONOHA_GENERATED_BATTLE_IDENTITY_CONTENT_H

#include <array>
#include <cstddef>
#include <cstdint>

namespace konoha
{{

struct battle_identity_record
{{
    const char* display_name = "";
    bool exact = false;
}};

inline constexpr std::array<battle_identity_record, {UNIT_COUNT}>
        battle_unit_identities = {{{{
{unit_rows}
}}}};

inline constexpr std::array<const char*, {UNIT_COUNT}>
        battle_unit_dialogue_names = {{{{
{dialogue_name_rows}
}}}};

inline constexpr std::array<std::int8_t, {UNIT_COUNT}>
        battle_unit_dialogue_label_frames = {{{{
{dialogue_label_frame_rows}
}}}};

inline constexpr std::array<battle_identity_record, {ACTION_COUNT}>
        battle_active_action_identities = {{{{
{action_rows}
}}}};

inline constexpr std::array<battle_identity_record, {NINJA_TOOL_COUNT}>
        battle_ninja_tool_identities = {{{{
{tool_rows}
}}}};

[[nodiscard]] constexpr const battle_identity_record*
battle_unit_identity(std::size_t character_id)
{{
    return character_id < battle_unit_identities.size() ?
            &battle_unit_identities[character_id] : nullptr;
}}

[[nodiscard]] constexpr const char*
battle_unit_dialogue_name(std::size_t character_id)
{{
    return character_id < battle_unit_dialogue_names.size() ?
            battle_unit_dialogue_names[character_id] : "";
}}

[[nodiscard]] constexpr int
battle_unit_dialogue_label_graphics_index(
        std::size_t character_id)
{{
    return character_id <
                    battle_unit_dialogue_label_frames.size() ?
            battle_unit_dialogue_label_frames[character_id] : -1;
}}

[[nodiscard]] constexpr const battle_identity_record*
battle_active_action_identity(std::size_t action_id)
{{
    return action_id < battle_active_action_identities.size() ?
            &battle_active_action_identities[action_id] : nullptr;
}}

[[nodiscard]] constexpr const battle_identity_record*
battle_ninja_tool_identity(std::size_t tool_id)
{{
    return tool_id < battle_ninja_tool_identities.size() ?
            &battle_ninja_tool_identities[tool_id] : nullptr;
}}

}}

#endif
"""


def _load_ascii_widths(root: Path) -> list[int]:
    source = (
        root
        / "third_party/butano/common/include"
        / "common_variable_16x16_sprite_font.h"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"variable_16x16_sprite_font_character_widths\[\]\s*=\s*\{"
        r"(?P<body>.*?)\n\};",
        source,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("unable to parse common 16x16 font widths")
    width_terms = re.findall(
        r"^\s*(\d+)(?:\s*\*\s*(\d+))?,\s*//",
        match.group("body"),
        flags=re.MULTILINE,
    )
    widths = [
        int(value) * (int(multiplier) if multiplier else 1)
        for value, multiplier in width_terms
    ]
    if len(widths) < ASCII_WIDTH_COUNT:
        raise ValueError("common 16x16 font has incomplete ASCII widths")
    return widths[:ASCII_WIDTH_COUNT]


def _load_ui_ascii_widths(root: Path) -> list[int]:
    source = (
        root
        / "third_party/butano/common/include"
        / "common_variable_8x8_sprite_font.h"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"variable_8x8_sprite_font_character_widths\[\]\s*=\s*\{"
        r"(?P<body>.*?)\n\};",
        source,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("unable to parse common 8x8 font widths")
    width_terms = re.findall(
        r"^\s*(\d+)(?:\s*\*\s*(\d+))?,\s*//",
        match.group("body"),
        flags=re.MULTILINE,
    )
    widths = [
        int(value) * (int(multiplier) if multiplier else 1)
        for value, multiplier in width_terms
    ]
    if len(widths) < ASCII_WIDTH_COUNT:
        raise ValueError("common 8x8 font has incomplete ASCII widths")
    widths = widths[:ASCII_WIDTH_COUNT]
    for character in ORIGINAL_UI_ASCII_GLYPH_SOURCES:
        widths[ord(character) - 32] = UI_GLYPH_WIDTH
    return widths


def _format_cpp_values(values: list[str], per_line: int = 8) -> str:
    return "\n".join(
        "    " + ", ".join(values[index : index + per_line]) + ","
        for index in range(0, len(values), per_line)
    )


def generate_font_header(root: Path | str) -> str:
    root = Path(root)
    content = load_identity_content(root)
    characters = content["utf8_characters"]
    character_values = [
        '"' + character.replace("\\", "\\\\").replace('"', '\\"') + '"'
        for character in characters
    ]
    widths = _load_ascii_widths(root)
    widths.extend(
        8 if character == "\u3000" else 15
        for character in characters
    )
    character_rows = _format_cpp_values(character_values)
    width_rows = _format_cpp_values([str(width) for width in widths], 16)
    return f"""// Generated by tools/generate_butano_battle_identity_content.py. Do not edit.
{FONT_PROVENANCE}
#ifndef KONOHA_BATTLE_IDENTITY_SPRITE_FONT_H
#define KONOHA_BATTLE_IDENTITY_SPRITE_FONT_H

#include "bn_span.h"
#include "bn_sprite_font.h"
#include "bn_sprite_items_battle_identity_font.h"
#include "bn_utf8_characters_map.h"

namespace konoha
{{

constexpr bn::utf8_character battle_identity_font_utf8_characters[] = {{
{character_rows}
}};

constexpr int8_t battle_identity_font_character_widths[] = {{
{width_rows}
}};

constexpr bn::span<const bn::utf8_character>
        battle_identity_font_utf8_characters_span(
                battle_identity_font_utf8_characters);

constexpr auto battle_identity_font_utf8_characters_map =
        bn::utf8_characters_map<
                battle_identity_font_utf8_characters_span>();

constexpr bn::sprite_font battle_identity_sprite_font(
        bn::sprite_items::battle_identity_font,
        battle_identity_font_utf8_characters_map.reference(),
        battle_identity_font_character_widths);

}}

#endif
"""


def generate_ui_font_header(root: Path | str) -> str:
    root = Path(root)
    content = load_identity_content(root)
    characters = content["utf8_characters"]
    character_values = [
        '"' + character.replace("\\", "\\\\").replace('"', '\\"') + '"'
        for character in characters
    ]
    widths = _load_ui_ascii_widths(root)
    widths.extend(
        4 if character == "\u3000" else 8
        for character in characters
    )
    character_rows = _format_cpp_values(character_values)
    width_rows = _format_cpp_values([str(width) for width in widths], 16)
    return f"""// Generated by tools/generate_butano_battle_identity_content.py. Do not edit.
{FONT_PROVENANCE}
#ifndef KONOHA_BATTLE_UI_SPRITE_FONT_H
#define KONOHA_BATTLE_UI_SPRITE_FONT_H

#include "bn_span.h"
#include "bn_sprite_font.h"
#include "bn_sprite_items_battle_ui_font.h"
#include "bn_utf8_characters_map.h"

namespace konoha
{{

constexpr bn::utf8_character battle_ui_font_utf8_characters[] = {{
{character_rows}
}};

constexpr int8_t battle_ui_font_character_widths[] = {{
{width_rows}
}};

constexpr bn::span<const bn::utf8_character>
        battle_ui_font_utf8_characters_span(
                battle_ui_font_utf8_characters);

constexpr auto battle_ui_font_utf8_characters_map =
        bn::utf8_characters_map<
                battle_ui_font_utf8_characters_span>();

constexpr bn::sprite_font battle_ui_sprite_font(
        bn::sprite_items::battle_ui_font,
        battle_ui_font_utf8_characters_map.reference(),
        battle_ui_font_character_widths);

}}

#endif
"""


def generate_preparation_font_header(root: Path | str) -> str:
    root = Path(root)
    content = load_identity_content(root)
    characters = content["utf8_characters"]
    character_values = [
        '"' + character.replace("\\", "\\\\").replace('"', '\\"') + '"'
        for character in characters
    ]
    widths = _load_ui_ascii_widths(root)
    widths.extend(
        4 if character == "\u3000" else 8
        for character in characters
    )
    character_rows = _format_cpp_values(character_values)
    width_rows = _format_cpp_values([str(width) for width in widths], 16)
    return f"""// Generated by tools/generate_butano_battle_identity_content.py. Do not edit.
{FONT_PROVENANCE}
#ifndef KONOHA_BATTLE_PREPARATION_SPRITE_FONT_H
#define KONOHA_BATTLE_PREPARATION_SPRITE_FONT_H

#include "bn_span.h"
#include "bn_sprite_font.h"
#include "bn_sprite_items_battle_preparation_font.h"
#include "bn_utf8_characters_map.h"

namespace konoha
{{

constexpr bn::utf8_character battle_preparation_font_utf8_characters[] = {{
{character_rows}
}};

constexpr int8_t battle_preparation_font_character_widths[] = {{
{width_rows}
}};

constexpr bn::span<const bn::utf8_character>
        battle_preparation_font_utf8_characters_span(
                battle_preparation_font_utf8_characters);

constexpr auto battle_preparation_font_utf8_characters_map =
        bn::utf8_characters_map<
                battle_preparation_font_utf8_characters_span>();

constexpr bn::sprite_font battle_preparation_sprite_font(
        bn::sprite_items::battle_preparation_font,
        battle_preparation_font_utf8_characters_map.reference(),
        battle_preparation_font_character_widths);

}}

#endif
"""


def generate_target_status_font_header(root: Path | str) -> str:
    return (
        generate_preparation_font_header(root)
        .replace(
            "BATTLE_PREPARATION_SPRITE_FONT",
            "BATTLE_TARGET_STATUS_SPRITE_FONT",
        )
        .replace("battle_preparation", "battle_target_status")
    )


def generate_result_font_header(root: Path | str) -> str:
    return (
        generate_preparation_font_header(root)
        .replace(
            "BATTLE_PREPARATION_SPRITE_FONT",
            "BATTLE_RESULT_SPRITE_FONT",
        )
        .replace("battle_preparation", "battle_result")
    )


def generate_result_compact_font_header(root: Path | str) -> str:
    return (
        generate_preparation_font_header(root)
        .replace(
            "BATTLE_PREPARATION_SPRITE_FONT",
            "BATTLE_RESULT_COMPACT_SPRITE_FONT",
        )
        .replace(
            "battle_preparation",
            "battle_result_compact",
        )
    )


def generate_target_metrics_font_header(root: Path | str) -> str:
    return (
        generate_preparation_font_header(root)
        .replace(
            "BATTLE_PREPARATION_SPRITE_FONT",
            "BATTLE_TARGET_METRICS_SPRITE_FONT",
        )
        .replace("battle_preparation", "battle_target_metrics")
    )


def generate_action_menu_font_header(root: Path | str) -> str:
    return (
        generate_preparation_font_header(root)
        .replace(
            "BATTLE_PREPARATION_SPRITE_FONT",
            "BATTLE_ACTION_MENU_SPRITE_FONT",
        )
        .replace("battle_preparation", "battle_action_menu")
    )


def generate_duel_status_font_header(root: Path | str) -> str:
    del root
    return f"""// Generated by tools/generate_butano_battle_identity_content.py. Do not edit.
{FONT_PROVENANCE}
#ifndef KONOHA_BATTLE_DUEL_STATUS_SPRITE_FONT_H
#define KONOHA_BATTLE_DUEL_STATUS_SPRITE_FONT_H

#include "bn_sprite_font.h"
#include "bn_sprite_items_battle_duel_status_font.h"

namespace konoha
{{

constexpr bn::sprite_font battle_duel_status_sprite_font(
        bn::sprite_items::battle_duel_status_font);

}}

#endif
"""


def _render_glyph(
    character: str,
    font: ImageFont.FreeTypeFont,
    glyph_size: int = GLYPH_SIZE,
) -> Image.Image:
    glyph = Image.new("L", (glyph_size, glyph_size), 0)
    draw = ImageDraw.Draw(glyph)
    bounds = draw.textbbox((0, 0), character, font=font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    position = (
        (glyph_size - width) // 2 - bounds[0],
        (glyph_size - height) // 2 - bounds[1],
    )
    draw.text(position, character, font=font, fill=255)

    indexed = Image.new("P", glyph.size, 0)
    indexed.putdata(
        [
            FOREGROUND_INDEX if pixel >= 128 else 0
            for pixel in glyph.get_flattened_data()
        ]
    )
    return indexed


def generate_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    root = Path(root)
    font_path = Path(font_path)
    if not font_path.is_file():
        raise ValueError(f"Chinese font is missing: {font_path}")
    content = load_identity_content(root)
    characters = content["utf8_characters"]

    common_path = (
        root
        / "third_party/butano/common/graphics"
        / "common_variable_16x16_font.bmp"
    )
    with Image.open(common_path) as source:
        if source.mode != "P" or source.size[0] != GLYPH_SIZE:
            raise ValueError("unexpected common 16x16 font format")
        ascii_font = source.crop(
            (0, 0, GLYPH_SIZE, ASCII_GLYPH_COUNT * GLYPH_SIZE)
        )
        palette = source.getpalette()

    result = Image.new(
        "P",
        (
            GLYPH_SIZE,
            (ASCII_GLYPH_COUNT + len(characters)) * GLYPH_SIZE,
        ),
        0,
    )
    result.putpalette(palette)
    result.paste(ascii_font, (0, 0))

    font = ImageFont.truetype(
        str(font_path),
        FONT_SIZE,
        index=FONT_FACE_INDEX,
    )
    for index, character in enumerate(characters):
        glyph = _render_glyph(character, font)
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (0, (ASCII_GLYPH_COUNT + index) * GLYPH_SIZE),
        )
    return result


def generate_ui_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    root = Path(root)
    font_path = Path(font_path)
    if not font_path.is_file():
        raise ValueError(f"Chinese font is missing: {font_path}")
    content = load_identity_content(root)
    characters = content["utf8_characters"]
    common_path = (
        root
        / "third_party/butano/common/graphics"
        / "common_variable_8x16_font.bmp"
    )
    with Image.open(common_path) as source:
        if (
            source.mode != "P"
            or source.size[0] != UI_GLYPH_WIDTH
        ):
            raise ValueError("unexpected common 8x16 font format")
        ascii_font = source.crop(
            (
                0,
                0,
                UI_GLYPH_WIDTH,
                ASCII_GLYPH_COUNT * UI_GLYPH_HEIGHT,
            )
        )
        palette = source.getpalette()

    result = Image.new(
        "P",
        (
            UI_GLYPH_WIDTH,
            (ASCII_GLYPH_COUNT + len(characters)) *
            UI_GLYPH_HEIGHT,
        ),
        0,
    )
    result.putpalette(palette)
    result.paste(ascii_font, (0, 0))
    for character, (
        source_path,
        left,
        top,
    ) in ORIGINAL_UI_ASCII_GLYPH_SOURCES.items():
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_WIDTH,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putdata(
            [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]
            + [0]
            * (
                UI_GLYPH_WIDTH
                * (UI_GLYPH_HEIGHT - UI_GLYPH_WIDTH)
            )
        )
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (
                0,
                (ord(character) - ord("!"))
                * UI_GLYPH_HEIGHT,
            ),
        )
    font = ImageFont.truetype(
        str(font_path),
        UI_FALLBACK_FONT_SIZE,
        index=FONT_FACE_INDEX,
    )
    for index, character in enumerate(characters):
        source_spec = (
            SCENARIO_41_ORIGINAL_GLYPH_SOURCES.get(character)
        )
        if source_spec:
            source_path, left, top = source_spec
            source_height = (
                UI_GLYPH_WIDTH
                if character in
                SCENARIO_41_ORIGINAL_COMPACT_UI_GLYPHS
                else UI_GLYPH_HEIGHT
            )
            with Image.open(root / source_path) as source:
                colors = source.convert("RGB").crop(
                    (
                        left,
                        top,
                        left + UI_GLYPH_WIDTH,
                        top + source_height,
                    )
                )
            source_pixels = list(colors.get_flattened_data())
            source_pixels.extend(
                [ORIGINAL_UI_BACKGROUND_COLOR]
                * (
                    UI_GLYPH_WIDTH
                    * (UI_GLYPH_HEIGHT - source_height)
                )
            )
            glyph = Image.new(
                "P",
                (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
                0,
            )
            glyph.putdata(
                [
                    0
                    if color ==
                    ORIGINAL_UI_BACKGROUND_COLOR
                    else ORIGINAL_UI_SHADOW_INDEX
                    if color in ORIGINAL_UI_SHADOW_COLORS
                    else ORIGINAL_UI_MIDTONE_INDEX
                    if color in ORIGINAL_UI_MIDTONE_COLORS
                    else ORIGINAL_UI_FOREGROUND_INDEX
                    for color in source_pixels
                ]
            )
        else:
            compact = _render_glyph(
                character, font, UI_GLYPH_WIDTH)
            glyph = Image.new(
                "P",
                (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
                0,
            )
            glyph.paste(compact, (0, 0))
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (
                0,
                (ASCII_GLYPH_COUNT + index) *
                UI_GLYPH_HEIGHT,
            ),
        )
    return result


def generate_preparation_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    root = Path(root)
    font_path = Path(font_path)
    result = generate_ui_font_bitmap(root, font_path)
    palette = result.getpalette()
    characters = load_identity_content(root)["utf8_characters"]
    for character, (
        source_path,
        left,
        top,
    ) in TARGET_STATUS_ASCII_GLYPH_SOURCES.items():
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_HEIGHT,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putdata(
            [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]
        )
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (
                0,
                (ord(character) - ord("!"))
                * UI_GLYPH_HEIGHT,
            ),
        )
    font = ImageFont.truetype(
        str(font_path),
        FONT_SIZE,
        index=FONT_FACE_INDEX,
    )
    for index, character in enumerate(characters):
        source_spec = PREPARATION_ORIGINAL_GLYPH_SOURCES.get(
            character
        )
        if source_spec:
            source_path, left, top = source_spec
            with Image.open(root / source_path) as source:
                colors = source.convert("RGB").crop(
                    (
                        left,
                        top,
                        left + UI_GLYPH_WIDTH,
                        top + UI_GLYPH_HEIGHT,
                    )
                )
            glyph = Image.new(
                "P",
                (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
                0,
            )
            glyph.putdata(
                [
                    0
                    if color == ORIGINAL_UI_BACKGROUND_COLOR
                    else ORIGINAL_UI_MIDTONE_INDEX
                    if color in ORIGINAL_UI_MIDTONE_COLORS
                    else ORIGINAL_UI_SHADOW_INDEX
                    if color in ORIGINAL_UI_SHADOW_COLORS
                    else ORIGINAL_UI_FOREGROUND_INDEX
                    for color in colors.get_flattened_data()
                ]
            )
        elif character in PREPARATION_BASE_GLYPH_SOURCES:
            source_path, left, top = (
                PREPARATION_BASE_GLYPH_SOURCES[character]
            )
            with Image.open(root / source_path) as source:
                colors = source.convert("RGB").crop(
                    (
                        left,
                        top,
                        left + UI_GLYPH_WIDTH,
                        top + UI_GLYPH_HEIGHT,
                    )
                )
            glyph = Image.new(
                "P",
                (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
                0,
            )
            glyph.putdata(
                [
                    0
                    if color == ORIGINAL_UI_BACKGROUND_COLOR
                    else ORIGINAL_UI_MIDTONE_INDEX
                    if color in ORIGINAL_UI_MIDTONE_COLORS
                    else ORIGINAL_UI_SHADOW_INDEX
                    if color in ORIGINAL_UI_SHADOW_COLORS
                    else ORIGINAL_UI_FOREGROUND_INDEX
                    for color in colors.get_flattened_data()
                ]
            )
        else:
            glyph = _render_glyph(
                character, font, GLYPH_SIZE)
            glyph = glyph.resize(
                (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
                Image.Resampling.NEAREST,
            )
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (
                0,
                (ASCII_GLYPH_COUNT + index) *
                UI_GLYPH_HEIGHT,
            ),
        )
    return result


def _result_source_glyph(
    root: Path,
    source_spec: tuple[str, int, int],
) -> Image.Image:
    source_path, left, top = source_spec
    with Image.open(root / source_path) as source:
        colors = source.convert("RGB").crop(
            (
                left,
                top,
                left + UI_GLYPH_WIDTH,
                top + UI_GLYPH_HEIGHT,
            )
        )
    glyph = Image.new(
        "P", (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT), 0)
    glyph.putdata(
        [
            0
            if color == ORIGINAL_UI_BACKGROUND_COLOR
            else ORIGINAL_UI_SHADOW_INDEX
            if color in ORIGINAL_UI_SHADOW_COLORS
            else ORIGINAL_UI_MIDTONE_INDEX
            if color in ORIGINAL_UI_MIDTONE_COLORS
            else ORIGINAL_UI_FOREGROUND_INDEX
            for color in colors.get_flattened_data()
        ]
    )
    return glyph


def generate_result_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    """Generate the original full-height result headings and totals."""

    root = Path(root)
    result = generate_preparation_font_bitmap(root, font_path)
    palette = result.getpalette()
    characters = load_identity_content(root)["utf8_characters"]
    for character, source_spec in (
        RESULT_LARGE_ASCII_GLYPH_SOURCES.items()
    ):
        glyph = _result_source_glyph(root, source_spec)
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (
                0,
                (ord(character) - ord("!")) *
                UI_GLYPH_HEIGHT,
            ),
        )
    for character, source_spec in RESULT_LARGE_GLYPH_SOURCES.items():
        glyph = _result_source_glyph(root, source_spec)
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (
                0,
                (
                    ASCII_GLYPH_COUNT +
                    characters.index(character)
                ) * UI_GLYPH_HEIGHT,
            ),
        )
    return result


def generate_result_compact_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    """Generate the original eight-pixel-high result score digits."""

    root = Path(root)
    result = generate_preparation_font_bitmap(root, font_path)
    palette = result.getpalette()
    for character, (source_path, left, top) in (
        RESULT_COMPACT_ASCII_GLYPH_SOURCES.items()
    ):
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_WIDTH,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putpalette(palette)
        glyph.putdata(
            [
                0
                if y >= UI_GLYPH_WIDTH or
                colors.getpixel((x, y)) ==
                ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_SHADOW_INDEX
                if colors.getpixel((x, y)) in
                ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_MIDTONE_INDEX
                if colors.getpixel((x, y)) in
                ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for y in range(UI_GLYPH_HEIGHT)
                for x in range(UI_GLYPH_WIDTH)
            ]
        )
        result.paste(
            glyph,
            (
                0,
                (ord(character) - ord("!")) *
                UI_GLYPH_HEIGHT,
            ),
        )
    return result


def generate_action_menu_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    root = Path(root)
    result = generate_preparation_font_bitmap(root, font_path)
    palette = result.getpalette()
    characters = load_identity_content(root)["utf8_characters"]
    for character, (
        source_path,
        left,
        top,
    ) in ACTION_MENU_ASCII_GLYPH_SOURCES.items():
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_HEIGHT,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putdata(
            [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]
        )
        glyph.putpalette(palette)
        glyph_index = ord(character) - ord("!")
        result.paste(
            glyph,
            (0, glyph_index * UI_GLYPH_HEIGHT),
        )
    for character, (
        source_path,
        left,
        top,
    ) in ACTION_MENU_ORIGINAL_GLYPH_SOURCES.items():
        if character not in characters:
            continue
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_HEIGHT,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putdata(
            [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]
        )
        glyph.putpalette(palette)
        result.paste(
            glyph,
            (
                0,
                (
                    ASCII_GLYPH_COUNT
                    + characters.index(character)
                )
                * UI_GLYPH_HEIGHT,
            ),
        )
    return result


def generate_target_status_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    root = Path(root)
    result = generate_preparation_font_bitmap(root, font_path)
    palette = result.getpalette()
    characters = load_identity_content(root)["utf8_characters"]
    glyph_sources = {
        **TARGET_STATUS_ASCII_GLYPH_SOURCES,
        **TARGET_STATUS_GLYPH_SOURCES,
    }
    for character, (source_path, left, top) in glyph_sources.items():
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_HEIGHT,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putdata(
            [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_SHADOW_INDEX
                if color == (231, 173, 140)
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]
        )
        glyph.putpalette(palette)
        if character in TARGET_STATUS_ASCII_GLYPH_SOURCES:
            glyph_index = ord(character) - ord("!")
        else:
            glyph_index = ASCII_GLYPH_COUNT + characters.index(
                character
            )
        result.paste(
            glyph,
            (0, glyph_index * UI_GLYPH_HEIGHT),
        )
    return result


def generate_target_metrics_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    root = Path(root)
    result = generate_target_status_font_bitmap(root, font_path)
    palette = result.getpalette()
    for character, (
        source_path,
        left,
        top,
    ) in TARGET_METRICS_ASCII_GLYPH_SOURCES.items():
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_HEIGHT,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putdata(
            [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]
        )
        glyph.putpalette(palette)
        glyph_index = ord(character) - ord("!")
        result.paste(
            glyph,
            (0, glyph_index * UI_GLYPH_HEIGHT),
        )
    return result


def generate_duel_status_font_bitmap(
    root: Path | str,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> Image.Image:
    root = Path(root)
    result = generate_ui_font_bitmap(root, font_path).crop(
        (
            0,
            0,
            UI_GLYPH_WIDTH,
            ASCII_GLYPH_COUNT * UI_GLYPH_HEIGHT,
        )
    )
    palette = result.getpalette()
    for character, (
        source_path,
        left,
        top,
    ) in DUEL_STATUS_ASCII_GLYPH_SOURCES.items():
        with Image.open(root / source_path) as source:
            colors = source.convert("RGB").crop(
                (
                    left,
                    top,
                    left + UI_GLYPH_WIDTH,
                    top + UI_GLYPH_WIDTH,
                )
            )
        glyph = Image.new(
            "P",
            (UI_GLYPH_WIDTH, UI_GLYPH_HEIGHT),
            0,
        )
        glyph.putdata(
            [
                0
                if color == ORIGINAL_UI_BACKGROUND_COLOR
                else ORIGINAL_UI_MIDTONE_INDEX
                if color in ORIGINAL_UI_MIDTONE_COLORS
                else ORIGINAL_UI_SHADOW_INDEX
                if color in ORIGINAL_UI_SHADOW_COLORS
                else ORIGINAL_UI_FOREGROUND_INDEX
                for color in colors.get_flattened_data()
            ]
            + [0] * (UI_GLYPH_WIDTH * UI_GLYPH_WIDTH)
        )
        glyph.putpalette(palette)
        glyph_index = ord(character) - ord("!")
        result.paste(
            glyph,
            (0, glyph_index * UI_GLYPH_HEIGHT),
        )
    return result


def generate_outputs(
    root: Path | str,
    output_directory: Path | str,
    *,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> dict[str, Path]:
    root = Path(root)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "content_header": (
            output_directory / "generated_battle_identity_content.h"
        ),
        "font_header": (
            output_directory / "battle_identity_sprite_font.h"
        ),
        "font_bitmap": output_directory / "battle_identity_font.bmp",
        "font_metadata": output_directory / "battle_identity_font.json",
        "ui_font_header": (
            output_directory / "battle_ui_sprite_font.h"
        ),
        "ui_font_bitmap": output_directory / "battle_ui_font.bmp",
        "ui_font_metadata": output_directory / "battle_ui_font.json",
        "result_font_header": (
            output_directory / "battle_result_sprite_font.h"
        ),
        "result_font_bitmap": (
            output_directory / "battle_result_font.bmp"
        ),
        "result_font_metadata": (
            output_directory / "battle_result_font.json"
        ),
        "result_compact_font_header": (
            output_directory
            / "battle_result_compact_sprite_font.h"
        ),
        "result_compact_font_bitmap": (
            output_directory / "battle_result_compact_font.bmp"
        ),
        "result_compact_font_metadata": (
            output_directory / "battle_result_compact_font.json"
        ),
        "action_menu_font_header": (
            output_directory / "battle_action_menu_sprite_font.h"
        ),
        "action_menu_font_bitmap": (
            output_directory / "battle_action_menu_font.bmp"
        ),
        "action_menu_font_metadata": (
            output_directory / "battle_action_menu_font.json"
        ),
        "preparation_font_header": (
            output_directory / "battle_preparation_sprite_font.h"
        ),
        "preparation_font_bitmap": (
            output_directory / "battle_preparation_font.bmp"
        ),
        "preparation_font_metadata": (
            output_directory / "battle_preparation_font.json"
        ),
        "target_status_font_header": (
            output_directory / "battle_target_status_sprite_font.h"
        ),
        "target_status_font_bitmap": (
            output_directory / "battle_target_status_font.bmp"
        ),
        "target_status_font_metadata": (
            output_directory / "battle_target_status_font.json"
        ),
        "target_metrics_font_header": (
            output_directory / "battle_target_metrics_sprite_font.h"
        ),
        "target_metrics_font_bitmap": (
            output_directory / "battle_target_metrics_font.bmp"
        ),
        "target_metrics_font_metadata": (
            output_directory / "battle_target_metrics_font.json"
        ),
        "duel_status_font_header": (
            output_directory / "battle_duel_status_sprite_font.h"
        ),
        "duel_status_font_bitmap": (
            output_directory / "battle_duel_status_font.bmp"
        ),
        "duel_status_font_metadata": (
            output_directory / "battle_duel_status_font.json"
        ),
    }
    outputs["content_header"].write_text(
        generate_content_header(root),
        encoding="utf-8",
    )
    outputs["font_header"].write_text(
        generate_font_header(root),
        encoding="utf-8",
    )
    outputs["ui_font_header"].write_text(
        generate_ui_font_header(root),
        encoding="utf-8",
    )
    outputs["result_font_header"].write_text(
        generate_result_font_header(root),
        encoding="utf-8",
    )
    outputs["result_compact_font_header"].write_text(
        generate_result_compact_font_header(root),
        encoding="utf-8",
    )
    outputs["action_menu_font_header"].write_text(
        generate_action_menu_font_header(root),
        encoding="utf-8",
    )
    outputs["preparation_font_header"].write_text(
        generate_preparation_font_header(root),
        encoding="utf-8",
    )
    outputs["target_status_font_header"].write_text(
        generate_target_status_font_header(root),
        encoding="utf-8",
    )
    outputs["target_metrics_font_header"].write_text(
        generate_target_metrics_font_header(root),
        encoding="utf-8",
    )
    outputs["duel_status_font_header"].write_text(
        generate_duel_status_font_header(root),
        encoding="utf-8",
    )
    bitmap = generate_font_bitmap(root, font_path)
    bitmap.save(outputs["font_bitmap"], format="BMP", bits=4)
    outputs["font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": GLYPH_SIZE,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    ui_bitmap = generate_ui_font_bitmap(root, font_path)
    ui_bitmap.save(
        outputs["ui_font_bitmap"], format="BMP", bits=4)
    outputs["ui_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    result_bitmap = generate_result_font_bitmap(root, font_path)
    result_bitmap.save(
        outputs["result_font_bitmap"],
        format="BMP",
        bits=4,
    )
    outputs["result_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    result_compact_bitmap = generate_result_compact_font_bitmap(
        root, font_path)
    result_compact_bitmap.save(
        outputs["result_compact_font_bitmap"],
        format="BMP",
        bits=4,
    )
    outputs["result_compact_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    action_menu_bitmap = generate_action_menu_font_bitmap(
        root, font_path)
    action_menu_bitmap.save(
        outputs["action_menu_font_bitmap"],
        format="BMP",
        bits=4,
    )
    outputs["action_menu_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    preparation_bitmap = generate_preparation_font_bitmap(
        root, font_path)
    preparation_bitmap.save(
        outputs["preparation_font_bitmap"],
        format="BMP",
        bits=4,
    )
    outputs["preparation_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    target_status_bitmap = generate_target_status_font_bitmap(
        root, font_path)
    target_status_bitmap.save(
        outputs["target_status_font_bitmap"],
        format="BMP",
        bits=4,
    )
    outputs["target_status_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    target_metrics_bitmap = generate_target_metrics_font_bitmap(
        root, font_path)
    target_metrics_bitmap.save(
        outputs["target_metrics_font_bitmap"],
        format="BMP",
        bits=4,
    )
    outputs["target_metrics_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    duel_status_bitmap = generate_duel_status_font_bitmap(
        root, font_path)
    duel_status_bitmap.save(
        outputs["duel_status_font_bitmap"],
        format="BMP",
        bits=4,
    )
    outputs["duel_status_font_metadata"].write_text(
        json.dumps(
            {
                "type": "sprite",
                "height": UI_GLYPH_HEIGHT,
            },
            ensure_ascii=False,
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    return outputs


def write_repository_outputs(
    root: Path | str,
    *,
    font_path: Path | str = DEFAULT_FONT_PATH,
) -> dict[str, Path]:
    root = Path(root)
    destinations = {
        "content_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "generated_battle_identity_content.h"
        ),
        "font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_identity_sprite_font.h"
        ),
        "font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_identity_font.bmp"
        ),
        "font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_identity_font.json"
        ),
        "ui_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_ui_sprite_font.h"
        ),
        "ui_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_ui_font.bmp"
        ),
        "ui_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_ui_font.json"
        ),
        "result_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_result_sprite_font.h"
        ),
        "result_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_result_font.bmp"
        ),
        "result_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_result_font.json"
        ),
        "result_compact_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_result_compact_sprite_font.h"
        ),
        "result_compact_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_result_compact_font.bmp"
        ),
        "result_compact_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_result_compact_font.json"
        ),
        "action_menu_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_action_menu_sprite_font.h"
        ),
        "action_menu_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_action_menu_font.bmp"
        ),
        "action_menu_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_action_menu_font.json"
        ),
        "preparation_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_preparation_sprite_font.h"
        ),
        "preparation_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_preparation_font.bmp"
        ),
        "preparation_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_preparation_font.json"
        ),
        "target_status_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_target_status_sprite_font.h"
        ),
        "target_status_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_target_status_font.bmp"
        ),
        "target_status_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_target_status_font.json"
        ),
        "target_metrics_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_target_metrics_sprite_font.h"
        ),
        "target_metrics_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_target_metrics_font.bmp"
        ),
        "target_metrics_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_target_metrics_font.json"
        ),
        "duel_status_font_header": (
            root
            / "butano-sequel/game/include/konoha"
            / "battle_duel_status_sprite_font.h"
        ),
        "duel_status_font_bitmap": (
            root
            / "butano-sequel/graphics"
            / "battle_duel_status_font.bmp"
        ),
        "duel_status_font_metadata": (
            root
            / "butano-sequel/graphics"
            / "battle_duel_status_font.json"
        ),
    }
    with tempfile.TemporaryDirectory() as temporary:
        generated = generate_outputs(
            root,
            Path(temporary),
            font_path=font_path,
        )
        for key, destination in destinations.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(generated[key], destination)
    return destinations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--font",
        type=Path,
        default=DEFAULT_FONT_PATH,
    )
    args = parser.parse_args()
    outputs = write_repository_outputs(
        args.root.resolve(),
        font_path=args.font,
    )
    print(
        "generated battle identities and font: "
        + ", ".join(str(path) for path in outputs.values())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
