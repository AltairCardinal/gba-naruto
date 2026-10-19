# Butano 通用 AI 单位回合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将敌方“选人 → 完整技能/忍具目录 → 规划 → 移动 → 效果 → 朝向 → 回合尾”
从 `scenario_41_battle` 抽成可供后续关卡复用、失败时零写的应用层流程。

**Architecture:** `battle_ai_turn_flow` 接收只读地图、关卡目标与 condition，复制
`BattleSession` 和 RNG，在副本中通过 `battle_action_browser`、`battle_ai`、
`battle_action_execution`、`battle_turn_flow` 完成一个单位的整次行动，全部成功后才提交。
AI 候选保存主动技能/忍具来源与忍具槽，避免相同 action ID 在两套目录中发生身份碰撞。

**Tech Stack:** C++20 固定容量模板、Butano 21.7.1、宿主 assert 测试、devkitARM、
受资源守卫的 mGBA 0.10.5。

## Global Constraints

- 不复制角色学习等级、动作成本、目标或效果规则；AI 必须消费共享角色目录。
- 不在 planner 或 presentation 中改写真实 `BattleSession`。
- 无合法动作时仍要完成移动/结束、朝向和无防御回合尾。
- 本里程碑只实现已有证据支持的 AI 无防御默认；AI 防御决策保持后续独立边界。
- 不提交 Git commit；用户未授权提交。

---

### Task 1: AI 候选保存动作来源身份

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_ai.h`
- Modify: `butano-sequel/game/tests/test_battle_ai.cpp`

**Interfaces:**
- Produces: `ai_candidate::action_kind` 与 `ai_candidate::tool_slot`
- Consumes: `action_definition::cost.kind`、`action_definition::cost.tool_slot`

- [x] **Step 1: 写失败测试**

在 `test_battle_ai.cpp` 构造相同 action ID 的主动技能与忍具定义，令忍具候选得分更高，断言：

```cpp
assert(tool_plan.action_kind ==
       battle_action_source_kind::ninja_tool);
assert(tool_plan.tool_slot == 2);
```

- [x] **Step 2: 确认红测**

Run:

```bash
c++ -std=c++20 -Wall -Wextra -Werror \
  -Ibutano-sequel/game/include \
  butano-sequel/game/tests/test_battle_ai.cpp \
  -o /tmp/test_battle_ai && /tmp/test_battle_ai
```

Expected: FAIL，`ai_plan` 尚无动作来源字段。

- [x] **Step 3: 最小实现**

为 `ai_candidate` 增加：

```cpp
battle_action_source_kind action_kind =
        battle_action_source_kind::active_action;
std::uint8_t tool_slot = no_tool_slot;
```

每次产生 ability candidate 时从 cost 写入：

```cpp
candidate.action_kind =
        action.cost.kind ==
                action_cost_kind::battle_local_ninja_tool_slot ?
        battle_action_source_kind::ninja_tool :
        battle_action_source_kind::active_action;
candidate.tool_slot = action.cost.tool_slot;
```

- [x] **Step 4: 确认绿测**

重跑定向命令，Expected: PASS。

### Task 2: 事务式 `battle_ai_turn_flow`

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_ai_turn_flow.h`
- Create: `butano-sequel/game/tests/test_battle_ai_turn_flow.cpp`

**Interfaces:**
- Consumes:
  `battle_session<MaxUnits>&`、`grid_map<Width, Height>`、`battle_unit_id`、
  `ai_objective`、`battle_condition_variant`、`deterministic_rng&`
- Produces:
  `battle_ai_turn_flow_result execute(...)`

- [x] **Step 1: 写失败测试**

测试必须覆盖：

1. 玩家阵营 AI 控制鸣人装备忍具 1 于槽 2，目标在忍具距离内；执行后计划身份为
   `ninja_tool/1/2`，敌方 HP 降低，槽 2 消耗，单位完成。
2. scenario 43 固定 12 槽会话结束玩家行动后，以 unit 2 执行真实角色目录；
   规划目标是鸣人，移动不超过 move range，行动后仍保持 12 个稳定槽。
3. 非 AI actor、错误 side、无效地图或 condition 错误时，完整 session 与 RNG 行为不提交；
   session 必须逐字段相等。
4. 若 action 在 `EffectsResolved` 后触发 outcome，流程立即返回 outcome，不再伪造朝向/防御。

- [x] **Step 2: 确认红测**

Run:

```bash
c++ -std=c++20 -Wall -Wextra -Werror \
  -Ibutano-sequel/game/include \
  butano-sequel/game/tests/test_battle_ai_turn_flow.cpp \
  -o /tmp/test_battle_ai_turn_flow
```

Expected: FAIL，头文件不存在。

- [x] **Step 3: 最小实现**

结果类型保存：

```cpp
enum class battle_ai_turn_flow_error : std::uint8_t {
    none,
    invalid_phase,
    invalid_actor,
    action_browser_failed,
    planning_failed,
    execution_failed,
    turn_flow_failed,
};

struct battle_ai_turn_flow_result {
    battle_ai_turn_flow_error error;
    ai_plan plan;
    battle_turn_flow_result turn;
    battle_action_source_kind action_kind;
    ability_id action_id;
    std::uint8_t tool_slot;
    bool action_resolved;
};
```

`execute` 必须：

- 复制 session 和 RNG；
- 验证 actor active、AI control、当前 side；
- 在副本选择 actor，通过 `battle_action_browser` 只收集 `selectable()` 项；
- 将定义交给 `battle_ai::plan`；
- preview move 后以 `kind/id/tool_slot` 回查唯一目录项；
- ability 统一调用 `battle_action_execution::resolve` 与 `battle_turn_flow::after_effects`；
- 非 outcome 时选择面向并以 `no_ability` 完成防御尾；
- 全部成功才把副本和 RNG 赋回调用者。

- [x] **Step 4: 确认绿测并重构**

重跑定向测试；清除 scenario 专用常量和重复 resolver 分派后再重跑。

### Task 3: scenario 41 敌方适配

**Files:**
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Modify: `butano-sequel/game/include/konoha/scenario_41_definition.h`
- Modify: `butano-sequel/game/tests/test_scenario_41_ai.cpp`
- Modify: `tests/test_butano_build.py`

**Interfaces:**
- Consumes: `battle_ai_turn_flow::execute`
- Removes: scenario facade 内的 AI `select_unit`、动作数组扫描、resolver 与 turn-flow 直连

- [x] **Step 1: 写 source-wiring 红测**

要求 `scenario_41_battle.h` 包含并调用 `battle_ai_turn_flow`，且 `_run_enemy_turn` 不再直接出现：

```text
battle_action_resolver::resolve_draft
battle_action_resolver::resolve_area_draft
battle_turn_flow::after_effects
battle_turn_flow::complete_defense
scenario_41_enemy_actions
```

- [x] **Step 2: 确认红测**

Run:

```bash
/usr/bin/python3 -m unittest \
  tests.test_butano_build.ButanoBuildTest.test_scenario_41_enemy_uses_shared_ai_turn_flow
```

Expected: FAIL，facade 仍直接编排 AI。

- [x] **Step 3: 最小适配**

`_run_enemy_turn` 只调用共享 flow，将 result 映射为既有动画、outcome、教程与玩家回合事件。
删除不再使用的 `scenario_41_enemy_actions()`。

- [x] **Step 4: 回归既有用户流程**

Run:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py
/usr/bin/python3 -m unittest discover -s tests
```

Expected: 全部 PASS；scenario 41 黄金路线无新增隐藏 A。

### Task 4: 构建、运行与持久证据

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `docs/superpowers/plans/2026-07-24-butano-ai-turn-flow.md`

- [x] **Step 1: devkitARM 构建**

通过 `tools/run_guarded.py` 执行 Butano build，要求 exit 0 且无 warning/error；记录 ROM/ELF
SHA-256 与大小。

- [x] **Step 2: mGBA 回归**

通过同一 heavy lock 执行 scenario 41 黄金路线，要求 completion marker、44 张关键截图、
final state 和 guard manifest 完整；自动路线继续静音，不签发音频听感。

- [x] **Step 3: 文档验收**

记录共享 AI flow 的事务边界、scenario 43 与忍具证据，同时明确以下未完成边界：

- AI 防御动作选择；
- 查克拉补充/休息命令；
- 真实地图 tile/collision 到所有场景的 wiring；
- 关卡脚本、剧情打断和结果表现。

- [x] **Step 4: 格式与状态**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: diff check PASS；不提交、不回滚用户改动。
