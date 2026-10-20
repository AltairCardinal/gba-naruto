# 甲线四道口径裁决（2026-10-20 11:58–13:2x）：落地口径与两条证据更正

本文件记录用户对四道待裁决项的**逐条选择**、执行口径，以及两条**由实测推翻的既有结论**。
配套施工与收据见 `notes/evidence/reverse-proof-update-20261020-v3/`。

---

## 0. 四道裁决的逐条落点

| # | 事项 | 用户的选择 | 本轮执行口径 |
|---|---|---|---|
| ① | **Tier-2 门槛** | **授权例外**：按现有 3,361 B 触发一次二级里程碑（一次 coverage rebuild + 一次 formal ≈ 65 min），并在 notes 与 AGENTS.md 记明「门槛例外 + 理由」 | 阶段 0–7 全流程照 `notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md` 执行；例外与理由记入本文件 + `AGENTS.md` 登记表 + `docs/sequel-roadmap.md` |
| ② | **D0 字段穷尽** | **方案 B：每条记录都要运行时因果证据 → 79 次采集** | 闸门代码**不改**（`tools/audit_reverse_engineering_proof.py:648-679` 三条判据原样保留，`claim_status` 保持 `incomplete`）。工作从「让 79 条记录各自拿到运行时因果证据」开始，见 §3 |
| ③ | **psg 修复路线** | **连 legacy 验证器 + 导出器一起修，artifact 重新落地** | 见 §4 的具体设计（关键：**不能再用冻结账本 SHA 做身份**，必须换成链时语义门） |
| ④ | **purelib 加固** | **加固 workaround：改这 2 个脚本，补所有候选 purelib（系统 + venv）** | 见 §2：口径不变（保住 `-I -S` 的最大隔离性），但**前提被实测推翻**，落地方式按 §2.2 调整 |

---

## 1. ① Tier-2 例外：门槛数值与例外理由（留痕）

### 1.1 三道门槛的实测值 vs 要求

| 门槛 | 要求 | 实测（待接入 3 包） | 是否满足 |
|---|---|---|---|
| 有效字节 | ≥ 10 KiB（= 0.15 pp 对本 ROM 的 9,437 B，见 `notes/tier2-threshold-policy-source-20261020.md`） | **3,361 B** | ✗ |
| 完成度提升 | ≥ 0.15 pp | **0.0534 pp** | ✗ |
| 同类待接入 | ≥ 4 个 | **3 个**（且分属 3 个不同 `primary_class`，各 1 个） | ✗ |

即便把**已入账**的同族 pointer-pool 1,542 B 与 fixed-renderer 1,124 B 也算进来，
也只有 3 个 packet / 4,903 B / 0.0779 pp，仍全不满足。

### 1.2 例外理由（必须与本文件一起被引用）

1. **三包不是凑数**：3,361 B 全部来自已提交、已由独立 verifier 逐字节重建的
   accepted artifact（`rom-animation-descriptor-pool-v2` 640 B、
   `rom-renderer-records-delta-v1` 1,668 B、`rom-display-text-delta-v1` 1,053 B）；
   它们的 `scope` 里**自然可达性、调用方分母、编辑/重定位安全**等一律为 `false`，
   晋升只认「静态闭包 + current-unknown 门」，**没有**借晋升放水。
2. **例外只针对门槛，不针对判据**：`/summary/*` 四元组照常刷新、
   `limitations[0]` 照常重算、每个包级 limitation 照常追加、
   22 个 runtime bank 的 132 条 blocker **一条不减**。
3. **可回溯**：本条 + `AGENTS.md` 登记表 + `docs/sequel-roadmap.md` 三处留痕，
   任何一次 formal 收据都能反查到「这批是门槛例外晋升的」。
4. **不产生政策先例**：本次是**一次性例外**，不修改门槛数值本身；
   后续批次仍按原三道门槛判定。

---

## 2. ④ purelib：口径不变，但**前提被实测推翻**

### 2.1 被推翻的前提（子代理实测，证据可复现）

用户选项的前提是「第一轮 formal 的 176 blockers 是解释器 purelib 漂移」。
**实测不成立**：

| 事实 | 证据 |
|---|---|
| 第二轮 formal 的 blockers 是 **175**，不是 176 | `notes/evidence/reverse-proof-update-20261020-v2/formal-parallel-report.json` |
| 175 条里 **0 条**提到 PIL / purelib / ImportError | 同上，逐条扫描 |
| **108 个 verifier 全部 `contract_ok: true`**，36 条 `-I -S` 命令 **36/36 exit 0** | 同上 |
| 第 176 条 blocker 的真因是**审计器自己的解释器**被换成了 venv | `notes/evidence/reverse-proof-update-20261019-v1/first-run-venv-interpreter/formal-parallel-report.json:787` |
| 机制在 `tools/audit_reverse_engineering_proof.py:470`：spec 里的 `"python3"` 被替换成 `sys.executable` ⇒ **子验证器用的解释器 = 审计器的解释器** | 源码 |
| `tools/verify_rom_sprite_loader_tail.py:194-196` **自己**会把 `sysconfig.get_path("purelib")` 补回 `sys.path` ⇒ `-S` 拦不住它 | 源码 + 实跑（系统解释器下 `-I -S` 也能 `verified: true`） |

⇒ **`-S` 与那条失败无因果关系**；v1 的 176 是**启动层事故**
（`run_formal_parallel.sh` 后来固定了 `PATH=/usr/local/bin:…$PATH` 才修好）。

### 2.2 因此的落地口径（口径不变：保住 `-I -S` 最大隔离性）

用户选的是「加固 workaround」，**不**是「删 `-S`」。这一点反而是对的：
删 `-S` 会踩 `tools/audit_reverse_engineering_proof.py:430-441` 的 flag 白名单
（只接受 `["-I","-S"]` 或无 flag），实测会**新增 1 条 blocker**
（`verifier uses unsupported python flags: -I`，175→176，`hash_bound` 97→96），
并且还要连带改 `tools/verify_legacy_artifact_acceptance.py:128` 的偏移解析。
⇒ 「零脚本删 `-S`」这条路**已被实测证伪**，本轮不走。

**加固的落点**（`-I -S` 保持不变，只把 purelib 候选补全）：

| 脚本 | 改法 | SHA 连锁 |
|---|---|---|
| `tools/verify_rom_sprite_loader_tail.py` | 加载 source verifier 前，把**所有候选 purelib**（当前解释器 + 系统 + venv）依次补进 `sys.path` | 审计器 `:33054` 硬钉它 ⇒ 审计器要更新 pin ⇒ 审计器 SHA ⇒ spec |
| `tools/export_rom_sprite_loader_tail.py` | 同上（导出器也动态加载 source verifier） | artifact `implementation.exporter_sha256` ⇒ **artifact 重新落地** ⇒ spec evidence |

**验收口径**（两条都要实测）：

```
$ /usr/local/bin/python3 -I -S tools/verify_rom_sprite_loader_tail.py --root . \
    --artifact-dir artifacts/rom-sprite-loader-tail-v1
  ⇒ {"verified": true, ...} exit=0
$ .venv/bin/python3 -I -S tools/verify_rom_sprite_loader_tail.py --root . \
    --artifact-dir artifacts/rom-sprite-loader-tail-v1
  ⇒ 也必须 exit=0（加固前是 ModuleNotFoundError: No module named 'PIL' exit=1）
```

### 2.3 必须更正的原结论

`notes/line-a-progress-20261019.md` §25.1 断言「存在一条零脚本改动的更优路径
（改 spec 删 `-S`）」——**该结论被本节实测推翻**（删 `-S` 新增 blocker + 需连带改 2 处）。
按仓库规则「逆向结论变化时更新原记录」，§25.1 已更正。

---

## 3. ② D0 方案 B：79 次运行时采集

### 3.1 口径

- 闸门**不改**：`tools/audit_reverse_engineering_proof.py:648-679` 的三条判据
  （`status == "exhaustive"` / `record_ids_total == record_ids_covered == 冻结分母` /
  存在哈希绑定 record+field+bank+evidence 四组 ID 的 verifier 合同）**原样保留**。
- `claim_status` 保持 `"incomplete"`；`docs/reverse-engineering-proof-policy.md` 第 5 条
  （每个有效 bank 按记录 ID 和字段 ID 穷尽覆盖）**一字不改**。
- 22 个 runtime bank 的 132 条 blocker **一条不减**。

⇒ 与「中间方案」相反：这里**不**新增 `coverage_class` 轴、
**不**放宽任何判据、**不**动 `sequel/bank-proofs.json` 的 `evidence_policy` 文案。
**唯一**变的是**证据**：每个字段的每个单元都要有运行时因果证据。

### 3.2 pilot 的权威分母（data-table-b，79 记录 × 1 字段 `text_ptr` = 79 cells）

| 项 | 值 | 来源 |
|---|---|---|
| 记录 ID | `"0"` … `"78"` | `sequel/content/data-table-b/bank.json` 的 `entries`（79 条，每条含 `_index` / `_raw_offset` / `text_ptr`） |
| 表位置 | `0x5A2034`，步长 4 B | 同上（`text_ptr` 为 u32，offset 0） |
| 字段 ID | `["text_ptr"]` | `entry_format.fields` |
| 单元总数 | 79 | 79 记录 × 1 字段 |
| 字节层 | **已 100% 闭合**（文本 blob 2,740 B + 指针表 316 B，unknown 0） | 活账本实测 |

### 3.3 方案 B 的第一步（可立即开工的三件事）

1. **修红**：pilot 工具 `tools/verify_data_table_b_partial_bank.py` **今天是红的**
   （`input identity mismatch: tools/project_resource_guard.py`）——
   合同 v1 钉的 `tools/project_resource_guard.py` = `17ca1354…`，实际 = `60bc5987…`
   （该文件在 `6b53e5ce` 把 idle 60→7200 / wall 600→9000 时改过，晚于合同冻结）。
   修法按 policy「输入漂移先失败关闭、以新版本和新收据恢复」：
   发 `tools/data/data-table-b-partial-bank-contract-v2.json`，**保留 v1 不动**。
2. **把 79 条记录的自然可达性做成可枚举的路由表**：
   79 个 message ID ↔ 79 个特效 descriptor **一对一**
   ⇒ 需要 **79 次**运行时采集；现有探针
   `tools/build_battle_message_runtime_probe.py:31-54` 是**单槽 scratch，一次 run 只出一条 ID**
   ⇒ 要扩成多槽/批量，否则 79 次采集的成本（emulator 实测仅 16.7 min，但**路由发现**才是大头）
   会被单槽设计放大。
3. **成本要量出来**：emulator 侧实测 16.7 min（baseline 6.357 s + candidate 6.335 s），
   但**路由发现**才是 24–40 工作日量级（类比 battle-effect 18 组 / 8 天）。
   ⇒ 第一件可交付的收据应是「**1 条记录**（记录 0，已有时序/像素 A/B）的完整采集 + 差分验收」，
   用来把「79 次」的真实成本从「数周」压成可排期数字。

### 3.4 与「中间方案」的关系（留档，不是本轮执行）

子代理已把「中间方案」的最小改动面算清（`coverage_class` 轴 + 三分支判据 + 9 处测试断言 +
先接 map-sprites），**本轮不执行**（用户选的是方案 B）。它保留为
「若 79 次采集的实测成本超过可承受范围时的回退路径」的现成施工图。

---

## 4. ③ psg：连 legacy 验证器 + 导出器一起修（设计已定，待执行）

### 4.1 三层因果（用户诊断，本轮复核确认）

| # | 因果 | 复核 |
|---|---|---|
| ① | 冻结基线摘要 `922e06e9…` 在全仓 37,542 个文件里**没有副本**（晋升前账本快照从未保存） | 确认：`tools/export_rom_psg_frequency_lookup.py:28` 硬编码 `COVERAGE_SHA256 = "922e06e9…"`，`:651-654` 的 `_coverage_baseline` 拿活账本比这个 SHA ⇒ 必抛 `coverage baseline identity changed` |
| ② | 那 226 B 早已是 psg 自己的 5 条 claim ⇒「现在必须 unknown」被本包自己的晋升推翻了 | 确认：导出器 `:646-647` 要求 `unknown_bytes == 226` 且 `primary_overlap_bytes == 0`，而活账本里这 226 B 已归 psg 自己 |
| ③ | legacy 验证器只认冻结前后状态；活账本归 bundle 包装器 + auditor | 确认：formal 实际跑的是 `tools/verify_rom_psg_frequency_lookup_bundle.py`（0.48 s，绿）；坏的是 legacy 活账本路径 + 导出器 |

### 4.2 关键设计决定：**不能再用「整个账本的 SHA」做身份**

`922e06e9…` 这类**字节身份**在账本每晋升一次就失效一次 ⇒ 任何以它为键的合同
都会在下一批晋升时再次变红。而**晋升前快照已不可重建**（账本已从 16,891 claims 走到 16,913，
且再过一轮就是 17,028）。

⇒ **改成链时语义身份**（与本轮在测试侧用的同一套模式）：

| 项 | 改法 |
|---|---|
| 导出器 `tools/export_rom_psg_frequency_lookup.py` | `_coverage_baseline` 读**活账本** → **剔掉本包自己的 claims**（`promotion_batch == "rom-psg-frequency-lookup-v1"`）→ 在该投影上断言 226 B 仍为 unknown 且不与任何其它 primary claim 重叠 → 把**活账本 SHA 记作 provenance**（冻结进 artifact，不再当 pin 用） |
| legacy 验证器 `tools/verify_rom_psg_frequency_lookup.py` | 活账本路径同样改成「剔掉本包自己的 claims 后再判 current-unknown」 |
| artifact | 重新落地 ⇒ `manifest.json` 的 `implementation.exporter_sha256` / `verifier_sha256` 变 ⇒ spec 的 evidence sha 变 ⇒ 一次 formal |

**稳定性论证**：新语义只依赖「这 226 B 在**剔掉本包自己**之后仍是 unknown」这一**属性**，
不依赖账本的整体字节身份 ⇒ 后续任何一批晋升**不会**再次让 psg 变红
（除非别的包也认领这 226 B，那时它会**正确地**报错）。

### 4.3 执行时必须同步的位置

| 位置 | 为什么 |
|---|---|
| `sequel/reverse-engineering-proof.json` 的 psg artifact evidence sha | artifact 重新落地 |
| psg legacy verifier 的 `script_sha256`（若在 spec 的 verifiers 里） | 验证器源码改 |
| `tools/audit_rom_byte_coverage.py` 的 psg verifier pin | 审计器硬钉验证器 SHA ⇒ 审计器 SHA 变 ⇒ spec |

---

## 5. 收据与产物路径

| 产物 | 路径 |
|---|---|
| 三包接入的施工单（只读侦察产出） | `notes/evidence/reverse-proof-update-20261020-v2/三包接入施工单-raw.md` |
| 三包的离线预演（无重叠 + 四元组复算） | `notes/evidence/reverse-proof-update-20261020-v3/preflight_three_promotions_20261020.py` |
| 三包的 proof 同步脚本（幂等 + 失败关闭） | `notes/evidence/reverse-proof-update-20261020-v3/apply.py` |
| 账本重建收据 | `notes/evidence/reverse-proof-update-20261020-v3/ledger-guard.json` |
| formal 收据 | `notes/evidence/reverse-proof-update-20261020-v3/formal-guard.json` + `formal-report.json` |
| 根因定量收据（90/90 生产者拒绝拿最终账本重放） | `notes/evidence/reverse-proof-update-20261020-v2/full-ledger-replay-20261020.json` |
