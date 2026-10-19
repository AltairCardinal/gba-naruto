# Butano 战后主技能修炼页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在战斗胜利与等级结算后提供可操作的主技能修炼页，并让投入的修炼点通过现有 progression 链影响后续正式战斗目录。

**Architecture:** 新增独立 `battle_primary_training_flow` 管理角色/技能选择，所有写入委托给 `train_primary_action`。`battle_scene_controller` 只增加 training 阶段和只读快照，`battle_runtime_scene` 只渲染快照并路由按键。

**Tech Stack:** C++20、Butano、现有 `character_progression_record` / `train_primary_action` / `battle_scene_controller`、系统 Clang、devkitARM、mGBA。

## Global Constraints

- 严格复用 `train_primary_action`，不得在 flow、controller 或 renderer 复制扣点/升级规则。
- 列表显示全部非空主技能槽；锁定、未习得和不可成长项不得为了“可点”而隐藏。
- 只实现主技能修炼；副技能资格、章节 SRAM 存档和专属音频保持未完成边界。
- 所有行为变化先见 RED；触及 controller/input wiring 必须有集成测试。
- 不提交、不推送，不混入工作区其他已有改动。

---

### Task 1: 主技能修炼 flow

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_primary_training_flow.h`
- Create: `butano-sequel/game/tests/test_battle_primary_training_flow.cpp`

**Interfaces:**
- Consumes: `std::array<character_progression_record, 3>&`、`unit_definitions`、`train_primary_action`
- Produces: `battle_primary_training_snapshot`、`begin`、`cycle_action`、`cycle_character`、`confirm`

- [x] **Step 1: 写失败测试**

测试以 Naruto LV2、一个修炼点和已同步槽状态开始，断言目录保留全部非空主槽；选中 action 8
后确认应得到 `0→1`、修炼点 `1→0`。另测 action 2 满级、action 3 锁定、不可成长项、
空目录与两角色 L/R 循环都不产生越权写入。

- [x] **Step 2: 运行测试确认 RED**

Run:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game \
  test_battle_primary_training_flow
```

Expected: FAIL，原因是 `battle_primary_training_flow.h` 尚不存在。

- [x] **Step 3: 写最小 flow**

定义固定容量 15 的目录项：

```cpp
struct battle_primary_training_entry {
    std::uint8_t slot_index;
    ability_id action_id;
    std::uint8_t level;
    std::uint8_t unlock_level;
};
```

快照同时携带 participant index、entry index/count、training points、last error；
`confirm` 唯一写操作为：

```cpp
return train_primary_action(roster[participant_index], entry.slot_index);
```

- [x] **Step 4: 运行聚焦测试确认 GREEN**

Run Task 1 的同一命令，Expected: PASS。

### Task 2: 接入结果/升级 controller

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_scene_controller.h`
- Modify: `butano-sequel/game/tests/test_battle_scene_results.cpp`
- Modify: `butano-sequel/game/tests/test_battle_all_scenario_runtime.cpp`

**Interfaces:**
- Consumes: `battle_primary_training_flow`
- Produces: `battle_scene_phase::training`、`snapshot.training`

- [x] **Step 1: 扩展结果集成测试并确认 RED**

把 battle 41 的结果链期望从
`level_up → complete` 改为 `level_up → training → complete`；在 training 中选择
Naruto action 8，断言 roster 的对应槽 `0→1`、training points `1→0`，B/完成命令后才
进入 complete。

- [x] **Step 2: 运行 controller 测试确认 RED**

```bash
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game \
  test_battle_scene_results test_battle_all_scenario_runtime
```

Expected: FAIL，旧 controller 在 level_up 确认后直接 complete。

- [x] **Step 3: 最小接线**

在 controller load 时清空 training flow；level_up 确认时调用 `begin`，成功则进入
training，否则 complete。training 阶段：

- `move_cursor(0, ±1)` → `cycle_action`
- `cycle_unit(±1)` → `cycle_character`
- `confirm()` → `confirm`
- `cancel()` → complete

任何训练失败返回可观察的 training error，但 controller 自身保持可继续操作，不把合法拒绝
升级为 runtime error。

- [x] **Step 4: 运行聚焦测试确认 GREEN**

Run Task 2 的同一命令，Expected: PASS。

### Task 3: 可见页面、输入和遥测 wiring

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `tests/test_butano_single_battle_domain.py`

**Interfaces:**
- Consumes: `snapshot.training`
- Produces: `TRAINING` 标题、角色/技能/等级/点数文本、A/B/L/R 输入、训练遥测

- [x] **Step 1: 写失败的 wiring 断言**

Python 测试要求 runtime scene：

- training 阶段的 A 仍只调用 `controller.confirm()`；
- B 调用 `controller.cancel()` 并退出训练，而不是直接退出 ROM；
- L/R 复用 `controller.cycle_unit()`；
- 文本从 `state.training` 与身份目录构造；
- 遥测包含 training character、action、level、points 和 last error。

- [x] **Step 2: 运行 Python 测试确认 RED**

```bash
python3 -m unittest -v tests.test_butano_single_battle_domain
```

Expected: FAIL，尚无 training 页面与遥测字段。

- [x] **Step 3: 实现只读表现**

`phase_label` 返回 `TRAINING`。详情第一行显示角色名与剩余点数，第二行显示技能名和
`LOCK/NEW/LV1/LV2/MAX`，提示 `A:TRAIN B:DONE L/R:CHAR`。合法拒绝复用现有 60 帧
`INVALID INPUT` 可见反馈，并把精确 error 写入遥测。

- [x] **Step 4: 运行 wiring 与场景测试确认 GREEN**

```bash
python3 -m unittest -v tests.test_butano_single_battle_domain
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game \
  test_battle_primary_training_flow test_battle_scene_results \
  test_battle_all_scenario_runtime
```

Expected: 全部 PASS。

### Task 4: 全量验证与长期证据

**Files:**
- Modify: `notes/battle-action-progression-20260726.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`

**Interfaces:**
- Produces: RED/GREEN、host、ARM、mGBA run ID 与未完成边界

- [x] **Step 1: 运行全量 host C++ 和相关 Python**

使用 `tools/run_guarded.py` 包装全量宿主测试，保存唯一 manifest；运行内容生成、架构、
遥测 Lua 契约与文档测试。

- [x] **Step 2: 检查格式和生成内容**

运行 `git diff --check`、JSON 解析和生成文件一致性测试。

- [x] **Step 3: 经 heavy lock 构建 ARM**

使用项目固定 devkitARM/Docker 命令并由 `tools/run_guarded.py` 记录 ROM/ELF 哈希和 RSS。

- [x] **Step 4: 经 heavy lock 运行静音 mGBA**

从 battle 41 路线推进到结果、升级和 TRAINING；投入 action 8 的一点，遥测必须观察
action 8、`0→1`、points `1→0`，随后退出训练并继续既有场景链。自动化保持 mute，
不得宣称音频撕裂已修复。

- [x] **Step 5: 更新文档**

记录玩家入口、成功/失败/空状态、证据文件、ROM/ELF 哈希；明确章节 SRAM、副技能修炼、
专属技能演出和非静音音频仍未闭合。同步纠正 `reaction_state` 不得解释为禁行资格。
