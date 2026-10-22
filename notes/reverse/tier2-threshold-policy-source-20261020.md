# Tier-2 批量里程碑门槛：政策原文、历史先例与口径分歧

> 产出：2026-10-20 09:3x，基线 `codex/reverse-engineering` @ `c05a26a2`。
> 方法：只读侦察（grep / git log / 读文件 / 读账本 JSON），**未跑任何长跑命令**，
> **未修改任何文件**。所有引用都带 `path:line`，可直接核验。

本文件的作用是**把门槛的原文固化下来**，避免每次讨论都退化成转述。
§6 末尾列出了我们自己的笔记与原文不一致的地方 —— 那几处是本文件最有价值的部分。

---

## 1. 门槛原文（三处权威文本，措辞不等价）

### 1.1 根 `AGENTS.md:35-39`（数值最明确）

> 相邻且信任边界相同的低风险 packet 必须先批量积累。满足以下任一条件才触发二级
> 里程碑审计：累计净增至少 10 KiB；预计完成度提升至少 0.15 个百分点；同类待接入
> packet 达到 4 个。二级审计统一执行
> coverage TDD、一次 canonical coverage rebuild、proof spec 同步、相关集成测试和一份
> 非降级 formal proof，不得为批内每个 packet 重复执行全量审计。

### 1.2 `AGENTS.md:40-43`（不满足时怎么办）

> 不满足二级门槛时，packet 保持在唯一实验目录并记录 canonical 候选、验证 receipt、
> 预计净增和非声明项；不得为了让整数百分比变化而放宽 owner、合并异构证据或提前写
> canonical coverage。审计器或规范变化先由定向 TDD/集成测试失败关闭，formal 统一留到
> 下一次二级里程碑或发布验收，不为单个变化临时扩张审计频率。

### 1.3 `AGENTS.md:50-54`（禁止算术外推）

> 二级里程碑不得用"旧 canonical + 各 packet 预计收益"的算术外推冒充集成验收。
> 必须至少有一条真实 canonical 集成测试，从落盘 coverage 重建每个 batch 的精确
> claim/byte 分母、跨包无重叠、保留 unknown gap 与 CFG aggregate，并绑定对应 guard
> receipt。

### 1.4 `docs/reverse-engineering-proof-policy.md:86-96`

> 1. **Packet 快速审计**：每个 packet 必须有先失败后通过的测试、独立 raw-input
>    verifier、固定 ROM/上游 artifact/输出身份、完整分母与非声明项，并覆盖边界、顺序、
>    重叠、current-unknown 投影和代表性单字节变异。通过后产物只能进入待接入队列；其
>    coverage 数量和完成百分比仍是 projection，不是 canonical 事实。
> 2. **批量里程碑审计**：同一信任边界的 packet 合计净增达到 10 KiB、预计完成度提升
>    达到 0.15 个百分点或累计 4 个时，统一完成 coverage
>    TDD、一次 canonical rebuild、proof spec 更新、相关集成测试和一次非降级 formal
>    proof。批内 packet 不得逐个重复全量 coverage/formal。

同文件 `:101-104`：

> Tier-2 必须从真实落盘 canonical 重建各 packet 的精确 claim/byte 分母、跨包无重叠、
> 保留 unknown gap 与 CFG aggregate；旧 canonical 加预计收益的算术外推只能作 Tier-1
> projection，不能作为里程碑验收。

### 1.5 `docs/remaining-reverse-work-plan-20261001.md:300-302`（唯一给了 pp→字节换算的文本）

> 5. 同信任边界达到4包、10KiB或0.15个百分点任一条件才Tier-2。0.15个百分点对本ROM
>    约9,438B；只计算去重净增。晋升前固定immutable precoverage、双重稳定报告，再统一
>    canonical/proof与一份formal。不得把P1/P3/P4异构证据硬拼以凑4包。

### 1.6 `docs/sequel-roadmap.md:3952`（三选一复述）

> 后续只在 4 packets、10 KiB 或 0.15pp 任一门槛触发 Tier-2；最终全量
> 审计只在 `unknown_bytes==0` 或 release 运行。

---

## 2. 判定主体：**文档约定，没有代码硬闸门**

| 检查 | 结果 |
|---|---|
| `grep -rn "10_240\|10240\|0\.15\|10 KiB\|10KiB" tools/` | **0 命中** |
| `grep -rn "10240\|10_240\|0\.15\b" tests/` | **0 命中** |
| `sequel/reverse-engineering-proof.json` 顶层键 | `schema, claim_status, base_rom, bank_proofs, policy, gates, trust_model` —— **无 threshold / milestone 键**；`policy` 的 9 个键也不含门槛 |
| `tools/audit_reverse_engineering_proof.py:145-149` | 只在注释里引用一份收据路径作耗时锚点，**无判定** |
| `tools/audit_rom_byte_coverage.py:7851, 8379, 8749, 9638, 9716, 9950 …` | `"promotion_batch": "cfg-v3-one-generation"` 等 —— 是**账本标签**，不是门槛闸门 |

**后果是硬的，但靠流程纪律而非机器强制**：`AGENTS.md:40-43` 明文禁止门槛未满足时
"提前写 canonical coverage"，`policy:101-104` 禁止用算术外推冒充验收。

⇒ **裁决结果无法靠改一个常量生效**，必须落进 `AGENTS.md` /
`docs/reverse-engineering-proof-policy.md` / `notes/`，由后续执行者遵守。

---

## 3.「同类 / 信任边界」的定义：仓库里没有

| 检查 | 结果 |
|---|---|
| `grep -rn "trust_boundary\|trust boundary\|信任边界" tools/` | **0 命中** |
| `sequel/reverse-engineering-proof.json` 的 `trust_model` | 只有 `local_audit_scope` / `external_authenticity_requirement` / `current_external_attestation`（值 `missing`）—— 与边界分类无关 |

**三处措辞互不等价**：

| 出处 | 措辞 | 覆盖范围 |
|---|---|---|
| `policy:90` | 「**同一信任边界**的 packet … 累计 4 个」 | 同一句同时限定三个门槛 |
| `AGENTS.md:36` | 「**同类待接入** packet 达到 4 个」 | 4-包计数用「同类」，**不是**「同信任边界」 |
| `remaining-reverse-work-plan:300` | 「**同信任边界**达到4包、10KiB或0.15个百分点」 | 三者统一用「同信任边界」 |

**唯一可操作的账本维度有两个，且不等价**：

- `primary_class` —— 逐 claim 字段（`sequel/rom-byte-coverage.json` 的 `claims[].primary_class`）
- `promotion_batch` —— 批标签（`claims[].promotion_batch`）

文字上的"信任边界"实例化只有生命周期/依赖域一种说法
（`remaining-reverse-work-plan:294`：「AI与协程是不同生命周期信任边界」），
**不可判定**。

---

## 4. 历史先例

### 4.1 通过的

| 日期 | 内容 | 走的门槛 | 出处 |
|---|---|---|---|
| 2026-08-31 / 09-01 | 首个**同信任边界**批次：v2 / proven-roots v6 / v1 consumed literal，净增 6,796 + 2,980 + 1,396 = **11,172 B** / 946 claims | **10 KiB** | `docs/sequel-roadmap.md:3718-3720` |
| 2026-09-01 | 四包 **7,140 B** / 116 claims（event-handler CFG 4,062 + sprite-component source 2,096 + Thumb 指令 778 + literal 204）—— **跨 primary_class** | **4-packet 计数** | `sequel/reverse-engineering-proof.json:4966` |
| 2026-09-02 | 四包 gross 8,083 B / 395 claims → **净增 4,738 B / 67 claims / 0.0753 pp** —— 分别是 battle-condition result text 3,961 + alternate dialogue 3,200 + story-state callback CFG 702 + callback entry C4CC 220，**明显跨 primary_class** | **4-packet 计数** | `docs/sequel-roadmap.md:3860-3862`、`:3895-3897` |
| 2026-09-04 | 四包 **4,862 B** / 61 claims | 4-packet 计数 | `sequel/reverse-engineering-proof.json:4964` |
| 2026-09-05 ×3 | 四包 **4,382 B** / 77 claims；四包 **4,231 B** / 141 claims；四包 **978 B** / 21 claims | 4-packet 计数 | `sequel/reverse-engineering-proof.json:4962`、`:4963`、`:4961` |
| 2026-09-30 | 四包 10 / 54 / 14 / 40 B = **118 B** / 21 claims —— **纯靠计数过闸**，比 10 KiB 低两个数量级 | 4-packet 计数 | `notes/rom-small-cfg-dependency-tier2-20260930.md:16`、`docs/sequel-roadmap.md:231-233` |

### 4.2 没通过的

| 日期 | 内容 | 差在哪 | 出处 |
|---|---|---|---|
| 2026-08-12 | 1 包 3,961 B | 1 包，远低于 10 KiB | `docs/reverse-engineering-handoff-20260812.md:1937-1941` |
| 2026-09-02 | 1 包 54 B / 0.000858 pp | 1 包 | `docs/sequel-roadmap.md:3873-3874` |
| 2026-09-02 | 2 包 7,161 B / **+0.1138 pp** | 0.1138 < 0.15 pp | `docs/sequel-roadmap.md:3856-3858` |
| 2026-09-05 | 3 包 862 B / 18 claims | 只有 3 包 | `docs/sequel-roadmap.md:4011-4013` |
| **2026-10-01** | **新显示文本 1 包 + 旧命令脚本 1 包 = 2,721 B** | **「分开…未达同类/净增门槛，不做Tier-2」** | `docs/sequel-roadmap.md:153-154`、`docs/reverse-engineering-handoff-current-20260905.md:153-154` |
| 2026-10-01 | 低地址脚本增量 1 包 / 12 B / 2 claims | 1 包 | `docs/sequel-roadmap.md:220-221` |

### 4.3 禁止性条款（"明禁"的原文出处集合）

| 原文 | path:line |
|---|---|
| 「不得为了让整数百分比变化而放宽 owner、**合并异构证据**或提前写 canonical coverage」 | `AGENTS.md:41` |
| 「**不得把P1/P3/P4异构证据硬拼以凑4包**」 | `docs/remaining-reverse-work-plan-20261001.md:302` |
| 「不能把**不同信任边界合并凑审计次数**」 | `notes/rom-release-gate-work-plan-20261001.md:95` |
| 「不能为了**凑包数拆开相邻同信任边界记录**，也不能重复审计本包代替新逆向证据」 | `notes/rom-renderer-records-delta-tier1-20261001.md:88-89` |
| 「新显示文本1包与旧命令脚本1包**分开**…未达同类/净增门槛」 | `docs/sequel-roadmap.md:153-154` |

---

## 5. 当前这批待接入 packet 的准确账（直接读账本实测）

`sequel/rom-byte-coverage.json`（SHA `9f8a8196…`，claim 16,913）里实测：

| `primary_class` | 账本现状 | `promotion_batch` | 待接入部分 |
|---|---|---|---|
| `fixed_cfg_consumer_renderer_command_script` | **31 claims / 2,666 B** | `rom-fixed-renderer-script-records-v1` + `rom-renderer-script-pointer-pool-records-v1` | 新包 1,668 B（未入账） |
| `fixed_cfg_consumer_renderer_display_text` | **不存在（0 claims）** | — | 1,053 B（未入账） |
| `fixed_consumer_animation_descriptor_group_bytes` | **1 claim / 1,136 B** | `rom-fixed-animation-descriptor-groups-v1` | M1 640 B（未入账，接入后并为 1,776 B） |

⇒ **待接入 = 3 个包 / 3,361 B / 3 个不同 `primary_class` 各 1 个**
⇒ 0.15 pp 换算：ROM accounted = 6,291,456 B，**0.15 pp = 9,437.2 B**；
10 KiB = 10,240 B ⇒ **有效字节门槛 = min = 9,437 B**（比 10 KiB 低 803 B）
⇒ 3,361 B = **0.0534 pp**

**三个门槛全不满足**（两种「同类」口径下都是）：

| 口径 | 计数 | < 4 |
|---|---|---|
| 按 `AGENTS.md:36` 字面「同类**待接入**」 | 命令脚本 1 + 显示文本 1 + 动画 1 = **3** | ✅ 不满足 |
| 按类内全部 packet（含已入账） | 命令脚本 3 + 动画 2 + 显示文本 1 = 6 个 packet，但**仍只覆盖 3 个 class** | 三个 class 仍各 < 4 |

**为什么没有现成的「第 4 个」**：`artifacts/rom-low-script-delta-v1`（12 B）是命令脚本包
1,668 B 的**逐字节真子集**（`low-script-delta-42b5` = `renderer-records-delta-42b5`，
`low-script-delta-42c2` = `renderer-records-delta-42c2`），
是**账本孤儿**（账本引用 0、proof 引用 0）。
接进审计器会让 `atomize_claims` 抛 `conflicting primary claims` ⇒ **绝不能接**。

---

## 6. 我们自己笔记里与原文不一致的地方（本文件最有价值的部分）

| # | 我们的转述 | 原文/实测 | 严重度 |
|---|---|---|---|
| E1 | 「晋升一个新 packet 的**硬闸门**」 | 原文没有"晋升"受门控的动作。Tier-1 通过的 packet **已经**可以进待接入队列（`policy:88-89`）。原文是「**才触发二级里程碑审计**」——是**批次**进 canonical，不是 packet 被卡住 | 概念性 |
| E2 | 字节门槛「≥10 KiB」 | **有效门槛是 9,437 B**（0.15 pp 换算），比 10 KiB **低 803 B**。写「10 KiB」会高估门槛 | 数值 |
| E3 | 未提「只计算**去重净增**」 | `remaining-reverse-work-plan:301` 明写。pp 门槛是「**预计**完成度提升」，只用于**触发**；验收必须靠真实 canonical 重建 | 遗漏 |
| E4 | 用「类」这个自造词 | 原文用「同一信任边界」/「同信任边界」/「同类待接入」三种措辞，**互不等价**；`tools/` 与 proof JSON 都没有定义 | 概念性 |
| E5 | 漏掉两个前置限定词 | `AGENTS.md:35` 有「**相邻**且信任边界相同的**低风险**」；`policy:90` **没有**这两个词 ⇒ 两份权威文本不一致。且「相邻」在仓库中**从未定义**。三个包地址跨度上互不"相邻"（M1 `[0x458564,0x45879C]`；命令脚本 29 段跨 `0x0BCD–0x542E`；显示文本 85 段跨 `0x12EE4C–0x463B16`） | 遗漏 + 文本冲突 |
| **E6** | 三个互相矛盾的字节数 | 我们笔记里同时存在 **3,361 B**（§20.1）、**4,334 B**（§18.5 ③ 行）、**4,903 B**（对话里）三个数。实测：**待接入 = 3,361 B**；4,334 B 是**命令脚本类全体**（1,668 + 1,542 + 1,124）；4,903 B 是**算错**（只加了 pointer-pool 却点名 fixed-renderer） | **必须更正** |
| E7 | 「政策明禁合计」 | 仓库里**没有**这六个字。原文是 §4.3 那五条不同措辞的禁令。我们的笔记把它写成结论句却没给出处 | 转述冒充原文 |
| E8 | 把禁令当统一强度 | 明禁的是：合并**异构证据**、硬拼**凑4包**、合并不同信任边界**凑审计次数**。而 `policy:90` 的「同一信任边界」限定整句三门槛，`AGENTS.md:36` 的 4-包计数用「同类待接入」——**是否仍受信任边界约束没有原文裁决**。**历史先例（§4.1 的 09-01、09-02 两批）明确跨 primary_class 放行** ⇒ 实践中"同类"被解释得**很宽** | 强度分层 |
| E9 | 把已入账包算进「待接入」 | `AGENTS.md:36` 字面是「同类**待接入** packet 达到 4 个」。pointer-pool（1,542 B）与 fixed-renderer（1,124 B）**已在账本里**（§5 实测）⇒ 按字面命令脚本类待接入 = **1** 个，不是 3 个 | **需裁决** |
| E10 | 把 M1 当新类 | M1 的 `primary_class` 与既有 `rom-fixed-animation-descriptor-groups-v1` **完全同名**，按 class 汇总时 1,136 + 640 = **1,776 B** 合并，且该值被 exporter/verifier **逐字节钉死**、改不了 ⇒ M1 是**向既有类追加**，不是"第 2 个同类待接入包" | 计数错误 |
| E11 | 说「门槛本身未定义」 | 三个数值在 `AGENTS.md:36` 与 `policy:90-93` 里是**明确的**。待裁的是**是否放宽口径**，不是数值 | 误述 |
| E12 | 指望找现成第 4 包 | 最像的 12 B 孤儿包已被明确否决（§5 末）。要凑第 4 包必须**新做逆向证据** | 前提错误 |
| E13 | 指望按原文判定「同信任边界」 | 仓库**没有**信任边界归属的原文，三个包也没有 ⇒ **不可判定**，任何结论只能标为推断 | 前提错误 |

---

## 7. 需要用户裁决的三点（仓库里找不到原文）

1. **「同类」按哪个维度判定** —— `primary_class`？`promotion_batch`？文字上的「生命周期
   信任边界」？（§3：三者不等价，且都无正式定义）
2. **「同类」取窄义还是宽义** —— `AGENTS.md:36` 的「同类待接入」（窄，单一批次内同边界）
   还是 `policy:90` 的「同一信任边界」+ 历史先例（宽，允许跨类凑批）。
   **历史先例 09-01 / 09-02 两批走的是宽义且已生效。**
3. **「待接入」是否排除已入账包** —— `AGENTS.md:36` 字面排除；我们笔记 §18.5 ③ 行的算法
   却把已入账的 pointer-pool / fixed-renderer 算进去了（E9）。

裁决后应回写 `AGENTS.md:35-43` 与 `docs/reverse-engineering-proof-policy.md:90-93`
（两处措辞需一并对齐「相邻 / 低风险」差异，见 E5）。

---

## 8. 两条有原文支撑的合法出路

1. **补第 4 个同类/同信任边界的待接入 packet** ⇒ 触 4-packet 门槛。
   先例：118 B 四包（2026-09-30）证明可行且成本低。
   但必须**新做逆向证据**：不能拆包（`rom-renderer-records-delta-tier1:88-89`）、
   不能用 12 B 孤儿包、且需满足 `AGENTS.md:35` 的「相邻 + 低风险」。
2. **补到 9,437 B 去重净增** ⇒ 触 pp 门槛（比 10 KiB 低 803 B）。
