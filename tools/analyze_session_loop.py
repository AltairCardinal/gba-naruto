#!/usr/bin/env python3
"""分析 MCode 会话消息文件，找出「无限循环思考」的结构性特征。

用法:
    python tools/analyze_session_loop.py <messages.jsonl> [--tail N] [--dump-thinking]

输入是 runtime 的 `messages.jsonl`：每行一个 JSON，`message` 字段要么是对象，
要么是 Python repr 的字符串（runtime 有些条目按字符串落盘），两种都要能解析。

输出:
  * 消息时间线（角色 / 时间戳 / 思考长度 / 工具名）
  * 重复检测：连续重复的 thinking 片段、重复的工具调用、重复的 bash 命令
  * 用户消息清单（会话的任务边界）
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load(path):
    """读出消息列表，兼容 dict / Python-repr 字符串两种 message 形态。"""
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = rec.get("message")
            if isinstance(msg, str):
                try:
                    msg = ast.literal_eval(msg)
                except (ValueError, SyntaxError):
                    try:
                        msg = json.loads(msg)
                    except json.JSONDecodeError:
                        msg = {"role": "unparsed", "content": msg}
            if not isinstance(msg, dict):
                msg = {"role": "unparsed", "content": str(msg)}
            msg["_id"] = rec.get("message_id")
            msg["_turn"] = rec.get("turn_id")
            msg["_lineno"] = lineno
            out.append(msg)
    return out


def parts(msg):
    """把 message 拆成 (thinking, text, tool_calls)。"""
    thinking, texts, calls = [], [], []
    content = msg.get("content")
    if isinstance(content, str):
        texts.append(content)
    elif isinstance(content, list):
        for blk in content:
            if not isinstance(blk, dict):
                continue
            t = blk.get("type")
            if t == "thinking":
                thinking.append(blk.get("thinking") or "")
            elif t in ("text", "output_text"):
                texts.append(blk.get("text") or "")
            elif t in ("tool_use", "tool_call", "toolCall"):
                calls.append(blk)
    for c in msg.get("tool_calls") or []:
        calls.append(c)
    return "\n".join(thinking), "\n".join(texts), calls


def tool_name(call):
    return call.get("tool_name") or call.get("name") or call.get("toolName") or "?"


def tool_arg(call):
    a = (
        call.get("tool_call_args")
        or call.get("arguments")
        or call.get("args")
        or call.get("input")
        or {}
    )
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except json.JSONDecodeError:
            pass
    return a if isinstance(a, dict) else {"_raw": str(a)}


def norm(text):
    """归一化思考文本，用于重复检测（去掉标点/空白/数字）。"""
    t = re.sub(r"[0-9A-Fa-fxX]{4,}", "#", text or "")
    t = re.sub(r"\s+", "", t)
    return t


def shingles(text, k=60):
    t = norm(text)
    if len(t) < k:
        return [t] if t else []
    return [t[i : i + k] for i in range(0, len(t) - k + 1, k)]


def tokens(text):
    """按「词/标点块」切分，用于相似度比较。"""
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[0-9A-Fa-fx]{3,}|\S", text or ""))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--tail", type=int, default=40)
    ap.add_argument("--dump-thinking", action="store_true")
    ap.add_argument("--dump-user", action="store_true")
    args = ap.parse_args()

    msgs = load(args.path)
    print(f"== {os.path.basename(args.path)}")
    print(f"消息条数: {len(msgs)}")

    rows = []
    users = []
    for i, m in enumerate(msgs):
        role = m.get("role")
        th, tx, calls = parts(m)
        names = [tool_name(c) for c in calls]
        ts = m.get("timestamp")
        rows.append(
            {
                "i": i,
                "role": role,
                "ts": ts,
                "think": len(th or ""),
                "text": len(tx or ""),
                "tools": names,
                "raw": th or "",
                "calls": calls,
                "turn": m.get("_turn"),
            }
        )
        if role == "user" and (tx or "").strip():
            users.append((i, ts, tx.strip()))

    print(f"用户消息 {len(users)} 条")
    if args.dump_user:
        for i, ts, tx in users:
            print(f"\n--- user @#{i} len={len(tx)}\n{tx[:3000]}")

    # ---- 时间线尾部 ----
    print(f"\n== 尾部 {args.tail} 条消息时间线")
    for r in rows[-args.tail :]:
        tstr = ""
        if r["ts"]:
            import datetime

            tstr = datetime.datetime.fromtimestamp(r["ts"] / 1000).strftime("%m-%d %H:%M:%S")
        print(
            f"#{r['i']:4d} {tstr:15s} {r['role']:12s} think={r['think']:6d} text={r['text']:6d} "
            f"tools={','.join(r['tools'])[:80]}"
        )

    # ---- 重复检测：相邻 thinking 的词集合相似度 ----
    print("\n== 相邻 thinking 词集合相似度（潜在死循环）")
    th_rows = [r for r in rows if r["role"] == "assistant" and r["raw"]]
    pairs = []
    for a, b in zip(th_rows, th_rows[1:]):
        sim = jaccard(tokens(a["raw"]), tokens(b["raw"]))
        pairs.append((sim, a, b))
    pairs.sort(key=lambda x: -x[0])
    print("  相似度最高的 15 对相邻思考：")
    for sim, a, b in pairs[:15]:
        print(f"   {sim:.2f}  #{a['i']} -> #{b['i']}  (think {a['think']} -> {b['think']})")

    print("\n  相似度 ≥0.45 的相邻对：")
    hot = [(s, a, b) for s, a, b in pairs if s >= 0.45]
    for sim, a, b in sorted(hot, key=lambda x: x[1]["i"]):
        print(f"   {sim:.2f}  #{a['i']} -> #{b['i']}")
    print(f"  （共 {len(hot)} 对 / 共 {len(pairs)} 对）")

    # ---- 连续段：从第一个高相似对开始、持续多轮都不下降 ----
    print("\n== 连续段（连续多轮相似度都不低于阈值）")
    thr = 0.40
    run = []
    for sim, a, b in sorted(pairs, key=lambda x: x[1]["i"]):
        if sim >= thr:
            if run and b["i"] - run[-1][1]["i"] <= 4:
                run.append((sim, a, b))
            else:
                if len(run) >= 3:
                    print(f"  段 #{run[0][1]['i']}..#{run[-1][2]['i']} 轮次={len(run)}")
                run = [(sim, a, b)]
        else:
            if len(run) >= 3:
                print(f"  段 #{run[0][1]['i']}..#{run[-1][2]['i']} 轮次={len(run)}")
            run = []
    if len(run) >= 3:
        print(f"  段 #{run[0][1]['i']}..#{run[-1][2]['i']} 轮次={len(run)}")

    # ---- 重复的工具调用（同一工具同一参数连续出现） ----
    print("\n== 重复的工具调用（同名 + 同参数）")
    call_hist = defaultdict(list)
    for r in rows:
        for c in r["calls"]:
            callargs = tool_arg(c)
            key = tool_name(c)
            sig = hashlib.sha1(
                json.dumps(callargs, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:10]
            call_hist[(key, sig)].append(r["i"])
    for (name, sig), idxs in sorted(call_hist.items(), key=lambda kv: -len(kv[1])):
        if len(idxs) >= 3:
            print(f"  {name} (args#{sig}) x{len(idxs)} @ {idxs[:12]}")

    # ---- thinking 自我重复：连续 n 条里出现同一个「结论段」 ----
    print("\n== 反复出现的 thinking 片段（同一句反复 ≥3 次）")
    counts = Counter()
    first_seen = {}
    for r in rows:
        for sh in set(shingles(r["raw"])):
            counts[sh] += 1
            first_seen.setdefault(sh, r["i"])
    for sh, c in counts.most_common(12):
        if c >= 3:
            print(f"  x{c} @#{first_seen[sh]}  {sh[:60]}")

    if args.dump_thinking:
        print("\n== 尾部 thinking 全文")
        for r in rows[-args.tail :]:
            if r["raw"]:
                print(f"\n----- #{r['i']} -----\n{r['raw'][:4000]}")


if __name__ == "__main__":
    main()
