#!/usr/bin/env python3
"""Synthetic fixture round-trip: prove a table's format by writing known
content and reading it back.

Why
---
Most of our tables are "we can read bytes out of it, but we cannot say what
the game does with them".  Waiting for dynamic verification is expensive
(and currently blocked on an mGBA build).  But the *format* of a table can be
proven without the game at all:

    write content of known meaning -> point the game at it -> read it back
    with our production reader -> the read must equal the write

If our reader recovers exactly what we wrote, the layout hypothesis is proven.
This does **not** prove the game uses the field the way we think (that stays
a dynamic-verification question), but it removes "we guessed the layout" from
the table of open problems.

Each fixture works on a copy of the base ROM and leaves the result in
`build/` for inspection, so nothing here can damage the real ROM.

Usage:
    python tools/synthetic_fixture.py
    python tools/synthetic_fixture.py --fixture battle_rules
    python tools/synthetic_fixture.py --json build/synthetic-fixture.json
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

import decode_story_script as ds  # noqa: E402
import extract_battle_tables as ebt  # noqa: E402
import extract_rewards as er  # noqa: E402
from tools import text_codec  # noqa: E402

BASE = 0x08000000
FREE_SPACE = 0x5DFBEC          # first 0xFF-filled byte after all game data

# ---------------------------------------------------------------- helpers


def free_space_claim(rom: bytearray, size: int) -> int:
    """Reserve `size` bytes of 0xFF-filled tail space; return its offset."""
    if rom[FREE_SPACE:FREE_SPACE + size] != b"\xFF" * size:
        raise AssertionError(
            f"0x{FREE_SPACE:X} is not free space any more - "
            "pick another tail offset"
        )
    return FREE_SPACE


def write_text(rom: bytearray, offset: int, text: str, mapping) -> int:
    """Write a font-coded, NUL-terminated string; return bytes written."""
    raw = text_codec.encode(text, "font", mapping) + b"\x00"
    rom[offset:offset + len(raw)] = raw
    return len(raw)


def u32(rom: bytearray, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def put_u32(rom: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", rom, offset, value)


# ---------------------------------------------------------------- fixtures

def fixture_story_before(rom: bytearray, mapping) -> list[dict]:
    """Story script VM: root-table pointer + instruction lengths + text.

    A synthetic script is appended to free space, the `before` root table of
    scene 1 is pointed at it, and the production VM decoder must read back
    exactly the text we wrote.
    """
    text = "合成夹具：剧情脚本"
    script = bytearray()
    script += bytes([0x02, 0x00, 0x01, 0x01])   # dialog box: flag, char, expr
    script += bytes([0x01])                      # text instruction
    script += text_codec.encode(text, "font", mapping)
    script += b"\x00"                           # text terminator
    script += bytes([0x00])                     # end of script

    off = free_space_claim(rom, len(script))
    rom[off:off + len(script)] = script
    root_slot = 0x060C74 + 1 * 4                 # before-root of scene 1
    put_u32(rom, root_slot, BASE + off)

    checks: list[dict] = []

    pointer_ok = u32(rom, root_slot) == BASE + off
    checks.append({
        "check": "root table entry points at the synthetic script",
        "expected": hex(BASE + off), "actual": hex(u32(rom, root_slot)),
        "pass": pointer_ok,
    })

    nodes, issues = ds.walk(rom, [off], mapping)
    checks.append({
        "check": "VM walk reports no issue",
        "expected": "[]", "actual": json.dumps(issues, ensure_ascii=False),
        "pass": not issues,
    })

    texts = [n.text for n in nodes.values() if n.text is not None]
    checks.append({
        "check": "decoded text equals the authored text",
        "expected": text,
        "actual": texts[0] if texts else None,
        "pass": bool(texts) and texts[0] == text,
    })

    ops = sorted({n.op for n in nodes.values()})
    checks.append({
        "check": "decoded opcodes are the ones we wrote (0x02, 0x01, 0x00)",
        "expected": [0, 1, 2], "actual": ops,
        "pass": ops == [0, 1, 2],
    })
    return checks


def fixture_battle_rules(rom: bytearray, mapping) -> list[dict]:
    """Battle win/lose condition table `0x594758`.

    A synthetic rules entry is written over stage 40 sub 0, including a
    description text placed in free space, and the production extractor must
    read back every field.
    """
    stage, sub = 40, 0
    base = ebt.RULES + stage * ebt.RULE_STRIDE + sub * ebt.RULE_SUB_STRIDE
    description = "合成夹具：胜利条件"

    text_off = free_space_claim(rom, 64)
    write_text(rom, text_off, description, mapping)

    rom[base] = 42                                   # turn limit
    for g in range(2):
        for i in range(4):
            q = base + 4 + g * 32 + i * 8
            rom[q + 0] = 0 if i else (1 + g)          # rule type
            rom[q + 1] = g                            # parameter a
            rom[q + 2] = 7                            # parameter b
            rom[q + 3] = 3                            # parameter c
            put_u32(rom, q + 4, BASE + text_off if i == 0 else 0)

    rules = ebt.extract_rules(rom, mapping)
    entry = next((r for r in rules if r["stage"] == stage and r["sub"] == sub), None)
    checks: list[dict] = []

    checks.append({
        "check": "entry is present",
        "expected": "found", "actual": "found" if entry else "missing",
        "pass": entry is not None,
    })
    if entry is None:
        return checks

    checks.append({
        "check": "turn limit",
        "expected": 42, "actual": entry["turn_limit"],
        "pass": entry["turn_limit"] == 42,
    })
    g0 = entry["groups"][0]
    checks.append({
        "check": "group 0 rule 0 type",
        "expected": 1, "actual": g0[0]["type"],
        "pass": g0[0]["type"] == 1,
    })
    checks.append({
        "check": "group 0 rule 0 parameters a/b/c",
        "expected": [0, 7, 3], "actual": [g0[0]["a"], g0[0]["b"], g0[0]["c"]],
        "pass": [g0[0]["a"], g0[0]["b"], g0[0]["c"]] == [0, 7, 3],
    })
    checks.append({
        "check": "group 0 rule 0 description text",
        "expected": description, "actual": g0[0]["text"],
        "pass": g0[0]["text"] == description,
    })
    g1 = entry["groups"][1]
    checks.append({
        "check": "group 1 rule 0 type (lose group)",
        "expected": 2, "actual": g1[0]["type"],
        "pass": g1[0]["type"] == 2,
    })
    return checks


def fixture_battle_actors(rom: bytearray, mapping) -> list[dict]:
    """Battle configuration `0x5461C4` (actor slots + map objects)."""
    stage, sub = 40, 0
    base = ebt.ACTORS + stage * ebt.ACTOR_STRIDE + sub * ebt.ACTOR_SUB_STRIDE
    slot0 = base + 4
    rom[slot0 + 0] = 7      # character id
    rom[slot0 + 1] = 0      # side
    rom[slot0 + 2] = 12     # x
    rom[slot0 + 3] = 9      # y
    rom[slot0 + 4] = 3      # facing
    rom[slot0 + 15] = 5     # level
    obj0 = base + ebt.ACTOR_OBJECTS
    rom[obj0 + 0] = 1       # object type: 忍具
    rom[obj0 + 1] = 3       # target
    rom[obj0 + 2] = 6       # x
    rom[obj0 + 3] = 8       # y

    actors = ebt.extract_actors(rom, mapping)
    entry = next((a for a in actors if a["stage"] == stage and a["sub"] == sub), None)
    checks: list[dict] = []
    checks.append({
        "check": "entry is present",
        "expected": "found", "actual": "found" if entry else "missing",
        "pass": entry is not None,
    })
    if entry is None:
        return checks

    slot = entry["actors"][0]
    checks.append({
        "check": "slot 0 id/side/x/y/facing/level",
        "expected": [7, 0, 12, 9, 3, 5],
        "actual": [slot["id"], slot["side"], slot["x"], slot["y"],
                   slot["facing"], slot["level"]],
        "pass": [slot["id"], slot["side"], slot["x"], slot["y"],
                 slot["facing"], slot["level"]] == [7, 0, 12, 9, 3, 5],
    })
    checks.append({
        "check": "slot 0 name resolved from the character name table",
        "expected": "旗木卡卡西", "actual": slot["name"],
        "pass": slot["name"] == "旗木卡卡西",
    })
    obj = entry["objects"][0]
    checks.append({
        "check": "map object 0 type/target/x/y",
        "expected": [1, 3, 6, 8],
        "actual": [obj["type"], obj["target"], obj["x"], obj["y"]],
        "pass": [obj["type"], obj["target"], obj["x"], obj["y"]] == [1, 3, 6, 8],
    })
    return checks


def fixture_reward_entry(rom: bytearray, mapping) -> list[dict]:
    """Reward table `0x59EAE0` — one synthetic 24-byte entry."""
    gold, bonus, tier = 321, 123, 7
    items = [(3, 2), (40, 1)]
    raw = bytearray(24)
    struct.pack_into("<HHH", raw, 0, gold, bonus, tier)
    for i, (item_id, count) in enumerate(items):
        struct.pack_into("<H", raw, 6 + i * 2, (item_id << 8) | count)
    rom[er.REWARDS:er.REWARDS + len(raw)] = raw

    entries = er.read_entries(rom, mapping)
    entry = entries[0]
    checks: list[dict] = []
    checks.append({
        "check": "gold", "expected": gold, "actual": entry["gold"],
        "pass": entry["gold"] == gold,
    })
    checks.append({
        "check": "bonus", "expected": bonus, "actual": entry["bonus"],
        "pass": entry["bonus"] == bonus,
    })
    checks.append({
        "check": "tier", "expected": tier, "actual": entry["tier"],
        "pass": entry["tier"] == tier,
    })
    decoded = [(it["item_id"], it["low"]) for it in entry["items"]]
    checks.append({
        "check": "reward items decode back to (id, count)",
        "expected": items, "actual": decoded,
        "pass": decoded == items,
    })
    names = [it["name"] for it in entry["items"]]
    checks.append({
        "check": "reward item names resolve in the 忍具 name table",
        "expected": "two non-empty names",
        "actual": names,
        "pass": all(names) and len(names) == 2,
    })
    return checks


FIXTURES = {
    "story_before": fixture_story_before,
    "battle_rules": fixture_battle_rules,
    "battle_actors": fixture_battle_actors,
    "reward_entry": fixture_reward_entry,
}

# Fixtures that live in their own module so the set can grow in parallel.
try:
    from tools.fixtures_extended import EXTRA_FIXTURES
except Exception:  # pragma: no cover - the extra module is optional
    EXTRA_FIXTURES = {}
FIXTURES.update(EXTRA_FIXTURES)


def run_fixture(name: str, rom_path: pathlib.Path, mapping,
                out_dir: pathlib.Path) -> dict:
    rom = bytearray(rom_path.read_bytes())
    before = bytes(rom)
    checks = FIXTURES[name](rom, mapping)
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = out_dir / f"synthetic-fixture-{name}.gba"
    fixture_path.write_bytes(bytes(rom))
    changed = sum(1 for a, b in zip(before, rom) if a != b)
    return {
        "fixture": name,
        "checks": checks,
        "passed": all(c["pass"] for c in checks),
        "changed_bytes_vs_base": changed,
        "fixture_rom": str(fixture_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default=None)
    ap.add_argument("--fixture", choices=sorted(FIXTURES), action="append")
    ap.add_argument("--out-dir", default="build/synthetic-fixtures")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    mapping, _ = text_codec.load_mapping(rom_path)
    names = args.fixture or sorted(FIXTURES)
    out_dir = REPO / args.out_dir

    results = [run_fixture(n, rom_path, mapping, out_dir) for n in names]
    report = {
        "rom": str(rom_path),
        "fixtures": results,
        "all_passed": all(r["passed"] for r in results),
    }
    if args.json:
        path = pathlib.Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"base ROM: {rom_path.name}")
    print()
    for r in results:
        print(f"[{r['fixture']}]  "
              f"{sum(c['pass'] for c in r['checks'])}/{len(r['checks'])} checks"
              f"  (changed {r['changed_bytes_vs_base']} bytes vs base)")
        for c in r["checks"]:
            flag = "OK  " if c["pass"] else "FAIL"
            print(f"   [{flag}] {c['check']}")
            if not c["pass"]:
                print(f"          expected: {c['expected']!r}")
                print(f"          actual  : {c['actual']!r}")
    print()
    print("RESULT:", "PASS - every fixture read back exactly what was written"
          if report["all_passed"] else "FAIL")
    print("note  : this proves the table *format*, not the game's use of it")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
