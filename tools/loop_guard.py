#!/usr/bin/env python3
"""会话死循环检测器 —— 在真正卡住之前给出机器可判定的警告。

背景：`notes/evidence/session-loop-analysis-20261023.md` 记录了两个会话
（`mvs_98a2…` / `mvs_39e4…`）陷进「无限循环思考」的过程。
根因不是「想不出来」，而是**每次尝试都产不出可判定的结果**，
于是一个不停提新假设，另一个不停重开同一轮。

这个脚本把那种形态变成**能跑出来的结论**：
拿会话的 `messages.jsonl` 进来，它按四条规则打分，
命中就以退出码 1 结束 —— 于是「我好像在打转」变成「工具说我确实在打转」。

用法:
    python tools/loop_guard.py <messages.jsonl> [--window 40] [--json]

退出码:
    0 = 没触发
    1 = 触发（疑似死循环）
    2 = 用法/读取错误

四条规则:
    R1 同址重入   最近 N 次工具调用里，同一个「锚点」（ROM 地址 / 脚本名 / 文件名）
                  反复出现 —— 在同一处反复打转。
    R2 空转回合   连续多条 assistant 消息**一条工具调用都没有** ——
                  Goal 续跑机制的燃料。
    R3 原地推演   相邻两条思考长度都在长、但词集合高度相似 —— 推理在原地转圈。
    R4 命令重复   同名工具 + 同一组参数重复调用。
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HEX = re.compile(r"0x[0-9a-fA-F]{6,8}")
# 只认**构建产物**当锚点：反复重建/反复看同一个 ROM 或截图 = 在同一个地方打转。
# 文档/脚本/JSON **不算** —— 反复编辑同一个文件是正常工作，不是循环。
ARTIFACT = re.compile(r"[A-Za-z0-9_\-\.]+\.(?:gba|bin|rom|png|sav|state)")
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
# 「到处都出现」的东西不能当锚点 —— 它们只会把检测器变成噪音。
# SOURCE_ROM 是**分析的输入**：任何 ROM 考证的探针都要读它，
# 反复提到它是正常工作，不是循环。
SOURCE_ROM = re.compile(r"(^|[\\/])base\.gba$")
GENERIC = {
    "python", "node", "npm", "build", "script", "scripts", "test", "tests",
    "main", "index", "rom", "base", "tool", "tools", "data", "pack", "output",
    "temp", "tmp", "import", "from", "json", "true", "false", "none", "self",
    "with", "open", "read", "write", "print", "return", "value", "name",
    "path", "file", "line", "text", "bytes", "size", "count",
}


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
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def split(m):
    """→ (thinking, text, tool_calls)"""
    th, tx, calls = [], [], []
    for b in blocks(m):
        t = b.get("type")
        if t == "thinking":
            th.append(b.get("thinking") or "")
        elif t == "text":
            tx.append(b.get("text") or "")
        elif t in ("toolCall", "tool_use", "tool_call"):
            calls.append(b)
    return "\n".join(th), "\n".join(tx), calls


def call_args(c):
    a = c.get("arguments") or c.get("input") or c.get("tool_call_args") or {}
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except json.JSONDecodeError:
            a = {"_raw": a}
    return a if isinstance(a, dict) else {"_raw": str(a)}


def call_text(c):
    return json.dumps(call_args(c), ensure_ascii=False, sort_keys=True)


def anchors(text):
    """把一次工具调用里出现的「锚点」抽出来。

    锚点必须**有区分度**才有意义，只收两类：
      * ROM 地址（`0x08097a1c`）—— 逆向工作里最典型的「同一个地方」；
      * 构建产物（`speaker-test.gba` / `screen.png`）——
        反复重建、反复看同一个产物 = 在同一个地方打转。

    **文档 / 脚本 / JSON 不算锚点** —— 反复编辑同一个文件是正常工作。
    普通单词（python / build / import……）全部剔除。
    """
    out = set()
    for m in HEX.findall(text):
        out.add(m.lower())
    for m in ARTIFACT.findall(text):
        if SOURCE_ROM.search(m):
            continue  # 分析的输入，不是「打转的那个地方」
        out.add(m.lower())
    return out


def tokens(text):
    return set(WORD.findall(text or "")) | set(HEX.findall(text or ""))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def analyse(msgs, window=40):
    """返回 (规则命中列表, 细节)。"""
    hits = []
    detail = {}

    # ---- 展平成「回合」序列 ----------------------------------------------
    turns = []  # (index, thinking, text, calls)
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        th, tx, calls = split(m)
        turns.append((i, th, tx, calls))

    # ---- R1 同址重入 -----------------------------------------------------
    calls_all = []
    for idx, th, tx, calls in turns:
        for c in calls:
            calls_all.append((idx, anchors(call_text(c))))
    if len(calls_all) >= 12:
        recent = calls_all[-window:]
        earlier = calls_all[:-window] or calls_all
        rec_cnt = Counter()
        for _, a in recent:
            rec_cnt.update(a)
        old_cnt = Counter()
        for _, a in earlier:
            old_cnt.update(a)
        n_recent = max(1, len(recent))
        best = None
        for anc, c in rec_cnt.items():
            rate = c / n_recent
            old_rate = old_cnt.get(anc, 0) / max(1, len(earlier))
            # 「有区分度」= 整体上并不常见，只在最近这段突然扎堆。
            if c >= 5 and rate >= 0.4 and old_rate <= 0.3:
                score = rate * (1 - old_rate) * c
                if best is None or score > best[0]:
                    best = (score, anc, c, rate, old_rate)
        # 「推进信号」：窗口里新写/新改的**不同文件**。
        # ⚠️ 这里**故意不自动压制 R1** —— 试过「有推进信号就不报」，
        # 结果把真正的事故会话（S1）也压掉了（它的窗口里也写过文件）。
        # ⇒ 结论：判据只负责**把可疑点标出来并给出人工判据**，不负责自动下结论。
        #    「看到 R1 先看细节，再决定要不要动手」—— 误杀的代价比漏报大。
        fresh_paths = set()
        for idx, th, tx, calls in turns[-window:]:
            for c in calls:
                nm = (c.get("name") or c.get("tool_name") or "").lower()
                if nm in ("write", "edit", "create", "write_file", "edit_file"):
                    a = call_args(c)
                    p = a.get("file_path") or a.get("path") or ""
                    if p:
                        fresh_paths.add(p)
        if best:
            _, anc, c, rate, old_rate = best
            hits.append("R1")
            detail["R1"] = {
                "anchor": anc,
                "recent_count": c,
                "recent_rate": round(rate, 3),
                "earlier_rate": round(old_rate, 3),
                "window": window,
                "fresh_files_in_window": len(fresh_paths),
                "human_hint": (
                    "窗口内新写了 %d 个文件 ⇒ 可能是在**深挖同一对象**而不是打转；"
                    "请人工确认后再决定是否终止。" % len(fresh_paths)
                ) if fresh_paths else "窗口内没有新产物 ⇒ 更像在原地打转。",
                "fresh_files": sorted(fresh_paths)[:6],
            }

    # ---- R2 空转回合（**连续**的一串「一条工具都没调」的助手回合） ----------
    # ⚠️ 2026-10-23 修正：原先统计的是「最近 15 条里有几条没调工具」，
    # 结果把**汇总输出**的空转回合也算成循环（实测误报一次：
    # 一个工人在写报告的空转回合之间夹着真实工作，被判成循环）。
    # ⇒ 正确口径是「**连续**的空转回合有多长」——
    #    真循环是一串接一串的空转（Goal 续跑提示夹在中间也是连续）；
    #    空转之后又接着干活的，不算。
    run = 0
    max_run = 0
    zero_run_idx = []
    for i, th, tx, calls in turns:
        if not calls:
            run += 1
            zero_run_idx.append(i)
            max_run = max(max_run, run)
        else:
            run = 0
            zero_run_idx = []
    if max_run >= 3:
        hits.append("R2")
        detail["R2"] = {
            "max_consecutive_zero_tool_turns": max_run,
            "recent": len(turns),
            "note": "连续这么多回合一条工具都没调 —— Goal 续跑提示的燃料（或纯空转）",
        }

    # ---- R3 原地推演（相邻思考相似且在变长） ------------------------------
    ths = [(idx, th) for idx, th, tx, calls in turns if th]
    for (i1, t1), (i2, t2) in zip(ths, ths[1:]):
        sim = jaccard(tokens(t1), tokens(t2))
        if sim >= 0.5 and len(t2) > len(t1) and len(t2) > 3000:
            hits.append("R3")
            detail["R3"] = {
                "pair": [i1, i2],
                "similarity": round(sim, 3),
                "len_before": len(t1),
                "len_after": len(t2),
            }
            break

    # ---- R4 同名工具 + 同参数重复 ----------------------------------------
    # ⚠️ 2026-10-23 修正：原先「同名 + 同参数出现 4 次」就报警，
    # 结果误判了**轮询等待**：`task_output(wait_ms=30000)` 连着调 4 次是在等后台任务，
    # 每次都返回「还在跑」——那是**等待**，不是循环。
    # ⇒ 带 `wait_ms` 的轮询一律不算。
    sig = defaultdict(list)
    for idx, th, tx, calls in turns:
        for c in calls:
            name = c.get("name") or c.get("tool_name") or "?"
            a = call_args(c)
            if "wait_ms" in a or "waitSeconds" in a:
                continue  # 轮询等待
            sig[(name, call_text(c))].append(idx)
    for (name, text), idxs in sig.items():
        if len(idxs) >= 4:
            hits.append("R4")
            detail["R4"] = {
                "tool": name,
                "count": len(idxs),
                "indices": idxs[:8],
                "arg_head": text[:120],
                "note": "同名工具 + 完全相同参数重复调用（轮询等待已排除）",
            }
            break

    # ---- R5 思考爆炸（长思考**且没有产出任何动作**） ------------------------
    # ⚠️ 2026-10-23 修正：原先只要「单条思考 > 30k 字符」就报警，误杀了
    # 「写一份很长的计划然后照着做」的**健康**worker（实测：一条 78k 字符的
    # 规划型思考后面紧跟着 7 次有效工具调用，是正常推进）。
    # 区分点不在长度，在**有没有动作**：
    #   长思考 + 接着调工具 = 正常（深度规划）；
    #   长思考 + 一条工具都没调 = 危险（烧光预算、什么也没产出）。
    big = [
        (i, len(th))
        for i, th, tx, calls in turns
        if len(th) >= 30000 and not calls
    ]
    if big:
        hits.append("R5")
        detail["R5"] = {
            "max_thinking_chars": max(l for _, l in big),
            "count_over_30k_no_action": len(big),
            "indices": [i for i, _ in big][:6],
            "note": "长思考且**一条工具都没调** —— 预算烧光、动作没做出来",
        }

    return hits, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--window", type=int, default=40)
    ap.add_argument("--limit", type=int, default=0, help="只分析前 N 条消息（用于对比健康期）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.path):
        print(f"找不到文件：{args.path}", file=sys.stderr)
        return 2
    msgs = load(args.path)
    if args.limit:
        msgs = msgs[: args.limit]
    hits, detail = analyse(msgs, args.window)

    if args.json:
        print(json.dumps({"hits": hits, "detail": detail}, ensure_ascii=False, indent=2))
        return 1 if hits else 0

    print(f"== 循环检测：{os.path.basename(args.path)}（{len(msgs)} 条消息）")
    if not hits:
        print("  结论：未触发任何规则 ✅")
        print("  （若你主观上觉得在打转，说明规则还不够 —— 把它补进这个脚本）")
        return 0

    print(f"  结论：触发 {len(hits)} 条规则 ⚠️  疑似死循环 —— 请立刻停下换方向")
    for h in hits:
        print(f"\n  [{h}]")
        for k, v in detail.get(h, {}).items():
            print(f"      {k} = {v}")
    print("\n  该做什么：见 notes/evidence/session-loop-analysis-20261023.md §4")
    print("            与 docs/handoff-20261023-speaker-names-conversion.md §5")
    return 1


if __name__ == "__main__":
    sys.exit(main())
