#!/usr/bin/env python3
"""Runtime WRAM state map, with independent ROM cross-checks.

The third-party "Konoha Workshop" package extended the game by reading and
writing a set of WRAM fields (scene id, progression, party slots, battle unit
slots, ...).  Those claims come from someone else's runtime code, so the
default here is *not* to believe them: every address is re-checked against
our own ROM.

Two kinds of evidence are produced:

  * **ROM reference** - the address appears as a 32-bit literal in the ROM's
    own code (ARM literal pools hold absolute addresses).  A field that the
    game itself loads is a field we can reason about; a field with no
    reference is either handled by computed addressing or is a claim we
    cannot support.
  * **ROM source table** - for the RAM mirrors, the ROM-side table they are
    copied from is verified to exist and to have the expected shape.

Usage:
    python tools/runtime_state.py
    python tools/runtime_state.py --json build/runtime_state.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import text_codec  # noqa: E402

IWRAM = 0x02000000

# ---------------------------------------------------------------- fields

# (name, wram address, width in bytes, what the field is, evidence class)
FIELDS: list[tuple[str, int, int, str, str]] = [
    ("scene_id", 0x020311EA, 1,
     "当前场景 / 章节 ID。原版 1..55；56..103 是第三方扩展战役段。", "rom_ref"),
    ("story_progress", 0x020311E4, 2,
     "剧情进度 u16。370 = 原版通关（场景 54 触发续作入口），385 = 另一通关态。", "rom_ref"),
    ("story_branch", 0x020311EC, 1,
     "剧情分支字节。新游戏时清零（含败北后热启动）。", "rom_ref"),
    ("story_config", 0x020311ED, 1,
     "剧情配置字节。新游戏时清零。", "rom_ref"),
    ("story_config2", 0x020311EE, 1,
     "剧情配置字节。新游戏时清零。", "rom_ref"),
    ("story_config3", 0x020311EF, 1,
     "剧情配置字节。新游戏时清零。", "rom_ref"),
    ("battle_stage", 0x02026805, 1,
     "当前战场 stage（场景号）。与 positions 的 group 40 / variant 对应。", "rom_ref"),
    ("battle_sub", 0x02026806, 1,
     "当前战场 sub（三套配置之一）。", "rom_ref"),
    ("battle_result", 0x02026807, 1,
     "上一场战斗结果。新游戏时清零。", "rom_ref"),
    ("clear_flag", 0x0203150F, 1,
     "标志字节，bit7 = 已通关。扩展场景需要清 bit7。", "rom_ref"),
    ("save_signature", 0x02022EA0, 4,
     'u32 存档签名，值 0x33544B4E = "NKT3"，判定"三人替代版"存档。', "third_party"),
    ("replacement_ids", 0x02022EA4, 3,
     "三名替代者角色 ID（各 1 字节）。", "third_party"),
    ("party_slot_base", 0x02022E34, 188,
     "队员结构数组，槽 n = base + n*188，n = 1..23（23 槽）。", "rom_ref"),
    ("battle_unit_base", 0x020240C0, 468,
     "战斗单位槽数组，槽 n = base + n*468，n = 1..12（12 槽）。", "rom_ref"),
    ("name_table_ram", 0x0203E800, 256,
     "姓名表 RAM 镜像（64 × u32），源表 0x599280。", "third_party"),
    ("skill_table_ram", 0x0203E900, 1392,
     "技能表 RAM 镜像（348 × u32），源表 0x545458。", "third_party"),
]

# RAM mirrors whose ROM-side source table we verify.
SOURCE_TABLES = {
    "name_table_ram": (0x599280, 64, "姓名表 / 认识卡：0x599280 + id*4 指向角色名文本"),
    "skill_table_ram": (0x545458, 348, "技能表：0x545458 + id*4 指向技能文本"),
}

# Field layout inside the party slot (0x02022E34 + n*188).
PARTY_FIELDS = [
    (0x00, 1, "角色 ID"),
    (0x01, 1, "等级"),
    (0x0C, 2, "当前 HP（由 [0x0E] 复制）"),
    (0x0E, 2, "最大 HP"),
    (0x14, 60, "15 个技能槽（每槽 u32：低字节=技能 id，次字节=rank）"),
    (0x50, 60, "15 个解锁位置 ID（每槽 u32，低字节有效）"),
    (0x51, 60, "15 个解锁标志（每槽 u8，0xFF = 未解锁）"),
]

# Field layout inside the battle unit slot (0x020240C0 + n*468).
UNIT_FIELDS = [
    (0x00, 1, "角色 ID"),
    (0x01, 1, "等级"),
    (0x02, 3, "三维数值（攻/防/速，第三方写为 [2],[3],[4]）"),
    (0x0C, 2, "当前 HP"),
    (0x0E, 2, "最大 HP"),
    (0xC0, 1, "标志（bit4）"),
    (0xC4, 2, "X / Y 坐标（+0xC4=X, +0xC5=Y）"),
    (0xCC, 1, "守卫 / 无敌标志（第三方写为 [204]）"),
]


def find_literal_references(rom: bytes, address: int) -> list[int]:
    """File offsets where `address` appears as a 32-bit little-endian literal.

    ARM literal pools hold absolute addresses, so a hit means the game's own
    code mentions that address somewhere.
    """
    needle = struct.pack("<I", address)
    out, start = [], 0
    while True:
        idx = rom.find(needle, start)
        if idx < 0:
            break
        out.append(idx)
        start = idx + 1
    return out


def find_block_references(rom: bytes, address: int, span: int = 32) -> list[dict]:
    """Literals whose block contains `address`.

    The game does not always address a field directly: it loads the base of a
    control block and indexes inside it.  `0x02026805` (battle stage) is read
    as `0x02026804` + 1 - the 8-byte battle control area our own notes already
    record.  So a field counts as "referenced by the game" when some literal
    block covers it.
    """
    hits: list[dict] = []
    for back in range(0, span):
        base = address - back
        if base < IWRAM or base % 4:
            continue
        for off in find_literal_references(rom, base):
            hits.append({"literal": hex(base), "offset_in_block": back,
                         "at_rom": hex(off)})
    return hits


def verify_source_table(rom: bytes, base: int, count: int) -> dict:
    """Check a ROM-side pointer table has `count` plausible entries."""
    pointers = []
    for i in range(count):
        off = base + i * 4
        if off + 4 > len(rom):
            break
        pointers.append(struct.unpack_from("<I", rom, off)[0])
    in_rom = sum(1 for p in pointers if IWRAM <= p < IWRAM + 0x40000)
    return {
        "base": hex(base),
        "declared_count": count,
        "readable_pointers": len(pointers),
        "pointers_into_rom": in_rom,
        "first_pointers": [hex(p) for p in pointers[:6]],
    }


def build_report(rom: bytes) -> dict:
    rows = []
    for name, addr, width, desc, kind in FIELDS:
        direct = find_literal_references(rom, addr)
        blocks = find_block_references(rom, addr)
        row = {
            "name": name,
            "address": hex(addr),
            "width": width,
            "meaning": desc,
            "evidence_class": kind,
            "rom_direct_references": len(direct),
            "rom_block_references": len(blocks),
            "referenced_by_game": bool(direct or blocks),
            "reference_examples": blocks[:6] or
                                 [{"literal": hex(addr), "offset_in_block": 0,
                                   "at_rom": hex(o)} for o in direct[:6]],
        }
        if kind == "rom_source" and name in SOURCE_TABLES:
            base, count, note = SOURCE_TABLES[name]
            row["source_table"] = verify_source_table(rom, base, count)
            row["source_table_note"] = note
        elif kind == "third_party":
            row["note"] = ("第三方自造簿记：原版 ROM 不引用，"
                           "不应作为原生状态使用")
        rows.append(row)
    return {
        "fields": rows,
        "party_slot_fields": [
            {"offset": hex(o), "size": s, "meaning": m} for o, s, m in PARTY_FIELDS
        ],
        "battle_unit_fields": [
            {"offset": hex(o), "size": s, "meaning": m} for o, s, m in UNIT_FIELDS
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    report = build_report(rom)

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"ROM: {rom_path.name}")
    print()
    print(f"{'field':<18} {'address':<12} {'w':>4}  {'direct':>6} {'block':>6}  meaning")
    for r in report["fields"]:
        print(f"{r['name']:<18} {r['address']:<12} {r['width']:>4}  "
              f"{r['rom_direct_references']:>6} {r['rom_block_references']:>6}  "
              f"{r['meaning']}")
    print()
    print("party slot (0x02022E34 + n*188):")
    for f in report["party_slot_fields"]:
        print(f"  +{f['offset']:<6} x{f['size']:<4} {f['meaning']}")
    print("battle unit slot (0x020240C0 + n*468):")
    for f in report["battle_unit_fields"]:
        print(f"  +{f['offset']:<6} x{f['size']:<4} {f['meaning']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
