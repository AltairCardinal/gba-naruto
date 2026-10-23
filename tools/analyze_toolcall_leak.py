#!/usr/bin/env python3
"""统计会话里「工具调用以文本形式泄漏」与「思考爆发」的现象。

要查的东西：
  1. assistant 的 text 字段里出现 `minimax[>` / `<invoke>` / `</tool_call>` 等标记
     —— 说明模型把工具调用写进了文本通道，runtime 收不到结构化 toolCall，
        这一轮就等于「什么都没做」。
  2. 单条 assistant 的 thinking 长度分布（思考爆发）。
  3. 每个 turn（goal 续跑）之间「无 toolCall 的 assistant 消息」占比。
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LEAK_MARKERS = ("minimax[>", "<invoke>", "</tool_call>", "<new_string>", "</invoke>", "</tool_call>")


def load(path):
    msgs = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = rec.get("message")
            if isinstance(m, str):
                try:
                    m = ast.literal_eval(m)
                except (ValueError, SyntaxError):
                    continue
            if isinstance(m, dict):
                msgs.append(m)
    return msgs


def blocks(m):
    c = m.get("content")
    if isinstance(c, list):
        return [b for b in c if isinstance(b, dict)]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    msgs = load(args.path)
    print(f"== {args.label or args.path}  ({len(msgs)} msgs)")

    leaked = []
    notool = []
    thinklens = []
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        bs = blocks(m)
        th = sum(len(b.get("thinking", "")) for b in bs if b.get("type") == "thinking")
        tx = "".join(b.get("text", "") for b in bs if b.get("type") == "text")
        has_tc = any(b.get("type") in ("toolCall", "tool_use", "tool_call") for b in bs)
        thinklens.append((i, th, len(tx), has_tc, m.get("stopReason")))
        if any(k in tx for k in LEAK_MARKERS):
            leaked.append((i, th, len(tx), has_tc, m.get("stopReason"), tx[:160]))
        if not has_tc:
            notool.append(i)

    print(f"assistant 消息: {len(thinklens)}")
    print(f"其中**没有任何结构化 toolCall**: {len(notool)}  ({100*len(notool)/max(len(thinklens),1):.0f}%)")
    print(f"text 里出现工具调用标记（泄漏）: {len(leaked)}")

    print("\n-- 泄漏样例（最后 12 条）--")
    for i, th, tl, tc, sr, tx in leaked[-12:]:
        print(f"  #{i} think={th} textlen={tl} toolCall={tc} stop={sr} :: {tx[:110]!r}")

    print("\n-- 思考长度分布（chars）--")
    ls = sorted(x[1] for x in thinklens)
    n = len(ls)
    if n:
        print(f"  n={n} min={ls[0]} p50={ls[n//2]} p90={ls[int(n*0.9)]} max={ls[-1]}")
    print("  最长的 10 条：")
    for i, th, tl, tc, sr in sorted(thinklens, key=lambda x: -x[1])[:10]:
        print(f"    #{i} think={th} text={tl} toolCall={tc} stop={sr}")

    print("\n-- 无 toolCall 的 assistant 消息（按时间列）--")
    for i in notool[-25:]:
        th, tl, tc, sr = next(x[1:] for x in thinklens if x[0] == i)
        print(f"    #{i} think={th} text={tl} stop={sr}")


if __name__ == "__main__":
    main()
