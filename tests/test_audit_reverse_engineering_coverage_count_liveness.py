"""覆盖计数的「活账本一致性」守卫。

背景
----
2026-10-20 池 3 晋升（unknown 87,631 → 86,089）打破了 proof 回归套件里的
**12 个测试**。根因不是晋升本身，而是：套件把「会随每次晋升变化的累计量」
写成了字面量（149,280 / 6,142,176 / 15,940 / 17,344 / 148,778 / 25,284 / …），
而这些字面量在每次晋升后都会变成历史值。

本文件是**元守卫**：它不再等 93 个测试跑完才报告失败，而是在秒级时间内
直接回答两个问题——

1. proof 合同里声明的 ``/summary/*`` 断言，是否与活账本逐项相等；
2. 任何测试文件里，是否还存在「拿字面量去比一个活账本键」的写法。

只要这两个问题任一为否，晋升链就会在**跑重活之前**失败关闭，
而不是在 45 分钟的套件末尾才吐出一串 F。

三类量的分类是本守卫的核心契约：

- **全局量 / 累计型**（随晋升变化）→ 必须写成 ``LIVE_COVERAGE_SUMMARY[...]`` 派生；
- **批次增量**（落地后固定）→ 必须保持硬编码，那是真正的回归护栏；
- **历史收据里的历史值**（有意钉住过去）→ 允许，但必须登记在
  ``HISTORICAL_PINNED`` 里并由本守卫复核其字面量没被悄悄放宽。

不在活账本里的键一律跳过——对拍不了就不假装验证过。
"""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sequel/rom-byte-coverage.json"
SPEC = ROOT / "sequel/reverse-engineering-proof.json"
TESTS_DIR = ROOT / "tests"
PROOF_TEST = TESTS_DIR / "test_audit_reverse_engineering_proof.py"

#: 必须保持「派生」而非字面量的全局量 / 累计量。
#:
#: ``consumer_code_slice_*`` 同属累计型：它是消费者代码切片族的累计总量，
#: 本轮实测随池 3 晋升从 25,284 / 111 变为 27,404 / 116。
GLOBAL_KEYS = (
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

#: 有意钉住**历史收据**里历史值的断言：文件名 → {summary 键: 历史字面量}。
#:
#: 这两处读的是 9-30 那次晋升冻结下来的 ``formal-report.json``，
#: 钉的是收据**当时**记录的 unknown_bytes = 87,631。
#: 它们不是活账本断言——活账本现在是 86,089，差值正是池 3 的 1,542 B。
#: 登记在此处是为了让「历史钉」不会悄悄扩大覆盖面。
HISTORICAL_PINNED = {
    "test_rom_small_cfg_batch_canonical.py": {"unknown_bytes": 87_631},
    "test_rom_renderer_script_pointer_pool_canonical.py": {"unknown_bytes": 87_631},
}

COVERAGE_VERIFIER = "tools/audit_rom_byte_coverage.py"


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _const_int(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _subscript_chain(node: ast.AST) -> list[str] | None:
    """把 ``a["b"]["c"]`` 还原成 ``["b", "c"]``；任一层不是字符串常量则返回 None。"""
    keys: list[str] = []
    while isinstance(node, ast.Subscript):
        value = _const_str(node.slice)
        if value is None:
            return None
        keys.append(value)
        node = node.value
    keys.reverse()
    return keys


def _summary_key(node: ast.AST) -> str | None:
    """把一个下标表达式解析成它指向的 summary 键名。

    支持两种写法：

    - ``coverage["contract"]["assertions"]["/summary/unknown_bytes"]``
    - ``rom_gate["rom_coverage_audit"]["summary"]["unknown_bytes"]``
    """
    keys = _subscript_chain(node)
    if not keys:
        return None
    if keys[-1].startswith("/summary/"):
        return keys[-1][len("/summary/") :]
    if len(keys) >= 3 and keys[-3] == "rom_coverage_audit" and keys[-2] == "summary":
        return keys[-1]
    return None


def _literal_assertions(source: str) -> list[tuple[int, str, int]]:
    """列出所有「字面量 vs summary 键」的断言，返回 (行号, 键, 字面量)。"""
    tree = ast.parse(source)
    found: list[tuple[int, str, int]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertEqual"
            and len(node.args) == 2
        ):
            continue
        left, right = node.args
        for literal_side, pointer_side in ((left, right), (right, left)):
            literal = _const_int(literal_side)
            if literal is None:
                continue
            key = _summary_key(pointer_side)
            if key is None:
                continue
            found.append((node.lineno, key, literal))
    return found


class CoverageCountLivenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.live = json.loads(LEDGER.read_text(encoding="utf-8"))["summary"]
        cls.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        coverage = next(
            item
            for item in cls.spec["gates"]["rom_byte_coverage"]["verifiers"]
            if item["command"][1] == COVERAGE_VERIFIER
        )
        cls.assertions = coverage["contract"]["assertions"]

    def test_spec_coverage_assertions_exist_in_live_ledger(self) -> None:
        """spec 声明的每个 /summary/* 断言都必须在活账本里有对应键。"""
        missing = sorted(
            pointer[len("/summary/") :]
            for pointer in self.assertions
            if pointer.startswith("/summary/")
            and pointer[len("/summary/") :] not in self.live
        )
        self.assertEqual([], missing)

    def test_spec_coverage_assertions_equal_live_ledger(self) -> None:
        """spec 声明的每个 /summary/* 断言值必须与活账本逐项相等。"""
        mismatched = []
        for pointer, declared in self.assertions.items():
            if not pointer.startswith("/summary/"):
                continue
            key = pointer[len("/summary/") :]
            if key not in self.live:
                continue
            if self.live[key] != declared:
                mismatched.append((key, declared, self.live[key]))
        self.assertEqual([], mismatched)

    def test_no_test_source_hardcodes_a_live_ledger_quantity(self) -> None:
        """任何测试文件都不得拿字面量去比一个活账本里存在的键。

        唯一例外是**登记过的历史钉**——它们钉的是冻结收据里的历史值。
        """
        stale: list[tuple[str, int, str, int, int]] = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "/summary/" not in source and "rom_coverage_audit" not in source:
                continue
            allowed = HISTORICAL_PINNED.get(path.name, {})
            for line, key, literal in _literal_assertions(source):
                current = self.live.get(key)
                if current is None:
                    continue
                if current == literal:
                    continue
                if allowed.get(key) == literal:
                    continue
                stale.append((path.name, line, key, literal, current))
        self.assertEqual([], stale)

    def test_historical_pins_are_still_pinned_to_the_old_value(self) -> None:
        """反向护栏：登记过的历史钉必须**仍然**钉在旧值上。

        如果有人把历史钉改成活账本当前值，登记就失去意义；
        如果有人把登记清空，覆盖面就被悄悄扩大了。
        """
        for name, pinned in HISTORICAL_PINNED.items():
            source = (TESTS_DIR / name).read_text(encoding="utf-8")
            for key, literal in pinned.items():
                observed = [
                    value
                    for _, asserted_key, value in _literal_assertions(source)
                    if asserted_key == key
                ]
                self.assertIn(
                    literal,
                    observed,
                    f"{name} 应当仍然钉住 {key}={literal}（9-30 收据的历史值）",
                )
                self.assertNotEqual(
                    self.live[key],
                    literal,
                    f"{name} 的 {key} 历史钉不得与活账本当前值相同，否则它不再是历史钉",
                )

    def test_global_quantities_are_derived_not_hardcoded(self) -> None:
        """全局量 / 累计量必须写成派生引用，不得回到字面量。"""
        source = PROOF_TEST.read_text(encoding="utf-8")
        hardcoded = sorted(
            (line, key, literal)
            for line, key, literal in _literal_assertions(source)
            if key in GLOBAL_KEYS
        )
        self.assertEqual([], hardcoded)

    def test_batch_increments_remain_hardcoded(self) -> None:
        """反向护栏：批次增量必须保持硬编码，不能被「一并派生」掉。

        取两个稳定的批次增量指针做样本——它们落地后不再变化，
        硬编码才是对它们的真正保护。
        """
        source = PROOF_TEST.read_text(encoding="utf-8")
        for key in (
            "positions_aux_dispatch_bytes",
            "cutscene_obj_alignment_gap_bytes",
        ):
            literals = [
                literal
                for _, asserted_key, literal in _literal_assertions(source)
                if asserted_key == key
            ]
            self.assertTrue(literals, f"批次增量 {key} 应当保持硬编码")
            self.assertEqual(
                {self.live[key]},
                set(literals),
                f"批次增量 {key} 的硬编码值必须与账本一致",
            )


if __name__ == "__main__":
    unittest.main()
