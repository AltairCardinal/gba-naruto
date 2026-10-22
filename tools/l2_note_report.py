#!/usr/bin/env python3
"""Generate the batch-2 section of the L2 evidence note from the JSON report.

The section is *derived* from `build/l2-runtime.json` so the numbers in the
note cannot drift away from the run that produced them.  Prose that a machine
cannot derive (the "not reached" narrative) lives in `EXTRA` below.

Usage:
    python tools/l2_note_report.py --json build/l2-runtime.json \
        --out build/l2-batch2-section.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.lib.io import write_text                       # noqa: E402
from l2_runtime_capture import STRUCTURES               # noqa: E402

BATCH2 = [
    "battle-handlers", "fonts", "data-table-a", "data-table-b",
    "function-pointers", "tile-assets", "sprite-frame-descriptors",
    "battle-encounters", "ninjutsu-names", "reward-table",
    "cutscene-scripts", "sprite-action-table",
]

EXTRA = {
    "battle-handlers": (
        "地图/战斗事件分派表。两个消费者都在 fn `0x0807F414` 里，"
        "下标来自 WRAM `r9 + 0x770` 的一个字节。"),
    "fonts": (
        "字宽表（256 字节，按字符码索引）。消费者 fn `0x0807EE50` 与 "
        "`battle-handlers` 在同一模块（`0x0807EE50`–`0x0807Fxxx`），"
        "两者都用 `movs r0,#0xee / lsls r0,r0,#3` = `0x770` 这个偏移。"),
    "data-table-a": "数据指针表 A（46 项 u32 ROM 指针）。",
    "data-table-b": "数据指针表 B（90 项 u32 ROM 指针）。",
    "function-pointers": (
        "13 槽 u32 钩子表，槽 0 / 12 是 `FFFFFFFF` 哨兵，槽 1..11 是 11 个"
        "代码指针（每槽相差 12 字节）。"),
    "tile-assets": (
        "图块/精灵资源记录表（68 字节/条 x 79），记录 `+0x0C` 是 6 个 u32 图块指针。"),
    "sprite-frame-descriptors": "精灵帧描述符表（10 字节/条 x 15）。",
    "battle-encounters": (
        "战斗遭遇记录表（16 字节/条 x 24）：3 个 u32 指针 + 1 个 u32 编号。"
        "消费者读的是记录 `+0x0C` 的编号字段。"),
    "ninjutsu-names": "忍具名表（u32 文本指针）。",
    "reward-table": "奖励表（24 字节/条 x 112）。",
    "cutscene-scripts": (
        "**关卡数据块表**（4 项 x 8 字节）：每项一对指针"
        "（LZ77 4bpp 图块 → VRAM `0x06016000`；LZ77 16 色调色板 → "
        "调色板 RAM `0x05000380`），由 BIOS `svc 0x12` 解压。"),
    "sprite-action-table": (
        "精灵动作表：`id*144 + action*16`，每项 4 个 u32 指针"
        "（frames / animations / gfx / palette），id 1..62 有效。"),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=pathlib.Path,
                    default=REPO / "build" / "l2-runtime.json")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = json.loads(args.json.read_text(encoding="utf-8"))
    by_name = {s["structure"]: s for s in data["structures"]}
    controls = {c["structure"]: c for c in data.get("negative_controls", [])}

    lines: list[str] = []
    lines.append("")
    lines.append("# 附录 C：L2 第二批的运行时结果（2026-10-21）")
    lines.append("")
    rom_path = pathlib.Path(data["rom"])
    try:
        rom_name = rom_path.relative_to(REPO).as_posix()
    except ValueError:
        rom_name = rom_path.name
    lines.append(f"ROM：`{rom_name}`，sha256 `{data['rom_sha256']}`。")
    lines.append("")
    lines.append("## C.1 判定结果")
    lines.append("")
    lines.append("| 结构 | 基址 | L2 消费者（ARM） | 判定点 | 状态 | 运行时下标 |")
    lines.append("|---|---|---|---|---|---|")
    reached, missed = [], []
    for key in BATCH2:
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
    lines.append(f"**{len(reached)} / {len(BATCH2)} 达到 L2**。")
    lines.append("")
    lines.append("## C.2 逐结构证据")
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
    lines.append("## C.3 未达到清单")
    lines.append("")
    lines.append("这 7 张表在 `tools/l2_runtime_capture.py` 里显式声明为 "
                 "`\"l2\": False`（**仍停在 L1**），并附上没到的原因：")
    lines.append("")
    for key in missed:
        rec = by_name[key]
        reason = STRUCTURES.get(key, {}).get("l1_reason", "")
        lines.append(f"* `{key}`（{rec['base']}）—— {reason}")
    lines.append("")
    body = "\n".join(lines) + "\n"
    if args.out:
        write_text(args.out, body)
        print(f"wrote {args.out} ({len(body)} chars)")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
