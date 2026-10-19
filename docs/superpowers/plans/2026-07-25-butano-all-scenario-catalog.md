# Butano 全战斗内容目录实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立覆盖 47 场、141 个变体的跨表内容契约，使地图、部署、条件、角色、主动术、忍具和被动在进入通用战斗控制器前可被统一验证和查询。

**Architecture:** 新增只读 `battle_content_catalog`，直接消费既有生成数组，不复制场景规则。验证核心接受数组参数以便测试注入损坏数据，生产包装器再绑定生成内容；通用场景入口后续只按 `(battle_id, variant)` 获取同一份 `battle_content_entry`。

**Tech Stack:** C++20 固定数组、Butano/ARM GBA、宿主 `g++` 测试、Python `unittest` 构建接线测试。

## Global Constraints

- 所有行为变化遵循 RED → GREEN → REFACTOR；先观察正确原因的失败。
- 不新增场景专用规则，不复制地图、部署、条件、角色或技能数据。
- 验证器不得分配堆内存，不得修改生成内容。
- 生产入口只接受完整通过验证的目录条目。
- 不自动提交、暂存或推送。

---

### Task 1: 全库跨表验证契约

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_content_catalog.h`
- Create: `butano-sequel/game/tests/test_battle_content_catalog.cpp`

**Interfaces:**
- Consumes: `battle_scenario_definition`、`battle_map_definition`、`battle_map_cell`、`battle_condition_variant`、`unit_definition`、`action_definition`、`passive_definition`。
- Produces: `battle_content_catalog_result validate_battle_content_catalog(...)` 与绑定生成数组的 `validate_generated_battle_content_catalog()`。

- [x] **Step 1: 写入失败测试**

测试必须断言生产内容为 47 场、141 个变体、85 个非空变体、41 个部署占位符变体，并分别注入错误 battle id、地图切片越界、阻塞部署格、重复部署格、无效角色、无效主动术、无效被动和 unsupported condition。

- [x] **Step 2: 运行测试并确认 RED**

Run:

```bash
g++ -std=c++20 -Wall -Wextra -Werror -Ibutano-sequel/game/include butano-sequel/game/tests/test_battle_content_catalog.cpp -o /tmp/test_battle_content_catalog
```

Expected: FAIL，原因是 `konoha/battle_content_catalog.h` 尚不存在。

- [x] **Step 3: 实现最小验证器**

验证顺序固定为：数组规模和连续 ID → 地图切片与尺寸 → 每变体部署坐标/碰撞/重复/selector → 固定角色与角色动作/被动引用 → 条件类型与参数。错误结果携带 `battle_id`、`variant`、`slot`，调用者不依赖字符串。

- [x] **Step 4: 运行测试并确认 GREEN**

Run:

```bash
g++ -std=c++20 -Wall -Wextra -Werror -Ibutano-sequel/game/include butano-sequel/game/tests/test_battle_content_catalog.cpp -o /tmp/test_battle_content_catalog
/tmp/test_battle_content_catalog
```

Expected: PASS。

### Task 2: 通用场景条目查询

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_content_catalog.h`
- Modify: `butano-sequel/game/tests/test_battle_content_catalog.cpp`

**Interfaces:**
- Consumes: 已验证的生成目录与 `(battle_id, variant)`。
- Produces: `battle_content_entry`，同时返回 scenario、map、condition 指针，以及 `empty/fixed_roster/deployment_required` 分类。

- [x] **Step 1: 写入失败测试**

断言 battle 9 variant 0 为 `fixed_roster`，battle 32 variant 0 为 `deployment_required`，battle 0 variant 0 为 `empty`；越界 battle/variant 返回空条目。

- [x] **Step 2: 运行并确认 RED**

Run: Task 1 的宿主编译和执行命令。

Expected: FAIL，原因是查询接口或分类尚不存在。

- [x] **Step 3: 实现只读查询**

查询不得重新解释 ROM 字节，只引用同索引的生成 scenario/map/condition；分类仅扫描对应 12 个部署槽。

- [x] **Step 4: 运行并确认 GREEN**

Run: Task 1 的宿主编译和执行命令。

Expected: PASS。

### Task 3: 构建接线与 ARM 容量门

**Files:**
- Modify: `tests/test_butano_build.py`
- Modify: `butano-sequel/benchmark/include/konoha_bench/self_test.h`
- Modify: `butano-sequel/benchmark/src/self_test.cpp`

**Interfaces:**
- Consumes: `validate_generated_battle_content_catalog()`。
- Produces: 构建时接线断言和 ROM 启动时的无堆全库自检结果。

- [x] **Step 1: 写入失败的 Python/自检接线测试**

测试要求自检调用生成目录验证器，并要求生产代码不出现 battle 9/43 的目录数据复制。

- [x] **Step 2: 运行并确认 RED**

Run:

```bash
python3 -m unittest tests.test_butano_build -v
```

Expected: FAIL，原因是自检尚未接线。

- [x] **Step 3: 接入嵌入式自检**

把目录验证结果作为现有 foundation self-test 的一项；失败时保持现有 `BN_ASSERT` 启动门，不新增 UI 旁路。

- [x] **Step 4: 运行宿主、Python 与 ARM 构建**

Run:

```bash
python3 tools/run_guarded.py --kind static --run-id butano-all-scenario-catalog-host -- g++ -std=c++20 -Wall -Wextra -Werror -Ibutano-sequel/game/include butano-sequel/game/tests/test_battle_content_catalog.cpp -o /tmp/test_battle_content_catalog
/tmp/test_battle_content_catalog
python3 -m unittest tests.test_butano_build -v
python3 tools/run_guarded.py --kind build --run-id butano-all-scenario-catalog-arm -- make -C butano-sequel -j2
```

Expected: 全部 PASS，ROM/EWRAM/IWRAM 均不越界。

### Task 4: 通用入口与代表性运行时验证

**Files:**
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `tests/test_butano_build.py`
- Verify: `tools/butano/mgba_battle_09_character_actions.lua`
- Verify: `tools/butano/mgba_scenario_43.lua`
- Verify: `tools/butano/mgba_scenario_41.lua`

**Interfaces:**
- Consumes: `battle_content_entry`。
- Produces: 一个按目录条目启动共享控制器的入口；现有 battle 9/43 包装函数只提供选择和表现资源，不再复制内容索引。

- [x] **Step 1: 写入入口失败测试**

测试要求 battle 9/43 包装器通过目录查询获取 scenario/map/condition，并让遥测记录请求的 battle/variant；无效或空条目在创建控制器前拒绝。

- [x] **Step 2: 运行并确认 RED**

Run:

```bash
python3 -m unittest tests.test_butano_battle_09_character_actions_runtime_script tests.test_butano_build -v
```

Expected: FAIL，原因是生产入口仍直接索引三份生成数组。

- [x] **Step 3: 最小接线并回归**

保留现有地图表现资源边界，但场景/地图/条件领域数据必须全部来自 `battle_content_entry`。不得增加 battle-specific resolver、AI 或回合分支。

- [x] **Step 4: 构建并运行 mGBA**

通过 `tools/run_guarded.py` 启动静音 mGBA，复跑 battle 9 完整角色动作路线、scenario 43 召唤路线与 scenario 41 golden route；验收遥测的 battle id、单位数、技能 ID、敌方完成数和回合推进。

Expected: 三条路线通过，控制器与玩家错误均为 0。

### Task 5: 文档与完成审计

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `tools/README.md`

- [x] **Step 1: 记录全库契约与证据**

记录 47/141/85/41 的口径、错误边界、宿主/ARM/mGBA manifest 和尚未覆盖的地图表现、部署 UI、章节脚本。

- [x] **Step 2: 最终验证**

Run:

```bash
git diff --check
```

Expected: PASS；随后复核 Goal，只有完整战斗要求全部有直接证据时才可标记完成。
