# Butano 重制版：已有成果盘点 + 逆向成果「应当被使用但未使用」的比例（2026-10-23）

**触发**：用户要求「整理项目对 butano 重制版的已有成果，以及已完成的逆向成果应当被
butano 重制版使用但未使用的比例」。

**一句话答案**：
> **物料层面（可导入的逆向成果）已经清零——严格口径 0 / 201 = 0%。**
> **欠账全在结论层：332 / 436 = 76.1% 的已闭合逆向结论还没有变成 Butano 侧的行为门禁**
> （对「已判定」的 361 条算是 92.0%）。

**机器收据**：`artifacts/butano-utilization-audit-v1/utilization.{json,md}`
**复算脚本**：`tools/butano_reverse_utilization_audit.py`（本仓 master 线）
**数据来源**：Butano 线三份既有收据（不改、不重算）：
`artifacts/butano-reverse-gap-v1/gap.json`、
`artifacts/butano-usable-backlog-v1/backlog.json`、
`artifacts/butano-wiring-coverage-v1/wiring.json`、
`artifacts/reverse-notes-index-v1/notes-index.json`。

**口径锚点**：逆向提交 `821d0937`（dirty=false）· ROM SHA-256 `1198ece7…5d05b` ·
三份收据生成于 2026-10-23T09:12–09:13Z。

---

## 0. 先说清楚：三条线、三棵树

| 树 | 路径 | 分支 | 角色 |
|---|---|---|---|
| 决策线 | `D:\Github\gba-naruto`（= `D:\Shell\Github\gba-naruto`，junction） | `master` | 规划 / 决策 / 本审计 |
| 重制线 | `D:\Github\gba-naruto-butano` | `codex/butano-foundation-research` | **Butano 重制版本体** |
| 逆向线 | `D:\Github\gba-naruto-reverse` | `codex/reverse-engineering` | 逆向成果真源（264 成果族 + 436 笔记） |

三者**刻意不合并**（`notes/windows-migration-20261020.md` §1.2）。
⇒ 「被使用没有」这个问题**只能在重制线里量**，本审计因此去读重制线的收据，
而不是把逆向树搬过来重算。

---

## 1. Butano 重制版已有成果（盘点）

### 1.1 代码规模（实测，非估算）

| 项 | 数字 |
|---|---|
| `butano-sequel/game/include/konoha/` 头文件 | **137 个 / 6.47 MB** |
| 其中最大 | `generated_battle_unit_visual_content.h` 1.42 MB、`generated_battle_presentation_content.h` 1.15 MB、`generated_battle_presentation_portrait_content.h` 950 KB、`generated_battle_scenario_content.h` 913 KB |
| 最大**手写**头 | `battle_scene_controller.h` 86 KB、`battle_action_system.h` 82 KB、`battle_player_action_flow.h` 66 KB、`battle_ai.h` 54 KB |
| `butano-sequel/game/src/` 源文件 | **4 个 / 330 KB**（`battle_runtime_scene.cpp` 296 KB、`battle_preparation_scene.cpp` 27 KB、`battle_campaign_sram.cpp` 6.6 KB、`scenario_43_scene.cpp` 171 B） |

### 1.2 13 个基础系统：全部有实现，成本已实测

`docs/butano-konoha-systems-cost.md`（重制线）拆了 **900 个逻辑单元 + 160 个集成单元**，
三点估算 **80.9 / 121.3 / 191.2 Codex 连续墙钟小时**，推荐规划值 121–191。
逐系统都有对应 C++（核心循环 `battle_runtime_scene.cpp`、寻路 `grid_pathfinder.h`、
动作系统 `battle_action_system.h`、AI `battle_ai.h`、存档 `battle_campaign_save.h` +
`battle_campaign_sram.cpp`、演出 `battle_combat_presentation.h` 等）。

### 1.3 实测样本（不是计划，是跑出来的）

| 样本 | 结果 | 出处 |
|---|---|---|
| B1–B6 五个内核微基准 | **1,262 行 C++**（含测试）+ 真实 ROM wiring，**29.34 分钟**；B6 干净 devkitARM 构建 64.4 s | `butano-konoha-systems-cost.md` |
| **scenario 41 完整纵切片** | **7.9869 小时**；战前菜单 → 四回合胜利 → 结算 → 升级 → **11 页战后对白** → 世界地图 → **5 首 BGM** → **14 个音效** | 同上 §Goal 实测 |
| 逐帧保真 | 组合拳 **264 帧在真实 mGBA 中 264/264 normalized RGB 一致** | 同上 |
| 已实现关卡 | **3 / 47**（场景 41 / 43 / 49；map header 表 47 条） | `butano-wiring-roadmap.md` 起点读数 |
| S49 覆盖层残差 | step-20 **2,917 px**（接线侧可回收 **613 px**，其余 2,304 px 属重制侧移动范围规则） | 同上 W2 |

> **关键**：scenario 41 的 264/264 已经证伪「复刻必然丢原版手感」——这原本是选
> 静态重编译版最强的反驳理由（`notes/sequel-platform-decision-20261023.md` §2）。

### 1.4 接线与门禁基建（这是重制版真正的复利资产）

| 项 | 数字 |
|---|---|
| Python 门禁测试文件 | **381** |
| C++ 宿主测试 | **121** 个 `.cpp` |
| 生成器（`GENERATED_PRODUCTS` 登记） | **16** |
| ROM 导入器 | **4**：`import_rom_pixel_ab_baselines.py`、`import_rom_relocation_specs.py`、`import_rom_reverse_families.py`、`import_rom_shelf_families.py` |
| 内容库 | **34** 个 bank，**34/34** 都写进了 `_provenance` 来源登记块（ROM 偏移/长度/哈希 + 提取器 + 逆向族/note，或明写「无来源」理由） |
| 图形资产 | **1,819** 个，其中 **1,807（99.4%）** 已按生成器归组、11 个真歧义明列 |
| 差异测量工具 | `measure_butano_reverse_gap.py`、`measure_butano_usable_backlog.py`、`measure_butano_wiring_coverage.py`、`audit_butano_reverse_provenance.py` |
| 里程碑 | 差异清单 **M0–M7 全完成**；接线图 **W0 ✅ W1 ✅ W4 ✅**，W2/W3/W5 🟡 |

---

## 2. 逆向成果被用到了哪一步（三层口径）

### 2.1 层 A · 成果族（264 个 = 逆向树 `artifacts/` 的晋升单位）

| 判定 | 族数 | 占比 |
|---|---:|---:|
| 进 Butano 构建链 | **164** | **62.1%** |
| 未进构建链 | **100** | **37.9%** |

已接线的 164 族按**血缘强度**再分（这一步很重要，见 §3.2）：

| 血缘 | 族数 | 含义 |
|---|---:|---|
| 声明式接线且有门禁 | **121** | 导入器/provenance 载体钉住族 + 逐文件哈希复核 |
| 复刻侧重导出、逐字节相同 | **41** | 字节对，但**血缘是本地重导出，不是导入** |
| 只作 verifier 证据 | **2** | 不消费 payload |

未接线的 100 族按状态：

| 状态 | 族数 | 能不能"用" |
|---|---:|---|
| `not-importable` | **51** | 不能导入——是控制流 / CFG / 覆盖分母，只能当**规格**用 |
| `no-material` | **37** | 无可导入材料（其中 9 族有 payload 但**逆向侧自己还没标 accepted**） |
| `unclassified` | **12** | 词表命中或全不命中，**有意不判定** |

按类别看：`rom` 126 族中 build **34**（早前读数是 0，已被 §8.6 的货架导入器改写）；
`visual` 64/70、`presentation` 14/14、`residual` 13/13、`map` 15/15、`battle` 3/3。

### 2.2 层 A' · 货架（已闭合 + 带 payload + 无人接）

**65 族**（= 51 analysis-only + 12 unclassified + 1 asset-direct + 1 table-direct）。
其中**能直接导入的只有 2 族**，而且这 2 族都已被 verifier 读作证据：
`overview-gradient-overlay-v1`、`character-runtime-unit-oam-bindings-v1`。
⇒ W4 记的 `on-shelf` 归零是**真的**。

### 2.3 层 B · 结论（436 篇逆向笔记）

| 桶 | 条数 | 占比 | 含义 |
|---|---:|---:|---|
| `implemented_in_code` | **29** | 6.6% | 已被重制侧构建链引用（行号可查） |
| **`needs_guard`** | **332** | **76.1%** | **结论已闭合，但还没转成门禁** |
| `not_applicable` | 43 | 9.9% | 与本复刻无关（逆向侧自有工程 / 快照副本） |
| `missing_evidence` | 19 | 4.4% | **逆向侧自己还没做完**（不是重制侧的债） |
| `needs_human_review` | 13 | 3.0% | 脚本判不了，需人看 |

`needs_guard` 里 **314 条连测试都没引用过**（W5 第一步已把其中 1,434 个 ROM 字节钉点
做成机器可检，但**语义门禁仍逐条待写**）。

---

## 3. 「应当被使用但未使用」的比例

分母必须先声明——同一批事实换单位，答案差一个数量级。

| 口径 | 分子 | 分母 | 比例 | 判读 |
|---|---:|---:|---:|---|
| **R1b 物料·严格**（已闭合 + 可直接导入 + **连 verifier 都没读过**） | **0** | 201 | **0.0%** | ✅ **物料层已清零** |
| **R1 物料·宽**（已闭合 + 可直接导入 + 未接进构建链） | **2** | 201 | **1.0%** | 这 2 族已被 verifier 读作证据 |
| **R2 结论·全部笔记** | **332** | 436 | **76.1%** | ⚠️ **真正的主欠账** |
| **R2b 结论·已判定的笔记** | **332** | 361 | **92.0%** | 同上，更严格的分母 |
| **R3 带 payload 却在构建链外** | 65 | 264 | 24.6% | 其中 63 族是控制流/未定，不是可导入素材 |
| **R4 全部在构建链外** | 100 | 264 | 37.9% | 含逆向侧未完成的 9 族 |

### 3.1 结论

1. **物料层没有欠账了。** W1（补回 26 族本地产物）+ W4（55 族接进导入器载体）做完后，
   「可导入且已闭合」的成果族**没有一族是彻底没人碰过的**。早前读数里的
   「71 族货架」已在 2026-10-22 由 W4 归零。
2. **欠账在结论层。** 332 条 `needs_guard` 是**结论已经闭合、但重制侧还没有把这条结论
   变成一条会红的行为门禁**。这是当前唯一大规模、可逐条推进、且有明确验收口径的存量。
3. **控制流类 51 族不是"没用上"，是"用不上"。** 它们是 CFG / 覆盖分母，
   `not-importable` 是**结构性结论**，不是遗漏。它们要通过层 B 的门禁被消费，
   不该被"导入"。

### 3.2 必须一起说清的两个折扣项

- **41 族 `local-rederived-identical`**：字节逐字节相同，但**不是从逆向成果导入的**，
  是重制侧自己的 producer 重跑出来的。重制线自己的边界声明第 4 条写着
  「不要把复刻侧本地重导出的副本当成接上了逆向成果」。
  ⇒ 若把"使用"定义成**血缘可证的导入**，可证导入只有 **121 / 264 = 45.8%**，
  另有 **41 族（15.5%）**是"结果对、血缘弱"。
- **`build` 是下界不是真值**（重制线自己的 §0.1）：名字引用只能证明"引用"，
  不能证明"数据血缘"。M0 的来源声明机制已把 35 个生成产物钉上
  `reverse-source: <族> @ <manifest-sha256>`，但 sink 面仍有
  **110 手写头 / 34 内容库 / 1,819 图形资产 / 4 运行时源码**没有声明载体
  （内容库与图形资产已做归属标注载体，但还没到"声明即血缘"的程度）。

---

## 4. 方法与复算

```powershell
# 本仓（master）——重算本审计
python tools/butano_reverse_utilization_audit.py `
    --butano-root 'D:\Shell\Github\gba-naruto-butano' `
    --out-dir artifacts/butano-utilization-audit-v1
```

脚本**不重算任何逆向事实**，只把重制线三份既有收据按 family id join 后出表，
因此不会与重制线自己公布的数字漂移。它**失败关闭**：收据缺失、三份收据的族集合
不一致、或 notes 桶数对不上 ⇒ 退出码 2 并给出具名原因。

**独立验证**：在重制线复跑差异测量，读数与既有收据逐字节一致——
索引条目 2,207、成果族分母 264、`build` 164（62.1%）、`doc` 87、`test` 3、`none` 10、
条目口径 `build` 445 / `doc` 335 / `local_artifact` 125 / `none` 1,073 / `test` 229、
台账 36 条 `missing` 0、成果类总缺口 `result_gap` 224（`result_total` 765）。

---

## 5. 踩坑记录（两个都值得留给下一个会话）

### 5.1 测量本身在 Windows 上是可复现的——差别只在写出的字节

在重制线复跑 `measure_butano_reverse_gap.py`（`--reverse-root` 指本机逆向树），
**读数与既有收据逐项一致**：索引条目 2,207、`build` 445 / `doc` 335 /
`local_artifact` 125 / `none` 1,073 / `test` 229、成果族 264、`build` 164、
`result_gap` 224、`ledger_missing` 0。
⇒ **重制线的测量口径没有平台依赖**，含"按内容排除本地副本"那条规则也照常生效。

**但写出的文件字节与 commit 里的不一致**（见 5.2），
且 `generated_at` 时间戳必然变。
⇒ **不要在 Windows 上直接覆写重制树的收据**：内容对、字节不对，
反而会让"证据身份"这条线变脏。要复算就写到仓外目录，
或用本审计脚本这种「只读既有收据、不重算」的方式。

### 5.2 `write_text` 在 Windows 上写 CRLF，破坏按 SHA-256 钉死的证据身份

重制线三份收据在 git 里是 **LF**。Python 的 `Path.write_text()` 在 Windows 上
默认 `newline=None` ⇒ 写出 **CRLF**（34,264 行全部变成 CRLF 版本，
字节数 955,840 → 990,062，`git diff` 显示全文 36,767 行改动）。
重制线自己的迁移记录写死「仓库用文件 SHA-256 当证据身份，换行符一改全部钉死失效，
且 `git status` 不会报脏」——**这次 `git status` 报脏了**（因为内容行也变了），
但如果只改行尾符不改正文，`git status` 就会装死。
⇒ 本审计脚本写收据时显式 `newline="\n"`（见 `main()` 里的 `write_text(..., newline="\n")`）。
⇒ **教训**：任何写进这三棵树的机器产物，在 Windows 上都必须显式指定 LF。

### 5.3 决策笔记引用的是**过期读数**（见 §6）

---

## 6. 对 `notes/sequel-platform-decision-20261023.md` §4/§6 的更正

### 6.1 数字更正（§4）

该文 §4「Butano 线当前有一笔必须先还的债」引的是 **M0–M7 刚做完时的读数**：

| §4 写的 | 2026-10-23 实测 | 差 |
|---|---|---|
| 成果族 `build` **88 / 262 = 33.6%** | **164 / 264 = 62.1%** | 分子 +76，分母 +2 |
| `rom` 类 **124 个，`build` = 0** | `rom` 类 126 个，**`build` = 34** | 货架导入器把 67 族接进构建链 |
| 结论层 notes 被消费 **17 / 427 = 4.0%** | `implemented_in_code` **29 / 436 = 6.6%** | 样本与分母都变了 |

**结论没变，但欠账的形状变了**：
§4 说「先按 M0–M7 把这些接进 Butano 构建」——**这一笔已经还了**（M0–M7 全 ✅，W0/W1/W4 ✅）。
现在真正剩下的欠账是**层 B 的 332 条 `needs_guard`**，不是「成果族没接进构建链」。

### 6.2 下一步更正（§6）——**M2 的债只还了一半，别当成还完了**

§6 第 1 项写「用原版 38 态分派器替换 Butano 侧自造的 26 个枚举，建 38↔26 映射表」。
实测这两件事的完成度**不一样**：

| 子项 | 状态 | 证据 |
|---|---|---|
| 建 38↔26 映射表 | ✅ **已完成并进构建链** | `sequel/content/battle_controller_states.json`：`state_count=38`、`named_count=26`、`unknown_count=12`、`mapping` 26 条、`remake_only_phases` 6、`original_only_states` 17、`remake_phase_count=26`；`rom-battle-controller-cfg-v1` 状态 = `wired-and-gated` |
| **用原版状态码驱动运行时** | ❌ **仍未做** | 同一份文件的头部写着 **`implemented: false`**，原文：*"It does NOT mean the remake implements the original state machine: the remake still runs its own 24-value `battle_scene_phase` enum."*（⚠️ 2026-10-26 订正：这段散文里的 **24** 已是过期数字，同一份文件的 `remake_phase_count` 字段写的是 **26**，且重制源 `battle_scene_controller.h` 的枚举实测 26 个成员 ⇒ 以 26 为准，散文没跟上。） |

⇒ **「重制侧带着一批猜的规则」这个判断今天依然成立**——
38 态表是**规格**，不是**运行时**。
换枚举之所以还压着，是因为映射表自己写着：8 个相是原版一个态的子相、
4 个是重制新增、12 个原版态语义未定、17 个原版有而重制还没有
⇒ 现在硬换会把未定语义编进运行时。
⇒ **下一步应当是「按 W5 把 332 条结论逐条转成行为门禁」，
其中包含那 12 个 `unknown` 态的语义定案**；在那之前不要换枚举，
也不要把新机制建在自造的 24 相上。

---

## 7. 边界声明

- 本审计**只做 join 与读数**。没有重算任何逆向结论，没有改重制树的任何文件，
  没有动三份既有收据（§4.1 的第一次误覆写已 `git checkout` 还原并逐字节核对）。
- 「被使用」的口径是重制线自己的（`build` = 构建链引用）。它有 §3.2 的两个折扣项，
  本审计不替重制线重新定义「使用」，只把口径与折扣一起摊开。
- 332/436 这类数字**随逆向树与重制树变动**，引用时必须带逆向提交号。
  本文的锚点是 `821d0937` / 收据生成于 2026-10-23T09:12Z。
