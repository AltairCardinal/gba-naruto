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
import pathlib
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
# WRAM 分配表（legacy bank "save-state"）：10 组 {u32 wram_addr, u32 alloc_size}。
# 存档数据本身在 SRAM，不在 ROM —— 这张表只管「每个子系统分到多少 EWRAM」。
WRAM_ALLOC_BASE = 0x53D848
WRAM_ALLOC_COUNT = 10
WRAM_ALLOC_STRIDE = 8
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

# ---------------------------------------------------------------------------
# 取值域（界面据此把裸数字渲染成带名字的下拉）
# ---------------------------------------------------------------------------
# 胜负条件类型。语义见 notes/battle-tables.md §1.1（原版说明文字）
# 与 §1.1.1（类型 2 / 3 的原生断点定案）。
CONDITION_TYPE_ENUMS = {
    1: "全灭敌方（a=1）/ 我方全灭（a=0）",
    2: "回合用尽（原生不读 a/b）",
    3: "指定角色已离场（a=阵营, b=角色 id）",
    6: "获得指定道具（a=道具序号）",
    7: "剩余体力比较（a=阵营）",
    8: "击杀数比较（a=阵营）",
    9: "收集物数量比较（a=阵营）",
}

# 战场物件类型。来源 notes/external-konoha-workshop-gap-20261020.md:178。
OBJECT_TYPE_ENUMS = {
    0: "空",
    1: "忍具",
    2: "强化素材",
    3: "专属修行卷轴",
    4: "认识卡",
    5: "机关宝箱",
    6: "特殊机关",
    7: "剧情物件",
}

# 奖励类别。来源 notes/reward-and-rules-semantics-20261020.md §3.1；
# 类别 → 名字表的对应由 ROM 自带的 4 槽指针表 0x0859F5E0 证明。
REWARD_CATEGORY_ENUMS = {
    0: "忍具",
    1: "强化素材",
    2: "认识卡",
    3: "技术",
}
REWARD_CATEGORY_TABLES = {
    "0": "ninjutsu_names",
    "1": "material_names",
    "2": "character_names",
    "3": "training_names",
}
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
# m4a SongHeader：8 字节头 + track_count × 4 字节轨道指针。
#
# 描述符**不再硬编码**：sound-ID 表里出现过的每一个描述符地址都被导出成一张
# 结构（notes/audio-ux-redesign-20261021.md §1.1：159 条音效指向 81 个不同
# 地址 = 80 个真实描述符 + 79 个音效共用的空哨兵）。
AUDIO_EMPTY_DESCRIPTOR = 0x08466068   # 空哨兵（0 轨 = 没有声音）
AUDIO_SONG_EMPTY_ID = "audio_song_empty"
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
      item: str | None = None,
      enum: dict[int, str] | None = None,
      relation: dict[str, str] | None = None,
      not_read: bool = False,
      bits: list[dict[str, Any]] | None = None,
      ptr_kind: str | None = None,
      param_meanings: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
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
    if enum:
        # 取值域 → 标签。界面据此渲染下拉，而不是让作者面对裸数字。
        field["enum"] = {str(k): v for k, v in enum.items()}
    if relation:
        # 该字段是一个 id，指向另一张表的同号槽位（界面据此显示名字并可跳转）。
        field["relation"] = relation
    if not_read:
        # 原生代码**不读**这个字节：界面把它降级为只读并说明，
        # 否则作者会白改一个没人读的字段。
        field["not_read"] = True
    if bits:
        # 位域里的若干位（其余位原样保留）。
        field["bits"] = bits
    if ptr_kind:
        # 这个指针指向的是**代码**（处理程序 / 剧本入口），不是数据载荷。
        # 界面上不能对代码指针说「未压缩原始数据」——那是数据载荷的说法。
        field["ptr_kind"] = ptr_kind
    if param_meanings:
        # 这个字段的取值决定了同一条记录里其它字段的含义
        # （例如条件类型 1/2/3 的 a/b 各自代表什么）。
        field["param_meanings"] = param_meanings
    return field


# 复合下标的分解方案：记录 id 按 parts **从外到内**分解（外层是高位）。
# 界面据此把「第 12 关 · 变体 1 · 槽 3」渲染出来，作者不用自己手算 id。
INDEX_SCHEMES = {
    "battle_actors": {
        "parts": [
            {"key": "stage", "label": "关卡 id", "count": 47, "text": "第 {stage} 关"},
            {"key": "variant", "label": "变体", "count": 3, "text": "变体 {variant}"},
            {"key": "slot", "label": "槽位", "count": 12, "text": "槽 {slot}"},
        ],
    },
    "battle_map_objects": {
        "parts": [
            {"key": "stage", "label": "关卡 id", "count": 47, "text": "第 {stage} 关"},
            {"key": "variant", "label": "变体", "count": 3, "text": "变体 {variant}"},
            {"key": "object", "label": "物件号", "count": 16, "text": "物件 {object}"},
        ],
    },
    "battle_rules": {
        "parts": [
            {"key": "stage", "label": "关卡 id", "count": 47, "text": "第 {stage} 关"},
            {"key": "variant", "label": "变体", "count": 3, "text": "变体 {variant}"},
        ],
    },
    "sprite_action_table": {
        "parts": [
            {"key": "sprite", "label": "精灵 id", "count": 36, "text": "精灵 {sprite}"},
            {"key": "action", "label": "动作", "count": 16, "text": "动作 {action}"},
        ],
    },
}

# 「一条记录代表什么」——域首页的表清单里给作者看的人话。
IDENTITIES = {
    "map_table": "关卡 id（47 条）",
    "battle_actors": "关卡 × 变体 × 槽位（47×3×12）",
    "battle_map_objects": "关卡 × 变体 × 物件号（47×3×16）",
    "battle_rules": "关卡 × 变体（47×3）",
    "battle_encounter_records": "记录下标（24 条）",
    "unit_slot_remap": "记录下标（43 项）",
    "unit_delta_table": "记录下标（16 项）",
    "level_blocks": "记录下标（4 项）",
    "object_descriptors": "记录下标（86 条）",
    "sprite_action_table": "精灵 id × 动作（36×16）",
    "story_logic_root": "关卡 id（47 条）",
    "story_events_root": "关卡 id（47 条）",
    "battle_handler_table": "记录下标（256 条）",
    "sprite_frame_descriptors": "记录下标（15 条）",
    "pickup_dispatch": "记录下标（7 条）",
    "battle_objectives": "说明文字（219 条，被战斗目标按绝对地址引用）",
}

# 这些表的绝大多数记录是空的（全零），默认先把它们藏起来。
HIDE_EMPTY = {
    "battle_actors", "battle_map_objects", "battle_rules",
    "battle_handler_table", "sprite_action_table",
}

# 表与表之间的**同键对应**：同一件事在两张表里各记一份。
#
# 战斗的「四件套」就是这样：战场布置 map_table 是按关卡编号的，
# 角色出生点 / 战场物件 / 战斗目标按「关卡 × 变体 × 槽」编号，
# 但它们讲的是**同一关**。以前界面上这几张表互不相干，
# 作者在「战场物件」里改一个值，看不出它属于哪一关的哪一关卡。
#
# by = "stage"：按 index_scheme 里的关卡号对应（没有 index_scheme 的按记录下标）。
PEERS: dict[str, list[dict[str, Any]]] = {
    "battle_actors": [
        {"table": "map_table", "by": "stage", "label": "战场布置描述符"},
    ],
    "battle_map_objects": [
        {"table": "map_table", "by": "stage", "label": "战场布置描述符"},
    ],
    "battle_rules": [
        {"table": "map_table", "by": "stage", "label": "战场布置描述符"},
    ],
    "portrait_table": [
        {"table": "character_template", "by": "id", "label": "角色定义表"},
    ],
}


def load_consumer_readers() -> dict[int, list[str]]:
    """结构表 → 原生读者地址。

    证据来自：
      * `notes/evidence/consumer-readers-20261022.json` —— 用
        `tools/consumer_locate.py --all` 按**更正后的基址**重新扫全 ROM 得到的
        （旧的那份里有一批表还挂在作废的旧基址上，对不上）；
      * `notes/evidence/consumer-evidence.json` —— 早期那份，补漏。

    **按文件偏移对上**，不按名字 —— 那两个文件里的表名有一批是旧名，
    按名字对会认错表。
    """
    global _CONSUMER_READERS
    if _CONSUMER_READERS is not None:
        return _CONSUMER_READERS
    _CONSUMER_READERS = {}
    here = pathlib.Path(__file__).resolve().parent.parent
    files = [
        here / "notes" / "evidence" / "consumer-readers-20261022.json",
        here / "notes" / "evidence" / "consumer-evidence.json",
    ]
    for path in files:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for info in _evidence_tables(data):
            try:
                offset = int(str(info.get("file_offset", "0x0")), 16)
            except ValueError:
                continue
            readers = sorted({
                c.get("reader") or c.get("reader_addr")
                for c in info.get("consumers", [])
                if isinstance(c, dict) and (c.get("reader") or c.get("reader_addr"))
            })
            readers = [r for r in readers if r]
            if readers and offset not in _CONSUMER_READERS:
                _CONSUMER_READERS[offset] = readers
    return _CONSUMER_READERS


def _evidence_tables(data: dict[str, Any]) -> list[dict[str, Any]]:
    """两份证据文件的结构不一样：一份按偏移做键，一份是 targets 列表。"""
    tables = data.get("tables")
    if isinstance(tables, dict):
        return list(tables.values())
    targets = data.get("targets")
    if isinstance(targets, list):
        return targets
    return []


_CONSUMER_READERS: dict[int, list[str]] | None = None

# `notes/evidence/consumer-evidence.json` 里有几张表没收录
# （它们的基址是**指针**而不是字面量，扫字面量扫不到），
# 但仓库的审计笔记里有确切的读者地址。按出处写在这里。
DOCUMENTED_CONSUMERS: dict[str, list[str]] = {
    # notes/completion-audit-20261020.md「头像表 + 拼块表」行：
    # 拼块表的地址是指针，存放在静态描述符 0x0846443C 的首字，
    # 而该描述符被这 7 处原生代码加载。
    "portrait_pieces": ["0x08077D12", "0x08089B06", "0x0808B356", "0x08091036",
                        "0x08091680", "0x08093846", "0x08096618"],
    # notes/completion-audit-20261020.md「精灵帧描述符表」行：3 个原生读者。
    "sprite_frame_descriptors": ["0x080806BA", "0x0808077E", "0x0808082E"],
    # notes/units-unsafe-table-fix-20260711.md 与
    # notes/evidence/units-offset-table-20261020.md：0x53F2EE 是独立的一张表，
    # 独立读者 0x08080AE0。
    "unit_delta_table": ["0x08080AE0"],
    # notes/dialogue-format.md：打开对白的运行时路径 0x080968A0（调用者 0x08096633）。
    "dialogue_slots": ["0x080968A0", "0x08096633"],
}


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
    # 原生读者：文本表也可能有（说话人名表就是被剧情 VM 读的）。
    readers = (load_consumer_readers().get(texts[0] if texts else -1)
                or DOCUMENTED_CONSUMERS.get(table_id))
    if readers:
        table["consumers"] = readers
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
    raw_only: bool = False,
    id_relation: dict[str, str] | None = None,
    consumers: list[str] | None = None,
    id_is_index: bool = False,
    ptr_relation: dict[str, Any] | None = None,
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
    if raw_only:
        # 这张表**一个已知字段都没有**：全是未解码的原始字节。界面据此
        # 只给一个十六进制编辑区，而不是 16 个一模一样的字段框。
        structure["raw_only"] = True
    if id_relation:
        # 记录下标本身就是一个 id，指向另一张表的同号槽位。
        structure["id_relation"] = id_relation
    if consumers:
        # 原生读者地址：改这张表会动到谁，界面直接写出来。
        structure["consumers"] = consumers
    else:
        # 没有显式给出就从证据文件里按文件偏移找。
        readers = load_consumer_readers().get(rom_offset)
        if not readers:
            readers = DOCUMENTED_CONSUMERS.get(structure_id)
        if readers:
            structure["consumers"] = readers
    if structure_id in PEERS:
        # 同一件事在另一张表里的对应记录（按关卡号对应）。
        structure["peers"] = PEERS[structure_id]
    if id_is_index:
        # 记录下标**本身就是 id**（音效 id、忍术 id…）。界面据此显示「id N」，
        # 而不是「第 N / M 条」那种 1 基计数 —— 音效 #0 就是音效 #0。
        structure["id_is_index"] = True
    if ptr_relation:
        # 指针型关系：这个字段存的是**地址**，而目标分散在多张表里
        # （音效描述符每个一条结构），所以这里给的是
        # 「地址 → 目标结构记录」的完整映射，界面据此生成下拉。
        structure["ptr_relation"] = ptr_relation
    if structure_id in INDEX_SCHEMES:
        # 复合下标的分解方案：界面据此把记录下标还原成
        # 「第 12 关 · 变体 1 · 槽 3」，作者不用自己手算 id。
        structure["index_scheme"] = INDEX_SCHEMES[structure_id]
    if structure_id in IDENTITIES:
        structure["identity"] = IDENTITIES[structure_id]
    if structure_id in HIDE_EMPTY:
        # 绝大多数记录是空的（全零），默认先藏起来。
        structure["hide_empty"] = True
    return structure


def character_template_fields() -> list[dict[str, Any]]:
    fields = [
        F("flag_00", 0x00, 1, "u8", "标志 00",
          "恒为 1；4 个消费者都不读它（notes/character-template-format-20261020.md 未解项 1）",
          "头部"),
        # 这六格以前叫「属性A~F」—— 界面上作者根本看不出是什么。
        # 仓库自己的指令级分析证明了它们进运行时实例的哪个偏移
        # （notes/character-template-format-20261020.md §2.2 的拷贝表），
        # 名字来自第三方逆向 notes/character-stats-addresses.md。
        # 两边的证据等级不同，所以标签写名字、说明写出处。
        F("stat_a", 0x01, 1, "u8", "攻击力",
          "运行时实例 +0x02。第三方逆向记作『攻击力』，仓库自己的指令级分析只证明它进实例 +0x02。上限 99",
          "基础属性"),
        F("stat_b", 0x02, 1, "u8", "防御力",
          "运行时实例 +0x03。第三方逆向记作『防御力』。上限 99",
          "基础属性"),
        F("stat_c", 0x03, 1, "u8", "敏捷度",
          "运行时实例 +0x04。第三方逆向记作『敏捷度』。上限 99",
          "基础属性"),
        F("stat_d", 0x04, 1, "u8", "移动力",
          "运行时实例 +0x05。第三方逆向记作『移动力』。上限 5",
          "基础属性"),
        F("stat_e", 0x05, 1, "u8", "忍具数",
          "运行时实例 +0x06。第三方逆向记作『忍具数』。上限 9",
          "基础属性"),
        F("stat_f", 0x06, 1, "u8", "查克拉",
          "运行时实例 +0x08。第三方逆向记作『查克拉』。上限 9",
          "基础属性"),
        F("flag_07", 0x07, 1, "u8", "标志 07",
          "恒为 0；4 个消费者都不读它（未解项 2）",
          "头部"),
        F("aux_stat", 0x08, 2, "u16", "副属性",
          "运行时实例 +0x0A，u16 整体拷贝。第三方逆向观察到它与手印数相同。上限 999",
          "基础属性"),
        F("hp_base", 0x0A, 2, "u16", "体力（HP）基础",
          "运行时实例 +0x0E = 体力上限；每级加 成长×(等级−1)÷100。上限 999",
          "基础属性"),
    ]
    for i in range(15):
        base = 0x0C + i * 4
        fields += [
            F(f"jutsu_{i}_id", base, 1, "u8", f"忍术{i} ID",
              "忍术记录表下标（0x59937C）", "忍术列表", "jutsu", i, "id",
              relation={"table": "jutsu_names", "kind": "text", "label": "忍术名"}),
            F(f"jutsu_{i}_value", base + 1, 1, "u8", f"忍术{i} 等级值",
              "0/1/3，0xFF = 未习得", "忍术列表", "jutsu", i, "value",
              enum={0: "等级 0", 1: "等级 1", 3: "等级 3", 0xFF: "未习得"}),
            F(f"jutsu_{i}_unlock", base + 2, 1, "u8", f"忍术{i} 解锁等级",
              "0 = 不会自动习得", "忍术列表", "jutsu", i, "unlock_level"),
            F(f"jutsu_{i}_pad", base + 3, 1, "u8", f"忍术{i} 填充",
              "恒为 0", "忍术列表", "jutsu", i, "pad"),
        ]
    for i in range(24):
        base = 0x48 + i * 4
        fields += [
            F(f"train_{i}_id", base, 1, "u8", f"技能{i} ID",
              "技能/特性表下标（0x5459C8 / 0x5A7060）", "技能列表", "training", i, "id",
              relation={"table": "training_names", "kind": "text", "label": "技能名"}),
            F(f"train_{i}_value", base + 1, 1, "u8", f"技能{i} 等级值",
              "等级值，B−1 是成长倍率", "技能列表", "training", i, "value"),
            F(f"train_{i}_unlock", base + 2, 1, "u8", f"技能{i} 解锁等级",
              "0 = 不会自动习得", "技能列表", "training", i, "unlock_level"),
            F(f"train_{i}_pad", base + 3, 1, "u8", f"技能{i} 填充",
              "恒为 0", "技能列表", "training", i, "pad"),
        ]
    for i in range(9):
        fields.append(F(f"item_{i}", 0xA8 + i, 1, "u8", f"道具槽{i}",
                        "忍具名表下标（0x599634），0 = 空", "道具槽", "items", i, "id",
                        relation={"table": "ninjutsu_names", "kind": "text", "label": "忍具名"}))
    return fields


# --------------------------------------------------------------------------
# 音频：sound-ID 表与 m4a 描述符
# --------------------------------------------------------------------------
def read_sound_id_rows(rom: bytes) -> list[dict[str, Any]]:
    """sound-ID 表的 159 行（每行 8 字节：描述符指针 + 播放通道 + 播放配置）。"""
    rows: list[dict[str, Any]] = []
    for sid in range(SOUND_ID_TABLE_COUNT):
        off = SOUND_ID_TABLE_BASE + sid * SOUND_ID_TABLE_STRIDE
        ptr, channel, config = struct.unpack_from("<IHH", rom, off)
        rows.append({
            "id": sid,
            "address": ptr,
            "offset": ptr - ROM_BASE if ptr else None,
            "channel": channel,
            "config": config,
        })
    return rows


def read_song_header(rom: bytes, address: int) -> dict[str, Any]:
    """一个 m4a SongHeader：8 字节头 + track_count 个 4 字节轨道指针。

    布局（与 tools/audio_song_headers.py 一致）：
        +0x00 u8  track_count
        +0x01 u8  block_count
        +0x02 u8  priority
        +0x03 u8  reverb（原生只读 bit7）
        +0x04 u32 voicegroup_ptr
        +0x08 u32 track_ptr[track_count]
    """
    off = address - ROM_BASE
    track_count = rom[off]
    return {
        "address": address,
        "offset": off,
        "track_count": track_count,
        "block_count": rom[off + 1],
        "priority": rom[off + 2],
        "reverb": rom[off + 3],
        "voicegroup_ptr": struct.unpack_from("<I", rom, off + 4)[0],
        "track_ptrs": [
            struct.unpack_from("<I", rom, off + 8 + i * 4)[0]
            for i in range(track_count)
        ],
        "size": 8 + track_count * 4,
    }


def build_audio_descriptors(rom: bytes) -> dict[str, Any]:
    """sound-ID 表指向的每一个描述符（按地址去重）。

    159 条音效指向 81 个不同地址：80 个真实描述符各被一条音效使用，
    其余 79 条共用同一个空哨兵（0 轨 = 没有声音）。
    """
    rows = read_sound_id_rows(rom)
    descriptors: dict[int, dict[str, Any]] = {}
    for row in rows:
        address = row["address"]
        if not address:
            continue
        header = descriptors.get(address)
        if header is None:
            header = read_song_header(rom, address)
            header["sound_ids"] = []
            descriptors[address] = header
        header["sound_ids"].append(row["id"])
    for header in descriptors.values():
        ids = header["sound_ids"]
        if header["track_count"] == 0:
            # 空哨兵：没有轨道，也没有声音。
            header["structure_id"] = AUDIO_SONG_EMPTY_ID
            header["label"] = "空哨兵描述符（没有声音）"
            header["kind"] = "empty"
        else:
            header["structure_id"] = f"audio_song_{ids[0]}"
            header["label"] = f"音频曲 {ids[0]}（m4a SongHeader）"
            header["kind"] = "song" if header["track_count"] > 1 else "sfx"
    return {"rows": rows, "descriptors": descriptors}


def read_play_thunk(rom: bytes, pointer: int) -> dict[str, Any]:
    """函数指针表的一个槽：是不是「movs r0,#k」的播放 thunk。

    表里存的是 Thumb 入口（地址低位 1 = Thumb），指令从 pointer & ~1 开始：

        push {lr} / movs r0,#k / bl <共享例程> / pop {r0} / bx r0

    k 就是这条 thunk 交给播放例程的参数。
    """
    code = pointer & ~1
    off = code - ROM_BASE
    info: dict[str, Any] = {"kind": "unknown", "pointer": pointer, "code": code}
    if off < 0 or off + 12 > len(rom):
        return info
    push, movs, bl1, bl2, pop, bx = struct.unpack_from("<6H", rom, off)
    if push != 0xB500 or bx != 0x4700:
        return info
    if (movs & 0xFF00) != 0x2000:
        return info
    info["kind"] = "play_entry"
    info["sound_id"] = movs & 0xFF
    # Thumb BL：第一个半字 11110 S imm10，第二个半字 11 J1 1 J2 imm11。
    if (bl1 & 0xF800) == 0xF000 and (bl2 & 0xD000) == 0xD000:
        s = (bl1 >> 10) & 1
        imm10 = bl1 & 0x3FF
        j1 = (bl2 >> 13) & 1
        j2 = (bl2 >> 11) & 1
        imm11 = bl2 & 0x7FF
        i1 = 1 - (j1 ^ s)
        i2 = 1 - (j2 ^ s)
        value = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if value & 0x1000000:
            value -= 0x2000000
        info["target"] = (code + 8 + value) & 0xFFFFFFFF
    return info


AUDIO_KIND_NAMES = {"song": "乐曲", "sfx": "短音效", "empty": "空哨兵", "null": "空指针"}


def build_audio_stats(rom: bytes) -> dict[str, Any]:
    """音频域的派生事实。

    这些事实**不占 ROM 字节**（统计、映射、共用关系），所以只能放在内容包的
    顶层 derived 段 —— 做成结构表的话，rom.js 会试图把它写回 ROM。
    """
    audio = build_audio_descriptors(rom)
    rows = audio["rows"]
    descriptors = audio["descriptors"]

    channel_hist: dict[int, int] = {}
    channel_kinds: dict[int, dict[str, int]] = {}
    for row in rows:
        channel = row["channel"]
        channel_hist[channel] = channel_hist.get(channel, 0) + 1
        header = descriptors.get(row["address"])
        kind = header["kind"] if header else "null"
        kinds = channel_kinds.setdefault(channel, {})
        kinds[kind] = kinds.get(kind, 0) + 1

    channel_enum: dict[str, str] = {}
    for channel in sorted(channel_hist):
        kinds = channel_kinds[channel]
        detail = "、".join(
            f"{AUDIO_KIND_NAMES.get(kind, kind)} {count} 条"
            for kind, count in sorted(kinds.items(), key=lambda kv: -kv[1])
        )
        channel_enum[str(channel)] = (
            f"{channel} · 通道 {channel}（{channel_hist[channel]} 条：{detail}）"
        )

    slots: dict[str, Any] = {}
    for slot in range(FUNCTION_POINTER_TABLE_COUNT):
        off = FUNCTION_POINTER_TABLE_BASE + slot * 4
        value = struct.unpack_from("<I", rom, off)[0]
        if value == 0xFFFFFFFF:
            slots[str(slot)] = {
                "kind": "sentinel",
                "value": "0xFFFFFFFF",
                "label": "哨兵（FFFFFFFF）",
            }
            continue
        info = read_play_thunk(rom, value)
        entry: dict[str, Any] = {"kind": info["kind"], "value": f"0x{value:08X}"}
        if info["kind"] == "play_entry":
            k = info["sound_id"]
            entry["sound_id"] = k
            entry["label"] = f"播放入口 · 音效 #{k}（推定）"
            entry["code"] = f"0x{info['code']:08X}"
            entry["target"] = f"0x{info['target']:08X}" if "target" in info else None
            # 槽号 → 音效号的对应是**静态推定**（thunk 里的 movs r0,#k），
            # 仓库里没有运行时证据闭环。
            entry["evidence"] = "static"
        else:
            entry["label"] = "（不是播放 thunk）"
        slots[str(slot)] = entry

    targets = sorted({
        entry["target"] for entry in slots.values()
        if entry.get("kind") == "play_entry" and entry.get("target")
    })
    if len(targets) == 1:
        target_text = f"全部跳向同一个例程 {targets[0]}"
    elif targets:
        target_text = "跳向 " + "、".join(targets)
    else:
        target_text = "没有解析出跳转目标"

    empty_ids = descriptors.get(AUDIO_EMPTY_DESCRIPTOR, {}).get("sound_ids", [])
    kinds_hist: dict[str, int] = {}
    for header in descriptors.values():
        kinds_hist[header["kind"]] = kinds_hist.get(header["kind"], 0) + 1

    return {
        "sound_id_count": len(rows),
        "descriptor_count": len(descriptors),
        "real_descriptor_count": sum(
            1 for header in descriptors.values() if header["kind"] != "empty"),
        "descriptor_kinds": {
            AUDIO_KIND_NAMES.get(kind, kind): count
            for kind, count in sorted(kinds_hist.items())
        },
        "empty_descriptor": f"0x{AUDIO_EMPTY_DESCRIPTOR:08X}",
        "empty_descriptor_offset": f"0x{AUDIO_EMPTY_DESCRIPTOR - ROM_BASE:06X}",
        "empty_sound_ids": len(empty_ids),
        "channel_histogram": {str(k): v for k, v in sorted(channel_hist.items())},
        "channel_kinds": {
            str(channel): {
                AUDIO_KIND_NAMES.get(kind, kind): count
                for kind, count in sorted(kinds.items(), key=lambda kv: -kv[1])
            }
            for channel, kinds in sorted(channel_kinds.items())
        },
        "channel_enum": channel_enum,
        "config_equals_channel": all(row["config"] == row["channel"] for row in rows),
        "descriptors": {
            f"0x{address:08X}": {
                "structure": header["structure_id"],
                "label": header["label"],
                "kind": header["kind"],
                "tracks": header["track_count"],
                "blocks": header["block_count"],
                "sound_ids": header["sound_ids"],
            }
            for address, header in sorted(descriptors.items())
        },
        "function_pointer_slots": slots,
        "function_pointer_note": (
            "1..11 槽是 11 条「movs r0,#k」的播放 thunk（k = 1..11），"
            f"{target_text}。"
            "k 与音效号的对应是静态推定，尚未由运行时证据闭环。"
        ),
    }


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
             "忍术列表 15 项、技能列表 24 项、道具槽 9 项。"
             "12 字节头里的六项属性在运行时实例里依次是 +0x02 / +0x03 / +0x04 / +0x05 / +0x06 / +0x08；"
             "仓库自己的指令级分析证明了偏移"
             "（notes/character-template-format-20261020.md §2.2 的拷贝表），"
             "名字（攻击力 / 防御力 / 敏捷度 / 移动力 / 忍具数 / 查克拉）"
             "来自第三方逆向 notes/character-stats-addresses.md —— 名字是第三方给的，不是本仓库证的。",
        id_relation={"table": "character_names", "kind": "text", "label": "角色名"},
        primary_columns=["stat_a", "stat_b", "stat_c", "hp_base", "aux_stat"],
        verification="L1 结构已证明 / 写回路径 tools/import_character_template.py",
    ))

    growth_fields = [
        F("hp_gain", 0x00, 2, "u16", "体力每级成长",
          "×100 存，除以 100 后加到体力上（0x0806DA3A）", "成长"),
        F("stat_f_gain", 0x02, 2, "u16", "查克拉每级成长",
          "×100 存，除以 100 后加到查克拉（实例 +0x08）", "成长"),
        F("stat_a_gain", 0x04, 2, "u16", "攻击力每级成长",
          "×100 存，除以 100 后加到攻击力（实例 +0x02）", "成长"),
        F("stat_b_gain", 0x06, 2, "u16", "防御力每级成长",
          "×100 存，除以 100 后加到防御力（实例 +0x03）", "成长"),
        F("stat_c_gain", 0x08, 2, "u16", "敏捷度每级成长",
          "×100 存，除以 100 后加到敏捷度（实例 +0x04）", "成长"),
        F("stat_d_gain", 0x0A, 2, "u16", "移动力每级成长",
          "×100 存，除以 100 后加到移动力（实例 +0x05）", "成长"),
        F("stat_e_gain", 0x0C, 2, "u16", "忍具数每级成长",
          "×100 存，除以 100 后加到忍具数（实例 +0x06）", "成长"),
        F("unused", 0x0E, 2, "u16", "未使用", "恒为 0", "成长"),
    ]
    out.append(make_structure(
        "per_character_stats", "characters", "逐角色成长表",
        PER_CHARACTER_STATS_BASE, PER_CHARACTER_STATS_STRIDE,
        growth_fields,
        (PER_CHARACTER_STATS_BASE + i * PER_CHARACTER_STATS_STRIDE
         for i in range(PER_CHARACTER_STATS_COUNT)),
        rom,
        note="每级数值 = 基础 + 成长 ×(等级−1) ÷ 100（整数除法）。"
             "成长项的名字跟角色定义表的六项属性一一对应"
             "（体力 / 攻击力 / 防御力 / 敏捷度 / 移动力 / 忍具数 / 查克拉），"
             "名字同样出自第三方逆向 notes/character-stats-addresses.md。",
        id_relation={"table": "character_names", "kind": "text", "label": "角色名"},
        primary_columns=["hp_gain", "stat_a_gain", "stat_b_gain", "stat_c_gain"],
        verification="L1 结构已证明 / 写回路径 tools/import_character_template.py",
    ))

    perk_fields = [
        F("kind", 0x00, 1, "u8", "特性类型", "决定效果分支（0x0D..0x13 出现过），语义未解", "特性"),
        F("unused_01", 0x01, 1, "u8", "未使用 +0x01", "恒为 0", "特性"),
        F("base", 0x02, 2, "u16", "基础值", "特性基础数值", "特性"),
        F("secondary", 0x04, 2, "u16", "次要值", "原生 0x0806DDF6 读取", "特性"),
        F("growth", 0x06, 2, "u16", "每级成长", "总成长 = 基础 + 成长×(等级值−1)", "特性"),
        F("extra_stat", 0x08, 2, "u16", "附加属性",
          "语义未解（notes/completion-audit-20261020.md 未解项 8）", "特性"),
        F("unused_0a", 0x0A, 2, "u16", "未使用 +0x0A", "恒为 0", "特性"),
    ]
    out.append(make_structure(
        "character_perks", "characters", "角色特性表（技能）",
        PERK_BASE, PERK_STRIDE, perk_fields,
        (PERK_BASE + i * PERK_STRIDE for i in range(PERK_COUNT)),
        rom,
        note="下标 = 技能（技术）id，与技能名表 0x5A7060 同空间。",
        id_relation={"table": "training_names", "kind": "text", "label": "技能名"},
        primary_columns=["kind", "base", "growth"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    portrait_fields: list[dict[str, Any]] = []
    for expr in range(5):
        portrait_fields.append(F(f"expr{expr}_gfx", expr * 8, 4, "ptr",
                                 f"表情{expr} 图像",
                                 "LZ77 4bpp 头像图块，80×80", "头像",
                                 "expr", expr, "gfx"))
        portrait_fields.append(F(f"expr{expr}_palette", expr * 8 + 4, 4, "ptr",
                                 f"表情{expr} 调色板",
                                 "64 色 BGR555（未压缩）", "头像",
                                 "expr", expr, "palette"))
    out.append(make_structure(
        "portrait_table", "characters", "头像指针表",
        PORTRAIT_TABLE_BASE, PORTRAIT_TABLE_STRIDE, portrait_fields,
        (PORTRAIT_TABLE_BASE + i * PORTRAIT_TABLE_STRIDE
         for i in range(PORTRAIT_TABLE_COUNT)),
        rom,
        note="每行 40 字节 = 5 个表情 × (图像指针 + 调色板指针)。",
        primary_columns=["expr0_gfx", "expr0_palette"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    piece_fields = [
        F("tile", 0x00, 4, "u32", "图块下标", "0xFFFF = 结束标记", "拼块"),
        F("x", 0x04, 2, "u16", "目标 X", "这块拼在头像的哪个 X 位置（像素）", "拼块"),
        F("y", 0x06, 2, "u16", "目标 Y", "这块拼在头像的哪个 Y 位置（像素）", "拼块"),
        F("w", 0x08, 2, "u16", "宽度（像素）", "这块占多宽", "拼块"),
        F("h", 0x0A, 2, "u16", "高度（像素）", "这块占多高", "拼块"),
    ]
    out.append(make_structure(
        "portrait_pieces", "characters", "头像拼块表",
        PORTRAIT_PIECES_BASE, PORTRAIT_PIECES_STRIDE, piece_fields,
        (PORTRAIT_PIECES_BASE + i * PORTRAIT_PIECES_STRIDE
         for i in range(PORTRAIT_PIECES_COUNT)),
        rom,
        note="6 块拼成 80×80 头像。",
        primary_columns=["tile", "x", "y"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    # ---- 忍术 -----------------------------------------------------------
    jutsu_fields = [
        F("unknown_00", 0x00, 1, "u8", "未解字节 +0x00", "复制到已习得忍术记录 +0x04，语义未解", "记录"),
        F("unknown_01", 0x01, 1, "u8", "未解字节 +0x01", "复制到已习得忍术记录 +0x05，语义未解", "记录"),
        F("flags", 0x02, 2, "u16", "标志位",
          "&0x1800>>5 → 0..0xC0 等级/点数；高字节在仓库里另被标为「未解」", "记录"),
    ]
    for i in range(6):
        # 标签用 **1 基**（成长目标1..6）并带上字节偏移：
        # `growth_type` 的取值 1..6 指向的就是这六个字节，而它们自己的下标是 0 基，
        # 两套编号相反会让作者把「成长目标=4」当成 grow_4（其实是 grow_3）。
        jutsu_fields.append(F(f"grow_{i}", 0x04 + i, 1, "u8", f"成长目标{i + 1}",
                              f"字节 +0x{0x04 + i:02X}：随等级成长的初值；"
                              f"由下面的「成长目标」字段选中（1..6 指到这里）", "成长"))
    jutsu_fields += [
        F("unknown_0a", 0x0A, 1, "u8", "未解字节 +0x0A",
          "语义未解（notes/completion-audit-20261020.md 未解项 8）", "记录"),
        F("unknown_0b", 0x0B, 1, "u8", "未解字节 +0x0B",
          "语义未解（未解项 8）", "记录"),
        F("growth_type", 0x0C, 1, "u8", "成长目标",
          "0/7 = 不成长；1..6 指向上面的成长目标1..6", "成长",
          enum={0: "不成长", 7: "不成长", 1: "成长目标1（+0x04）",
                2: "成长目标2（+0x05）", 3: "成长目标3（+0x06）",
                4: "成长目标4（+0x07）", 5: "成长目标5（+0x08）",
                6: "成长目标6（+0x09）"}),
        F("unknown_0d", 0x0D, 1, "u8", "未解字节 +0x0D",
          "语义未解（未解项 8）", "记录"),
        F("growth_amount", 0x0E, 1, "u8", "每级成长量",
          "值 = (等级−1) × 本值；实测 87 条记录中 +0x0F 恒为 0，"
          "所以本字段是单字节（仓库里把 +0x0E 记成 u16 属高字节恒零的等价写法）",
          "成长"),
        F("pad_0f", 0x0F, 1, "u8", "填充 +0x0F", "实测 87 条记录恒为 0", "记录"),
    ]
    out.append(make_structure(
        "jutsu_record", "ninjutsu", "忍术记录表",
        JUTSU_RECORD_BASE, JUTSU_RECORD_STRIDE, jutsu_fields,
        (JUTSU_RECORD_BASE + i * JUTSU_RECORD_STRIDE for i in range(JUTSU_RECORD_COUNT)),
        rom,
        note="下标 = 忍术 id，与忍术名表 0x59937C 同空间。",
        id_relation={"table": "jutsu_names", "kind": "text", "label": "忍术名"},
        primary_columns=["growth_type", "growth_amount", "flags"],
        verification="L1 结构已证明 / 写回路径 tools/import_character_template.py",
    ))

    # ---- 道具 -----------------------------------------------------------
    # 标签跟包里其它未解码字节统一（「未解字节 +0xNN」），
    # 免得作者以为「字节00」是某种编号。
    item_fields = [F(f"raw_{i:02x}", i, 1, "hex", f"未解字节 +0x{i:02X}",
                     "16 字节的字段语义尚未证明（7 个原生读者，见 notes/completion-audit-20261020.md）；"
                     "按原始字节编辑", "原始字节")
                   for i in range(16)]
    out.append(make_structure(
        "item_record", "items", "道具/忍具记录表",
        ITEM_RECORD_BASE, ITEM_RECORD_STRIDE, item_fields,
        (ITEM_RECORD_BASE + i * ITEM_RECORD_STRIDE for i in range(ITEM_RECORD_COUNT)),
        rom,
        note="94 条 16 字节记录。仓库里**没有任何一处证明**这 16 字节的字段含义，"
             "所以本表按原始字节呈现并编辑，不臆造字段名。\n"
             "**编辑器构建线会把它原样写回**（`rom.js::applyStructures`），"
             "所以在编辑器里改这里是真的会进 ROM 的。",
        primary_columns=["raw_00", "raw_01", "raw_02", "raw_03"],
        verification="L1 结构已证明 / 编辑器构建线会写回（外部 Python 导入线尚无）",
        raw_only=True,
        id_relation={"table": "ninjutsu_names", "kind": "text", "label": "忍具名"},
    ))

    reward_fields = [
        F("gold", 0x00, 2, "u16", "金币", "关卡奖励金币", "奖励"),
        F("upgrade_points", 0x02, 2, "u16", "强化点", "升级素材点数", "奖励"),
        F("tier", 0x04, 2, "u16", "等级门槛", "与运行时 0x0202680C 比较", "奖励"),
    ]
    for k in range(8):
        reward_fields += [
            F(f"slot{k}_category", 0x06 + k * 2, 1, "u8", f"道具位{k} 类别",
              "类别 → 名字表的对应由 ROM 自带的 4 槽指针表 0x0859F5E0 证明",
              "道具掉落", "slots", k, "category", enum=REWARD_CATEGORY_ENUMS),
            F(f"slot{k}_item", 0x07 + k * 2, 1, "u8", f"道具位{k} 物品ID",
              "该类别的名称表下标；0 = 列表结束", "道具掉落", "slots", k, "item_id",
              relation={"kind": "by_category", "label": "物品名",
                        "categories": REWARD_CATEGORY_TABLES}),
        ]
    reward_fields += [
        F("reserved_16", 0x16, 1, "u8", "保留 +0x16", "恒为 0，没有消费者读它", "保留"),
        F("reserved_17", 0x17, 1, "u8", "保留 +0x17", "恒为 0，没有消费者读它", "保留"),
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
        F("background_id", 0x1C, 1, "u8", "剧情底图ID", "指向底图表 0x59903C", "底图",
          relation={"table": "background_table", "kind": "structure", "label": "底图"}),
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
        F("character_id", 0x00, 1, "u8", "角色ID", "0 = 空槽", "角色",
          relation={"table": "character_names", "kind": "text", "label": "角色名"}),
        F("side", 0x01, 1, "u8", "阵营（原生不读）",
          "0=我方 1=敌方。**编成消费者不读这一字节**，阵营走 unit_flags 的 bit0",
          "角色", not_read=True, enum={0: "我方", 1: "敌方"}),
        F("x", 0x02, 1, "u8", "出生 X", "初始 X 坐标（格）", "出生点"),
        F("y", 0x03, 1, "u8", "出生 Y", "初始 Y 坐标（格）", "出生点"),
        F("facing", 0x04, 1, "u8", "朝向/参数", "写入 unit+0xC9", "出生点"),
        F("unit_flags", 0x08, 4, "u32", "单位标志",
          "bit0 = 阵营（**这个才是生效的**）；unit+0xC0 = flags|side|0x10", "角色",
          bits=[{"mask": 1, "label": "阵营", "enum": {"0": "我方", "1": "敌方"}}]),
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
          "决定外观与音效", "物件", enum=OBJECT_TYPE_ENUMS),
        F("target", 0x01, 1, "u8", "触发目标", "决定触发的剧本（13 项效果表）", "物件"),
        F("x", 0x02, 1, "u8", "X 坐标", "物件所在的 X 坐标（格）", "物件"),
        F("y", 0x03, 1, "u8", "Y 坐标", "物件所在的 Y 坐标（格）", "物件"),
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
        # 这张表的第一条记录**不在**编成矩阵的基址上，而在它之后 0x8A4 处
        # （物件区紧跟在 12 个角色槽后面）。早先这里填的是 BATTLE_ACTORS_BASE，
        # 于是面板头显示的 ROM 地址与表里第一条记录对不上，
        # 连带「这个指针指向哪张表」也判错（两个区间重叠）。
        BATTLE_ACTORS_BASE + BATTLE_OBJECT_OFFSET, BATTLE_OBJECT_STRIDE, object_fields,
        object_offsets, rom,
        note="每关卡变体 16 个物件，位于编成组 +0x8A4（紧跟在 12 个角色槽后面）。",
        primary_columns=["type", "target", "x", "y"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    rule_fields = [F("turn_limit", 0x00, 1, "u8", "回合上限", "0 = 无限制", "回合")]
    for group in range(2):
        label = "胜利条件" if group == 0 else "失败条件"
        for k in range(4):
            base = 0x04 + group * 0x20 + k * 8
            rule_fields += [
                F(f"g{group}_{k}_type", base, 1, "u8", f"{label}{k} 类型",
                  "原生语义见 notes/battle-tables.md §1.1.1",
                  label, "rules", group * 4 + k, "type",
                  enum=CONDITION_TYPE_ENUMS),
                F(f"g{group}_{k}_a", base + 1, 1, "u8", f"{label}{k} 参数A",
                  "含义随类型而变：1 = 1 我方胜 / 0 我方负；3 = 阵营；"
                  "6 = 道具序号；7/8/9 = 0 我方 / 1 对方。类型 2 不读它。"
                  "逐类型的原生语义见 notes/battle-tables.md §1.1",
                  label, "rules", group * 4 + k, "a"),
                F(f"g{group}_{k}_b", base + 2, 1, "u8", f"{label}{k} 参数B",
                  "类型 3 = 角色 id（判据在 0x020240C0 的 12 个单位槽）；"
                  "类型 2 不读它", label, "rules", group * 4 + k, "b",
                  relation={"table": "character_names", "kind": "text", "label": "角色名",
                            "when": "type=3"}),
                F(f"g{group}_{k}_c", base + 3, 1, "u8", f"{label}{k} 参数C", "恒为 0", label,
                  "rules", group * 4 + k, "c"),
                F(f"g{group}_{k}_text_ptr", base + 4, 4, "ptr", f"{label}{k} 说明文本",
                  "「条件」页显示的说明", label, "rules", group * 4 + k, "text_ptr",
                  relation={"table": "battle_objectives", "kind": "text", "label": "说明文字"}),
            ]
    rule_offsets = [
        BATTLE_RULES_BASE + s * BATTLE_RULE_STAGE_STRIDE + u * BATTLE_RULE_SUB_STRIDE
        for s in range(BATTLE_RULE_COUNT) for u in range(BATTLE_VARIANT_COUNT)
    ]
    out.append(make_structure(
        "battle_rules", "battle", "战斗目标（胜负条件）",
        BATTLE_RULES_BASE, BATTLE_RULE_SUB_STRIDE, rule_fields,
        rule_offsets, rom,
        note="47 关 × 3 变体 × 0x44 字节。index = 关卡 s / 变体 u。"
             "每条记录 2 组条件（胜利 / 失败）× 4 条，每条 8 字节："
             "类型 u8、参数 A/B/C 各 u8、说明文字指针 u32。"
             "类型的原生语义：1 = 击破敌方全部 / 我方全灭（a=1 胜 / 0 负）；"
             "2 = 回合用尽（**代码完全不读 a/b**）；"
             "3 = 指定角色已离场（a=阵营、b=角色 id）；"
             "6 = 获得指定道具（a=道具序号）；"
             "7 = 剩余体力比较、8 = 击杀数比较、9 = 收集物数量比较（a=0 我方 / 1 对方）。"
             "逐条的原生语义与证据见 notes/battle-tables.md §1.1。",
        primary_columns=["turn_limit"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    encounter_fields = [
        F("ptr_0", 0x00, 4, "ptr", "指针 0（效果表下标）",
          "消费者只取它的低字节作 13 项效果表的下标", "遭遇"),
        F("ptr_1", 0x04, 4, "ptr", "指针 1", "没有原生读者读它", "遭遇"),
        F("ptr_2", 0x08, 4, "ptr", "指针 2", "没有原生读者读它", "遭遇"),
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
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
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
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    wram_fields = [
        F("wram_addr", 0x00, 4, "u32", "EWRAM 起始地址",
          "子系统分到的内存起点（原生取值都在 0x0202xxxx）", "内存分配"),
        F("alloc_size", 0x04, 4, "u32", "分配大小", "字节数", "内存分配"),
    ]
    out.append(make_structure(
        "wram_allocation", "assets", "WRAM 分配表",
        WRAM_ALLOC_BASE, WRAM_ALLOC_STRIDE, wram_fields,
        (WRAM_ALLOC_BASE + i * WRAM_ALLOC_STRIDE for i in range(WRAM_ALLOC_COUNT)),
        rom,
        note="10 组 {u32 EWRAM 地址, u32 大小}。4 个原生读者："
             "0x0806869A / 0x08068954 / 0x08068CC0 / 0x08068D98。\n"
             "**旧称「存档描述符表」是错的**：存档数据在 SRAM，不在 ROM；"
             "这张表只决定每个子系统分到多少 EWRAM。",
        primary_columns=["wram_addr", "alloc_size"],
        verification="L3 格式已证明 / 写回路径可用（tools/import_battle_config.py::write_wram_alloc）",
        # 只有 3 段有仓库依据（notes/battle-config-format.md:162-165），
        # 其余 4 段**不编名字** —— 界面上写「未命名」比瞎猜强。
        record_labels={
            0: "战斗状态结构",
            1: "战斗状态结构",
            3: "战斗状态结构",
            5: "战斗控制标志",
            7: "战斗主数据",
        },
        # 4 个原生读者（notes/completion-audit-20261020.md「save-state」行）
        consumers=["0x0806869A", "0x08068954", "0x08068CC0", "0x08068D98"],
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
    sprite_ptr_labels = (
        ("frames_ptr", "帧指针", "精灵帧描述符表（精灵帧描述符表 0x53EE98）"),
        ("animations_ptr", "动画指针", "动画数据块"),
        ("gfx_ptr", "图块图形", "LZ77 图形"),
        ("palette_ptr", "调色板", "调色板"),
    )
    for i, (name, label, desc) in enumerate(sprite_ptr_labels):
        sprite_fields.append(F(name, i * 4, 4, "ptr", label, desc, "指针"))
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
        F("tilemap_ptr", 0x08, 4, "ptr", "tilemap 图层",
          "LZ77 640 字节（32×32 的图层数据）", "背景"),
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
        verification="L1 结构已证明（id 1..7、9..13）· 编辑器构建线会写回（仓库里没有专用导入工具）",
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
        fields = [F("ptr", 0, 4, "ptr", "剧本首地址", "该场景的剧本首地址", "场景指针",
          ptr_kind="code")]
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
          "该关卡第 u 个奖励在奖励表 0x59EAE0 里的下标", "任务索引",
          relation={
              # 这个字段是**一段连续行**的基址：每一关占 3 个子项，
              # 同时落在奖励表与三张任务文本表里。
              # 以前没声明，奖励表 / 任务文本表在界面上看不到任何来源。
              "kind": "row_range",
              "tables": ["reward_table", "mission_titles",
                         "mission_descriptions", "mission_hints"],
              "count": MISSION_SUBS,
              "label": "本关的任务与奖励",
          }),
    ]
    out.append(make_structure(
        "mission_index", "route", "任务索引表",
        MISSION_INDEX_BASE, 1, mission_index_fields,
        (MISSION_INDEX_BASE + s for s in range(MISSION_INDEX_STAGES)), rom,
        note="每关 3 个子文本；任务文本表下标 = 本表值[关卡] + 子编号（0..2）。"
             "本表 48 字节（关卡 0..47）。",
        primary_columns=["value"],
        record_labels={s: f"第{s}关" for s in range(MISSION_INDEX_STAGES)},
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    font_fields = [
        F("start_code", 0x00, 2, "u16", "起始码", "本段第一个字形码", "字形段"),
        F("count", 0x02, 1, "u8", "字数", "本段字形数量", "字形段"),
        F("pad", 0x03, 1, "u8", "填充 +0x03", "对齐用的填充字节", "字形段"),
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
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    # --- 其余已证实、此前未进包的表 ---------------------------------------
    # --- 音频：sound-ID 分派表 + 全部 m4a 描述符 ---------------------------
    audio = build_audio_descriptors(rom)
    descriptors = audio["descriptors"]
    audio_stats = build_audio_stats(rom)
    channel_enum = {int(k): v for k, v in audio_stats["channel_enum"].items()}

    sound_id_fields = [
        F("descriptor_ptr", 0x00, 4, "ptr", "描述符指针",
          "指向 m4a SongHeader（编辑器里是带名字的下拉）", "声音"),
        F("player_index", 0x04, 2, "u16", "播放通道",
          "原生 voice 索引，取值 0..3", "声音", enum=channel_enum),
        F("player_config", 0x06, 2, "u16", "播放配置",
          "原生 159 行里与播放通道逐行相等", "声音", enum=channel_enum),
    ]
    # 描述符指针的选项集：81 个地址（80 个真实描述符 + 1 个空哨兵）。
    # 它们分散在 81 张结构里，所以选项集放在**结构级**（ptr_relation），
    # 而不是字段级 relation（那只能挂一张表）。
    ptr_options = [
        {
            "value": address,
            "label": header["label"],
            "structure": header["structure_id"],
            "record_id": 0,
            "tracks": header["track_count"],
            "blocks": header["block_count"],
            "kind": header["kind"],
            "empty": header["kind"] == "empty",
            "sound_ids": header["sound_ids"],
            "shared": len(header["sound_ids"]),
        }
        for address, header in sorted(descriptors.items())
    ]
    out.append(make_structure(
        "sound_id_table", "audio", "音频 sound-ID 表",
        SOUND_ID_TABLE_BASE, SOUND_ID_TABLE_STRIDE, sound_id_fields,
        (SOUND_ID_TABLE_BASE + i * SOUND_ID_TABLE_STRIDE
         for i in range(SOUND_ID_TABLE_COUNT)),
        rom,
        note="159 条 × 8 字节：指向 m4a 歌曲描述符，并给出播放通道与配置。"
             "79 条指向空哨兵（ROM 0x466068，0 轨 = 没有声音），"
             "其余 80 条各有一个真实描述符。音效 id 就是这张表里的下标（0 基）。",
        primary_columns=["descriptor_ptr", "player_index"],
        record_labels={i: f"音效 #{i}" for i in range(SOUND_ID_TABLE_COUNT)},
        id_is_index=True,
        ptr_relation={
            "kind": "pointer_map",
            "field": "descriptor_ptr",
            "options": ptr_options,
        },
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    for address, header in sorted(descriptors.items()):
        tracks = header["track_count"]
        song_fields = [
            F("track_count", 0x00, 1, "u8", "轨道数",
              "引擎按这个数读轨道指针", "歌曲头"),
            F("block_count", 0x01, 1, "u8", "块数",
              "原生 ROM 里全部为 0；这一字节的用途未证实", "歌曲头"),
            F("priority", 0x02, 1, "u8", "优先级",
              "原生取值 0 / 10 / 255，语义未完全证实", "歌曲头"),
            F("reverb", 0x03, 1, "u8", "混响",
              "原生只读 bit7（L2 运行时证据）", "歌曲头",
              enum={0: "关", 128: "开（bit7）"}),
            F("voicegroup_ptr", 0x04, 4, "ptr", "音色组指针",
              "音色组在 0x084648xx 区，尚未解码", "歌曲头"),
        ]
        for t in range(tracks):
            song_fields.append(F(f"track{t}_ptr", 8 + t * 4, 4, "ptr",
                                 f"轨道 {t + 1} 指针",
                                 "指向压缩的轨道数据（编辑器改不了采样本身）", "轨道",
                                 array="tracks", index=t, item="ptr"))
        if header["kind"] == "empty":
            song_note = ("空哨兵：0 个轨道 —— 这个描述符没有声音。"
                         f"{len(header['sound_ids'])} 个音效共用它。")
        else:
            song_note = (f"m4a SongHeader：8 字节头 + {tracks} 个轨道指针。"
                         "音频样本本体是压缩载荷，不在本表里；"
                         "这里能改的是「指向哪段轨道数据」。")
        out.append(make_structure(
            header["structure_id"], "audio", header["label"],
            header["offset"], header["size"], song_fields,
            (header["offset"],), rom,
            note=song_note,
            primary_columns=["track_count", "block_count", "priority"],
            verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
        ))

    out.append(make_structure(
        "function_pointer_table", "audio", "函数指针表",
        FUNCTION_POINTER_TABLE_BASE, 4,
        [F("ptr", 0, 4, "ptr", "代码指针", "槽 0 与槽 12 是 FFFFFFFF 哨兵", "指针",
              ptr_kind="code")],
        (FUNCTION_POINTER_TABLE_BASE + i * 4
         for i in range(FUNCTION_POINTER_TABLE_COUNT)),
        rom,
        note="13 槽 u32。" + audio_stats["function_pointer_note"],
        primary_columns=["ptr"],
        record_labels={i: f"槽 {i}" for i in range(FUNCTION_POINTER_TABLE_COUNT)},
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    out.append(make_structure(
        "font_width_table", "story", "字宽表",
        FONT_WIDTH_TABLE_BASE, 1,
        [F("width", 0, 1, "u8", "字宽", "按字符码索引", "字宽")],
        (FONT_WIDTH_TABLE_BASE + i for i in range(FONT_WIDTH_TABLE_COUNT)),
        rom,
        note="256 字节，按字符码索引的宽度。",
        primary_columns=["width"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    handler_fields = [
        F("handler_a", 0x00, 4, "ptr", "处理程序 A",
          "本条事件的第一个处理程序（代码地址）", "分派", ptr_kind="code"),
        F("handler_b", 0x04, 4, "ptr", "处理程序 B",
          "本条事件的第二个处理程序（代码地址）", "分派", ptr_kind="code"),
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
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
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
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    out.append(make_structure(
        "pickup_dispatch", "battle", "原生拾取分派表",
        PICKUP_DISPATCH_BASE, 4,
        [F("handler", 0, 4, "ptr", "处理程序", "7 个拾取处理程序", "分派",
              ptr_kind="code")],
        (PICKUP_DISPATCH_BASE + i * 4 for i in range(PICKUP_DISPATCH_COUNT)),
        rom,
        note="7 个拾取处理程序指针。",
        primary_columns=["handler"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
    ))

    for table_id, base, count, label, readers in (
        ("data_pointer_table_a", DATA_POINTER_A_BASE, DATA_POINTER_A_COUNT,
         "数据指针表 A", ["0x0808A6BA", "0x0808B19E"]),
        ("data_pointer_table_b", DATA_POINTER_B_BASE, DATA_POINTER_B_COUNT,
         "数据指针表 B", ["0x080985D8", "0x08099D26"]),
    ):
        out.append(make_structure(
            table_id, "assets", label,
            base, 4,
            [F("ptr", 0, 4, "ptr", "指针",
               "这一格决定「用哪一份资源」；指向的资源本体（压缩载荷）"
               "在编辑器里改不了", "指针")],
            (base + i * 4 for i in range(count)),
            rom,
            note=f"{count} 项 u32 指针表；指向的资源本体不在本表里。",
            primary_columns=["ptr"],
            verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
            consumers=readers,
        ))

    asset_fields = [
        F("head", 0x00, 12, "hex", "未解头部 +0x00", "未解码的 12 字节，原样保留", "资源记录"),
    ]
    for t in range(6):
        asset_fields.append(F(f"tile_ptr_{t}", 0x0C + t * 4, 4, "ptr",
                               f"图块指针 {t + 1}",
                               "指向一份图块资源（载荷不可改，改的是「用哪一份」）", "图块",
                               array="gfx", index=t, item="ptr"))
    asset_fields.append(F("mid", 0x24, 4, "hex", "未解中段 +0x24",
                          "未解码的 4 字节，原样保留", "资源记录"))
    for s in range(3):
        asset_fields.append(F(f"script_ptr_{s}", 0x28 + s * 4, 4, "ptr",
                               f"脚本指针 {s + 1}",
                               "指向一段脚本资源（载荷不可改，改的是「用哪一份」）", "脚本",
                               array="script", index=s, item="ptr"))
    out.append(make_structure(
        "tile_asset_records", "assets", "图块/精灵资源记录表",
        TILE_ASSET_RECORDS_BASE, TILE_ASSET_RECORDS_STRIDE, asset_fields,
        (TILE_ASSET_RECORDS_BASE + i * TILE_ASSET_RECORDS_STRIDE
         for i in range(TILE_ASSET_RECORDS_COUNT)),
        rom,
        note="79 条 × 68 字节：6 个图块指针 + 3 个脚本指针，其余未解码。"
             "79 条记录里只有 31 种不同的图块组合、69 种不同的脚本组合 —— "
             "改一条会影响共用同一组合的那些记录。",
        primary_columns=["tile_ptr_0", "script_ptr_0"],
        verification="L1 结构已证明 · 编辑器构建线会写回（仓库里没有专用导入工具）",
        consumers=["0x0809881E"],
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

    for table_id, base, label, prefix in (
        ("mission_titles", MISSION_TITLE_BASE, "任务标题表", "标题"),
        ("mission_descriptions", MISSION_DESC_BASE, "任务说明表", "说明"),
        ("mission_hints", MISSION_HINT_BASE, "任务提示表", "提示"),
    ):
        out.append(build_text_table(
            rom, mapping, table_id, "route", label,
            base, MISSION_ENTRY_COUNT,
            note="每关 3 个子奖励文本。下标 = 任务索引表[关卡] + 子编号（0..2），"
                 "最大用到 111 号槽位，所以表长 112。",
            id_prefix=prefix,
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

    objectives, objective_offsets = build_battle_objectives(rom, mapping)
    out.append(objectives)
    return out, objective_offsets


def build_battle_objectives(
    rom: bytes, mapping: dict[int, str]
) -> tuple[dict[str, Any], set[int]]:
    """战斗目标说明文字（游戏内「条件」页显示的那句话）。

    胜负条件表 `battle_rules` 的每条条件都带一个**绝对地址指针**，指向一句
    说明文字。这张表把那些不重复的句子收进来，编辑器因此能显示与改写它们。

    这些句子的地址会被从「全 ROM 文本索引」里剔除 —— 同一段字节只能有一个
    归属，否则两个表都写同一处地址就会互相覆盖。
    """
    pointers: dict[int, dict[str, Any]] = {}
    for s in range(BATTLE_RULE_COUNT):
        for u in range(BATTLE_VARIANT_COUNT):
            base = (BATTLE_RULES_BASE + s * BATTLE_RULE_STAGE_STRIDE
                    + u * BATTLE_RULE_SUB_STRIDE)
            rule_id = s * BATTLE_VARIANT_COUNT + u
            for g in range(2):
                for k in range(4):
                    field = 0x04 + g * 0x20 + k * 8
                    (ptr,) = struct.unpack_from("<I", rom, base + field + 4)
                    if not ptr:
                        continue
                    offset = ptr - 0x08000000
                    entry = pointers.setdefault(offset, {
                        "pointer": ptr,
                        "bindings": [],
                    })
                    entry["bindings"].append({
                        "rule": rule_id, "stage": s, "variant": u,
                        "group": g, "index": k,
                    })

    records = []
    bindings = []
    for record_id, offset in enumerate(sorted(pointers)):
        entry = pointers[offset]
        end = rom.find(b"\x00", offset)
        if end < 0:
            end = len(rom)
        raw = rom[offset:end]
        text = decode_text(raw, mapping)
        # 标签：作者认的是「第几关的哪条条件」，不是地址。
        # 一段说明文字可能被好几条战斗目标共用，这时把共用处数也写出来。
        first = entry["bindings"][0] if entry["bindings"] else None
        if first:
            group_name = "胜利条件" if first["group"] == 0 else "失败条件"
            label = (f"第{first['stage']}关 · 变体{first['variant']} · "
                     f"{group_name}{first['index']}")
            if len(entry["bindings"]) > 1:
                label += f" 等 {len(entry['bindings'])} 处"
        else:
            label = f"0x{entry['pointer']:08X}"
        records.append({
            "id": record_id,
            "label": label,
            "pointer_offset": None,
            "pointer": entry["pointer"],
            "text_offset": offset,
            "capacity": len(raw) + 1,
            "text": text,
            "original_text": text,
            "raw": b64(raw),
        })
        for binding in entry["bindings"]:
            bindings.append({
                "rule": binding["rule"],
                "group": binding["group"],
                "index": binding["index"],
                "text_id": record_id,
            })

    table = {
        "id": "battle_objectives",
        "module": "battle",
        "label": "战斗目标说明文字",
        "pointer_table_offset": None,
        "count": len(records),
        "relocatable": False,
        "nul_terminated": True,
        "note": "胜负条件表里每条条件都带一个绝对地址指针，指向游戏内「条件」页"
                "显示的那句话（例：「打败业头・冥头了」）。\n"
                "**只能等长改写**：这些地址被 ROM 里的代码写死，改长了没有地方放。"
                "\n这些句子不在「全 ROM 文本索引」里，以免同一段字节有两个归属。",
        "records": records,
        "bindings": bindings,
    }
    return table, set(pointers)


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
    table = {
        "id": table_id,
        "module": module,
        "label": label,
        "pointer_table_offset": None,
        "count": count,
        "relocatable": False,
        "nul_terminated": True,
        "inline_records": True,
        "records": records,
    }
    if note:
        table["note"] = note
    readers = load_consumer_readers().get(base)
    if readers:
        table["consumers"] = readers
    return table


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
            portraits: list[dict[str, Any]] = []
            for node in nodes:
                op = node["op"]
                if op == 0x08:
                    # 设置头像 + 说话人名字（头像ID @ +1）。
                    # 仓库的 opcode 表已证：名字取自 0x085A57C4 + id*12，
                    # 头像部分取自头像指针表 0x085A4DEC + id*40。
                    # 实测这个字节落在 1..61，全在头像表的 64 条之内。
                    portraits.append({
                        "rom_offset": node["offset"],
                        "portrait_id": rom[node["offset"] + 1],
                    })
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
                "portraits": portraits,
            })
    return out


def build_dominant_text_index(rom: bytes, mapping: dict[int, str],
                               limit: int = 20000,
                               exclude: set[int] | frozenset[int] = frozenset(),
                               owned: dict[int, str] | None = None
                               ) -> dict[str, Any]:
    """Every font-coded string in the cartridge, found with the ROM's own font.

    This is the editor's safety net: whatever the named tables miss, the
    author can still find and edit it here.

    `exclude` holds the ROM offsets of strings that already belong to a
    dedicated table (the battle objectives) — a string must have exactly one
    home, otherwise two tables would write the same address.

    `owned` maps a ROM offset to the table that already owns it.  Those
    strings are still *listed* here (so the author can find them), but they
    are marked `owned_by` and the builder skips them: editing the same bytes
    from two tables would silently overwrite one of the two changes.
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
            if b == 0x0A:
                # 换行是合法码位（码位 10），见 notes/font-encoding.md §2。
                # 早先这里按 "b < 0x20 一律非法" 处理，把所有含换行的文本块
                # 整块丢掉了 —— 其中就有 32 条战斗目标说明文字。
                j += 1
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
        if s in exclude:
            continue        # already owned by a dedicated table
        text = decode_text(seg, mapping)
        if len(text) < 1:
            continue
        record = {
            "id": len(records),
            "label": f"0x{s:06X}",
            "pointer_offset": None,
            "pointer": None,
            "text_offset": s,
            "capacity": len(seg) + 1,
            "text": text,
            "original_text": text,
            "raw": b64(seg),
        }
        if owned and s in owned:
            # 这段字节已经属于某张具名表：在这里只**列出来**，
            # 但写回时跳过 —— 同一段字节被两张表各写一次，改动会互相覆盖。
            record["owned_by"] = owned[s]
        records.append(record)

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


def build_derived(rom: bytes, structures: list[dict[str, Any]],
                  texts: list[dict[str, Any]]) -> dict[str, Any]:
    """Facts the exporter worked out about the ROM that are **not** records.

    Right now that is one thing: what a ROM pointer points at.  The editor
    has to answer 「0x0859F988 是什么」, and it must be able to answer it
    **without the original ROM being loaded** — so the judgement is made
    here, at export time, and travels with the pack.

    A pointer's payload is judged from the byte at the target: GBA LZ77
    blocks start with 0x10 and carry their decompressed size in the next
    three bytes; anything else is raw data.  Pointers that land on a
    known structure record are left out — the editor already names those.
    """
    # 地址 → 落在哪张表的哪条记录（已知结构优先）
    known: dict[int, str] = {}
    for structure in structures:
        for record in structure.get("records", []):
            known.setdefault(int(record["rom_offset"]), structure["label"])

    addresses: set[int] = set()
    for structure in structures:
        for field in structure.get("fields", []):
            if field.get("type") != "ptr":
                continue
            for record in structure.get("records", []):
                value = (record.get("values") or {}).get(field["key"])
                if isinstance(value, int) and value:
                    addresses.add(value)

    targets: dict[str, Any] = {}
    for address in sorted(addresses):
        if address in known:
            continue
        offset = address - ROM_BASE
        if offset < 0 or offset + 4 > len(rom):
            continue
        header = rom[offset]
        key = f"0x{address:08X}"
        if header == 0x10:
            size = int.from_bytes(rom[offset + 1:offset + 4], "little")
            targets[key] = {
                "kind": "lz77",
                "size": size,
                "label": f"LZ77 块（解压后 {size:,} 字节）",
            }
        else:
            targets[key] = {
                "kind": "raw",
                "size": None,
                "label": "未压缩原始数据",
            }
    return {
        "pointer_targets": targets,
        # 音频域的派生事实：描述符 → 音效 id 列表 / 轨道数 / 共用关系、
        # 播放通道分布、函数指针表每个槽「是什么」。
        # 这些**不占 ROM 字节**，所以只能放顶层 derived 段
        # （做成结构表的话 rom.js 会试图把它们写回 ROM）。
        "sound_stats": build_audio_stats(rom),
    }


def build_pack(rom_path: Path, with_text_index: bool = True) -> dict[str, Any]:
    rom = rom_path.read_bytes()
    mapping, report = text_codec.load_mapping(rom_path)

    structures = build_structures(rom, mapping)
    texts, objective_offsets = build_text_tables(rom, mapping)
    if with_text_index:
        # 具名表已经拥有的字节：文本索引里仍然列出来（作者找得到），
        # 但标记归属并跳过写回，免得两处改同一段字互相覆盖。
        owned: dict[int, str] = {}
        for table in texts:
            for record in table.get("records", []):
                offset = record.get("text_offset")
                if offset is None or offset in owned:
                    continue
                owned[offset] = f"{table['id']}#{record['id']}"
        texts.append(build_dominant_text_index(rom, mapping,
                                               exclude=objective_offsets,
                                               owned=owned))

    # 同一张表里，多条记录可能指向**同一段字节**（例如任务标题表里 27 个槽位
    # 共用同一串全角空格）。那其实是**同一个字符串**，改一处必须一起改，
    # 否则构建时后写的会覆盖先写的、改动凭空消失。
    for table in texts:
        by_offset: dict[int, list[int]] = {}
        for record in table.get("records", []):
            offset = record.get("text_offset")
            if offset is None:
                continue
            by_offset.setdefault(offset, []).append(record["id"])
        for record in table.get("records", []):
            offset = record.get("text_offset")
            if offset is None:
                continue
            shared = by_offset.get(offset, [])
            if len(shared) > 1:
                record["shared_with"] = [i for i in shared if i != record["id"]]

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
        "derived": build_derived(rom, structures, texts),
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
