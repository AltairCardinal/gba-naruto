# Scenario 49 mGBA Victory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 scenario 47 的 generation 8 SAV 通过合法按键在真实 mGBA 中完成 battle 14，
验证任务友军、五敌、胜负、奖励、成长、SRAM 和 49→50，而不是只签发宿主纵切或入口截图。

**Architecture:** 保持现有 battle domain、controller、resolver、condition 和 campaign
不变。先在 telemetry 尾部追加完整单位运行态和资源选择预览，保留所有既有 ABI 偏移；
再让 scenario 49 的 Lua 驱动逐字复现已通过宿主纵切的“最低 HP 可达敌人、佐助豪火球、
查克拉不足时补充、小樱第二回合优先槽 5”输入策略。只有遥测证明领域层与宿主不一致时，
才另开红测修改生产行为。

**Tech Stack:** C++20 header-only battle domain、Butano/devkitARM、Python unittest、
mGBA Lua、`tools/run_guarded.py`。

## Global Constraints

- 不写 mGBA 内存；Lua 只允许读 telemetry、发送按键、写 artifact。
- 所有行为变更先红后绿；运行时 wiring 同时有 C++ ABI 测试和 Python/Lua 协议测试。
- 保留工作区已有改动，不提交、不 push。
- mGBA、Docker/ARM 构建和全量宿主测试均经 `tools/run_guarded.py` heavy lock。
- 每次运行使用新 run ID，不覆盖失败产物。

---

### Task 1: Append complete unit telemetry without breaking existing offsets

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/tests/test_battle_runtime_scene_gate.cpp`
- Test: `butano-sequel/game/tests/test_battle_runtime_scene_gate.cpp`

**Interfaces:**
- Consumes: `battle_scene_snapshot<12>::units` and `battle_player_action_flow_snapshot::resource_preview`.
- Produces: tail fields `unit_hp[12]`, `unit_chakra[12]`, `unit_side[12]`,
  `unit_control[12]`, `resource_preview_amount`, `resource_preview_maximum_amount`,
  `condition_outcome`.

- [x] **Step 1: Write the failing ABI test**

Append static assertions after the existing offset 616 fields:

```cpp
static_assert(
        offsetof(battle_runtime_scene_telemetry, unit_hp) == 620);
static_assert(
        offsetof(battle_runtime_scene_telemetry, unit_chakra) == 668);
static_assert(
        offsetof(battle_runtime_scene_telemetry, unit_side) == 716);
static_assert(
        offsetof(battle_runtime_scene_telemetry, unit_control) == 764);
static_assert(
        offsetof(
                battle_runtime_scene_telemetry,
                resource_preview_amount) == 812);
static_assert(
        offsetof(
                battle_runtime_scene_telemetry,
                resource_preview_maximum_amount) == 816);
static_assert(
        offsetof(
                battle_runtime_scene_telemetry,
                condition_outcome) == 820);
static_assert(sizeof(battle_runtime_scene_telemetry) == 824);
```

- [x] **Step 2: Run the gate and verify RED**

Run:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game test_battle_runtime_scene_gate
```

Expected: compile failure because the seven tail fields do not exist.

- [x] **Step 3: Add the tail fields and populate them**

Append the exact fields to the telemetry struct:

```cpp
std::uint32_t unit_hp[12] = {};
std::uint32_t unit_chakra[12] = {};
std::uint32_t unit_side[12] = {};
std::uint32_t unit_control[12] = {};
std::uint32_t resource_preview_amount = 0;
std::uint32_t resource_preview_maximum_amount = 0;
std::uint32_t condition_outcome = 0;
```

In `write_battle_telemetry`, clear all arrays for 12 slots, then fill each real unit from the public
snapshot. Write resource preview values from `state.player.resource_preview`; write outcome from
`state.outcome`. Do not move any existing field.

- [x] **Step 4: Run the gate and verify GREEN**

Run the same command. Expected: `PASS test_battle_runtime_scene_gate`.

---

### Task 2: Add an exact scenario 49 legal-input driver

**Files:**
- Modify: `tools/butano/mgba_battle_campaign_route.lua`
- Modify: `tests/test_butano_battle_campaign_route_runtime_script.py`
- Test: `tests/test_butano_battle_campaign_route_runtime_script.py`

**Interfaces:**
- Consumes: Task 1 telemetry tail at offsets 620–820 and generated battle 14 map.
- Produces: `scenario_49_drive_completion(battle)` and per-transition JSON trace files.

- [x] **Step 1: Write failing script-contract and map-fidelity tests**

The tests must require:

```python
for token in (
    "scenario_49_completion",
    "SCENARIO_49_MAP",
    "scenario_49_weakest_enemy",
    "scenario_49_planned_destination",
    "scenario_49_drive_completion",
    "unit.hp = emu:read32(",
    "unit.chakra = emu:read32(",
    "unit.control = emu:read32(",
    "resource_preview_amount =",
    "condition_outcome =",
):
    self.assertIn(token, script)
self.assertNotIn("emu:write", script)
```

Map fidelity must parse battle 14 from `generated_battle_map_content.h` and compare all 285 cells
against 19 rows of 15 `.`/`#` characters in `SCENARIO_49_MAP`.

- [x] **Step 2: Run the Python test and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_butano_battle_campaign_route_runtime_script
```

Expected: failure because scenario 49 driver and tail reads do not exist.

- [x] **Step 3: Implement the minimum legal-input driver**

The selection order must be:

```lua
if actor.character_id == 2 and actor.chakra < 2 and
        not scenario_49_replenished_sasuke then
    -- stay in place, choose COMMAND_REPLENISH_CHAKRA,
    -- cycle to resource_preview_maximum_amount, confirm
else
    local action =
        actor.character_id == 2 and actor.chakra >= 2 and
            ACTION_SASUKE_FIRE or ACTION_TAIJUTSU
    local enemy =
        actor.character_id == 3 and battle.round >= 2 and
            active unit 5 or
        scenario_49_weakest_enemy(
            battle, actor, action range)
    -- BFS over exact battle 14 terrain and occupied cells,
    -- move at most PLAYER_MOVEMENT_BUDGET,
    -- attack only when target is in range.
end
```

`scenario_49_weakest_enemy` matches the host comparator: reachable before unreachable; among
reachable choose lower HP then shorter distance; among unreachable choose shorter distance then lower
HP. ARM 上的同分敌方路线与宿主不同，因此驱动不写死宿主坐标序列：敌人多于两个时以
Naruto/Sasuke 守卫位保护任务友军，敌人降至两个后再追击；影分身是真实单位槽。最终
outcome 断言 `condition_outcome == win`、unit 4 active/HP positive、units 5–9 inactive、
round `<= 9`，并按 reward row 39 验证第 9 回合 bonus 为 0、成长和 campaign state。

- [x] **Step 4: Run Python/Lua checks and verify GREEN**

Run:

```bash
python3 -m unittest \
  tests.test_butano_battle_campaign_route_runtime_script
luac -p tools/butano/mgba_battle_campaign_route.lua
```

Expected: all Python tests pass and Lua parses.

---

### Task 3: Run full ROM victory and publish evidence

**Files:**
- Modify: `notes/butano-battle-scenario-49-allied-ai-runtime-20260727.md`
- Modify: `notes/evidence/butano-scenario-49-allied-ai-runtime-20260727.json`
- Modify: `docs/sequel-roadmap.md`
- Create: `artifacts/butano-battle-scenario-49-allied-ai-complete-20260728-<run>/`

**Interfaces:**
- Consumes: generation 8 SAV SHA-256
  `3f473ececd31485800c1d907ca7a9b97350fc74f354ffb5a9032ce349a9dbc88`.
- Produces: signed scenario 50 SAV, audit JSON, stage-complete screenshot, guard JSON and hashes.

- [x] **Step 1: Build ARM and resolve exact telemetry symbols**

Run guarded `tools/butano/build.sh butano-sequel`, then resolve
`konoha_battle_runtime_telemetry` and `konoha_battle_campaign_runtime_telemetry` from the exact ELF
with the pinned devkitARM image.

- [x] **Step 2: Run the full mGBA route**

Copy the exact ROM and generation 8 SAV to a new artifact directory. Run mGBA with
`COMPLETE_STAGE=1`, expected scenario 49/battle 14/next scenario 50, and the exact Task 1 addresses.
Expected: success marker, no `failure.txt`, `condition_outcome=win`, unit 4 survives, five enemies
inactive, result verified, SRAM generation 9 verified, scenario 50.

- [x] **Step 3: Run full verification**

Run guarded:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game
```

Also run all relevant Python tests, `luac -p`, JSON parsing and `git diff --check`.

- [x] **Step 4: Update durable evidence**

Replace the current “host-full-turn-and-rom-entry-passed” manifest status with a full-ROM-passed
status only after Step 2 succeeds. Record exact ROM/ELF/SAV/script hashes, telemetry addresses, round,
kill distribution, reward, progression, save generation, guard peak RSS, and superseded negative runs.
Keep audio explicitly unsigned because the route remains muted.

## Plan self-review

- Spec coverage: closes the exact outstanding boundary documented for scenario 49 without changing
  battle semantics merely to make automation pass.
- Placeholder scan: no TBD/TODO or unspecified test command remains.
- Type consistency: all telemetry names and offsets are identical across C++, Lua and tests.
- Scope: does not expand into scenario 50 gameplay, audio, or new combat presentation content.
