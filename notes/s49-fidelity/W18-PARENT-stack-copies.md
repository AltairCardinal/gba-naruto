# W18-PARENT —— 会话栈拷贝的全仓普查（13 处）与**嵌套覆盖**陷阱

> 2026-10-25 01:2x · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 数据源：W1 自己生成的 `.su`（`build/w18-w1/su/`）+
> 全仓 grep（`battle_session<...> X = Y;`）
> 关联：`notes/s49-fidelity/U1-d4-fix.md`（根因）·
> `notes/s49-fidelity/WAVE18-TASKS.md` §1（W1 任务书）
> 父代理裁决：`notes/s49-fidelity/W18-PARENT-ratchet-red.md` ·
> `notes/s49-fidelity/W18-PARENT-residual-structure.md`

---

## 0. 一句话结论

> ⭐ **全仓有 13 处「事务性会话拷贝」**（`battle_session<MaxUnits> next = session;`），
> 每处 **8,052 B**（`sizeof(battle_session<12>)`）。
> ⇒ 这是 D4 栈溢出的**同一个根因的 13 个实例**，不是一处。
> ⇒ 其中 **5 处在胜利收尾路径**上（`battle_turn_flow.h`）⇒ **只修攻击确认链不够**：
> 战斗打完那一刻照样溢出 ⇒ 「真实打完仗」仍然拿不到。
> ⇒ ⭐⭐ **且这些拷贝会嵌套存活**：`advance_empty_side` 持着自己的副本时
> 又调用 `resolve_battlefield_object_event`（它再拷一份）
> ⇒ **单个共享的 EWRAM 事务缓冲会被内层覆盖** ⇒ 工作区**必须可嵌套（≥2 个缓冲）**。

---

## 1b. ⭐ 精化：13 处里**只有 3 处在运行时**

**判据**：一个含 8,052 B 会话拷贝的函数，若在运行时被调用，它的栈帧必然 ≥ 8,052
⇒ **它必然以独立条目出现在 `.su` 里**（或被内联进一个 ≥ 8,052 的帧）。

`.su` 里 `battle_turn_flow` / `battle_action_system` / `battle_action_combinations` 的**全部**条目：

```
battle_turn_flow.h:48   advance_empty_side                    16880   ← 拷贝版（运行时）★R2
battle_turn_flow.h:125  complete_non_target_action_in_place      112   ← in_place（运行时）
battle_turn_flow.h:194  after_effects_in_place                   24   ← in_place（运行时）
battle_turn_flow.h:262  complete_defense_in_place               104   ← in_place（运行时）
battle_turn_flow.h:355  complete_defense_in_place               120   ← in_place（运行时）
battle_turn_flow.h:437  _resolve_battlefield_objects            712   ← 运行时
battle_action_system.h:685  resolve_area_draft_in_place         1496   ← in_place（运行时）
battle_action_system.h:759  resolve_battlefield_object_event    8088   ← 拷贝版（运行时）★R1
battle_action_system.h:899  resolve_draft_in_place               800   ← in_place（运行时）
battle_action_combinations.h:307  resolve                       9504   ← 拷贝版（运行时）★R3
```

⇒ ⭐ **运行时真正会炸的会话拷贝 = 3 处**：

| # | 站点 | 栈帧 | 归属 |
|---:|---|---:|---|
| **R1** | `battle_action_system.h:765` `resolve_battlefield_object_event` | 8,088 | W1 |
| **R2** | `battle_turn_flow.h:53` `advance_empty_side` | 16,880 | W1 |
| **R3** | `battle_action_combinations.h:320` `battle_action_combinations::resolve` | 9,504 | W1 |

⇒ 其余 10 处拷贝版**只被单元测试调用**（运行时走各自的 `_in_place` 变体）
⇒ **不用改**（改了没有运行时收益，只让 diff 变大）。

### 1b.1 ⭐ 由此得到的最小改动方案（**EWRAM 占用从 16,104 B 降到 8,052 B**）

* `battle_turn_flow.h` **已有** `_in_place` 变体写法
  （`complete_non_target_action_in_place` / `complete_defense_in_place` / `after_effects_in_place`），
  **唯一漏掉的就是 `advance_empty_side`**（它没有 in_place 变体 ⇒ 自己拷到栈上）。
* 而 `battle_encounter_runtime.h:929-936` 的 `advance_empty_side()` **没有用** `_transaction_session()`
  ⇒ 于是 `battle_turn_flow` 只好自己在栈上拷。
* ⇒ **最小改法**：
  1. 给 `battle_turn_flow` 加 `advance_empty_side_in_place(...)`；
  2. `battle_encounter_runtime::advance_empty_side()` 改成
     `_transaction_session()` + in_place 调用 + 成功后提交（照 `confirm_target()`（:764-786））。
* ⇒ ⭐ **R2 不需要新缓冲**（复用已有的 `battle_encounter_runtime::_transaction_workspace.session`）。
* ⇒ **新增 EWRAM 常驻只剩 1 个缓冲 = 8,052 B**（给 R1）⇒ **判定台残差风险减半**。

### 1b.2 嵌套深度重新确认

改完后：`_transaction_session()`（**缓冲 #1**，已存在）→ `advance_empty_side_in_place`
→ `_resolve_battlefield_objects` → `resolve_battlefield_object_event`（**缓冲 #2**，新建）
⇒ **恰好 2 层，两个缓冲生命周期不重叠** ✓
⇒ ⭐ 「单缓冲被内层覆盖」的陷阱在改完后自动消失，
**前提是 R1 的缓冲独立于 `battle_encounter_runtime::_transaction_workspace`**。

---

## 1c. 全仓普查：13 处会话拷贝

| # | 文件 : 行 | 所在函数 | 归属（wave 18） |
|---:|---|---|---|
| 1 | `battle_action_combinations.h:320` | `battle_action_combinations::resolve`（栈帧 **9,504**） | **W1** |
| 2 | `battle_action_system.h:670` | `battle_action_resolver::resolve_*`（草稿解析） | **W1** |
| 3 | `battle_action_system.h:765` | `battle_action_resolver::resolve_battlefield_object_event`（栈帧 **8,088**） | **W1** |
| 4 | `battle_action_system.h:881` | `battle_action_resolver::resolve_area_draft` | **W1** |
| 5 | `battle_defense_preparation.h:146` | `battle_defense_preparation::commit` | ⚠️ 无人认领 |
| 6 | `battle_player_action_flow.h:1206` | `battle_player_action_flow::confirm_target` | **W2** |
| 7 | `battle_player_action_flow.h:1722` | `battle_player_action_flow`（资源命令提交） | **W2** |
| 8 | `battle_resource_commands.h:176` | `battle_resource_commands::commit` | ⚠️ 无人认领 |
| 9 | `battle_turn_flow.h:53` | `battle_turn_flow::advance_empty_side`（栈帧 **16,880**） | **W1**（父代理追加） |
| 10 | `battle_turn_flow.h:110` | `battle_turn_flow::complete_non_target_action` | **W1**（父代理追加） |
| 11 | `battle_turn_flow.h:182` | `battle_turn_flow::after_effects` | **W1**（父代理追加） |
| 12 | `battle_turn_flow.h:243` | `battle_turn_flow::complete_defense`（ability 版） | **W1**（父代理追加） |
| 13 | `battle_turn_flow.h:336` | `battle_turn_flow::complete_defense`（action_definition 版） | **W1**（父代理追加） |

> ⚠️ 第 5、8 号（`battle_defense_preparation.h` / `battle_resource_commands.h`）**无人认领**：
> 它们在**防御**与**资源命令（忍具）**路径上 ⇒ wave 19 的候选。

---

## 2. ⭐ 栈帧全景（`.su` 实测，帧 ≥ 1,000 B 的全部函数）

| 字节 | 函数 / 文件 | 路径 |
|---:|---|---|
| **16,880** | `battle_turn_flow::advance_empty_side`（`battle_turn_flow.h:48`） | **胜利收尾** |
| 9,736 | `battle_campaign_state` 拷贝（`battle_campaign_sram.h`） | 战役存档 |
| **9,504** | `battle_action_combinations::resolve`（`battle_action_combinations.h:307`） | **攻击确认（组合技）** |
| **8,088** | `battle_action_resolver::resolve_battlefield_object_event`（`battle_action_system.h:759`） | **战场物件结算** |
| 6,192 | `battle_condition_variant` 拷贝（`battle_conditions.h`） | 条件判定 |
| **6,136** | `run_visible_battle_scene`（`battle_runtime_scene.cpp:8066`） | **场景根（所有链的底座）** |
| 5,992 | `pathfinder_workspace`（`grid_pathfinder.h`） | 寻路 |
| **5,864** | `battle_action_resolver::preview_area`（`battle_action_system.h:574`） | **攻击确认（面积预览）** |
| 4,712 | `upgrade_ninja_tool`（`battle_campaign_sram.h`） | 战役 |
| 4,504 | `apply_battle_occupancy` | 战斗占位 |
| 4,464 | `std::array<battle_map_cell, 12151>` 拷贝 | 地图 |
| 4,360 | `battle_ai_plan_workspace`（`battle_ai_turn_flow.h`） | AI 回合 |
| 2,432 | `battle_scene_controller::tick()` | 场景 tick |
| 2,160 | `target_legal`（`battle_player_action_flow.h`） | 目标合法性 |
| 1,608 / 1,592 | 会话相关 | — |
| **1,496** | `resolve_area_draft_in_place`（`battle_action_system.h:685`） | 攻击确认 |
| 1,464 | 战役背包 | — |
| **1,424** | `_resolve_battlefield_object_event_in_place`（`battle_action_system.h:781`） | 战场物件 |
| **1,392** | `battle_action_combinations::_resolve_sequence`（`battle_action_combinations.h:496`） | 组合技 |

---

## 3. ⭐⭐⭐ 嵌套覆盖陷阱（**最容易被忽略、且症状最隐蔽**）

### 3.1 事实

`battle_turn_flow.h:66`（`advance_empty_side` 内部）：
```cpp
if(! _resolve_battlefield_objects(next, transition, next_rng, result))
```
而 `battle_turn_flow.h:479-485`（`_resolve_battlefield_objects` 内部）：
```cpp
const action_result item =
        battle_action_resolver::
                resolve_battlefield_object_event(
                        session,        // ← 外层那个 next
                        *event, payload, rng);
```
而 `battle_action_system.h:765`（`resolve_battlefield_object_event` 内部）**自己又拷一份会话**。

⇒ **调用内层的那一刻，外层的会话副本还在用。**

### 3.2 后果

若事务工作区是**全局单例**：
外层把 `session` 拷进工作区 → 内层又用**同一个**工作区拷 `session`
⇒ **外层副本被内层覆盖** ⇒ 事务语义被破坏
⇒ 症状 = 「**结算结果偶发错乱**」，**不崩、不栈溢出**，最难查的一类 bug。

### 3.3 要求

* 工作区必须**可嵌套**：**≥ 2 个缓冲**（深度 2 够用，已知最大嵌套 = 2），
  或做成带 acquire/release 的**缓冲池**。
* ⛔ **切勿用「取模轮换」省缓冲**：嵌套返回顺序不保证 ⇒ 会串。
* 最大嵌套深度需要 W1 自己再核一遍：
  `battle_action_combinations::resolve` → `_resolve_sequence` →
  `battle_action_execution::resolve_in_place` → `resolve_area_draft_in_place`
  这条链里**有没有第二次拷贝**（有 ⇒ 深度 > 2 ⇒ 池子要更大）。

### 3.4 EWRAM 预算

2 个缓冲 = **16,104 B**；3 个 = 24,156 B。EWRAM 只有 256 KB，Butano 的 EWRAM 堆也在里面。
⇒ **必须同时盯判定台残差**（EWRAM 排布变化 ⇒ VRAM/OAM 分配顺序可能变 ⇒ 画面可能变）。
⇒ 残差变大 ⇒ **换方法**（细粒度回滚 / 只外层 EWRAM 化），**不要**接受。

---

## 4. 两条链的栈深算术（修复后应当成立）

**可用栈 = 21,308 B**（栈顶 `0x03007F00`，栈底 `0x03002BC4`）。

### 链 A —— 攻击确认

| 帧 | 字节 |
|---|---:|
| `run_visible_battle_scene` | 6,136 |
| `battle_scene_controller::confirm` | 896 |
| `_confirm_target` | 592 |
| `target_legal` | 2,160 |
| `battle_player_action_flow::confirm_target_in_place` | 808 |
| `battle_action_resolver::resolve_draft_in_place` | 800 |
| `resolve_area_draft_in_place` | 1,496 |
| `preview_area` | 5,864 |
| 小帧合计 | ≈ 560 |
| **合计** | **≈ 18,312** ✅（裕量 ≈ 3,000 B） |

> ⚠️ 前提：8,088 与 9,504 两个大帧已改成 EWRAM 工作区。
> 若组合技路径仍带 9,504 的旧帧 ⇒ 27,816 ❌ **必须一起改**。

### 链 B —— 胜利收尾

| 帧 | 字节 |
|---|---:|
| `run_visible_battle_scene` | 6,136 |
| `battle_scene_controller::tick` | 2,432 |
| `advance_empty_side` | 16,880 → **≈ 36**（修好后） |
| `resolve_battlefield_object_event` | 8,088 → **≈ 36**（修好后） |
| **合计** | **≈ 8,640** ✅（裕量 ≈ 12,600 B） |

> ⚠️ **修前** = 6,136 + 2,432 + 16,880 + 8,088 = **33,536** ❌
> ⇒ **这解释了为什么「战斗打完之后」还会炸**。

---

## 5. 给 W1 的追加（已发出）

`task_append` 到 `bg_5a4f3898-ed32-4025-adab-b7836da43324`：

1. 新增独占文件 `game/include/konoha/battle_turn_flow.h`（5 处拷贝）；
2. ⭐ **嵌套覆盖陷阱**（§3）；
3. EWRAM 预算与残差风险（§3.4）；
4. 判定问题扩成**两条链**都要 ≤ 21,308 B；
5. 新增验收项 **W1-5b：真实胜利**（战斗结束后场景帧必须继续推进，不许在胜利那一刻停死）。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **P-16** | ⭐ 全仓 13 处事务性会话拷贝，每处 8,052 B | grep `battle_session<\w+> \w+ = \w+;` | 成立（13 处，见 §1） | **已确认** |
| **P-17** | ⭐ 胜利路径有独立于攻击确认的溢出 | `.su`：场景 6,136 + tick 2,432 + `advance_empty_side` 16,880 + `resolve_battlefield_object_event` 8,088 = **33,536 > 21,308** | 成立 | **已确认** |
| **P-18** | ⭐ 两份会话拷贝会同时存活 | `battle_turn_flow.h:66` → `:479-485` → `battle_action_system.h:765` | 成立 | **已确认** |
| **P-19** | 单缓冲工作区会破坏事务语义 | P-18 + 单缓冲 ⇒ 内层覆盖外层 | 成立 | **已确认** |
| **P-20** | 至少 2 个缓冲即可（最大嵌套 = 2） | 已枚举所有 `_in_place` / 拷贝对的调用关系 | 成立（**W1 需再核一遍组合技链**） | **已确认（W1 复核中）** |
| **P-21** | 修好后两条链都 ≤ 21,308 B | 链 A ≈ 18,312、链 B ≈ 8,640 | 成立（算术） | **未验（待 W1 实测 `.su` + 运行时复测）** |
