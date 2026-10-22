<task_output status="succeeded">
<task_output_cursor next_offset="65536" truncated="true" />
我先确认目标仓库与分支状态，然后并行展开几路侦察。
仓库与分支确认。现在并行读取 M1 动画池包与两个 renderer 包的现场。
受管 run 目录 `renderer-records-delta` 仍在。现在读 M1 payload 结构与两个 renderer 包的 `final/` 收据。
M1 的 `promotion.claim_count=1`（不是 29/85 那类），已记下。现在读两个受管 run 的 `.experiment.json` 与审计器主结构。
审计器有 38,580 行。我需要精确定位既有的两个参照函数和它们的常量块。
找到锚点了。现在读核心参照实现：`_project_dependency_packet_claims` 与其 spec 常量区。
核心机制已清楚。现在读 `_fixed_renderer_script_record_claims` 与 `class_for`/`kind_for` 用法范例。
现在读 `build_manifest` 的累积段与既有 `FIXED_ANIMATION_DESCRIPTOR_GROUPS` 包（可能与 M1 重叠）。
关键发现：既有 `rom-fixed-animation-descriptor-groups-v1` 已占 1,136 B。现在对比 M1 的实际区间并读既有 animation descriptor 包的实现。
M1 区间 = `[4555564, 4556204]`（0x458564–0x45879C），与既有 descriptor-groups 包（0x12D574–0x12E164）不同区。现在读活账本与两个 renderer 包的 final 收据。
账本与包结构清楚了。现在做 SHA 一致性实测（implementation_inputs vs 仓库实时文件）+ 查 verifier / 合同 / promote 工具。
全部 `implementation_inputs` 与仓库实时文件 **MATCH**。现在核对 M1 的实现 SHA、合同 JSON、以及 promote 工具的接口。
实现 SHA 全部 MATCH。现在读 `promote_run` 的确切行为与三个 verifier 的入口签名。
三个 verifier 都有 `verify_artifact(root, artifact)`。现在读它们的返回报告字段与两个 renderer payload 的 promotion 结构。
三个 payload 的 `promotion.claims` 结构与审计器期望完全一致。现在实测三个 verifier 是否还能通过。
M1 verifier 通过（`verified: true`，0.17s）。现在实测两个 renderer 包的 verifier。
三个 verifier 全部通过。现在做核心的账本重叠实测（纯读，不跑审计器）。
三包区间全部落在当前 unknown，无重叠。现在查 `rom-low-script-delta-v1`（12 B）并读 `atomize_claims` 以做账本投影。
`rom-low-script-delta-v1` 是**孤儿 artifact**（账本引用 0）。现在实测其区间归属，并读 proof spec。
**实测确认**：`rom-low-script-delta-v1` 的 2 个 claim 完全落在新包 `renderer-records-delta-42b5/42c2` 内，但它是账本孤儿。现在做账本精确投影。
Proof 的 coverage verifier 钉了 `script_sha256: 33932f14…`。现在做账本投影复算 + 核对审计器实时 SHA。
审计器 SHA 与 proof 钉值 **MATCH**（`1fba1112…`）。`atomize_claims` 是 O(n²) 太慢，我改用等价的 O(n log n) 算法复算。
投影复算精确复现基线（18675/86089/6205367），可信。现在核对 summary 键、proof 的 evidence/limitations 格式。
锁定了同步点。现在读 policy 文档、liveness 测试、以及 `_sync_policy_counts` 的 apply 脚本。
现在读关键的 `apply.py` 同步脚本 —— 它决定 proof 更新怎么落地。
`apply.py` 是 proof 更新的完整模板。现在读 `complete_run`/`_inventory`（promote 会改什么）并核对 proof 现有 evidence。
三个包在 proof 中 evidence/verifier **全缺**，需全部新增。现在读 promote 的 CLI 形态并实测 inventory 是否会变。
inventory 重算**逐字节相同** —— promote 只会改 `.experiment.json`。现在定位 docs/notes 待改行并算新百分比。
工作树有未提交修改，包括 `tools/audit_rom_byte_coverage.py` 本身 —— 必须先确认是否已有并行接线工作。
关键上下文：工作树的改动是 PSG pin 刷新（与本任务无关），且有一条 formal proof 在飞。检查 heavy lock 状态。
在飞的 standalone auditor 已持有 heavy lock。最后核实账本里「已投影包 claim」的完整字段集。
最后两项核查：proof 审计器如何比对 contract.assertions，以及 auditor SHA 的所有引用点。
发现一个**关键阻塞**：两个 renderer verifier 的报告没有 `schema` 字段，而 proof 全部 98 条 verifier 合同都要求 `/schema`。核实既有同类包的先例。
既有先例确认：同类 3 个包中只有 1 个进了 proof `verifiers`。现在查证据清单哈希绑定（evidence 变更会连带影响哪些断言）。
侦察完成，证据齐备。以下是施工单。

---

# 甲线三包接入施工单（只读侦察产出）

**仓库** `/Users/altair/github/gba-naruto-reverse`　**分支** `codex/reverse-engineering`
**基线** 工作树 HEAD `b83061e3` + 未提交改动（见 §6 风险 d）

---

## 1. M1 动画池包身份核实

### 1.1 manifest（`artifacts/rom-animation-descriptor-pool-v2/manifest.json`）

| 字段 | 值 |
|---|---|
| `schema` | `git-artifact-promotion-v1` |
| `artifact_schema` | `rom-animation-descriptor-pool-v2` |
| `artifact_status` | `accepted` |
| `files["rom-animation-descriptor-pool-v2.json"].size` | `35254` |
| `files["rom-animation-descriptor-pool-v2.json"].sha256` | `7f9c4a36c0f29f3abe0351a7ba5af96c5f27a8d396d81fbe28ed34df574ebf7f` |
| manifest 自身 size / sha256 | `1195` / `81a4e698d523a0e78c379a2c0dbb8bed48cdeec726b11fb096cf8b7a70befffa` |
| `implementation.exporter_sha256` | `537d2af7c8ff457d7bddda2a1430e6c85f66a889dbdd7a7f2d34cc3f459e01e3` → `tools/export_rom_animation_descriptor_pool_v2.py`（33 319 B）✅ live MATCH |
| `implementation.verifier_sha256` | `53d7a82acf5a8a55ceb311ce51da392a29c5ec6dfcd18d1c2a21cd2a8745fea7` → `tools/verify_rom_animation_descriptor_pool_v2.py`（29 501 B）✅ live MATCH |
| `implementation.test_sha256` | `c0d8486e3474e17ad90f3b301303f0cc33a9a30a2641f5d949d6b614642abd2e` → `tests/test_export_rom_animation_descriptor_pool_v2.py` ✅ live MATCH |
| `summary` | `base_pair_count 7` / `descriptor_count 8` / `descriptor_entry_count 24` / `sequence_count 8` / `promotion_bytes 640` |

### 1.2 claim 结构（payload `promotion`）

```
promotion.claim_count = 1          ← 不是 29/85，用户表格里的 "?" 由此确定
promotion.promotion_bytes = 640    ← 用户暂记 640 B 正确
promotion.promotion_batch = "rom-animation-descriptor-pool-v2"
promotion.promoted_from_primary_class = "unknown"
claims[0]:
  id            = "animation-descriptor-pool-45832c"
  range         = [4555564, 4556204]   (0x458564..0x45879C)
  primary_class = "fixed_consumer_animation_descriptor_group_bytes"
  claim_kind    = "fixed_consumer_animation_descriptor_group_bytes"
  bytes_sha256  = "9be0375fab3cd7f25c99d6cdcfedfd3727d5d787b56532ac72894c74f5ec511c"
```

**用户表格里 M1 的 `primary_class` / `claim_kind` 问号，答案是 `fixed_consumer_animation_descriptor_group_bytes`（两者同名）。**

> ⚠️ **class 撞名（必读）**：该 `primary_class` 与账本里**已存在**的 `rom-fixed-animation-descriptor-groups-v1`（claim `fixed-animation-descriptor-groups-12d574`，range `[1234292,1235428]` = 0x12D574..0x12E164，1 136 B）**完全同名**。账本按 class 汇总时两族合并：1 136 + 640 = 1 776 B。
> 该值**不可更改**：M1 verifier 走 `payload_raw != _canonical(rebuilt)` 逐字节比对（`tools/verify_rom_animation_descriptor_pool_v2.py:653`），改 payload 就必须重跑 exporter 并重签 manifest。**建议：接受撞名**（语义上两族确实都是「固定消费者动画描述符组字节」），靠 `promotion_batch` 区分。

### 1.3 payload 内部结构（`byte_attribution` / `scope` / `limitations`）

- `byte_attribution`: `descriptor_bytes 496` + `padding_bytes 16` + `pointer_slot_bytes 64` + `sequence_bytes 64` = `total_bytes 640`，`unattributed_bytes 0`
- `pointer_slots`: `slot_count 16` / `table_count 14`（7 张 descriptor_table + 7 张 group_table）
- `descriptors`: `entry_count 24` / `entry_stride 20` / `terminator_value 65535` / `terminator_width 2` / `terminator_position "head"`
- `sequences`: `sequence_count 8` / `item_size 8` / `terminator_value 65535` / `terminator_width 4`
- `excluded_regions[0]`: `[4556204, 4556692)` 488 B，`family_attributed: false`，原因 = 异族尾巴（ASCII `'LV'` + 数字串）
- `scope` 全 false：`all_callers_share_this_input` / `callback_domain_closed` / `caller_denominator_closed` / `descriptor_editing_safety` / `flags_domain_closed` / `heterogeneous_tail_family_closed` / `index_domain_closed` / `natural_runtime_reachability` / `opaque_renderer_side_effects`
- `scope_notes`: 9 条逐项说明（callback 域、caller 分母 48→7、flags 域、异族尾巴、runtime 可达性等）
- `consumer_contract.caller_site_denominator`: `base_pair_pools 48` / `attributed_pools 2` / `unattributed_pools 46` / `closed false`

**payload 里没有 `limitations` 键**（该语义在 `scope` + `scope_notes` + `consumer_contract` 三处）。

### 1.4 verifier / 冻结合同

- **有**独立 verifier：`tools/verify_rom_animation_descriptor_pool_v2.py`，入口 `verify_artifact(root, artifact, expected_artifact=None)`（第 630 行），返回 `{"schema": "rom-animation-descriptor-pool-v2-verification-v1", "verified": True, "errors": [], "promotion_bytes": 640, "descriptor_count": 8, "descriptor_entry_count": 24, "base_pair_count": 7}`
- **实测**：`/usr/local/bin/python3 tools/verify_rom_animation_descriptor_pool_v2.py --root . --artifact artifacts/rom-animation-descriptor-pool-v2` → `verified: true`，**0.17 s**
- **无** `tools/data/` 冻结合同 JSON：M1 的「合同」就是 payload 本身 + ROM 独立重建比对（`tools/data/` 14 个文件里只有两个 renderer 合同）
- **无** `tools/data/rom-animation-descriptor-pool-v2-contract-v1.json`

### 1.5 活账本状态（只读实测，未跑审计器）

- range `[4555564,4556204]` **全部落在当前 unknown**，与既有 16 913 个 primary claim **零重叠**
- 与 `rom-fixed-animation-descriptor-groups-v1`（0x12D574..0x12E164）**不同区**，无冲突
- `grep -c animation_descriptor_pool tools/audit_rom_byte_coverage.py` = **0**（确认未接审计器）

---

## 2. 两个 renderer 包的 promote 前置条件

### 2.1 受管 run 存活状况

| | 命令脚本包 | 显示文本包 |
|---|---|---|
| 受管 run | `build/experiments/active/renderer-records-delta/combined-tier1-20261001-v1/` | `build/experiments/active/display-text-delta/tier1-20261001-v1/` |
| `status` | `completed` | `completed` |
| `promoted_to` | **无** | **无** |
| `task` / `run_id` | `renderer-records-delta` / `combined-tier1-20261001-v1` | `display-text-delta` / `tier1-20261001-v1` |
| `inventory` | 27 文件 / 86 879 B / sha `0bc172e6…` | 38 文件 / 334 850 B / sha `1eda6525…` |
| `final/` 成员 | `manifest.json` + `rom-renderer-records-delta.json` | `manifest.json` + `rom-display-text-delta.json` |

✅ **两个受管 run 都还在**，`build/` 本轮未被清理。

### 2.2 promote 的确切命令

`tools/experiment_workspace.py` 的 CLI（`main()` 第 484–531 行）：`promote` 子命令收 `--task` / `--run-id` / `--artifact-name` 三个必填参数。

```bash
/usr/local/bin/python3 tools/experiment_workspace.py promote \
    --root . \
    --task renderer-records-delta \
    --run-id combined-tier1-20261001-v1 \
    --artifact-name rom-renderer-records-delta-v1

/usr/local/bin/python3 tools/experiment_workspace.py promote \
    --root . \
    --task display-text-delta \
    --run-id tier1-20261001-v1 \
    --artifact-name rom-display-text-delta-v1
```

- 输出：`{"artifact_path":"artifacts/rom-renderer-records-delta-v1"}` / `{"artifact_path":"artifacts/rom-display-text-delta-v1"}`
- **`--artifact-name` 必须等于 verifier 里写死的 `ARTIFACT` 常量**：`tools/verify_rom_renderer_records_delta.py:29` = `Path('artifacts/rom-renderer-records-delta-v1')`、`tools/verify_rom_display_text_delta.py:26` = `Path('artifacts/rom-display-text-delta-v1')`。名字写错 → `intended_manifest()` 比对失败 → `manifest contract changed`。
- `artifacts/<name>/` 必须**不存在**（`promote_run` 第 336–337 行抛 `FileExistsError`）。当前两个目录都不存在 ✅
- 预算：`max_files` / `max_bytes` 默认值远超 2 文件 / ~36 KB，无需 `large_artifact_justification`。

### 2.3 notes/evidence 副本能否走同一条路？

**不能。** `_run_path()`（第 55–61 行）硬编码为 `root/build/experiments/active/<task>/<run_id>`，`notes/evidence/**` 下的目录对 promote 不可达。

**但两份副本与受管 run 逐字节相同**（实测比对）：

| 文件 | build/ 与 notes/evidence/ 是否相同 |
|---|---|
| `final/manifest.json` (renderer) | ✅ 相同（`7191a579d0995fef…`） |
| `final/rom-renderer-records-delta.json` | ✅ 相同（`12f9688e7ac67e83…`） |
| `final/manifest.json` (display) | ✅ 相同（`c63319575c27969f…`） |
| `final/rom-display-text-delta.json` | ✅ 相同（`1fb3541e0d97fe38…`） |

⇒ 从 `build/` promote 出的 `artifacts/` 内容与历史收据副本完全一致；**即使 `build/` 日后被清，只要 `notes/evidence/**/final/` 还在，仍必须重建受管 run**（`init` → 重放 exporter → 重新冻结 `final/`），不能直接拷贝 notes 副本 —— 因为 promote 只认 `build/experiments/active/` 下的 run 目录。

### 2.4 promote 会改写什么

`promote_run`（第 307–365 行）：

1. `_validate_promotion_manifest(final)` —— 硬校验：manifest 是 canonical JSON、`schema == "git-artifact-promotion-v1"`、`artifact_status == "accepted"`、`verifier.exit_code == 0`、`files` 清单与 `final/` 实际成员**一一对应**且 sha256/size 匹配、无 symlink。两个 `final/manifest.json` 均满足。
2. `shutil.copytree(final, temporary)` → `os.replace(temporary, artifacts/<name>)`（原子）
3. `complete_run(root, task, run_id)` → **重算并重写 `.inventory.json`**，再重写 `.experiment.json`（`status` 保持 `completed`，`completed_at` 保持原值）
4. `.experiment.json` **新增两个键**：`promoted_to`（= `artifacts/<name>`）、`promoted_at`（ISO 时间戳）
5. 失败回滚：`shutil.rmtree(target)` + `_restore_file()` 还原 `.experiment.json` / `.inventory.json` 的原始字节

**实测 `.inventory.json` 会不会变**：按 `_inventory()` 逻辑离线重算，与现有文件**逐字节相同**：

| run | 现 `.inventory.json` sha256 | 重算 sha256 | 相同 |
|---|---|---|---|
| renderer | `0bc172e61b625767173140ff0709df5a7034ac016fc0164d26ddf6a559fb25e7` | 同左 | ✅ True |
| display | `1eda6525557eca995ed5c2e77f4bfd3cbd74658bebe47b73d4d8830870f8bda4` | 同左 | ✅ True |

⇒ **`.inventory.json` 内容不变**（只会被重写相同字节）；**只有 `.experiment.json` 变**（多 `promoted_to` + `promoted_at`）。

**`notes/evidence/**/final/` 会不会被回写？不会。** promote 只操作 `build/experiments/active/<task>/<run_id>/`。notes 副本保持无 `promoted_to` 的历史收据形态，自带文件清单完好，**不会破坏**。反过来说，也不要去改 notes 副本 —— 它是历史事实。

### 2.5 promote 前置验收：verifier 现在还能通过吗？✅ 全部通过

| verifier | 目标 | 实测输出 | 耗时 |
|---|---|---|---|
| `verify_rom_renderer_records_delta.py` | `build/.../combined-tier1-20261001-v1/final` | `verified: true, contract_ok: true, errors: [], promotion_bytes: 1668, record_count: 29, consumer_count: 47, accepted_site_count: 34, excluded_site_count: 13` | < 1 s |
| `verify_rom_display_text_delta.py` | `build/.../tier1-20261001-v1/final` | `verified: true, contract_ok: true, errors: [], promotion_bytes: 1053, record_count: 85, consumer_count: 92, source_verifier_count: 6` | ~70 s |
| `verify_rom_animation_descriptor_pool_v2.py` | `artifacts/rom-animation-descriptor-pool-v2` | `verified: true, promotion_bytes: 640` | 0.17 s |

### 2.6 `implementation_inputs` 逐条与仓库实时文件比对（**7/7 全 MATCH**）

命令脚本包（`final/manifest.json`）：

| path | pinned sha256 | pinned size | live sha256 | live size | 判定 |
|---|---|---|---|---|---|
| `tools/export_rom_renderer_records_delta.py` | `7764bfcbabb945b6ec84ec672184bcbde9333dd9e1750199b5ce8c4bb3685b2a` | 6 607 | 同 | 6 607 | ✅ |
| `tools/verify_rom_renderer_records_delta.py` | `cad0e044a09dacc00ad75ac905edb8d83d9d92f836d219eca1f7ce8e5f349f46` | 11 708 | 同 | 11 708 | ✅ |
| `tests/test_rom_renderer_records_delta.py` | `5af965dd6325bb2301ac1e31fa6e7b108b2121b4d29832e84c2518aaa2839513` | 9 784 | 同 | 9 784 | ✅ |

显示文本包（`final/manifest.json`）：

| path | pinned sha256 | pinned size | live sha256 | live size | 判定 |
|---|---|---|---|---|---|
| `tools/export_rom_display_text_delta.py` | `10f6c5bebe56aa832ddbd766c5bd087fccd3637ecbcbd1acbba696331fdca944` | 6 857 | 同 | 6 857 | ✅ |
| `tools/verify_rom_display_text_delta.py` | `01e9a8a6ba4e0137bfa60a4a6f4d632caa3fc3a5a76b9989426196e4ce828cb0` | 12 148 | 同 | 12 148 | ✅ |
| `tools/rom_display_text_parameter_flow.py` | `416c7652a1ad9e7c281305fae8283c9636eb334fb8ed4708f033afa99ee4098e` | 3 282 | 同 | 3 282 | ✅ |
| `tests/test_rom_display_text_delta.py` | `7c32e692eef0c984fc26ae62370f4e1ab467c6ce8663c26148f3cfc90f12df98` | 9 533 | 同 | 9 533 | ✅ |

**合同 JSON 交叉核对**（`public_contract_sha256` vs `tools/data/` 实体）：

| 合同文件 | pinned | live | 判定 |
|---|---|---|---|
| `tools/data/rom-renderer-records-delta-contract-v1.json` | `59b4c53393c58fb0f3f25f78a3963908fe10984afa0e26036981dffaddc1eec6` | 同 | ✅ |
| `tools/data/rom-display-text-delta-contract-v1.json` | `ca0f7e4e384fdaffd7c7ae5dd73da1c6ff9bcc9ff5d5a0f211a8810f5f76e390` | 同 | ✅ |

---

## 3. auditor 接线方案

### 3.0 三处插入锚点（当前工作树行号）

| 位置 | 锚点 | 插在哪 |
|---|---|---|
| **常量块** | `FIXED_ANIMATION_DESCRIPTOR_GROUPS_VERIFIER_SHA256` 块结束于 **33662**，`BATTLE_DISTANCE_DISPATCHER_CFG_ARTIFACT` 起于 **33663** | 插在 **33662 与 33663 之间** |
| **claim 函数** | `_fixed_animation_descriptor_group_claims` 结束于 **35240**（`return claims`），`_battle_distance_dispatcher_cfg_claims` 起于 **35243** | 插在 **35240 与 35243 之间** |
| **`build_manifest()`** | `_small_cfg_dependency_batch_claims` 行在 **36089**，`claims.sort(...)` 行在 **36090** | 插在 **36089 与 36090 之间** |

### 3.1 常量块（可直接粘贴到 33662 之后）

```python
RENDERER_RECORDS_DELTA_ARTIFACT = Path("artifacts/rom-renderer-records-delta-v1")
RENDERER_RECORDS_DELTA_PAYLOAD = "rom-renderer-records-delta.json"
RENDERER_RECORDS_DELTA_MANIFEST_SIZE = 1_569
RENDERER_RECORDS_DELTA_MANIFEST_SHA256 = (
    "7191a579d0995fef7c55b41af2488abf02a882e8d22c06dd5489d0e4b0d2c72e"
)
RENDERER_RECORDS_DELTA_PAYLOAD_SIZE = 35_709
RENDERER_RECORDS_DELTA_PAYLOAD_SHA256 = (
    "12f9688e7ac67e83b089f341001bb0e0c543c2197fe22202399b9a4119794b67"
)
RENDERER_RECORDS_DELTA_VERIFIER = Path("tools/verify_rom_renderer_records_delta.py")
RENDERER_RECORDS_DELTA_VERIFIER_SHA256 = (
    "cad0e044a09dacc00ad75ac905edb8d83d9d92f836d219eca1f7ce8e5f349f46"
)
DISPLAY_TEXT_DELTA_ARTIFACT = Path("artifacts/rom-display-text-delta-v1")
DISPLAY_TEXT_DELTA_PAYLOAD = "rom-display-text-delta.json"
DISPLAY_TEXT_DELTA_MANIFEST_SIZE = 1_683
DISPLAY_TEXT_DELTA_MANIFEST_SHA256 = (
    "c63319575c27969f9c0bbeb271a436cd4195f32f946b26bda62f64dbf0cbc69d"
)
DISPLAY_TEXT_DELTA_PAYLOAD_SIZE = 94_550
DISPLAY_TEXT_DELTA_PAYLOAD_SHA256 = (
    "1fb3541e0d97fe383e665723c337760a40d19aebade32e7e1f6afa53a599e75a"
)
DISPLAY_TEXT_DELTA_VERIFIER = Path("tools/verify_rom_display_text_delta.py")
DISPLAY_TEXT_DELTA_VERIFIER_SHA256 = (
    "01e9a8a6ba4e0137bfa60a4a6f4d632caa3fc3a5a76b9989426196e4ce828cb0"
)
ANIMATION_DESCRIPTOR_POOL_V2_ARTIFACT = Path(
    "artifacts/rom-animation-descriptor-pool-v2"
)
ANIMATION_DESCRIPTOR_POOL_V2_PAYLOAD = "rom-animation-descriptor-pool-v2.json"
ANIMATION_DESCRIPTOR_POOL_V2_MANIFEST_SIZE = 1_195
ANIMATION_DESCRIPTOR_POOL_V2_MANIFEST_SHA256 = (
    "81a4e698d523a0e78c379a2c0dbb8bed48cdeec726b11fb096cf8b7a70befffa"
)
ANIMATION_DESCRIPTOR_POOL_V2_PAYLOAD_SIZE = 35_254
ANIMATION_DESCRIPTOR_POOL_V2_PAYLOAD_SHA256 = (
    "7f9c4a36c0f29f3abe0351a7ba5af96c5f27a8d396d81fbe28ed34df574ebf7f"
)
ANIMATION_DESCRIPTOR_POOL_V2_VERIFIER = Path(
    "tools/verify_rom_animation_descriptor_pool_v2.py"
)
ANIMATION_DESCRIPTOR_POOL_V2_VERIFIER_SHA256 = (
    "53d7a82acf5a8a55ceb311ce51da392a29c5ec6dfcd18d1c2a21cd2a8745fea7"
)
```

> 常量值来源：manifest/payload 的 size+sha256 见 §1.1、§2.6；verifier sha256 = manifest `implementation_inputs` 钉值（已核对 live 文件一致）。

### 3.2 三个 claim 函数（可直接粘贴到 35240 之后）

```python
def _renderer_records_delta_claims(root, rom, existing_claims):
    """Project the 29 renderer command-script records of the delta packet."""

    from tools.verify_rom_renderer_records_delta import verify_artifact

    def class_for(row):
        value = row.get("primary_class")
        if value != "fixed_cfg_consumer_renderer_command_script":
            raise ValueError("renderer records delta semantic class changed")
        return value

    def kind_for(row):
        value = row.get("claim_kind")
        if value != "fixed_cfg_consumer_renderer_command_script_bytes":
            raise ValueError("renderer records delta claim kind changed")
        return value

    spec = {
        "label": "renderer records delta",
        "artifact": RENDERER_RECORDS_DELTA_ARTIFACT,
        "payload": RENDERER_RECORDS_DELTA_PAYLOAD,
        "manifest_size": RENDERER_RECORDS_DELTA_MANIFEST_SIZE,
        "manifest_sha": RENDERER_RECORDS_DELTA_MANIFEST_SHA256,
        "payload_size": RENDERER_RECORDS_DELTA_PAYLOAD_SIZE,
        "payload_sha": RENDERER_RECORDS_DELTA_PAYLOAD_SHA256,
        "verifier": RENDERER_RECORDS_DELTA_VERIFIER,
        "verifier_sha": RENDERER_RECORDS_DELTA_VERIFIER_SHA256,
        "promotion_bytes": 1_668,
        "claim_count": 29,
        "batch": "rom-renderer-records-delta-v1",
        "hash_field": "bytes_sha256",
        "class_for": class_for,
        "kind_for": kind_for,
    }
    claims = _project_dependency_packet_claims(
        root,
        rom,
        existing_claims,
        spec=spec,
        verify_root=lambda verifier_root, artifact: verify_artifact(
            verifier_root, artifact
        ),
    )
    for claim in claims:
        claim["current_unknown_verified_by_auditor"] = True
        claim["coverage_projection_gate"] = "current_unknown_before_projection"
        claim["canonical_cfg_consumer_denominator_verified"] = True
        claim["interpreter_r0_parameter_flow_verified"] = True
    return claims


def _display_text_delta_claims(root, rom, existing_claims):
    """Project the 85 display-text records of the delta packet."""

    from tools.verify_rom_display_text_delta import verify_artifact

    def class_for(row):
        value = row.get("primary_class")
        if value != "fixed_cfg_consumer_renderer_display_text":
            raise ValueError("display text delta semantic class changed")
        return value

    def kind_for(row):
        value = row.get("claim_kind")
        if value != "fixed_cfg_consumer_renderer_display_text_bytes":
            raise ValueError("display text delta claim kind changed")
        return value

    spec = {
        "label": "display text delta",
        "artifact": DISPLAY_TEXT_DELTA_ARTIFACT,
        "payload": DISPLAY_TEXT_DELTA_PAYLOAD,
        "manifest_size": DISPLAY_TEXT_DELTA_MANIFEST_SIZE,
        "manifest_sha": DISPLAY_TEXT_DELTA_MANIFEST_SHA256,
        "payload_size": DISPLAY_TEXT_DELTA_PAYLOAD_SIZE,
        "payload_sha": DISPLAY_TEXT_DELTA_PAYLOAD_SHA256,
        "verifier": DISPLAY_TEXT_DELTA_VERIFIER,
        "verifier_sha": DISPLAY_TEXT_DELTA_VERIFIER_SHA256,
        "promotion_bytes": 1_053,
        "claim_count": 85,
        "batch": "rom-display-text-delta-v1",
        "hash_field": "bytes_sha256",
        "class_for": class_for,
        "kind_for": kind_for,
    }
    claims = _project_dependency_packet_claims(
        root,
        rom,
        existing_claims,
        spec=spec,
        verify_root=lambda verifier_root, artifact: verify_artifact(
            verifier_root, artifact
        ),
    )
    for claim in claims:
        claim["current_unknown_verified_by_auditor"] = True
        claim["coverage_projection_gate"] = "current_unknown_before_projection"
        claim["canonical_cfg_consumer_denominator_verified"] = True
        claim["interpreter_r0_parameter_flow_verified"] = True
    return claims


def _animation_descriptor_pool_v2_claims(root, rom, existing_claims):
    """Project the animation descriptor pool's single 640-byte group claim."""

    from tools.verify_rom_animation_descriptor_pool_v2 import verify_artifact

    def class_for(row):
        value = row.get("primary_class")
        if value != "fixed_consumer_animation_descriptor_group_bytes":
            raise ValueError("animation descriptor pool semantic class changed")
        return value

    def kind_for(row):
        value = row.get("claim_kind")
        if value != "fixed_consumer_animation_descriptor_group_bytes":
            raise ValueError("animation descriptor pool claim kind changed")
        return value

    spec = {
        "label": "animation descriptor pool v2",
        "artifact": ANIMATION_DESCRIPTOR_POOL_V2_ARTIFACT,
        "payload": ANIMATION_DESCRIPTOR_POOL_V2_PAYLOAD,
        "manifest_size": ANIMATION_DESCRIPTOR_POOL_V2_MANIFEST_SIZE,
        "manifest_sha": ANIMATION_DESCRIPTOR_POOL_V2_MANIFEST_SHA256,
        "payload_size": ANIMATION_DESCRIPTOR_POOL_V2_PAYLOAD_SIZE,
        "payload_sha": ANIMATION_DESCRIPTOR_POOL_V2_PAYLOAD_SHA256,
        "verifier": ANIMATION_DESCRIPTOR_POOL_V2_VERIFIER,
        "verifier_sha": ANIMATION_DESCRIPTOR_POOL_V2_VERIFIER_SHA256,
        "promotion_bytes": 640,
        "claim_count": 1,
        "batch": "rom-animation-descriptor-pool-v2",
        "hash_field": "bytes_sha256",
        "class_for": class_for,
        "kind_for": kind_for,
    }
    claims = _project_dependency_packet_claims(
        root,
        rom,
        existing_claims,
        spec=spec,
        verify_root=lambda verifier_root, artifact: verify_artifact(
            verifier_root, artifact
        ),
    )
    for claim in claims:
        claim["current_unknown_verified_by_auditor"] = True
        claim["coverage_projection_gate"] = "current_unknown_before_projection"
        claim["descriptor_pool_denominator_verified"] = True
        claim["pointer_slot_terminator_verified"] = True
        claim["natural_runtime_claimed"] = False
    return claims
```

**形态与既有实现完全一致**（逐项对齐 `_fixed_renderer_script_record_claims` 35016–35062 与 `_fixed_animation_descriptor_group_claims` 35193–35240）：

| spec 键 | 用途 |
|---|---|
| `label` | 报错前缀 |
| `artifact` / `payload` | 目录与 payload 文件名 |
| `manifest_size` / `manifest_sha` / `payload_size` / `payload_sha` | 冻结身份（`_project_dependency_packet_claims` 第 33857 行四元组比对） |
| `verifier` / `verifier_sha` | verifier 路径与 SHA（`_checked_repository_file`） |
| `promotion_bytes` / `claim_count` | 字节与 claim 分母（33860、33863 行） |
| `batch` | 写入 claim 的 `promotion_batch` |
| `hash_field` | `bytes_sha256`（三包 payload 都用这个键名） |
| `class_for` / `kind_for` | 语义类/种类闭包，**同时**充当「语义未变」的失败关闭闸门 |
| `verify_root=` | `lambda verifier_root, artifact: verify_artifact(verifier_root, artifact)` |

**没有** `mode_for` → `mode` 恒为 `None`（三包都是数据字节，非代码），与 `_fixed_animation_descriptor_group_claims` 一致。**没有** `is_code`/`is_literal` 分支 —— 走 `class_for` 分支（第 33875–33880 行）。

### 3.3 `build_manifest()` 里三行 `claims += ...`

插在 **36089 之后、36090 之前**：

```python
    claims += _small_cfg_dependency_batch_claims(root, rom, claims)      # 36089（既有）
    claims += _renderer_records_delta_claims(root, rom, claims)          # 新增
    claims += _display_text_delta_claims(root, rom, claims)               # 新增
    claims += _animation_descriptor_pool_v2_claims(root, rom, claims)     # 新增
    claims.sort(key=lambda claim: (claim["range"], claim["id"]))           # 36090（既有）
```

**顺序敏感性**：

- `existing_claims` 参数就是**累加到当前为止的整张 `claims` 列表**（`claims += f(root, rom, claims)` —— 传的是同一个列表对象）。因此传入的必须是「已含全部既有 claim」的列表。
- `_require_current_unknown_ranges`（33795–33849 行）用它做三件事：① 所有 id 唯一且非空；② `role ∈ {primary, secondary}`；③ primary claim 之间不得重叠（`right[0] < left[1]` → 抛 "conflicting primary claims"）；④ 候选区间不得被任何 primary claim 覆盖（否则抛 "is not current unknown"）。
- ⇒ **新三包必须放在所有 `claims +=` 之后**：只有这样，传入的 `existing_claims` 才包含全部 16 913 条既有 claim，重叠检查才有意义。
- 实际上三包与既有 claim **零重叠**（§4 已实测），因此插入位置在功能上不敏感；但**放在末尾**是唯一符合语义的顺序（"最后晋升的先看到全部既有 owner"），且与既有 89 行 `claims +=` 的排列习惯一致。
- 三包**彼此**也不重叠，所以三行之间的相对顺序自由。
- ⚠️ **不可**在 `claims.sort()` 之后插入 —— sort 之后的列表顺序已按 range 排好，但语义上 `existing_claims` 就变成"排好序但仍完整"，其实也可；不过放在 sort 前更符合既有全部 89 行的写法。

### 3.4 M1 是否需要另一套形状？—— **不需要**

M1 走 `_project_dependency_packet_claims` 完全可行，理由：

1. 它的 `promotion.claims` 是**标准列表**，元素含 `id` / `range` / `bytes_sha256` / `primary_class` / `claim_kind`（键集 = `['bytes_sha256','claim_kind','id','primary_class','range']`），与该函数第 33862–33896 行的读取方式完全对齐。
2. `hash_field = "bytes_sha256"` ✅（`row.get("bytes_sha256")` 命中）
3. `claim_count = 1`、`promotion_bytes = 640` ✅（第 33863、33898 行）
4. 它的 verifier `verify_artifact` 返回 `verified: True` + `promotion_bytes: 640` ✅（第 33860 行要求）
5. `promotion.claims` 内**无重叠** ✅（第 33898 行 `a["range"][1] > b["range"][0]` 检查通过）
6. 它的 `artifacts/rom-animation-descriptor-pool-v2/` 目录成员恰为 `{manifest.json, rom-animation-descriptor-pool-v2.json}` ✅（`_checked_artifact_directory` 默认 `expected_files`）

**它不是 pointer/descriptor 池的特例**：`pointer_slots` / `descriptors` / `sequences` 这些子结构是**包内部**的字节归因分解，claim 层面仍是一条连续区间 `[4555564,4556204]`（496+16+64+64 全部连续），所以对审计器而言就是**一个普通 record 型 primary claim**。

唯一的语义差异：**M1 与既有 `rom-fixed-animation-descriptor-groups-v1` 共用 `primary_class`**（§1.2 撞名）。这在审计器层面不违规（`atomize_claims` 与 `_require_current_unknown_ranges` 都不要求 class 唯一），但意味着账本按 class 汇总时两族合并。

### 3.5 summary 键：需不需要新增？

**不需要（推荐沿用先例）。** 已核：既有三个同类包 `rom-fixed-renderer-script-records-v1` / `rom-renderer-script-pointer-pool-records-v1` / `rom-fixed-animation-descriptor-groups-v1` 在账本 `summary` 里**都没有**专属键（`grep` 确认无 `*_bytes` / `*_claim_count` 条目），proof 的 514 条 `/summary/*` 断言里**也没有**它们的键。

⇒ 新三包**不新增** summary 键 ⇒ proof 里只有 4 个 `/summary/*` 断言需要改（见 §5）。

> 若甲线希望「三包字节可被 proof 单独断言」，那就必须新增 6 个 summary 键（每包 `*_bytes` + `*_claim_count`），并在 `build_manifest()` 的 summary dict（约 36098–36400 行）里加 6 个 `sum(...)` 表达式 + proof 里加 6 条 `/summary/*` 断言。**代价**：账本 schema 扩张、proof 合同扩张、覆盖率审计器 diff 变大。**默认建议：不加**；三包字节改由 `limitations` 文字钉住（§5）。

---

## 4. canonical 重建后的预期账本数字

### 4.1 复算方法（未跑审计器）

用与 `atomize_claims`（`tools/audit_rom_byte_coverage.py:7023`）**语义等价**的 O(n log n) 算法（端点集排序 + 逐 claim 覆盖区间归属 + 冲突即报错）离线复算。

**基线自校验**（证明复算等价）：

| 指标 | 复算值 | 账本 `summary` | 判定 |
|---|---|---|---|
| `claim_count` | 16 913 | 16 913 | ✅ |
| `segment_count` | 18 675 | 18 675 | ✅ |
| `accounted_bytes` | 6 291 456 | 6 291 456 | ✅ |
| `unknown_bytes` | 86 089 | 86 089 | ✅ |
| `classified_bytes` | 6 205 367 | 6 205 367 | ✅ |

### 4.2 投影值（基线 + 三包）

| 指标 | 现值 | 投影值 | Δ |
|---|---:|---:|---:|
| `claim_count` | 16 913 | **17 028** | **+115**（= 1 + 29 + 85） |
| `segment_count` | 18 675 | **18 882** | **+207** |
| `accounted_bytes` | 6 291 456 | 6 291 456 | 0 |
| `unknown_bytes` | 86 089 | **82 728** | **−3 361** |
| `classified_bytes` | 6 205 367 | **6 208 728** | **+3 361** |

`+207` 段数的来源：三包共 115 条 claim 切进原本连续的 unknown 段，把每条 claim 边界都变成新段端点。**注意：不是 115** —— 3 361 B 被切成 115 段后，unknown 段被这些边界进一步细分。实测 18 882。

### 4.3 不重叠核对结果

| 核对项 | 结果 |
|---|---|
| 命令脚本包（29 条，1 668 B，span 0x0BCD..0x542E）内部自重叠 | **0** |
| 显示文本包（85 条，1 053 B，span 0x12EE4C..0x463B16）内部自重叠 | **0** |
| M1（1 条，640 B，0x458564..0x45879C）内部自重叠 | **0** |
| 三包与活账本 16 913 条既有 primary claim 的重叠 | **0**（全部落在当前 unknown） |
| 命令脚本 × 显示文本 | **0** |
| 命令脚本 × M1 | **0** |
| 显示文本 × M1 | **0** |
| 活账本 16 913 条 primary claim 彼此重叠 | **0**（复算确认） |

**按 class 的 totals 变化**：

| `primary_class` | 现 | 投影 | Δ |
|---|---:|---:|---:|
| `fixed_cfg_consumer_renderer_command_script` | 2 666 | 4 334 | +1 668 |
| `fixed_cfg_consumer_renderer_display_text` | 0 | 1 053 | +1 053 |
| `fixed_consumer_animation_descriptor_group_bytes` | 1 136 | 1 776 | +640 |

---

## 5. 账本外要同步的每一处

### 5.1 `sequel/reverse-engineering-proof.json` → `gates.rom_byte_coverage`

#### (a) `evidence` 追加 6 条（当前 188 条 → 194 条）

```json
{"path": "artifacts/rom-renderer-records-delta-v1/manifest.json", "sha256": "7191a579d0995fef7c55b41af2488abf02a882e8d22c06dd5489d0e4b0d2c72e"},
{"path": "artifacts/rom-renderer-records-delta-v1/rom-renderer-records-delta.json", "sha256": "12f9688e7ac67e83b089f341001bb0e0c543c2197fe22202399b9a4119794b67"},
{"path": "artifacts/rom-display-text-delta-v1/manifest.json", "sha256": "c63319575c27969f9c0bbeb271a436cd4195f32f946b26bda62f64dbf0cbc69d"},
{"path": "artifacts/rom-display-text-delta-v1/rom-display-text-delta.json", "sha256": "1fb3541e0d97fe383e665723c337760a40d19aebade32e7e1f6afa53a599e75a"},
{"path": "artifacts/rom-animation-descriptor-pool-v2/manifest.json", "sha256": "81a4e698d523a0e78c379a2c0dbb8bed48cdeec726b11fb096cf8b7a70befffa"},
{"path": "artifacts/rom-animation-descriptor-pool-v2/rom-animation-descriptor-pool-v2.json", "sha256": "7f9c4a36c0f29f3abe0351a7ba5af96c5f27a8d396d81fbe28ed34df574ebf7f"}
```

**可选追加 2 条合同 JSON**（先例：`tools/data/rom-small-cfg-dependency-publication-v1.json` 在 evidence 里；两个 renderer 合同是各自 verifier 的 `CONTRACT_SHA` 来源，加进 evidence 可让合同本身可审计）：

```json
{"path": "tools/data/rom-renderer-records-delta-contract-v1.json", "sha256": "59b4c53393c58fb0f3f25f78a3963908fe10984afa0e26036981dffaddc1eec6"},
{"path": "tools/data/rom-display-text-delta-contract-v1.json", "sha256": "ca0f7e4e384fdaffd7c7ae5dd73da1c6ff9bcc9ff5d5a0f211a8810f5f76e390"}
```

**另需刷新**：`sequel/rom-byte-coverage.json` 自己的 evidence 条目 sha256（账本重建后变化，由 `apply.py` 步骤 1 自动处理）。

> **重要：evidence 变更不会连带打破任何 hash 绑定断言。** 实测 proof 全文 `gate_evidence` / `gate_cases` 出现次数 = **0** —— 即 `_check_gate_coverage` 要求的 `/gate_evidence/<gate>` 绑定在当前 spec 里**本来就不存在**（既有 blocker，与本次改动无关）。

#### (b) `verifiers` 追加 —— **只有 M1 能加，两个 renderer 包不能加**（关键阻塞）

`tools/audit_reverse_engineering_proof.py` 的合同校验：
- `_contract()`（第 247–265 行）：`assertions` 必须非空、**`/schema` 必须是字符串**、且有 `/verified is True` 或 `/errors == []`
- 第 965–972 行：逐键 `_json_pointer(payload, pointer)`，**pointer 在实际 report 里不存在 → `<missing>` → 失配**

现状：proof 现有 **98/98** 条 verifier 合同**都带** `/schema`；而两个 renderer verifier 的 report **没有 `schema` 键**：

```
tools/verify_rom_renderer_records_delta.py:210-212 → report = {'verified': True, 'contract_ok': True, 'errors': [], 'consumer_count': 47, 'accepted_site_count': 34, 'excluded_site_count': 13, 'record_count': 29, 'promotion_bytes': 1668, 'natural_runtime_reachability': False, 'current_unknown_checked': False, 'immutable_unknown_projection_checked': True}   ← 无 schema
tools/verify_rom_display_text_delta.py:206-208   → report = {'verified': True, 'contract_ok': True, 'errors': [], 'consumer_count': 92, 'record_count': 85, 'promotion_bytes': 1053, 'source_verifier_count': 6, ...}   ← 无 schema
```

⇒ **给它们写 `/schema` 断言必然失配**。而**改 verifier 加 `schema`** 会连锁打破：`final/manifest.json` 的 `implementation_inputs` 钉的 verifier SHA 失配 → `intended_manifest()` 比对失败 → 需重冻 `final/` → `notes/evidence/**` 历史收据与新 manifest 不一致 → **破坏历史收据完整性**。**不建议**。

**先例支持「不是每个包都要有 proof verifier 条目」**：

| 包 | verifier 有 `schema`？ | 在 proof `verifiers` 里？ |
|---|---|---|
| `verify_rom_fixed_renderer_script_records.py` | ✅ 有 | ❌ **不在** |
| `verify_rom_renderer_script_pointer_pool_records.py` | ✅ 有 | ✅ 在 |
| `verify_rom_fixed_animation_descriptor_groups.py` | ✅ 有 | ❌ **不在** |

**推荐方案**：

- **M1 可以加**（它的 report 有 `schema`）：
```json
{
  "command": ["python3", "tools/verify_rom_animation_descriptor_pool_v2.py", "--root", ".", "--artifact", "artifacts/rom-animation-descriptor-pool-v2"],
  "script_sha256": "53d7a82acf5a8a55ceb311ce51da392a29c5ec6dfcd18d1c2a21cd2a8745fea7",
  "contract": {
    "format": "json",
    "assertions": {
      "/schema": "rom-animation-descriptor-pool-v2-verification-v1",
      "/verified": true,
      "/errors": [],
      "/descriptor_count": 8,
      "/descriptor_entry_count": 24,
      "/base_pair_count": 7,
      "/promotion_bytes": 640
    }
  }
}
```
- **两个 renderer 包不加 `verifiers` 条目**，只加 `evidence`（§5.1a）。它们的验证已被 coverage auditor 在建账时强制执行（`verify_root` 闭包 + `independent_verifier_path` / `independent_verifier_sha256` / `independent_verifier_report_sha256` 写进每条 claim），由 auditor 自己的合同（`/summary/*` 断言）间接钉住。
  - 若甲线坚持要 proof 级 verifier 条目，**唯一安全做法**是改 verifier 加 `schema` 并**重冻整条链**（重跑 exporter → 新 manifest → 新 `notes/evidence` 副本 → 新 artifacts）—— 成本远超本轮收益。**列为待决项**。

#### (c) `limitations` 追加

- **`limitations[0]`**（未分类字节声明）必须刷新：
```
"The manifest explicitly accounts for all 6291456 bytes, but 82728 bytes (1.3149%) remain semantically unknown."
```
（现值：`86089 bytes (1.3683%)`）—— 格式与 `apply.py` 第 214–217 行、`tests/test_audit_reverse_engineering_proof.py:3399-3405` 一致。

- **新增 3 条**（每包一条，与 `apply.py` 第 222–234 行的 pointer-pool 先例同形）：

```
"The renderer records delta artifact classifies exactly 1668 previously unknown bytes as 29 renderer command-script records across 47 consumer sites (34 accepted, 13 excluded) in [0x000BCD,0x00542E), using the already accepted command grammar; natural runtime reachability, the global consumer denominator and the excluded sites remain unclaimed."

"The display text delta artifact classifies exactly 1053 previously unknown bytes as 85 display-text records across 92 consumers in [0x12EE4C,0x463B16), bound to six independently verified source verifiers; natural runtime reachability, text semantics and the global consumer denominator remain unclaimed."

"The animation descriptor pool v2 artifact classifies exactly 640 previously unknown bytes as one animation descriptor group at [0x458564,0x45879C), comprising 496 descriptor bytes, 64 pointer-slot bytes, 64 sequence bytes and 16 structurally verified padding bytes; the 488-byte heterogeneous tail at [0x45879C,0x458A34) remains outside the claim and unclaimed. Only 2 of 48 base-pair pools are attributed, so the caller denominator is not closed; the callback domain, the flags domain, the index domain, natural runtime reachability, editing safety and free or allocatable space remain unclaimed."
```

> 措辞里刻意带上「不闭合」的部分（`scope` 里 9 个 false 标志、48→2 的 caller 分母、488 B 异族尾巴），与账本的「保守不外推」契约一致。

#### (d) coverage verifier 自身的 `/summary/*` 断言 —— **只有 4 条要改**

| 断言 | 现值 | 新值 |
|---|---|---|
| `/summary/unknown_bytes` | `86089` | **`82728`** |
| `/summary/classified_bytes` | `6205367` | **`6208728`** |
| `/summary/claim_count` | `16913` | **`17028`** |
| `/summary/segment_count` | `18675` | **`18882`** |

其余 510 条 `/summary/*` 断言**不变**（三包不新增 summary 键，见 §3.5）。`/schema`、`/verified`、`/state_inventory_complete`、`/semantic_classification_complete` 不变。

### 5.2 auditor 自身 SHA 的同步

- **当前 live SHA**（`tools/audit_rom_byte_coverage.py`，含工作树未提交的 PSG pin 刷新 4 行）：`1fba11127dba9dcc0155c342ff2dcb1b00e9671fee5d12f3a6d2aa3e158cbe6c`
- **当前 proof 钉值**：`sequel/reverse-engineering-proof.json:789` = `1fba11127dba9dcc0155c342ff2dcb1b00e9671fee5d12f3a6d2aa3e158cbe6c` → **当前一致** ✅
  （HEAD 版本是 `e3a771db83c496f4f2815177a76dfccd709c4f9f4717ca9850a7be827dd3a203`，已由 2026-10-20 的 pin 刷新改成 `1fba1112…`；`e3a771db…` 现在**无任何引用**。）
- **接线后**：新 SHA = `sha256(改完的 tools/audit_rom_byte_coverage.py)`，**必须**写回 `sequel/reverse-engineering-proof.json` 的 `gates.rom_byte_coverage.verifiers[0].script_sha256`（该条目 `command[1] == "tools/audit_rom_byte_coverage.py"`）。
- **该 SHA 全仓库只有一个引用点**（实测 `grep`）：`sequel/reverse-engineering-proof.json:789`。改 auditor 不会连带打破别的硬编码。
- **自动化**：`apply.py` 第 182–189 行（`_find_coverage_verifier` → 刷新 `script_sha256`）+ 第 190–208 行（把 514 条 `/summary/*` 断言逐键刷成活账本值）**已经能做这件事**。但 `apply.py` 是**上一个包的单包脚本**（`PACKAGE_ARTIFACT` / `PACKAGE_BATCH` 等常量硬编码为 pointer-pool），**不能直接复用**；要么照它复制一份三包版（推荐），要么在它的基础上参数化。

### 5.3 `docs/` 与 `notes/` 需要跟着改的行

| 文件 | 行 | 现状措辞 | 改成 |
|---|---|---|---|
| `docs/reverse-engineering-proof-policy.md` | 163–165 | `` `6,205,367` 字节／`98.63165219624838%`／`86,089` 字节／16,913 claims / 18,675 segments`` | `` `6,208,728` 字节／`98.68507385253906%`／`82,728` 字节／17,028 claims / 18,882 segments`` |
| `sequel/reverse-engineering-proof.json` | 4960 | `"The manifest explicitly accounts for all 6291456 bytes, but 86089 bytes (1.3683%) remain semantically unknown."` | `"... but 82728 bytes (1.3149%) remain semantically unknown."` |
| `notes/line-a-progress-20261019.md` | 127 | `当前 16,913 claims / 18,675 segments）。` | `当前 17,028 claims / 18,882 segments）。` |
| `notes/line-a-progress-20261019.md` | 265–268 | 池 3 入账表（`87,631 → 86,089` / `6,203,825 → 6,205,367` / `16,912 → 16,913` / `18,675（不变）`） | **历史记录，不要改**；本轮应**新增一行/一表**记录三包（`86,089 → 82,728` / `6,205,367 → 6,208,728` / `16,913 → 17,028` / `18,675 → 18,882`） |
| `notes/line-a-progress-20261019.md` | 320–321 | `2,721 B 两包未入账；其中 1,668 B 缺 artifact 目录。` | 本轮完成后应改写为「已入账」并注明 M1 640 B |
| `notes/line-a-progress-20261019.md` | 171 | `M0-c 2,721 B 两包入账 \| **未完成** \| 显示文本 1,053 B 有永久收据；**旧命令脚本 1,668 B 的产物只在被 gitignore 的 build/ 下，没有 artifact 目录**` | 状态改「已完成」，补 artifact 路径与新计数 |
| `notes/line-a-progress-20261019.md` | 173 | `M0-c 孤儿 artifact \| 待清理 \| artifacts/rom-low-script-delta-v1/ 账本引用 0、proof 引用 0` | 见 §6(e)：本轮**不处理**（新包已完全覆盖其区间），但要写明「已被 `rom-renderer-records-delta-v1` 覆盖，不再独立入账」 |
| `notes/line-a-progress-20261019.md` | 327 | `artifacts/rom-low-script-delta-v1/ 的孤儿状态未处理。` | 同上，补一句说明 |
| `notes/line-a-progress-20261019.md` | 564–565 | 「policy 文档同步」条目（记录上一轮做法） | 追加本轮三包的同步结果 |
| `notes/line-a-progress-20261019.md` | 690–693 | 历史对照表（`149,280` / `6,142,176` / `15,940` / `17,344` → `86,089` / `6,205,367` / `16,913` / `18,675`） | 右列更新为新值（或新增一列，取决于该表语义） |
| `docs/sequel-roadmap.md` | 文件末尾（约 218–224 行的 2026-10-01 区块后） | 最新条目停在 2026-09-05（`6,203,707 / 87,749 / 16,891 / 18,664`） | **追加 2026-10-20 三包入账条目**（AGENTS.md 强制要求路线图同步）。注意 roadmap 已落后两轮（池 3 的 86,089 也没记）—— 建议补两条或一条合并说明 |

**不会破的测试**（实测确认）：

- `tests/test_audit_reverse_engineering_proof.py` 的 `assertGreaterEqual(len(gate["evidence"]), 96)` / `assertGreaterEqual(len(gate["verifiers"]), 92)`（12 处）—— 是下界，**evidence 188→194、verifiers 98→99 不会破**。
- `tests/test_audit_reverse_engineering_coverage_count_liveness.py` —— 它的 `test_no_test_source_hardcodes_a_live_ledger_quantity` 会自动抓出任何残留的硬编码全局量；`test_current_spec_binds_*` 系列若涉及我们的 4 个 `/summary/*` 键，会在 proof 刷新后转绿。
- `tests/test_coverage_evidence_selector_repairs.py:66` 只是注释（`87,749 → 87,631 → 86,089`），非断言。
- `tests/test_verify_rom_psg_frequency_lookup.py:109` 只是注释。
- `HISTORICAL_PINNED`（`test_audit_reverse_engineering_coverage_count_liveness.py:69-72`）钉的是 9-30 收据的历史值 `87_631`（`test_rom_small_cfg_batch_canonical.py` / `test_rom_renderer_script_pointer_pool_canonical.py`）—— **不要动**，那是历史钉；`test_historical_pins_are_still_pinned_to_the_old_value` 还断言它**不得**等于活账本当前值。

---

## 6. 风险清单

### (a) 三包与活账本既有 claim 的重叠 → **无风险** ✅

实测：三包全部 115 条 claim 与活账本 16 913 条 primary claim **零重叠**，全部落在当前 unknown 段内（`unknown_bytes` 86 089 的范围内）。活账本自身 primary claim 之间也无重叠。

### (b) 有没有别的包已认领同样字节（重复 claim）→ **账本内无重复** ✅ / **仓库内有孤儿重叠** ⚠️

- 账本内：`_require_current_unknown_ranges` 会在建账时对每条新 claim 复查「不是 current unknown」，任何重叠都会**失败关闭**并让审计器退出非 0。已实测无重叠。
- **仓库内**：`artifacts/rom-low-script-delta-v1/` 的 2 条 claim 与新包**完全重复**，详见 (e)。

### (c) `verify_rom_renderer_records_delta.py` 的 `implementation_inputs` 与仓库实时文件 → **一致** ✅

7/7 逐条 MATCH（§2.6）。两个合同 JSON 的 `public_contract_sha256` 也与 `tools/data/` 实体 MATCH。

**但有一个时序风险**：这三个文件（`tools/verify_rom_renderer_records_delta.py` 等）**同时**被两处钉住：
1. `final/manifest.json` 的 `implementation_inputs`（冻结值，**不能改**）
2. 审计器常量 `RENDERER_RECORDS_DELTA_VERIFIER_SHA256`（新加的）

⇒ **这两个 verifier / exporter / test 文件在本轮之后必须冻结**。任何后续修改都会同时打破 manifest 钉值和审计器常量，需要「改文件 → 重冻 final/ → 重 promote → 刷新审计器常量 → 重建账本」全链重跑。

### (d) promote 依赖 `build/experiments/active/` 存活，而 `build/` 历史上被清理过 → **真实风险** ⚠️

- `build/` **被 `.gitignore` 忽略**（`.gitignore:12`），实测 `git check-ignore` 确认 `build/experiments/active/display-text-delta/tier1-20261001-v1/final/manifest.json` 命中。
- ⇒ 受管 run **不受版本控制保护**，随时可能被 `build/` 清理连带清掉。
- **当前两个 run 都活着**（§2.1）✅
- **缓解**：`notes/evidence/**/final/` 的副本与受管 run **逐字节相同**（§2.3），内容不会丢；但 promote **不能**直接用副本（路径写死在 `build/experiments/active/`）。若 `build/` 被清，**必须重建受管 run**（`init` → 重放 exporter → 重冻 `final/`），不能只拷文件。
- **建议**：promote 之后，`artifacts/rom-renderer-records-delta-v1/` 与 `artifacts/rom-display-text-delta-v1/` 进入版本控制（`artifacts/` **不**在 `.gitignore` 里 —— 确认：`.gitignore` 只有 `build/`，没有 `artifacts/`），从此不再依赖 `build/`。这是本轮 promote 的**主要收益**。
- **顺序要求**：promote 必须在「账本重建」**之前**完成（审计器要读 `artifacts/` 下的新包），而账本重建之前必须等在飞的重活结束（见 (f)）。

### (e) `rom-low-script-delta-v1`（12 B）是否是新包的真子集 → **实测：是；但它是账本孤儿，不会造成重复 claim** ✅

**实测结论**：

| low-script claim | range | bytes | 落在新包哪条 claim 内 |
|---|---|---:|---|
| `low-script-delta-42b5` | `[0x42B5, 0x42BD)` | 8 | `renderer-records-delta-42b5`（**完全相同**） |
| `low-script-delta-42c2` | `[0x42C2, 0x42C6)` | 4 | `renderer-records-delta-42c2`（**完全相同**） |

两条 low-script claim 的 `primary_class` / `claim_kind` 与新包**完全相同**（`fixed_cfg_consumer_renderer_command_script` / `..._bytes`），且区间**逐字节相同**。⇒ **确认为新包的真子集**（12 B ⊂ 1 668 B）。

**但不会造成重复 claim**，因为：
- 活账本里**没有** `rom-low-script-delta-v1` 的任何 claim（实测：`summary` 无该 batch；claims 里无 `promotion_batch == "rom-low-script-delta-v1"`；`notes/line-a-progress-20261019.md:173` 明写「账本引用 0、proof 引用 0」）。
- 它是**孤儿 artifact**：账本引用 0、proof 引用 0、note 自承违反受管发布流程。

⇒ **不要**把 `artifacts/rom-low-script-delta-v1/` 接进审计器。若接，会与新包产生真正的重复 claim，`atomize_claims` 抛 "conflicting primary claims"。

**处置建议**：本轮**不处理**它（清理是独立任务）。但应在 `notes/line-a-progress-20261019.md:173` 与 `:327` 写明「其 12 B 已被 `rom-renderer-records-delta-v1` 逐字节覆盖，不再具备独立入账价值；孤儿 artifact 待独立清理」。

### (f) 额外风险：heavy lock 正在被占用 + 工作树不干净

- **有在飞的受管重活**（实测 `ps`）：PID 36372 `run_guarded.py … tools/audit_rom_byte_coverage.py --root .`（只读模式，无 `--write`），PID 36374 是其子进程，07:42 启动，100% CPU，已消耗 5 min CPU 时间。它持有 `build/resource-guard/heavy.lock`。
  - ⇒ 任何新的受管重活（账本重建 `--write`、formal proof）会得到 **exit 75 / `lock-busy`**（`tools/project_resource_guard.py:716`；实测记录见 `notes/line-a-progress-20261019.md:81-82, 87, 107`）。
  - ⇒ **必须等它自然结束再动 auditor 或账本**。注意：它是 `--root .` 只读审计，**不写账本**，所以它不会和我们抢写；但它会产出「对着**改动前** auditor 的收据」，若我们随后改 auditor + 重建账本，这份收据即失效（需重跑）。
- **工作树不干净**：`git status` 显示 8 个已改文件 + 1 个未跟踪目录，其中包括 `tools/audit_rom_byte_coverage.py`（4 行 PSG pin 刷新）、`sequel/reverse-engineering-proof.json`（1 行 script_sha256）、`tests/test_audit_reverse_engineering_proof.py`（42 行）、`tests/test_audit_reverse_engineering_coverage_count_liveness.py`（+149 行，新增）、`notes/line-a-progress-20261019.md`（+205 行），以及未跟踪的 `notes/evidence/reverse-proof-update-20261020-v2/`。
  - ⇒ 这些是**别人/上一轮的在飞工作**，本轮**不应覆盖或回退**。施工时新增的改动应叠加在其上。
  - ⇒ **不要 `git checkout` / `stash` / `commit`**（本任务已禁止 git 写操作）。
- **磁盘余量**：`notes/line-a-progress-20261019.md` 记录磁盘 96–98% 占用 —— 账本重建会写一个 ~50 MB 的 `sequel/rom-byte-coverage.json`，formal 会写更多收据。**动前先查 `df -h`**。
- **formal proof 本身已「不完整」**：`notes/evidence/reverse-proof-update-20261019-v1/formal-parallel-report.json` 记录 `complete: false`、**175 个既有 blocker**。本轮不修这些，只需保证**不新增** blocker。

### (g) 额外风险：proof 合同与 verifier 报告形状不匹配（已在 §5.1(b) 展开）

两个 renderer verifier 的 report 无 `schema` 键 ⇒ 不能进 proof `verifiers`。若强行加，`_contract()` 校验或第 965 行的逐键比对会失败，**新增 blocker**。

### (h) 额外风险：M1 的 class 撞名（已在 §1.2 展开）

`fixed_consumer_animation_descriptor_group_bytes` 被两族共用，账本 per-class 汇总会合并（1 136 + 640 = 1 776 B）。因 payload 被 exporter/verifier 逐字节钉死，**不可改**。

---

## 7. 动手顺序清单

### 阶段 0 — 可立即并行（纯只读/无副作用）

| # | 步骤 | 并行性 | 验收命令 |
|---|---|---|---|
| 0.1 | 等在飞的 `audit_rom_byte_coverage.py` 结束并确认 lock 释放 | 串行阻塞后续所有重活 | `ps aux \| grep audit_rom_byte_coverage` 空 + `ls -la build/resource-guard/heavy.lock` |
| 0.2 | 确认磁盘余量 | 与 0.1 并行 | `df -h .` |
| 0.3 | 复核三包 verifier 仍通过 | 与 0.1 并行 | `python3 tools/verify_rom_animation_descriptor_pool_v2.py --root . --artifact artifacts/rom-animation-descriptor-pool-v2`（0.2 s）<br>`python3 tools/verify_rom_renderer_records_delta.py --root . --artifact-dir build/experiments/active/renderer-records-delta/combined-tier1-20261001-v1/final`<br>`python3 tools/verify_rom_display_text_delta.py --root . --artifact-dir build/experiments/active/display-text-delta/tier1-20261001-v1/final`（~70 s） |
| 0.4 | 复核 `implementation_inputs` 7 条 SHA 仍 MATCH | 与 0.1 并行 | 复用 §2.6 的比对脚本 |
| 0.5 | 复核 `sequel/reverse-engineering-proof.json` 与 `tools/audit_rom_byte_coverage.py` 当前 SHA 仍是 `1fba1112…` | 与 0.1 并行 | `shasum -a 256 tools/audit_rom_byte_coverage.py` |

### 阶段 1 — promote（**必须串行，且必须在阶段 2 之前**）

| # | 步骤 | 并行性 | 验收命令 |
|---|---|---|---|
| 1.1 | promote 命令脚本包 | 与 1.2 **可并行**（不同 task/run_id/artifact 名，promote 不持 heavy lock） | `python3 tools/experiment_workspace.py promote --root . --task renderer-records-delta --run-id combined-tier1-20261001-v1 --artifact-name rom-renderer-records-delta-v1` → 输出 `{"artifact_path":"artifacts/rom-renderer-records-delta-v1"}`；校验 `ls artifacts/rom-renderer-records-delta-v1/` = 2 个文件，且 `shasum -a 256` 与 §5.1(a) 的 sha 一致 |
| 1.2 | promote 显示文本包 | 与 1.1 并行 | 同上，`--task display-text-delta --run-id tier1-20261001-v1 --artifact-name rom-display-text-delta-v1` |
| 1.3 | 校验 promote 后的 artifact 能通过 verifier | 1.1+1.2 之后 | `python3 tools/verify_rom_renderer_records_delta.py --root . --artifact-dir artifacts/rom-renderer-records-delta-v1` → `verified: true`（注意此时 manifest 里的 `implementation_inputs` 与 live 仍需 MATCH）<br>`python3 tools/verify_rom_display_text_delta.py --root . --artifact-dir artifacts/rom-display-text-delta-v1` → `verified: true` |
| 1.4 | 确认 `notes/evidence/**/final/` **未被改动** | 1.1+1.2 之后 | `git status --porcelain notes/evidence/` 应与阶段 0 一致（`rom-renderer-records-delta-tier1-20261001-v1` / `rom-display-text-delta-tier1-20261001-v1` **不应出现**） |
| 1.5 | 记录 `.experiment.json` 的变化 | 1.1+1.2 之后 | `cat build/experiments/active/*/*/.experiment.json \| grep promoted_to` → 两条 `promoted_to` |

### 阶段 2 — auditor 接线（**纯编辑，串行**）

| # | 步骤 | 并行性 | 验收 |
|---|---|---|---|
| 2.1 | 插入 §3.1 的 26 个常量（33662 之后） | 串行 | `grep -n "RENDERER_RECORDS_DELTA_ARTIFACT\|DISPLAY_TEXT_DELTA_ARTIFACT\|ANIMATION_DESCRIPTOR_POOL_V2_ARTIFACT" tools/audit_rom_byte_coverage.py` |
| 2.2 | 插入 §3.2 的 3 个 claim 函数（35240 之后） | 串行 | `python3 -c "import ast;ast.parse(open('tools/audit_rom_byte_coverage.py').read())"` |
| 2.3 | 插入 3 行 `claims += ...`（36089 之后、36090 之前） | 串行 | 同上；`grep -n "_renderer_records_delta_claims(root, rom, claims)"` |
| 2.4 | 语法 + 导入自检 | 2.1–2.3 后 | `python3 -c "import importlib.util;s=importlib.util.spec_from_file_location('a','tools/audit_rom_byte_coverage.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print('ok')"`（不跑 `main()`） |
| 2.5 | **离线预演**（不跑审计器、不写盘）：用 §4 的 O(n log n) 复算验证新 `claims` 集合无重叠、字节数 = 3 361 | 2.4 后 | 复算输出 `unknown=82728, classified=6208728, claim_count=17028, segment_count=18882`，与 §4.2 一致 |
| 2.6 | 算新的 auditor SHA | 2.4 后 | `shasum -a 256 tools/audit_rom_byte_coverage.py` → 记为 `NEW_AUDIT_SHA` |

### 阶段 3 — 账本重建（**重活，串行，独占 heavy lock**）

| # | 步骤 | 验收命令 |
|---|---|---|
| 3.1 | 重建账本（受管，idle 必须放宽到 ≥7200 s） | `python3 tools/run_guarded.py --summary notes/evidence/<新目录>/ledger-guard.json --lock-file build/resource-guard/heavy.lock --cwd . --wall-timeout-s 9000 --idle-timeout-s 7200 -- python3 tools/audit_rom_byte_coverage.py --root . --write`<br>**验收**：`python3 -c "import json;s=json.load(open('sequel/rom-byte-coverage.json'))['summary'];print(s['unknown_bytes'],s['classified_bytes'],s['claim_count'],s['segment_count'])"` → 必须等于 `82728 6208728 17028 18882`；否则**停止**并回滚 |
| 3.2 | 确认新 claim 落在账本里 | `grep -c "animation-descriptor-pool-45832c\|renderer-records-delta-\|display-text-delta-" sequel/rom-byte-coverage.json` → 115 |

### 阶段 4 — proof 同步（**纯编辑，串行**）

| # | 步骤 | 验收 |
|---|---|---|
| 4.1 | 写 6（或 8）条 `evidence` | `python3 -c "import json;g=json.load(open('sequel/reverse-engineering-proof.json'))['gates']['rom_byte_coverage'];print(len(g['evidence']))"` → 194（或 196） |
| 4.2 | 刷新 `sequel/rom-byte-coverage.json` 的 evidence sha256 | 同 apply.py 第 108–117 行 |
| 4.3 | 追加 M1 的 `verifiers` 条目（**只有 M1**） | 契约逐键能对上 M1 report 的 6 个字段 |
| 4.4 | 刷新 coverage verifier 的 `script_sha256` = `NEW_AUDIT_SHA` | `grep -n "$NEW_AUDIT_SHA" sequel/reverse-engineering-proof.json` |
| 4.5 | 刷新 4 条 `/summary/*` 断言（`/summary/unknown_bytes` 82728、`/summary/classified_bytes` 6208728、`/summary/claim_count` 17028、`/summary/segment_count` 18882） | 逐条对 |
| 4.6 | 刷新 `limitations[0]` + 追加 3 条包级 limitation | `python3 -c "import json;g=json.load(open('sequel/reverse-engineering-proof.json'))['gates']['rom_byte_coverage'];print(g['limitations'][0])"` |
| 4.7 | 刷新 `docs/reverse-engineering-proof-policy.md` 163–165 | `python3 -c "import json;...assert '6,208,728' in policy"` |

> 4.1–4.7 可由**照抄 `notes/evidence/reverse-proof-update-20261019-v1/apply.py` 的三包版**一次完成（该脚本已实现 §5.2 全部 5 步：ledger evidence sha、包 evidence、包 verifier、auditor sha + 全量 `/summary/*`、limitations[0] + 包级 limitation、policy 计数）。**推荐做法**：复制 `apply.py` 到 `notes/evidence/<新目录>/apply.py`，把 `PACKAGE_*` 常量换成三包循环。

### 阶段 5 — 定向测试（**串行，秒级**）

| # | 步骤 | 验收命令 |
|---|---|---|
| 5.1 | 活账本一致性守卫 | `python3 -m pytest tests/test_audit_reverse_engineering_coverage_count_liveness.py -q` → 全绿 |
| 5.2 | proof 套件（定向） | `python3 -m pytest tests/test_audit_reverse_engineering_proof.py -q` → 全绿（或至少无**新增**红） |
| 5.3 | 三包 verifier 回归 | `python3 -m pytest tests/test_rom_renderer_records_delta.py tests/test_rom_display_text_delta.py tests/test_export_rom_animation_descriptor_pool_v2.py -q` |

### 阶段 6 — formal proof（**重活，独占 lock，~40 min**）

| # | 步骤 | 验收命令 |
|---|---|---|
| 6.1 | 受管 formal | `python3 tools/run_guarded.py --summary notes/evidence/<新目录>/formal-guard.json --lock-file build/resource-guard/heavy.lock --cwd . --wall-timeout-s 9000 --idle-timeout-s 7200 -- python3 tools/audit_reverse_engineering_proof.py --root . --execute-verifiers --allow-incomplete --verifier-jobs 4 --output notes/evidence/<新目录>/formal-report.json` |
| 6.2 | 比对 blocker 数量 | `complete: false` 仍可接受，但 **blocker 数 ≤ 175**（不得新增）；重点看 `failed_verifiers` 里**不含**三个新 verifier |
| 6.3 | 确认 coverage gate 数字 | report 里 `gate_results.rom_byte_coverage.rom_coverage_audit.summary` → `unknown_bytes: 82728, claim_count: 17028` |

### 阶段 7 — 文档 / 笔记同步（可与 6 并行）

| # | 步骤 |
|---|---|
| 7.1 | `docs/reverse-engineering-proof-policy.md` 163–165（若 4.7 未做） |
| 7.2 | `docs/sequel-roadmap.md` 末尾追加 2026-10-20 三包入账条目（AGENTS.md 强制） |
| 7.3 | `notes/line-a-progress-20261019.md`：171（M0-c 两包 → 已完成）、173/327（low-script 孤儿 → 写明被新包覆盖）、320-321、690-693、§12.1 追加本轮条目 |
| 7.4 | 新建 `notes/<三包入账>-20261020.md` 记录施工与收据路径（AGENTS.md 要求有意义的发现形成仓库内持久产物） |

### 关键串行约束（不可并行）

1. **阶段 0.1 → 阶段 3/6**：heavy lock 一次只能一个受管重活（exit 75）。
2. **阶段 1 → 阶段 2**：审计器常量指向 `artifacts/`，包必须先 promote 到位。
3. **阶段 2 → 阶段 3**：auditor 改完才能重建账本。
4. **阶段 3 → 阶段 4**：账本重建完才能刷新 proof 的 `/summary/*`（apply.py 读活账本）。
5. **阶段 2.4 → 阶段 4.4**：`NEW_AUDIT_SHA` 必须在 auditor 定稿后算。
6. **阶段 4 → 阶段 6**：proof 改完才能跑 formal。

---

## 附：核心证据索引

| 事实 | 证据位置 |
|---|---|
| `_project_dependency_packet_claims` 契约 | `tools/audit_rom_byte_coverage.py:33852-33900` |
| `_require_current_unknown_ranges` 失败关闭 | `tools/audit_rom_byte_coverage.py:33795-33849` |
| `atomize_claims` 语义 | `tools/audit_rom_byte_coverage.py:7023-7092` |
| 参照实现 A | `tools/audit_rom_byte_coverage.py:35016-35062`（fixed renderer script records） |
| 参照实现 B | `tools/audit_rom_byte_coverage.py:35193-35240`（fixed animation descriptor groups） |
| `build_manifest()` 累加段 | `tools/audit_rom_byte_coverage.py:36020-36090` |
| promote 实现 | `tools/experiment_workspace.py:236-365`（校验 236-304 / promote 307-365） |
| promote CLI | `tools/experiment_workspace.py:493-496, 510-518` |
| proof 合同校验 | `tools/audit_reverse_engineering_proof.py:247-265`（`_contract`）、`965-972`（逐键比对） |
| proof 同步模板 | `notes/evidence/reverse-proof-update-20261019-v1/apply.py`（尤其 182-234） |
| policy 计数锚点 | `docs/reverse-engineering-proof-policy.md:163-165` |
| 活账本一致性守卫 | `tests/test_audit_reverse_engineering_coverage_count_liveness.py` |
| M1 不可改 class 的根因 | `tools/verify_rom_animation_descriptor_pool_v2.py:653`（`payload_raw != _canonical(rebuilt)`） |
| 在飞重活 | `ps`: PID 36372/36374，`notes/evidence/reverse-proof-update-20261020-v2/run_formal_para
</task_output>