# D0「bank 字段穷尽」：闸门真身、真实量级与三条路的代价

> 产出：2026-10-20 09:4x，基线 `codex/reverse-engineering` @ `610575ba`。
> 方法：只读侦察（grep / git log / 读文件 / 读 ledger 与 formal 报告 JSON），
> **未跑 formal / 审计器 / mGBA / unittest**，**未修改任何文件**。
> 引用一律带 `path:line`。

---

## 0. TL;DR —— 原来的二选一是错的

原问题被表述成「**字段穷尽** = 静态闭包即可（A），还是每条记录都要运行时因果证据（B → 79 次采集）」。
**实测表明这个框架本身有问题**：

1. `natural_gameplay_all_ids_proven` **不是闸门**，它甚至不是阻塞源
   —— 它是一个被哈希钉死的「**不夸大**标记」，改成 `true` 反而会让审计器 raise。
2. 真正的闸门在 `tools/audit_reverse_engineering_proof.py:648-679`，判的是
   **`coverage.status == "exhaustive"` + 记录 ID 穷尽 + 存在绑定穷尽分母的 verifier 合同**。
3. **字节层早已 100% 入账**（3,056 B / unknown 0 / 2 个消费者已绑定）⇒
   D0 是 **bank 完结判定**问题，不是字节晋升问题。
4. **D0 的真实量级不是 79 条，是 22 个 bank / 2,954 条记录 / 25,543 个 record×field 单元。**
   data-table-b 的 79 条只占 **2.7%**。
5. **B 的成本差不是「一个数量级」，是两到三个数量级**（A = 0 额外工作；B = 数周），
   而且 90% 的成本**不是 emulator 时间**。

---

## 1. 合同位置与逐字原文

### 1.1 合同四件套（79 槽 battle-message 族）

| 角色 | 路径 | 关键行 |
|---|---|---|
| bank 本体（字段数据表） | `sequel/content/data-table-b/bank.json` | `entry_count: 79`、`entry_size: 4`、`entry_format.fields[0].name = "text_ptr"`、`verification: "runtime_verified"` |
| 静态闭包 manifest | `artifacts/rom-battle-message-text-inventory-v1/manifest.json` | `scope` 块 22–33 行 |
| 静态闭包 payload | `artifacts/rom-battle-message-text-inventory-v1/battle-message-text-inventory.json` | `scope` 块 3647–3658 行 |
| exporter | `tools/export_rom_battle_message_text_inventory.py` | `SCOPE` 91–102、`LIMITATIONS` 102–108 |
| 独立 verifier | `tools/verify_rom_battle_message_text_inventory.py` | `SCOPE` 87–98、`LIMITATIONS` 99–105 |
| 覆盖审计器 | `tools/audit_rom_byte_coverage.py` | `BATTLE_MESSAGE_TEXT_SCOPE` 6437–6448 |
| 测试 | `tests/test_export_rom_battle_message_text_inventory.py` | 78 |

> ⚠️ **同名歧义**：完全同名的 `natural_gameplay_all_ids_proven` 还存在于**另一族 45 槽
> packet** `rom-training-text-script-inventory-v1`
> （`artifacts/rom-training-text-script-inventory-v1/manifest.json:28`、
> `tools/export_rom_training_text_script_inventory.py:96`、
> `tools/verify_rom_training_text_script_inventory.py:92`、
> `tools/audit_rom_byte_coverage.py:6272`）。
> **data-table-b 对应的是 79 槽 battle-message 族**
> （79 条 × 1,411 B 文本 + 1,329 B 零填充 = 2,740 B，加 316 B 指针表 = 3,056 B）。

### 1.2 `scope` 块逐字（manifest 全文 46 行）

`artifacts/rom-battle-message-text-inventory-v1/manifest.json:22-33`：

```json
  "scope": {
    "all_inter_record_bytes_accounted": true,
    "all_pointer_slots_parser_bounded": true,
    "editing_safety_proven": false,
    "fixed_79_slot_denominator_complete": true,
    "natural_gameplay_all_ids_proven": false,          ← 目标字段
    "natural_gameplay_id_zero_proven": true,
    "pointer_table_already_classified_by_bank": true,
    "runtime_index_bounds_proven": false,
    "unicode_decoding_complete": false,
    "zero_padding_safe_allocatable": false
  },
```

exporter 的源字面量（`tools/export_rom_battle_message_text_inventory.py:91-108`）：

```python
SCOPE = {
    "fixed_79_slot_denominator_complete": True,
    "all_pointer_slots_parser_bounded": True,
    "all_inter_record_bytes_accounted": True,
    "pointer_table_already_classified_by_bank": True,
    "runtime_index_bounds_proven": False,
    "natural_gameplay_all_ids_proven": False,          ← 源字面量
    "unicode_decoding_complete": False,
    "editing_safety_proven": False,
    "zero_padding_safe_allocatable": False,
}
LIMITATIONS = [
    "The 316-byte pointer table is denominator evidence only because data-table-b already owns it as fixed_table.",
    "Natural action-7 evidence binds message ID 0 only; runtime bounds and natural execution of every ID remain unproven.",
    "The 1,329 zero bytes are structural inter-record padding, not text and not proven safe allocatable space.",
    "Unicode decoding, editing safety, physical-GBA behavior, and the preceding 0x5A14F4..0x5A1580 bytes remain unclaimed.",
]
```

---

## 2. 目标字段的每一个读取点 —— 它是「不夸大标记」，不是闸门

| # | path:line | 行为 | 性质 |
|---|---|---|---|
| 1 | `tools/export_rom_battle_message_text_inventory.py:97` | 写 `False` 进 `SCOPE`；经 `:342` 进 payload、经 `_expected_manifest` 进 manifest | **写** |
| 2 | `tools/verify_rom_battle_message_text_inventory.py:93` | `SCOPE` 常量；用于 `:492`（payload）与 `:505`（`_expected_manifest`）；`:561` 重建 manifest 后与磁盘比对 | **相等性钉** |
| 3 | `tools/audit_rom_byte_coverage.py:6443` | `BATTLE_MESSAGE_TEXT_SCOPE`；用于 `:29523`（manifest scope 字典整体不等 → `raise ValueError("battle-message-text manifest contract changed")` @ `:29526`）与 `:29532`（payload scope 同比对 → `raise ValueError("battle-message-text payload denominator changed")` @ `:29548`） | **相等性钉（fail-closed）** |
| 4 | `tests/test_export_rom_battle_message_text_inventory.py:78` | `assertFalse(payload["scope"]["natural_gameplay_all_ids_proven"])` | 回归测试 |
| 5 | manifest `:27` / payload `:3652` | 记录性副本 | 记录 |
| 6 | 同名孪生族（45 槽） | 4 处 | 独立 |

**判定**：

- **claim 生成完全不读它**。`tools/audit_rom_byte_coverage.py:29434` 的
  `_battle_message_text_claims()` 造 158 条 claim（2,740 B）时只检查 scope
  **字典整体相等**（`:29523`、`:29532`），**从不对 scope 里任何布尔量做 `if` 分支**。
- **bank 级审计器根本不读它**。`grep -n "natural_gameplay" tools/audit_reverse_engineering_proof.py`
  → **零命中**。
- **`sequel/bank-proofs.json` 里没有这个字段**（只有 `coverage` / `evidence` /
  `verifiers` / `limitations` / `bank_sha256`）。该文件在 `tools/` 里**没有生成器**
  （`grep -rln "bank-proofs" tools/` 只命中 `audit_reverse_engineering_proof.py`，
  即只读），是**手工维护**的。**两者之间没有任何代码推导关系。**
- 它唯一的「闸门性」是**反向的**：把 `False` 改成 `True` 会让 `:29523`/`:29532`
  的相等性比对失败 → 审计器 raise → **fail-closed，防止静默超额声明**。

⇒ **`natural_gameplay_all_ids_proven` 是一个被哈希钉死的「不夸大」标记，
不是「不 true 就不让晋升」的闸门。**

---

## 3. 真正的闸门（`tools/audit_reverse_engineering_proof.py:648-679`）

```python
653        if coverage.get("status") != "exhaustive":
654            blockers.append(
655                f"{slug}: coverage status={coverage.get('status')!r}, expected 'exhaustive'"
656            )
657        if (
658            coverage.get("record_ids_total") != expected_record_ids
659            or coverage.get("record_ids_covered") != expected_record_ids
660        ):
661            blockers.append(f"{slug}: record coverage is not exhaustively ID-bound")
...
666        exhaustive_contract_bound = any(
667            contract["assertions"].get("/record_ids_covered") == expected_record_ids
668            and contract["assertions"].get("/field_ids_covered") == expected_field_ids
671            and contract["assertions"].get("/bank_sha256") == actual_bank_sha
672            and contract["assertions"].get("/evidence_sha256") == _evidence_hashes(proof)
674            for contract in _valid_contracts(proof)
675        )
676        if not exhaustive_contract_bound:
677            blockers.append(
678                f"{slug}: no verifier contract binds the exhaustive record, field, bank and evidence IDs"
679            )
```

**判据是三条**：① `coverage.status == "exhaustive"`
② `record_ids_covered == record_ids_total`（逐 ID）
③ 存在一个哈希绑定了 record/field/bank/evidence 四组 ID 的 verifier 合同。

---

## 4. 它现在是否真的被阻塞

### 4.1 字节层：**否**，早已 100% 入账

`sequel/rom-byte-coverage.json` 实测（读账本，非估计）：

```
region [5903744, 5906800)  = 3,056 B
overlapping segments       = 159
unknown-class segments     = 0
```

| 部分 | 字节 | claim | 来源 |
|---|---:|---|---|
| 指针表 | **316 B** | `bank-data-table-b-000`，`primary_class: "fixed_table"`，`records: 79`，range `[5906484, 5906800)` | `sequel/content/data-table-b/bank.json` 作 evidence |
| 文本 + 间隙 | **2,740 B** | 158 条（`battle_message_renderer_text` 79 + `battle_message_inter_record_zero_padding` 79） | `artifacts/rom-battle-message-text-inventory-v1/battle-message-text-inventory.json` |

消费者：`0x08098624` / `0x08099D58`
（`notes/rom-battle-message-text-inventory-20260811.md:26-29`）。

⇒ 原问题的前提「79 记录、2740+316 B、unknown 0、2 个消费者已绑定」**全部核实通过**。

### 4.2 bank 层：**是**，但阻塞源是那三条闸门

`notes/evidence/reverse-proof-update-20261020-v2/formal-parallel-report.json`
→ `bank_results["data-table-b"]`：

```json
{
  "bank": "data-table-b",
  "blockers": [
    "data-table-b: verifier path argument escapes repository: /Users/altair/github/mgba-build-c16/qt/mGBA.app/Contents/MacOS/mGBA",
    "data-table-b: unresolved limitations remain (2)",
    "data-table-b: coverage status='artifact_verified_natural_route', expected 'exhaustive'",
    "data-table-b: record coverage is not exhaustively ID-bound",
    "data-table-b: no verifier contract binds the exhaustive record, field, bank and evidence IDs"
  ],
  "classification": "runtime_verified",
  "complete": false,
  "contracted_verifier_count": 0,
  "coverage_status": "artifact_verified_natural_route",
  "declared_records_covered": 1,
  "declared_records_total": 79,
  "evidence_valid": true,
  "hash_bound_verifier_count": 1,
  "limitations_count": 2,
  "proof_bound": true
}
```

**5 个 blocker 里 3 个是 D0 问题，2 个与 D0 无关**（mGBA 绝对路径不可移植 + 2 条 limitations）。

### 4.3 D0 的真实量级：不是 data-table-b 一个包

同一份 175-blocker 报告按类别统计：

```
coverage_status_not_exhaustive      22   ← 全部 22 个有效 bank
record_coverage_not_id_bound        22
no_exhaustive_contract              22
field_coverage                      16
unresolved_limitations              29
verifier_path_escapes_repo           3
other                               61
```

```
declared_runtime_record_coverage: {records_covered: 23, records_total: 2954}
```

`complete: true` 的 bank **只有 10 个 `disproved` 候选**（不需要运行时证明）。
**22 个有效运行时 bank 全部 incomplete。**

权威报告 `docs/final-completion-report.md:29-30` 原文：

```
| 有效 bank 全记录/字段穷尽 | 0 / 22 | 22 / 22 | 未完成 |
| 有效 bank 直接证据声明记录 | 23 / 2,954 | 2,954 / 2,954 且逐 ID 可重放 | 未完成 |
```

⇒ **D0 的口径决定 22 个 bank、2,954 条记录、25,543 个 record×field 单元的完结判定；
data-table-b 的 79 条只占其中 1/37。**

---

## 5. 方案 B 的成本量化（逐条标注实测/推算）

### 5.1 可复用的采集基础设施（全部已在仓库内）

| 路径 | 用途 |
|---|---|
| `tools/mgba_input_sequence_replay.lua` | 从 checkpoint 起按输入序列重放并截图 |
| `tools/build_battle_message_runtime_probe.py` | data-table-b 专属探针，`HOOK = 0x080985E2`（`:19`），记录 message ID / 选中指针 / 目标前 16 B；支持同表 4 字节指针 A/B（`:84-87`） |
| `tools/verify_data_table_b_message0_pointer_ab.py` / `tools/export_data_table_b_message0_pointer_ab.py` | message0 像素 A/B 的 verifier / exporter |
| `tools/run_guarded.py` + `tools/project_resource_guard.py` | 资源守卫 + heavy lock |
| `tools/mgba_runtime_safety.py`、`tools/inspect_mgba_savestate.py`、`tools/patch_mgba_savestate_memory.py` | savestate 读写 / 安全补丁 |
| `tools/run_macos_mgba_replay.py` / `run_macos_mgba_single_input.py` / `run_macos_mgba_input_sequence.py` | mGBA 启动器 |
| `artifacts/runtime-checkpoints/*.ss9`（含 `scenario-50-action7-shadow-clone-confirmation.ss9`） | 已固化的自然检查点 |

**一个「一次跑一条」的硬约束**：`tools/build_battle_message_runtime_probe.py:31-54`
的 stub 每次命中都写**同一个** `SCRATCH = 0x0203FD60`（`:24`），只保留**最后一次**命中。
**现有探针每次运行只能产出一条 ID 的证据。**

### 5.2 「一次运行时因果取证」具体做什么

以 data-table-b 自己的 message0 证据为准
（`artifacts/data-table-b-message0-pointer-pixel-ab-v1/evidence.json`）：

1. 从固化 checkpoint `artifacts/runtime-checkpoints/scenario-50-action7-shadow-clone-confirmation.ss9` 起
2. `tools/mgba_input_sequence_replay.lua` 按 1 个按键（`A`, down_frame 5, up_frame 13, hold 8）重放 300 帧 → 截图 + savestate
3. 探针在 `0x080985E2` 命中，scratch 记录 message_id / selected_pointer / 前 16 B
4. 改 ROM：`0x5A2034 + id*4` 的 4 字节 `text_ptr` 换成**同表另一条**的指针（donor），重建候选 ROM（本次实际只改 1 字节 `5906484`）
5. 候选 ROM 再跑**同样**的输入序列
6. 像素 A/B：本次 928 个差异像素
7. 落盘 manifest + verifier + evidence，钉 ROM/二进制/脚本 SHA

### 5.3 [实测] 复用已有 route 的机器时间

`artifacts/data-table-b-message0-pointer-pixel-ab-v1/raw.tar` 内
`baseline/guard.json` / `candidate/guard.json`：

| 指标 | 实测值 |
|---|---:|
| baseline mGBA run 墙钟 | **6.357 s** |
| candidate mGBA run 墙钟 | **6.335 s** |
| 两次 run 之间的间隔（ROM 重建 + 指针 patch + verifier） | **67.41 s** |
| 峰值 RSS | 108.97 / 109.12 MiB |
| 帧数 / 按键数 | 300 帧 / 1 个按键 |

⇒ 纯 emulator 时间：79 × 2 × 6.35 s ≈ **16.7 分钟**（单次实测外推）
⇒ 含 ROM 重建的单条端到端 ≈ **80 s/条 ⇒ 79 条 ≈ 1.8 小时**（由实测时间戳推导）

### 5.4 [实测] 离线重放几乎免费，但不产生新覆盖

| 指标 | 实测值 | 来源 |
|---|---:|---|
| data-table-b 部分合同离线重放 | **4.14 s / 124.43 MiB / 非降级** | `notes/rom-data-table-b-partial-bank-20261001.md:75-76` |
| 四 bank 集中离线重放矩阵 | **51.67 s / 148.68 MiB** | `notes/rom-partial-bank-joint-matrix-20261001.md:35` |

但 `notes/rom-data-table-b-partial-bank-20261001.md:16` 原文：「这是历史两次采集的离线重放，
**不是新的 mGBA 运行**」，`:79` 原文：「合同迁移**不计新增自然覆盖**或 ROM 分类收益」。

### 5.5 [实测] 真正的成本大头：route 发现

| 指标 | 实测值 | 来源 |
|---|---|---|
| 单个战斗目标的 route 迭代次数 | **15+ 轮**（每轮 80–600 帧 mGBA run） | `notes/scenario-50-battle-15-runtime-20260720.md` |
| battle-effect 族（18 组，最接近 79 条的同构类比）campaign | **2026-08-01 → 2026-08-09，8 天**，产出 258 个 group artifact，最终 `production pixel A/B 保持 12/18` | Git commit 日期 + `docs/sequel-roadmap.md:2764,2778` |
| 单日多 bank 闭合峰值 | **2026-08-09 一天 14 个 bank** | `git log --since=2026-08-07 --until=2026-08-12` |
| mGBA 基础设施本身的建立成本 | enablement **1:29:23** + 证据链加固 **2:28:49** + 功能本体 **0:37:15**（合计 4:56:37） | `docs/codex-mgba-cost-time-audit-20260716.md:17-21` |

> 2026-08-09 一天 14 个 bank 之所以可能，是因为
> `notes/bank-player-visible-closure-plan-20260806.md:37-42` 规定的流程依赖
> **已存在的 scenario 41 / 50 基础快照**，每个 bank 只闭合 **1 条记录**。
> **这条产能数字不能线性外推到 79 条** —— 79 条需要 79 个**不同**的自然触发。

### 5.6 结构性放大因子：79 ↔ 79 一对一

`sequel/content/data-table-b/bank.json` 的 `notes` 字段原文：

> "The 79 IDs **correlate one-to-one with the battle/effect visual descriptor bank**."

`notes/text-and-battle-visual-consumers-20260713.md:24-25` 同样确认：
"Its 79 IDs match the visual descriptor count."；`tile-assets` 是 `0x5A320C` 处
**79 records × 0x44**。

⇒ **route 发现次数 ≈ 79，不是 1。**

### 5.7 量级区间

| 情形 | 量级 | 标注 |
|---|---|---|
| **B 的下界**（79 条全由 1–2 条 battle route 触发 + 探针改环形缓冲） | 1 条 route + 158 次 run ≈ **2–4 小时** + 探针改造（改 `build_battle_message_runtime_probe.py` 会触发 manifest `implementation` 哈希重签链） | [类比推算]，前提未验证 |
| **B 的中位**（按 battle-effect 同构 campaign 0.3–0.5 天/组、79 组类比） | **24–40 个工作日**的 mGBA route 工作 | [类比推算]，由 18 组 / 8 天外推 |
| **B 的上界**（79 条分散在不同 battle/角色/技能线，每条从 boot 重新导航） | **2–4 个月** | [类比推算] |

**必须强调**：B 的成本 **90% 不是 emulator 时间（16.7 min），而是 route 发现**。
只看 emulator 时间会把 B 与 A 的差距看成「分钟级 vs 零」，**严重低估**。

---

## 6. 中间方案：仓库里已有 5 类先例

### 6.1 ⭐ 正式 catalog 里已有 17 种 denomination

`sequel/bank-proofs.json` 的 `coverage.status` 已存在 17 种取值，data-table-b 用的是其中之一：

```
data-table-b     artifact_verified_natural_route   1/79
cutscene-scripts artifact_verified_natural_route   1/8
palettes         artifact_verified_natural_route   1/15
tile-assets      artifact_verified_natural_route   1/79
map-events       artifact_verified_natural_recovery 1/256
positions        runtime_observation_not_causal_ab  1/1728
```

脚本实测直方图：`artifact_verified_natural_route` 4 个、`disproved` 10 个、其余 15 种各 1–2 个。
**没有任何一个 bank 的 status 是 `"exhaustive"`。**
⇒ **「静态闭包 + 代表性运行时抽样 + 显式未覆盖分母」就是仓库既有的正式口径。**

### 6.2 ⭐ record×field 单元矩阵（typed partial contract）

- `notes/rom-data-table-b-partial-bank-20261001.md` +
  `tools/verify_data_table_b_partial_bank.py` +
  `tools/data/data-table-b-partial-bank-contract-v1.json`
- 原文（`:11-13`）："verified=true、cells_total=79、cells_covered 只有 record_id="0" /
  field_id="text_ptr"，其余 **78 个单元显式列入 cells_uncovered**；
  changed_pixel_count=928、**exhaustive=false**"
- 四 bank 联合矩阵 `notes/rom-partial-bank-joint-matrix-20261001.md`：
  "候选分母是 193 records / 811 record×field 单元，实际覆盖 4 个，未覆盖 807 个"
- ⚠️ **状态：候选，未入正式 catalog**。`notes/rom-data-table-b-partial-bank-20261001.md:66`
  原文："proposal.json 仅作候选，**没有写入 sequel/bank-proofs.json**"
- 政策授权路径：`docs/reverse-engineering-proof-policy.md:118-130`（"部分 bank 证据的结构化迁移"）
  —— "接入时同步 live catalog、proof 引用与 formal，**不能用离线提案宣称正式 blocker 已减少**"

### 6.3 ⭐ 分数式自然覆盖（「N/79」同形）

`artifacts/battle-effect-group18-natural-pixel-ab-v1/evidence.json` scope：

```json
{"all_18_effect_groups_runtime_verified": false, "execution_mode": "natural-delayed-object",
 "natural_gameplay_route": true, "production_natural_pixel_ab": "9/18", ...}
```

`artifacts/battle-effect-group03-natural-pixel-ab-v1/evidence.json` 同形 `"6/18"`。
⇒ **「N/79 + 显式 all=false」是仓库现成的表达形状。**

### 6.4 仓库级普遍约定：107 个已提交 artifact 带 false 自然标记

脚本实测：107 个 `artifacts/*/manifest.json` 的 `scope` 里含
`natural_* / runtime_* / exhaustive_* = false`，**同时都已入账**。
例：`rom-fixed-consumer-text-inventory-v1`（`natural_gameplay_index_coverage_complete: false`）、
`rom-selector-text-bindings-v1`（`natural_gameplay_all_records_proven: false`）、
`rom-value-range-text-inventory-v1`（`natural_gameplay_all_ranges_proven: false`）。

⇒ **「静态闭包已提交、运行时标记留 false」是全仓库既定做法**，不是 data-table-b 的特例。

### 6.5 ⭐ OpenSpec 已把「单条代表性 A/B」写成正式计划

`openspec/changes/upgrade-remaining-runtime-banks/tasks.md:22`（批次 A 第 3.3 项）：

> "从同一 pre-action 快照成对运行 `data-table-b` 基线与**单一文本指针对照**，证明 ID、
> `0x085A2034 + id*4`、NUL 文本消费者及可见消息"

`:23`："根据 3.3 的证据更新 `data-table-b` **最终等级**、bank 元数据、紧凑证据……
**不满足三重门禁时保持 `code_verified`**"

⇒ **「一条代表性记录 + 显式降级」已被 change 提案认可为可接受的完成形态。**

### 6.6 政策原文背书「verified ≠ exhaustive」

`docs/reverse-engineering-proof-policy.md:123-124`：

> "分母来自完整冻结 bank schema，**未覆盖单元保留**，控制物化、自然入口和实体硬件分别声明。
> **verified=true 仅表示合同声明的证据通过，不等于 exhaustive=true。**"

---

## 7. 三条路的代价与收益

| | 代价 | 收益 | 风险 |
|---|---|---|---|
| **A（静态闭包即算穷尽）** | 改 `sequel/bank-proofs.json` 的 `evidence_policy.coverage_counting` + 审计器判定（`audit_reverse_engineering_proof.py:648-679`）→ 更新 `sequel/reverse-engineering-proof.json` 的 `bank_proofs.sha256`（现 `f52524fb…`）+ 审计器 SHA → **重跑 1 次 formal（[实测] 1,464.7 s ≈ 24.4 min）** | 22 个 bank 一次性从 0/22 变成可判定；data-table-b 立刻从 5 blockers 降到 2 | **这是对「100%」门槛的实质放宽**，需明确授权；与 `docs/final-completion-report.md` 的 "0/22" 表述冲突，须同步改写 |
| **B（79 条逐条运行时因果证据）** | **24–40 工作日**（[类比推算]）；纯 emulator 仅 16.7 min（[实测]），route 发现占 90% | 唯一真正满足 policy 第 5 条原文；可解锁 22 bank × 2,954 record × 25,543 单元 | 成本随 bank 数**非线性**上升（22 bank 全做 ≈ 数百日）；RNG / 命中 / 替身导致 route 不可复现（`notes/scenario-50-battle-15-runtime-20260720.md:49-52,96-100`） |
| **中间方案（仓库已有多重先例）** | 低。`bank-proofs.json` 17 种 denomination 已在用；typed partial contract 工具链已存在且**离线重放 4.14 s**；「N/79」表达已在用；OpenSpec 计划已认可 | 把「运行时自然可达」与「字段/记录穷尽」**解耦**：静态闭包已 100% 入账（3,056 B，unknown 0，2 消费者绑定），运行时覆盖按 `records_covered` 逐条累加（当前 1/79） | 需要把 `coverage.status` 语义从「必须 exhaustive」改为「允许带显式未覆盖分母的部分态」——**仍要改审计器 + 重跑 formal**，但**不改 policy 第 5 条原文**，只把「exhaustive」降为完成门之一而非唯一门 |

---

## 8. 建议

**推荐走中间方案，把 D0 拆成两个独立判据，而不是在 A / B 之间二选一。**

1. **A 与 B 回答的不是同一个问题。** 仓库已把「静态闭包穷尽」和「运行时自然可达」
   拆成**两个不同的 scope 字段**（`fixed_79_slot_denominator_complete` vs
   `natural_gameplay_all_ids_proven`），且 `docs/reverse-engineering-proof-policy.md:123`
   明文要求「控制物化、自然入口和实体硬件**分别声明**」。
   把 D0 强行合成一个布尔量，本身就违反仓库自己的分声明原则。
2. **B 的成本不是「一个数量级」，是两到三个数量级**（0 vs 数周），
   且 79 条 ↔ 79 个特效 descriptor 一对一 ⇒ route 几乎无法复用。
3. **D0 的真实杠杆在 22 个 bank，不在 data-table-b。**
   先解口径、再批量执行，比先做 79 条采集再发现还有 21 个 bank 更划算。
4. **最小落法**：
   - 保留 `natural_gameplay_all_ids_proven=false` 不动（它现在是 fail-closed 的
     「不夸大」钉，改它会触发 `audit_rom_byte_coverage.py:29523/29532` 的 raise）；
   - 在 `sequel/bank-proofs.json` 增加**第三维**（`coverage.status` 允许
     `partial_explicit_denominator` + `records_uncovered` 显式列表），
     复用已写好的 `tools/verify_data_table_b_partial_bank.py` /
     `tools/data/data-table-b-partial-bank-contract-v1.json`
     （`notes/rom-data-table-b-partial-bank-20261001.md:11-13` 已产出 1/79 + 78 个 `cells_uncovered`）；
   - 改 `tools/audit_reverse_engineering_proof.py:648-679` 接受「显式未覆盖分母」为合法态，
     **保留** policy 第 5 条对最终 100% 声明的要求（partial 态可入账、
     但 `claim_status` 仍 `incomplete`）；
   - 同步 `sequel/reverse-engineering-proof.json` 的 `bank_proofs.sha256`（`f52524fb…`）
     + 审计器 SHA → 重跑 1 次 formal（[实测] ~24.4 min）。
   - `notes/rom-data-table-b-partial-bank-20261001.md:65-66` 原文已预演过这个接入动作：
     "真实 auditor 的 CLI contract_ok=true，但 partial bank complete=false，保留 4 个局部
     blockers。proposal.json 仅作候选" —— **脚本和合同都已就绪，只差 policy 决策**。
5. **如果坚持 B**，先做**一个抽样可行性探针**再决定：用环形缓冲改造后的探针跑 1 条完整
   battle，看**一次 run 最多能自然产出多少个不同 message ID**（记作 `k`）。
   这个数字直接把 B 从「79 条 route」降到「约 79/k 条 route」，
   是**唯一能把 B 的成本从数周压到可裁决区间的信息**，成本约 1 个工作日。

---

## 9. 未知 / 风险

1. **未实测**：B 的 route 发现成本（24–40 日 / 2–4 月）是**类比推算**，
   基于 battle-effect 18 组的 8 天 campaign。仓库内**没有**「79 条 message ID 逐条采集」
   的任何历史记录可作直接实测锚点。
2. **未验证**：`k` = 一次 battle run 最多能自然触发多少个不同 message ID ——
   决定 B 成本的关键未知量。
3. **`records_covered` 计数口径未定义**：`sequel/bank-proofs.json` 里 `records_covered`
   是数字（1），而 `tools/audit_reverse_engineering_proof.py:658` 比较的是**列表**
   `record_ids_covered`。两套口径的桥接在 `_valid_contracts` / proof spec 里，
   **未逐行读完**（该文件共 ~1,290 行，读了 590–719）。若要改审计器，
   需先读 `_check_bank` 全函数。
4. **同名字段歧义**：`natural_gameplay_all_ids_proven` 同时存在于 79 槽 battle-message 族
   与 45 槽 training-text-script 族。改 policy 时两族会同时受影响。
5. **未跑任何长跑命令**：所有数字来自读取收据、ledger、Git 提交日期和 notes，未复现。
