#!/usr/bin/env python3
"""Extract the Konoha Senki battle data tables.

Three tables the editor never had decoded before:

  rules   0x594758  victory / defeat conditions, per stage and per sub-config
  mission 0x348DAC  index into three text tables (title / description / hint)
  actors  0x5461C4  the 12 character slots of each stage and sub-config

Layout
------
rules  entry = 0x594758 + stage*0xCC + sub*0x44
           +0x00 u8   turn limit
           +0x04 group 0: 4 rules x 8 bytes   (type, a, b, c, u32 text ptr)
           +0x24 group 1: 4 rules x 8 bytes
       a rule is 8 bytes: type u8, a u8, b u8, c u8, text pointer u32

mission index = rom[0x348DAC + stage] + sub   (u8 table, 3 entries per stage)
mission text  = table[0x59AA5C | 0x59D214 | 0x59E920][index*4]  -> ROM pointer

actors entry = 0x5461C4 + stage*0x1AAC + sub*0x8E4
           +0x00 .. +0x03  header
           +0x04 + i*0xB8  12 character slots (id, side, x, y, facing, level, ...)
           +0x8A4          16 map objects x 4 bytes (type, target, x, y)

Usage:
    python tools/extract_battle_tables.py
    python tools/extract_battle_tables.py --json build/battle_tables.json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import konoha_font as kf  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = 0x08000000

RULES = 0x594758
RULE_STRIDE = 0xCC
RULE_SUB_STRIDE = 0x44
MISSION_INDEX = 0x348DAC
MISSION_TABLES = (("title", 0x59AA5C), ("description", 0x59D214), ("hint", 0x59E920))
ACTORS = 0x5461C4
ACTOR_STRIDE = 0x1AAC
ACTOR_SUB_STRIDE = 0x8E4
ACTOR_SLOT = 0xB8
ACTOR_OBJECTS = 0x8A4

BATTLE_STAGES = 46
SUBS = 3

RULE_TYPE_NAMES = {
    0: "unknown",
    1: "turn-based",
    2: "turn-based-alt",
    3: "character-alive",
    4: "unknown-4",
    5: "side-based",
    6: "item-based",
    7: "side-based-7",
    8: "side-based-8",
    9: "side-based-9",
    10: "arrive-at-position (third-party extension, not native)",
}


def u32(rom: bytes, p: int) -> int:
    return struct.unpack_from("<I", rom, p)[0]


def u16(rom: bytes, p: int) -> int:
    return struct.unpack_from("<H", rom, p)[0]


def text_at(rom: bytes, ptr: int, mapping: dict[int, str]) -> str:
    off = ptr - BASE
    if not (0 <= off < len(rom)):
        return ""
    text, _ = kf.decode_at(rom, off, mapping)
    return "\n".join(line.rstrip("　") for line in text.split("\n")).rstrip("　")


def extract_rules(rom: bytes, mapping: dict[int, str]) -> list[dict]:
    out = []
    for stage in range(1, BATTLE_STAGES + 1):
        for sub in range(SUBS):
            p = RULES + stage * RULE_STRIDE + sub * RULE_SUB_STRIDE
            if p + RULE_SUB_STRIDE > len(rom):
                continue
            groups = []
            for g in range(2):
                rules = []
                for i in range(4):
                    q = p + 4 + g * 32 + i * 8
                    rtype = rom[q]
                    a, b, c = rom[q + 1], rom[q + 2], rom[q + 3]
                    ptr = u32(rom, q + 4)
                    rules.append({
                        "index": i,
                        "type": rtype,
                        "type_name": RULE_TYPE_NAMES.get(rtype, "unknown"),
                        "a": a, "b": b, "c": c,
                        "text_ptr": f"0x{ptr:08X}",
                        "text": text_at(rom, ptr, mapping),
                    })
                groups.append(rules)
            if any(r["type"] or r["text"] for g in groups for r in g) or rom[p]:
                out.append({
                    "stage": stage, "sub": sub,
                    "turn_limit": rom[p],
                    "groups": groups,
                })
    return out


def extract_missions(rom: bytes, mapping: dict[int, str]) -> list[dict]:
    out = []
    for stage in range(1, BATTLE_STAGES + 1):
        base_idx = rom[MISSION_INDEX + stage]
        for sub in range(SUBS):
            index = base_idx + sub
            entry = {"stage": stage, "sub": sub, "index": index}
            for label, table in MISSION_TABLES:
                ptr = u32(rom, table + index * 4)
                entry[label] = {"ptr": f"0x{ptr:08X}", "text": text_at(rom, ptr, mapping)}
            out.append(entry)
    return out


def extract_actors(rom: bytes, mapping: dict[int, str]) -> list[dict]:
    out = []
    for stage in range(1, BATTLE_STAGES + 1):
        for sub in range(SUBS):
            base = ACTORS + stage * ACTOR_STRIDE + sub * ACTOR_SUB_STRIDE
            slots = []
            for i in range(12):
                q = base + 4 + i * ACTOR_SLOT
                cid = rom[q]
                slots.append({
                    "index": i,
                    "id": cid,
                    "name": kf.read_character_names(rom, mapping).get(cid, "") if cid else "",
                    "side": rom[q + 1],
                    "x": rom[q + 2],
                    "y": rom[q + 3],
                    "facing": rom[q + 4],
                    "level": rom[q + 15],
                })
            objects = []
            for i in range(16):
                q = base + ACTOR_OBJECTS + i * 4
                objects.append({"index": i, "type": rom[q], "target": rom[q + 1],
                                "x": rom[q + 2], "y": rom[q + 3]})
            if any(s["id"] for s in slots) or any(o["type"] for o in objects):
                out.append({"stage": stage, "sub": sub, "actors": slots, "objects": objects})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the full extraction as JSON")
    ap.add_argument("--stage", type=int, help="show one stage in detail")
    ap.add_argument("rom", nargs="?")
    args = ap.parse_args()

    rom_path = pathlib.Path(args.rom) if args.rom else next(REPO.glob("*.gba"))
    rom = rom_path.read_bytes()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    mapping, _ = kf.build_mapping(rom)
    names = kf.read_character_names(rom, mapping)

    rules = extract_rules(rom, mapping)
    missions = extract_missions(rom, mapping)
    actors = extract_actors(rom, mapping)

    print(f"rules   : {len(rules)} stage/sub entries with content")
    print(f"missions: {len(missions)} stage/sub entries")
    print(f"actors  : {len(actors)} stage/sub entries with content")

    type_hist = collections.Counter()
    for entry in rules:
        for g in entry["groups"]:
            for r in g:
                if r["type"] or r["text"]:
                    type_hist[r["type"]] += 1
    print("\nrule type histogram:")
    for t, c in sorted(type_hist.items()):
        print(f"  type {t:2d}  {c:4d}   {RULE_TYPE_NAMES.get(t, 'unknown')}")

    if args.stage:
        print(f"\n=== stage {args.stage} ===")
        for entry in rules:
            if entry["stage"] != args.stage:
                continue
            print(f"  sub {entry['sub']}  turn_limit={entry['turn_limit']}")
            for gi, g in enumerate(entry["groups"]):
                for r in g:
                    if r["type"] or r["text"]:
                        print(f"    g{gi}[{r['index']}] type={r['type']} "
                              f"a={r['a']} b={r['b']} c={r['c']}  {r['text']!r}")
        for entry in missions:
            if entry["stage"] == args.stage:
                print(f"  mission sub{entry['sub']} idx={entry['index']}")
                for label, _ in MISSION_TABLES:
                    print(f"    {label:12s} {entry[label]['text']!r}")
        for entry in actors:
            if entry["stage"] == args.stage:
                print(f"  actors sub{entry['sub']}:")
                for s in entry["actors"]:
                    if s["id"]:
                        print(f"    slot{s['index']:2d} id={s['id']:3d} {s['name']:8s} "
                              f"side={s['side']} x={s['x']} y={s['y']} lvl={s['level']}")

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "rom": rom_path.name,
            "rules": rules, "missions": missions, "actors": actors,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
