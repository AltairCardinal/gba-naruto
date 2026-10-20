# 审计器测试模块整体跑：残留失败的逐个诊断 + 57 处漏网/错向的全面排查（2026-10-20 09:5x–10:0x）

> 背景：`tests/test_audit_rom_byte_coverage`（88 个测试类 / 359 个测试方法）
> 从没被整体跑过。§22 把其中 131 处陈旧账本快照改写成界。
> 本文件记录首次整体跑的残留失败、逐个根因、按「**全局量派生、批次增量硬编码**」
> 的修法，以及**全文件 2,955 个 `assert*` 的全面 AST 排查**结果。
> 首次运行：PID 47459（100% CPU，单进程），日志 `/tmp/auditor-module-full.log`
> （停在 83 ok / 6 FAIL，25%）。**已按 §7 的判断停跑**，修复后重跑：
> **分 4 片并行**（见 §9），日志 `/tmp/auditor-shard{0,1,2,3}.log`。

---

## 0. 结论先行

**6 个残留失败全部是「账本／包推进后的既存语义漂移」，不是 131 处改写引入的回归。**

判定方法：把改写前的版本（`git show ae9f60f2:tests/test_audit_rom_byte_coverage.py`）
与当前版本逐方法比对，并**单独取每个失败的真实 traceback**。

| # | 用例 | 改写是否触碰 | 真因 | 性质 |
|---|---|---|---|---|
| 1 | `BattleSoundSelectorCoverageTests.test_helper_is_non_recursive_and_build_manifest_integration_is_exact` | 触碰了 4 行界（那 4 行**全部通过**） | `class_at(0x53E495)` 期望 `unknown`，实测 `fixed_index_u8_lookup_tail` | 既存漂移 |
| 2 | `BootCopySourcesQuickProjectionTests.test_projection_rejects_existing_primary_overlap` | **未触碰** | 报错文案从 `current unknown` 变成 `conflicting primary claims` | 既存漂移 |
| 3 | `BootCopySourcesQuickProjectionTests.test_projects_one_claim_and_combined_674_unknown_bytes` | 触碰了 2 行界（在**报错行之后**） | `text-BG loop continuation is not current unknown` | 既存漂移 |
| 4 | `CfgProvenRootsV20QuickProjectionTests.test_wiring_verifier_identity_and_staged_cfg_aggregate` | **未触碰** | 全局聚合 171,060 → **173,136** | 全局量漂移 |
| 5 | `BootThumbCodeLiteralAlignmentGapCoverageTests.test_alignment_gap_is_explicitly_excluded_from_cfg_code_totals` | 触碰了 4 行界（**全部通过**） | 分母摘要 `0874b758…` → **`8ab38e24…`** | 全局量漂移 |
| 6 | `MenuPortraitLz77PaletteAlignmentGapCoverageTests.test_promotes_exact_ranges_owner_boundaries_evidence_and_nonclaims` | **未触碰** | 全局聚合 6,127,495 → **6,205,367** | 全局量漂移 |

**#3 的关键证据**：traceback 停在 `tests/test_audit_rom_byte_coverage.py:14356`
的 `coverage_auditor._text_bg_loop_continuation_claims(...)` 调用，
**在我改写的两行断言（文件末尾）之前** ⇒ 改写根本没被执行到。

**#1 的关键证据**：`class_at(0x53E495)` 那一行在改写前后**逐字相同**；
活账本实测 `0x53E495` 归 `fixed-index-u8-tail-53e492`
（range `0x53E492..0x53E496`，class `fixed_index_u8_lookup_tail`，
batch `rom-fixed-index-u8-tail-v1`）—— 与本表的 `0x53E496` **相邻且不重叠**。

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

### 5.1 ✅ 更正：审计器**自己的**测试文件**没有被钉** ⇒ 本轮修改**不需要重跑 formal**

> **2026-10-20 09:5x 更正。** 本文件初稿写的是
> 「`tests/test_audit_rom_byte_coverage.py` 被审计器硬钉（27 处 `_TEST_SHA256` 引用）
> ⇒ 改它 ⇒ 审计器 SHA 变 ⇒ spec 同步 ⇒ 重跑 formal」。
> **那个判断是错的**，已实测推翻：

| 检查 | 结果 |
|---|---|
| 审计器钉的 62 个测试文件里有没有它 | **没有**（62 个全是 `test_export_*` / `test_verify_*` 的**上游包测试**） |
| `grep -n "test_audit_rom_byte_coverage" tools/audit_rom_byte_coverage.py` | 只有 **L7063 的一句注释**，无任何 SHA 比对 |
| `grep -c "test_audit_rom_byte_coverage" sequel/reverse-engineering-proof.json` | **0** |
| 审计器运行时读不读它 | **不读**（它不在 62 个 pin 目标里） |

那 27 处 `_TEST_SHA256` 引用是**这个测试文件在钉别人**（每个上游包的
`test_export_*` / `test_verify_*`），**不是**别人在钉它。

⇒ **改 `tests/test_audit_rom_byte_coverage.py` 不改变审计器 SHA**
⇒ **不需要**改 `sequel/reverse-engineering-proof.json` 的 `script_sha256`
⇒ **不需要重跑 formal**（formal v2 收据 `trust_anchor.spec_sha256 = 39b7ebd7…`
与审计器 SHA 都未变，旧收据继续有效）。

**同样不被钉的还有**（实测）：`tests/test_audit_reverse_engineering_coverage_count_liveness.py`
（元守卫模块）、`tests/test_audit_reverse_engineering_proof.py`（93 套件模块）——
它们只被**按路径引用**（元守卫扫 93 套件源码），没有 SHA 钉。

### 5.2 真正的硬约束

- **被钉的是那 62 个上游包测试**（`test_export_*` / `test_verify_*`）。
  改其中任何一个 ⇒ 审计器里对应的 `_TEST_SHA256` 常量要改 ⇒ 审计器 SHA 变
  ⇒ `sequel/reverse-engineering-proof.json` 的 `script_sha256` 要同步
  ⇒ **需重跑一次 formal**。本轮**没有**动这 62 个文件里的任何一个。
- **跑长套件期间不得改被 pin 的文件**：审计器在运行时从磁盘读它并与硬钉比对
  ⇒ 改它会让**后续**测试自伤失败（这正是本轮 psg 踩过的坑）。
  本轮的做法是**先停掉模块整体跑**（停在 83 ok / 6 fail，25%），再改文件，
  避免自伤污染。
- 修完必须**重跑整个模块**拿最终 summary，并**重跑 93 套件**
  （其中 `test_current_repository_does_not_overclaim_completion` 会检查
  仓库声明是否夸大，受本轮 notes 改动影响）。

---

## 6. 元守卫的补强方向（未做，记档）

§22 的元守卫扫的是「`assertEqual` + 活账本字面量」这一形态，
所以漏掉了两类：

1. **接收者是局部变量的全局量**（#4 的 `projected` = `_cfg_code_aggregate(...)`）
2. **全局量的摘要形式**（#5 的 `cfg_code_claim_kind_denominator_sha256`）

⇒ 若要补，应增加「接收者溯源到活账本或活聚合调用」+「键名含
`cfg_*` / `*_denominator_sha256` / `*_aggregate*`」这两条检测规则。
**本轮未做**（改元守卫会改审计器测试文件 ⇒ 又要同步 SHA + 重跑 formal）。
⚠️ 这条约束**不成立**（见 §5.1）：元守卫模块
`tests/test_audit_reverse_engineering_coverage_count_liveness.py` **也没有被钉**，
改它同样不需要同步 spec、不需要重跑 formal。

---

## 7. 全文件全面排查：57 处漏网 + 17 处**我自己引入的错向**（2026-10-20 10:0x）

只修 6 个已知失败是不够的——它们只是最先暴露的。对全文件
**88 个类 / 359 个方法 / 2,955 个 `assert*`（1,885 `assertEqual` + 280 界断言）**
做了 AST 全量遍历 + 按作用域解析接收者绑定链，得到 **57 处仍需处理**。

### 7.1 最重要的发现：**我上一轮的 131 处改写引入了 17 处新缺陷**

`commit c3e2b71c` 的**元组形态**改写用了一个方向启发式：
`method = "assertLessEqual" if "-" in actual else "assertGreaterEqual"`
——它把 `c["range"][1] - c["range"][0]` 里的**减号**误读成「这个量会缩小」，
于是给**只会增长的批次字节总量**加了**上界**；另一半把**批次 claim 数的等号**
放松成了下界。

| 类别 | 处数 | 后果 |
|---|---:|---|
| **上界留在了错误一侧**（批次字节总量） | 8 | 批次**合法变大**时**误报失败**（`assertLessEqual(sum(...), 94)` 而 94 是本包的固定字节数） |
| **批次等号被放松成下界**（批次 claim 数） | 8 | 批次**变小**这种**真回归漏报** |
| `non_claims` 长度等号被放松 | 1 | 同上（`assertGreaterEqual(len(row["non_claims"]), 4)`） |

涉及的 8 个包：`rom-boot-interwork-continuation-v1`(6 条/94 B)、
`rom-cfg-proven-roots-v19`(14 条/1,660 B)、`rom-unbound-chapter-script-tail-v1`(3/3,186)、
`rom-chapter-script-consumer-roots-v1`(2/16,175)、`rom-battle-condition-result-text-v1`(219/3,961)、
`rom-alternate-dialogue-table-v1`(161/3,200)、`rom-story-state-callback-cfg-v1`(13/702)、
`rom-story-state-entry-c4cc-v1`(2/220)。**全部还原为 `assertEqual`。**

> 元守卫第 12 项（界的方向）**当场抓到过一处**同类错向（`unknown_bytes` 用了
> `assertGreaterEqual`），但**没能覆盖这一类** —— 因为那 8 处的接收者是
> **批次增量**（本包自己的字节数），不是活账本量，守卫的「界的方向」规则
> 只对活账本派生量生效。**这 17 处如果不靠这次全量 AST 排查，会一直潜伏。**

### 7.2 §A：38 处仍写死的全局量（两种此前抓不到的形态）

1. **接收者是局部变量**（`projected` / `stable` / `classified` / `unknown` /
   `segments` / `claims`）——原脚本的接收者解析认不出（既非 `summary["key"]`
   也非全量 `["claims"]` 聚合）。
2. **投影族**：输入是 `[*self.PRIOR, *self.CLAIMS]` 的**子集聚合**，而
   `self.PRIOR` 本身就是**活账本按 `promotion_batch` 的过滤**
   ⇒ 投影值 = 活账本子集，随账本推进单调增长。

涉及的类：`V17V18HelperCfgQuickProjectionTests`（元组形态 1 处 → 4 条界）、
`PrebattleMenuControllerCfgQuickProjectionTests`、`StoryCallbackDependencyQuickProjectionTests`、
`StoryNextDependencyCfgQuickProjectionTests`、`BootRegisterInitDependencyCfgQuickProjectionTests`、
`CfgProvenRootsV17CoverageTests`、`CutsceneObjPaletteDefinitionAlignmentGapCoverageTests`、
`TileBgLz77PaletteAlignmentGapCoverageTests`、`BootThumbCodeLiteralAlignmentGapCoverageTests`。

### 7.3 §B：2 处全局分母摘要

`cfg_code_claim_kind_denominator_sha256` **不单调**（新增一个 staged kind 就变一次），
既不能当界、也不能钉死某一版 ⇒ 改为**与活注册表对拍**：
新增测试侧 helper `_expected_cfg_registry_sha256(claims)`，按审计器同一规则
（`stable` 注册表 + 实际观测到的 staged kind）重算摘要。
落点：`RomByteCoverageAuditTests`（`ad155f92…`）与 `CfgProvenRootsV15CoverageTests`（`0874b758…`）。

### 7.4 §C：约 430 处**确认是批次增量、必须保持硬编码**

逐条与活账本比对**全部与活值相等**（含 397 处包专属 `summary` 键 + 33 处包专属摘要
+ 各包自身 `len(claims)`）⇒ **不动**。这批是真正的回归护栏。

### 7.5 §E：活值算不出的站点（7 组，需实跑坐实）

- 5 个投影类的 `projected` 活值：聚合输入 = 活账本 + **生产函数重投影**的 claim。
  只能证明「若重投影结果 == 活账本中同批 claim，则活值 = 全量聚合」。
  该等价性已由 #4 独立证实（V20 的活值正是 173,136/174,124/4,064/55）。
- 4 个 gap 族与 V17 的 `classified` / `unknown` / `len(segments)` / `len(claims)`：
  已**精确验证** `|baseline| + |本包 claim| = 16,913`（menu 16,861+52、
  tile_bg 16,829+84、boot_thumb 16,901+12、cutscene_obj 16,909+4）⇒ 集合 = 全量活账本。

### 7.6 修复脚本

`notes/evidence/reverse-proof-update-20261020-v2/apply_global_quantity_bounds_20261020.py`
—— **54 个替换点**（覆盖 57 处断言变更；元组 1 点 → 4 条界），
幂等、`--dry-run`、**失败关闭**（每条必须在目标类块内恰好命中一次，
否则非 0 退出并打印全部问题）。
实测：dry-run → apply → 再 apply（幂等：「没有任何改动」）。

**元守卫 12/12 全绿**（5.952 s）：新写法（含 `assertEqual(674, …)` 的**批次增量
硬编码**、派生摘要、界的方向）完全符合「全局量派生、批次增量硬编码」。

---

## 8. 顺带统一：已晋升链包的「重投影基线」

§0 的 #2 / #3 病根是**同一个**：一个已经进入 canonical 账本的 packet，
**不能**再对着同一个账本投影一次——生产者的 current-unknown 门会直接拒绝
（`"<label> is not current unknown"` 或 `"<label> are not current unknown"`）。

本轮共发现 **6 处**这种过期投影点，分属 **4 个类**，其中 3 个类在首次整体跑时
**还没跑到**（首跑停在 25%）：

| 类 | 投影的已入账 packet |
|---|---|
| `TextBgLoopContinuationQuickProjectionTests` | text-BG loop continuation |
| `BootCopySourcesQuickProjectionTests` | text-BG loop continuation + boot copy source |
| `TextBgTaskClosureQuickProjectionTests` | 上述两个（`setUpClass`） |
| `FixedRendererScriptRecordsQuickProjectionTests` | 上述两个 + text-BG task closure（`setUpClass`） |

**统一修法**：新增模块级

```python
REPROJECTED_PACKET_CHAIN = (
    ("rom-text-bg-loop-continuation-v1", "_text_bg_loop_continuation_claims"),
    ("rom-boot-copy-sources-v1", "_boot_copy_source_claims"),
    ("rom-text-bg-task-closure-v1", "_text_bg_task_closure_claims"),
    ("rom-fixed-renderer-script-records-v1", "_fixed_renderer_script_record_claims"),
)
```

与两个 helper `_reproject_chain(coverage, rom, upto)` /
`_reproject_chain_baseline(coverage, upto)`：从活账本剔掉要重投影的批次，
再按**原链序**重投影 ⇒ 覆盖到的字节与账本一致，生产者的 current-unknown 门又能跑。

**为什么不能只修这 6 处失败**：另外 3 个类里的过期投影点**还没跑到**，
不一起修就会在重跑时整类 error（`setUpClass` 失败 ⇒ 该类全部用例 error）。
这正是「先跑 25% 拿到形态、再全量 AST 排查、再一次性修完」的价值。


---

## 9. 重跑方式：分 4 片并行（而不是单进程串行）

首次整体跑的实测速率：**83 个用例 / 71 分钟**（含各类的 `setUpClass` 里
`build_manifest` 与外部验证器冷重放），线性外推全部 359 个方法需要 **~5 小时**。
而这 5 小时里**什么都做不了**（被 pin 的文件不能改）。

处置：**停掉串行跑，改分 4 片并行**。

| 片 | 类数 | 方法数 | 日志 |
|---|---:|---:|---|
| shard0 | 17 | 90 | `/tmp/auditor-shard0.log` |
| shard1 | 24 | 90 | `/tmp/auditor-shard1.log` |
| shard2 | 24 | 90 | `/tmp/auditor-shard2.log` |
| shard3 | 23 | 89 | `/tmp/auditor-shard3.log` |

分片方式：按各类的**方法数**贪心分 4 片（重类先放，平衡到 89–90 个方法/片）。

**为什么安全**：
- 本模块的用例**只读**仓库；唯一会写盘的 `RomByteCoverageWritePathTests`
  写的是 `tempfile.TemporaryDirectory()`（已核实），**不碰** `sequel/rom-byte-coverage.json`。
- 本模块的类**互不依赖**（每个类自带 `setUpClass`），类内方法按字母序保持不变。
- 机器有 **12 逻辑核**，4 片各占 1 核，负载 ~2.3/12，swap 2,048 MiB（已用 1,176）。

**代价**（诚实记录）：分片结果**不能**与首次串行跑的**墙钟**直接比较；
它只回答「是否全绿」，不回答「串行要多久」。

---

## 10. 分 4 片的第一轮结果：9 个失败（不是 6 个）

首轮 4 片跑出的失败比 §0 记录的 6 个多，原因见 §10.1：**6 个是在只跑到 25% 时
看到的**，后面 3 个类在首轮启动时**还没排到**。

| # | 用例 | 所在类 | 真因（实测 traceback） |
|---|---|---|---|
| A | `test_projects_exact_30_records_and_four_packet_total` | `FixedRendererScriptRecordsQuickProjectionTests` | 过期投影点（§8）：本包自己已在账本里，基线没剔掉 |
| B | `test_projection_rejects_non_unknown_overlap` | 同上 | 同上 |
| C | `test_committed_manifest_has_exact_projected_totals_segments_and_limitation` | `MPlayMainSchedulerCoverageTests` | 硬编码段区间键 `(0x09A3DC,0x09A42C)` 被后继批次切开 ⇒ KeyError |
| D | `Mp2kNoteAllocatorCoverageTests` 的 3 个用例 | `Mp2kNoteAllocatorCoverageTests` | 拿最终账本重放生产者，撞 current-unknown 门 |
| E | `test_promotes_only_verified_current_unknown_windows` | `SpriteDefinitionResolvedWindowCoverageTests` | 同 D |
| F | `test_exact_seven_packet_projection_and_evidence` | `CfgConsumedLiteralBatchCoverageTests` | `non_claims` 条数**按批不同**（4/5/6），旧断言一律写死 4 |
| G | `test_promotes_exact_semantic_ranges_and_preserves_holes_and_rejection` | `CfgProvenRootsV15CoverageTests` | v15 的空洞/被拒范围被**后继批次 v16** 认领 |

### 10.1 A/B 与 §8 的关系：`_reproject_chain` 的语义漏洞

§8 的 `_reproject_chain(coverage, rom, upto)` 里 `upto` 兼任了两个职责：
「剔掉前 N 个批次」与「重建前 N 个批次」。但调用方真正需要的是**三件事**分开：

1. 剔掉本用例**自己要重投影**的那个包（否则生产者认领到自己已在账本里的字节）；
2. 剔掉**后继批次**（否则生产者看到的是最终账本而不是自己回合的账本）；
3. 重建前置链包（按原链序）。

修法：给 helper 加独立的 `excluded` 参数，**剔掉但不重建**：

```python
def _reproject_chain(coverage, rom, upto, excluded=()):
    rebuilt_batches = {batch for batch, _ in REPROJECTED_PACKET_CHAIN[:upto]}
    dropped_batches = rebuilt_batches | set(excluded)
    ...
```

调用方：`TextBgTaskClosureQuickProjectionTests` → `upto=2, excluded=("rom-text-bg-task-closure-v1",)`；
`FixedRendererScriptRecordsQuickProjectionTests` → `upto=3, excluded=("rom-fixed-renderer-script-records-v1",)`。

### 10.2 C：硬编码段区间键 ⇒ 改成派生比对

`MPlayMainSchedulerCoverageTests` 原本钉 5 个**段区间键**。其中
`(0x09A3DC, 0x09A42C)` 当初是 unknown 间隙，后来被
`armv4t_cfg_v2_consumed_literal_word` 与 `armv4t_cfg_proven_roots_v15_*`
合法切开 ⇒ 键不存在 ⇒ `KeyError: (631772, 631852)`。

**实测到的全局不变量**（本轮新发现，16,913 条 claim / 18,675 段全量核对）：

> **段表 = 主 claim 表的逐字节投影。**
> 6,205,367 个被认领字节逐个比对，错配 **0**；86,089 个 unknown 字节与
> `summary.unknown_bytes` **完全相等**；16,913 条 claim 的 `role` **全部**是
> `primary`（无第二角色）；主 claim 之间重叠 **0**。

这个不变量比「钉死区间键」**更强**：区间键只能证明「当初那个区间现在还是那样」，
而投影比对能证明「段表和 claim 表处处自洽」。于是新增模块级 helper：

```python
def _window_tiles(claims, segments, start, end):
    """tiles = 段表在窗口上的铺法；owner = 每字节的 (primary_class, promotion_batch)"""
```

C 改为：窗口必须**连续铺满** → 每段类别必须**等于**该字节的 claim 投影 →
本包自己认领的两段必须**原样在位**（`[[0x09A42C,0x09A684],[0x09A688,0x09A694]]`）
→ 窗口内其余字节**不得**挂在本包名下。

### 10.3 D/E：链时基线

D（mp2k）：`_mp2k_note_allocator_claims` 在 `build_manifest` 里排在
`_cfg_consumed_literal_batch_claims` **之前**；后者认领了本包排除邻居
`[0x09A6D2,0x09A6D8)` 里的 **4 个字节** `[0x09A6D4,0x09A6D8)`。
生产链里两者不重叠，所以账本是对的；但拿**最终账本**重放本包生产者，
生产者会看到「排除邻居已不是 unknown」⇒ raise
`MP2K note-allocator excluded bytes are no longer unknown`。
修法：`_baseline()` 里加 `LATER_BATCHES = ("rom-cfg-v2-consumed-literals-v1",)`。

E（sprite-definition）：本包**已晋升**（3 条 claim，`claim_kind ==
"sprite_definition_resolved_window_bytes"`），用最终账本重放 ⇒
`sprite-definition resolved-window promotion changed`。
修法：基线剔掉本包自己的 `claim_kind`。实测：剔掉后重放得回
**3 段 / 1,720 B**（`[0x12F598,0x12F7DC)`、`[0x12F7DC,0x12F818)`、
`[0x12F818,0x12FDA0)`），与账本一致。

D 在**已提交账本**上的断言同步改成逐字节派生：排除邻居的每个字节
要么仍是 `unknown`、要么归**别的批次**，但**绝不能**挂在本包名下。

### 10.4 F：`non_claims` 条数是**批次增量**

旧断言对所有 7 个批次一律 `assertEqual(4, len(row["non_claims"]))`。
实测每批自带清单长度不同：

| 批次 | `non_claims` 条数 |
|---|---:|
| `rom-cfg-proven-roots-batch-consumed-literals-v1` | 4 |
| `rom-cfg-v1-consumed-literals-v1` | 4 |
| `rom-cfg-v2-consumed-literals-v1` | 5 |
| `rom-cfg-v3-consumed-literals-v1` | 5 |
| `rom-cfg-v6-consumed-literals-v1` | 5 |
| `rom-battle-controller-consumed-literals-v1` | 5 |
| `rom-cfg-v2-shadowed-consumed-literals-v1` | 6 |

⇒ 写进 `EXPECTED` 表作为**每批硬编码的批次增量**（不是全局量，不该派生）。
⚠️ 侦察阶段报出来的 live 值 4 是**陈旧的**，真值 5——再次印证
「任何被引用的数字必须自己重测再落盘」。

### 10.5 G：v15 空洞被 v16 认领

`CfgProvenRootsV15CoverageTests` 的 `HOLES` 与 `REJECTED_RANGE` 断言
「必须仍是 unknown」。实测：v15 的空洞 `[0x06128C,0x0612BC)` 已被
`rom-cfg-proven-roots-v16`（code + `rom-cfg-proven-roots-v16-consumed-literals-v1`）
认领，`REJECTED_RANGE [0x09C0F4,0x09C110)` 同理——**v16 的目标区正是 v15 的空洞**。
这与 D 同构：v15 的空洞在链时是 unknown，链时被 v16 合法占用。
改法与 D 一致（逐字节派生，断言「不是 v15 自己的」）。

---

## 11. 根因的定量收据：**90 / 90** 个生产者拒绝「拿最终账本重放」

新增可复现探针
`notes/evidence/reverse-proof-update-20261020-v2/probe_full_ledger_replay_20261020.py`
（只读；按 `build_manifest` 的**生产链顺序**解析出 90 个 `claims += _xxx_claims(root, rom, claims)`
调用点，逐个拿**最终账本**重放，记录抛错）。

**结果：90 个生产者，90 个全部 raise，0 个能干净重放**（总耗时 617.3 s）。

| 错误类型 | 数量 | 含义 |
|---|---:|---|
| A `… batch is already present` | 40 | 本包已晋升，重复批次 |
| B `… is / are not current unknown` | 33 | 字节已被**后继批次**认领 |
| C `… require a pre-X baseline` | 14 | 基线必须早于本包 |
| D `… promotion changed` | 1 | 窗口被后继批次切开 |
| E `duplicate … promotion batch` | 1 | 同 A |
| F `battle-controller CFG promoted code denominator …` | 1 | 分母守卫 |

**结论（比 §0 的猜测更强）**：「拿最终账本当基线重放生产者」这个写法
**在全模块 100% 不成立**——不是 9 处个案，而是**模式本身**。
每条生产链上的生产者都有自己的守卫（重复批次 / current-unknown / pre-X 基线），
只有「链时基线」才让得通。

**代价最贵的重放**（说明「重放一次生产者」不是廉价操作）：
`_boot_register_init_dependency_cfg_claims` 83.7 s、
`_cfg_proven_roots_v18_claims` 67.5 s、`_fast_audit_four_packet_claims` 66.3 s、
`_cfg_proven_roots_v17_claims` 60.3 s。
最便宜的 5 个是 0.000 s（批次守卫先触发）。

收据：`notes/evidence/reverse-proof-update-20261020-v2/full-ledger-replay-20261020.json`。
