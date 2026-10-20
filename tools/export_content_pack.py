#!/usr/bin/env python3
"""Export the ROM's editable content into the editor's content pack.

The pack is the editor's *initial data*: a complete, self-describing dump of
every structure and every text table the editor can edit.  Two invariants:

  * every structure's field list TILES its record exactly — known fields plus
    `hex` filler for every byte nobody has decoded — so an untouched pack
    rebuilds the original ROM byte for byte;
  * every text table keeps its original bytes, so the editor can show the
    ROM as it is and write back only what the author changed.

Usage:
    python tools/export_content_pack.py --rom rom/base.gba \
        --out rom-editor/content/pack.json
    python tools/export_content_pack.py --check      # verify the pack is current
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from tools import text_codec  # noqa: E402
from tools.lib.io import write_text  # noqa: E402

ROM_BASE = 0x08000000
PACK_FORMAT = "naruto-konoha-content-pack"
PACK_VERSION = 1

# --- geometry constants (all adjudicated; see notes/ and the RE handoff) ----
CHARACTER_TEMPLATE_BASE = 0x54241C
CHARACTER_TEMPLATE_STRIDE = 0xB4
CHARACTER_TEMPLATE_COUNT = 63          # id 0 = null, 1..62 live
PER_CHARACTER_STATS_BASE = 0x545068
PER_CHARACTER_STATS_STRIDE = 0x10
PER_CHARACTER_STATS_COUNT = 63
JUTSU_RECORD_BASE = 0x545458            # 忍术记录表
JUTSU_RECORD_STRIDE = 0x10
JUTSU_RECORD_COUNT = 87
PERK_BASE = 0x5459C8                   # 角色特性表（技能）
PERK_STRIDE = 0x0C
PERK_COUNT = 45
ITEM_RECORD_BASE = 0x545BE4            # 道具/忍具记录表
ITEM_RECORD_STRIDE = 0x10
ITEM_RECORD_COUNT = 94
REWARD_BASE = 0x59EAE0
REWARD_STRIDE = 0x18
REWARD_COUNT = 112
CHARACTER_NAMES_BASE = 0x599280
CHARACTER_NAMES_COUNT = 63
JUTSU_NAMES_BASE = 0x59937C
JUTSU_NAMES_COUNT = 87
NINJUTSU_NAMES_BASE = 0x599634        # 忍具名表
NINJUTSU_NAMES_COUNT = 94
MATERIAL_NAMES_BASE = 0x5A7E8C
MATERIAL_NAMES_COUNT = 18
TRAINING_NAMES_BASE = 0x5A7060
TRAINING_NAMES_COUNT = 45
PORTRAIT_TABLE_BASE = 0x5A4DEC
PORTRAIT_TABLE_COUNT = 64
PORTRAIT_TABLE_STRIDE = 40
PORTRAIT_PIECES_BASE = 0x4643C0
PORTRAIT_PIECES_STRIDE = 0x14
PORTRAIT_PIECES_COUNT = 6

MAP_TABLE_BASE = 0x53D910
MAP_TABLE_STRIDE = 32
MAP_TABLE_COUNT = 47
BATTLE_ACTORS_BASE = 0x5461C4
BATTLE_GROUP_STRIDE = 0x1AAC
BATTLE_VARIANT_STRIDE = 0x8E4
BATTLE_SLOT_STRIDE = 0xB8
BATTLE_SLOT_COUNT = 12
BATTLE_GROUP_COUNT = 47                # group 47 would land on battle_rules
BATTLE_VARIANT_COUNT = 3
BATTLE_OBJECT_OFFSET = 0x8A4
BATTLE_OBJECT_COUNT = 16
BATTLE_OBJECT_STRIDE = 4
BATTLE_RULES_BASE = 0x594758
BATTLE_RULE_STAGE_STRIDE = 0xCC
BATTLE_RULE_SUB_STRIDE = 0x44
BATTLE_RULE_COUNT = 47
BATTLE_ENCOUNTER_BASE = 0x54229C
BATTLE_ENCOUNTER_STRIDE = 16
BATTLE_ENCOUNTER_COUNT = 24
UNIT_REMAP_BASE = 0x53F298
UNIT_REMAP_COUNT = 43
UNIT_DELTA_BASE = 0x53F2EE
UNIT_DELTA_COUNT = 16
LEVEL_BLOCK_BASE = 0x53DF70
LEVEL_BLOCK_COUNT = 4
OBJECT_DESCRIPTOR_BASE = 0x53F140
OBJECT_DESCRIPTOR_COUNT = 86
SPRITE_ACTION_BASE = 0x596CCC
SPRITE_ACTION_COUNT = 576
SPRITE_ACTION_STRIDE = 16

BACKGROUND_TABLE_BASE = 0x59903C
BACKGROUND_TABLE_STRIDE = 16
BACKGROUND_TABLE_COUNT = 14
STORY_BEFORE_ROOT = 0x060C74
STORY_AFTER_ROOT = 0x060D54
STORY_LOGIC_ROOT = 0x060E34
STORY_EVENTS_ROOT = 0x060EF0
STORY_ROOT_SLOTS = 56          # before / after: scenes 1..55
STORY_BATTLE_ROOT_SLOTS = 47   # logic / events: scenes 1..46
MISSION_INDEX_BASE = 0x348DAC
MISSION_INDEX_STAGES = 48      # stage 0..47
MISSION_SUBS = 3
MISSION_TITLE_BASE = 0x59AA5C
MISSION_DESC_BASE = 0x59D214
MISSION_HINT_BASE = 0x59E920
MISSION_ENTRY_COUNT = 112      # 下标 = mission_index[stage] + sub
DIALOGUE_TABLE_BASE = 0x461CE8
DIALOGUE_SLOT_COUNT = 1524      # 305 组 × (4 条 + 1 个 NULL 分隔)
DIALOGUE_GROUP_SIZE = 4
SPEAKER_NAME_BASE = 0x5A57C4
SPEAKER_NAME_STRIDE = 12
SPEAKER_NAME_COUNT = 32        # 记录数未确证；按 32 条呈现
FONT_SEGMENT_BASE = 0x53D644
FONT_SEGMENT_COUNT = 31
FONT_SEGMENT_STRIDE = 8
BACKGROUND_TABLE_BASE = 0x59903C
BACKGROUND_TABLE_STRIDE = 16
BACKGROUND_TABLE_COUNT = 36     # 0x59903C .. 0x599280 之间放得下 36 条

# --- 其余已证实、但此前未进包的表（见 notes/evidence/content-pack-export-20261021.md §4.1）
SOUND_ID_TABLE_BASE = 0x465B70
SOUND_ID_TABLE_STRIDE = 8
SOUND_ID_TABLE_COUNT = 159
AUDIO_SONG_BASE = {            # m4a SongHeader：8 字节头 + track_count × 4 字节轨道指针
    1: (0x536368, 8),
    2: (0x536BC4, 10),
    8: (0x538FEC, 9),
    11: (0x53AB74, 10),
    14: (0x53C3BC, 8),
}
FUNCTION_POINTER_TABLE_BASE = 0x53D5F0
FUNCTION_POINTER_TABLE_COUNT = 13
FONT_WIDTH_TABLE_BASE = 0x53E596
FONT_WIDTH_TABLE_COUNT = 256
BATTLE_HANDLER_TABLE_BASE = 0x53E698
BATTLE_HANDLER_TABLE_COUNT = 256
BATTLE_HANDLER_STRIDE = 8
SPRITE_FRAME_DESC_BASE = 0x53EE98
SPRITE_FRAME_DESC_COUNT = 15
SPRITE_FRAME_DESC_STRIDE = 10
PICKUP_DISPATCH_BASE = 0x0815E4
PICKUP_DISPATCH_COUNT = 7
DATA_POINTER_A_BASE = 0x5A143C
DATA_POINTER_A_COUNT = 46
DATA_POINTER_B_BASE = 0x5A2034
DATA_POINTER_B_COUNT = 90
TILE_ASSET_RECORDS_BASE = 0x5A320C
TILE_ASSET_RECORDS_COUNT = 79
TILE_ASSET_RECORDS_STRIDE = 68

TASK_LABEL = "任务"


# --------------------------------------------------------------------------
# field helpers
# --------------------------------------------------------------------------
def F(key: str, offset: int, size: int, ftype: str, label: str,
      desc: str = "", group: str | None = None,
      array: str | None = None, index: int | None = None,
      item: str | None = None) -> dict[str, Any]:
    field = {
        "key": key,
        "offset": offset,
        "size": size,
        "type": ftype,
        "label": label,
    }
    if desc:
        field["desc"] = desc
    if group:
        field["group"] = group
    if array:
        field["array"] = array
    if index is not None:
        field["index"] = index
    if item:
        field["item"] = item
    return field


def tile(entry_size: int, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a field list that covers [0, entry_size) exactly, no gaps."""
    ordered = sorted(fields, key=lambda f: f["offset"])
    out: list[dict[str, Any]] = []
    cursor = 0
    for field in ordered:
        if field["offset"] < cursor:
            raise ValueError(
                f"字段重叠: {field['key']} @0x{field['offset']:X} < 0x{cursor:X}"
            )
        if field["offset"] + field["size"] > entry_size:
            raise ValueError(
                f"字段超出记录: {field['key']} @0x{field['offset']:X}"
                f"+{field['size']} > 记录长度 {entry_size}；"
                f"字段必须描述【单条】记录，不是整张表"
            )
        if field["offset"] > cursor:
            gap = field["offset"] - cursor
            out.append(F(f"raw_{cursor:02x}", cursor, gap, "hex",
                         f"未解字节 +0x{cursor:02X}",
                         "尚未解码的原始字节，原样保留"))
            cursor = field["offset"]
        out.append(field)
        cursor = field["offset"] + field["size"]
    if cursor < entry_size:
        gap = entry_size - cursor
        out.append(F(f"raw_{cursor:02x}", cursor, gap, "hex",
                     f"未解字节 +0x{cursor:02X}",
                     "尚未解码的原始字节，原样保留"))
    return out


def read_fields(rom: bytes, offset: int, fields: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in fields:
        chunk = rom[offset + field["offset"]: offset + field["offset"] + field["size"]]
        ftype = field["type"]
        if ftype == "hex":
            values[field["key"]] = chunk.hex()
        elif ftype == "u8":
            values[field["key"]] = chunk[0]
        elif ftype in ("u16", "s16"):
            values[field["key"]] = struct.unpack_from("<H", chunk, 0)[0]
            if ftype == "s16":
                raw = values[field["key"]]
                values[field["key"]] = raw - 0x10000 if raw >= 0x8000 else raw
        elif ftype in ("u32", "s32", "ptr"):
            values[field["key"]] = struct.unpack_from("<I", chunk, 0)[0]
            if ftype == "s32":
                raw = values[field["key"]]
                values[field["key"]] = raw - (1 << 32) if raw >= 0x80000000 else raw
        else:
            raise ValueError(f"未知字段类型 {ftype}")
    return values


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------
def decode_text(raw: bytes, mapping: dict[int, str]) -> str:
    return text_codec.decode(raw, mapping)


def text_block_end(rom: bytes, offset: int, limit: int = 4096) -> int:
    """Offset just past the NUL-terminated string at `offset`."""
    end = offset
    stop = min(len(rom), offset + limit)
    while end < stop and rom[end] != 0:
        end += 1
    return end


def build_text_table(
    rom: bytes,
    mapping: dict[int, str],
    table_id: str,
    module: str,
    label: str,
    pointer_base: int,
    count: int,
    note: str = "",
    nul_terminated: bool = True,
    id_prefix: str = "",
) -> dict[str, Any]:
    """A u32 pointer table whose entries point at font-coded strings."""
    records = []
    texts = []
    for i in range(count):
        ptr_offset = pointer_base + i * 4
        ptr = struct.unpack_from("<I", rom, ptr_offset)[0]
        record: dict[str, Any] = {
            "id": i,
            "label": f"{id_prefix}{i}" if id_prefix else str(i),
            "pointer_offset": ptr_offset,
            "pointer": ptr,
            "text_offset": None,
            "capacity": 0,
            "text": None,
            "original_text": None,
            "raw": "",
        }
        if ptr and ROM_BASE <= ptr < ROM_BASE + len(rom):
            text_offset = ptr - ROM_BASE
            end = text_block_end(rom, text_offset)
            raw = rom[text_offset:end]
            text = decode_text(raw, mapping)
            record["text_offset"] = text_offset
            record["capacity"] = len(raw) + (1 if nul_terminated else 0)
            record["text"] = text
            record["original_text"] = text
            record["raw"] = b64(raw)
            texts.append(text_offset)
        records.append(record)

    table = {
        "id": table_id,
        "module": module,
        "label": label,
        "pointer_table_offset": pointer_base,
        "count": count,
        "relocatable": True,
        "nul_terminated": nul_terminated,
        "records": records,
    }
    if note:
        table["note"] = note
    if texts:
        table["text_span"] = {
            "start": min(texts),
            "end": max(texts),
        }
    return table


# --------------------------------------------------------------------------
# structure builders
# --------------------------------------------------------------------------
def make_structure(
    structure_id: str,
    module: str,
    label: str,
    rom_offset: int,
    entry_size: int,
    fields: list[dict[str, Any]],
    record_offsets: Iterable[int],
    rom: bytes,
    note: str = "",
    primary_columns: list[str] | None = None,
    record_labels: dict[int, str] | None = None,
    verification: str = "",
) -> dict[str, Any]:
    tiled = tile(entry_size, fields)
    records = []
    for offset in record_offsets:
        rid = len(records)
        record: dict[str, Any] = {
            "id": rid,
            "rom_offset": offset,
            "raw": b64(rom[offset:offset + entry_size]),
            "values": read_fields(rom, offset, tiled),
        }
        if record_labels and rid in record_labels:
            record["label"] = record_labels[rid]
        records.append(record)
    structure = {
        "id": structure_id,
        "module": module,
        "label": label,
        "rom_offset": rom_offset,
        "entry_size": entry_size,
        "entry_count": len(records),
        "fields": tiled,
        "records": records,
    }
    if note:
        structure["note"] = note
    if primary_columns:
        structure["primary_columns"] = primary_columns
    if verification:
        structure["verification"] = verification
    return structure


def character_template_fields() -> list[dict[str, Any]]:
    fields = [
        F("flag_00", 0x00, 1, "u8", "标志00", "恒为 1，无原生读者", "头部"),
        F("stat_a", 0x01, 1, "u8", "属性A 基础", "三项主属性之一，上限 99", "基础属性"),
        F("stat_b", 0x02, 1, "u8", "属性B 基础", "三项主属性之一，上限 99", "基础属性"),
        F("stat_c", 0x03, 1, "u8", "属性C 基础", "三项主属性之一，上限 99", "基础属性"),
        F("stat_d", 0x04, 1, "u8", "属性D 基础", "上限 5", "基础属性"),
        F("stat_e", 0x05, 1, "u8", "属性E 基础", "上限 9", "基础属性"),
        F("stat_f", 0x06, 1, "u8", "属性F 基础", "上限 9", "基础属性"),
        F("flag_07", 0x07, 1, "u8", "标志07", "恒为 0，无原生读者", "头部"),
        F("aux_stat", 0x08, 2, "u16", "副属性", "运行时上限 999", "基础属性"),
        F("hp_base", 0x0A, 2, "u16", "HP 基础", "运行时上限 999", "基础属性"),
    ]
    for i in range(15):
        base = 0x0C + i * 4
        fields += [
            F(f"jutsu_{i}_id", base, 1, "u8", f"忍术{i} ID",
              "忍术记录表下标（0x59937C）", "忍术列表", "jutsu", i, "id"),
            F(f"jutsu_{i}_value", base + 1, 1, "u8", f"忍术{i} 等级值",
              "0/1/3，0xFF = 未习得", "忍术列表", "jutsu", i, "value"),
            F(f"jutsu_{i}_unlock", base + 2, 1, "u8", f"忍术{i} 解锁等级",
              "0 = 不会自动习得", "忍术列表", "jutsu", i, "unlock_level"),
            F(f"jutsu_{i}_pad", base + 3, 1, "u8", f"忍术{i} 填充",
              "恒为 0", "忍术列表", "jutsu", i, "pad"),
        ]
    for i in range(24):
        base = 0x48 + i * 4
        fields += [
            F(f"train_{i}_id", base, 1, "u8", f"技能{i} ID",
              "技能/特性表下标（0x5459C8 / 0x5A7060）", "技能列表", "training", i, "id"),
            F(f"train_{i}_value", base + 1, 1, "u8", f"技能{i} 等级值",
              "等级值，B−1 是成长倍率", "技能列表", "training", i, "value"),
            F(f"train_{i}_unlock", base + 2, 1, "u8", f"技能{i} 解锁等级",
              "0 = 不会自动习得", "技能列表", "training", i, "unlock_level"),
            F(f"train_{i}_pad", base + 3, 1, "u8", f"技能{i} 填充",
              "恒为 0", "技能列表", "training", i, "pad"),
        ]
    for i in range(9):
        fields.append(F(f"item_{i}", 0xA8 + i, 1, "u8", f"道具槽{i}",
                        "忍具名表下标（0x599634），0 = 空", "道具槽", "items", i, "id"))
    return fields


def build_structures(rom: bytes, mapping: dict[int, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    # ---- 角色属性 -------------------------------------------------------
    out.append(make_structure(
        "character_template", "characters", "角色定义表",
        CHARACTER_TEMPLATE_BASE, CHARACTER_TEMPLATE_STRIDE,
        character_template_fields(),
        (CHARACTER_TEMPLATE_BASE + i * CHARACTER_TEMPLATE_STRIDE
         for i in range(CHARACTER_TEMPLATE_COUNT)),
        rom,
        note="每个角色 0xB4 字节。id 0 是空槽，1..62 是有效角色。"
             "忍术列表 15 项、技能列表 24 项、道具槽 9 项。",
        primary_columns=["stat_a", "stat_b", "stat_c", "hp_base", "aux_stat"],
        verification="L1 结构已证明 / 写回路径 tools/import_character_template.py",
    ))

    growth_fields = [
        F("hp_gain", 0x00, 2, "u16", "HP 成长", "每级成长 ×100", "成长"),
        F("stat_f_gain", 0x02, 2, "u16", "属性F 成长", "每级成长 ×100", "成长"),
        F("stat_a_gain", 0x04, 2, "u16", "属性A 成长", "每级成长 ×100", "成长"),
        F("stat_b_gain", 0x06, 2, "u16", "属性B 成长", "每级成长 ×100", "成长"),
        F("stat_c_gain", 0x08, 2, "u16", "属性C 成长", "每级成长 ×100", "成长"),
        F("stat_d_gain", 0x0A, 2, "u16", "属性D 成长", "每级成长 ×100", "成长"),
        F("stat_e_gain", 0x0C, 2, "u16", "属性E 成长", "每级成长 ×100", "成长"),
        F("unused", 0x0E, 2, "u16", "未使用", "恒为 0", "成长"),
    ]
    out.append(make_structure(
        "per_character_stats", "characters", "逐角色成长表",
        PER_CHARACTER_STATS_BASE, PER_CHARACTER_STATS_STRIDE,
        growth_fields,
        (PER_CHARACTER_STATS_BASE + i * PER_CHARACTER_STATS_STRIDE
         for i in range(PER_CHARACTER_STATS_COUNT)),
        rom,
        note="每级数值 = 基础 + 成长 ×(等级−1) ÷ 100（整数除法）。",
        primary_columns=["hp_gain", "stat_a_gain", "stat_b_gain", "stat_c_gain"],
        verification="L1 结构已证明 / 写回路径 tools/import_character_template.py",
    ))

    perk_fields = [
        F("kind", 0x00, 1, "u8", "特性类型", "决定效果分支（0x0D..0x13 出现过），语义未解", "特性"),
        F("unused_01", 0x01, 1, "u8", "未使用", "", "特性"),
        F("base", 0x02, 2, "u16", "基础值", "特性基础数值", "特性"),
        F("secondary", 0x04, 2, "u16", "次要值", "原生 0x0806DDF6 读取", "特性"),
        F("growth", 0x06, 2, "u16", "每级成长", "总成长 = 基础 + 成长×(等级值−1)", "特性"),
        F("extra_stat", 0x08, 2, "u16", "附加属性", "", "特性"),
        F("unused_0a", 0x0A, 2, "u16", "未使用", "", "特性"),
    ]
    out.append(make_structure(
        "character_perks", "characters", "角色特性表（技能）",
        PERK_BASE, PERK_STRIDE, perk_fields,
        (PERK_BASE + i * PERK_STRIDE for i in range(PERK_COUNT)),
        rom,
        note="下标 = 技能（技术）id，与技能名表 0x5A7060 同空间。",
        primary_columns=["kind", "base", "growth"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    portrait_fields: list[dict[str, Any]] = []
    for expr in range(5):
        portrait_fields.append(F(f"expr{expr}_gfx", expr * 8, 4, "ptr",
                                 f"表情{expr} 图像",
                                 "LZ77 4bpp 头像图块，80×80", "头像"))
        portrait_fields.append(F(f"expr{expr}_palette", expr * 8 + 4, 4, "ptr",
                                 f"表情{expr} 调色板",
                                 "64 色 BGR555（未压缩）", "头像"))
    out.append(make_structure(
        "portrait_table", "characters", "头像指针表",
        PORTRAIT_TABLE_BASE, PORTRAIT_TABLE_STRIDE, portrait_fields,
        (PORTRAIT_TABLE_BASE + i * PORTRAIT_TABLE_STRIDE
         for i in range(PORTRAIT_TABLE_COUNT)),
        rom,
        note="每行 40 字节 = 5 个表情 × (图像指针 + 调色板指针)。",
        primary_columns=["expr0_gfx", "expr0_palette"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    piece_fields = [
        F("tile", 0x00, 4, "u32", "图块下标", "0xFFFF = 结束标记", "拼块"),
        F("x", 0x04, 2, "u16", "目标 X", "", "拼块"),
        F("y", 0x06, 2, "u16", "目标 Y", "", "拼块"),
        F("w", 0x08, 2, "u16", "宽度(px)", "", "拼块"),
        F("h", 0x0A, 2, "u16", "高度(px)", "", "拼块"),
    ]
    out.append(make_structure(
        "portrait_pieces", "characters", "头像拼块表",
        PORTRAIT_PIECES_BASE, PORTRAIT_PIECES_STRIDE, piece_fields,
        (PORTRAIT_PIECES_BASE + i * PORTRAIT_PIECES_STRIDE
         for i in range(PORTRAIT_PIECES_COUNT)),
        rom,
        note="6 块拼成 80×80 头像。",
        primary_columns=["tile", "x", "y"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    # ---- 忍术 -----------------------------------------------------------
    jutsu_fields = [
        F("unknown_00", 0x00, 1, "u8", "未知00", "复制到已习得忍术记录 +0x04，语义未解", "记录"),
        F("unknown_01", 0x01, 1, "u8", "未知01", "复制到已习得忍术记录 +0x05，语义未解", "记录"),
        F("flags", 0x02, 2, "u16", "标志位",
          "&0x1800>>5 → 0..0xC0 等级/点数；高字节在仓库里另被标为「未解」", "记录"),
    ]
    for i in range(6):
        jutsu_fields.append(F(f"grow_{i}", 0x04 + i, 1, "u8", f"成长目标{i}",
                              "六个随等级成长的字节属性", "成长"))
    jutsu_fields += [
        F("unknown_0a", 0x0A, 1, "u8", "未知0A", "", "记录"),
        F("unknown_0b", 0x0B, 1, "u8", "未知0B", "", "记录"),
        F("growth_type", 0x0C, 1, "u8", "成长目标", "0/7 = 不成长；1..6 指向上面的成长目标", "成长"),
        F("unknown_0d", 0x0D, 1, "u8", "未知0D", "", "记录"),
        F("growth_amount", 0x0E, 1, "u8", "每级成长量",
          "值 = (等级−1) × 本值；实测 87 条记录中 +0x0F 恒为 0，"
          "所以本字段是单字节（仓库里把 +0x0E 记成 u16 属高字节恒零的等价写法）",
          "成长"),
        F("pad_0f", 0x0F, 1, "u8", "填充0F", "实测 87 条记录恒为 0", "记录"),
    ]
    out.append(make_structure(
        "jutsu_record", "ninjutsu", "忍术记录表",
        JUTSU_RECORD_BASE, JUTSU_RECORD_STRIDE, jutsu_fields,
        (JUTSU_RECORD_BASE + i * JUTSU_RECORD_STRIDE for i in range(JUTSU_RECORD_COUNT)),
        rom,
        note="下标 = 忍术 id，与忍术名表 0x59937C 同空间。",
        primary_columns=["growth_type", "growth_amount", "flags"],
        verification="L1 结构已证明 / 写回路径 tools/import_character_template.py",
    ))

    # ---- 道具 -----------------------------------------------------------
    item_fields = [F(f"raw_{i:02x}", i, 1, "hex", f"字节{i:02X}",
                     "16 字节的字段语义尚未证明，按原始字节编辑", "原始字节")
                   for i in range(16)]
    out.append(make_structure(
        "item_record", "items", "道具/忍具记录表",
        ITEM_RECORD_BASE, ITEM_RECORD_STRIDE, item_fields,
        (ITEM_RECORD_BASE + i * ITEM_RECORD_STRIDE for i in range(ITEM_RECORD_COUNT)),
        rom,
        note="94 条 16 字节记录。仓库里**没有任何一处证明**这 16 字节的字段含义，"
             "所以本表按原始字节呈现并编辑，不臆造字段名。",
        primary_columns=["raw_00", "raw_01", "raw_02", "raw_03"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    reward_fields = [
        F("gold", 0x00, 2, "u16", "金币", "关卡奖励金币", "奖励"),
        F("upgrade_points", 0x02, 2, "u16", "强化点", "升级素材点数", "奖励"),
        F("tier", 0x04, 2, "u16", "等级门槛", "与运行时 0x0202680C 比较", "奖励"),
    ]
    for k in range(8):
        reward_fields += [
            F(f"slot{k}_category", 0x06 + k * 2, 1, "u8", f"道具位{k} 类别",
              "0=忍具 1=强化素材 2=认识卡 3=技能", "道具掉落", "slots", k, "category"),
            F(f"slot{k}_item", 0x07 + k * 2, 1, "u8", f"道具位{k} 物品ID",
              "该类别的名称表下标；0 = 列表结束", "道具掉落", "slots", k, "item_id"),
        ]
    reward_fields += [
        F("reserved_16", 0x16, 1, "u8", "保留16", "恒为 0，无消费者", "保留"),
        F("reserved_17", 0x17, 1, "u8", "保留17", "恒为 0，无消费者", "保留"),
    ]
    out.append(make_structure(
        "reward_table", "items", "奖励表",
        REWARD_BASE, REWARD_STRIDE, reward_fields,
        (REWARD_BASE + i * REWARD_STRIDE for i in range(REWARD_COUNT)),
        rom,
        note="112 条。下标 = 任务索引(0x348DAC) + 关卡子编号。",
        primary_columns=["gold", "upgrade_points", "tier"],
        verification="L1 结构已证明 / 写回路径 tools/import_reward.py",
    ))

    # ---- 战斗 -----------------------------------------------------------
    map_fields = [
        F("raw_width", 0x00, 2, "u16", "原始宽", "图块宽 = 原始宽 ÷ 4", "尺寸"),
        F("raw_height", 0x02, 2, "u16", "原始高", "图块高 = 原始高 ÷ 2", "尺寸"),
        F("tile_gfx_ptr", 0x04, 4, "ptr", "图块图形", "LZ77 4bpp 图形", "资源指针"),
        F("palette_ptr", 0x08, 4, "ptr", "调色板", "LZ77 384 字节", "资源指针"),
        F("layer0_ptr", 0x0C, 4, "ptr", "图层0", "LZ77 tilemap", "资源指针"),
        F("layer1_ptr", 0x10, 4, "ptr", "图层1", "LZ77 tilemap；0 = 无图层1", "资源指针"),
        F("metatile_ptr", 0x14, 4, "ptr", "组合图块表", "LZ77，8 字节/项", "资源指针"),
        F("terrain_ptr", 0x18, 4, "ptr", "通行值表", "LZ77，每格 u16", "资源指针"),
        F("background_id", 0x1C, 1, "u8", "剧情底图ID", "指向底图表 0x59903C", "底图"),
    ]
    out.append(make_structure(
        "map_table", "battle", "战场布置描述符",
        MAP_TABLE_BASE, MAP_TABLE_STRIDE, map_fields,
        (MAP_TABLE_BASE + i * MAP_TABLE_STRIDE for i in range(MAP_TABLE_COUNT)),
        rom,
        note="47 条 32 字节记录。index = 关卡 id（原生 0x08069044 按 id×32 取址）。",
        primary_columns=["raw_width", "raw_height", "background_id"],
        verification="L1 结构已证明 / 写回路径 tools/import_battle_config.py",
    ))

    actor_fields = [
        F("character_id", 0x00, 1, "u8", "角色ID", "0 = 空槽", "角色"),
        F("side", 0x01, 1, "u8", "阵营", "0=我方 1=敌方（编成路径不读此字段）", "角色"),
        F("x", 0x02, 1, "u8", "出生 X", "初始 X 坐标（格）", "出生点"),
        F("y", 0x03, 1, "u8", "出生 Y", "初始 Y 坐标（格）", "出生点"),
        F("facing", 0x04, 1, "u8", "朝向/参数", "写入 unit+0xC9", "出生点"),
        F("unit_flags", 0x08, 4, "u32", "单位标志", "bit0 = 阵营；unit+0xC0 = flags|side|0x10", "角色"),
        F("level", 0x0F, 1, "u8", "等级", "unit+0x0F", "角色"),
    ]
    actor_offsets = []
    actor_labels: dict[int, str] = {}
    for g in range(BATTLE_GROUP_COUNT):
        for v in range(BATTLE_VARIANT_COUNT):
            for s in range(BATTLE_SLOT_COUNT):
                actor_offsets.append(
                    BATTLE_ACTORS_BASE + g * BATTLE_GROUP_STRIDE
                    + v * BATTLE_VARIANT_STRIDE + 4 + s * BATTLE_SLOT_STRIDE
                )
    out.append(make_structure(
        "battle_actors", "battle", "角色出生点（编成表）",
        BATTLE_ACTORS_BASE, BATTLE_SLOT_STRIDE, actor_fields,
        actor_offsets, rom,
        note="47 关 × 3 变体 × 12 槽位，每槽 0xB8 字节。"
             "index = 关卡 g / 变体 v / 槽位 s。",
        primary_columns=["character_id", "side", "x", "y"],
        verification="L1 结构已证明 / 写回路径 tools/import_battle_config.py",
    ))

    object_fields = [
        F("type", 0x00, 1, "u8", "物件类型",
          "0空 1忍具 2强化素材 3修行卷轴 4认识卡 5机关宝箱 6特殊机关 7剧情物件", "物件"),
        F("target", 0x01, 1, "u8", "触发目标", "决定触发的剧本（13 项效果表）", "物件"),
        F("x", 0x02, 1, "u8", "X", "", "物件"),
        F("y", 0x03, 1, "u8", "Y", "", "物件"),
    ]
    object_offsets = []
    for g in range(BATTLE_GROUP_COUNT):
        for v in range(BATTLE_VARIANT_COUNT):
            base = (BATTLE_ACTORS_BASE + g * BATTLE_GROUP_STRIDE
                    + v * BATTLE_VARIANT_STRIDE + BATTLE_OBJECT_OFFSET)
            for o in range(BATTLE_OBJECT_COUNT):
                object_offsets.append(base + o * BATTLE_OBJECT_STRIDE)
    out.append(make_structure(
        "battle_map_objects", "battle", "战场物件",
        BATTLE_ACTORS_BASE, BATTLE_OBJECT_STRIDE, object_fields,
        object_offsets, rom,
        note="每关卡变体 16 个物件，位于编成组 +0x8A4。",
        primary_columns=["type", "target", "x", "y"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    rule_fields = [F("turn_limit", 0x00, 1, "u8", "回合上限", "0 = 无限制", "回合")]
    for group in range(2):
        label = "胜利条件" if group == 0 else "失败条件"
        for k in range(4):
            base = 0x04 + group * 0x20 + k * 8
            rule_fields += [
                F(f"g{group}_{k}_type", base, 1, "u8", f"{label}{k} 类型",
                  "1全灭 2指定角色在场 3指定角色离场 6获得道具 7剩余HP 8击杀数 9收集数",
                  label, "rules", group * 4 + k, "type"),
                F(f"g{group}_{k}_a", base + 1, 1, "u8", f"{label}{k} 参数A", "", label,
                  "rules", group * 4 + k, "a"),
                F(f"g{group}_{k}_b", base + 2, 1, "u8", f"{label}{k} 参数B",
                  "类型 3 时是角色 id", label, "rules", group * 4 + k, "b"),
                F(f"g{group}_{k}_c", base + 3, 1, "u8", f"{label}{k} 参数C", "恒为 0", label,
                  "rules", group * 4 + k, "c"),
                F(f"g{group}_{k}_text_ptr", base + 4, 4, "ptr", f"{label}{k} 说明文本",
                  "「条件」页显示的说明", label, "rules", group * 4 + k, "text_ptr"),
            ]
    rule_offsets = [
        BATTLE_RULES_BASE + s * BATTLE_RULE_STAGE_STRIDE + u * BATTLE_RULE_SUB_STRIDE
        for s in range(BATTLE_RULE_COUNT) for u in range(BATTLE_VARIANT_COUNT)
    ]
    out.append(make_structure(
        "battle_rules", "battle", "战斗目标（胜负条件）",
        BATTLE_RULES_BASE, BATTLE_RULE_SUB_STRIDE, rule_fields,
        rule_offsets, rom,
        note="47 关 × 3 变体 × 0x44 字节。index = 关卡 s / 变体 u。",
        primary_columns=["turn_limit"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    encounter_fields = [
        F("ptr_0", 0x00, 4, "ptr", "指针0", "消费者只取其低字节作下标", "遭遇"),
        F("ptr_1", 0x04, 4, "ptr", "指针1", "无原生读者", "遭遇"),
        F("ptr_2", 0x08, 4, "ptr", "指针2", "无原生读者", "遭遇"),
        F("entry_id", 0x0C, 4, "u32", "遭遇ID", "两个原生读者都读这一项", "遭遇"),
    ]
    out.append(make_structure(
        "battle_encounter_records", "battle", "战斗遭遇记录表",
        BATTLE_ENCOUNTER_BASE, BATTLE_ENCOUNTER_STRIDE, encounter_fields,
        (BATTLE_ENCOUNTER_BASE + i * BATTLE_ENCOUNTER_STRIDE
         for i in range(BATTLE_ENCOUNTER_COUNT)),
        rom,
        note="24 条 16 字节记录。目标记录的自描述格式尚未解码。",
        primary_columns=["entry_id", "ptr_0"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    remap_fields = [F("value", 0, 2, "u16", "重映射值",
                      "槽位 → 内部编号；运行时再加 WRAM 0x0202CA24 的基址", "重映射")]
    out.append(make_structure(
        "unit_slot_remap", "battle", "单位槽位重映射表",
        UNIT_REMAP_BASE, 2, remap_fields,
        (UNIT_REMAP_BASE + i * 2 for i in range(UNIT_REMAP_COUNT)),
        rom,
        note="43 项 u16。取值是 {0..48} 去掉 6 个编号的一个排列。",
        primary_columns=["value"],
        verification="L1 结构已证明 / 写回仅允许复用原生取值",
    ))

    delta_fields = [F("delta", 0, 2, "s16", "位移",
                      "八方向移动偏移（可正可负）", "位移")]
    out.append(make_structure(
        "unit_delta_table", "battle", "八方向位移表",
        UNIT_DELTA_BASE, 2, delta_fields,
        (UNIT_DELTA_BASE + i * 2 for i in range(UNIT_DELTA_COUNT)),
        rom,
        note="16 项有符号 u16。",
        primary_columns=["delta"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    level_fields = [
        F("gfx_ptr", 0x00, 4, "ptr", "图块图形", "LZ77 4bpp", "关卡块"),
        F("palette_ptr", 0x04, 4, "ptr", "调色板", "LZ77 16 色", "关卡块"),
    ]
    out.append(make_structure(
        "level_blocks", "battle", "关卡数据块表",
        LEVEL_BLOCK_BASE, 8, level_fields,
        (LEVEL_BLOCK_BASE + i * 8 for i in range(LEVEL_BLOCK_COUNT)),
        rom,
        note="4 项 × 8 字节，每项一对指针（图块 + 调色板）。",
        primary_columns=["gfx_ptr", "palette_ptr"],
        verification="L1 结构已证明 / 写回路径 tools/import_battle_config.py",
    ))

    descriptor_fields = [F("ptr", 0, 4, "ptr", "对象描述符指针",
                           "对象描述符首地址", "描述符")]
    out.append(make_structure(
        "object_descriptors", "battle", "对象描述符表",
        OBJECT_DESCRIPTOR_BASE, 4, descriptor_fields,
        (OBJECT_DESCRIPTOR_BASE + i * 4 for i in range(OBJECT_DESCRIPTOR_COUNT)),
        rom,
        note="86 项 u32 指针。",
        primary_columns=["ptr"],
        verification="L1 结构已证明 / 写回路径 tools/import_battle_config.py",
    ))

    sprite_fields = []
    for i, name in enumerate(("frames_ptr", "animations_ptr", "gfx_ptr", "palette_ptr")):
        sprite_fields.append(F(name, i * 4, 4, "ptr", name, "精灵资源指针", "指针"))
    out.append(make_structure(
        "sprite_action_table", "battle", "精灵动作表",
        SPRITE_ACTION_BASE, SPRITE_ACTION_STRIDE, sprite_fields,
        (SPRITE_ACTION_BASE + i * SPRITE_ACTION_STRIDE
         for i in range(SPRITE_ACTION_COUNT)),
        rom,
        note="576 项 × 16 字节（4 个 u32 指针）。index = 精灵 id × 16 + 动作。",
        primary_columns=["frames_ptr", "gfx_ptr"],
        verification="L1 结构已证明 / 写回路径 tools/import_sprite_action.py",
    ))

    # ---- 剧情 -----------------------------------------------------------
    background_fields = [
        F("gfx_ptr", 0x00, 4, "ptr", "图块图形", "LZ77 图形", "背景"),
        F("palette_ptr", 0x04, 4, "ptr", "调色板", "LZ77 384 字节", "背景"),
        F("tilemap_ptr", 0x08, 4, "ptr", "tilemap", "LZ77 640 字节（32×32）", "背景"),
        F("bpp_flag", 0x0C, 4, "u32", "色深标志", "0 = 4bpp，1 = 8bpp", "背景"),
    ]
    out.append(make_structure(
        "background_table", "story", "剧情底图表",
        BACKGROUND_TABLE_BASE, BACKGROUND_TABLE_STRIDE, background_fields,
        (BACKGROUND_TABLE_BASE + i * BACKGROUND_TABLE_STRIDE
         for i in range(BACKGROUND_TABLE_COUNT)),
        rom,
        note="0x59903C 起、到人物名表 0x599280 之前共 36 个槽位。"
             "**只有 id 1..7 与 9..13 符合背景记录格式**（图形/调色板/tilemap/色深）；"
             "id 14..35 是另一种记录形态（32 字节调色板），字段含义不同。",
        primary_columns=["gfx_ptr", "palette_ptr", "bpp_flag"],
        verification="L1 结构已证明（id 1..7、9..13）/ 尚无写回路径",
    ))

    for table_id, base, slots, label, note in (
        ("story_before_root", STORY_BEFORE_ROOT, STORY_ROOT_SLOTS,
         "剧情脚本根表（before）", "场景 1..55 指向 before 剧本。槽 0 恒为 0。"),
        ("story_after_root", STORY_AFTER_ROOT, STORY_ROOT_SLOTS,
         "剧情脚本根表（after）", "场景 1..55 指向 after 剧本。"),
        ("story_logic_root", STORY_LOGIC_ROOT, STORY_BATTLE_ROOT_SLOTS,
         "战场事件逻辑根表", "场景 1..46 指向战斗中的事件逻辑剧本。"),
        ("story_events_root", STORY_EVENTS_ROOT, STORY_BATTLE_ROOT_SLOTS,
         "战场事件根表", "场景 1..46 指向战斗事件表剧本。"),
    ):
        fields = [F("ptr", 0, 4, "ptr", "剧本首地址", "该场景的剧本首地址", "场景指针")]
        out.append(make_structure(
            table_id, "story" if table_id in ("story_before_root", "story_after_root") else "battle",
            label, base, 4, fields,
            (base + i * 4 for i in range(slots)), rom,
            note=note,
            primary_columns=["ptr"],
            verification="L1 结构已证明 / 写回路径 tools/import_story_script.py（仅定宽操作数）",
        ))

    mission_index_fields = [
        F("value", 0, 1, "u8", "奖励下标起点",
          "该关卡第 u 个奖励在奖励表 0x59EAE0 里的下标", "任务索引")
    ]
    out.append(make_structure(
        "mission_index", "route", "任务索引表",
        MISSION_INDEX_BASE, 1, mission_index_fields,
        (MISSION_INDEX_BASE + s for s in range(MISSION_INDEX_STAGES)), rom,
        note="每关 3 个子文本；任务文本表下标 = 本表值[关卡] + 子编号（0..2）。"
             "本表 48 字节（关卡 0..47）。",
        primary_columns=["value"],
        record_labels={s: f"第{s}关" for s in range(MISSION_INDEX_STAGES)},
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    font_fields = [
        F("start_code", 0x00, 2, "u16", "起始码", "本段第一个字形码", "字形段"),
        F("count", 0x02, 1, "u8", "字数", "本段字形数量", "字形段"),
        F("pad", 0x03, 1, "u8", "填充", "", "字形段"),
        F("glyph_offset", 0x04, 4, "ptr", "字形偏移", "ROM 指针，每字形 32 字节（8×8 4bpp）", "字形段"),
    ]
    out.append(make_structure(
        "font_segments", "story", "字形段表",
        FONT_SEGMENT_BASE, FONT_SEGMENT_STRIDE, font_fields,
        (FONT_SEGMENT_BASE + i * FONT_SEGMENT_STRIDE
         for i in range(FONT_SEGMENT_COUNT)),
        rom,
        note="31 段 × 8 字节。字库本身决定游戏能画出哪些字。",
        primary_columns=["start_code", "count"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    # --- 其余已证实、此前未进包的表 ---------------------------------------
    sound_id_fields = [
        F("descriptor_ptr", 0x00, 4, "ptr", "描述符指针", "指向 m4a SongHeader", "声音"),
        F("player_index", 0x04, 2, "u16", "播放通道", "", "声音"),
        F("player_config", 0x06, 2, "u16", "播放配置", "", "声音"),
    ]
    out.append(make_structure(
        "sound_id_table", "audio", "音频 sound-ID 表",
        SOUND_ID_TABLE_BASE, SOUND_ID_TABLE_STRIDE, sound_id_fields,
        (SOUND_ID_TABLE_BASE + i * SOUND_ID_TABLE_STRIDE
         for i in range(SOUND_ID_TABLE_COUNT)),
        rom,
        note="159 条 × 8 字节：指向 m4a 歌曲描述符，并给出播放通道与配置。",
        primary_columns=["descriptor_ptr", "player_index"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    for sound_id, (base, tracks) in sorted(AUDIO_SONG_BASE.items()):
        size = 8 + tracks * 4
        song_fields = [
            F("track_count", 0x00, 1, "u8", "轨道数", "", "歌曲头"),
            F("block_count", 0x01, 1, "u8", "块数", "", "歌曲头"),
            F("priority", 0x02, 1, "u8", "优先级", "", "歌曲头"),
            F("reverb", 0x03, 1, "u8", "混响", "", "歌曲头"),
            F("voicegroup_ptr", 0x04, 4, "ptr", "音色组指针", "", "歌曲头"),
        ]
        for t in range(tracks):
            song_fields.append(F(f"track{t}_ptr", 8 + t * 4, 4, "ptr",
                                 f"轨道{t} 指针", "", "轨道"))
        out.append(make_structure(
            f"audio_song_{sound_id}", "audio", f"音频曲 {sound_id}（m4a SongHeader）",
            base, size, song_fields,
            (base,), rom,
            note=f"m4a SongHeader：8 字节头 + {tracks} 个轨道指针（40 字节以内的描述符）。"
                 "音频样本本体不在本表里。",
            primary_columns=["track_count", "block_count", "priority"],
            verification="L1 结构已证明 / 尚无写回路径",
        ))

    out.append(make_structure(
        "function_pointer_table", "audio", "函数指针表",
        FUNCTION_POINTER_TABLE_BASE, 4,
        [F("ptr", 0, 4, "ptr", "代码指针", "槽 0 与槽 12 是 FFFFFFFF 哨兵", "指针")],
        (FUNCTION_POINTER_TABLE_BASE + i * 4
         for i in range(FUNCTION_POINTER_TABLE_COUNT)),
        rom,
        note="13 槽 u32。",
        primary_columns=["ptr"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    out.append(make_structure(
        "font_width_table", "story", "字宽表",
        FONT_WIDTH_TABLE_BASE, 1,
        [F("width", 0, 1, "u8", "字宽", "按字符码索引", "字宽")],
        (FONT_WIDTH_TABLE_BASE + i for i in range(FONT_WIDTH_TABLE_COUNT)),
        rom,
        note="256 字节，按字符码索引的宽度。",
        primary_columns=["width"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    handler_fields = [
        F("handler_a", 0x00, 4, "ptr", "处理程序 A", "", "分派"),
        F("handler_b", 0x04, 4, "ptr", "处理程序 B", "", "分派"),
    ]
    out.append(make_structure(
        "battle_handler_table", "battle", "战斗/地图事件处理程序分派表",
        BATTLE_HANDLER_TABLE_BASE, BATTLE_HANDLER_STRIDE, handler_fields,
        (BATTLE_HANDLER_TABLE_BASE + i * BATTLE_HANDLER_STRIDE
         for i in range(BATTLE_HANDLER_TABLE_COUNT)),
        rom,
        note="256 条 × 8 字节，每条两个代码指针（167 条非空）。"
             "各字段的业务名尚未定。",
        primary_columns=["handler_a", "handler_b"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    frame_fields = [
        F("kind", 0x00, 2, "u16", "类别/链表结束", "业务名未定", "帧描述"),
        F("delta_2", 0x02, 2, "s16", "有符号量", "业务名未定", "帧描述"),
        F("delta_4", 0x04, 2, "s16", "有符号量", "业务名未定", "帧描述"),
        F("kind_6", 0x06, 2, "u16", "类别", "业务名未定", "帧描述"),
        F("end_flag", 0x08, 2, "u16", "结束标志", "业务名未定", "帧描述"),
    ]
    out.append(make_structure(
        "sprite_frame_descriptors", "battle", "精灵帧描述符表",
        SPRITE_FRAME_DESC_BASE, SPRITE_FRAME_DESC_STRIDE, frame_fields,
        (SPRITE_FRAME_DESC_BASE + i * SPRITE_FRAME_DESC_STRIDE
         for i in range(SPRITE_FRAME_DESC_COUNT)),
        rom,
        note="15 条 × 10 字节，五个 u16 字段的业务名都还没定。",
        primary_columns=["kind", "delta_2", "kind_6"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    out.append(make_structure(
        "pickup_dispatch", "battle", "原生拾取分派表",
        PICKUP_DISPATCH_BASE, 4,
        [F("handler", 0, 4, "ptr", "处理程序", "7 个拾取处理程序", "分派")],
        (PICKUP_DISPATCH_BASE + i * 4 for i in range(PICKUP_DISPATCH_COUNT)),
        rom,
        note="7 个拾取处理程序指针。",
        primary_columns=["handler"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    for table_id, base, count, label in (
        ("data_pointer_table_a", DATA_POINTER_A_BASE, DATA_POINTER_A_COUNT, "数据指针表 A"),
        ("data_pointer_table_b", DATA_POINTER_B_BASE, DATA_POINTER_B_COUNT, "数据指针表 B"),
    ):
        out.append(make_structure(
            table_id, "assets", label,
            base, 4,
            [F("ptr", 0, 4, "ptr", "指针", "", "指针")],
            (base + i * 4 for i in range(count)),
            rom,
            note=f"{count} 项 u32 指针表；指向的资源本体不在本表里。",
            primary_columns=["ptr"],
            verification="L1 结构已证明 / 尚无写回路径",
        ))

    asset_fields = [
        F("head", 0x00, 12, "hex", "头部", "未解码的 12 字节", "资源记录"),
    ]
    for t in range(6):
        asset_fields.append(F(f"tile_ptr_{t}", 0x0C + t * 4, 4, "ptr",
                               f"图块指针{t}", "", "图块"))
    asset_fields.append(F("mid", 0x24, 4, "hex", "中间字段", "未解码", "资源记录"))
    for s in range(3):
        asset_fields.append(F(f"script_ptr_{s}", 0x28 + s * 4, 4, "ptr",
                               f"脚本指针{s}", "", "脚本"))
    out.append(make_structure(
        "tile_asset_records", "assets", "图块/精灵资源记录表",
        TILE_ASSET_RECORDS_BASE, TILE_ASSET_RECORDS_STRIDE, asset_fields,
        (TILE_ASSET_RECORDS_BASE + i * TILE_ASSET_RECORDS_STRIDE
         for i in range(TILE_ASSET_RECORDS_COUNT)),
        rom,
        note="79 条 × 68 字节：6 个图块指针 + 3 个脚本指针，其余未解码。",
        primary_columns=["tile_ptr_0", "script_ptr_0"],
        verification="L1 结构已证明 / 尚无写回路径",
    ))

    return out


def build_text_tables(rom: bytes, mapping: dict[int, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    out.append(build_text_table(
        rom, mapping, "character_names", "characters", "人物名表",
        CHARACTER_NAMES_BASE, CHARACTER_NAMES_COUNT,
        note="63 个槽位：0 = 「无」占位，1..62 与角色定义表同号。",
        id_prefix="角色",
    ))
    out.append(build_text_table(
        rom, mapping, "training_names", "characters", "技能名表",
        TRAINING_NAMES_BASE, TRAINING_NAMES_COUNT,
        note="45 个槽位，与角色特性表同空间。",
        id_prefix="技能",
    ))
    out.append(build_text_table(
        rom, mapping, "jutsu_names", "ninjutsu", "忍术名表",
        JUTSU_NAMES_BASE, JUTSU_NAMES_COUNT,
        note="87 个槽位，与忍术记录表同号。",
        id_prefix="忍术",
    ))
    out.append(build_text_table(
        rom, mapping, "ninjutsu_names", "items", "忍具名表",
        NINJUTSU_NAMES_BASE, NINJUTSU_NAMES_COUNT,
        note="94 个槽位（0 = 占位，1..93 = 名称），与道具记录表同号。",
        id_prefix="忍具",
    ))
    out.append(build_text_table(
        rom, mapping, "material_names", "items", "强化素材名表",
        MATERIAL_NAMES_BASE, MATERIAL_NAMES_COUNT,
        note="18 个槽位。",
        id_prefix="素材",
    ))

    for table_id, base, label in (
        ("mission_titles", MISSION_TITLE_BASE, "任务标题表"),
        ("mission_descriptions", MISSION_DESC_BASE, "任务说明表"),
        ("mission_hints", MISSION_HINT_BASE, "任务提示表"),
    ):
        out.append(build_text_table(
            rom, mapping, table_id, "route", label,
            base, MISSION_ENTRY_COUNT,
            note="每关 3 个子奖励文本。下标 = 任务索引表[关卡] + 子编号（0..2），"
                 "最大用到 111 号槽位，所以表长 112。",
            id_prefix="条目",
        ))

    out.append(build_text_table(
        rom, mapping, "dialogue_slots", "story", "对白槽位表",
        DIALOGUE_TABLE_BASE, DIALOGUE_SLOT_COUNT,
        note="游戏自己的对白指针表（0x461CE8）：1524 个槽位 = 305 组 × "
             "（4 条 + 1 个 NULL 分隔）。每组 4 条是「一道题 + 三个选项」。"
             "槽位号与组号不是一回事：第 g 组的 4 条落在槽 5g..5g+3。",
        id_prefix="槽",
    ))

    out.append(build_inline_text_table(
        rom, mapping, "speaker_names", "story", "说话人名表（内联）",
        SPEAKER_NAME_BASE, SPEAKER_NAME_COUNT, SPEAKER_NAME_STRIDE,
        note="剧情 VM 的 0x08 指令按 id 指向这张表：每条 12 字节，"
             "字形码直接写在里面（不是指针表）。记录总数尚未确证。\n"
             "**同一批字节还有第二种读法**：`tools/table_registry.py` 把它登记成"
             "「调色板源表」（每条 = 一个 u32 色值 + 8 字节 0，12 个原生读者）。"
             "两种读法描述的是同一片地址，按说话人名表呈现。",
    ))

    return out


def build_inline_text_table(
    rom: bytes,
    mapping: dict[int, str],
    table_id: str,
    module: str,
    label: str,
    base: int,
    count: int,
    stride: int,
    note: str = "",
) -> dict[str, Any]:
    """A table whose records hold the font codes *inline* (no pointer).

    The speaker-name table at 0x5A57C4 works this way: each record is a
    fixed-size slot with the codes written straight into it.
    """
    records = []
    for i in range(count):
        offset = base + i * stride
        raw = rom[offset:offset + stride]
        end = raw.find(b"\x00")
        if end < 0:
            end = len(raw)
        text = decode_text(raw[:end], mapping)
        records.append({
            "id": i,
            "label": f"说话人{i}",
            "pointer_offset": None,
            "pointer": None,
            "text_offset": offset,
            "capacity": stride,
            "text": text,
            "original_text": text,
            "raw": b64(raw),
        })
    return {
        "id": table_id,
        "module": module,
        "label": label,
        "pointer_table_offset": None,
        "count": count,
        "relocatable": False,
        "nul_terminated": True,
        "inline_records": True,
        "note": note,
        "records": records,
    }


def build_scripts(rom: bytes) -> list[dict[str, Any]]:
    """Decode the story VM scripts and expose the editable parts.

    The **route** (剧情路线) does not live in a table — it lives inside the
    scripts, as the "next scene" instructions `0x16` (48 处) and `0x1A`
    (15 处).  The **in-battle story** lives in the `logic` / `events` scripts,
    where `0x1E` (载入地图), `0x1F` (子配置) and `0x23` (队员) decide what a
    battle scene loads and who joins.

    All of those operands are **fixed width**, so rewriting them in place
    cannot move a byte and therefore cannot invalidate the scripts' branch
    targets.  That is exactly the constraint the repo's own write-back path
    (`tools/import_story_script.py`) works under, and this dump reuses its
    scanner so the two never disagree.

    `0x22`（把角色加入战斗配置）is included as raw bytes only: the three
    operand bytes' individual meanings are not pinned down, so the editor
    shows them as bytes rather than inventing field names.
    """
    from tools import import_story_script as iss

    roots = {
        "before": (STORY_BEFORE_ROOT, 55),
        "after": (STORY_AFTER_ROOT, 55),
        "logic": (STORY_LOGIC_ROOT, 46),
        "events": (STORY_EVENTS_ROOT, 46),
    }
    # op → operand name → (offset inside the instruction, size)
    wanted = {
        0x16: {"scene": (1, 1)},
        0x1A: {"scene": (1, 1), "flag": (2, 1)},
        0x1E: {"map": (1, 1)},
        0x1F: {"config": (1, 1)},
        0x23: {"member_a": (1, 1), "member_b": (2, 1)},
    }
    labels = {
        "scene": "下一场景 id",
        "flag": "相位标志",
        "map": "地图 id",
        "config": "子配置 id",
        "member_a": "队员 A",
        "member_b": "队员 B",
    }
    out: list[dict[str, Any]] = []
    for name, (base, max_scene) in roots.items():
        for scene in range(1, max_scene + 1):
            slot = base + scene * 4
            ptr = struct.unpack_from("<I", rom, slot)[0]
            if not ptr:
                continue
            root = ptr - ROM_BASE
            if not (0 <= root < len(rom)):
                continue
            try:
                nodes = iss.scan_script(rom, root)
            except Exception:  # noqa: BLE001 - a broken script must not stop the export
                continue

            route: list[dict[str, Any]] = []
            operands: list[dict[str, Any]] = []
            for node in nodes:
                op = node["op"]
                if op in wanted:
                    for field, (delta, size) in wanted[op].items():
                        at = node["offset"] + delta
                        value = rom[at] if size == 1 else struct.unpack_from("<H", rom, at)[0]
                        operands.append({
                            "name": field,
                            "label": labels[field],
                            "rom_offset": at,
                            "size": size,
                            "value": value,
                            "before_hex": rom[at:at + size].hex(),
                            "opcode": op,
                        })
                    if op in (0x16, 0x1A):
                        route.append({
                            "op": op,
                            "rom_offset": node["offset"],
                            "scene_rom_offset": node["offset"] + 1,
                            "scene": rom[node["offset"] + 1],
                            "flag": rom[node["offset"] + 2] if op == 0x1A else None,
                            "kind": "cursor" if op == 0x1A else "after",
                        })
                elif op == 0x22:
                    # 把角色加入战斗配置：3 个操作数字节，含义未钉死，按原始字节呈现
                    at = node["offset"] + 1
                    operands.append({
                        "name": "raw",
                        "label": "把角色加入战斗配置（3 字节，字段含义未钉死）",
                        "rom_offset": at,
                        "size": 3,
                        "value": rom[at:at + 3].hex(),
                        "before_hex": rom[at:at + 3].hex(),
                        "opcode": op,
                    })
            out.append({
                "id": f"{name}.{scene}",
                "root": name,
                "scene": scene,
                "script_offset": root,
                "pointer_slot": slot,
                "instruction_count": len(nodes),
                "route": route,
                "operands": operands,
            })
    return out


def build_dominant_text_index(rom: bytes, mapping: dict[int, str],
                               limit: int = 20000) -> dict[str, Any]:
    """Every font-coded string in the cartridge, found with the ROM's own font.

    This is the editor's safety net: whatever the named tables miss, the
    author can still find and edit it here.
    """
    def is_text(seg: bytes) -> bool:
        j = 0
        while j < len(seg):
            b = seg[j]
            if b == 1:
                j += 2
                continue
            if b == 2:
                j += 3
                continue
            if 0x80 <= b <= 0x9F:
                if j + 1 >= len(seg):
                    return False
                if ((b << 8) | seg[j + 1]) not in mapping:
                    return False
                j += 2
                continue
            if b < 0x20 or b > 0x7E:
                return False
            j += 1
        return True

    records = []
    i = 0
    n = len(rom)
    while i < n and len(records) < limit:
        if rom[i] == 0:
            i += 1
            continue
        s = i
        while i < n and rom[i] != 0:
            i += 1
        seg = rom[s:i]
        if len(seg) < 2 or not is_text(seg):
            continue
        text = decode_text(seg, mapping)
        if len(text) < 1:
            continue
        records.append({
            "id": len(records),
            "label": f"0x{s:06X}",
            "pointer_offset": None,
            "pointer": None,
            "text_offset": s,
            "capacity": len(seg) + 1,
            "text": text,
            "original_text": text,
            "raw": b64(seg),
        })

    return {
        "id": "rom_text_index",
        "module": "story",
        "label": "全 ROM 文本索引",
        "pointer_table_offset": None,
        "count": len(records),
        "relocatable": False,
        "nul_terminated": True,
        "note": "用 ROM 自带的字库扫描全卡带得到的所有字符串。"
                "这些字符串被代码里的绝对地址引用，**不能改变长度**；"
                "变长请改用「对白槽位表」等指针表驱动的文本表。",
        "records": records,
    }


def build_pack(rom_path: Path, with_text_index: bool = True) -> dict[str, Any]:
    rom = rom_path.read_bytes()
    mapping, report = text_codec.load_mapping(rom_path)

    structures = build_structures(rom, mapping)
    texts = build_text_tables(rom, mapping)
    if with_text_index:
        texts.append(build_dominant_text_index(rom, mapping))

    # The encoder must emit the *canonical* code for a character: eight
    # characters are spelled by two codes and only the base-run spelling is
    # canonical (tools/text_codec.py::build_canonical_reverse_mapping).
    reverse, reverse_report = text_codec.build_canonical_reverse_mapping(mapping)

    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "generated": None,
        "rom": {
            "name": rom_path.name,
            "size": len(rom),
            "sha256": hashlib.sha256(rom).hexdigest(),
        },
        "font": {
            "code_to_char": {
                f"{code:04X}": ch for code, ch in sorted(mapping.items())
            },
            "char_to_code": {
                ch: f"{code:04X}" for ch, code in sorted(reverse.items())
            },
            "coverage": report.get("catalog_segments_matched"),
            "segments_total": report.get("catalog_segments_total"),
            "duplicate_characters": reverse_report.get("duplicate_characters"),
        },
        "structures": structures,
        "texts": texts,
        "scripts": build_scripts(rom),
        "patches": [],
        "notes": [
            "本包由 tools/export_content_pack.py 从 rom/base.gba 导出。",
            "每个结构的字段列表精确铺满整条记录，未解码的字节以 hex 字段原样保留。",
            "文本表分两类：指针表驱动（可重定位、可变长）与绝对地址引用（只能等长改写）。",
        ],
    }


# ---------------------------------------------------------------------------
# Portrait assets: export, write-back, round-trip self-check
# ---------------------------------------------------------------------------
#
# Layout (all proved by the native consumer at 0x08096138):
#
#   portrait table   0x085A4DEC + id*40 + expr*8  -> (gfx ptr, palette ptr)
#   gfx              LZ77 stream (GBA BIOS Lz77UnCompWram, `svc #0x11` at
#                    0x0809C0EC) -> exactly 6400 bytes = 80x80 at 8bpp
#   palette          128 raw bytes = 64 BGR555 colours
#
# The graphics are compressed, so a write-back has to fit inside the bytes
# the ROM already reserved for that portrait: the distance from the LZ77
# stream to the next asset.  `portrait_budget()` measures it.

PORTRAIT_TABLE_BASE = 0x5A4DEC
PORTRAIT_ROW_STRIDE = 40
PORTRAIT_EXPR_STRIDE = 8
PORTRAIT_EXPR_COUNT = 5
PORTRAIT_ROWS = 64
PORTRAIT_PALETTE_BYTES = 128
PORTRAIT_GRAPHICS_BYTES = 6400

LZ77_MAX_MATCH = 18      # the format stores length-3 in 4 bits
LZ77_MAX_DISTANCE = 4096  # the format stores distance-1 in 12 bits


def _lz77_match(data: bytes, buckets: dict[int, list[int]], pos: int,
                total: int, best_only: bool) -> tuple[int, int]:
    """Longest (or nearest) match for `pos`; returns (length, distance)."""
    limit = min(LZ77_MAX_MATCH, total - pos)
    if limit < 3:
        return 0, 0
    key = data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16)
    floor = pos - LZ77_MAX_DISTANCE
    best_len = 0
    best_distance = 0
    for candidate in reversed(buckets.get(key, ())):
        if candidate < floor:
            break
        length = 3
        while length < limit and data[candidate + length] == data[pos + length]:
            length += 1
        if length > best_len:
            best_len = length
            best_distance = pos - candidate
            if best_len == limit:
                break
            if not best_only:
                break        # nearest match wins
    return best_len, best_distance


def _lz77_encode(data: bytes, nearest: bool, lazy: bool) -> bytes:
    """One LZ77 encoding strategy."""
    out = bytearray(b"\x10")
    out += len(data).to_bytes(3, "little")
    total = len(data)
    buckets: dict[int, list[int]] = {}
    pos = 0
    while pos < total:
        flags = 0
        tokens = bytearray()
        for bit in range(8):
            if pos >= total:
                break
            consumed = pos
            length, distance = _lz77_match(data, buckets, pos, total, not nearest)
            if length >= 3 and lazy and pos + 1 < total:
                ahead_len, ahead_dist = _lz77_match(data, buckets, pos + 1,
                                                     total, False)
                if ahead_len > length:
                    length = 0            # defer: emit a literal instead
            if length >= 3:
                flags |= 1 << (7 - bit)
                packed = distance - 1
                tokens.append(((length - 3) << 4) | (packed >> 8))
                tokens.append(packed & 0xFF)
                pos += length
            else:
                tokens.append(data[pos])
                pos += 1
            for index in range(consumed, pos):
                if index + 3 <= total:
                    key = (data[index] | (data[index + 1] << 8)
                           | (data[index + 2] << 16))
                    bucket = buckets.setdefault(key, [])
                    bucket.append(index)
                    if len(bucket) > 2048:
                        del bucket[:-2048]
        out.append(flags)
        out += tokens
    return bytes(out)


def lz77_compress(data: bytes) -> bytes:
    """Encode `data` as a GBA LZ77 stream with back-references.

    The format is the one `tools/lib/lz77.py` decodes: a 4-byte header
    (``0x10`` + 24-bit decompressed size), then groups of one flag byte and
    up to eight tokens, the flag bits consumed **MSB first**.  A literal is
    one byte; a back-reference is two bytes
    ``b0 = (len-3) << 4 | (distance-1) >> 8`` and ``b1 = (distance-1) & 0xFF``
    with ``len`` in 3..18 and ``distance`` in 1..4096.

    `tools/lib/lz77.py` only ships a literal-only encoder, which is 7200
    bytes for a portrait - far too big to write back in place.

    Three strategies (longest match / nearest match / lazy matching) are
    tried and the smallest result wins, because a write-back only fits when
    the new stream is no longer than the one the ROM already reserves.
    """
    if len(data) >= 0x1000000:
        raise ValueError("LZ77 payload too large for a 24-bit size field")
    best = b""
    for nearest, lazy in ((False, False), (True, False), (False, True)):
        candidate = _lz77_encode(data, nearest, lazy)
        if not best or len(candidate) < len(best):
            best = candidate
    return best


def portrait_entries(rom: bytes) -> list[dict[str, Any]]:
    """Every (id, expression) row of the portrait table with valid pointers."""
    entries = []
    for portrait_id in range(PORTRAIT_ROWS):
        for expression in range(PORTRAIT_EXPR_COUNT):
            offset = (PORTRAIT_TABLE_BASE + portrait_id * PORTRAIT_ROW_STRIDE
                      + expression * PORTRAIT_EXPR_STRIDE)
            gfx, palette = struct.unpack_from("<II", rom, offset)
            if not (ROM_BASE <= gfx < ROM_BASE + len(rom)):
                continue
            if not (ROM_BASE <= palette < ROM_BASE + len(rom)):
                continue
            if rom[gfx - ROM_BASE] != 0x10:
                continue
            entries.append({
                "id": portrait_id,
                "expression": expression,
                "table_offset": offset,
                "gfx_ptr": gfx,
                "gfx_offset": gfx - ROM_BASE,
                "palette_ptr": palette,
                "palette_offset": palette - ROM_BASE,
            })
    return entries


def portrait_budget(rom: bytes, entries: list[dict[str, Any]]) -> dict[int, int]:
    """Bytes available for each portrait's LZ77 stream.

    The stream may not run into the next asset, so the budget is the
    distance from the stream's start to the next asset address.
    """
    addresses = sorted({entry["gfx_offset"] for entry in entries}
                       | {entry["palette_offset"] for entry in entries})
    budget: dict[int, int] = {}
    for index, address in enumerate(addresses):
        limit = (addresses[index + 1] if index + 1 < len(addresses)
                 else len(rom))
        budget[address] = limit - address
    return budget


def portrait_assets(rom: bytes, entries: list[dict[str, Any]],
                     budget: dict[int, int]) -> list[dict[str, Any]]:
    """Export every portrait: decompressed graphics + raw palette."""
    from tools.lib import lz77

    out = []
    for entry in entries:
        graphics = lz77.decompress(rom, entry["gfx_offset"])
        if len(graphics) != PORTRAIT_GRAPHICS_BYTES:
            raise ValueError(
                "portrait %d/%d decompresses to %d bytes, expected %d"
                % (entry["id"], entry["expression"], len(graphics),
                   PORTRAIT_GRAPHICS_BYTES))
        palette = rom[entry["palette_offset"]:
                      entry["palette_offset"] + PORTRAIT_PALETTE_BYTES]
        out.append({
            **entry,
            "graphics": graphics,
            "palette": palette,
            "budget": budget.get(entry["gfx_offset"], 0),
        })
    return out


def import_portrait(rom: bytes, entry: dict[str, Any], graphics: bytes,
                    palette: bytes, budget: int) -> tuple[bytes, list[tuple[int, int]]]:
    """Write one portrait back into `rom`.

    Returns the patched ROM and the list of byte ranges that were changed.
    Only two ranges may change: the LZ77 stream that was written and the
    palette block.  Everything else is copied verbatim.
    """
    if len(graphics) != PORTRAIT_GRAPHICS_BYTES:
        raise ValueError("portrait graphics must be %d bytes"
                         % PORTRAIT_GRAPHICS_BYTES)
    if len(palette) != PORTRAIT_PALETTE_BYTES:
        raise ValueError("portrait palette must be %d bytes"
                         % PORTRAIT_PALETTE_BYTES)
    stream = lz77_compress(graphics)
    if len(stream) > budget:
        raise ValueError(
            "compressed portrait is %d bytes but only %d are available"
            % (len(stream), budget))
    patched = bytearray(rom)
    patched[entry["gfx_offset"]:entry["gfx_offset"] + len(stream)] = stream
    patched[entry["palette_offset"]:
            entry["palette_offset"] + PORTRAIT_PALETTE_BYTES] = palette
    changed = [
        (entry["gfx_offset"], entry["gfx_offset"] + len(stream)),
        (entry["palette_offset"],
         entry["palette_offset"] + PORTRAIT_PALETTE_BYTES),
    ]
    return bytes(patched), changed


def verify_portrait_roundtrip(rom: bytes) -> tuple[int, list[str]]:
    """Prove the portrait write-back is lossless and non-destructive.

    For every live portrait:
      1. export the decompressed graphics and the palette;
      2. write them straight back;
      3. export again - the result must equal the first export;
      4. every byte outside the two written ranges must be untouched.

    Returns ``(checked, problems)``.
    """
    from tools.lib import lz77

    entries = portrait_entries(rom)
    budget = portrait_budget(rom, entries)
    problems: list[str] = []
    checked = 0
    for entry in entries:
        graphics = lz77.decompress(rom, entry["gfx_offset"])
        palette = rom[entry["palette_offset"]:
                      entry["palette_offset"] + PORTRAIT_PALETTE_BYTES]
        try:
            patched, changed = import_portrait(rom, entry, graphics, palette,
                                               budget[entry["gfx_offset"]])
        except ValueError as exc:
            problems.append("portrait %d/%d: %s" % (entry["id"],
                                                     entry["expression"], exc))
            continue
        checked += 1
        # 3. re-export
        again = lz77.decompress(patched, entry["gfx_offset"])
        if again != graphics:
            problems.append("portrait %d/%d: graphics do not survive the round trip"
                            % (entry["id"], entry["expression"]))
        again_palette = patched[entry["palette_offset"]:
                                entry["palette_offset"] + PORTRAIT_PALETTE_BYTES]
        if again_palette != palette:
            problems.append("portrait %d/%d: palette does not survive the round trip"
                            % (entry["id"], entry["expression"]))
        # 4. nothing else may move
        outside = _bytes_outside(rom, patched, changed)
        if outside is not None:
            problems.append("portrait %d/%d: byte 0x%06X changed outside the "
                            "declared fields" % (entry["id"],
                                                entry["expression"], outside))
    return checked, problems


def _bytes_outside(original: bytes, patched: bytes,
                   changed: list[tuple[int, int]]) -> int | None:
    """First byte that differs outside `changed`, or None."""
    cursor = 0
    for start, end in sorted(changed):
        if start > cursor and original[cursor:start] != patched[cursor:start]:
            for index in range(cursor, start):
                if original[index] != patched[index]:
                    return index
        cursor = max(cursor, end)
    if cursor < len(original) and original[cursor:] != patched[cursor:]:
        for index in range(cursor, len(original)):
            if original[index] != patched[index]:
                return index
    return None


def export_portrait_assets(rom: bytes, out_dir: Path) -> dict[str, Any]:
    """Write every portrait's graphics and palette into `out_dir`."""
    entries = portrait_entries(rom)
    budget = portrait_budget(rom, entries)
    assets = portrait_assets(rom, entries, budget)
    # Some graphics streams are shared by several portraits: writing one of
    # them changes every sharer, so the index has to say so.
    sharers: dict[int, list[dict[str, int]]] = {}
    for asset in assets:
        sharers.setdefault(asset["gfx_offset"], []).append(
            {"id": asset["id"], "expression": asset["expression"]})
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for asset in assets:
        stem = "portrait_%02d_expr%d" % (asset["id"], asset["expression"])
        (out_dir / (stem + ".gfx.bin")).write_bytes(asset["graphics"])
        (out_dir / (stem + ".pal.bin")).write_bytes(asset["palette"])
        index.append({
            "id": asset["id"],
            "expression": asset["expression"],
            "graphics_file": stem + ".gfx.bin",
            "palette_file": stem + ".pal.bin",
            "gfx_ptr": "0x%08X" % asset["gfx_ptr"],
            "palette_ptr": "0x%08X" % asset["palette_ptr"],
            "graphics_bytes": len(asset["graphics"]),
            "palette_bytes": len(asset["palette"]),
            "compressed_budget": asset["budget"],
            "shared_graphics_with": sharers[asset["gfx_offset"]],
        })
    payload = {
        "format": "naruto-konoha-portrait-assets",
        "version": 1,
        "note": "同一份图形可能被多个表情共用（见 shared_graphics_with），"
                "改一处会同时改掉所有共用者。",
        "portraits": index,
    }
    write_text(out_dir / "portrait-index.json",
               json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    return payload


def write_gzip(path: Path, data: bytes) -> None:
    """Write a deterministic gzip file (no timestamp, so the digest is stable)."""
    import gzip
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=handle, mtime=0) as gz:
            gz.write(data)


BASE_ROM_CHUNK_BYTES = 262_144


def write_base_rom_module(rom_path: Path, out_dir: Path) -> tuple[int, int]:
    """Write the base ROM next to the editor, gzip-compressed.

    The editor folder alone is then enough to rebuild the original ROM: the
    content pack carries every editable structure's content, and this file is
    the canvas it is written into.

    It is stored compressed because browsers cap how much a single page may
    download (measured: ~6.3 MB in the desktop FilePanel browser, which the
    bare 6,291,456-byte ROM already exceeds once the content pack is added).
    The ROM compresses to ~43 %, and the browser decompresses it natively with
    DecompressionStream — no base64, no giant strings.
    """
    rom = rom_path.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in list(out_dir.glob("part-*.bin.gz")) + list(out_dir.glob("manifest.json")):
        stale.unlink()
    target = out_dir / "base-rom.bin.gz"
    write_gzip(target, rom)
    return len(rom), target.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the ROM content pack.")
    parser.add_argument("--rom", type=Path, default=REPO / "rom" / "base.gba")
    parser.add_argument("--out", type=Path,
                        default=REPO / "rom-editor" / "content" / "pack.json")
    parser.add_argument("--rom-out", type=Path,
                        default=REPO / "rom-editor" / "content" / "base-rom",
                        help="directory for the base64 base-ROM chunks")
    parser.add_argument("--no-rom", action="store_true",
                        help="skip writing the base ROM chunks")
    parser.add_argument("--text-index-out", type=Path,
                        default=REPO / "rom-editor" / "content" / "text-index.json",
                        help="where to write the exhaustive ROM text index")
    parser.add_argument("--no-text-index", action="store_true",
                        help="do not write the separate text index file")
    parser.add_argument("--check", action="store_true",
                        help="only verify the pack on disk matches the ROM")
    parser.add_argument("--portrait-out", type=Path, default=None,
                        help="export every portrait's graphics and palette here")
    parser.add_argument("--portrait-self-test", action="store_true",
                        help="prove the portrait write-back is lossless")
    parser.add_argument("--portrait-write", type=int, default=None,
                        metavar="ID", help="portrait id for --portrait-write")
    parser.add_argument("--portrait-expression", type=int, default=0,
                        help="expression index for --portrait-write")
    parser.add_argument("--portrait-graphics", type=Path, default=None,
                        help="6400-byte raw graphics file for --portrait-write")
    parser.add_argument("--portrait-palette", type=Path, default=None,
                        help="128-byte raw palette file for --portrait-write")
    parser.add_argument("--portrait-rom-out", type=Path, default=None,
                        help="write the patched ROM here (never touches rom/base.gba)")
    args = parser.parse_args(argv)

    if args.portrait_self_test:
        rom = args.rom.read_bytes()
        checked, problems = verify_portrait_roundtrip(rom)
        print("portrait self-test: %d portraits round-tripped" % checked)
        for problem in problems[:20]:
            print("FAIL:", problem)
        if problems:
            print("%d problem(s)" % len(problems))
            return 1
        print("PORTRAIT SELF-TEST: PASS")
        return 0

    if args.portrait_out is not None:
        rom = args.rom.read_bytes()
        payload = export_portrait_assets(rom, args.portrait_out)
        print(f"已导出头像素材: {args.portrait_out} "
              f"({len(payload['portraits'])} 个表情)")
        return 0

    if args.portrait_write is not None:
        if not (args.portrait_graphics and args.portrait_palette
                and args.portrait_rom_out):
            print("Error: --portrait-write needs --portrait-graphics, "
                  "--portrait-palette and --portrait-rom-out", file=sys.stderr)
            return 1
        rom = args.rom.read_bytes()
        entries = portrait_entries(rom)
        budget = portrait_budget(rom, entries)
        match = [e for e in entries
                 if e["id"] == args.portrait_write
                 and e["expression"] == args.portrait_expression]
        if not match:
            print(f"Error: portrait {args.portrait_write}/"
                  f"{args.portrait_expression} has no assets", file=sys.stderr)
            return 1
        entry = match[0]
        graphics = args.portrait_graphics.read_bytes()
        palette = args.portrait_palette.read_bytes()
        patched, changed = import_portrait(rom, entry, graphics, palette,
                                           budget[entry["gfx_offset"]])
        # the bytes outside the declared fields must be untouched
        outside = _bytes_outside(rom, patched, changed)
        if outside is not None:
            print(f"FAIL: byte 0x{outside:06X} changed outside the declared fields",
                  file=sys.stderr)
            return 1
        args.portrait_rom_out.parent.mkdir(parents=True, exist_ok=True)
        args.portrait_rom_out.write_bytes(patched)
        changed_bytes = sum(end - start for start, end in changed)
        print(f"已写回头像 {args.portrait_write}/{args.portrait_expression} -> "
              f"{args.portrait_rom_out}（声明字段共 {changed_bytes} 字节）")
        sharers = [(e["id"], e["expression"]) for e in entries
                    if e["gfx_offset"] == entry["gfx_offset"]
                    and (e["id"], e["expression"])
                    != (args.portrait_write, args.portrait_expression)]
        if sharers:
            print("  注意：这份图形同时被以下表情共用，它们也一起变了：%s"
                  % ", ".join("%d/%d" % item for item in sharers))
        return 0

    pack = build_pack(args.rom, with_text_index=False)
    payload = json.dumps(pack, ensure_ascii=False, indent=1)

    if args.check:
        if not args.out.exists():
            print(f"FAIL: {args.out} 不存在")
            return 1
        current = args.out.read_text(encoding="utf-8")
        import re
        strip = lambda s: re.sub(r'"generated": "[^"]*"', '"generated": null', s)
        if strip(current) != payload:
            print("FAIL: 内容包与 ROM 不一致，需要重新导出")
            return 1
        print("OK: 内容包与 ROM 一致")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_text(args.out, payload)
    # A gzipped compact copy for the browser: the pack is mostly repetitive
    # JSON and shrinks ~14x, and browsers cap how much a single page may
    # download (measured: ~6–10 MB in the desktop FilePanel browser, and the
    # base ROM alone is 6.3 MB, so the pack has to be as small as possible).
    compact = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
    min_path = args.out.with_name("pack.min.json")
    write_gzip(min_path.with_suffix(".json.gz"), compact.encode("utf-8"))
    size = args.out.stat().st_size
    print(f"已导出内容包: {args.out} ({size:,} 字节)")
    print(f"  浏览器用: {min_path.with_suffix('.json.gz')} "
          f"({min_path.with_suffix('.json.gz').stat().st_size:,} 字节 gzip，"
          f"解压后 {len(compact.encode()):,} 字节)")
    print(f"  结构 {len(pack['structures'])} 个 / "
          f"记录 {sum(s['entry_count'] for s in pack['structures']):,} 条")
    print(f"  文本表 {len(pack['texts'])} 个 / "
          f"文本 {sum(t['count'] for t in pack['texts']):,} 条")
    print(f"  字形码 {len(pack['font']['code_to_char']):,} 个")
    if not args.no_rom:
        rom_size, packed_size = write_base_rom_module(args.rom, args.rom_out)
        print(f"已导出原版 ROM: {args.rom_out / 'base-rom.bin.gz'} "
              f"({rom_size:,} 字节 → {packed_size:,} 字节 gzip)")
    if not args.no_text_index:
        index_pack = build_pack(args.rom, with_text_index=True)
        index_table = index_pack["texts"][-1]
        args.text_index_out.parent.mkdir(parents=True, exist_ok=True)
        index_payload = json.dumps(index_table, ensure_ascii=False, indent=1)
        write_gzip(args.text_index_out.with_suffix(".json.gz"),
                   index_payload.encode("utf-8"))
        print(f"已导出全 ROM 文本索引: {args.text_index_out.with_suffix('.json.gz')} "
              f"({index_table['count']:,} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
