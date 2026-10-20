#!/usr/bin/env python3
"""Character template table `0x54241C` - decoded layout and field semantics.

The table holds one 180-byte (``0xB4``) record per character, id 1..62
(id 0 is an all-zero null slot).  Every field below was recovered from the
**native consumer code**, not from values that "look like" HP or attack.

Native readers of ``0x0854241C`` (``tools/consumer_locate.py`` finds four):

``0x0806D4A0`` - *character build*
    Walks the 24-slot WRAM instance pool at ``0x02022E34`` (stride ``0xBC``),
    picks a free slot, and copies the template into it::

        0x0806D4D2  ldr  r0, [pc, #0x40]      ; r0 = 0x0854241C
        0x0806D4D4  adds r7, r1, r0          ; r7 = 0x0854241C + id*0xB4
        0x0806D4F6  ldrb r0, [r1, #0xc]       ; template[0x0C + 4*i]
        0x0806D4F8  strb r0, [r2, #0x14]      ; instance[0x14 + 4*i]
        0x0806D4FA  ldrb r0, [r1, #0xd]       ; template[0x0D + 4*i]
        0x0806D520  strb r0, [r1, #0x15]      ; instance[0x15 + 4*i]
        0x0806D540  ldrb r1, [r0]            ; template[0x48 + 4*i]
        0x0806D546  strb r1, [r0]            ; instance[0x50 + 4*i]
        0x0806D54C  ldrb r0, [r0]            ; template[0x49 + 4*i]
        0x0806D576  strb r1, [r0, #0x51]     ; instance[0x51 + 4*i]

``0x0806D964`` - *stat initialisation*
    Turns the template header into the instance's runtime stats::

        0x0806D984  ldr  r0, [pc, #0xc]       ; r0 = 0x0854241C
        0x0806D988  mov  sb, r1               ; sb = &template[id]
        0x0806D98C  ldr  r0, [pc, #8]         ; r0 = 0x08545068
        0x0806D98E  adds r1, r1, r0           ; r1 = 0x08545068 + id*0x10

        0x0806D9CE  ldrb r4, [r2, #1]         ; template[+0x01]
        0x0806D9D2  strb r4, [r6, #2]         ; instance[+0x02] = stat base
        0x0806D9E2  ldrb r1, [r2, #2]         ; template[+0x02] -> instance[+0x03]
        0x0806D9F6  ldrb r1, [r2, #3]         ; template[+0x03] -> instance[+0x04]
        0x0806DA0A  ldrb r1, [r2, #4]         ; template[+0x04] -> instance[+0x05]
        0x0806DA1E  ldrb r1, [r2, #5]         ; template[+0x05] -> instance[+0x06]
        0x0806DA32  ldrb r1, [r2, #6]         ; template[+0x06] -> instance[+0x08]
        0x0806DA46  ldrh r1, [r2, #0xa]       ; template[+0x0A] -> instance[+0x0E]
        0x0806DA50  ldrh r0, [r1, #8]         ; template[+0x08] -> instance[+0x0A]

``0x080899EC`` - *level-up / unlock scan*   (called from ``0x08089B7E``)
    Proves what the third byte of every 4-byte entry means::

        0x08089A0C  ldrb r2, [r1, #0x14]   ; instance[0x14+4i] = jutsu id
        0x08089A14  ldrb r0, [r1, #0x15]   ; instance[0x15+4i] = jutsu value
        0x08089A16  cmp  r0, #0xff        ; 0xFF == "not learned yet"
        0x08089A18  bne  0x8089a60
        0x08089A32  mov  r1, r8            ; r8 = &template[id]
        0x08089A34  adds r0, r1, r3       ; r3 = i*4
        0x08089A36  ldrb r1, [r0, #0xe]   ; template[0x0E+4i] = unlock level
        0x08089A38  cmp  r1, #0
        0x08089A3A  beq  0x8089a60        ; gate 0 == never unlocks
        0x08089A3C  ldrb r0, [r6, #1]     ; instance[1] = character level
        0x08089A3E  cmp  r0, r1
        0x08089A40  blo  0x8089a60        ; level < gate -> still locked
        0x08089A48  strb r0, [r2, #0x15]  ; locked value 0xFF -> 0 (learned)

    The unlocked ids are written to a list that the level-up screen turns into
    names, which is what proves the *meaning* of the id columns::

        0x08089DD8  ldr  r0, [pc, #0x10]   ; 0x0859937C  jutsu name table
        0x08089DDA  ldrb r1, [r4]         ; list byte
        0x08089DDC  lsls r1, r1, #2
        0x08089DDE  adds r1, r1, r0
        0x08089DE0  ldr  r1, [r1]         ; jutsu name
        0x08089DF0  ldr  r0, [pc, #0x30]   ; 0x085A7060  training name table
        0x08089DF4  ands r1, r2, #0x7f    ; strip the segment-2 marker 0x80

``0x08092694`` - *battle-config -> instance copy*
    Reads the template header and the per-entry unlock level again
    (``0x0809272C``: ``adds r0, r8`` / ``adds r0, #0x4a`` ->
    ``template[0x4A+4i]`` = the segment-2 unlock level).

The two 4-byte entry regions are therefore:

* ``+0x0C..+0x47`` (15 entries) - the character's **jutsu (忍术) list**;
* ``+0x48..+0xA7`` (24 entries) - the character's **training (技术) list**.

Both share the layout ``(id u8, value u8, unlock_level u8, pad u8)``.

Unresolved fields are reported with an explicit ``*_unknown`` key and a
``resolved: false`` flag; they are never given a speculative name.  The tool
also **fails loudly**: if the ROM does not contain the exact instruction bytes
the conclusions above rest on, it exits non-zero instead of printing garbage.

Usage:
    python tools/character_templates.py rom/base.gba
    python tools/character_templates.py rom/base.gba --id 1
    python tools/character_templates.py rom/base.gba --json build/character_templates.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from tools.lib.io import write_json, write_text  # noqa: E402
from tools.text_codec import decode, load_mapping  # noqa: E402

# --- table geometry (file offsets inside the ROM image) ----------------------
#: Template table.  63 slots of 0xB4 bytes: id 0 is an all-zero null slot and
#: the real characters are id 1..62.  The table ends exactly at 0x545068,
#: which is where the per-character growth table starts.
TEMPLATE_BASE = 0x54241C
TEMPLATE_STRIDE = 0xB4
TEMPLATE_SLOTS = 63  # id 0..62
TEMPLATE_COUNT = 62  # real characters, id 1..62
TEMPLATE_ID_MIN = 1
TEMPLATE_ID_MAX = 62

#: Per-character growth table, 16 bytes per id (63 slots, id 0..62).
#: Ends exactly at 0x545458, the start of the 16-byte jutsu records.
SKILLS16_BASE = 0x545068
SKILLS16_STRIDE = 0x10
SKILLS16_SLOTS = 63

#: 16-byte jutsu records, indexed by **jutsu id** (0..86).
#: The index is proved by 0x0809457C..0x08094594: the template's segment-1 id
#: is multiplied by 16 and added to 0x08545458.
JUTSU_RECORD_BASE = 0x545458
JUTSU_RECORD_STRIDE = 0x10
#: 0x545458 + 87*16 == 0x5459C8 exactly: the region is 1392 bytes == 87
#: 16-byte records.  The third-party "348 u32" copy is the same bytes read
#: with the wrong stride.
JUTSU_RECORD_COUNT = 87

#: 12-byte perk records, indexed by the training (技术) id.
#: ``0x085459C8 + index*12`` at 0x0806D6E0..0x0806D6E8.
PERK_BASE = 0x5459C8
PERK_STRIDE = 0x0C

#: Character name table: u32 pointers to font-coded strings.  Index 0 is the
#: "no name" placeholder; indices 1..62 line up 1:1 with the template ids.
#: The table itself holds 150 entries (0x599280 + 150*4 == 0x5994D8).
NAME_TABLE = 0x599280
NAME_COUNT = 64  # slots 0..63 (index 63 is another "no name" slot)

#: Jutsu (忍术) name table: u32 pointers, 87 entries, index == jutsu id.
#: Same index space as the 16-byte records at 0x545458.
JUTSU_NAME_TABLE = 0x59937C
JUTSU_NAME_COUNT = 87

#: Training (技术) name table: u32 pointers, 45 entries, index == training id.
#: This is the very same table the reward dispatcher uses for reward
#: category 3 (技术).
TRAINING_NAME_TABLE = 0x5A7060
TRAINING_NAME_COUNT = 45

#: Ninjutsu item (忍具) name table: u32 pointers, 94 entries.  The 9 item
#: slots of a template hold ids from this space, because the build path calls
#: 0x0808FA34 - the same "add one item to the inventory" routine the reward
#: dispatcher calls for reward category 0 (忍具).
NINJUTSU_NAME_TABLE = 0x599634
NINJUTSU_NAME_COUNT = 94

# --- template record layout -------------------------------------------------
#: 12-byte header.  ``target`` is the runtime instance offset the byte lands
#: in; ``evidence`` is the instruction that copies it.  ``evidence is None``
#: means the field is **not** understood - those keys carry ``_unknown``.
HEADER_FIELDS = (
    # (offset, size, key, target, meaning, evidence)
    (0x00, 1, "field_0x00_unknown", None,
     "未解：id 1..62 恒为 1，四个原生消费者都不读它", None),
    (0x01, 1, "stat_a_base", "+0x02", "属性 A 基础值 (+等级-1)", "0x0806D9CE"),
    (0x02, 1, "stat_b_base", "+0x03", "属性 B 基础值 (+等级-1)", "0x0806D9E2"),
    (0x03, 1, "stat_c_base", "+0x04", "属性 C 基础值 (+等级-1)", "0x0806D9F6"),
    (0x04, 1, "stat_d_base", "+0x05", "属性 D 基础值 (上限 5)", "0x0806DA0A"),
    (0x05, 1, "stat_e_base", "+0x06", "属性 E 基础值 (上限 9)", "0x0806DA1E"),
    (0x06, 1, "stat_f_base", "+0x08", "属性 F 基础值 (上限 9)", "0x0806DA32"),
    (0x07, 1, "field_0x07_unknown", None,
     "未解：全部 62 条恒为 0，四个原生消费者都不读它", None),
    (0x08, 2, "aux_stat", "+0x0A", "副属性 u16 (上限 999)", "0x0806DA50"),
    (0x0A, 2, "hp_base", "+0x0E", "体力 u16 基础值 (上限 999)", "0x0806DA46"),
)

#: First 4-byte-entry segment: 15 entries at +0x0C - the jutsu (忍术) list.
JUTSU_OFFSET = 0x0C
JUTSU_COUNT = 15
#: Second 4-byte-entry segment: 24 entries at +0x48 - the training (技术) list.
TRAINING_OFFSET = 0x48
TRAINING_COUNT = 24
#: 9 byte item ids at +0xA8.
ITEMS_OFFSET = 0xA8
ITEMS_COUNT = 9

#: Instance offsets the two segments are copied to.
JUTSU_TARGET = 0x14
TRAINING_TARGET = 0x50

#: Cap applied to the u16 stats (literal 0x000003E7 at 0x0806DB40).
U16_CAP = 999

#: Per-instance caps, read from the clamp chain at 0x0806DA5A..0x0806DA90.
STAT_CAPS = {0x02: 99, 0x03: 99, 0x04: 99, 0x05: 5, 0x06: 9, 0x08: 9}

#: The 8 u16 of ``0x545068 + id*0x10`` and what each one does.
SKILLS16_FIELDS = (
    # (u16 index, key, meaning, evidence)
    (0, "hp_gain_x100", "体力每级增长 x100", "0x0806DA3A"),
    (1, "stat_f_gain_x100", "属性 F 每级增长 x100", "0x0806DA26"),
    (2, "stat_a_gain_x100", "属性 A 每级增长 x100", "0x0806D9C2"),
    (3, "stat_b_gain_x100", "属性 B 每级增长 x100", "0x0806D9D6"),
    (4, "stat_c_gain_x100", "属性 C 每级增长 x100", "0x0806D9EA"),
    (5, "stat_d_gain_x100", "属性 D 每级增长 x100", "0x0806D9FE"),
    (6, "stat_e_gain_x100", "属性 E 每级增长 x100", "0x0806DA12"),
    (7, "unused", "未使用 (恒为 0)", None),
)

#: The 16-byte jutsu record at ``0x545458 + jutsu_id*16``.
#: ``evidence is None`` -> the byte is copied around but its meaning is not
#: established; those keys carry ``_unknown``.
JUTSU_RECORD_FIELDS = (
    # (offset, size, key, meaning, evidence)
    (0x00, 1, "record_0x00_unknown",
     "未解：被拷到「已习得忍术」表项的 +0x04 字节", "0x08094582"),
    (0x01, 1, "record_0x01_unknown",
     "未解：被拷到「已习得忍术」表项的 +0x05 字节", "0x08094592"),
    (0x02, 2, "record_0x02_flags",
     "u16 位域：0x080922DE 取 & 0x1800 后 >>5，得到 0..0xC0 的档位/点数", "0x080922D8"),
    (0x03, 1, "field_0x03_unknown", "未解", None),
    (0x04, 1, "stat_growth_target_1", "六个随等级成长的字节字段之一", "0x0806D8B2"),
    (0x05, 1, "stat_growth_target_2", "六个随等级成长的字节字段之一", "0x0806D8C0"),
    (0x06, 1, "stat_growth_target_3", "六个随等级成长的字节字段之一", "0x0806D8CE"),
    (0x07, 1, "stat_growth_target_4", "六个随等级成长的字节字段之一", "0x0806D8DC"),
    (0x08, 1, "stat_growth_target_5", "六个随等级成长的字节字段之一", "0x0806D8EA"),
    (0x09, 1, "stat_growth_target_6", "六个随等级成长的字节字段之一", "0x0806D8F8"),
    (0x0A, 1, "field_0x0A_unknown", "未解", None),
    (0x0B, 1, "field_0x0B_unknown", "未解", None),
    (0x0C, 1, "growth_type",
     "成长目标选择子：0=不成长, 1..6=分别成长 +0x04..+0x09, 7=不成长", "0x0806D876"),
    (0x0D, 1, "field_0x0D_unknown", "未解", None),
    (0x0E, 2, "growth_per_level", "每级成长量 u16", "0x0806D8AC"),
    (0x0F, 1, "field_0x0F_unknown", "未解", None),
)

# --- ROM layout guards ------------------------------------------------------
#: Every conclusion in this tool rests on the native code below.  If the ROM
#: is not the one the conclusions were derived from, these bytes will not
#: match and the tool exits non-zero instead of printing a plausible lie.
ROM_LAYOUT_CHECKS = (
    (0x0806D4CC, "b420", "0x0806D4A0 建立函数：步长常量 movs r0,#0xB4"),
    (0x0806D514, "1c245408", "0x0806D4A0 建立函数：模板表字面量 0x0854241C"),
    (0x0806D97E, "b420", "0x0806D964 属性初始化：步长常量 movs r0,#0xB4"),
    (0x0806D994, "1c245408", "0x0806D964 属性初始化：模板表字面量 0x0854241C"),
    (0x08089AD8, "1c245408", "0x080899EC 解锁扫描：模板表字面量 0x0854241C"),
    (0x0809270C, "1c245408", "0x08092694 战斗配置搬运：模板表字面量 0x0854241C"),
    (0x08094650, "58545408", "0x08094550 忍术记录表字面量 0x08545458"),
    (0x08089DEC, "7c935908", "0x08089DD8 忍术名表字面量 0x0859937C"),
    (0x08089E24, "60705a08", "0x08089DF0 技术名表字面量 0x085A7060"),
    (0x0806D708, "c8595408", "0x0806D6E6 特性记录表字面量 0x085459C8"),
)


def _u8(buf: bytes, off: int) -> int:
    return buf[off]


def _u16(buf: bytes, off: int) -> int:
    return int.from_bytes(buf[off:off + 2], "little")


def _read_u16(rom: bytes, off: int) -> int:
    return int.from_bytes(rom[off:off + 2], "little")


def _read_u32(rom: bytes, off: int) -> int:
    return int.from_bytes(rom[off:off + 4], "little")


def _decode_name(rom: bytes, ptr: int, mapping: dict[int, str] | None) -> str | None:
    """Decode a font-coded string behind a u32 pointer."""
    if mapping is None:
        return None
    off = ptr - 0x08000000
    if not 0 <= off < len(rom):
        return None
    try:
        return decode(rom[off:off + 32], mapping)
    except Exception:  # pragma: no cover - decoding must never break the tool
        return None


def read_name(rom: bytes, cid: int, mapping: dict[int, str]) -> str | None:
    """Decode the character name (font-coded string behind a u32 pointer)."""
    if not 0 <= cid < NAME_COUNT:
        return None
    off = NAME_TABLE + cid * 4
    if off + 4 > len(rom):
        return None
    ptr = _read_u32(rom, off)
    if not 0x08000000 <= ptr < 0x08000000 + len(rom):
        return None
    return _decode_name(rom, ptr, mapping)


def read_table_name(rom: bytes, base: int, index: int,
                    mapping: dict[int, str] | None) -> str | None:
    """Decode the name at ``index`` of a u32 name-pointer table."""
    off = base + index * 4
    if off + 4 > len(rom):
        return None
    ptr = _read_u32(rom, off)
    if not 0x08000000 <= ptr < 0x08000000 + len(rom):
        return None
    return _decode_name(rom, ptr, mapping)


def table_capacity(rom: bytes, base: int, limit: int = 512) -> int:
    """Number of consecutive ROM text pointers at ``base``."""
    count = 0
    for i in range(limit):
        off = base + i * 4
        if off + 4 > len(rom):
            break
        ptr = _read_u32(rom, off)
        if not 0x08000000 <= ptr < 0x08000000 + len(rom):
            break
        count += 1
    return count


def effective_value(entry: dict, level: int) -> int:
    """Value the runtime actually stores, for a character of ``level``.

    0x08089A16 / 0x08089A48: a locked entry (``value == 0xFF``) whose
    ``unlock_level`` is in ``1..level`` is rewritten to ``0``; otherwise the
    raw value is copied verbatim.
    """
    if entry["value"] == 0xFF and 1 <= entry["unlock_level"] <= level:
        return 0
    return entry["value"]


def is_unlocked(entry: dict, level: int) -> bool:
    """True when the entry is active at ``level``.

    0x08089A36..0x08089A48: ``unlock_level != 0`` and
    ``unlock_level <= character level`` -> the entry is unlocked and its
    placeholder value becomes 0.
    """
    return 0 < entry["unlock_level"] <= level


def parse_entry(seg: bytes, index: int, kind: str) -> dict:
    """Decode one 4-byte entry ``(id u8, value u8, unlock_level u8, pad u8)``."""
    value = seg[1]
    unlock = seg[2]
    return {
        "slot": index,
        "kind": kind,
        "id": seg[0],
        "value": value,
        "unlock_level": unlock,
        "field_0x03_unknown": seg[3],
        # 0x08089A16 / 0x08089A80: 0xFF == "not learned yet"
        "value_is_placeholder": value == 0xFF,
    }


def parse_jutsu_record(rom: bytes, jutsu_id: int) -> dict | None:
    """The 16-byte jutsu record at ``0x545458 + jutsu_id*16``."""
    off = JUTSU_RECORD_BASE + jutsu_id * JUTSU_RECORD_STRIDE
    if off + JUTSU_RECORD_STRIDE > len(rom):
        return None
    rec = rom[off:off + JUTSU_RECORD_STRIDE]
    out = {"index": jutsu_id, "offset": off}
    for rel, size, key, meaning, evidence in JUTSU_RECORD_FIELDS:
        value = rec[rel] if size == 1 else _u16(rec, rel)
        out[key] = {
            "value": value,
            "meaning": meaning,
            "evidence": evidence,
            "resolved": evidence is not None,
        }
    return out


def parse_template(rom: bytes, cid: int, mapping: dict[int, str] | None) -> dict:
    base = TEMPLATE_BASE + cid * TEMPLATE_STRIDE
    blob = rom[base:base + TEMPLATE_STRIDE]

    header = {}
    for off, size, key, target, meaning, evidence in HEADER_FIELDS:
        value = _u8(blob, off) if size == 1 else _u16(blob, off)
        header[key] = {
            "offset": off,
            "value": value,
            "instance_offset": target,
            "meaning": meaning,
            "evidence": evidence,
            "resolved": evidence is not None,
        }

    jutsu = []
    for i in range(JUTSU_COUNT):
        off = JUTSU_OFFSET + i * 4
        entry = parse_entry(blob[off:off + 4], i, "jutsu")
        entry["template_offset"] = off
        entry["instance_offset"] = JUTSU_TARGET + i * 4
        entry["name"] = read_table_name(rom, JUTSU_NAME_TABLE, entry["id"], mapping)
        entry["record"] = parse_jutsu_record(rom, entry["id"])
        jutsu.append(entry)

    training = []
    for i in range(TRAINING_COUNT):
        off = TRAINING_OFFSET + i * 4
        entry = parse_entry(blob[off:off + 4], i, "training")
        entry["template_offset"] = off
        entry["instance_offset"] = TRAINING_TARGET + i * 4
        entry["name"] = read_table_name(rom, TRAINING_NAME_TABLE, entry["id"], mapping)
        entry["perk"] = read_perk(rom, entry["id"])
        training.append(entry)

    items = list(blob[ITEMS_OFFSET:ITEMS_OFFSET + ITEMS_COUNT])
    item_names = [
        read_table_name(rom, NINJUTSU_NAME_TABLE, i, mapping) if i else None
        for i in items
    ]

    out = {
        "id": cid,
        "template_offset": base,
        "name": read_name(rom, cid, mapping) if mapping else None,
        "header": header,
        "jutsu_list": jutsu,
        "training_list": training,
        "items": items,
        "item_names": item_names,
        "skills16": parse_skills16(rom, cid),
    }
    return out


def parse_skills16(rom: bytes, cid: int) -> dict:
    base = SKILLS16_BASE + cid * SKILLS16_STRIDE
    out = {"offset": base}
    for idx, key, meaning, evidence in SKILLS16_FIELDS:
        out[key] = {
            "value": _read_u16(rom, base + idx * 2),
            "meaning": meaning,
            "evidence": evidence,
            "resolved": evidence is not None,
        }
    return out


def read_perk(rom: bytes, index: int) -> dict | None:
    """Read the 12-byte perk record the training id points at."""
    if index <= 0:
        return None
    off = PERK_BASE + index * PERK_STRIDE
    if off + PERK_STRIDE > len(rom):
        return None
    rec = rom[off:off + PERK_STRIDE]
    return {
        "offset": off,
        "type": rec[0],
        "base": _u16(rec, 2),
        "growth": _u16(rec, 6),
        "evidence": "0x0806D6E0",
    }


def read_jutsu_records(rom: bytes) -> list[dict]:
    """All 87 sixteen-byte jutsu records (NOT a u32 pointer table)."""
    out = []
    for i in range(JUTSU_RECORD_COUNT):
        off = JUTSU_RECORD_BASE + i * JUTSU_RECORD_STRIDE
        rec = rom[off:off + JUTSU_RECORD_STRIDE]
        out.append(
            {
                "index": i,
                "offset": off,
                "bytes": list(rec),
                "u16": [_u16(rec, k * 2) for k in range(8)],
            }
        )
    return out


def field_distribution(templates: list[dict]) -> dict:
    dist: dict[str, Counter] = {}
    for tpl in templates:
        for key, info in tpl["header"].items():
            dist.setdefault(key, Counter())[info["value"]] += 1
    out = {}
    for key, counter in dist.items():
        out[key] = {
            "distinct": len(counter),
            "min": min(counter),
            "max": max(counter),
            "values": {str(k): v for k, v in sorted(counter.items())},
        }
    return out


def segment_statistics(templates: list[dict]) -> dict:
    stats = {"jutsu_list": {}, "training_list": {}}
    for name in ("jutsu_list", "training_list"):
        values: Counter = Counter()
        gates: Counter = Counter()
        indexes: Counter = Counter()
        filled = 0
        for tpl in templates:
            for entry in tpl[name]:
                values[entry["value"]] += 1
                gates[entry["unlock_level"]] += 1
                indexes[entry["id"]] += 1
                if entry["id"] or entry["value"]:
                    filled += 1
        stats[name] = {
            "entries": len(templates) * (
                JUTSU_COUNT if name == "jutsu_list" else TRAINING_COUNT),
            "non_empty_entries": filled,
            "value_histogram": {str(k): v for k, v in sorted(values.items())},
            "unlock_level_histogram": {str(k): v for k, v in sorted(gates.items())},
            "id_histogram": {str(k): v for k, v in sorted(indexes.items())},
        }
    return stats


# --------------------------------------------------------------------------
# validation - the tool must fail loudly instead of printing garbage
# --------------------------------------------------------------------------
def validate(rom: bytes, templates: list[dict]) -> list[str]:
    """Return a list of problems; an empty list means the ROM matches."""
    problems: list[str] = []

    # 1. the three tables must be exactly adjacent
    if TEMPLATE_BASE + TEMPLATE_SLOTS * TEMPLATE_STRIDE != SKILLS16_BASE:
        problems.append(
            "template table does not end at the growth table "
            f"(0x{TEMPLATE_BASE + TEMPLATE_SLOTS * TEMPLATE_STRIDE:X} != "
            f"0x{SKILLS16_BASE:X})")
    if SKILLS16_BASE + SKILLS16_SLOTS * SKILLS16_STRIDE != JUTSU_RECORD_BASE:
        problems.append("growth table does not end at the jutsu record table")
    if JUTSU_RECORD_BASE + JUTSU_RECORD_COUNT * JUTSU_RECORD_STRIDE != PERK_BASE:
        problems.append("jutsu record table does not end at the perk table")

    # 2. the native code the conclusions rest on must be byte-identical
    for addr, expect, what in ROM_LAYOUT_CHECKS:
        got = rom[addr - 0x08000000:addr - 0x08000000 + len(expect) // 2].hex()
        if got != expect:
            problems.append(
                f"ROM layout mismatch at 0x{addr:08X}: expected {expect}, "
                f"got {got} ({what})")

    # 3. the ROM must be large enough
    if len(rom) < PERK_BASE + PERK_STRIDE * 64:
        problems.append(f"ROM too small ({len(rom)} bytes)")

    # 4. the null slots must be null
    if any(rom[TEMPLATE_BASE:TEMPLATE_BASE + TEMPLATE_STRIDE]):
        problems.append("template slot 0 is not all-zero (null slot broken)")
    if any(rom[SKILLS16_BASE:SKILLS16_BASE + SKILLS16_STRIDE]):
        problems.append("growth table slot 0 is not all-zero (null slot broken)")

    # 5. the name tables must have the capacity the id domains assume
    for base, expect, label in (
        (JUTSU_NAME_TABLE, JUTSU_NAME_COUNT, "jutsu name table 0x59937C"),
        (TRAINING_NAME_TABLE, TRAINING_NAME_COUNT, "training name table 0x5A7060"),
        (NINJUTSU_NAME_TABLE, NINJUTSU_NAME_COUNT, "ninjutsu name table 0x599634"),
    ):
        cap = table_capacity(rom, base)
        if cap < expect:
            problems.append(
                f"{label} holds only {cap} entries, expected at least {expect}")
        elif cap > expect:
            problems.append(
                f"{label} holds {cap} entries, expected exactly {expect}")

    # 6. every id must stay inside its name table
    for tpl in templates:
        for entry in tpl["jutsu_list"]:
            if entry["id"] >= JUTSU_NAME_COUNT:
                problems.append(
                    f"character {tpl['id']} jutsu id {entry['id']} is outside the "
                    f"{JUTSU_NAME_COUNT}-entry jutsu name table")
            if entry["id"] >= JUTSU_RECORD_COUNT:
                problems.append(
                    f"character {tpl['id']} jutsu id {entry['id']} is outside the "
                    f"{JUTSU_RECORD_COUNT}-entry jutsu record table")
        for entry in tpl["training_list"]:
            if entry["id"] >= TRAINING_NAME_COUNT:
                problems.append(
                    f"character {tpl['id']} training id {entry['id']} is outside "
                    f"the {TRAINING_NAME_COUNT}-entry training name table")
        for item in tpl["items"]:
            if item and item >= NINJUTSU_NAME_COUNT:
                problems.append(
                    f"character {tpl['id']} item id {item} is outside the "
                    f"{NINJUTSU_NAME_COUNT}-entry ninjutsu name table")

    return problems


def _unlock_note(entry: dict, level: int) -> str:
    """Human readable state of one 4-byte entry at ``level``."""
    if entry["value"] != 0xFF:
        return "开局已习得"
    if entry["unlock_level"] == 0:
        return "value=0xFF 且无等级门槛（永不自动解锁）"
    if entry["unlock_level"] <= level:
        return f"等级{level}已解锁（value 0xFF -> 0）"
    return f"等级{entry['unlock_level']} 解锁（当前 {level} 未解锁）"


def field_split(templates: list[dict]) -> dict:
    """Proved / unknown split of every field the tool knows about."""
    proved, unknown = [], []
    for off, size, key, _target, meaning, evidence in HEADER_FIELDS:
        (proved if evidence else unknown).append({
            "where": "header", "offset": f"+0x{off:02X}", "size": size,
            "key": key, "meaning": meaning, "evidence": evidence,
        })
    for rel, size, key, meaning, evidence in JUTSU_RECORD_FIELDS:
        (proved if evidence else unknown).append({
            "where": "jutsu_record", "offset": f"+0x{rel:02X}", "size": size,
            "key": key, "meaning": meaning, "evidence": evidence,
        })
    for rel, key, meaning, evidence in SKILLS16_FIELDS:
        (proved if evidence else unknown).append({
            "where": "growth_table", "offset": f"u16[{rel}]", "size": 2,
            "key": key, "meaning": meaning, "evidence": evidence,
        })
    for label, count, base, table in (
        ("jutsu_list", JUTSU_COUNT, JUTSU_OFFSET, JUTSU_NAME_TABLE),
        ("training_list", TRAINING_COUNT, TRAINING_OFFSET, TRAINING_NAME_TABLE),
    ):
        for rel, key, meaning, evidence in (
            (0, "id", "忍术/技术 id（名字表下标）", "0x08089DD8 / 0x08089DF0"),
            (1, "value", "档位值；0xFF = 未习得", "0x08089A16 / 0x08089A80"),
            (2, "unlock_level", "解锁所需等级（0 = 永不解锁）", "0x08089A36 / 0x08089A8A"),
            (3, "field_0x03_unknown", "未解（不参与任何已定位的读路径）", None),
        ):
            (proved if evidence else unknown).append({
                "where": label, "offset": f"+0x{base + rel:02X} (+{rel})",
                "size": 1, "key": key, "meaning": meaning, "evidence": evidence,
            })
    by_area: dict[str, dict] = {}
    for item in proved:
        by_area.setdefault(item["where"], {"proved": 0, "unknown": 0})["proved"] += 1
    for item in unknown:
        by_area.setdefault(item["where"], {"proved": 0, "unknown": 0})["unknown"] += 1
    return {
        "proved": proved,
        "unknown": unknown,
        "proved_count": len(proved),
        "unknown_count": len(unknown),
        "by_area": by_area,
    }


def render_text(templates: list[dict], args, problems: list[str]) -> str:
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add("角色定义表 0x54241C  (id*0xB4, %d 条: id %d..%d; id 0 是全 0 空槽)" % (
        TEMPLATE_COUNT, TEMPLATE_ID_MIN, TEMPLATE_ID_MAX))
    add("原生消费者: 0x0806D4A0 (建立) / 0x0806D964 (属性初始化) / "
        "0x080899EC (等级解锁) / 0x08092694 (战斗配置搬运)")
    add("紧邻: 0x545068 = 逐角色成长表(id*16, 63 槽) -> 0x545458 = 忍术记录表"
        "(16 字节 x 87, 下标 = 忍术 id) -> 0x5459C8 = 12 字节特性表")
    add("=" * 78)

    split = field_split(templates)
    add("")
    add("字段语义划分: 已证 %d 项 / 明确未解 %d 项" % (
        split["proved_count"], split["unknown_count"]))
    for area, cell in split["by_area"].items():
        add("    %-14s 已证 %d / 未解 %d" % (area, cell["proved"], cell["unknown"]))
    add("  已证: %s" % ", ".join(
        "%s@%s" % (p["key"], p["offset"]) for p in split["proved"]))
    add("  未解: %s" % ", ".join(
        "%s@%s" % (p["key"], p["offset"]) for p in split["unknown"]))
    add("")

    shown = templates
    if args.id is not None:
        shown = [t for t in templates if t["id"] == args.id]
        if not shown:
            add(f"没有 id {args.id}")
            return "\n".join(lines) + "\n"

    for tpl in shown:
        head = tpl["header"]
        add("")
        add(f"--- id {tpl['id']}  @{tpl['template_offset']:#08x}  {tpl['name'] or '?'} ---")
        for _, size, key, target, meaning, evidence in HEADER_FIELDS:
            info = head[key]
            tgt = target or "-"
            ev = evidence or "未解"
            add("    +0x%02X=%-5s -> %-5s %s [%s]" % (
                info["offset"], info["value"], tgt, meaning, ev))

        sk = tpl["skills16"]
        add("    技能/成长表 0x545068+id*16: "
            + " ".join(f"{key}={sk[key]['value']}" for _, key, _, _ in SKILLS16_FIELDS))

        add("    忍术表 (+0x0C, 15 项) -> 实例 +0x14  [名字表 0x%X]" % JUTSU_NAME_TABLE)
        for e in tpl["jutsu_list"]:
            if not (e["id"] or e["value"] or e["unlock_level"]):
                continue
            add("        忍术id=%-3d %-8s value=%-3d %s" % (
                e["id"], e["name"] or "?", e["value"], _unlock_note(e, args.level)))

        add("    技术表 (+0x48, 24 项) -> 实例 +0x50  [名字表 0x%X]" % TRAINING_NAME_TABLE)
        for e in tpl["training_list"]:
            if not (e["id"] or e["value"] or e["unlock_level"]):
                continue
            perk = e["perk"]
            pstr = (f"  特性 type={perk['type']} base={perk['base']} "
                    f"growth={perk['growth']}" if perk else "  特性 (id 0 -> 无记录)")
            add("        技术id=%-3d %-8s value=%-3d %s%s" % (
                e["id"], e["name"] or "?", e["value"], _unlock_note(e, args.level),
                pstr))

        add(f"    忍具槽 (+0xA8, 9 字节, 名字表 0x{NINJUTSU_NAME_TABLE:X}): "
            f"{tpl['items']}")
        named = [(i, n) for i, n in zip(tpl["items"], tpl["item_names"]) if i]
        if named:
            add("      " + ", ".join(f"{i}={n}" for i, n in named))

    if args.id is None:
        add("")
        add("=" * 78)
        add("字段取值分布")
        add("=" * 78)
        for key, info in field_distribution(templates).items():
            vals = info["values"]
            head = ", ".join(f"{k}x{v}" for k, v in list(vals.items())[:8])
            add(f"  {key:<20} distinct={info['distinct']:<3} "
                f"range={info['min']}..{info['max']}  {head}")

        add("")
        add("条目区统计")
        for name, info in segment_statistics(templates).items():
            add(f"  {name}: {info['non_empty_entries']}/{info['entries']} 非空")
            add(f"    value        : {info['value_histogram']}")
            add(f"    unlock_level : {info['unlock_level_histogram']}")

        add("")
        add("0x545458 读法: 16 字节忍术记录表 x %d (不是 u32 指针表, 不是 348 条)" %
            JUTSU_RECORD_COUNT)
        add("  证据: 0x0809457C ldrb r0,[r2,#0x14] -> 忍术 id")
        add("        0x0809457E lsls r0,r0,#4 ; 0x08094580 add r0,r8(=0x08545458)")
        add("        -> 0x545458 + 忍术id*16 ; 名字表 0x%X 同为 87 条" % JUTSU_NAME_TABLE)
        add("  记录字段: +0x00/+0x01 已证被搬运但语义未解; +0x02 位域;"
            " +0x04..+0x09 六个成长目标; +0x0C 成长目标选择子; +0x0E 每级成长量")
        add("  明确未解: +0x03 +0x0A +0x0B +0x0D +0x0F")

    add("")
    add("=" * 78)
    if problems:
        add("SELF-CHECK FAILED (ROM 布局与本工具的假设不符):")
        for p in problems:
            add("   - %s" % p)
    else:
        add("SELF-CHECK PASSED: 布局/常量/名字表容量/取值域全部与假设一致")
    add("=" * 78)
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Decode the character template table 0x54241C.")
    ap.add_argument("rom", type=pathlib.Path, help="ROM path (default rom/base.gba)")
    ap.add_argument("--id", type=int, default=None, help="only show this character id")
    ap.add_argument(
        "--level",
        type=int,
        default=1,
        help="character level used to compute the effective entry values",
    )
    ap.add_argument("--json", type=pathlib.Path, default=None, help="write JSON report")
    ap.add_argument("--out", type=pathlib.Path, default=None, help="write the text report")
    args = ap.parse_args()

    rom_path: pathlib.Path = args.rom
    if not rom_path.exists():
        rom_path = REPO / "rom" / "base.gba"
    rom = rom_path.read_bytes()

    try:
        mapping, _ = load_mapping(rom_path)
    except Exception:  # pragma: no cover - names are optional
        mapping = None

    templates = [
        parse_template(rom, cid, mapping)
        for cid in range(TEMPLATE_ID_MIN, TEMPLATE_ID_MAX + 1)
    ]
    for tpl in templates:
        for key in ("jutsu_list", "training_list"):
            for entry in tpl[key]:
                entry["effective_value_at_level"] = effective_value(entry, args.level)
                entry["unlocked_at_level"] = is_unlocked(entry, args.level)
        tpl["level_used_for_effective_values"] = args.level

    problems = validate(rom, templates)
    split = field_split(templates)

    report = {
        "rom": str(rom_path),
        "table": {
            "base": TEMPLATE_BASE,
            "stride": TEMPLATE_STRIDE,
            "count": TEMPLATE_COUNT,
            "slots": TEMPLATE_SLOTS,
            "id_range": [TEMPLATE_ID_MIN, TEMPLATE_ID_MAX],
            "null_slot_id": 0,
            "ends_at": TEMPLATE_BASE + TEMPLATE_SLOTS * TEMPLATE_STRIDE,
        },
        "skills16_table": {
            "base": SKILLS16_BASE,
            "stride": SKILLS16_STRIDE,
            "slots": SKILLS16_SLOTS,
            "ends_at": SKILLS16_BASE + SKILLS16_SLOTS * SKILLS16_STRIDE,
        },
        "consumers": {
            "build": "0x0806D4A0",
            "stat_init": "0x0806D964",
            "unlock_scan": "0x080899EC",
            "battle_config_copy": "0x08092694",
            "instance_pool": "0x02022E34 (24 slots, stride 0xBC)",
        },
        "name_tables": {
            "character": {"base": NAME_TABLE, "entries": 150},
            "jutsu": {"base": JUTSU_NAME_TABLE, "entries": JUTSU_NAME_COUNT},
            "training": {"base": TRAINING_NAME_TABLE, "entries": TRAINING_NAME_COUNT},
            "ninjutsu_item": {"base": NINJUTSU_NAME_TABLE, "entries": NINJUTSU_NAME_COUNT},
        },
        "header_fields": [
            {
                "offset": off,
                "size": size,
                "key": key,
                "instance_offset": target,
                "meaning": meaning,
                "evidence": evidence,
                "resolved": evidence is not None,
            }
            for off, size, key, target, meaning, evidence in HEADER_FIELDS
        ],
        "jutsu_list": {
            "template_offset": JUTSU_OFFSET,
            "count": JUTSU_COUNT,
            "instance_offset": JUTSU_TARGET,
            "layout": "(id u8, value u8, unlock_level u8, pad u8)",
            "id_table": JUTSU_NAME_TABLE,
            "evidence": "0x0806D4F6 / 0x08089A0C / 0x08089DD8",
        },
        "training_list": {
            "template_offset": TRAINING_OFFSET,
            "count": TRAINING_COUNT,
            "instance_offset": TRAINING_TARGET,
            "layout": "(id u8, value u8, unlock_level u8, pad u8)",
            "id_table": TRAINING_NAME_TABLE,
            "evidence": "0x0806D540 / 0x08089A74 / 0x08089DF0",
        },
        "items": {
            "template_offset": ITEMS_OFFSET,
            "count": ITEMS_COUNT,
            "id_table": NINJUTSU_NAME_TABLE,
            "evidence": "0x0806D590 / 0x0806D596 (0x0808FA34)",
        },
        "skills16": {
            "base": SKILLS16_BASE,
            "stride": SKILLS16_STRIDE,
            "fields": [
                {"u16_index": i, "key": key, "meaning": meaning, "evidence": ev,
                 "resolved": ev is not None}
                for i, key, meaning, ev in SKILLS16_FIELDS
            ],
        },
        "jutsu_record_table": {
            "base": JUTSU_RECORD_BASE,
            "stride": JUTSU_RECORD_STRIDE,
            "count": JUTSU_RECORD_COUNT,
            "reading": "16-byte records (NOT a u32 pointer table)",
            "index": "jutsu id (same space as the jutsu name table)",
            "evidence": "0x0809457C / 0x08094580 / 0x08094592",
            "fields": [
                {"offset": rel, "size": size, "key": key, "meaning": meaning,
                 "evidence": evidence, "resolved": evidence is not None}
                for rel, size, key, meaning, evidence in JUTSU_RECORD_FIELDS
            ],
        },
        "perk_table_0x5459C8": {
            "base": PERK_BASE,
            "stride": PERK_STRIDE,
            "layout": "(type u8, pad u8, base u16, pad u16, growth u16, pad u16)",
            "evidence": "0x0806D6E0 / 0x0806D6E8",
        },
        "field_semantics": split,
        "field_distribution": field_distribution(templates),
        "segment_statistics": segment_statistics(templates),
        "jutsu_records": read_jutsu_records(rom),
        "self_check_problems": problems,
        "characters": templates,
    }

    text = render_text(templates, args, problems)
    if args.json:
        write_json(args.json, report)
        print(f"JSON report written to: {args.json}")
    if args.out:
        write_text(args.out, text)
        print(f"Text report written to: {args.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(text, end="")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
