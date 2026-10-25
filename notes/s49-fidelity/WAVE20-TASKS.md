# WAVE20-TASKS —— wave 20 任务书（四路并行）

> 创建：2026-10-25 01:45 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/W19-A-opening-title.md` ·
> `W19-B-settlement-tail.md` · `W19-D-real-settlement-chain.md`
> （⚠️ `W19-C-black-fade.md` **缺失** —— C 路被截断，父代理已从它的代码注释与产物转述其结论，见 §0.4）
> 父代理：`notes/s49-fidelity/W18-PARENT-residual-structure.md`
> 任务书：`notes/s49-fidelity/WAVE19-TASKS.md`

---

## 0. 本波目标

### 0.1 ⭐⭐ wave 19 已经拿下的东西（**已接线进共享树**）

| 项 | wave 18 末 | wave 19 末 |
|---|---|---|
| 「開始」标题卡 | ⛔ 按 A 冻住 / 不按则 A↔B 无限循环 | ✅ **纯定时、完全无视输入、一次走完**（按/不按 A 的 300 帧 **30/30 帧 sha256 逐字节相同**） |
| 步偏移 | +4 → 第 10 步掉到 **+3** | ✅ **恒为 +4**（sha 精确匹配集合 `{+3}` → `{+4}`） |
| 原版姿态 B | 重制侧画不出来 | ✅ **首次出现在 walk 里**（原版 `step-10` ↔ 重制侧 `step-14`：**2,761 → 278 px**） |
| 結算屏人物 | 1,898 px | ✅ **0 px**（結算屏 2,582 → **684 px**）⇒ **推翻 U2 的 8bpp 前提**：立绘自身只要 15/12/15 色 ⇒ **4bpp 就够** |
| 戰後對白 | 26,819 px | ✅ **0 px**（A 路落 B 的接线 + B 的资产） |
| 任務菜單 | 37,694 px | ✅ **0 px**（同上） |
| 结算链合计 | −66,411 px | ⇒ **−66,411 px**（對白 + 菜單 + 人物） |

### 0.2 ⭐⭐ 本波要打的四个目标（**都是新挖出来的阻塞**）

| 流 | 主题 | 为什么是它 |
|---|---|---|
| **E1** | ⭐⭐ **Butano 调色板耗尽** + 黑场 B2/B3/B4 | **真胜利后结算链第一页就死在 Butano 错误屏** ⇒ 真实结算链整条拿不到 |
| **E2** | ⭐⭐ **戰鬥分发奖规则**（684 px） | 「击倒发奖」规则**根本不存在** ⇒ 真实战斗的战果也必然是 0/0/0 |
| **E3** | ⭐⭐ **战斗段首帧的 ~73 k px** | 判定台剩余的最大块（原版 `step-19/21/22` vs 重制侧各差 24k–28k px） |
| **E4** | ⭐ **逆向线取证** + 旧资产清理 | 给 E2/E3 提供**原版真值**；顺带清 33 张无人引用的旧对白资产（~1 MB ROM） |

### 0.3 文件归属（互斥，越界 = 违规 ⇒ 写「接线请求」交父代理）

| 流 | 独占文件 |
|---|---|
| **E1** | `game/src/battle_runtime_scene.cpp`、`game/include/konoha/battle_visual_resource_coordinator.h` |
| **E2** | `game/include/konoha/battle_action_system.h`、`game/include/konoha/battle_results.h` |
| **E3** | `game/include/konoha/battle_map_visual_projection.h`、`game/include/konoha/battle_map_content.h`、`game/include/konoha/battle_scene_presentation.h`、`game/include/konoha/battle_original_states.h` |
| **E4** | **不改任何重制线产品文件**（逆向线**只读**）；新工具放 `tools/s49_w20e/`；资产清理只在**自己的副本**里做并交清单 |

> ⚠️ **`game/src/battle_runtime_scene.cpp` 归 E1 独占。**
> E2/E3/E4 若需要改它 ⇒ **不要改**，写「接线请求」（文件 + 行 + 改成什么 + 为什么），由父代理转交 E1。

### 0.4 ⭐ W19-C 的交接（**它的笔记没写成，父代理从代码注释与产物转述**）

C 路改了 2 个文件（**已接线**）：

1. **`game/include/konoha/battle_black_field_star_mask.h`** — 加了「**位置没变就不重写**」的短路
   （`previous_level` / `previous_known` / `fresh` 三个判断）。
   ⇒ 目的：星形光圈的淡入从 **28 帧对齐到原版的 24 帧**。
   ⇒ 注释里写明根因：**「上一级的摆放只有在遮罩还在屏上时才知道」**
   ⇒ 场景的 core update 必须先跑完才能提交新的一级 ⇒ **一级变化跨两帧才可见** ⇒ 淡入 28 帧。
2. **`src/main.cpp`** — **开机白屏**改法：GBA 的 forced blank（DISPCNT bit 15）**开机就在**
   ⇒ 屏是**白的**；但ano 在 `bn::core::init()` 的第一次 core update 才写 DISPCNT，
   而那次 update 之前是 crt0 花 **12 个 GBA 帧**清 EWRAM ⇒ **开机有 13 帧纯白**（双倍录制编号是 26 帧）。
   ⇒ 改法：**提前清 forced blank**，并用**背景色**（BG 调色板 entry 0 = 准备场景主色 231,247,214）
   顶替 ⇒ 开机读起来像「游戏已经起来了」，且**原版开机既无白帧也无黑帧**（第 3 帧起就是标题画面）。

⚠️ **C 路的实测黑场清单（它自己的 `build/w19-c/blackfade-b6b/blackfade.json`）**：
| # | 帧段 | 总帧 | 淡出 | 持黑 | 淡入 | 状态 |
|---|---|---:|---:|---:|---:|---|
| 1 | 00527–00532 | 6 | 0 | 6 | 0 | ⛔ **B2**（准备→战斗 6 帧纯黑） |
| 2 | 01549–01618 | 70 | 24 | 18 | 28 | ⚠️ 淡入仍 28（原版 24） |
| 3 | 01659–01660 | 2 | 0 | 2 | 0 | ⛔ **B3**（生长→对白 2 帧纯黑） |
| 4 | 02123–02130 | 8 | 0 | 8 | 0 | ⛔ **B4**（对白内部 8 帧纯黑） |
| 5 | 02171–02250 | 80 | 28 | 24 | 28 | ⚠️ C 的星形短路应把 28 → 24（**需复测**） |

⇒ **B2 / B3 / B4 都在 `battle_runtime_scene.cpp`**（E1 的文件）⇒ E1 顺带做掉。

### 0.5 ⭐⭐⭐ 收口巡检的重大更正（2026-10-25 14:5x · 父代理）

> **完整报告：`notes/s49-fidelity/W20-RECOVER-lanes.md`**
> **补丁：`build/w20-verify/e1-palette-fix.patch`（2,532 B / +35 行 / 唯一改动文件 `battle_runtime_scene.cpp`）**

⚠️ **本任务书是「E1 从零修调色板」的版本 —— 但那个前提已经不成立了。**

| 项 | 实际 |
|---|---|
| **E1 的修法** | ⭐ **已经在盘上并被验证过**（`build/w20-e1/`）：进入全屏结算相位前**先释放决斗森林（4bpp/32 色）+ 决斗 HUD**，再让 8bpp/256 色的胜利屏背景进来 ⇒ 16 槽 bank 不再被两个屏幕尺寸的背景同时占 |
| **A/B 证据** | 同 lane 同探针：修前 1 页 + Butano 错误屏；修后 **48 页 + `final_phase=task_menu` + 无错误屏** |
| **真实战斗** | `poke_commands=0`、`outcome=1`、蜂 25→0、结算链 48 页、7 段相位全走到 |
| **逐字节相同** | 真实链里 **9 帧与原版真值 sha256 完全相同** ⇒ 「真实链能走完 7 段」第一次被实测证明 |
| **⛔ 残差** | 結算屏比无修法的 ROM **差 35,006 px**（整块偏绿 ⇒ 画在决斗森林的调色板上，而不是結算屏自己的底板） |
| **黑场** | B2/B3/B4 **一件都没做完** |

⇒ **E1 的任务从「从零修」变成「搬 + 修残差」**：
1. `git apply build/w20-verify/e1-palette-fix.patch`（只改一个文件）；
2. **修 §3.2 的背景层归属**（結算屏必须画在自己的底板上）；
3. 核对时间线后移（事件 2 的帧号从 01549 → 01639）；
4. 黑场 B2/B3/B4 + 事件 2/5 淡入 28 → 24。

⚠️ **验收必须是「三者同时成立」**：**48 页** ∧ **結算屏 ≤ 684 px** ∧ **无 Butano 错误屏**。
**只满足第一项的修法 = E1 现在这个状态（会让結算屏差 35 k px）。**

⚠️ **E2 的任务也变了**：「击倒 ⇒ 戰鬥分转给攻击者」的逻辑
`battle_action_system.h:2327-2333` **早就有了**；
真正缺的是**阵型表里的种子数据**（`generated_battle_scenario_content.h` 的 scenario 14，
5 个敌人的 `battle_experience` 字段**全是 0**）⇒ 取证归 **E4**，E2 只需补数据 + 复用已写好的测试
（`build/w20-e2/butano-sequel/game/tests/test_battle_experience_award.cpp` 已是可编译的断言骨架）。

⚠️ **E3 已有实质进展**：步偏移扫描出 **best_offset = 4**（total 648,356 → **148,914 px**），
3 对精确匹配（`step-14/15/17-A` ↔ `step-18/19/21-A`）⇒ 从这个起点继续。

---

### 0.6 隔离副本（各路只在自己的副本里改和构建）

| 流 | 副本根 |
|---|---|
| E1 | `D:\Github\gba-naruto\build\w20-e1\butano-sequel` |
| E2 | `D:\Github\gba-naruto\build\w20-e2\butano-sequel` |
| E3 | `D:\Github\gba-naruto\build\w20-e3\butano-sequel` |
| E4 | `D:\Github\gba-naruto\build\w20-e4\butano-sequel` |

构建命令（把 `w20-eX` 换成你的流）：
```
wsl -d Ubuntu-24.04 -- bash -lc "cd /mnt/d/Github/gba-naruto/build/w20-eX/butano-sequel && source /opt/devkitpro/devkitarm.sh && export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4"
```
⚠️ **本机构建非字节可复现** ⇒ 一切测量绑定**你自己那份 ROM 的 sha**。
⚠️ **禁止**在共享树 `D:\Shell\Github\gba-naruto-butano\butano-sequel` 里改文件或构建。

### 0.6 全波共同纪律

1. **一次只改一处，跑一次，记一行。**
2. **一次尝试必须能回答一个「是/否」问题。**
3. **连续 3 次同样结果 ⇒ 停**，写进台账，换方法。
4. **结论落进假设台账**（假设 / 判定方法 / 结果 / 状态=未验·已证伪·已确认）。
5. **新写文件一律 LF、无 BOM**；**不提交 git**。
6. **逆向线 `D:\Shell\Github\gba-naruto-reverse` 全程只读。**
7. ⛔ **改含中文的源文件一律用 `edit`/`write` 工具**，**不要用 PowerShell 的 `Set-Content` / `-replace`**。
8. ⚠️ **内存**：RAM 32.5 GB、总空闲约 10 GB；`mgba-probe` 长录制吃 7–8 GB 且泄漏
   ⇒ **全机同一时刻最多 1 路跑长录制（>60 s）**；跑完检查孤儿进程。
9. 单测：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w20-eX/butano-sequel`
   ⇒ 已知基线 **pass=118 / fail=20** ⇒ **多出任何一项 ⇒ 你引入的回归**。

---

## 1. ⭐⭐ E1 流 —— Butano 调色板耗尽 + 黑场 B2/B3/B4

### 1.1 现象（D 路实测，ROM `db676a63…`）

真实战斗成功（`from_real_battle: true`、`poke_commands: 0`、`bee_hp_dropped: true`、`outcome: 1`、round 13），
**但结算链在第 1 页（勝利屏）就死**：

```
BPP4 palette create failed. Colors count: 32 / no more available colors
```
⇒ 相位冻结在 13 ⇒ **7 段一段都进不去** ⇒ **真实结算链整条拿不到**。

**A/B 对照（同一 ROM、同一探针）**：
| 链 | 结果 |
|---|---|
| **真实链**（真打过一场） | ⛔ 第 1 页就炸（Butano 错误屏） |
| **poked 自检链** | ✅ **48 页全走完、无错** |
| **不用忍具的败北真实链** | ⛔ **同样炸** ⇒ 与忍具/胜负无关 |

**已测到的事实**：
* Butano 状态实测**只剩 1 个 8bpp / 256 色的调色板**（16 槽）⇒ 4bpp 无空槽；
* 全工程唯一匹配的两张屏幕尺寸背景：**勝利屏 `scenario_41_victory_bg`（8bpp / 256 色）**
  与 **`battle_duel_forest`（4bpp / 32 色）**；
* ⇒ **两张屏幕尺寸背景撞车**（同时活着 ⇒ 调色板 bank 被吃满）。

### 1.2 你的任务

1. **定位**：确认两张背景同时活着的代码路径。
   D 路给的接线点（**请自己核实**）：`battle_runtime_scene.cpp:1605-1624` 与 `5528-5545`
   ⇒ **胜利屏背景与决斗森林背景不得同活** + 恰当的 `bn::core::update()`。
2. **修法**：让它们**不同时活着**（释放其中一张 / 错开创建时序）。
   ⚠️ 但ano 的 BG 槽位是**按需分配**的 ⇒ 光「不同时活着」未必够；
   必要时显式 `bn::bg_ptr` 复位 + `bn::core::update()`。
   ⇒ **以实测为准**（错误屏必须消失）。
3. **顺手做掉黑场 B2 / B3 / B4**（§0.4 表里的 #1 / #3 / #4，都在同一个文件）：
   * **B2**（准备→战斗 6 帧纯黑，`battle_runtime_scene.cpp:8152`）：
     ⚠️ **被 64 KB BG 图块区卡死**（准备背景 32 KB + 部署地图 64 KB 无法共存 ⇒ **到 0 帧不可能**）
     ⇒ 给出**可达到的最小帧数 + 硬证据**，不要承诺 0。
   * **B3**（生长→对白 2 帧纯黑，`:5066-5067` 的 `map.reset(); bn::core::update();`）：
     把这次交接**挪进遮罩还盖着屏幕的持黑段**（顺带把事件 2 的淡入 28 → 24）。
   * **B4**（对白内部 8 帧纯黑，`:6497-6514` + `battle_visual_resource_coordinator.h:119-131`）：
     把交换**推迟到事件 2 淡出的末几级**。
4. **复测黑场清单**（C 路的 `build/w19-c/blackfade-b6b/blackfade.json` 是基线）：
   事件 2 与事件 5 的淡入都应变成 **24**；B2/B3/B4 应收掉或给出最小可达值。

### 1.3 ⭐ 判定问题（是/否）

> **「修好后，真实战斗打完仗之后，结算链的 7 段能否全部录到（不再出现 Butano 错误屏）？」**

### 1.4 验收

| # | 项 | 判据 |
|---|---|---|
| E1-1 | 调色板 | 真实链第 1 页**不再**出现 `BPP4 palette create failed` |
| E1-2 | 真实链 | 7 段（勝利 / 結算 / 6 張升級 / 忍具一覽 / 戰後對白 / 任務菜單）**全部录到** |
| E1-3 | 黑场 B2 | 给出最小可达帧数 + 硬证据 |
| E1-4 | 黑场 B3 / B4 | 收掉（2 帧 / 8 帧纯黑消失） |
| E1-5 | 黑场淡入 | 事件 2 与事件 5 的淡入 = **24** |
| E1-6 | 单测 | pass=118/fail=20 |

### 1.5 ⚠️ 收口后补的口径澄清（2026-10-25 14:2x，父代理）

> ⭐⭐ **E1 是整条 wave 20 的硬前置，且阻塞在已接受 ROM 上原样存在。**
> 收口后的复测（用流水线钉住的副本 `build/s49-package-w19b/work/pinned-rom/measured.gba`，
> sha `e2182fff9…` = **已接受基线的 ROM**，不重建、不改产品代码）：
>
> ```
> python tools/s49_battle_balance/v1_battle.py \
>   --rom build/s49-package-w19b/work/pinned-rom/measured.gba \
>   --exe build/mgba-probe-w19/mgba-probe.exe \
>   --out build/w20-verify/accepted-run --boot --max-turns 400 --use-tools
> ```
>
> | 段 | 结果 |
> |---|---|
> | **真实战斗** | ✅ `outcome=1`、5 只蜂 **25 → 0**、`bee_hp_dropped=true`、`escort_alive=true`、`poke_commands=0`、`errors=[]`、13 回合 / 60,518 帧 / 31.4 s |
> | **结算链** | ⛔ **`settlement pages: 1`**、`final_phase: 13 (outcome)`、第 1 页 = **Butano 错误屏**（`BPP4 palette create failed. Colors count: 32`）、stderr 里 bank 只剩 1 个 8bpp/256 色的调色板 |
>
> ⇒ **E1-1 / E1-2 在已接受 ROM 上都还是红的** ⇒
> **E1 不修 ⇒ E2 拿不到可对照的真实結算屏（684 px 的发奖规则无法在真实链上验证）、
> E3 的「真实链逐屏差表」同样拿不到。**
>
> ⇒ 🎯 **对照基线已经备好**：`build/w20-verify/accepted-run/`
> （`battle.json` + `shots/page-000-outcome.png` 错误屏截图 + `stderr.txt`）。
> **E1 修好后跑同一条命令 ⇒ 错误屏必须消失、`settlement pages ≥ 7`；这就是 E1-1/E1-2 的验收。**

> ⭐ **另一个口径澄清**：`build/w19-b/align-final.json` 那张「結算链逐屏差表」是在 ***poked* 链**上量的
> （`build/w19-b/chain-final/chain.json` 的 `entry.method` = 「controller state poke (phase + outcome)」）
> ⇒ **「結算链 4 屏 0 px」是资产/渲染层的结论（可信）**，
> 但**不能**当成「真实战斗打完仗后结算链能走完 7 段」的证据。
>
> **代码侧复核（收口后只读确认，三个阻塞都还在）**：
> * `_add_victory_background()`（`battle_runtime_scene.cpp:1647`）建 8bpp/256 色胜利屏背景；
>   `_release_background_before_bpp_transition()`（`:5661`）**只** `reset()` `_duel_hud_background` 与 `map`，
>   **不释放胜利屏背景**；`_bind_duel_background()`（`:5673`）随后建 4bpp/32 色 `battle_duel_forest`（要 2 个连续槽）
>   ⇒ **16 槽 bank 被 8bpp 占满 ⇒ 后到的 4bpp 请求必然 `BN_ERROR`** ⇒ 阻塞仍在。
> * 「戰鬥分」发奖规则：`battle_results.h:369-395` 的 `_battle_experience()` 只累加
>   `unit->carried_experience`（同角色转移）+ 被动 `battle_experience_passive_target`
>   ⇒ **无「击倒发奖」写点** ⇒ 684 px 仍是产品缺口。

---

## 2. ⭐⭐ E2 流 —— 「戰鬥分」发奖规则（684 px）

### 2.1 现象（D 路实测并定位）

結算屏残差 **2,582 px** 里，**684 px 全在数值区（y 104–160）**，立绘 1,898 px 在 y 0–104（**已被 B 路清零**）。
⇒ **只剩第 2 行「戰鬥分」不同**：

| | 原版 | 重制侧 |
|---|---|---|
| 任务经验（125） | **100 / 150 / 0** | 0 / 0 / 0 |
| 回合奖励（75） | **300 / 350 / 200** | 200 / 200 / 200 |

**根因（D 路查实）**：
* `battle_results.h:369-395` 的 `battle_experience` = **Σ `unit->carried_experience`**；
* 该字段**全工程只有两个写点**：
  1. `battle_scenario_loader.h:465` 的**场景种子**（实测为 **0**）；
  2. `battle_action_system.h:2330-2332` 的**阵亡零和转移**（受害者身上的经验转给凶手）。
* ⇒ **没有「击倒发奖」规则** ⇒ **真实战斗的战果也必然是 0/0/0**（不是 poked 链的假象）。

**原版公式未知** ⚠️：D 路提示「场景 46 捕获猫也有 59/59/30 ⇒ **不是『击倒数 × 常数』**」。

### 2.2 你的任务

1. ⭐ **查原版公式**（逆向线**只读**）：
   * 原版战斗结果字节在 **`0x02026807`**（0/1/2）；
   * 逆向线 `D:\Shell\Github\gba-naruto-reverse` 里有 `artifacts/runtime-checkpoints/`
     （大量 `*-evidence.json`，含 `battle` 段的字段与真值）与 `docs/`、`notes/`；
   * 找**多个场景**的战果数值，反推公式（是「击倒数 × 某个量」「参与回合数 × 常数」
     还是「按剩余血量/伤害累计」）。
   ⇒ **不要猜**：先把原版的**取值表**列出来（场景 × 三行数值），再写公式，
   并用**至少 3 个场景**验证你的公式。
2. **实现**（在你的独占文件里）：把规则加进 `battle_action_system.h` 的结算路径
   （**击倒时**给攻击方加经验）与 `battle_results.h` 的取值。
3. **接线请求**：如果规则需要在 `battle_runtime_scene.cpp` 或 `battle_scenario_loader.h` 里加种子/触发点 ⇒ 写请求。

### 2.3 ⭐ 判定问题（是/否）

> **「重制侧的战果数值能否与原版在同一个战斗里逐行相同？」**

### 2.4 验收

| # | 项 | 判据 |
|---|---|---|
| E2-1 | 原版取值表 | ≥ 3 个场景 × 3 行数值（**从逆向线读到的真值**，不是猜的） |
| E2-2 | 公式 | 写出公式 + 用 E2-1 的表**全部验证通过** |
| E2-3 | 实现 | 真实战斗的战果与原版**逐行相同**（結算屏残差 → **0 px**） |
| E2-4 | 单测 | pass=118/fail=20；**新规则要有单测** |

---

## 3. ⭐⭐ E3 流 —— 战斗段首帧的 ~73 k px（判定台剩余最大块）

### 3.1 现象

判定台残差里，**原版 `step-19 / 21 / 22` 三帧**与重制侧各差 **24,460 / ~28 k / ~28 k px**，
合计 **~73 k px**（占残差的大头）。
⇒ 这三帧的**时刻已经对齐**（A 路修好卡片后偏移恒为 +4），**画面仍差** ⇒
是**战斗场景本身的布景/相机差异**，不是流程错位。

**锚点（判定台报告）**：
| 原版帧 | `bg_hofs` | `overlay.lit_cells` / 族计数 | `unique_colours` |
|---|---|---|---:|
| `step-19-A` | `[160, 261, 268]` | 0（blank 256） | 65 |
| `step-21-A` | `[160, 261, 268]` | 0（blank 256） | 84 |
| `step-22-A` | `[160, 261, 268]` | **176**（band 4 / edge 107 / hatch 14 / line_alt 6 / solid 45） | 75 |

**重制侧同刻**：`bg_hofs` = **`[160, 0, 131]`**（原版是 `[160, 261, 268]`）
⇒ ⭐ **地图滚动的第二个/第三个分量差得很远** ⇒ **相机/布景不是同一个位置**。

### 3.2 你的任务

1. **定位**：重制侧在战斗段第 1 回合的相机/布景与原版差在哪。
   * 原版 `bg_hofs` 的 `[160, 261, 268]` 与重制侧的 `[160, 0, 131]` 分别代表什么
     （**读 `battle_map_visual_projection.h` / `battle_map_content.h` 的投影规则**）；
   * 原版那三帧的**布景内容**是什么（从真值帧看）；
   * 重制侧那三帧的布景内容是什么。
2. **修**（在你的独占文件里）：把战斗段首帧的相机/布景对齐原版。
   ⇒ ⚠️ 若必须改 `battle_runtime_scene.cpp` ⇒ 写接线请求。
3. **给出可证下界**（若不可完全对齐）。

### 3.3 ⭐ 判定问题（是/否）

> **「原版 `step-19/21/22` 的相机与布景能否与重制侧逐像素一致？若不能，可证下界是多少？」**

### 3.4 验收

| # | 项 | 判据 |
|---|---|---|
| E3-1 | 相机 | 重制侧战斗段首帧的 `bg_hofs` 与原版 `[160, 261, 268]` 同义（给出映射关系） |
| E3-2 | 布景 | 三帧的残差显著下降（给出数字） |
| E3-3 | 下界 | 不可归零的部分给出可证下界 + 硬证据 |
| E3-4 | 单测 | pass=118/fail=20 |

---

## 4. ⭐ E4 流 —— 逆向线取证 + 旧资产清理（**不改任何重制线产品文件**）

### 4.1 任务一：给 E2 提供**原版「戰鬥分」取值表**

* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **只读**；
* 找**多个场景**的战果数值（3 行：任务经验 / 回合奖励 / 总经验），
  每个都要**可复算的来源**（哪个 `*-evidence.json` / 哪个检查点 / 哪张真值图）；
* 输出**表**：场景 × 3 行数值 × 来源路径。
⇒ 这是 E2 的 E2-1 的输入 ⇒ **做完立刻把表发给父代理**（父代理转交 E2）。

### 4.2 任务二：给 E3 提供**战斗段首帧的原版布景真值**

* 原版 `step-19 / 21 / 22` 的画面内容（地图位置、单位、覆盖层）；
* 能取到的原版检查点/真值帧路径。

### 4.3 任务三：旧资产清理清单（ROM 瘦身）

* B 路报告：**33 张无人引用的旧对白资产**仍在 ROM（约 **1 MB**）
  ⇒ 在**你自己的副本**里确认它们**确实无人引用**（用 `grep` 引用面 + 构建产物核对），
  产出一份**可安全删除的清单**（文件名 + 引用面证据 + 预计省下的字节数）。
* ⚠️ **本波不要真的删**（避免与 B 路的资产冲突）⇒ 只交清单。

### 4.4 ⭐ 判定问题（是/否）

> **「逆向线里是否**存在**可复算的原版战果数值（≥ 3 个场景），足以反推出发奖公式？」**
> **「那 33 张对白资产是否真的无人引用？」**

### 4.5 验收

| # | 项 | 判据 |
|---|---|---|
| E4-1 | 战果取值表 | ≥ 3 场景 × 3 行，每个带来源路径 |
| E4-2 | 布景真值 | 三帧的原版画面描述 + 路径 |
| E4-3 | 资产清单 | 33 张（或实际数量）的文件 + 引用面证据 + 预计字节 |
| E4-4 | 仪器 | 新工具放 `tools/s49_w20e/` |

---

## 5. 波末验收（父代理执行）

| # | 项 | 判据 |
|---|---|---|
| 1 | 接线 | 四路的独占文件拷回共享树（`tools/s49_wave18/integrate.py --apply`）+ 接线请求逐条处理 |
| 2 | 统一构建 | `ROM fixed!`，sha 记录 |
| 3 | ⭐ 真实结算链 | 7 段全部录到，逐屏差表 |
| 4 | 結算屏 | 残差 **684 → 0 px** |
| 5 | 黑场 | 事件集合与帧数对齐原版 |
| 6 | 判定台 | 新 ROM 上重跑，给出残差与归因 |
| 7 | 棘轮 | 残差**只许变小**；单测 pass=118/fail=20 |
| 8 | 12 步流水线 | `python tools/s49_package/run_pipeline.py --out build/s49-package-w20` |
| 9 | 路线图 | `docs/sequel-roadmap.md` 回填 wave 20 里程碑 |
