#!/usr/bin/env python3
"""把 proof 回归测试里对「活账本全局量」的硬编码字面量改为派生引用。

背景
----
``tests/test_audit_reverse_engineering_proof.py`` 里有一批断言把
「会随每次晋升而变化的累计量」写成了字面量。每一次覆盖晋升都会让这批
断言变红 —— 2026-10-20 这一轮池 3 晋升（unknown 87,631 → 86,089）就打破了
12 个测试。

本脚本把这些位置的字面量换成 ``LIVE_COVERAGE_SUMMARY[...]`` 派生引用；
**批次自身的增量指针保持硬编码**（那是这套测试真正要守的回归护栏）。

语义分类
--------
派生（会随晋升变化）
    unknown_bytes / classified_bytes / claim_count / segment_count
    cfg_reachable_thumb_code_bytes / cfg_promoted_unknown_bytes
    cfg_primary_claim_count / cfg_code_claim_kind_count
    cfg_code_claim_kind_denominator_sha256
    consumer_code_slice_bytes / consumer_code_slice_claim_count
        —— 消费者代码切片族的累计总量，与上面的 cfg_* 同属「累计型」，
           同样随晋升变化（本轮实测 25,284 → 27,404）。

不派生（批次增量，固定不变）
    其余一切 ``/summary/<key>``（例如 positions_aux_dispatch_bytes、
    cfg_proven_roots_v14_extension_code_bytes 等）。

本脚本是幂等的：已派生的位置不匹配任何替换模式，再跑一次结果不变。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DERIVE_KEYS = (
    "unknown_bytes",
    "classified_bytes",
    "claim_count",
    "segment_count",
    "cfg_reachable_thumb_code_bytes",
    "cfg_promoted_unknown_bytes",
    "cfg_primary_claim_count",
    "cfg_code_claim_kind_count",
    "cfg_code_claim_kind_denominator_sha256",
    "consumer_code_slice_bytes",
    "consumer_code_slice_claim_count",
)
DERIVE = set(DERIVE_KEYS)

# --- 模式 A：assertEqual(<字面量>, <expr>["/summary/<key>"]) -----------------
#     <expr> 允许包含下标链，但不允许出现括号。
_A_LITERAL_FIRST = re.compile(
    r"assertEqual\(\s*(?P<lit>\"[0-9a-fA-F]{8,}\"|[0-9][0-9_]*)\s*,\s*"
    r"(?P<expr>[A-Za-z_][\w\.\[\]\"']*?)\[\s*[\"']/summary/(?P<key>\w+)[\"']\s*\]\s*,?\s*\)",
    re.S,
)
# --- 模式 A2：assertEqual(<字面量>, rom_gate[...]["summary"][<key>]) ----------
_A2_ROM_GATE = re.compile(
    r"assertEqual\(\s*(?P<lit>\"[0-9a-fA-F]{8,}\"|[0-9][0-9_]*)\s*,\s*"
    r"rom_gate\[\s*\"rom_coverage_audit\"\s*\]\s*\[\s*\"summary\"\s*\]\s*\[\s*[\"'](?P<key>\w+)[\"']\s*\]\s*,?\s*\)",
    re.S,
)
# --- 模式 A3：assertEqual(<expr>["/summary/<key>"], <字面量>) -----------------
_A3_LITERAL_SECOND = re.compile(
    r"assertEqual\(\s*(?P<expr>[A-Za-z_][\w\.\[\]\"']*?)\[\s*[\"']/summary/(?P<key>\w+)[\"']\s*\]\s*,\s*"
    r"(?P<lit>\"[0-9a-fA-F]{8,}\"|[0-9][0-9_]*)\s*\)",
    re.S,
)
# --- 模式 B：字典字面量 "/summary/<key>": ( "<sha>" ) ----------------------
_B_DICT = re.compile(
    r"(\"(/summary/(?P<key>\w+))\":\s*)\(\s*\"(?P<val>[0-9a-fA-F]{8,})\"\s*\)",
    re.S,
)

LITERAL_RE = re.compile(r"^(?:\"(?P<s>[0-9a-fA-F]{8,})\"|(?P<i>[0-9][0-9_]*))$")


def _is_derive_key(key: str) -> bool:
    return key in DERIVE


def _replace_a(text: str, pattern: re.Pattern, swap: bool) -> tuple[str, int]:
    """swap=True 表示把字面量换到右侧（模式 A3）。"""
    hits = 0

    def sub(match: re.Match) -> str:
        nonlocal hits
        key = match.group("key")
        if not _is_derive_key(key):
            return match.group(0)
        hits += 1
        derived = f'LIVE_COVERAGE_SUMMARY["{key}"]'
        expr = match.group("expr")
        pointer = f'["/summary/{key}"]'
        if swap:
            return f"assertEqual({expr}{pointer}, {derived})"
        return f"assertEqual({derived}, {expr}{pointer})"

    return pattern.sub(sub, text), hits


def _replace_a2(text: str) -> tuple[str, int]:
    hits = 0

    def sub(match: re.Match) -> str:
        nonlocal hits
        key = match.group("key")
        if not _is_derive_key(key):
            return match.group(0)
        hits += 1
        return (
            f'assertEqual(LIVE_COVERAGE_SUMMARY["{key}"], '
            f'rom_gate["rom_coverage_audit"]["summary"]["{key}"])'
        )

    return _A2_ROM_GATE.sub(sub, text), hits


def _replace_b(text: str) -> tuple[str, int]:
    hits = 0

    def sub(match: re.Match) -> str:
        nonlocal hits
        key = match.group("key")
        if not _is_derive_key(key):
            return match.group(0)
        hits += 1
        return f'{match.group(1)}LIVE_COVERAGE_SUMMARY["{key}"]'

    return _B_DICT.sub(sub, text), hits


def transform(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    text, counts["A_literal_first"] = _replace_a(text, _A_LITERAL_FIRST, swap=False)
    text, counts["A2_rom_gate"] = _replace_a2(text)
    text, counts["A3_literal_second"] = _replace_a(text, _A3_LITERAL_SECOND, swap=True)
    text, counts["B_dict"] = _replace_b(text)
    return text, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="仓库根目录")
    parser.add_argument(
        "--target",
        default="tests/test_audit_reverse_engineering_proof.py",
        help="待改写的测试文件（相对 root）",
    )
    parser.add_argument(
        "--apply", action="store_true", help="真正写盘；缺省只做 dry-run 报告"
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    target = (root / args.target).resolve()
    if not target.is_file():
        print(json.dumps({"status": "refused", "reason": f"target missing: {target}"}))
        return 2

    original = target.read_text(encoding="utf-8")
    updated, counts = transform(original)
    changed = updated != original

    report = {
        "target": str(target.relative_to(root)),
        "derive_keys": list(DERIVE_KEYS),
        "replacements": counts,
        "total_replacements": sum(counts.values()),
        "changed": changed,
        "applied": bool(args.apply),
    }
    if args.apply and changed:
        target.write_text(updated, encoding="utf-8")
        report["status"] = "applied"
    elif args.apply:
        report["status"] = "no-op"
    else:
        report["status"] = "dry-run"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
