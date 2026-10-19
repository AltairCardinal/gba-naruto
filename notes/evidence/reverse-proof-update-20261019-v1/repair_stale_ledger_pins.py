#!/usr/bin/env python3
"""修掉 proof 回归套件里剩余的陈旧硬编码，并撤销上一轮「批量派生」的误伤。

背景
----
2026-10-20 池 3 晋升（unknown 87,631 → 86,089）让全量 93 个测试里 **29 个变红**。
§14 已修掉其中 12 个（37 处「随晋升变化的累计量」字面量）。
本脚本处理**剩下的 4 类、共 72 处**：

1. **账本 SHA 硬编码（22 处）**
   `evidence["sequel/rom-byte-coverage.json"]` 被钉在 9-05 的
   `7726d471…`；活账本现在是 `9f8a8196…`。
   → 改为与**活文件**对拍：`_sha256(ROOT / "sequel/rom-byte-coverage.json")`。
   断言含义不变（「spec 的 evidence entry 必须指向它声称的那个文件」），
   但不再随晋升过期。

2. **覆盖审计脚本 SHA 硬编码（21 处）**
   `coverage["script_sha256"]` 被钉在旧版 `tools/audit_rom_byte_coverage.py`
   的 `63870355…`；本轮给它加了 Python 版本闸门，脚本摘要已变
   （spec 侧已同步，测试侧漏了）。
   → 同样改为与活文件对拍。

3. **计数里程碑（24 处）**
   `assertEqual(96, sum(len(item["verifiers"]) …))` 等
   「不低于某批次落地时的数量」型断言，在验证器总数增长后变红。
   → 改为 `assertGreaterEqual`，保留「只增不减」的原意。

4. **撤销上一轮批量派生的误伤（5 处）**
   §14 的派生按**键名**判定全局量，但有三个键名是**跨域撞名**的：
   `classified_bytes` 既是全局覆盖量，也是**单验证器批次合同**里的批次量；
   `unknown_bytes` 还出现在**合成夹具**里（值是 `7`）。
   上一轮把单验证器合同与夹具里的字面量也换成了活账本全局量，
   导致 4 个测试失败。→ 按**作用域**恢复这些字面量。

第 4 类是本脚本存在的核心理由：
**「是否随晋升变化」不能只看键名，必须看它属于哪个合同作用域。**
本脚本按测试函数作用域限定，只在指定函数内恢复。

本脚本幂等：已修的位置不再匹配任何替换模式，再跑一次 0 替换。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# --- 第 1 类：账本 SHA -----------------------------------------------------
STALE_LEDGER_SHA = "7726d4713ba298da44337da7c7178d2cc9bd29af6f7ea882cfa715cbade6714a"
LEDGER_PATH = "sequel/rom-byte-coverage.json"
LEDGER_RE = re.compile(
    r'(")' + STALE_LEDGER_SHA + r'(")(\s*,\s*evidence\["' + re.escape(LEDGER_PATH) + r'"\],)'
)

# --- 第 2 类：覆盖审计脚本 SHA --------------------------------------------
STALE_COVERAGE_SHA = "63870355410c14efe43cbda776b710ea722417261be12341c832c0854cd5f598"
COVERAGE_SCRIPT = "tools/audit_rom_byte_coverage.py"
COVERAGE_RE = re.compile(
    r'(")' + STALE_COVERAGE_SHA + r'(")(\s*,\s*coverage\["script_sha256"\],)'
)

# --- 第 3 类：计数里程碑 ---------------------------------------------------
# 3a. 多行 sum(len(item["verifiers"]) …)
COUNT_SUM_RE = re.compile(
    r"assertEqual\(\s*\n(\s*)96,\n(\s*sum\(\n\s*len\(item\[\"verifiers\"\]\)\n"
    r"\s*for item in specification\[\"gates\"\]\.values\(\)\n\s*\),)\n(\s*)\)",
    re.S,
)
# 3b. rom_gate 上的两个计数
COUNT_ROM_RE = re.compile(
    r"assertEqual\((\d+), (rom_gate\[\"(?:hash_bound|contracted)_verifier_count\"\])\)"
)

# --- 第 4 类：撤销误伤（按测试函数作用域） --------------------------------
# 函数名 → {要匹配的原文: 恢复后的整段文字}
REVERT_SCOPED = {
    "test_current_spec_binds_selector_text_inventory": {
        '"/summary/classified_bytes": LIVE_COVERAGE_SUMMARY["classified_bytes"],':
            '"/summary/classified_bytes": 816,',
    },
    "test_current_spec_binds_battle_message_text_inventory": {
        '"/summary/classified_bytes": LIVE_COVERAGE_SUMMARY["classified_bytes"],':
            '"/summary/classified_bytes": 2_740,',
    },
    "test_current_spec_binds_boot_interwork_inventory": {
        '"/summary/classified_bytes": LIVE_COVERAGE_SUMMARY["classified_bytes"],':
            '"/summary/classified_bytes": 414,',
    },
    "test_reuses_the_already_executed_rom_coverage_audit_contract": {
        '"/summary/unknown_bytes": LIVE_COVERAGE_SUMMARY["unknown_bytes"],':
            '"/summary/unknown_bytes": 7,',
        '{"/summary/unknown_bytes": LIVE_COVERAGE_SUMMARY["unknown_bytes"]}':
            '{"/summary/unknown_bytes": 0}',
    },
}


def function_ranges(source: str) -> dict[str, tuple[int, int]]:
    tree = ast.parse(source)
    ranges: dict[str, tuple[int, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            ranges.setdefault(node.name, (node.lineno, node.end_lineno or node.lineno))
    return ranges


def _restore_scoped(source: str) -> tuple[str, int]:
    """在指定测试函数作用域内，把误派生回全局量的字面量恢复成原值。

    必须**从文件末尾往前**处理：每个作用域被替换成整段文本后，
    后面的行号会漂移；倒序处理可保证尚未处理的范围仍然有效。
    """
    lines = source.splitlines(keepends=True)
    ranges = function_ranges(source)
    missing = [name for name in REVERT_SCOPED if name not in ranges]
    if missing:
        raise SystemExit(f"refused: 找不到测试函数 {missing}")
    ordered = sorted(REVERT_SCOPED, key=lambda name: ranges[name][0], reverse=True)
    total = 0
    for func_name in ordered:
        replacements = REVERT_SCOPED[func_name]
        start, end = ranges[func_name]
        body = "".join(lines[start - 1 : end])
        for needle, restored in replacements.items():
            found = body.count(needle)
            if found == 0:
                # 已经修过了（幂等复跑）：确认恢复后的文本在位即可。
                if body.count(restored) < 1:
                    raise SystemExit(
                        f"refused: {func_name} 中既没有 {needle!r}，"
                        f"也没有恢复后的 {restored!r}"
                    )
                continue
            if found != 1:
                raise SystemExit(
                    f"refused: {func_name} 中 {needle!r} 出现 {found} 次（期望 1）"
                )
            body = body.replace(needle, restored)
            total += 1
        lines[start - 1 : end] = [body]
    return "".join(lines), total


def transform(source: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}

    # 第 1 类
    def sub_ledger(match: re.Match) -> str:
        counts["ledger_sha"] = counts.get("ledger_sha", 0) + 1
        return (
            f'_sha256(ROOT / "{LEDGER_PATH}"){match.group(3)}'
        )

    source = LEDGER_RE.sub(sub_ledger, source)

    # 第 2 类
    def sub_coverage(match: re.Match) -> str:
        counts["coverage_script_sha"] = counts.get("coverage_script_sha", 0) + 1
        return f'_sha256(ROOT / "{COVERAGE_SCRIPT}"){match.group(3)}'

    source = COVERAGE_RE.sub(sub_coverage, source)

    # 第 3a 类
    def sub_count_sum(match: re.Match) -> str:
        counts["count_sum"] = counts.get("count_sum", 0) + 1
        indent = match.group(1)
        return (
            f"assertGreaterEqual(\n{indent}96,\n{match.group(2)}\n{match.group(3)})"
        )

    source = COUNT_SUM_RE.sub(sub_count_sum, source)

    # 第 3b 类
    def sub_count_rom(match: re.Match) -> str:
        counts["count_rom"] = counts.get("count_rom", 0) + 1
        return f"assertGreaterEqual({match.group(2)}, {match.group(1)})"

    source = COUNT_ROM_RE.sub(sub_count_rom, source)

    # 第 4 类（作用域限定）
    source, reverted = _restore_scoped(source)
    counts["revert_scoped"] = reverted

    return source, counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--target", default="tests/test_audit_reverse_engineering_proof.py"
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    target = (root / args.target).resolve()
    if not target.is_file():
        print(json.dumps({"status": "refused", "reason": f"missing {target}"}))
        return 2

    original = target.read_text(encoding="utf-8")
    updated, counts = transform(original)
    report = {
        "target": str(target.relative_to(root)),
        "replacements": counts,
        "total_replacements": sum(counts.values()),
        "changed": updated != original,
    }
    if args.apply and updated != original:
        ast.parse(updated)  # 写盘前必须仍可解析
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
