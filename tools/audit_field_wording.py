#!/usr/bin/env python3
"""字段说明的可读性审计：找出「技术上对，但作者看不懂」的那些。

为什么要另起一个工具：`tools/audit_field_labels.py` 查的是**占位名**
（「字节00」「未知0A」「属性A」这种），那些已经清干净了。

但还有另一类问题：说明本身**没有占位名**，却仍然是 ROM 的内部视角 ——
作者读到的是「字节 +0x04」「由下面的『成长目标』字段选中（1..6 指到这里）」
这种只有逆向者看得懂的句子，而不是「这个东西在游戏里是什么」。

本工具把每个字段的 label / desc 摊开，按**内部词汇**打标：
  * 偏移当主语：说明的主体是「字节 +0xNN」「记录」「字段」这类内部对象
  * 交叉引用：说明里出现「下面的 X 字段」「上面的 X」这类指路
  * 公式裸奔：直接给公式却不说这是什么
  * 只说「未解」：说清了没证明，却没说这个值在游戏里是干嘛的

用法：
    python tools/audit_field_wording.py              # 报告写到 build/field-wording.md
    python tools/audit_field_wording.py --print      # 直接打到标准输出
    python tools/audit_field_wording.py --only jutsu # 只看某张表
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACK = REPO / "rom-editor" / "content" / "pack.json"

# ---- 内部词汇：出现在说明里通常说明写的是 ROM 的视角，不是作者的视角 ----

# 以内部对象当主语的句子：「字节 +0x04」「记录 [+0x0C]」「字段 +0x02」
OFFSET_SUBJECT = re.compile(
    r"(字节|记录|字段|槽位|偏移|位域|指针)\s*[+＋]?\s*0x[0-9A-Fa-f]{2,4}"
)
# 交叉引用：「由下面的『成长目标』字段选中」「见上面的」
CROSS_REF = re.compile(r"(下面|上面|上面那|前面)的?[「『\"']?\S{1,8}[」』\"']?\s*字段")
# 裸公式：等号两边都是符号，且没提「等级」「值」这类词
BARE_FORMULA = re.compile(r"[=＝]\s*[^，。；\n]{0,24}×[^，。；\n]{0,24}")
# 只说「未解」却没说这个值是干嘛的
ONLY_UNDECIDED = re.compile(r"^[^。]{0,24}(未解|未证|语义未解|尚未证明)[。\s]*$")
# 说明里出现 ROM 地址：那是**证据**，不是解释 ——
# 作者要的是「这东西是干嘛的」，地址该待在笔记里。
ROM_ADDRESS = re.compile(r"0x0[0-9A-Fa-f]{5,7}")
# 解释太长的字段：作者读不下去
TOO_LONG = 160


def load_pack():
    with PACK.open(encoding="utf-8") as fh:
        return json.load(fh)


def flags_for(field):
    """这个字段的说明有哪些「看不懂」的打标。"""
    desc = str(field.get("desc") or "")
    label = str(field.get("label") or "")
    is_array_item = bool(field.get("array"))
    out = []
    if OFFSET_SUBJECT.search(desc):
        out.append("偏移当主语")
    if CROSS_REF.search(desc):
        out.append("交叉引用")
    if BARE_FORMULA.search(desc) and not any(w in desc for w in ("等级", "数值", "倍数")):
        out.append("裸公式")
    if ONLY_UNDECIDED.match(desc.strip()):
        out.append("只说未解")
    if ROM_ADDRESS.search(desc):
        out.append("说明里塞了 ROM 地址")
    if len(desc) > TOO_LONG:
        out.append(f"说明过长（{len(desc)} 字）")
    # label 带编号本身不算问题（「属性加成 1..6」「图层0」都清楚）；
    # 有问题的是**两个不同的东西共用一个词** —— 那个由 ambiguous_labels() 判。
    return out


def ambiguous_labels(structure):
    """同一张表里，「带编号的那几个」与「点名它们的那一个」用了同一个词。

    这是「成长目标1..6」与「成长目标」那种撞车：
    作者看到「成长目标=4」不知道说的是第 4 个槽还是那一格。
    编号本身没问题（属性加成 1..6、图层0/1 都不歧义），
    有歧义的是**两个不同的东西共用一个词**。
    """
    labels = [str(f.get("label") or "") for f in structure.get("fields", [])]
    out = []
    for field in structure.get("fields", []):
        label = str(field.get("label") or "")
        if not re.search(r"[0-9]$", label):
            continue
        stem = re.sub(r"[0-9]+$", "", label).strip()
        if not stem:
            continue
        # 同一张表里另有一个字段的标签正好是这个词干
        if any(other != label and other.strip() == stem for other in labels):
            out.append(field)
    return out


def collect(pack, only=None):
    rows = []
    for structure in pack.get("structures", []):
        if only and only not in structure.get("id", ""):
            continue
        ambiguous = {f.get("key") for f in ambiguous_labels(structure)}
        for field in structure.get("fields", []):
            flags = flags_for(field)
            if field.get("key") in ambiguous:
                flags.append("label 与另一个字段撞词")
            if not flags:
                continue
            rows.append({
                "table": structure.get("id"),
                "table_label": structure.get("label"),
                "key": field.get("key"),
                "label": field.get("label"),
                "desc": field.get("desc"),
                "flags": flags,
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="print_out", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    pack = load_pack()
    total = sum(len(s.get("fields", [])) for s in pack.get("structures", []))
    rows = collect(pack, args.only)

    by_flag = {}
    for row in rows:
        for flag in row["flags"]:
            by_flag.setdefault(flag, []).append(row)

    lines = []
    lines.append("# 字段说明可读性审计\n")
    lines.append(f"- 全包字段总数：**{total}**")
    lines.append(f"- 命中「看不懂」打标的字段：**{len(rows)}**")
    lines.append("")
    lines.append("| 打标 | 字段数 |")
    lines.append("|---|---|")
    for flag, items in sorted(by_flag.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| {flag} | {len(items)} |")
    lines.append("")

    for table in sorted({r["table"] for r in rows}):
        items = [r for r in rows if r["table"] == table]
        lines.append(f"## {table}（{items[0]['table_label']}）— {len(items)} 个\n")
        for row in items:
            lines.append(f"- **{row['label']}** `+0x` — {'/'.join(row['flags'])}")
            lines.append(f"  - 原文：{row['desc']}")
        lines.append("")

    text = "\n".join(lines)
    if args.print_out:
        sys.stdout.write(text)
    else:
        out = REPO / "build" / "field-wording.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"报告写到 {out.relative_to(REPO)}")
        print(f"字段总数 {total}，命中 {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
