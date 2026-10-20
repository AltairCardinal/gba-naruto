#!/usr/bin/env python3
"""Battle map object system: pickup records, dispatch table, background table.

The battle configuration (`0x5461C4 + stage*0x1AAC + sub*0x8E4`) ends with 16
map-object records at `+0x8A4`, 4 bytes each: `type, target, x, y`.  This tool
decodes the whole object system against our ROM.

What is verified here (not copied):
  * the native pickup dispatch table at `0x815E4` - how many handlers the game
    really has;
  * the three name tables the pickup windows read (忍具 / 强化素材 / 认识卡);
  * the story background table `0x59903C + id*16` (gfx, palette, tilemap, flag);
  * how many of the 16 records of a given stage are actually occupied.

The "13 mechanisms" naming used by the third-party editor is a *taxonomy on
top* of the native dispatch table and is reported separately, so the two are
not confused.

Usage:
    python tools/object_tables.py
    python tools/object_tables.py --json build/object_tables.json
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

# --- native tables -------------------------------------------------------
DISPATCH_TABLE = 0x815E4          # pickup dispatch pointers
DISPATCH_MAX = 16
BACKGROUND_TABLE = 0x59903C       # story background table, 16 bytes per id
BACKGROUND_IDS = 16

ACTOR_TABLE = 0x5461C4
GROUP_STRIDE = 0x1AAC
SUB_STRIDE = 0x8E4
OBJECT_OFFSET = 0x8A4
OBJECT_COUNT = 16

NAME_TABLES = {
    "ninjutsu": (0x599634, 93),   # 忍具名
    "material": (0x5A7E8C, 16),   # 强化素材名
    "character": (0x599280, 62),  # 人物名 / 认识卡
}

# The 8 record types, as the game treats them.
OBJECT_TYPES = {
    0: "空位（不放置）",
    1: "忍具",
    2: "强化素材",
    3: "专属修行卷轴",
    4: "认识卡（人物图鉴）",
    5: "机关宝箱",
    6: "特殊机关（卷轴外观）",
    7: "剧情物件",
}

# Types 3 and 4 only appear when their precondition holds, so the "item number"
# the game reports is not the same as the record index.
CONDITIONAL_TYPES = {3, 4}

# Naming overlay used by the third-party editor for types 5/6/7.
THIRD_PARTY_MECHANISM_NAMES = {
    1: "开门机关", 2: "空箱 / 开门分支", 3: "停止傀儡的机关",
    4: "开门机关（另一组）", 5: "空箱 / 开门分支（另一组）",
    6: "停止傀儡的机关（另一组）", 7: "密书", 8: "空箱 / 密书分支",
    9: "甘薯（收集计数）", 10: "发现奖励（强化剂剧情）", 11: "空事件",
    12: "宝箱教学", 13: "认识卡教学",
}


def read_name_table(rom: bytes, base: int, count: int, mapping) -> list[str]:
    names = []
    for i in range(1, count + 1):
        ptr = struct.unpack_from("<I", rom, base + i * 4)[0] - 0x08000000
        if not (0 <= ptr < len(rom)):
            names.append("")
            continue
        text, _ = text_codec.decode_tokens(rom, ptr, mapping)
        names.append(text.replace("\n", "").strip())
    return names


def read_dispatch(rom: bytes) -> list[dict]:
    out = []
    for i in range(DISPATCH_MAX):
        value = struct.unpack_from("<I", rom, DISPATCH_TABLE + i * 4)[0]
        out.append({
            "index": i,
            "offset": DISPATCH_TABLE + i * 4,
            "value": value,
            "is_rom_pointer": 0x08000000 <= value < 0x09000000,
        })
    native = [d for d in out if d["is_rom_pointer"]]
    # The table ends where the pointers stop.
    end = 0
    for i, d in enumerate(out):
        if d["is_rom_pointer"]:
            end = i + 1
        else:
            break
    return out, end, len(native)


def read_backgrounds(rom: bytes) -> list[dict]:
    out = []
    for i in range(BACKGROUND_IDS):
        p = BACKGROUND_TABLE + i * 16
        ptrs = [struct.unpack_from("<I", rom, p + k * 4)[0] for k in range(4)]
        out.append({
            "id": i,
            "offset": p,
            "gfx": ptrs[0], "palette": ptrs[1], "tilemap": ptrs[2],
            "flag_8bpp": ptrs[3],
            "valid": any(0x08000000 <= x < 0x09000000 for x in ptrs[:3]),
        })
    return out


def read_objects(rom: bytes, stage: int, sub: int) -> list[dict]:
    base = ACTOR_TABLE + stage * GROUP_STRIDE + sub * SUB_STRIDE
    out = []
    for i in range(OBJECT_COUNT):
        p = base + OBJECT_OFFSET + i * 4
        otype, target, x, y = rom[p], rom[p + 1], rom[p + 2], rom[p + 3]
        out.append({
            "index": i, "offset": p, "type": otype, "target": target,
            "x": x, "y": y, "occupied": otype != 0,
            "type_name": OBJECT_TYPES.get(otype, f"未知类型 {otype}"),
            "conditional": otype in CONDITIONAL_TYPES,
        })
    return out


def object_name(rec: dict, names: dict[str, list[str]]) -> str:
    t, target = rec["type"], rec["target"]
    if t == 1 and 1 <= target <= len(names["ninjutsu"]):
        return names["ninjutsu"][target - 1]
    if t == 2 and 1 <= target <= len(names["material"]):
        return names["material"][target - 1]
    if t == 3 and 1 <= target <= len(names["character"]):
        return f"{names['character'][target - 1]}的专属修行卷轴"
    if t == 4 and 1 <= target <= len(names["character"]):
        return f"{names['character'][target - 1]}的认识卡"
    if t in (5, 6, 7):
        return THIRD_PARTY_MECHANISM_NAMES.get(target, f"机关 {target}")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--stage", type=int, default=40)
    ap.add_argument("--sub", type=int, default=0)
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()
    mapping, _ = text_codec.load_mapping(rom_path)

    names = {k: read_name_table(rom, base, count, mapping)
             for k, (base, count) in NAME_TABLES.items()}
    dispatch, dispatch_len, native_ptrs = read_dispatch(rom)
    backgrounds = read_backgrounds(rom)
    objects = read_objects(rom, args.stage, args.sub)
    for rec in objects:
        rec["name"] = object_name(rec, names)

    report = {
        "rom": str(rom_path),
        "dispatch_table": {
            "address": hex(DISPATCH_TABLE),
            "native_handler_count": dispatch_len,
            "pointers_in_range": native_ptrs,
            "entries": dispatch,
        },
        "background_table": {
            "address": hex(BACKGROUND_TABLE),
            "stride": 16,
            "entries": backgrounds,
        },
        "name_tables": {
            k: {"address": hex(base), "count": count,
                "sample": names[k][:6]}
            for k, (base, count) in NAME_TABLES.items()
        },
        "object_types": OBJECT_TYPES,
        "conditional_types": sorted(CONDITIONAL_TYPES),
        "third_party_mechanism_names": THIRD_PARTY_MECHANISM_NAMES,
        "sample_stage": {"stage": args.stage, "sub": args.sub,
                         "objects": objects},
    }
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"ROM: {rom_path.name}")
    print()
    print(f"native pickup dispatch @ {hex(DISPATCH_TABLE)}: "
          f"{dispatch_len} handlers (entries 0..{dispatch_len - 1})")
    for d in dispatch[:dispatch_len]:
        print(f"  [{d['index']}] -> {d['value']:#010x}")
    print(f"  (third-party editor names {len(THIRD_PARTY_MECHANISM_NAMES)} "
          f"mechanisms on top of this)")
    print()
    valid_bg = [b for b in backgrounds if b["valid"]]
    print(f"story background table @ {hex(BACKGROUND_TABLE)} (16 bytes/id): "
          f"{len(valid_bg)} valid ids -> {[b['id'] for b in valid_bg]}")
    print()
    for key, (base, count) in NAME_TABLES.items():
        print(f"name table {hex(base)} ({count}): {names[key][:5]}")
    print()
    occ = [r for r in objects if r["occupied"]]
    print(f"stage {args.stage} sub {args.sub}: {len(occ)}/16 records occupied")
    for r in objects:
        if r["occupied"]:
            flag = " (conditional)" if r["conditional"] else ""
            print(f"  [{r['index']:2d}] type={r['type']} {r['type_name']:<12} "
                  f"target={r['target']:<3} ({r['x']},{r['y']}) "
                  f"{r['name']}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
