# 活账本 SHA 身份在晋升后失效 —— 2026-10-20 实测与施工面

本文件记录 2026-10-20 第四轮（Tier-2 例外三包晋升）**实测发现**的一类系统性回归，
以及由此修正的裁决③④施工面。它是 `notes/four-decisions-20261020.md` 的补充与更正。

---

## 1. 新发现：本轮晋升打红了 4 个导出器测试模块（23 项）

三包晋升（`rom-renderer-records-delta-v1` / `rom-display-text-delta-v1` /
`rom-animation-descriptor-pool-v2`）把活账本从 `24cf30aa…` 换成 `d34672a8…`。
这一换使**以整账本摘要做身份**的导出器全部失效。

实测（`/usr/local/bin/python3 -m unittest tests.<module>`，2026-10-20 13:2x）：

| 测试模块 | 结果 | 根因 |
| --- | --- | --- |
| `tests.test_export_rom_sprite_loader_tail` | 9 项：1 failure + 5 errors | `sprite loader coverage identity changed` |
| `tests.test_export_rom_chapter_selector_code_slice` | 9 项：1 failure + 5 errors | 同类 |
| `tests.test_export_rom_profile_selector_code_slices` | 6 项：5 errors | 同类 |
| `tests.test_export_rom_battle_status_bar_caller_slice` | 9 项：1 failure + 5 errors | 同类 |
| `tests.test_export_rom_psg_frequency_lookup` | 15 项：OK | 它钉的是重建基线，不读活账本摘要做闸门 |

**这 4 个模块不在 93 套件内，也不在整模块 `tests.test_audit_rom_byte_coverage` 内**，
所以两轮长跑都看不到它们 ⇒ 这是本轮晋升引入的**未覆盖回归**，不是历史遗留。

**分母口径**：这是「测试通过数」问题，**不是**逆向完成量问题；完成度仍是
98.68507385253906%（unknown 82,728 / classified 6,208,728 / claims 17,028 / segments 18,882）。

---

## 2. 根因：导出器与验证器的 coverage 身份策略不对称

仓库里同一族包的**验证器**早已实现 `baseline` / `post` 双模式，
**导出器**却仍硬钉「整账本摘要相等」。晋升 ⇒ 导出器红、验证器绿。

以 `tools/verify_rom_sprite_loader_tail.py` 为例（实测行号）：

```python
digest = _sha(raw)
if digest == COVERAGE_SHA256:
    mode = "baseline"
else:
    mode = "post"          # post 模式改验「本包自己的 claim 精确持有该段」
```

`tools/export_rom_sprite_loader_tail.py` 同名函数只有 baseline 分支：

```python
if _sha(raw) != COVERAGE_SHA256:
    raise ValueError("sprite loader coverage identity changed")
```

四份验证器（`verify_rom_sprite_loader_tail` / `verify_rom_chapter_selector_code_slice` /
`verify_rom_profile_selector_code_slices` / `verify_rom_battle_status_bar_caller_slice`）
的 `BASELINE_SUMMARY` 完全相同（classified 6,142,176 / unknown 149,280 /
claim 15,940 / segment 17,344），且 `COVERAGE_SHA256` 同为 `24cf30aa…`。

**可用范式已经在仓库里**：`baseline/post` 双模式 + post 模式验「本包 claim 精确持有」。
四个导出器只需把对应验证器的 `_validate_coverage` **原样移植**（外加补 `BASELINE_SUMMARY`），
不需要发明新机制。

### 移植可行性（AST 实测）
逐对比对四对 `export_*` / `verify_*` 的 `_validate_coverage` 源码：
差异 79–91 行，且差异**全部**是「post 模式缺失」这一件事
（`diff` 逐块核对：digest 闸门、summary 校验、claim 精确持有检查、段 owner 期望值）。
**导出器版本 = 验证器版本减去 post 模式**，无其它语义差异 ⇒ 机械移植。

移植对 payload 字节**无影响**：
`_validate_coverage` 的返回值里只有 `path` / `sha256` / `current_primary_state` 被 payload 取用，
新增的 `mode` 键不进入 payload ⇒ payload 内容不变（但 payload 内嵌 `implementation.exporter.sha256`，
改导出器后 **payload 与 manifest 摘要都会变**，见 §3）。

---

## 3. 修正裁决③④的施工面（与原计划的三处偏差）

原计划写「同步 spec 的 3 个值、**不需要重跑账本**」。**实测后不成立**，更正如下。

### 3.1 spec 要同步的不是 3 个值，而是按改动面逐项重算

以 sprite-loader-tail 为例，改动会同时命中四处：

| 位置 | 为什么会变 |
| --- | --- |
| `sequel/reverse-engineering-proof.json` → `verifiers[].script_sha256`（`tools/verify_rom_sprite_loader_tail.py`） | 验证器文件字节变了（裁决④ 加固 purelib） |
| 同上 → `verifiers[].script_sha256`（`tools/audit_rom_byte_coverage.py`） | 审计器要改 pin 常量 |
| 同上 → `evidence[].sha256`（`artifacts/rom-sprite-loader-tail-v1/manifest.json`） | manifest 内嵌 `implementation.exporter/verifier.sha256` |
| 同上 → `evidence[].sha256`（`artifacts/rom-sprite-loader-tail-v1/rom-sprite-loader-tail.json`） | payload 内嵌 `implementation.exporter/verifier.sha256` |

外加 `sequel/rom-byte-coverage.json` 自身也是 spec 的 evidence（`path` 在 spec 第 29 行），
账本一变，它的摘要也要同步 ⇒ 实际是 **5 个**（sprite-loader-tail 一包），
四包全改就是 **4×5 + 审计器自身** 的规模。**不能用「3 个值」的旧说法。**

### 3.2 账本必须重建

`tools/audit_rom_byte_coverage.py` 把每条 claim 的证据身份写进账本：
`evidence_sha256` / `promotion_manifest_sha256` / `independent_verifier_sha256` /
`independent_verifier_report_sha256`。
实测活账本里 `rom-sprite-loader-tail-v1` 那条 claim 就带着这四个值。
⇒ 重新落地 artifact ⇒ 这四个值变 ⇒ **账本字节变 ⇒ 必须重建** ⇒ 账本摘要变 ⇒ spec 同步。

### 3.3 重落地必须先过「已有 artifact 自检」这一关

`tools/export_rom_sprite_loader_tail.py` 的 `_validate_output` 在目标目录已存在时，
会先调 `verify_artifact` 自检，失败即拒绝覆盖。
改完验证器后旧 artifact 的 `implementation.verifier.sha256` 已陈旧 ⇒ 自检必失败 ⇒
**导出器会拒绝覆盖**。落地顺序必须让「文件已改、artifact 未重落地」这个中间态可被绕过
（例如先移走 artifact 目录再落地），否则会卡死。

### 3.4 psg 的改动面比 sprite-loader-tail 小

`tools/verify_rom_psg_frequency_lookup.py` 的 payload **不**内嵌 `implementation`
（payload 顶层键：consumer / coverage_baseline / limitations / literal_bindings / lookup /
producer_denominator / promotion / provenance / rom / schema / scope / table），
`implementation` 只在 manifest 里 ⇒ 改 psg 验证器/导出器后 **payload 摘要不变、只有 manifest 变**。
且 `tools/verify_rom_psg_frequency_lookup_bundle.py` 本身就是「不与活账本耦合」的旁路验证器
⇒ psg 走链时语义身份有现成先例可循。

---

## 4. purelib 加固（裁决④）的实测定位

- `tools/audit_reverse_engineering_proof.py:470` 用 `sys.executable` 顶替 spec 里的 `"python3"`
  ⇒ 解释器换谁，子验证器就换谁。
- spec 里**确实**有这一条（`-I -S`）：
  `python3 -I -S tools/verify_rom_sprite_loader_tail.py --root . --artifact-dir artifacts/rom-sprite-loader-tail-v1`
  （此前误以为 spec 没有该条目，实为查错了层级——verifiers 在 `gates.rom_byte_coverage.verifiers` 下，不在顶层）。
- `tools/verify_rom_sprite_loader_tail.py:194-196` 只补**当前解释器**的 purelib：
  `sysconfig.get_path("purelib")`。实测：
  - 系统解释器 `/usr/local/bin/python3` → purelib `/usr/local/lib/python3.14/site-packages` → **有 PIL** ✓
  - 逆向树 `.venv/bin/python3` → purelib `.venv/lib/python3.14/site-packages` → **只有 pip，没有 PIL** ✗
    （`tools/verify_sprite_definition_animations.py:14` 需要 `from PIL import Image, ImageDraw`）
  ⇒ 用 venv 解释器跑 formal 时该验证器失败，这就是第 176 条 blocker 的真因。
- 用户裁决：**补所有候选 purelib**（当前解释器 + 系统 + venv）。
  实现约束：PIL 是 C 扩展，**必须只补与当前解释器同 minor 版本**的 site-packages，
  否则会引入 ABI 不兼容的二进制扩展。

---

## 5. 施工顺序（合并为一次账本重建 + 一次 formal）

把裁决③④与 §1 的 4 个红模块合并，**只重建一次账本、只跑一次 formal**：

1. 四个导出器：补 `BASELINE_SUMMARY` + 移植验证器的 `_validate_coverage`（post 模式）。
2. `tools/verify_rom_sprite_loader_tail.py` + `tools/export_rom_sprite_loader_tail.py`：
   purelib 候选补全（裁决④）。
3. psg 验证器 + 导出器：整账本摘要 → 链时语义身份（裁决③）：
   读活账本 → 剔掉本包自己的 claims → 断言 226 B 仍 unknown（或已被本包精确持有）
   且不与别的 primary claim 重叠 → 活账本摘要只作 provenance。
4. 重新落地 5 个 artifact（4 个 consumer-code-slice 包 + psg）。
5. 更新 `tools/audit_rom_byte_coverage.py` 的全部相关 pin 常量。
6. 受管重建账本（`tools/run_guarded.py`，wall 9000 / idle 7200）。
7. 同步 spec（逐项重算，不复用旧计数）+ 刷新 policy 文档计数。
8. 一次 formal（系统解释器，不把 `.venv` 前置到 PATH）。
9. 跑四个导出器测试模块 + 整模块 + 93 套件，回填收据。

裁决②（D0 方案 B）不碰账本与 spec，可与第 6/8 步的重活并行。

---

## 6. 待更正的上游说法

`notes/four-decisions-20261020.md` 里「裁决④…**不需要重跑账本**（claim 不变）」「同步 spec 的 3 个值」
两句**与实测不符**，须按本文件 §3 更正为：账本必须重建；spec 需按改动面逐项重算
（sprite-loader-tail 一包即 5 个值）。
