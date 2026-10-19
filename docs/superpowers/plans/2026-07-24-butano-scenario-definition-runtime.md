# Butano 数据驱动战斗场景定义实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把原 ROM 的 47 个地图头、47×3 套编成记录和既有 condition 内容接成
Butano 可消费的只读 `BattleScenarioDefinition`，并用 battle 15 的三主角、护送单位和
五敌部署证明同一 `BattleSession` 可以承载后续关卡。

**Architecture:** 生成器保留 ROM 原始 selector，不把 `0xFA–0xFF` 猜成角色 ID。
`fixed_character` 可以直接实例化；`deployment_placeholder` 必须由战前 roster 显式绑定。
装载器先构造临时候选会话，全部记录通过后才原子替换目标会话。场景定义只提供领域数据，
不包含 Butano BG、sprite、输入或音频对象。

**Tech Stack:** Python 3、C++20 固定容量数组、Butano 21.7.1、系统 Clang 宿主测试、
devkitARM Docker 构建。

## Global Constraints

- 所有生产行为先写失败测试，确认正确失败后再实现。
- 复用 `unit_definitions`、`battle_condition_variants`、`instantiate_unit` 和
  `BattleSession`；不得另建场景专用 HP、技能或胜负真值。
- 地图战斗格尺寸按已验证 loader 关系 `width / 4`、`height / 2` 生成。
- 编成记录 `selector <= 62` 是固定角色；`0xFA–0xFF` 保持部署占位符。
- 生成器遇到其他 selector、非法阵营、越界坐标或非整除地图尺寸时必须失败。
- 不提交、不推送，除非用户另行授权。

---

### Task 1：生成 47 场地图与编成内容

**Files:**

- Create: `tools/generate_butano_battle_scenario_content.py`
- Create: `tests/test_generate_butano_battle_scenario_content.py`
- Create: `butano-sequel/game/include/konoha/generated_battle_scenario_content.h`
- Create: `butano-sequel/game/include/konoha/battle_scenario_content.h`

**Interfaces:**

- Consumes: `sequel/content/maps/bank.json`,
  `sequel/content/positions/bank.json`.
- Produces:
  `load_scenario_content(root: Path) -> list[dict]`,
  `generate_header(scenarios: list[dict]) -> str`,
  `battle_scenario_definitions[47]`.

- [x] **Step 1: Write the failing generator test**

测试导入尚不存在的生成器，并断言：

```python
scenarios = load_scenario_content(ROOT)
self.assertEqual(len(scenarios), 47)
self.assertEqual((scenarios[41]["grid_width"], scenarios[41]["grid_height"]), (9, 22))
self.assertEqual(
    [(r["selector"], r["side"], r["x"], r["y"]) for r in scenarios[41]["variants"][0]],
    [(1, 0, 4, 10), (30, 1, 4, 4)],
)
self.assertEqual(len(scenarios[15]["variants"][0]), 9)
self.assertEqual(scenarios[32]["variants"][0][0]["selector_kind"], "deployment_placeholder")
```

- [x] **Step 2: Run the generator test and verify RED**

Run:

```bash
PATH=/usr/bin:/bin:/usr/sbin:/sbin /usr/bin/python3 \
  -m unittest tests.test_generate_butano_battle_scenario_content
```

Expected: FAIL because `tools.generate_butano_battle_scenario_content` does not exist.

- [x] **Step 3: Implement strict parsing and header generation**

生成以下领域形状：

```cpp
enum class scenario_selector_kind : std::uint8_t
{
    fixed_character,
    deployment_placeholder,
};

struct battle_scenario_unit_slot
{
    bool enabled;
    scenario_selector_kind selector_kind;
    std::uint8_t selector;
    battle_side side;
    grid_point position;
    battle_facing facing;
};

struct battle_scenario_definition
{
    std::uint8_t battle_id;
    std::uint8_t grid_width;
    std::uint8_t grid_height;
    std::uint32_t map_flags;
    std::array<std::array<battle_scenario_unit_slot, 12>, 3> variants;
};
```

`parameter & 3` 只映射为 `up/right/down/left`，完整 raw selector 与 variant 均保留。
空记录写成 `enabled=false`，固定数组顺序与 ROM `record_id` 一致。

- [x] **Step 4: Regenerate and verify GREEN**

Run:

```bash
PATH=/usr/bin:/bin:/usr/sbin:/sbin /usr/bin/python3 \
  tools/generate_butano_battle_scenario_content.py --root .
PATH=/usr/bin:/bin:/usr/sbin:/sbin /usr/bin/python3 \
  -m unittest tests.test_generate_butano_battle_scenario_content
```

Expected: PASS, generated header is byte-for-byte stable on a second run.

### Task 2：原子场景装载与显式动态部署

**Files:**

- Create: `butano-sequel/game/include/konoha/battle_scenario_loader.h`
- Create: `butano-sequel/game/tests/test_battle_scenario_loader.cpp`

**Interfaces:**

- Consumes:
  `battle_scenario_definition`,
  `unit_definitions`,
  caller-provided `battle_scenario_load_policy`.
- Produces:
  `battle_scenario_load_result load_battle_scenario(...)`.

- [x] **Step 1: Write the failing loader test**

测试要求：

```cpp
battle_session<21> session;
const auto result = load_battle_scenario(
        battle_scenario_definitions[15], 0, policy, session);
assert(result.error == battle_scenario_load_error::none);
assert(session.unit_count() == 9);
assert(session.unit_at(0)->character_id == 1);
assert(session.unit_at(3)->character_id == 30);
assert(session.unit_at(3)->control == battle_control::scripted);
assert(session.unit_at(8)->character_id == 35);
```

另测 battle 32 未提供占位符绑定时返回
`unresolved_deployment_placeholder` 且目标 session 完全不变；提供六个绑定后才能加载。

- [x] **Step 2: Compile and verify RED**

Run:

```bash
/usr/bin/clang++ -std=c++20 -Ibutano-sequel/game/include \
  butano-sequel/game/tests/test_battle_scenario_loader.cpp \
  -o /tmp/test_battle_scenario_loader
```

Expected: FAIL because `battle_scenario_loader.h` does not exist.

- [x] **Step 3: Implement minimal atomic loader**

策略接口包含：

```cpp
struct battle_scenario_load_policy
{
    std::array<std::uint8_t, 6> placeholder_characters;
    std::array<bool, 63> scripted_characters;
};
```

占位符索引严格为 `0xFF - selector`。固定和绑定后的 character ID 都必须小于
`unit_definitions.size()` 且模板 active。实例 ID 使用 `record_id + 1`，默认玩家阵营为
`player`、敌方阵营为 `ai`，策略命中的角色为 `scripted`。任何错误都只返回错误码，
不修改传入 session。

- [x] **Step 4: Verify GREEN and refactor**

Run:

```bash
/usr/bin/clang++ -std=c++20 -Ibutano-sequel/game/include \
  butano-sequel/game/tests/test_battle_scenario_loader.cpp \
  -o /tmp/test_battle_scenario_loader
/usr/bin/codesign --force --sign - /tmp/test_battle_scenario_loader
/tmp/test_battle_scenario_loader
```

Expected: PASS.

### Task 3：battle 15 护送关卡跨系统验收

**Files:**

- Create: `butano-sequel/game/tests/test_battle_scenario_15_integration.cpp`
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Modify: `butano-sequel/game/include/konoha/scenario_41_definition.h`
- Modify: `tests/test_butano_build.py`

**Interfaces:**

- Consumes: Task 2 loader、`battle_condition_variants[15][0]`、
  `BattleSession` 调度与 action resolver。
- Produces: 固定角色场景不再依赖手写 `instantiate_unit` 部署。

- [x] **Step 1: Write failing integration tests**

battle 15 测试从生成定义加载 9 个单位：

```cpp
assert(session.start_round() == battle_transition::unit_selection_opened);
assert(session.select_unit(4) == battle_transition::invalid);
assert(session.select_unit(1) == battle_transition::action_draft_opened);
```

将护送单位 4 设为 inactive 后：

```cpp
const auto outcome = battle_condition_interpreter::evaluate_session(
        session, battle_condition_variants[15][0]);
assert(outcome.outcome == battle_condition_outcome::loss);
```

scenario 41 构造测试要求角色 1/30 的坐标来自
`battle_scenario_definitions[41].variants[0]`，源码不再手写两个
`instantiate_unit(...)`。

- [x] **Step 2: Verify RED**

Run the two focused C++/Python tests. Expected: battle 15 test cannot find loader,
and source-wiring assertion fails because scenario 41 still hand-writes deployment.

- [x] **Step 3: Wire fixed formation loading**

`scenario_41_battle` 调用通用 loader 加载 battle ID 41、variant 0。教程技能过滤、
入口演出和当前 condition ID 保持独立，不把故事场景 ID、地图/编成 ID和 condition ID
强行合并。

- [x] **Step 4: Verify GREEN**

Run focused tests, then all `butano-sequel/game/tests/test_*.cpp`.
Expected: battle 15 调度/护送失败与 scenario 41 既有黄金路线测试全部通过。

### Task 4：证据、文档与目标机验证

**Files:**

- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`

**Interfaces:**

- Consumes: 生成清单、宿主测试、ARM ROM 和 mGBA 路线。
- Produces: 可审计的场景数据覆盖与剩余脚本边界。

- [x] **Step 1: Record exact evidence and boundaries**

记录 47 个地图、47×3×12 固定槽、固定角色/占位符数量、battle 15 的 9 单位部署、
生成输入哈希、测试数量和 ROM 哈希。明确剧情触发器、战中脚本及 47 张地图的 Butano
图形资产仍是后续工作。

- [x] **Step 2: Run final verification**

Run:

```bash
git diff --check
PATH=/usr/bin:/bin:/usr/sbin:/sbin /usr/bin/python3 -m unittest \
  tests.test_generate_butano_battle_scenario_content \
  tests.test_generate_butano_battle_condition_content \
  tests.test_butano_build \
  tests.test_butano_research_docs
```

再经 `tools/run_guarded.py` 执行全部宿主 C++ 测试、固定 devkitARM Docker 构建和
scenario 41 mGBA 黄金路线。

- [x] **Step 3: Completion boundary**

只有数据生成、battle 15 集成、scenario 41 迁移和三层验证都通过后，才声明本里程碑完成。
Goal 仍保持 active，直至剧情脚本、全部地图表现和多关卡自然路线均完成。
