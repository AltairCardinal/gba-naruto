#!/usr/bin/env python3
"""Decode the Konoha Senki story script VM.

The game drives story scenes, battle setup and conditional events from a
bytecode VM. Every scene has up to four roots:

    before  0x060C74  pre-battle story script
    after   0x060D54  post-battle story script
    logic   0x060E34  in-battle event logic
    events  0x060EF0  in-battle event table

Each root table holds one u32 ROM pointer per scene id (file offsets in ROM).

This tool walks the bytecode into a node graph and extracts the dialogue.
Text is rendered with tools/konoha_font.py - the game's own double-byte font
codes, *not* Shift-JIS.

Usage:
    python tools/decode_story_script.py --scene 1
    python tools/decode_story_script.py --scene 1 --raw
    python tools/decode_story_script.py --all --out build/story_scripts.json
    python tools/decode_story_script.py --stats
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import konoha_font as kf  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
BASE = 0x08000000

ROOT_TABLES = {
    "before": 0x060C74,
    "after": 0x060D54,
    "logic": 0x060E34,
    "events": 0x060EF0,
}
STORY_SCENES = 55
BATTLE_SCENES = 46

# Instruction length in bytes. Unknown opcodes abort the walk of that branch.
LENGTHS = {
    0: 1, 2: 4, 3: 2, 4: 4, 7: 5, 8: 2, 9: 2, 10: 2, 11: 6, 12: 6, 13: 5,
    14: 3, 15: 2, 16: 1, 17: 2, 18: 5, 20: 3, 21: 8, 22: 2, 23: 4, 24: 4,
    25: 4, 26: 3, 27: 3, 28: 3, 29: 3, 30: 2, 31: 2, 33: 5, 34: 4, 35: 3,
    50: 5, 51: 2, 52: 8, 53: 9, 54: 8, 55: 3, 56: 7, 57: 6,
}

# Opcodes carrying a single branch pointer, and the offset of that pointer.
BRANCH = {11: 2, 12: 2, 21: 4, 52: 4, 53: 5, 54: 4, 56: 3, 57: 2}
# Opcodes carrying a pointer at +1 only.
SINGLE_TARGET = (7, 13, 50)
# Opcodes whose payload starts with a text run, and where that run starts.
TEXT_OPS = {1: 1, 5: 2, 32: 2}

OP_NAMES = {
    0: "end", 2: "portrait", 3: "narration", 4: "?", 5: "menu-text",
    6: "branch2", 7: "jump", 8: "?", 9: "?", 10: "?", 11: "branch",
    12: "branch", 13: "call", 14: "?", 15: "?", 16: "?", 17: "?", 18: "?",
    20: "?", 21: "init-jump", 22: "?", 23: "?", 24: "?", 25: "?", 26: "next-scene",
    27: "music", 28: "?", 29: "?", 30: "enter-battle", 31: "?", 32: "dialogue",
    33: "?", 34: "add-member", 35: "?", 50: "event-entry", 51: "?",
    52: "condition", 53: "condition", 54: "presence", 55: "set-flag",
    56: "test-flag", 57: "config-check",
}


def u32(rom: bytes, p: int) -> int:
    return struct.unpack_from("<I", rom, p)[0]


def root_pointer(rom: bytes, table: int, scene: int) -> int | None:
    ptr = u32(rom, table + scene * 4)
    if ptr == 0:
        return None
    off = ptr - BASE
    return off if 0 <= off < len(rom) else None


class Node:
    __slots__ = ("offset", "op", "length", "targets", "text", "text2", "raw")

    def __init__(self, offset: int, op: int, length: int):
        self.offset = offset
        self.op = op
        self.length = length
        self.targets: list[int] = []
        self.text: str | None = None
        self.text2: str | None = None
        self.raw = b""

    def as_dict(self) -> dict:
        return {
            "offset": self.offset,
            "rom_address": f"0x{self.offset + BASE:08X}",
            "op": self.op,
            "op_name": OP_NAMES.get(self.op, "?"),
            "length": self.length,
            "targets": [f"0x{t + BASE:08X}" for t in self.targets],
            "text": self.text,
            "text2": self.text2,
            "raw": self.raw.hex(" "),
        }


def walk(rom: bytes, roots: list[int], mapping: dict[int, str]) -> tuple[dict[int, Node], list[str]]:
    """Walk the bytecode into a node graph; returns (nodes, issues)."""
    nodes: dict[int, Node] = {}
    issues: list[str] = []
    stack = [r for r in roots if 0 <= r < len(rom)]
    budget = 200000
    while stack and budget > 0:
        budget -= 1
        p = stack.pop()
        if p in nodes:
            continue
        op = rom[p]
        # Text instructions and the two-branch instruction derive their length
        # from the data itself, so they are NOT in the LENGTHS table.
        if op in TEXT_OPS or op == 19 or op == 6:
            length = None
        else:
            length = LENGTHS.get(op)
            if length is None:
                issues.append(f"unknown opcode 0x{op:02X} at 0x{p + BASE:08X}")
                continue
        if length is not None and p + length > len(rom):
            issues.append(f"opcode 0x{op:02X} at 0x{p + BASE:08X} runs past ROM end")
            continue
        node = Node(p, op, length or 0)
        node.raw = rom[p : p + (length or 0)]

        if op in TEXT_OPS:
            text, nxt = kf.decode_at(rom, p + TEXT_OPS[op], mapping)
            node.text = text
            node.length = nxt - p
        elif op == 19:
            text, nxt = kf.decode_at(rom, p + 4, mapping)
            node.text = text
            end = nxt
            if rom[p + 2]:
                text2, nxt2 = kf.decode_at(rom, nxt + 1, mapping)
                node.text2 = text2
                end = nxt2
            node.length = end - p

        if op == 6:
            node.targets = [u32(rom, p + 1) - BASE, u32(rom, p + 5) - BASE]
            node.length = 9
        elif op in SINGLE_TARGET:
            node.targets = [u32(rom, p + 1) - BASE]
        elif op in BRANCH:
            node.targets = [u32(rom, p + BRANCH[op]) - BASE]

        nodes[p] = node
        if node.length <= 0:
            issues.append(f"opcode 0x{op:02X} at 0x{p + BASE:08X} has zero length")
            continue

        for t in node.targets:
            if not (0 <= t < len(rom)):
                issues.append(f"branch out of ROM at 0x{p + BASE:08X}")
                continue
            stack.append(t)
        if op not in (0, 6, 7):
            stack.append(p + node.length)
    if budget <= 0:
        issues.append("walk budget exhausted")
    return nodes, issues


def validate(nodes: dict[int, Node]) -> list[str]:
    """Every branch target must land on an instruction boundary."""
    bad = []
    for node in nodes.values():
        for t in node.targets:
            if t not in nodes:
                bad.append(f"0x{node.offset + BASE:08X} -> 0x{t + BASE:08X} is not an instruction start")
    return bad


def collect_text(nodes: dict[int, Node]) -> list[dict]:
    """Pull the dialogue lines out of a node graph, in offset order."""
    out = []
    for node in sorted(nodes.values(), key=lambda n: n.offset):
        if node.text:
            out.append({
                "rom_address": f"0x{node.offset + BASE:08X}",
                "op": node.op,
                "op_name": OP_NAMES.get(node.op, "?"),
                "text": node.text,
            })
    return out


def scene_roots(rom: bytes, scene: int) -> dict[str, int]:
    roots = {}
    for name, table in ROOT_TABLES.items():
        if name in ("logic", "events") and scene > BATTLE_SCENES:
            continue
        p = root_pointer(rom, table, scene)
        if p is not None:
            roots[name] = p
    return roots


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", type=int, help="scene id to decode (1..55)")
    ap.add_argument("--all", action="store_true", help="decode every scene")
    ap.add_argument("--raw", action="store_true", help="dump raw node bytes")
    ap.add_argument("--stats", action="store_true", help="opcode histogram and issues")
    ap.add_argument("--out", help="write JSON report here")
    ap.add_argument("rom", nargs="?", help="ROM path (default: repo root .gba)")
    args = ap.parse_args()

    rom_path = pathlib.Path(args.rom) if args.rom else next(REPO.glob("*.gba"))
    rom = rom_path.read_bytes()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    mapping, font_report = kf.build_mapping(rom)
    print(f"font: {len(mapping)} codes, {font_report['catalog_segments_matched']}"
          f"/{font_report['catalog_segments_total']} segments matched", file=sys.stderr)

    scenes = range(1, STORY_SCENES + 1) if (args.all or args.scene is None) else [args.scene]
    report: dict = {"rom": rom_path.name, "font": font_report, "scenes": {}}
    all_issues: list[str] = []
    hist: dict[str, int] = {}

    for scene in scenes:
        roots = scene_roots(rom, scene)
        if not roots:
            continue
        merged: dict[int, Node] = {}
        issues: list[str] = []
        for name, root in roots.items():
            nodes, iss = walk(rom, [root], mapping)
            merged.update(nodes)
            issues += [f"[{name}] {m}" for m in iss]
        bad = validate(merged)
        issues += bad
        all_issues += issues
        for n in merged.values():
            key = f"0x{n.op:02X} {OP_NAMES.get(n.op, '?')}"
            hist[key] = hist.get(key, 0) + 1
        report["scenes"][str(scene)] = {
            "roots": {k: f"0x{v + BASE:08X}" for k, v in roots.items()},
            "node_count": len(merged),
            "issues": issues,
            "nodes": [n.as_dict() for n in sorted(merged.values(), key=lambda n: n.offset)],
        }

        if args.scene and not args.all:
            print(f"=== scene {scene} ===")
            for name, root in roots.items():
                print(f"  root {name:7s} -> 0x{root + BASE:08X}")
            for n in sorted(merged.values(), key=lambda n: n.offset):
                line = (f"  0x{n.offset + BASE:08X}  op=0x{n.op:02X} "
                        f"{OP_NAMES.get(n.op, '?'):12s} len={n.length}")
                if n.targets:
                    line += " -> " + ", ".join(f"0x{t + BASE:08X}" for t in n.targets)
                print(line)
                if n.text is not None:
                    print(f"       text: {n.text}")
                if n.text2 is not None:
                    print(f"       text2: {n.text2}")
                if args.raw:
                    print(f"       raw : {n.raw.hex(' ')}")
            if issues:
                print("  ISSUES:")
                for i in issues:
                    print(f"    - {i}")

    if args.stats:
        print("\n=== opcode histogram ===")
        for k in sorted(hist, key=lambda k: -hist[k]):
            print(f"  {k:24s} {hist[k]}")
        print(f"\n=== issues: {len(all_issues)} ===")
        for i in all_issues[:40]:
            print(f"  - {i}")
        if len(all_issues) > 40:
            print(f"  ... and {len(all_issues) - 40} more")

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
