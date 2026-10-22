#!/usr/bin/env python3
"""Authoritative table base addresses, and a cross-check against the content banks.

Why a registry
--------------
`sequel/content/*/bank.json` each carry their own `table_offset`.  Those are
*derived facts about the ROM* living in editable content files, and nothing
checked them against a single source of truth.  That is exactly the shape of
bug we already paid for once: a stale `_rom_offset` in a content file
(`notes/u32-pointer-real-writeback-20260710.md`).

The third-party package made the same thing an explicit invariant
(*"Base pointers come from the ROM's own catalogue, never from untrusted
project JSON"*) and proved it with a poisoned-project test.  This module is
our version:

  * `TABLES` is the single authoritative source for the base address of every
    table we have verified;
  * `verify_table_bases()` checks every content bank against it;
  * a mismatch is an error, not a warning.

Tables we have **not** independently verified are listed with
`verified=False`, so the registry is honest about what is known.

Several legacy content banks claim the *same* address under different
names, or claim an address the ROM does not back.  Those collisions are
**adjudicated** here rather than hidden: `CONFLICTS` records the verdict
(merge / split / repoint / falsify), the canonical owner, the native
consumer that proves it and the check that would falsify it.  The raw
collision stays visible in `verify_table_bases()["alias_conflicts"]` so the
audit trail is not lost.  See `notes/alias-conflicts-20261020.md` for the
long form and `tools/alias_audit.py` for the machine check.

Usage:
    python tools/table_registry.py
    python tools/table_registry.py --json build/table-registry.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

CONTENT_ROOT = REPO / "sequel" / "content"

# name -> (address, verified, note)
TABLES: dict[str, tuple[int, bool, str]] = {
    # --- verified in this repo -------------------------------------------
    "font_segments": (0x53D644, True,
                      "字形段表 31 槽 x 8 字节；26 段非空，26/26 指纹匹配"),
    "story_before_root": (0x060C74, True, "剧情脚本 before 根指针表（场景 1..55）"),
    "story_after_root": (0x060D54, True, "剧情脚本 after 根指针表（场景 1..55）"),
    "story_logic_root": (0x060E34, True, "战场事件 logic 根指针表（场景 1..46）"),
    "story_events_root": (0x060EF0, True, "战场事件表根指针表（场景 1..46）"),
    "battle_rules": (0x594758, True,
                     "胜负条件表 stage*0xCC + sub*0x44；86 条有内容，7 类语义由说明文字证实"),
    "mission_index": (0x348DAC, True, "任务文字索引 u8 表，每场景 3 条"),
    "mission_title_table": (0x59AA5C, True, "任务标题文本表"),
    "mission_description_table": (0x59D214, True, "任务说明文本表"),
    "mission_hint_table": (0x59E920, True, "任务提示文本表"),
    "battle_actors": (0x5461C4, True,
                      "战斗配置/编成：stage*0x1AAC + sub*0x8E4，每组 12 槽 x 0xB8"),
    "reward_table": (0x59EAE0, True, "奖励表 24 字节/条，原版 112 条"),
    "character_names": (0x599280, True, "人物名 / 认识卡 62 条"),
    "skill_table": (0x545458, True, "忍术记录表 16 字节/条，87 条（下标 = 忍术 id）"),
    "ninjutsu_names": (0x599634, True, "忍具名表 93 条"),
    "material_names": (0x5A7E8C, True, "强化素材名表 16 条"),
    "portrait_table": (0x5A4DEC, True, "头像指针表 id*40 + expr*8"),
    "portrait_pieces": (0x4643C0, True,
                        "头像拼块表 20 字节/块，6 块拼成 80x80。"
                        "**2026-10-21 闭合**：本表自己没有字面量读者，"
                        "但指针 `0x084643C0` 是静态描述符 `0x0846443C` 的首字，"
                        "而该描述符地址被 **7 处原生代码**加载"
                        "（0x08077D12 / 0x08089B06 / 0x0808B356 / 0x08091036 / "
                        "0x08091680 / 0x08093846 / 0x08096618），"
                        "其中 0x08096618 在头像加载路径上；"
                        "运行时读数（tools/closure_portrait_pieces.py）确认"
                        "描述符首字 = 0x084643C0、6 条记录与 ROM 逐字节相等。"
                        "记录布局：u16 起始 tile / u16 0 / u16 x / u16 y / u16 w / "
                        "u16 h / u16 0x0100 / u16 0x0100 / u16 0x20FF / u16 0"),
    "background_table": (0x59903C, True, "剧情底图表 id*16，14 个有效 id"),
    "pickup_dispatch": (0x815E4, True, "原生拾取分派表，7 个处理程序"),
    "map_table": (0x53D910, True,
                  "战斗地图表 32 字节/条；terrain 长度 == 图块宽 x 图块高 x 2（47/47）"),
    "character_template": (0x54241C, True, "角色定义表 0xB4/条，63 条"),
    # 2026-10-21: the `units` bank's base was right but its framing was not.
    # `0x53F298` is a 43-entry u16 REMAP table (a permutation of 0..48 minus
    # {14,15,16,17,19,20}); its value is added to a runtime u16 at WRAM
    # 0x0202CA24 and masked back to 16 bits, i.e. an index into a 64 KB
    # window.  The old "u16[64] unit id table" spanned three structures.
    "unit_slot_remap": (0x53F298, True,
                        "单位槽重映射表 43 项 u16（0..48 的排列，去掉 6 个未用 id）；"
                        "值 + WRAM 0x0202CA24 的 u16 后掩到 16 位"),
    "unit_delta_table": (0x53F2EE, True,
                         "紧邻的有符号增量表 16 项 u16（读者 0x08080AE0）"),
    # 2026-10-21: the callback dispatch tables, located at instruction level
    # (see notes/evidence/callback-dispatch-tables-20261021.md).  None of them
    # has a literal reference to its own base -- the bases are computed.
    "glyph_metrics_table": (
        0x53E328, True,
        "字形度量表 6 字节/字形（+0 宽度像素、+1 另一侧偏移）；"
        "读者 0x0807EE98/0x0807EEA8/0x0807EEBE，索引 = [r3+2]*2 + [r3+4]*4；"
        "全 ROM 7 个字面量读者"),
    "object_type_records": (
        0x53EF30, True,
        "对象类型记录表 **步长 24 字节**、21 条（id 0x01..0x15）："
        "+0x00 u32 表索引（0 = id 不可用）、+0x04..+0x0C 备用、"
        "+0x10 初始化函数、+0x14 更新函数；"
        "派发点 0x0807FE56（id*24），其 +0 再索引 object_spawn_table；"
        "表尾 0x53EF30 + 21*24 = 0x53F140 正好接 object_descriptor_table"),
    "object_spawn_table": (
        0x59911C, True,
        "实体描述分派表 8 字节/条（两个代码指针 0x0834xxxx）；"
        "由对象类型记录的 +0x00 索引（×8），派发点 0x0807FE7E/0x0807FE80"),
    "entity_spawn_jump_table": (
        0x53F310, True,
        "实体生成跳表 4 字节/条、13 项（id 1..13，id 0 为 0），"
        "每项是调 fn 0x08080BA0（生成）或 fn 0x08080B08（读描述符）的 thunk；"
        "命令字最高字节 = 实体类型号，派发点 0x08080E44"),
    # 2026-10-21: `mechanism-effects` lives in the *code* region -- it is a
    # 13-entry function pointer table, not a data table.  It has exactly one
    # literal site (0x08081368) which holds the table's own address.
    "mechanism_effect_table": (
        0x08136C, True,
        "机制效果分派表 13 项代码指针（**在代码区**），"
        "消费者 fn 0x080812DC；基址 0x0808136C 的唯一字面量位置是 0x08081368"),
    # 2026-10-21: the five legacy `story*` banks turned out to be m4a
    # SongHeaders of sound ids 1/2/8/11/14, each legacy base 4 bytes late
    # (anchored on the voicegroup pointer instead of the header start).
    "audio_song_1": (0x536368, True, "m4a SongHeader（sound id 1），8 轨"),
    "audio_song_2": (0x536BC4, True, "m4a SongHeader（sound id 2），10 轨"),
    "audio_song_8": (0x538FEC, True, "m4a SongHeader（sound id 8），9 轨"),
    "audio_song_11": (0x53AB74, True, "m4a SongHeader（sound id 11），10 轨"),
    "audio_song_14": (0x53C3BC, True, "m4a SongHeader（sound id 14），8 轨"),
    # 2026-10-21: the legacy `character-stats` / `character-stats-b` bases were
    # skewed windows into ONE table; `levels` was skewed by one record.
    "per_character_stats": (0x545068, True,
                            "逐角色属性表 16 字节/条，63 条（0x545068..0x545458，"
                            "末尾正好接忍术记录表 0x545458）；读者 0x0806D98C"),
    "battle_encounter_records": (0x54229C, True,
                                 "战斗遭遇记录表 16 字节/条，24 条"
                                 "（3 个 u32 指针 + 1 个 u32 编号）；2 个原生读者；"
                                 "表尾正好接角色模板 0x54241C"),
    "item_skill_records": (0x545BE4, True,
                            "道具/技能记录表 16 字节/条，94 条；7 个原生读者；"
                            "表尾正好接战斗编成矩阵 0x5461C4"),
    "character_perks": (0x5459C8, True,
                        "角色特性表 12 字节/条，45 条（0x5459C8..0x545BE4）；"
                        "6 个读者"),
    # A live table the repository had not registered at all: three native
    # readers, 10-byte records.
    "sprite_frame_descriptors": (0x53EE98, True,
                                 "精灵帧描述符表 10 字节/条，15 条；"
                                 "3 个原生读者（0x080806BA / 0x0808077E / 0x0808082E）"),
    "sprite_action_table": (0x596CCC, True,
                            "精灵动作表 id*144 + action*16，每项 4 个 u32 指针"
                            "(frames, animations, gfx, palette)；id 1..62 有效，id 0/63 空槽；"
                            "18 个原生读者，例如 0x0806B76C (fn 0x0806B720)"),
    "sound_id_table": (0x465B70, True,
                       "音频 sound-ID 表 159 条 x 8 字节；原生读者 0x08061E3A/0x0809AAC6 "
                       "(fn 0x08061D8C / 0x0809A998)"),
    # 2026-10-21: the last nine legacy banks were adjudicated by
    # tools/rebase_resolve.py; see notes/evidence/rebase-resolve-20261021.md
    # and notes/evidence/legacy-rebase-final-20261021.md.  Every address below
    # is the one a NATIVE READER loads, and every "end" is proved by the
    # table running exactly into the next known structure.
    "battle_handler_table": (0x53E698, True,
                             "战斗/地图事件处理程序分派表 8 字节/条 x 256"
                             "（每条两个 u32 代码指针，167 条非空）；"
                             "原生读者 0x0807F934 / 0x0807FD28（fn 0x0807F414）；"
                             "表尾 0x53E698 + 256*8 = 0x53EE98 正好接精灵帧描述符表"),
    "font_width_table": (0x53E596, True,
                         "字宽表 1 字节/条 x 256（按字符码索引）；"
                         "唯一原生读者 0x0807F0FC（fn 0x0807EE50）"
                         "执行 'ldrb r0,[r0]' 取字符码后加到 0x0853E596 再取宽度；"
                         "表尾 0x53E596 + 256 = 0x53E696，距下一张表 0x53E698 差 2 字节"),
    "data_pointer_table_a": (0x5A143C, True,
                             "数据指针表 A：46 项 u32，全部是 ROM 指针（46/46）；"
                             "原生读者 0x0808A6BA / 0x0808B19E；"
                             "表尾 0x5A143C + 46*4 = 0x5A14F4"),
    "data_pointer_table_b": (0x5A2034, True,
                             "数据指针表 B：90 项 u32（79 项是 ROM 指针）；"
                             "原生读者 0x080985D8 / 0x08099D26；"
                             "表尾 0x5A2034 + 90*4 = 0x5A219C"),
    "tile_asset_records": (0x5A320C, True,
                           "图块/精灵资源记录表 68 字节/条 x 79（+0x0C 是 6 个 u32 图块指针，"
                           "+0x28/+0x2C/+0x30 是 3 个 u32 脚本指针；"
                           "记录里允许出现全 0 的空槽）；"
                           "10 个原生读者，例如 0x0809881E（fn 0x0809880C）"
                           "用 'ldrb' 取 8 位索引后按 idx*17*4 = idx*68 定位；"
                           "表尾 0x5A320C + 79*68 = 0x5A4708 处结构干净断裂"
                           "（前后是指针块结构变了），再往后是 16 字节步长的另一张表"),
    "palette_source_table": (0x5A57C4, True,
                             "调色板源表 12 字节/条（每条 = 一个 u32 色值 + 8 字节 0）；"
                             "12 个原生读者；正好接在头像表 0x5A4DEC + 63*40 之后"),
    "function_pointer_table": (0x53D5F0, True,
                               "函数指针表 13 槽 u32：槽 0 与槽 12 是 FFFFFFFF 哨兵，"
                               "槽 1..11 是 11 个代码指针（0x08061C8D 起每槽 +12 字节等距）；"
                               "原生读者 0x08061DD4（fn 0x08061D8C）以 *4 索引；"
                               "表尾 0x53D5F0 + 13*4 = 0x53D624 正好接 printf 格式串"),

    # --- adjudicated legacy banks ------------------------------------------
    # These addresses are the ones the legacy extraction got wrong or could
    # not tell apart.  `notes/alias-conflicts-20261020.md` records the
    # adjudication; `CONFLICTS` below is the machine-readable form and
    # `tools/alias_audit.py` re-derives it from the ROM.
    "legacy_object_window_53f138": (
        0x53F138, False,
        "已裁决：0x53F138 是 0x53F140 起的 88 槽指针数组的头部窗口"
        "（槽 0/1 = 代码指针 0x080808BD / 0x08080965，槽 2..87 = 0x0812F5xx 场景对象描述符）。"
        "audio 身份作废（此处与音频无关），palettes 身份作废（目标不是 RGB555 调色板）。"
        "真实基址见 object_descriptor_table"),
    "legacy_skill_record_window": (
        0x546100, False,
        "已裁决：items 与 skills 是同一张 16 字节记录表，规范名 skills，"
        "items 降级为弃用别名。0x546100 只是该表**第 81 条 + 12 字节**的"
        "错位窗口（真基址 0x545BE4，94 条，7 个原生读者），本身没有原生读者"),
    "object_descriptor_table": (
        0x53F140, True,
        "已裁决：0x53F140 是 **43 条 8 字节记录**（每条 {u32 指针, u32 指针}），"
        "指向 0x0812F5xx 的场景对象/动作描述符记录；原生读者 0x08080B12"
        "（fn 0x08080B08）用 'lsls r0, r7, #3' 按 ×8 取表并连续读 +0 / +4；"
        "表尾 0x53F140 + 43*8 = 0x53F298 正好接 unit_slot_remap。"
        "旧称「86 项 u32 指针表」只是同一片字节的 u32 视图。"
        "旧称 0x53F1DC / 0x53F200 是这张表的窗口"),
    "legacy_resource_pointers": (
        0x596F0C, False,
        "已裁决：**不是与精灵动作表并列的另一张表**，而是 "
        "sprite_action_table（0x596CCC）**第 5 条记录**的窗口"
        "（0x596CCC + 4*144 = 0x596F0C）；原生读者 0x0807B220 把它装进 r0 "
        "交给 fn 0x080625A4 —— 与 map-sprites 同一条取表指令"),
    "falsified_sappy_claim": (
        0x079668, False,
        "已证伪：0x08079668 是文本/消息对象分派函数，不是 Sappy 音频分发器——"
        "它从 0x08599634（忍具名文本指针表）与 0x0859937C 取文本指针，"
        "再调 0x08066758 构造显示对象。bank 的 command_handlers / "
        "event_audio_mapping 结论作废；真正的 sound-ID 表在 0x465B70"),

    # --- inherited from the legacy bank extraction, not independently
    #     re-verified here.  Listed so a mismatch is still visible, but they
    #     are not treated as authoritative. --------------------------------
    "legacy_battle_encounters": (0x542384, False,
                                 "已裁决：真实基址 0x54229C（16 字节/条 x 24），"
                                 "旧基址 0x542384 晚了 14 条 + 8 字节"),
    "legacy_battle_handlers": (0x53E6D8, False,
                               "已裁决：真实基址 0x53E698（8 字节/条 x 256，2 个 u32 代码指针），"
                               "旧基址 0x53E6D8 是第 8 条起的错位窗口"),
    "legacy_character_stats": (0x54507A, False,
                               "已裁决：真实基址 0x545068（16 字节/条 x 63），"
                               "旧基址 0x54507A 是第 1 条 + 2 字节的窗口"),
    "legacy_character_stats_b": (0x545200, False,
                                 "已裁决：真实基址 0x545068（同一张表），"
                                 "旧基址 0x545200 = 0x545068 + 25*16 + 8"),
    "legacy_cutscene_scripts": (0x53DF70, False, "过场脚本表"),
    "legacy_data_table_a": (0x5A14A4, False,
                            "已裁决：真实基址 0x5A143C（u32 ROM 指针 x 46），"
                            "旧基址 0x5A14A4 = 0x5A143C + 26*4"),
    "legacy_data_table_b": (0x5A2120, False,
                            "已裁决：真实基址 0x5A2034（u32 x 90），"
                            "旧基址 0x5A2120 = 0x5A2034 + 59*4"),
    "legacy_fonts": (0x53E5B4, False,
                     "已裁决：真实基址 0x53E596（字宽表 256 字节，按字符码索引），"
                     "旧基址 0x53E5B4 晚了 30 字节"),
    "legacy_function_pointers": (0x53D5F4, False,
                                 "已裁决：真实基址 0x53D5F0（13 槽 u32，槽 0/12 为哨兵），"
                                 "旧基址 0x53D5F4 是槽 1（第一个真实指针）"),
    "legacy_levels": (0x5459D4, False,
                      "已裁决：真实基址 0x5459C8（12 字节/条 x 45），"
                      "旧基址 0x5459D4 晚了 12 字节"),
    "legacy_map_events": (0x53EB08, False,
                          "已裁决：真实基址 0x53E698（与 battle-handlers 同一张表），"
                          "旧基址 0x53EB08 = 0x53E698 + 142*8"),
    "legacy_menu_ui": (0x5A5774, False,
                       "已裁决：旧基址 0x5A5774 是头像表 0x5A4DEC 的第 61..62 行"
                       "（每行 40 字节），不是独立的菜单 UI 表"),
    "legacy_save_state": (0x53D848, False, "存档描述符表"),
    "legacy_story": (0x53636C, False, "旧剧情表（与剧情 VM 的根表不是同一张）"),
    "legacy_story_b": (0x536BC8, False, "旧剧情表 b"),
    "legacy_story_c": (0x538FF0, False, "旧剧情表 c"),
    "legacy_story_d": (0x53AB78, False, "旧剧情表 d"),
    "legacy_story_e": (0x53C3C0, False, "旧剧情表 e"),
    "legacy_tile_assets": (0x5A3218, False,
                           "已裁决：真实基址 0x5A320C（68 字节/条，+0x0C 是 6 个 u32 "
                           "图块指针），旧基址 0x5A3218 是记录 0 的 +0x0C 指针块窗口"),
    "legacy_units": (0x53F298, False,
                     "单位 ID 表（旧命名；2026-10-21 证明它其实是 43 项 u16 "
                     "重映射表，见 unit_slot_remap）"),
}

# content bank name -> the registry entry it must agree with
#
# Several legacy banks describe the *same* structure under different names.
# They all point at one registry entry, so the cross-check below still
# validates every one of them; which name is canonical is decided in
# `CONFLICTS` and in `notes/alias-conflicts-20261020.md`.
BANK_TO_REGISTRY = {
    "maps": "map_table",
    "encounter-zones": "map_table",      # merge: 同一张 32 字节地图描述符表
    "positions": "battle_actors",
    "units": "unit_slot_remap",        # 2026-10-21: 重映射表 + 运行时基址偏移
    "battle-encounters": "battle_encounter_records",
    "battle-handlers": "battle_handler_table",   # 2026-10-21: 旧基址 0x53E6D8 错了 8 条
    "character-stats": "per_character_stats",
    "character-stats-b": "per_character_stats",   # 同一张表的另一个错位窗口
    "cutscene-scripts": "legacy_cutscene_scripts",
    "data-table-a": "data_pointer_table_a",       # 2026-10-21: 旧基址 0x5A14A4 错了 26 项
    "data-table-b": "data_pointer_table_b",       # 2026-10-21: 旧基址 0x5A2120 错了 59 项
    "fonts": "font_width_table",                  # 2026-10-21: 旧基址 0x53E5B4 晚了 30 字节
    "function-pointers": "function_pointer_table",  # 2026-10-21: 旧基址 0x53D5F4 是槽 1
    "items": "item_skill_records",         # 2026-10-21: 旧基址 0x546100 是错位窗口
    "skills": "item_skill_records",
    "levels": "character_perks",
    "map-events": "battle_handler_table",    # 2026-10-21: 与 battle-handlers 是同一张表
    "map-sprites": "object_descriptor_table",
    "menu-ui": "portrait_table",             # 2026-10-21: 旧窗口是头像表第 61..62 行
    "audio": "legacy_object_window_53f138",     # 已退役，见 RETIRED
    "palettes": "legacy_object_window_53f138",   # 已退役，见 RETIRED
    "resource-pointers": "legacy_resource_pointers",
    "sappy-engine": "falsified_sappy_claim",   # 已退役，见 RETIRED
    "save-state": "legacy_save_state",
    "sprite-animations": "sprite_action_table",
    "story": "audio_song_1",          # 2026-10-21: 实为 m4a SongHeader
    "story-b": "audio_song_2",
    "story-c": "audio_song_8",
    "story-d": "audio_song_11",
    "story-e": "audio_song_14",
    "tile-assets": "tile_asset_records",   # 2026-10-21: 旧基址 0x5A3218 是记录 0 的 +0x0C 窗口
    "battle-config": "skill_table",
}

# ---------------------------------------------------------------------------
# Alias adjudication
# ---------------------------------------------------------------------------
# The legacy extraction produced several banks that claim the same address
# (or claim an address that the ROM does not back).  Completion condition
# C1 ("身份唯一") and C6 ("无待裁决冲突", notes/completion-audit-20261020.md
# §1.1) are satisfied when such a collision carries an explicit decision --
# not when the collision is silently hidden.
#
# `CONFLICTS` is that decision table.  `tools/alias_audit.py` re-derives the
# collisions from the banks + the ROM and fails when a collision has no
# entry here, so a new collision cannot slip in unnoticed.
#
# Long form, with the per-conflict dead-man-switch checks and the proposed
# diffs for files this registry may not touch:
#
#     notes/alias-conflicts-20261020.md
#
# Keys are the hex file offsets of the contested address.  Each entry:
#   banks             every bank involved in the collision
#   verdict           merge | split | repoint | falsify
#   base_status       native-reader | relocated | unproven-window | not-a-table
#   canonical_bank    the bank that owns the structure after the decision
#   canonical_address the authoritative base address after the decision
#   dispositions      per-bank disposition (merge / deprecated / falsified)
#   evidence          the native-consumer instruction that proves the verdict
#   falsifiable_test  the check that would prove the verdict wrong
#   checks            the mechanical checks `tools/alias_audit.py` runs
# ---------------------------------------------------------------------------
CONFLICTS: dict[str, dict] = {
    "0x545068": {
        "banks": ["character-stats", "character-stats-b"],
        "verdict": "merge",
        "base_status": "skewed-window",
        "canonical_bank": "character-stats",
        "canonical_address": 0x545068,
        "dispositions": {
            "character-stats": "canonical: 逐角色属性表 0x545068，63 条 x 16 字节",
            "character-stats-b": "deprecated-alias: 同一张表的另一个错位窗口"
                                 "（旧基址 0x545200 = 0x545068 + 25*16 + 8）",
        },
        "evidence": "唯一原生读者 0x0806D98C（fn 0x0806D964）载入 0x08545068 "
                    "并以 x16 索引（lsls r1,r2,#4）；同一函数的另一次载入是 "
                    "角色模板 0x0854241C（x180），两者是两张不同的表。"
                    "表尾 0x545068 + 63*16 = 0x545458，正好是忍术记录表的起点。",
        "falsifiable_test": "0x0806D98C 必须仍以 x16 索引 0x08545068；"
                            "0x545068 + 63*16 必须仍等于 0x545458；"
                            "两个 bank 的 20/18 条目必须逐字节等于 ROM 在 "
                            "0x545068 + 16*(1+i)+2 / 0x545068 + 16*(25+i)+8 处的字节。"
                            "若任一条不成立，本裁决作废。",
        "checks": [
            {"kind": "reader", "address": 0x545068, "at": 0x0806D98C,
             "why": "0x0806D98C 必须读 0x08545068（逐角色属性表）"},
            {"kind": "reader", "address": 0x545458, "at": 0x0806D866,
             "why": "0x0806D866 必须读 0x08545458（忍术记录表）—— 它紧接在属性表之后"},
        ],
    },
    "0x545be4": {
        "banks": ["items", "skills"],
        "verdict": "merge",
        "base_status": "skewed-window",
        "canonical_bank": "skills",
        "canonical_address": 0x545BE4,
        "dispositions": {
            "items": "deprecated-alias: 同一张 16 字节记录表，items 不再是独立道具表",
            "skills": "canonical",
        },
        "evidence": (
            "0x545BE4 有 7 个原生读者（0x0806D91A，fn 0x0806D85C），步长 16 字节；"
            "0x545BE4 + 94*16 = 0x5461C4，正好是战斗编成矩阵的起点。"
            "旧基址 0x546100 = 0x545BE4 + 81*16 + 12，是这张表的**第 81 条 + 12 字节**"
            "的错位窗口（ROM 里 0x08546100 仍然零读者）。"
        ),
        "falsifiable_test": (
            "0x0806D91A 必须仍以 x16 索引 0x08545BE4；0x545BE4 + 94*16 必须仍等于 "
            "0x5461C4；两个 bank 的条目必须逐字节等于 ROM 在 0x545BE4 + 16*i 处的字节。"
            "若任一条不成立，本裁决作废。"
        ),
        "checks": [
            {"kind": "reader", "address": 0x545BE4, "at": 0x0806D91A,
             "why": "0x0806D91A 必须读 0x08545BE4（道具/技能记录表）"},
            {"kind": "reader", "address": 0x5461C4, "at": 0x0806DF28,
             "why": "0x0806DF28 必须读 0x085461C4（战斗编成矩阵）—— "
                    "它紧接在这张表之后"},
        ],
    },
    "0x53f138": {
        "banks": ["audio", "palettes", "map-sprites"],
        "verdict": "falsify",
        "base_status": "relocated",
        "canonical_bank": "map-sprites",
        "canonical_address": 0x53F140,
        "dispositions": {
            "audio": "falsified: 0x53F138 与音频无关，其 Sappy 叙事整体作废",
            "palettes": "deprecated-window: 目标不是 RGB555 调色板；"
                        "0x53F138 只是 0x53F140 数组头部 2 个代码指针的窗口",
            "map-sprites": "repointed: 真实基址 0x53F140（86 项 u32 指针表）",
        },
        "evidence": (
            "0x0853F138 无原生读者；0x0853F140 有 1 个读者 0x08080B12（fn 0x08080B08），"
            "经 0x08063494 → 0x080625A4 按 id*11 索引；"
            "槽 0/1 = 0x080808BD / 0x08080965（代码指针），槽 2..87 指向 0x0812F5xx 记录；"
            "记录 0x12F5B0 内含 u32 指针 0x0812F598 / 0x0812F5B4，不是 32 字节 RGB555 调色板"
        ),
        "falsifiable_test": (
            "0x0812F5B0 起的 32 字节若能解出 16 个 BGR555 且含 0x7FFF 透明色，"
            "则 palettes 的旧身份成立、本裁决作废；"
            "0x08080B12 若不是读 0x0853F140，则真实基址另有其处"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x53F138,
             "why": "0x53F138 本身没有原生读者，它只是数组头部窗口"},
            {"kind": "reader", "address": 0x53F140, "at": 0x08080B12,
             "why": "0x08080B12 必须读 0x0853F140（真实基址）"},
        ],
    },
    "0x53d910": {
        "banks": ["encounter-zones", "maps"],
        "verdict": "merge",
        "base_status": "native-reader",
        "canonical_bank": "maps",
        "canonical_address": 0x53D910,
        "dispositions": {
            "encounter-zones": "deprecated-alias: 同一张 32 字节地图描述符表，"
                               "+0x1C 字段的 zone_id 命名待定",
            "maps": "canonical",
        },
        "evidence": (
            "0x0853D910 有 8 个原生读者；关键消费者 0x08069040（fn 0x08068FF0 地图 loader）"
            "执行 'ldr r5,[pc,#0x98]' 取 0x0853D910、'lsls r6, r2, #5'（步长 32 字节）、"
            "'adds r0, r5, #4' 读 +0x04 图形指针，随后依次读 +0x08/+0x0C/+0x10/+0x14"
        ),
        "falsifiable_test": (
            "0x08069040 的步长若不是 32、或基址不是 0x0853D910，则 maps 的描述符表身份不成立；"
            "反向检验：47 个条目的 terrain 解压长度必须 == 宽 x 高 x 2（47/47）"
        ),
        "checks": [
            {"kind": "reader", "address": 0x53D910, "at": 0x08069040,
             "why": "地图 loader 0x08069040 必须读 0x0853D910"},
            {"kind": "reader", "address": 0x53D910, "at": 0x08069220,
             "why": "同一 loader 里的第二处 0x0853D910 读取"},
        ],
    },
    "0x53f200": {
        "banks": ["sprite-animations"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "sprite-animations",
        "canonical_address": 0x596CCC,
        "dispositions": {
            "sprite-animations": "repointed: 真实精灵动作表 0x596CCC"
                                 "（id*144 + action*16，每项 4 个 u32 指针）",
        },
        "evidence": (
            "0x0853F200 无原生读者；它只是 0x53F140 起的指针数组第 48 项起的 38 窗口。"
            "0x08596CCC 有 18 个原生读者，0x0806B76C（fn 0x0806B720）执行 "
            "'muls r1, r0, r1' 做 id 索引；条目 = 4 个 u32 指针 (frames, animations, gfx, palette)，"
            "id 1..62 有效、id 0/63 全 0、id 64 起已是另一张表"
        ),
        "falsifiable_test": (
            "0x08596CCC + 63*144 的条目必须全 0、+ 64*144 的条目必须含非 ROM 指针；"
            "若 id 64 起仍是动作表，则表的 id 范围不是 1..62，本裁决的表长需修正"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x53F200,
             "why": "0x53F200 不得有原生读者，它只是 0x53F140 数组的窗口"},
            {"kind": "reader", "address": 0x596CCC, "at": 0x0806B76C,
             "why": "0x0806B76C 必须读 0x08596CCC（真实精灵动作表）"},
        ],
    },
    "0x596f0c": {
        "banks": ["resource-pointers"],
        "verdict": "merge",
        "base_status": "native-reader-window",
        "canonical_bank": "sprite-animations",
        "canonical_address": 0x596CCC,
        "dispositions": {
            "resource-pointers": "deprecated-window: 0x596F0C = 0x596CCC + 0x240，"
                                 "即精灵动作表的第 36 项（id 4 / action 0），"
                                 "不是独立的资源指针表",
        },
        "evidence": (
            "0x08596F0C 只有 1 个原生读者 0x0807B220（fn 0x0807AE04）；"
            "而**同一个函数**还读 0x08596CCC（0x0807AF1C / 0x0807AF64 / 0x0807AFA4 / "
            "0x0807AFE4）—— 一个函数同时读表首和表内 +0x240，"
            "说明两者是同一张表而不是两张表。"
            "算术上 0x596CCC + 0x240 = 0x596F0C，正好落在动作表内"
            "（id 4 / action 0，步长 id*144 + action*16）"
        ),
        "falsifiable_test": (
            "0x0807AE04 若不再读 0x08596CCC，或 0x08596F0C 的条目形态与"
            "0x596CCC 的 4-u32 指针记录不同构，则 resource-pointers 可能是独立表，"
            "本裁决作废"
        ),
        "checks": [
            {"kind": "reader", "address": 0x596F0C, "at": 0x0807B220,
             "why": "0x0807B220 必须读 0x08596F0C（表内窗口）"},
            {"kind": "reader", "address": 0x596CCC, "at": 0x0807AF1C,
             "why": "同一函数 0x0807AE04 必须也读 0x08596CCC（表首），"
                    "这是「同一张表的两个窗口」的关键证据"},
        ],
    },
    "0x079668": {
        "banks": ["sappy-engine"],
        "verdict": "falsify",
        "base_status": "not-a-table",
        "canonical_bank": None,
        "canonical_address": None,
        "dispositions": {
            "sappy-engine": "falsified: 0x08079668 是文本/消息对象分派函数，不是音频分发器",
        },
        "evidence": (
            "0x08079668 的字面量池里有 0x08599634 与 0x0859937C —— 前者是本仓库已登记的"
            "忍具名文本指针表（0x599634），其条目指向字模编码的中文串（如 0x08002288 = "
            "'81 7C 81 7C ... 00'），不是音频采样；"
            "它再调 0x08066758，该函数 'bl 0x080655b4' 分配显示对象后 'bl 0x0806626c' 初始化，"
            "是显示对象构造而非音频播放。0x08079668 本身没有任何字面量指向 0x53F138"
        ),
        "falsifiable_test": (
            "若 0x08066758 内部出现 PCM/混音寄存器写入或调用 Sappy 播放例程，"
            "则 '文本/消息对象分派' 的判定作废；"
            "若 0x08599634 的条目指向音频采样而非字模编码文本，则 bank 反而成立"
        ),
        "also_inspect": [0x599634, 0x59937C, 0x079668],
        "checks": [
            {"kind": "no_reader", "address": 0x53F138,
             "why": "0x08079668 从不读 0x0853F138，Sappy 音频表不存在"},
            {"kind": "reader", "address": 0x599634, "at": 0x080796E4,
             "why": "0x080796E4 必须读 0x08599634（忍具名文本指针表），"
                    "这证明它取的是文本指针而不是音频采样"},
            {"kind": "reader", "address": 0x59937C, "at": 0x080796D8,
             "why": "0x080796D8 必须读 0x0859937C（另一张文本指针表）"},
        ],
    },
    "0x53f1dc": {
        "banks": ["map-sprites"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "map-sprites",
        "canonical_address": 0x53F140,
        "dispositions": {
            "map-sprites": "repointed: 0x53F1DC 是 0x53F140 起的第 39 项窗口；"
                           "门禁文档记的 0x53E1DC 不成立",
        },
        "evidence": (
            "0x0853F1DC 与 0x0853E1DC 都没有原生读者（各 0 个）。"
            "0x53F1DC = 0x53F140 + 0x9C，即真实基址的第 39 项，"
            "其后的 47 项正好到 0x53F298（u16 单位表）之前；"
            "0x53E1DC 落在事件处理程序区（最近的高热度索引是 0x53E014 / 9 读者、"
            "0x53E328 / 7 读者），其字节是 0x1C00 / 0x2400 / 0x07 这类小整数，不含指针"
        ),
        "falsifiable_test": (
            "0x53E1DC 起的连续项若能被读成合法 0x08xxxxxx 指针，"
            "则门禁文档的 0x53E1DC 成立、本裁决作废；"
            "反向检验：0x53F140 的 86 项必须全部是合法 ROM 指针"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x53F1DC,
             "why": "0x53F1DC 不得有原生读者，它只是 0x53F140 数组的窗口"},
            {"kind": "no_reader", "address": 0x53E1DC,
             "why": "门禁文档记的 0x53E1DC 同样没有原生读者"},
            {"kind": "reader", "address": 0x53F140, "at": 0x08080B12,
             "why": "0x08080B12 必须读 0x0853F140（真实基址）"},
        ],
    },
    # ------------------------------------------------------------------
    # 2026-10-21: the last nine legacy bases, adjudicated by
    # tools/rebase_resolve.py (notes/evidence/rebase-resolve-20261021.md).
    # Every verdict below is re-checkable by `tools/alias_audit.py`, which
    # re-derives the native readers from the ROM itself.
    # ------------------------------------------------------------------
    "0x53e698": {
        "banks": ["battle-handlers", "map-events"],
        "verdict": "merge",
        "base_status": "native-reader",
        "canonical_bank": "battle-handlers",
        "canonical_address": 0x53E698,
        "dispositions": {
            "battle-handlers": "canonical: 处理程序分派表 0x53E698，8 字节/条 x 256",
            "map-events": "deprecated-alias: 同一张表；旧基址 0x53EB08 = "
                          "0x53E698 + 142*8（8 字节记录按 4 字节步长读，"
                          "所以旧记录里 23/47 条是同一个处理程序）",
        },
        "evidence": (
            "0x0853E698 有 2 个原生读者 0x0807F934 / 0x0807FD28（fn 0x0807F414）；"
            "每条 8 字节 = 两个 u32 代码指针。表尾 0x53E698 + 256*8 = 0x53EE98，"
            "正好是已登记的精灵帧描述符表 0x53EE98。"
            "旧基址 0x53E6D8 与 0x53EB08 在 ROM 里都零引用。"
        ),
        "falsifiable_test": (
            "0x0807F934 必须仍读 0x0853E698；0x53E698 + 256*8 必须仍等于 0x53EE98；"
            "两个 bank 的记录必须逐字节等于 ROM 在 0x53E698 + 8*i 处的字节。"
            "若任一条不成立，本裁决作废。"
        ),
        "checks": [
            {"kind": "reader", "address": 0x53E698, "at": 0x0807F934,
             "why": "0x0807F934 必须读 0x0853E698（处理程序分派表）"},
            {"kind": "reader", "address": 0x53E698, "at": 0x0807FD28,
             "why": "0x0807FD28 必须读 0x0853E698（同一张表的第二处读取）"},
        ],
    },
    "0x53e6d8": {
        "banks": ["battle-handlers"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "battle-handlers",
        "canonical_address": 0x53E698,
        "dispositions": {
            "battle-handlers": "repointed: 真实基址 0x53E698；旧基址 0x53E6D8 是第 8 条窗口",
        },
        "evidence": "0x0853E6D8 在 ROM 里零引用；0x0853E698 有 2 个原生读者。",
        "falsifiable_test": "0x0807F934 若不再读 0x0853E698，则真实基址另有其处。",
        "checks": [
            {"kind": "no_reader", "address": 0x53E6D8,
             "why": "0x53E6D8 不得有原生读者，它只是错位窗口"},
            {"kind": "reader", "address": 0x53E698, "at": 0x0807F934,
             "why": "0x0807F934 必须读 0x0853E698（真实基址）"},
        ],
    },
    "0x53eb08": {
        "banks": ["map-events"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "battle-handlers",
        "canonical_address": 0x53E698,
        "dispositions": {
            "map-events": "deprecated-alias: 与 battle-handlers 是同一张表；"
                          "旧基址 0x53EB08 = 0x53E698 + 142*8",
        },
        "evidence": (
            "0x0853EB08 在整个 ROM 里没有任何字节模式出现；"
            "0x53EB08 - 0x53E698 = 0x470 = 142*8，正好落在 8 字节记录表的第 142 项；"
            "旧记录 47 条里有 23 条是同一个处理程序 —— 这是「8 字节记录按 4 字节步长读」"
            "的特征，而不是一张独立的、以 0 结尾的表。"
        ),
        "falsifiable_test": (
            "0x0853EB08 若在 ROM 里出现任意一次字面量引用，或 0x53EB08 处的字节"
            "不是 0x53E698 + 142*8 处的字节，则 map-events 可能是独立表，本裁决作废。"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x53EB08,
             "why": "0x53EB08 不得有原生读者"},
            {"kind": "reader", "address": 0x53E698, "at": 0x0807F934,
             "why": "0x0807F934 必须读 0x0853E698（map-events 的真实基址）"},
        ],
    },
    "0x53e5b4": {
        "banks": ["fonts"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "fonts",
        "canonical_address": 0x53E596,
        "dispositions": {
            "fonts": "repointed: 真实基址 0x53E596（字宽表 256 字节）；"
                     "旧基址 0x53E5B4 晚了 30 字节",
        },
        "evidence": (
            "唯一原生读者 0x0807F0FC（fn 0x0807EE50）执行 "
            "'ldr r1,[pc,#0x14]' 取 0x0853E596，再 'ldrb r0,[r0]' 取字符码、"
            "相加后 'ldrb r1,[r0]' 取宽度 —— 索引是 8 位字符码，所以表是 256 字节。"
            "0x53E596 + 256 = 0x53E696，距下一张表 0x53E698 差 2 字节。"
        ),
        "falsifiable_test": (
            "0x0807F0FC 必须仍读 0x0853E596；若字宽表的条目数不是 256，"
            "则 bank 的 entry_count 需要同步修正。"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x53E5B4,
             "why": "0x53E5B4 不得有原生读者，它只是 30 字节后的错位窗口"},
            {"kind": "reader", "address": 0x53E596, "at": 0x0807F0FC,
             "why": "0x0807F0FC 必须读 0x0853E596（字宽表）"},
        ],
    },
    "0x5a14a4": {
        "banks": ["data-table-a"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "data-table-a",
        "canonical_address": 0x5A143C,
        "dispositions": {
            "data-table-a": "repointed: 真实基址 0x5A143C（u32 ROM 指针 x 46）；"
                            "旧基址 0x5A14A4 = 0x5A143C + 26*4",
        },
        "evidence": (
            "0x085A143C 有 2 个原生读者 0x0808A6BA / 0x0808B19E；"
            "46 项全是 ROM 指针（指针比例 46/46）；表尾 0x5A143C + 46*4 = 0x5A14F4。"
        ),
        "falsifiable_test": "0x0808A6BA 必须仍读 0x085A143C；表尾必须仍是 0x5A14F4。",
        "checks": [
            {"kind": "no_reader", "address": 0x5A14A4,
             "why": "0x5A14A4 不得有原生读者"},
            {"kind": "reader", "address": 0x5A143C, "at": 0x0808A6BA,
             "why": "0x0808A6BA 必须读 0x085A143C（数据指针表 A）"},
        ],
    },
    "0x5a2120": {
        "banks": ["data-table-b"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "data-table-b",
        "canonical_address": 0x5A2034,
        "dispositions": {
            "data-table-b": "repointed: 真实基址 0x5A2034（u32 x 90）；"
                            "旧基址 0x5A2120 = 0x5A2034 + 59*4",
        },
        "evidence": (
            "0x085A2034 有 2 个原生读者 0x080985D8 / 0x08099D26；"
            "90 项里 79 项是 ROM 指针；表尾 0x5A2034 + 90*4 = 0x5A219C。"
        ),
        "falsifiable_test": "0x080985D8 必须仍读 0x085A2034；表尾必须仍是 0x5A219C。",
        "checks": [
            {"kind": "no_reader", "address": 0x5A2120,
             "why": "0x5A2120 不得有原生读者"},
            {"kind": "reader", "address": 0x5A2034, "at": 0x080985D8,
             "why": "0x080985D8 必须读 0x085A2034（数据指针表 B）"},
        ],
    },
    "0x5a5774": {
        "banks": ["menu-ui"],
        "verdict": "repoint",
        "base_status": "native-reader-window",
        "canonical_bank": "menu-ui",
        "canonical_address": 0x5A4DEC,
        "dispositions": {
            "menu-ui": "deprecated-alias: 旧基址 0x5A5774 = 头像表 0x5A4DEC 的第 61 行"
                       "（每行 40 字节），覆盖第 61..62 行，不是独立的菜单 UI 表",
        },
        "evidence": (
            "0x085A4DEC 的唯一原生读者 0x08096158（fn 0x08096138）执行 "
            "'lsls r0,r2,#2; adds r0,r0,r2; lsls r0,r0,#3'（= id*40）"
            "与 'lsls r1,r1,#3'（= expr*8），再从 0x085A4DEC 取指针。"
            "0x5A5774 - 0x5A4DEC = 0x988 = 61*40 —— 正好是第 61 行的行首，"
            "而且 0x5A5774 + 80 = 0x5A57C4 = 0x5A4DEC + 63*40，即头像表第 63 行的行首。"
        ),
        "falsifiable_test": (
            "0x08096158 必须仍读 0x085A4DEC 并按 id*40+expr*8 索引；"
            "若 0x5A5774 起的内容不是头像表第 61..62 行，则 menu-ui 可能是独立表。"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x5A5774,
             "why": "0x5A5774 不得有原生读者，它只是头像表内的窗口"},
            {"kind": "reader", "address": 0x5A4DEC, "at": 0x08096158,
             "why": "0x08096158 必须读 0x085A4DEC（头像表，menu-ui 的真实基址）"},
        ],
    },
    "0x53d5f4": {
        "banks": ["function-pointers"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "function-pointers",
        "canonical_address": 0x53D5F0,
        "dispositions": {
            "function-pointers": "repointed: 真实基址 0x53D5F0（13 槽 u32，槽 0/12 是哨兵）；"
                                 "旧基址 0x53D5F4 是槽 1",
        },
        "evidence": (
            "唯一原生读者 0x08061DD4（fn 0x08061D8C）以 *4 索引 0x0853D5F0。"
            "13 个槽里槽 0 与槽 12 是 FFFFFFFF 哨兵，槽 1..11 是 11 个代码指针，"
            "等距 12 字节（0x08061C8D + 12*i）。表尾 0x53D5F0 + 13*4 = 0x53D624，"
            "正好接 printf 格式串 \"%d8,*%...\"。"
        ),
        "falsifiable_test": (
            "0x08061DD4 必须仍读 0x0853D5F0；ROM[0x53D5F4 + 4i] 必须仍等于 "
            "0x08061C8D + 12*i（i = 0..10）；槽 0 与槽 12 必须仍是 FFFFFFFF。"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x53D5F4,
             "why": "0x53D5F4 不得有原生读者，它只是槽 1"},
            {"kind": "reader", "address": 0x53D5F0, "at": 0x08061DD4,
             "why": "0x08061DD4 必须读 0x0853D5F0（函数指针表）"},
        ],
    },
    "0x5a3218": {
        "banks": ["tile-assets"],
        "verdict": "repoint",
        "base_status": "relocated",
        "canonical_bank": "tile-assets",
        "canonical_address": 0x5A320C,
        "dispositions": {
            "tile-assets": "repointed: 真实基址 0x5A320C（68 字节/条 x 79，+0x0C 是 6 个 u32 "
                           "图块指针）；旧基址 0x5A3218 是记录 0 的 +0x0C 指针块窗口",
        },
        "evidence": (
            "0x085A320C 有 10 个原生读者；读者 0x0809881E（fn 0x0809880C）执行 "
            "'ldrb r2,[r3]' 取 8 位索引，再 'lsls r1,r2,#4; adds r1,r1,r2; "
            "lsls r1,r1,#2'（= idx*17*4 = idx*68）定位记录，"
            "随后 'ldr r0,[r8,#0xc]' 读 +0x0C 的 6 个图块指针。"
            "旧 bank 的 6 条记录正好是记录 0 的 +0x0C..+0x24 指针块。"
        ),
        "falsifiable_test": (
            "0x0809881E 必须仍读 0x085A320C 并按 idx*68 定位；"
            "若记录步长不是 68，则 tile-assets 的结构判定作废；"
            "记录数 79 由「指针块结构在 0x5A4708 处干净断裂」确定 —— "
            "若 0x5A4708 起的内容又能按 68 字节读成同样的记录，则条数需修正。"
        ),
        "checks": [
            {"kind": "no_reader", "address": 0x5A3218,
             "why": "0x5A3218 不得有原生读者，它只是记录 0 的字段窗口"},
            {"kind": "reader", "address": 0x5A320C, "at": 0x0809881E,
             "why": "0x0809881E 必须读 0x085A320C（图块资源记录表）"},
            {"kind": "reader", "address": 0x5A320C, "at": 0x0809845C,
             "why": "0x0809845C 必须读 0x085A320C（同一张表的第二处读取）"},
        ],
    },
}

# Banks whose claimed identity was disproved: they keep their historical
# address in bank.json (so the raw collision stays visible in the audit
# trail) but they no longer own a table.
FALSIFIED: dict[str, str] = {
    "sappy-engine": CONFLICTS["0x079668"]["dispositions"]["sappy-engine"],
    "audio": CONFLICTS["0x53f138"]["dispositions"]["audio"],
}

# Banks that were **retired from the content catalogue** (2026-10-21).
#
# "Retired" is the concrete action the completion audit asked for when it
# said "身份已作废，应退役该 bank": the bank keeps its file (so the audit
# trail -- what it used to claim and why that claim died -- stays readable)
# but it is flagged `retired: true` in bank.json, it no longer appears in
# `BANK_TO_REGISTRY` (it does not own a table), and no tool re-imports it.
RETIRED: dict[str, str] = {
    "sappy-engine": (
        "身份作废：0x08079668 是文本/消息对象分派函数，不是 Sappy 音频分发器。"
        "真正的 sound-ID 表在 0x465B70（见 sound-id-table）"),
    "audio": (
        "身份作废：0x53F138 处是 0x53F140 指针数组头部的 2 个代码指针，"
        "与音频无关；Sappy 叙事整体作废"),
    "palettes": (
        "身份作废：0x53F138 只是 0x53F140 数组头部的窗口，不是 RGB555 调色板。"
        "调色板数据在 VRAM 0x05000380，由 0x53DF70 的关卡数据块经 BIOS "
        "svc 0x12 解压写入"),
}

# Deprecated bank name -> the canonical bank that owns the structure.
ALIASES: dict[str, str] = {
    "items": "skills",
    "encounter-zones": "maps",
    "palettes": "map-sprites",
    "resource-pointers": "sprite-animations",
}



def load_bank_offsets(content_root: pathlib.Path | None = None) -> dict[str, int | None]:
    """bank name -> declared table_offset (None when the bank declares none)."""
    root = content_root or CONTENT_ROOT
    out: dict[str, int | None] = {}
    for path in sorted(root.glob("*/bank.json")):
        name = path.parent.name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out[name] = None
            continue
        offset = data.get("table_offset")
        out[name] = int(offset) if isinstance(offset, int) else None
    return out


def load_bank_meta(content_root: pathlib.Path | None = None) -> dict[str, dict]:
    """bank name -> {offset, entry_count, entry_size, alias_of, falsified}."""
    root = content_root or CONTENT_ROOT
    out: dict[str, dict] = {}
    for path in sorted(root.glob("*/bank.json")):
        name = path.parent.name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out[name] = {}
            continue
        offset = data.get("table_offset")
        out[name] = {
            "offset": int(offset) if isinstance(offset, int) else None,
            "entry_count": data.get("entry_count") if isinstance(data.get("entry_count"), int) else None,
            "entry_size": data.get("entry_size") if isinstance(data.get("entry_size"), int) else None,
            "alias_of": data.get("alias_of"),
            "falsified": bool(data.get("falsified")),
        }
    return out


def verify_table_bases(content_root: pathlib.Path | None = None) -> dict:
    """Cross-check every content bank against the registry."""
    declared = load_bank_offsets(content_root)
    rows = []
    errors = []
    for bank, registry_key in sorted(BANK_TO_REGISTRY.items()):
        if bank not in declared:
            continue
        expected, verified, note = TABLES[registry_key]
        actual = declared[bank]
        match = actual == expected
        rows.append({
            "bank": bank,
            "registry_entry": registry_key,
            "declared": actual,
            "declared_hex": hex(actual) if actual is not None else None,
            "authoritative": expected,
            "authoritative_hex": hex(expected),
            "match": match,
            "authoritative_verified": verified,
            "note": note,
        })
        if not match:
            errors.append(
                f"{bank}: declares table_offset {actual and hex(actual)} but the "
                f"authoritative base is {hex(expected)} ({registry_key})"
            )

    # Alias conflicts: two banks claiming the same base.
    #
    # The raw collision stays visible here on purpose -- it is the audit
    # trail.  What makes it *adjudicated* is the matching entry in
    # `CONFLICTS`; `adjudicated` says whether such an entry exists.
    by_base: dict[int, list[str]] = defaultdict(list)
    for bank, offset in declared.items():
        if offset is not None:
            by_base[offset].append(bank)
    aliases = []
    for base, names in sorted(by_base.items()):
        if len(names) < 2:
            continue
        key = hex(base)
        decision = CONFLICTS.get(key)
        aliases.append({
            "address": key,
            "banks": sorted(names),
            "adjudicated": decision is not None,
            "verdict": decision["verdict"] if decision else None,
            "canonical_bank": decision["canonical_bank"] if decision else None,
            "canonical_address": decision["canonical_address"] if decision else None,
        })

    # Windows that overlap without sharing a base address (e.g. 0x53F138 and
    # 0x53F140) are the same class of problem and must be adjudicated too.
    overlaps = []
    meta = load_bank_meta(content_root)
    ranges = []
    for bank, info in sorted(meta.items()):
        offset = info.get("offset")
        if offset is None:
            continue
        count = info.get("entry_count") or 1
        size = info.get("entry_size") or 4
        ranges.append((bank, offset, offset + max(count, 1) * max(size, 1)))
    for i, (bank_a, lo_a, hi_a) in enumerate(ranges):
        for bank_b, lo_b, hi_b in ranges[i + 1:]:
            if lo_a < hi_b and lo_b < hi_a and lo_a != lo_b:
                key = hex(min(lo_a, lo_b))
                decision = CONFLICTS.get(key)
                overlaps.append({
                    "address": key,
                    "banks": sorted([bank_a, bank_b]),
                    "adjudicated": decision is not None,
                })

    return {
        "banks_checked": len(rows),
        "rows": rows,
        "mismatches": errors,
        "alias_conflicts": aliases,
        "alias_overlaps": overlaps,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None)
    ap.add_argument("--allow-legacy-mismatch", action="store_true",
                    help="only fail on banks whose base is independently verified")
    args = ap.parse_args()

    report = verify_table_bases()
    if args.json:
        path = pathlib.Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"content banks checked: {report['banks_checked']}")
    print()
    for row in report["rows"]:
        if row["match"]:
            continue
        print(f"  MISMATCH {row['bank']}: declares {row['declared_hex']}, "
              f"authoritative {row['authoritative_hex']} ({row['registry_entry']})")
    print()
    if report["alias_conflicts"]:
        print("alias conflicts (two banks claim the same base):")
        for alias in report["alias_conflicts"]:
            print(f"  {alias['address']} <- {', '.join(alias['banks'])}")
        print()

    strict = [r for r in report["rows"]
              if not r["match"] and r["authoritative_verified"]]
    if report["mismatches"]:
        print(f"mismatches: {len(report['mismatches'])} "
              f"({len(strict)} on independently verified bases)")
    else:
        print("mismatches: 0 - every content bank agrees with the registry")

    if strict:
        return 1
    if report["mismatches"] and not args.allow_legacy_mismatch:
        print("(use --allow-legacy-mismatch to downgrade legacy-only mismatches)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
