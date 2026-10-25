# W18-PARENT —— 棘轮红灯裁决：覆盖层「青 + 橙」的规则回退

> 2026-10-25 00:2x · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE18-TASKS.md` §5.1
> 上游：`notes/s49-fidelity/U1-d4-fix.md` §3.1（红项归属） ·
> `notes/s49-fidelity/U2-overlay-settlement.md` §2 ·
> `notes/s49-fidelity/U3-wave17-package.md` §0（12 步流水线 11 绿 / 第 2 步红）

---

## 0. 一句话结论

> ⛔ **wave 17 结束时棘轮是红的**，红项 = `test_battle_range_ui_phase_truth_table`
> （**新增红**，HEAD 基线 20 项预存债之外多出来的第 1 项），
> **归属 U2**（它改了 `battle_range_ui_style.h` 的相位规则）。
> ⇒ 它**卡着 12 步出包流水线**（「不是全程绿 ⇒ 不许成为基线」）。
> ⇒ **父代理已裁决并修好：回退 U2 的规则改动**，理由**不是**「测试方便」，
> 而是 **U2 的改动本身把活相位规则改错了**，而且 U2 自己实测它**是 no-op**。

---

## 1. 冲突的两条规则（逐字）

### 1.1 真值表测试（wave 13 加的，**未被 git 跟踪**）

`game/tests/test_battle_range_ui_phase_truth_table.cpp` 第 24–30 行的自述：

```
//   move phase      : move if reachable, else blocked if blocked, else grid
//                     (the cursor cell is *not* special -- it is the acting
//                     unit's own cell, inside the cyan reach set);
//   other phases    : cursor > target > attack range > blocked > grid
//                     (the cyan reach set is not painted at all).
```

它引用的原版帧证据：
* 原版**移动相位**帧（`movegrid`）**零黄、零绿、零橙** —— 192 个亮起的逻辑格
  是 solid 83 / edge 63 / hatch 46（wave 12 / X2，台账 X2-H4）；
* 原版**目标选择**帧**零青** —— 青（可达集）只属于移动相位（wave 13 / G，台账 **G-H15**）。

第 155–156 行：**同一组输入** `(move=false, cursor=false, in_move=true, attack=false, target=false, blocked=false)`
⇒ 断言 `== grid`。

### 1.2 U2 wave 17 的规则改动

`game/include/konoha/battle_range_ui_style.h` 的 `battle_range_ui_cell_kind()`：

```cpp
// 改前
if(in_move_range && move_phase) { return battle_range_ui_tile_kind::move; }
// 改后（U2）
if(in_move_range)               { return battle_range_ui_tile_kind::move; }
```

U2 在 `game/tests/test_battle_range_ui_style.cpp` 里同时加了一条**相反**的断言
（改后第 197–204 行）：

```cpp
assert(battle_range_ui_cell_kind(false, false, true, false, false, false) ==
       battle_range_ui_tile_kind::move);   // 同一组输入 ⇒ 必须是 move
```

⇒ **两条断言对同一组输入给出相反要求** ⇒ 二者必有一条红。

### 1.3 U2 给出的新证据

> 「原版自己的结算帧里，青与橙**同时出现**，连续 67 个采样
> （dense walk 的 beat 22..24，帧 486..552）。」

---

## 2. 父代理的裁决：**回退规则**（保留真值表测试）

### 2.1 为什么不是「改测试去迁就规则」

两条原版观察**可以同时成立**，因为它们说的是**两个不同的帧**：

| 原版帧 | 相位性质 | 青是否出现 | 证据 |
|---|---|---|---|
| 目标选择帧 | **活帧**（缓冲被重画） | **零青** | G-H15 |
| 移动相位帧 | **活帧** | 满屏青 | X2 / X2-H4 |
| 结算帧 | **非活帧** | 青 + 橙 | U2 本波实测 |

⇒ 结算帧里的青**不是该相位「画」出来的**，
而是**上一相位（移动相位）留在缓冲里的青没有被清掉**。
⇒ **这是缓冲行为（渲染层），不是分类规则（`cell_kind`）的行为。**

### 2.2 为什么「放开相位门」是错的做法

1. **与活相位证据直接矛盾**：目标选择帧零青 ⇒ 活相位里青必须被相位门锁住。
2. **U2 自己实测它是 no-op**：青+橙共现 **0 / 783**（改前改后一样），
   walk 相位 **130 格一个没降**（130 → 130）⇒ 这条规则改动**不产生任何可观测差异**。
3. **它把「缓冲残迹」写成了「活规则」**：一旦实现缓冲不清，
   结算帧的青会由**残留**产生，而规则又允许**当场**画青 ⇒ 两个来源叠加，
   反而可能画多。

### 2.3 实际改动（父代理亲手改，2 个文件）

| 文件 | 改动 |
|---|---|
| `game/include/konoha/battle_range_ui_style.h` | `if(in_move_range)` → `if(in_move_range && move_phase)`；注释重写为「青只属于移动相位」+「结算帧的青+橙是缓冲不清的残迹，须在缓冲层复现，不是本分类器的规则」+ 指向本笔记 |
| `game/tests/test_battle_range_ui_style.cpp` | U2 那条相反断言改回 `== grid`（与真值表测试一致），注释写明理由；**U2 块里其余断言全部保留**（青/橙异格共现、绿赢青、移动相位三无、三族互不相同） |

⚠️ 改动一律用 `edit` 工具（这两个文件含中文注释，PS 5.1 的 `Set-Content` 会毁 UTF-8）。

### 2.4 保留的开放项（**不是这次能销掉的**）

> ⭐ **「原版结算帧的青 + 橙」仍未复现。**
> 回退规则后，重制侧结算帧**没有青**，而原版有 ⇒ 这正是覆盖层残差里
> 「walk 相位 130 格」那一类的来源之一。
> ⇒ **正确修法 = 覆盖层缓冲在相位切换时不清**（渲染层，
> `game/src/battle_runtime_scene.cpp` —— wave 18 由 W4 独占）。
> ⇒ **记为 wave 19 的开放项**，不要用「放开相位门」去糊。

---

## 3. 验证

| # | 项 | 结果 |
|---|---|---|
| 1 | 单测棘轮（共享树，`build/w1-run-all-tests.sh`） | 见 §3.1 |
| 2 | 红项归属 | `test_battle_range_ui_phase_truth_table`（新增红）⇒ **U2**；U1 的 21 项里其余 20 项与 HEAD 逐名相同（预存债） |
| 3 | 12 步流水线 | wave 18 波末统一跑；**目标是 12/12 全绿**（wave 17 是 11/12） |

### 3.1 单测棘轮读数

| | pass | fail |
|---|---:|---:|
| HEAD 基线（`build/run-baseline-tests.sh`，`git archive HEAD` 快照） | 101 | 20 |
| wave 17 末（U1 实测） | 117 | **21**（多出 `test_battle_range_ui_phase_truth_table`） |
| **本次回退后（实测，共享树）** | **118** | **20** ✅ |

> ⭐ **读数：`w1-all-tests: pass=118 fail=20 status=1`**（`status=1` 是那 20 项预存债，不是新红）。
> 失败的 20 项**与 HEAD 基线逐名相同**
> （`test_battle_all_scenario_runtime` / `campaign_route` / `campaign_save` /
> `campaign_scenario_42..47,49` / `dynamic_deployment_turn` / `material_pickups` /
> `presentation_controller` / `runtime_scene_gate` / `s49_input_flow` / `s49_opening` /
> `scene_character_actions` / `scene_controller` / `scene_multi_unit` / `scene_results`）
> ⇒ **零新增红**，`test_battle_range_ui_phase_truth_table` **回到绿**。
>
> （父代理自办，2026-10-25 00:3x）

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **P-1** | 棘轮红项是 U2 引入的 | 该测试只 `#include "battle_range_ui_style.h"`；基线快照（`git archive HEAD`）里**没有**这个文件 ⇒ 只可能由工作区的规则改动触发 | 成立 | **已确认** |
| **P-2** | 两条断言对同一组输入给出相反要求 | 逐字对拍 `test_battle_range_ui_phase_truth_table.cpp:155` 与 `test_battle_range_ui_style.cpp:197` | 成立（输入全同，只有期望不同） | **已确认** |
| **P-3** | 原版结算帧的青是**缓冲残迹**而不是活规则 | 目标选择帧零青（G-H15）⇒ 青在活帧里被相位门锁住；结算帧的青+橙只能来自未清缓冲 | 成立 | **已确认** |
| **P-4** | U2 的规则改动是 no-op | U2 自测：青+橙共现 0/783（前后同）、walk 相位 130 → 130 | 成立 | **已确认** |
| **P-5** | ⭐ 回退规则 ⇒ 棘轮恢复绿，且**不丢**任何可观测的还原度 | 跑全量单测；比对 U2 的实测读数 | 见 §3.1 | **已确认** |
| **P-6** | 回退后结算帧少青 ⇒ 残差变大？ | U2 已证明该规则在活帧里不产生可观测差异 ⇒ 像素读数不变 | 成立（推理，见 P-4） | **已确认（待波末判定台复核）** |
