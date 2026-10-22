#!/usr/bin/env python3
"""Batch-3 helper: enumerate and disassemble the native readers of a table.

Why this tool exists
--------------------
`tools/l2_runtime_capture.py` needs three hand-picked facts per structure:

  1. the **reader** -- the instruction that loads the table base,
  2. the **decision point** -- the instruction after it where the base, the
     index and the field value are all in registers,
  3. the **stride** -- how the index is scaled into the table.

Batch 3 adds fourteen structures (several of them are *aliases* of tables
that other batches already proved).  Picking those three facts by eye over a
whole-ROM disassembly is slow and error prone, so this helper prints, for
every native reader of a table, the enclosing function and the instruction
window around the reader.  Nothing here is trusted automatically: the tool
only *prints*; the choices are still made by reading the code, and every
address that ends up in `l2_runtime_capture.py` is re-verified at run time
by the static checks there (the reader must be in the `LiteralIndex` reader
set) and by the negative control.

Usage:
    python tools/l2_batch3.py --list
    python tools/l2_batch3.py per_character_stats --window 14
    python tools/l2_batch3.py --all --window 14 --json build/l2-batch3-readers.json
    python tools/l2_batch3.py --dump unit_slot_remap --count 43 --stride 2
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

from consumer_locate import (LiteralIndex, decode_function,       # noqa: E402
                             disassemble, find_function_start)
from table_registry import TABLES                                # noqa: E402
from tools.lib.io import write_text                              # noqa: E402

ROM_BASE = 0x08000000

# The fourteen structures of L2 batch 3.
#
# `alias_of` records that the structure key names a table that another key
# already proves (a deprecated bank name); the alias still gets its own entry
# in the gate, because the *bank* is what the content pipeline names.
BATCH3 = [
    "character-stats", "character-stats-b", "encounter-zones", "map-sprites",
    "units", "resource-pointers", "save-state", "sprite-animations",
    "items", "skills", "levels", "mission-text", "battle-config",
    "story-background-table",
]

# Prose the machine cannot derive: what the structure *is* and, for the ones
# that did not reach L2, what was tried.
EXTRA = {
    "character-stats": "逐角色属性表（16 字节/条 x 63）。",
    "character-stats-b": "**弃用别名**：与 `character-stats` 是同一张表。",
    "encounter-zones": "**弃用别名**：与 `maps` 是同一张 32 字节地图描述符表。",
    "map-sprites": "场景对象描述符表（8 字节/条 x 43，每条两个 u32 指针）。",
    "units": "单位槽重映射表（2 字节/条 x 43）。",
    "resource-pointers": "精灵动作表的**窗口**（`sprite_action_table + 4*144`）。",
    "save-state": "WRAM 分配表（8 字节/条：u32 WRAM 地址 + u32 大小）。",
    "sprite-animations": "**弃用别名**：与 `sprite-action-table` 是同一张表。",
    "items": "道具/技能记录表（16 字节/条 x 94）。",
    "skills": "**弃用别名**：与 `items` 是同一张表（registry 的规范名）。",
    "levels": "角色特性表（12 字节/条 x 45）。",
    "mission-text": "任务文字索引表（1 字节/条 x 48）。",
    "battle-config": "战斗编成矩阵：`group*0x1AAC + sub*0x8E4 + slot*0xB8 + 4`。",
    "story-background-table": "剧情底图表（16 字节/条 x 14）。",
}


def window(rom: bytes, reader: int, mode: str, span: int) -> list[str]:
    """The instructions around `reader`, with the literal pool filtered out."""
    fn_start = find_function_start(rom, reader, mode)
    insns = []
    if fn_start is not None:
        insns = decode_function(rom, fn_start, mode)
    index = next((i for i, insn in enumerate(insns) if insn.address == reader),
                 None)
    if index is None:
        insns = disassemble(rom, (reader - 0x60) & ~3, 0x60, "arm")
        index = next((i for i, insn in enumerate(insns) if insn.address == reader),
                     None)
        if index is None:
            return [f"    (reader 0x{reader:08X} not disassembled)"]
    lines = []
    for insn in insns[max(0, index - span):index + span + 1]:
        marker = ">>" if insn.address == reader else "  "
        lines.append(f"  {marker} {insn.address:08X}  {insn.mnemonic:8s} "
                     f"{insn.op_str}")
    return lines


def readers_of(index: LiteralIndex, name: str) -> list[tuple[int, str]]:
    """(reader address, mode) for every native reader of the table base."""
    offset, _verified, _note = TABLES[name]
    base = offset + ROM_BASE
    modes: dict[int, str] = {}
    for addr, mode in index.readers_of(base):
        modes.setdefault(addr, mode)
    return sorted(modes.items())


def thumb_call_sites(rom: bytes, target: int) -> list[int]:
    """Every Thumb `bl` that targets `target` (a code or data address)."""
    out: list[int] = []
    for off in range(0, len(rom) - 3, 2):
        hw1 = struct.unpack_from("<H", rom, off)[0]
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = struct.unpack_from("<H", rom, off + 2)[0]
        if (hw2 & 0xD000) != 0xD000:
            continue
        s = (hw1 >> 10) & 1
        imm10 = hw1 & 0x3FF
        j1 = (hw2 >> 13) & 1
        j2 = (hw2 >> 11) & 1
        imm11 = hw2 & 0x7FF
        i1 = (~(j1 ^ s)) & 1
        i2 = (~(j2 ^ s)) & 1
        value = ((s << 24) | (i1 << 23) | (i2 << 22)
                 | (imm10 << 12) | (imm11 << 1))
        if value & (1 << 24):
            value -= (1 << 25)
        dest = (ROM_BASE + off + 4 + value) & 0xFFFFFFFF
        if dest == target or dest == (target & ~1):
            out.append(ROM_BASE + off)
    return out


def dump_table(rom: bytes, base: int, count: int, stride: int,
               width: int = 4) -> list[str]:
    """Print the ROM bytes of a table, `count` records of `stride` bytes."""
    lines = []
    for i in range(count):
        off = base - ROM_BASE + i * stride
        chunk = rom[off:off + min(stride, width)]
        if stride >= width:
            words = [struct.unpack_from("<I", rom, off + 4 * k)[0]
                     for k in range(stride // 4)]
            text = " ".join(f"{w:08X}" for w in words)
        else:
            text = chunk.hex(" ")
        lines.append(f"  [{i:3d}] @0x{base + i * stride:08X}  {text}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table", nargs="?", default=None,
                    help="registry entry name (or a batch-3 structure key)")
    ap.add_argument("--all", action="store_true", help="every batch-3 table")
    ap.add_argument("--list", action="store_true", help="list the batch-3 tables")
    ap.add_argument("--window", type=int, default=12,
                    help="instructions shown on each side of the reader")
    ap.add_argument("--rom", type=pathlib.Path, default=REPO / "rom" / "base.gba")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--dump", default=None,
                    help="dump a registry table's ROM bytes instead")
    ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--stride", type=int, default=16)
    ap.add_argument("--width", type=int, default=4)
    ap.add_argument("--report", type=pathlib.Path, default=None,
                    help="write the appendix D runtime section from "
                         "build/l2-runtime.json")
    ap.add_argument("--report-json", type=pathlib.Path,
                    default=REPO / "build" / "l2-runtime.json")
    ap.add_argument("--calls", default=None,
                    help="list the Thumb `bl` call sites of an address "
                         "(e.g. 0x0806D910)")
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.calls:
        rom = args.rom.read_bytes()
        target = int(args.calls, 16)
        sites = thumb_call_sites(rom, target)
        print(f"0x{target:08X}: {len(sites)} call site(s)")
        for site in sites:
            owner = find_function_start(rom, site, "thumb")
            print(f"    0x{site:08X}  (in fn 0x{(owner or 0):08X})")
        return 0

    if args.report:
        body = build_report(args.report_json)
        if args.report == "-":
            sys.stdout.write(body)
        else:
            write_text(args.report, body)
            print(f"wrote {args.report} ({len(body)} chars)")
        return 0

    rom = args.rom.read_bytes()

    if args.dump:
        offset, verified, note = TABLES[args.dump]
        base = offset + ROM_BASE
        print(f"== {args.dump} base=0x{base:08X} verified={verified}")
        print(f"   note: {note}")
        for line in dump_table(rom, base, args.count, args.stride, args.width):
            print(line)
        return 0

    if args.list:
        from l2_runtime_capture import STRUCTURES
        for key in BATCH3:
            spec = STRUCTURES[key]
            offset, verified, note = TABLES[spec["registry"]]
            print(f"{key:26s} {spec['registry']:28s} base=0x{offset + ROM_BASE:08X} "
                  f"route={spec['route']:9s} group={spec.get('group', key)} "
                  f"verified={verified}")
        return 0

    if args.all:
        wanted = list(BATCH3)
    elif args.table:
        matched = [n for n in BATCH3 if n[0] == args.table]
        if not matched and args.table in TABLES:
            matched = [(args.table, args.table, 0, 0, [])]
        if not matched:
            print(f"ERR unknown table {args.table!r}", file=sys.stderr)
            return 2
        wanted = matched
    else:
        ap.print_help()
        return 2

    index = LiteralIndex(rom)
    report: dict = {}
    for key, name, stride, count, extra in wanted:
        offset, verified, note = TABLES[name]
        base = offset + ROM_BASE
        print(f"== {key}  ({name})  base=0x{base:08X}  verified={verified} "
              f"{'; '.join(extra)}")
        print(f"   note: {note}")
        entries = []
        for addr, mode in readers_of(index, name):
            fn_start = find_function_start(rom, addr, mode)
            print(f"   reader 0x{addr:08X} [{mode}]  "
                  f"fn start 0x{(fn_start or 0):08X}")
            for line in window(rom, addr, mode, args.window):
                print(line)
            entries.append({"reader": f"0x{addr:08X}", "mode": mode,
                            "function": f"0x{(fn_start or 0):08X}"})
        report[key] = {"registry": name, "base": f"0x{base:08X}",
                       "verified": verified, "readers": entries}
        print()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
        print(f"wrote {args.json}")
    return 0


def build_report(json_path: pathlib.Path) -> str:
    """The appendix D runtime section, derived from the capture's own JSON."""
    import json as _json
    from l2_runtime_capture import STRUCTURES

    data = _json.loads(json_path.read_text(encoding="utf-8"))
    by_name = {s["structure"]: s for s in data["structures"]}
    controls = {c["structure"]: c for c in data.get("negative_controls", [])}

    lines: list[str] = []
    lines.append("")
    lines.append("## D.3 判定结果")
    lines.append("")
    lines.append("| 结构 | 基址 | L2 消费者（ARM） | 判定点 | 状态 | 运行时下标 |")
    lines.append("|---|---|---|---|---|---|")
    reached, missed = [], []
    for key in BATCH3:
        rec = by_name.get(key)
        if rec is None:
            continue
        base = rec["base"]
        if rec["ok"]:
            cap = next(c for c in rec["captures"] if c.get("ok"))
            lines.append(
                f"| `{key}` | `{base}` | `{cap['consumer_reader']}`"
                f"（fn `{cap['consumer_function']}`） | `{cap['decision_point']}` "
                f"| ✅ L2 | {cap['index']} |")
            reached.append((key, cap))
        else:
            hit = [c for c in rec["captures"] if not c.get("error")]
            where = ("、".join(f"`{c['decision_point']}`" for c in hit)
                     if hit else "无")
            lines.append(f"| `{key}` | `{base}` | — | {where} | ❌ 未达到 | — |")
            missed.append(key)
    lines.append("")
    lines.append(f"**{len(reached)} / {len(BATCH3)} 达到 L2**。")
    lines.append("")
    lines.append("## D.4 逐结构证据")
    lines.append("")
    for key, cap in reached:
        rec = by_name[key]
        lines.append(f"### `{key}`（{rec['base']}）")
        lines.append("")
        lines.append(EXTRA.get(key, ""))
        lines.append("")
        lines.append(f"**消费者**：`{cap['consumer_reader']}`"
                     f"（fn `{cap['consumer_function']}`），"
                     f"**判定点**：`{cap['decision_point']}`，"
                     f"命中 `{cap['hit_at']}`。")
        lines.append("")
        lines.append("```")
        lines.append(f"pc={cap['pc']}  lr={cap['lr']}  sp={cap['sp']}")
        for reg, value in cap["registers"].items():
            lines.append(f"{reg}={value}")
        lines.append(f"表基址字节(16): {cap['table_base_bytes']}")
        lines.append(f"表项 @ {cap['entry_address']} (16): {cap['entry_bytes']}")
        lines.append("```")
        lines.append("")
        lines.append("**寄存器 ↔ 字段对应**")
        lines.append("")
        lines.append("| 检查 | 结果 | 明细 |")
        lines.append("|---|---|---|")
        for check in cap["checks"]:
            mark = "✅" if check["ok"] else "❌"
            lines.append(f"| {check['name']} | {mark} | `{check['detail']}` |")
        lines.append("")
        control = controls.get(key)
        if control:
            for check in control["checks"]:
                mark = "✅" if check["ok"] else "❌"
                lines.append(f"**反向对照**：{mark} {check['name']} —— {check['detail']}")
            lines.append("")
    lines.append("## D.5 未达到清单")
    lines.append("")
    if missed:
        lines.append("下列结构在 `tools/l2_runtime_capture.py` 里显式声明为 "
                     "`\"l2\": False`（**仍停在 L1**），并附上没到的原因：")
        lines.append("")
        for key in missed:
            rec = by_name[key]
            reason = STRUCTURES.get(key, {}).get("l1_reason", "")
            lines.append(f"* `{key}`（{rec['base']}）—— {reason}")
    else:
        lines.append("（本批 14 个结构全部达到 L2。）")
    lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
