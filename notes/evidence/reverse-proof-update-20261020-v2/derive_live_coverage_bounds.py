#!/usr/bin/env python3
"""把审计器测试模块里**陈旧的账本快照断言**改写成上下界断言。

为什么需要它
------------
`tests/test_audit_rom_byte_coverage.py` 有 20 个测试方法把**账本总量**写死成
字面量（`self.assertEqual(6_126_383, summary["classified_bytes"])`）。账本每晋升
一次，这些字面量就变成历史值 —— 2026-10-20 实测 **80 处**陈旧断言已经让该模块
**跑不过**。这类失败每次晋升都会重来一遍，是纯粹的噪声。

正确的改法（**仓库里已有先例**：同文件第 11565–11568、11796–11799 行就是这个形态）
----------------------------------------------------------------------------
快照等号 `assertEqual(<冻结值>, summary["<key>"])` 的原意是「账本**至少**已经
到这个状态」。那就把它变成**界**：

- 只会**增长**的量（``classified_bytes`` / ``claim_count`` / ``segment_count`` /
  ``cfg_*`` 家族聚合）→ **下界** ``assertGreaterEqual(实际值, 冻结值)``；
- 只会**缩小**的量（``unknown_bytes``）→ **上界** ``assertLessEqual(实际值, 冻结值)``。

界必须留在正确的一侧，否则断言会立刻失败 —— 那样它就不再是护栏，只是噪声。

**这个脚本不碰批次增量**（各 packet 自己的 promotion_bytes / claim_count 等）：
那些是真正的回归护栏，必须保持硬编码。

用法
----
```bash
/usr/local/bin/python3 derive_live_coverage_bounds.py --root . --dry-run
/usr/local/bin/python3 derive_live_coverage_bounds.py --root . --apply
```

幂等：改写后的调用不再是 ``assertEqual``，再跑一次没有可改的地方 → 报 ``changed: 0``。
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys

#: 只会缩小的量 → 用上界（assertLessEqual）。
SHRINKING_KEYS = frozenset({"unknown_bytes"})

#: 目标文件里账本快照的形态：
#: <断言对象>.assertEqual(<字面量>, <summary 变量>["<键>"])
PATTERN = re.compile(
    r'(?P<indent>[ \t]*)'
    r'(?P<obj>[A-Za-z_][A-Za-z0-9_]*)'
    r'\.assertEqual\('
    r'(?P<lit>[0-9][0-9_]*)'
    r',\s*'
    r'(?P<base>[A-Za-z_][A-Za-z0-9_]*)'
    r'\["(?P<key_name>[A-Za-z0-9_]+)"\]'
    r'\)'
)

#: 活账本的唯一判据：赋值表达式里出现这个相对路径。
LIVE_LEDGER_MARKER = "sequel/rom-byte-coverage.json"


#: 元组形态的通用模式：``assertEqual((<数>, ...), (<表达式>, ...))``。
#: 表达式里允许**两层**括号（``len(self._rom())`` 就是两层）。
_EXPR = r"(?:[^()]|\([^()]*\)|\([^()]*\([^()]*\)[^()]*\))*"
TUPLE_PATTERN = re.compile(
    r'(?P<indent>[ \t]*)'
    r'(?P<obj>[A-Za-z_][A-Za-z0-9_]*)'
    r'\.assertEqual\(\s*'
    r'\((?P<expected>' + _EXPR + r')\)\s*,\s*'
    r'\((?P<actual>' + _EXPR + r')\)\s*,?\s*\)'
)


#: 第三形态：按 key 取活账本摘要的生成器元组断言
#:     self.assertEqual(
#:         (6_198_347, 93_109, 16_793),
#:         tuple(coverage["summary"][key] for key in (
#:             "classified_bytes", "unknown_bytes", "claim_count",
#:         )),
#:     )
#: 期望值与 key 顺序一一对应 → 拆成逐 key 的界。
GENERATOR_PATTERN = re.compile(
    r'(?P<indent>[ \t]*)'
    r'(?P<obj>[A-Za-z_][A-Za-z0-9_]*)\.assertEqual\(\s*'
    r'\(\s*(?P<expected>(?:[0-9][0-9_]*\s*,\s*)*[0-9][0-9_]*)\s*\)\s*,\s*'
    r'tuple\(\s*(?P<base>[A-Za-z_][A-Za-z0-9_]*)\["summary"\]\[key\]\s*'
    r'for\s+key\s+in\s*\((?P<keys>[^)]*)\)\s*\)\s*,?\s*\)',
    re.DOTALL,
)


#: 第四形态：``assertEqual(<字面量>, <全量聚合变量>["<cfg 键>"])``
FULL_AGGREGATE_PATTERN = re.compile(
    r'(?P<indent>[ \t]*)'
    r'(?P<obj>[A-Za-z_][A-Za-z0-9_]*)\.assertEqual\(\s*'
    r'(?P<lit>[0-9][0-9_]*)\s*,\s*'
    r'(?P<base>[A-Za-z_][A-Za-z0-9_]*)\["(?P<key_name>[A-Za-z0-9_]+)"\]\s*\)'
)


#: 第五形态：``assertEqual({...}, <全量聚合变量>)``
DICT_PATTERN = re.compile(
    r'(?P<indent>[ \t]*)'
    r'(?P<obj>[A-Za-z_][A-Za-z0-9_]*)\.assertEqual\(\s*'
    r'\{(?P<body>[^{}]*)\}\s*,\s*'
    r'(?P<base>[A-Za-z_][A-Za-z0-9_]*)\s*,?\s*\)',
    re.DOTALL,
)


def _split_top_level(text: str) -> list[str]:
    """按**顶层逗号**切分（括号内的逗号不算）。"""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for character in text:
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        if character == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _enclosing_scopes_source(source: str, offset: int) -> str:
    """取包含该偏移量的**最内层函数 + 所在类**的源码文本。

    基线常常是经类里的辅助方法取的（``baseline = self._baseline()``），
    所以只看函数体看不到活账本路径 —— 必须把类体也算进来。
    """
    tree = ast.parse(source)
    lines = source.splitlines()
    # offset 是**字符偏移**，要换算成行号才能和 AST 的 lineno 比。
    line_number = source.count("\n", 0, offset) + 1
    best_function = ""
    best_class = ""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno)
            if start <= line_number <= end:
                candidate = "\n".join(lines[start - 1 : end])
                if len(candidate) > len(best_function):
                    best_function = candidate
        elif isinstance(node, ast.ClassDef):
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno)
            if start <= line_number <= end:
                candidate = "\n".join(lines[start - 1 : end])
                if len(candidate) > len(best_class):
                    best_class = candidate
    return best_function + "\n" + best_class


def _live_summary_receivers(source: str) -> set[str]:
    """找出**确实绑定到活账本**的 summary 接收者（**按作用域**解析）。

    典型形态是两级别名：

        manifest = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text())
        summary = manifest["summary"]

    必须**按作用域**解析：同一个名字 `manifest` 在不同作用域里可能指向**不同**的东西
    （实测本文件里既有 `manifest = json.loads(活账本)`，也有
    `manifest = coverage_auditor.build_manifest(ROOT)`，后者是**重建**结果）。
    不分作用域就会把两者串起来 —— 那正是第一次实现漏掉全部 91 处的原因。

    作用域链：方法 → 类 → 模块。任何拿不准的写法一律**不算活**（fail-closed）。
    """
    tree = ast.parse(source)

    def scope_map(body: list[ast.stmt]) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for node in body:
            if not isinstance(node, ast.Assign):
                continue
            text = ast.unparse(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    mapping.setdefault(target.id, []).append(text)
        return mapping

    module_scope = scope_map(tree.body)
    class_scopes: dict[str, dict[str, list[str]]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_scopes[node.name] = scope_map(node.body)

    def bound_to_live(
        name: str,
        scopes: list[dict[str, list[str]]],
        seen: frozenset[str] = frozenset(),
    ) -> bool:
        if name in seen:
            return False
        for scope in scopes:
            for text in scope.get(name, ()):
                if LIVE_LEDGER_MARKER in text:
                    return True
            for other, texts in scope.items():
                if other == name:
                    continue
                for text in texts:
                    if re.search(rf"\b{re.escape(name)}\b", text) and bound_to_live(
                        other, scopes, seen | {name}
                    ):
                        return True
        return False

    live: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (
            isinstance(value, ast.Subscript)
            and isinstance(value.slice, ast.Constant)
            and value.slice.value == "summary"
        ):
            continue
        base = value.value
        if not isinstance(base, ast.Name):
            continue
        scopes = [module_scope]
        # 找到该赋值所在的方法与类，拼出作用域链
        for class_node in tree.body:
            if not isinstance(class_node, ast.ClassDef):
                continue
            if class_node.name not in class_scopes:
                continue
            for sub in class_node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if any(node is inner for inner in ast.walk(sub)):
                        scopes = [
                            scope_map(sub.body),
                            class_scopes[class_node.name],
                            module_scope,
                        ]
                        break
        if not bound_to_live(base.id, scopes):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                live.add(target.id)
    return live


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument(
        "--target",
        type=pathlib.Path,
        default=pathlib.Path("tests/test_audit_rom_byte_coverage.py"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    target = args.target if args.target.is_absolute() else root / args.target
    ledger = root / "sequel/rom-byte-coverage.json"
    live = json.loads(ledger.read_text(encoding="utf-8"))["summary"]
    source = target.read_text(encoding="utf-8")
    receivers = _live_summary_receivers(source)

    changes: list[tuple[int, str, str, int, int, str]] = []
    for match in PATTERN.finditer(source):
        base = match.group("base")
        if base not in receivers:
            continue
        key = match.group("key_name")
        if key not in live:
            continue
        literal = int(match.group("lit").replace("_", ""))
        current = live[key]
        if current == literal:
            continue  # 仍然成立 → 留着当等号护栏
        method = (
            "assertLessEqual" if key in SHRINKING_KEYS else "assertGreaterEqual"
        )
        line = source.count("\n", 0, match.start()) + 1
        changes.append((line, key, method, literal, current, base))

    print(f"目标文件：{target.relative_to(root)}")
    print(f"活账本摘要键数：{len(live)}；陈旧快照断言：**{len(changes)}** 处")
    for line, key, method, literal, current, _ in changes[:8]:
        print(f"  行 {line:6d}  {key:38s} {literal:>12,} → {method:<19s} (活值 {current:,})")
    if len(changes) > 8:
        print(f"  ... 其余 {len(changes) - 8} 处同形")

    if args.dry_run or not args.apply:
        print("（dry-run，未写盘）")
        return 0

    def replace(match: re.Match[str]) -> str:
        base = match.group("base")
        if base not in receivers:
            return match.group(0)
        key = match.group("key_name")
        if key not in live:
            return match.group(0)
        literal = int(match.group("lit").replace("_", ""))
        if live[key] == literal:
            return match.group(0)
        method = "assertLessEqual" if key in SHRINKING_KEYS else "assertGreaterEqual"
        return (
            f'{match.group("indent")}{match.group("obj")}.{method}('
            f'{base}["{key}"], {match.group("lit")})'
        )

    updated = PATTERN.sub(replace, source)

    # 第二形态：投影总量的元组断言 → 拆成逐项的界
    def replace_tuple(match: re.Match[str]) -> str:
        expected_parts = _split_top_level(match.group("expected"))
        actual_parts = _split_top_level(match.group("actual"))
        if len(expected_parts) != len(actual_parts) or not expected_parts:
            return match.group(0)
        numbers: list[int] = []
        for part in expected_parts:
            cleaned = part.replace("_", "").replace(",", "").strip()
            if not cleaned.isdigit():
                return match.group(0)
            numbers.append(int(cleaned))
        # 只有**所在函数读了活账本**的才转换：这类投影依赖活账本基线，
        # 每次晋升都会漂移；而批次内的局部计数（与账本无关）必须原样保留。
        if LIVE_LEDGER_MARKER not in _enclosing_scopes_source(
            source, match.start()
        ):
            return match.group(0)
        indent = match.group("indent")
        lines: list[str] = []
        for number, actual in zip(numbers, actual_parts):
            # 方向必须按**键名**判（unknown_bytes 只会缩小）；实参是
            # 无名表达式时才回退到「有没有减号」的启发式。
            key_match = re.search(r'\["(?P<key>[A-Za-z0-9_]+)"\]$', actual)
            if key_match is not None and key_match.group("key") in SHRINKING_KEYS:
                method = "assertLessEqual"
            elif key_match is not None:
                method = "assertGreaterEqual"
            else:
                method = "assertLessEqual" if "-" in actual else "assertGreaterEqual"
            lines.append(
                f"{indent}{match.group('obj')}.{method}({actual}, {number:_})"
            )
        return "\n".join(lines)

    tuple_matches = list(TUPLE_PATTERN.finditer(updated))
    converted = 0
    for match in tuple_matches:
        replacement = replace_tuple(match)
        if replacement != match.group(0):
            converted += 1
    updated = TUPLE_PATTERN.sub(replace_tuple, updated)
    if tuple_matches:
        print(f"投影元组断言：发现 {len(tuple_matches)} 处，改写 **{converted}** 处")

    # 第三形态：按 key 取活账本摘要的生成器元组
    def replace_generator(match: re.Match[str]) -> str:
        numbers = [
            int(part.replace("_", ""))
            for part in _split_top_level(match.group("expected"))
        ]
        keys = [
            part.strip().strip('"')
            for part in _split_top_level(match.group("keys"))
            if part.strip()
        ]
        if len(numbers) != len(keys) or not keys:
            return match.group(0)
        indent = match.group("indent")
        lines: list[str] = []
        for key, number in zip(keys, numbers):
            method = "assertLessEqual" if key in SHRINKING_KEYS else "assertGreaterEqual"
            lines.append(
                f'{indent}{match.group("obj")}.{method}('
                f'{match.group("base")}["summary"]["{key}"], {number:_})'
            )
        return "\n".join(lines)

    generator_matches = list(GENERATOR_PATTERN.finditer(updated))
    generator_converted = 0
    for match in generator_matches:
        if replace_generator(match) != match.group(0):
            generator_converted += 1
    updated = GENERATOR_PATTERN.sub(replace_generator, updated)
    if generator_matches:
        print(
            f"生成器元组断言：发现 {len(generator_matches)} 处，"
            f"改写 **{generator_converted}** 处"
        )

    # 第四形态：对**全量**活账本 claims 求得的聚合
    #     aggregate = coverage_auditor._cfg_code_aggregate(coverage["claims"])
    #     self.assertEqual(172_148, aggregate["cfg_reachable_thumb_code_bytes"])
    # 只有这种「输入是全量活账本 claims」的聚合才会随晋升漂移；
    # 「prior + 本包 claim」这类子集投影的冻结值是**对的**，必须原样保留。
    full_ledger_aggregates: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        rendered = ast.unparse(node.value)
        if "_cfg_code_aggregate" not in rendered:
            continue
        if not re.search(r"\[['\"]claims['\"]\]", rendered):
            continue
        for binding in node.targets:
            if isinstance(binding, ast.Name):
                full_ledger_aggregates.add(binding.id)

    if full_ledger_aggregates:
        print(
            "全量活账本聚合变量："
            + ", ".join(sorted(full_ledger_aggregates))
        )

    def replace_full_aggregate(match: re.Match[str]) -> str:
        base = match.group("base")
        if base not in full_ledger_aggregates:
            return match.group(0)
        key = match.group("key_name")
        if key not in live:
            return match.group(0)
        literal = int(match.group("lit").replace("_", ""))
        if live[key] == literal:
            return match.group(0)
        method = "assertLessEqual" if key in SHRINKING_KEYS else "assertGreaterEqual"
        return (
            f'{match.group("indent")}{match.group("obj")}.{method}('
            f'{base}["{key}"], {match.group("lit")})'
        )

    updated = FULL_AGGREGATE_PATTERN.sub(replace_full_aggregate, updated)

    # 第五形态：整字典断言
    #     self.assertEqual({"cfg_…": 165_572, …}, aggregate)
    # 数字项 → 界；摘要项（sha256）→ 与活账本对拍（它不单调，不能当界）。
    def ledger_variable(scope_text: str) -> str | None:
        """找该作用域里从活账本读出来的变量名（``coverage`` 之类）。

        在**全文件** AST 里找候选，再用作用域文本筛选 —— 作用域片段本身
        不是合法 Python，不能单独 parse。
        """
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Assign):
                continue
            if LIVE_LEDGER_MARKER not in ast.unparse(node.value):
                continue
            for binding in node.targets:
                if isinstance(binding, ast.Name) and re.search(
                    rf"\b{re.escape(binding.id)}\b", scope_text
                ):
                    return binding.id
        return None

    def replace_dict(match: re.Match[str]) -> str:
        base = match.group("base")
        if base not in full_ledger_aggregates:
            return match.group(0)
        body = match.group("body")
        entries = re.findall(
            r'"(?P<key>[A-Za-z0-9_]+)"\s*:\s*'
            r'(?P<value>\(?\s*[0-9][0-9_]*\s*\)?|"[0-9a-f]{64}")',
            body,
        )
        if not entries:
            return match.group(0)
        scope = _enclosing_scopes_source(source, match.start())
        ledger_var = ledger_variable(scope)
        indent = match.group("indent")
        lines: list[str] = []
        for key, value in entries:
            if value.strip("() ").replace("_", "").isdigit():
                number = int(value.strip("() ").replace("_", ""))
                if key in live and live[key] != number:
                    method = (
                        "assertLessEqual"
                        if key in SHRINKING_KEYS
                        else "assertGreaterEqual"
                    )
                    lines.append(
                        f'{indent}{match.group("obj")}.{method}('
                        f'{base}["{key}"], {number:_})'
                    )
                else:
                    lines.append(
                        f'{indent}{match.group("obj")}.assertEqual('
                        f'{base}["{key}"], {number:_})'
                    )
            else:
                if ledger_var is None:
                    continue
                lines.append(
                    f'{indent}{match.group("obj")}.assertEqual('
                    f'{ledger_var}["summary"]["{key}"], {base}["{key}"])'
                )
        if not lines:
            return match.group(0)
        return "\n".join(lines)

    dict_matches = list(DICT_PATTERN.finditer(updated))
    dict_converted = 0
    for match in dict_matches:
        if replace_dict(match) != match.group(0):
            dict_converted += 1
    updated = DICT_PATTERN.sub(replace_dict, updated)
    if dict_matches:
        print(
            f"整字典断言：发现 {len(dict_matches)} 处，改写 **{dict_converted}** 处"
        )

    if updated == source:
        print("没有任何改动（幂等）")
        return 0
    target.write_text(updated, encoding="utf-8")
    print(f"已写盘：{len(changes)} 处改成上下界断言")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
