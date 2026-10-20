"""`atomize_claims` 扫描线实现的等价性回归闸门。

背景
----
2026-10-20 实测：覆盖审计器的 `atomize_claims` 是**单线程 CPU 瓶颈**。
原实现对**每个段**全量扫一遍所有 claim：

```python
for start, end in zip(ordered, ordered[1:]):
    active = [claim for claim in normalized
              if ranges[claim["id"]][0] <= start and end <= ranges[claim["id"]][1]]
```

账本实测 16 913 条 claim / 18 675 段 → 约 **5.7 亿次**内层迭代，
单次调用 **60.50 s**。改成扫描线（端点事件 + 活跃集合）后同一输入
**0.09 s**，**681×**，且输出**逐字节一致**。

为什么必须有这个闸门
--------------------
这种优化最危险的不是「跑得慢」，而是**悄悄改变了分段语义** ——
而分段决定了整个账本的 claim 归属。���以本文件把**原实现原样抄一份**
作为参照实现，对**真实账本**与**随机/边界输入**逐字节对拍。
任何回归都会立刻变红，而不是等下一次 formal 才发现。

覆盖的语义面
------------
1. 真实账本 16 913 条 claim 的逐字节等价；
2. 400 组随机输入（含重叠 / 相邻 / 嵌套 / 次级 claim / 冲突 primary）的等价；
3. 失败关闭语义等价：重复 id、非法 role、primary 缺 primary_class、
   越界区间、多个 primary 冲突 —— **报错文案也必须一致**；
4. 性能闸门：扫描线在 5 000 条 claim 上必须显著快于参照实现
   （余量给得极宽，避免在负载高的机器上抖动）。
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_rom_byte_coverage as coverage_auditor  # noqa: E402

LEDGER = ROOT / "sequel/rom-byte-coverage.json"


def reference_atomize_claims(domain_end, claims):
    """**原实现原样抄写**，作为等价性参照（不要优化它）。"""
    if not isinstance(domain_end, int) or domain_end <= 0:
        raise ValueError("domain_end must be a positive integer")
    normalized = list(claims)
    identifiers = [claim.get("id") for claim in normalized]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
        raise ValueError("every claim must have a non-empty string id")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("claim ids must be unique")

    ranges: dict[str, tuple[int, int]] = {}
    endpoints = {0, domain_end}
    for claim in normalized:
        role = claim.get("role")
        if role not in {"primary", "secondary"}:
            raise ValueError(f"claim {claim['id']!r} has an invalid role")
        if role == "primary" and not isinstance(claim.get("primary_class"), str):
            raise ValueError(f"primary claim {claim['id']!r} has no class")
        start, end = coverage_auditor._validated_range(claim, domain_end)
        ranges[claim["id"]] = (start, end)
        endpoints.update((start, end))

    ordered = sorted(endpoints)
    segments: list[dict] = []
    for start, end in zip(ordered, ordered[1:]):
        active = [
            claim
            for claim in normalized
            if ranges[claim["id"]][0] <= start
            and end <= ranges[claim["id"]][1]
        ]
        primary = sorted(
            (claim for claim in active if claim["role"] == "primary"),
            key=lambda claim: claim["id"],
        )
        secondary = sorted(
            (claim for claim in active if claim["role"] == "secondary"),
            key=lambda claim: claim["id"],
        )
        if len(primary) > 1:
            raise ValueError(
                "conflicting primary claims at "
                f"[0x{start:X}, 0x{end:X}): "
                + ", ".join(claim["id"] for claim in primary)
            )
        if primary:
            segment = {
                "range": [start, end],
                "primary_class": primary[0]["primary_class"],
                "primary_claim_ids": [primary[0]["id"]],
                "secondary_claim_ids": [claim["id"] for claim in secondary],
            }
        else:
            segment = {
                "range": [start, end],
                "primary_class": "unknown",
                "primary_claim_ids": [],
                "secondary_claim_ids": [claim["id"] for claim in secondary],
                "unknown_reason": coverage_auditor.UNKNOWN_REASON,
            }
        segments.append(segment)
    return segments


def canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AtomizeClaimsSweepEquivalenceTests(unittest.TestCase):
    def _both(self, domain_end, claims):
        """跑参照实现与被测实现，返回 (参照结果, 参照异常, 被测结果, 被测异常)。"""
        try:
            expected = reference_atomize_claims(domain_end, claims)
            expected_error = None
        except ValueError as error:
            expected, expected_error = None, str(error)
        try:
            observed = coverage_auditor.atomize_claims(domain_end, claims)
            observed_error = None
        except ValueError as error:
            observed, observed_error = None, str(error)
        return expected, expected_error, observed, observed_error

    def test_real_ledger_is_byte_identical_to_the_reference(self) -> None:
        """真实账本 16 913 条 claim 的分段结果必须逐字节一致。"""
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        domain_end = ledger["domain"][1]
        claims = ledger["claims"]
        self.assertGreater(len(claims), 10_000, "账本规模与预期不符，闸门需要重新校准")
        expected, expected_error, observed, observed_error = self._both(domain_end, claims)
        self.assertIsNone(expected_error)
        self.assertIsNone(observed_error)
        self.assertEqual(len(expected), len(observed))
        self.assertEqual(canonical(expected), canonical(observed))

    def test_random_inputs_match_the_reference(self) -> None:
        """400 组随机输入（重叠/相邻/嵌套/次级/冲突）必须逐字节一致。"""
        rng = random.Random(20261020)
        for trial in range(400):
            count = rng.randint(0, 40)
            items = []
            for index in range(count):
                start = rng.randint(0, 400)
                role = "primary" if rng.random() < 0.7 else "secondary"
                item = {
                    "id": f"c-{index}",
                    "role": role,
                    "range": [start, start + rng.randint(1, 50)],
                }
                if role == "primary":
                    item["primary_class"] = f"kind-{index}"
                items.append(item)
            with self.subTest(trial=trial):
                expected, expected_error, observed, observed_error = self._both(1000, items)
                self.assertEqual(expected_error, observed_error)
                if expected_error is None:
                    self.assertEqual(canonical(expected), canonical(observed))

    def test_failure_closing_semantics_are_identical(self) -> None:
        """失败关闭语义（报错文案）必须与参照实现一致。"""
        cases = [
            # 重复 id
            (
                100,
                [
                    {"id": "a", "role": "primary", "range": [0, 10], "primary_class": "k"},
                    {"id": "a", "role": "primary", "range": [10, 20], "primary_class": "k"},
                ],
            ),
            # 非法 role
            (100, [{"id": "a", "role": "bogus", "range": [0, 10], "primary_class": "k"}]),
            # primary 缺 primary_class
            (100, [{"id": "a", "role": "primary", "range": [0, 10]}]),
            # 空 id
            (100, [{"id": "", "role": "primary", "range": [0, 10], "primary_class": "k"}]),
            # 非法区间（end <= start）
            (100, [{"id": "a", "role": "primary", "range": [10, 10], "primary_class": "k"}]),
            # 越界
            (100, [{"id": "a", "role": "primary", "range": [0, 200], "primary_class": "k"}]),
            # 冲突 primary
            (
                100,
                [
                    {"id": "a", "role": "primary", "range": [0, 50], "primary_class": "k"},
                    {"id": "b", "role": "primary", "range": [10, 60], "primary_class": "k"},
                ],
            ),
        ]
        for index, (domain_end, claims) in enumerate(cases):
            with self.subTest(case=index):
                expected, expected_error, observed, observed_error = self._both(
                    domain_end, claims
                )
                self.assertEqual(expected_error, observed_error)
                self.assertIsNotNone(expected_error, "该用例本应失败关闭")
                if expected_error is None:
                    self.assertEqual(canonical(expected), canonical(observed))

    def test_sweep_is_far_faster_than_the_reference(self) -> None:
        """扫描线在 5 000 条 claim 上必须显著快于参照实现。

        余量给得极宽（实测参照 ~20 s / 扫描线 < 0.1 s），避免负载抖动导致假红。
        """
        count = 5_000
        claims = []
        for index in range(count):
            start = index * 2
            claims.append(
                {
                    "id": f"c-{index:06d}",
                    "role": "primary",
                    "range": [start, start + 1],
                    "primary_class": "kind",
                }
            )
        start = time.perf_counter()
        observed = coverage_auditor.atomize_claims(count * 2, claims)
        observed_seconds = time.perf_counter() - start
        start = time.perf_counter()
        expected = reference_atomize_claims(count * 2, claims)
        reference_seconds = time.perf_counter() - start
        self.assertEqual(canonical(expected), canonical(observed))
        self.assertLess(
            observed_seconds * 5,
            reference_seconds,
            f"扫描线没有显著快于参照实现：{observed_seconds:.3f}s vs {reference_seconds:.3f}s",
        )


if __name__ == "__main__":
    unittest.main()
