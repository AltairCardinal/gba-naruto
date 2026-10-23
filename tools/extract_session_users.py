#!/usr/bin/env python3
"""把 MCode 会话里的「用户消息」按来源分拣导出，便于看清任务边界与 goal 续跑提示。

用法:
    python tools/extract_session_users.py <messages.jsonl> [--out FILE]

分类：
  REAL      真人输入
  GOAL-NUDGE `<archon_internal_context source="goal">` —— runtime 自动续跑提示
  REMINDER  system-reminder 注入
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


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


def text_of(m):
    c = m.get("content")
    if isinstance(c, list):
        return "\n".join(b.get("text", "") for b in c if isinstance(b, dict))
    return str(c or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out")
    ap.add_argument("--tail-chars", type=int, default=900)
    args = ap.parse_args()

    msgs = load(args.path)
    fh = io.open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
    fh.write(f"===== {args.path} ({len(msgs)} msgs) =====\n")
    for i, m in enumerate(msgs):
        if m.get("role") != "user":
            continue
        t = text_of(m)
        if "<archon_internal_context" in t:
            kind, body = "GOAL-NUDGE", t[-args.tail_chars :]
        elif "<system-reminder>" in t:
            kind, body = "REMINDER", t[-args.tail_chars :]
        else:
            kind, body = "REAL", t
        fh.write(f"\n--- user #{i} [{kind}] len={len(t)} ---\n{body}\n")
    if args.out:
        fh.close()
        print("written", args.out)


if __name__ == "__main__":
    main()
