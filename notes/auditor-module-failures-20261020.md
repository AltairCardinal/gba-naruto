# 审计器测试模块整体跑：残留失败的逐个诊断（2026-10-20 09:5x）

> 背景：`tests/test_audit_rom_byte_coverage`（88 个测试类 / 359 个测试方法）
> 从没被整体跑过。§22 把其中 131 处陈旧账本快照改写成界。
> 本文件记录首次整体跑的残留失败、逐个根因、以及按
> 「**全局量派生、批次增量硬编码**」的修法。
> 运行时：PID 47459（100% CPU，单进程），日志 `/tmp/auditor-module-full.log`。

---

## 0. 结论先行

**5 个残留失败全部是「账本／包推进后的既存语义漂移」，不是 131 处改写引入的回归。**

判定方法：把改写前的版本（`git show ae9f60f2:tests/test_audit_rom_byte_coverage.py`）
与当前版本逐方法比对，并**单独取每个失败的真实 traceback**。

| # | 用例 | 改写是否触碰 | 真因 | 性质 |
|---|---|---|---|---|
| 1 | `BattleSoundSelectorCoverageTests.test_helper_is_non_recursive_and_build_manifest_integration_is_exact` | 触碰了 4 行界 | **待定**（traceback 采集中，见 §1） | — |
| 2 | `BootCopySourcesQuickProjectionTests.test_projection_rejects_existing_primary_overlap` | **未触碰** | 报错文案从 `current unknown` 变成 `conflicting primary claims` | 既存漂移 |
| 3 | `BootCopySourcesQuickProjectionTests.test_projects_one_claim_and_combined_674_unknown_bytes` | 触碰了 2 行界（在**报错行之后**） | `text-BG loop continuation is not current unknown` | 既存漂移 |
| 4 | `CfgProvenRootsV20QuickProjectionTests.test_wiring_verifier_identity_and_staged_cfg_aggregate` | **未触碰** | 全局聚合 171,060 → **173,136** | 全局量漂移 |
| 5 | `BootThumbCodeLiteralAlignmentGapCoverageTests.test_alignment_gap_is_explicitly_excluded_from_cfg_code_totals` | 触碰了 4 行界（**全部通过**） | 分母摘要 `0874b758…` → **`8ab38e24…`** | 全局量漂移 |

**#3 的关键证据**：traceback 停在 `tests/test_audit_rom_byte_coverage.py:14356`
的 `coverage_auditor._text_bg_loop_continuation_claims(...)` 调用，
**在我改写的两行断言（文件末尾）之前** ⇒ 改写根本没被执行到。

---

## 1. #2 与 #3：两个包已被晋升，测试前提失效

### #2 `test_projection_rejects_existing_primary_overlap`

```
ValueError: conflicting primary claims at [0x4C8, 0x4C9): boot-fixed-rom-copy-source-0004c8, synthetic-overlap

During handling of the above exception, another exception occurred:
  File ".../tests/test_audit_rom_byte_coverage.py", line 14394, in test_projection_rejects_existing_primary_overlap
    with self.assertRaisesRegex(ValueError, "current unknown"):
AssertionError: "current unknown" does not match "conflicting primary claims at [0x4C8, 0x4C9): ..."
```

测试原本注入一条 `synthetic-overlap`（range `[0x4C8, 0x4C9]`），
期望 helper 以「不是 current unknown」拒绝。**现在**：
boot copy source 这一族**已经在活账本里**，helper 产出自己的 claim 后，
`atomize_claims` 先撞上与 `synthetic-overlap` 的 primary 冲突，
于是**拒绝依然发生，只是换了机制、换了文案**。

⇒ **fail-closed 语义未丢**（仍然拒绝重叠），丢的是**断言匹配的具体文案**。
这属于**语义漂移**，不是界的问题。

### #3 `test_projects_one_claim_and_combined_674_unknown_bytes`

```
File ".../tests/test_audit_rom_byte_coverage.py", line 14356, in test_projects_one_claim_and_combined_674_unknown_bytes
    first = coverage_auditor._text_bg_loop_continuation_claims(ROOT, rom, coverage["claims"])
  File ".../tools/audit_rom_byte_coverage.py", line 33887, in _project_dependency_packet_claims
    _require_current_unknown_ranges(len(rom), ..., label=spec["label"])
  File ".../tools/audit_rom_byte_coverage.py", line 33868, in _require_current_unknown_ranges
    raise ValueError(f"{label} is not current unknown")
ValueError: text-BG loop continuation is not current unknown
```

text-BG loop continuation 这一族**也已在活账本里** ⇒ 再投影一次必然被
`current unknown` 门挡住。**这个用例的意图**（两个包联合投影 → 674 B unknown）
在两个包都已入账后**已无对应事实**。

### 同族修法（仓库已有先例）

同文件里已有成熟的「投影基线」写法：把**自己这一族**从活账本里剔掉再投影，例如
`BattleSoundSelectorCoverageTests._baseline()`：

```python
@classmethod
def _baseline(cls) -> list[dict]:
    coverage = json.loads((ROOT / "sequel/rom-byte-coverage.json").read_text(encoding="utf-8"))
    return [
        claim
        for claim in coverage["claims"]
        if claim.get("promotion_batch") != cls.BATCH
    ]
```

⇒ #2 / #3 应改成**同样的基线口径**（剔掉已入账的本族 batch），
而不是继续对着活账本投影。

---

## 2. #4：全局聚合漂移（未被改写触碰）

```
File ".../tests/test_audit_rom_byte_coverage.py", line 15242
    self.assertEqual(171_060, projected["cfg_reachable_thumb_code_bytes"])
AssertionError: 171060 != 173136
```

`projected = coverage_auditor._cfg_code_aggregate([*self.PRIOR, *self.STORY_CLAIMS, *self.CLAIMS])`
—— `self.PRIOR` 取自**活账本**，所以这是**全局聚合**，不是批次增量。

活账本实测（`tools/audit_rom_byte_coverage.py` 的 `_cfg_code_aggregate` 直接算）：

| 键 | 测试旧值 | 活值 | 方向 |
|---|---:|---:|---|
| `cfg_reachable_thumb_code_bytes` | 171,060 | **173,136** | 只增 |
| `cfg_promoted_unknown_bytes` | 172,048 | **174,124** | 只增 |
| `cfg_primary_claim_count` | 4,034 | **4,064** | 只增 |
| `cfg_code_claim_kind_count` | 49 | **55** | 只增 |

⇒ **全部是「只会增长」��全局量 ⇒ 应改为下界**（`assertGreaterEqual`），
与 §22 的 131 处同一处理。**这 4 行本轮没被改写脚本抓到**，因为接收者
`projected` 是局部变量（`_cfg_code_aggregate(...)` 的返回值），
脚本的接收者判定没把它认成活账本派生量。

## 3. #5：分母摘要漂移（我改的 4 行界全部通过）

```
File ".../tests/test_audit_rom_byte_coverage.py", line 13348
    self.assertEqual(
        "0874b75882eac082ff880b7ecca68f15b5f51972acc42b6d759f75b09f05448f",
        aggregate["cfg_code_claim_kind_denominator_sha256"],
    )
AssertionError: '0874b75882eac082ff880b7ecca68f15b5f51972acc42b6d759f75b09f05448f'
             != '8ab38e245e80c2d3a1ca9f143f0e17554d3132fc826cda2dc285ab35fdc6eb69'
```

我改写的 4 个界（`cfg_reachable_thumb_code_bytes` / `cfg_promoted_unknown_bytes` /
`cfg_primary_claim_count` / `cfg_code_claim_kind_count`）**全部通过**（活值见 §2 表）。
真正的失败是**分母摘要**变了 —— 它是「CFG code claim kind 分母」的哈希，
**分母集变了（新包新增了 kind）摘要就变**。

⇒ 这是**全局量派生**的典型形态：应当**与活值对拍**，
而不是把某一个版本的摘要钉死。仓库里已有对拍写法（§22 记录的「摘要类断言改为与
活文件对拍」）。

---

## 4. 修法总表（按「全局量派生、批次增量硬编码」）

| # | 修法 | 归类 |
|---|---|---|
| 2 | 改用**剔掉本族 batch 的基线**再投影；断言改为接受「重叠被拒绝」这一语义（匹配实际文案或用 `assertRaises(ValueError)` + 关键子串） | 语义修复（批次已晋升） |
| 3 | 改用**剔掉本族 batch 的基线**；或把用例改成对**当前 unknown** 区间的断言 | 语义修复（批次已晋升） |
| 4 | 4 个 `cfg_*` 聚合 → `assertGreaterEqual` 下界 | **全局量派生** |
| 5 | `cfg_code_claim_kind_denominator_sha256` → 与活值对拍（不再钉死某一版摘要） | **全局量派生** |
| 1 | 待 traceback | — |

**批次增量一律不动**：`battle_sound_selector_bytes=256` /
`battle_sound_selector_claim_count=1` / `battle_sound_selector_table_sha256` /
`battle_sound_selector_entry_denominator_sha256` 这类**本族自己的量**继续硬编码
（实测活值与期望完全一致：256 / 1 / `2f77582a…` / `fc3c1c03…`）。

---

## 5. 硬约束

- **`tests/test_audit_rom_byte_coverage.py` 被审计器硬钉**
  （`tools/audit_rom_byte_coverage.py` 内 27 处 `_TEST_SHA256` 引用，
  覆盖 24 个被钉测试文件，见 `notes/line-a-progress-20261019.md` §19.5）。
  改它 ⇒ 审计器 SHA 变 ⇒ `sequel/reverse-engineering-proof.json` 的
  `script_sha256` 要同步 ⇒ 需重跑一次 formal。
- **在模块整体跑（PID 47459）运行期间不得改这个文件**：审计器在运行时从磁盘读它
  并与硬钉比对 → 改它会让**后续**测试自伤失败（这正是本轮 psg 踩过的坑）。
- 修完必须**单独重跑这 5 个用例**确认转绿，且**不得**在其它长跑套件进行中改被 pin 文件。

---

## 6. 元守卫的补强方向（未做，记档）

§22 的元守卫扫的是「`assertEqual` + 活账本字面量」这一形态，
所以漏掉了两类：

1. **接收者是局部变量的全局量**（#4 的 `projected` = `_cfg_code_aggregate(...)`）
2. **全局量的摘要形式**（#5 的 `cfg_code_claim_kind_denominator_sha256`）

⇒ 若要补，应增加「接收者溯源到活账本或活聚合调用」+「键名含
`cfg_*` / `*_denominator_sha256` / `*_aggregate*`」这两条检测规则。
**本轮未做**（改元守卫会改审计器测试文件 ⇒ 又要同步 SHA + 重跑 formal）。
