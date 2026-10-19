# Butano 两阶段行动提交与通用行动尾部实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正技能解析器过早完成单位行动的问题，使移动/技能效果原子提交后仍经过目标抢占、面向选择、防御准备和单位完成，再推进己方下一单位、敌方阶段或下一回合。

**Architecture:** `battle_action_resolver` 只提交不可撤销的移动、资源和效果，并把
`BattleSession` 推进到 `effects_resolved`；它不再设置面向、防御或 `ledger.completed`。
`BattleSession` 提供显式的 `open_facing_selection`、`select_facing` 和
`complete_action` 三段尾部 API。场景或后续通用 `BattleController` 只能在目标判定未抢占时
调用这些 API；玩家与 AI 使用同一尾部状态机。

**Tech Stack:** C++20 固定容量领域模型、系统 Clang 宿主测试、Butano 21.7.1、
devkitARM Docker、mGBA 0.10.5 script backport。

## Global Constraints

- 复用 `BattleSession`、`battle_action_resolver`、`battle_condition_interpreter` 和已有
  roster scheduler；不得另建关卡专用行动账本。
- 保留原 ROM 已验证顺序：`0x8000` 效果/打断 → `0x9000` 面向 →
  `0x9100/0x9200` 防御准备 → `0xD000` 单位完成。
- 效果失败时 session 必须完全不变；效果成功后资源/HP/位置不可取消，但单位尚未完成。
- 目标在 effects-resolved 边界成立时必须能结束战斗并跳过面向/防御。
- AI 可以自动选择面向和“无防御”，但必须调用与玩家相同的尾部 API。
- 不提交、不推送；保留工作区内所有既有改动。

---

### Task 1：以失败测试锁定正确的技能后状态

**Files:**

- Create: `butano-sequel/game/tests/test_battle_action_tail.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_session.h`
- Modify: `butano-sequel/game/include/konoha/battle_action_system.h`

**Interfaces:**

- Consumes:
  `battle_action_resolver::resolve_draft(...)`,
  `battle_session<MaxUnits>::draft()`.
- Produces:
  `battle_lifecycle::effects_resolved`,
  `battle_transition::effects_committed`,
  `battle_session<MaxUnits>::open_facing_selection()`,
  `battle_session<MaxUnits>::select_facing(battle_facing)`,
  `battle_session<MaxUnits>::complete_action(ability_id)`.

- [x] **Step 1: Write the failing action-tail test**

测试创建一个玩家和一个敌人，选择玩家、预览移动并执行非致死动作，然后断言：

```cpp
assert(result.success());
assert(session.lifecycle() == battle_lifecycle::effects_resolved);
assert(session.unit(1)->ledger.moved);
assert(session.unit(1)->ledger.acted);
assert(! session.unit(1)->ledger.completed);
assert(session.current_side() == battle_side::player);
assert(session.draft().active);
assert(session.open_facing_selection() ==
       battle_transition::facing_selection_opened);
assert(session.select_facing(battle_facing::right) ==
       battle_transition::defense_selection_opened);
assert(session.complete_action(7) == battle_transition::side_changed);
assert(session.unit(1)->ledger.completed);
assert(session.unit(1)->ledger.defense_ability == 7);
```

另测在 `effects_resolved` 状态不能再次 preview/resolve/cancel，非法尾部调用保持 session 不变。

- [x] **Step 2: Compile and verify RED**

Run:

```bash
/usr/bin/clang++ -std=c++20 -Ibutano-sequel/game/include \
  butano-sequel/game/tests/test_battle_action_tail.cpp \
  -o /tmp/test_battle_action_tail
```

Expected: FAIL because `effects_resolved` and the three action-tail APIs do not exist.

- [x] **Step 3: Split effect commit from unit completion**

In `battle_session.h`:

```cpp
enum class battle_lifecycle : std::uint8_t
{
    preparation,
    unit_select,
    action_drafting,
    effects_resolved,
    facing_select,
    defense_select,
};
```

Add private `commit_resolved_effects()` for the resolver. It applies the draft position and
`ledger.moved`, keeps the draft actor bound, and enters `effects_resolved`. Add public:

```cpp
battle_transition open_facing_selection();
battle_transition select_facing(battle_facing facing);
battle_transition complete_action(ability_id defense_ability);
```

`complete_action` alone sets `ledger.completed`, clears the draft, ticks side-end statuses and
returns `unit_completed` / `side_changed` / `round_advanced`.

In `battle_action_system.h`, remove both calls to `next.commit_action(...)`; after setting
`ledger.acted=true`, call `next.commit_resolved_effects()`. Resolver overloads no longer accept
or write facing.

- [x] **Step 4: Verify GREEN**

Compile, ad-hoc sign and execute `test_battle_action_tail`. Expected: PASS.

### Task 2：迁移共享 resolver 的所有调用者

**Files:**

- Modify: `butano-sequel/game/tests/test_battle_action_system.cpp`
- Modify: `butano-sequel/game/tests/test_battle_effect_handlers.cpp`
- Modify: `butano-sequel/game/tests/test_battle_summon_lifecycle.cpp`
- Modify: `butano-sequel/game/tests/test_battle_encounter_integration.cpp`
- Modify: remaining `butano-sequel/game/tests/test_*.cpp` resolver call sites as compiler reports

**Interfaces:**

- Consumes: Task 1 three-stage tail API.
- Produces: every test explicitly distinguishes effects committed from unit completed.

- [x] **Step 1: Compile the full host suite and record expected failures**

Run every `butano-sequel/game/tests/test_*.cpp`. Expected: old resolver overloads and assertions
that assumed immediate `ledger.completed` fail.

- [x] **Step 2: Update tests at real phase boundaries**

Tests that only inspect effect output stop before the tail. Tests that select another unit or
assert side/round changes explicitly execute:

```cpp
assert(session.open_facing_selection() ==
       battle_transition::facing_selection_opened);
assert(session.select_facing(facing) ==
       battle_transition::defense_selection_opened);
const battle_transition completed = session.complete_action(defense_ability);
```

Summoned units remain born with `ledger.completed=true` for the current round; only the summoner
waits in the tail. Do not weaken effect, atomicity, summon or condition assertions.

- [x] **Step 3: Run all host tests**

Expected: every C++ test program compiles, signs and exits 0 under `tools/run_guarded.py`.

### Task 3：接入目标抢占与多单位尾部

**Files:**

- Create: `butano-sequel/game/include/konoha/battle_turn_flow.h`
- Create: `butano-sequel/game/tests/test_battle_turn_flow.cpp`
- Modify: `butano-sequel/game/tests/test_battle_scenario_15_integration.cpp`

**Interfaces:**

- Consumes:
  `battle_condition_interpreter::evaluate_session`,
  Task 1 tail API.
- Produces:
  `battle_turn_flow_result after_effects(...)`,
  `battle_turn_flow_result complete_defense(...)`.

- [x] **Step 1: Write failing interruption and continuation tests**

Test two paths:

1. A nonlethal action yields no condition result, so `after_effects` opens facing, defense
   completion returns to the next player unit without changing side.
2. A lethal action satisfies the win condition at effects-resolved; `after_effects` returns
   `victory` and leaves lifecycle at `effects_resolved`, proving facing/defense were skipped.

Battle 15 additionally proves three players complete through the tail before the enemy phase;
enemy lethal damage to character 30 returns loss before enemy facing/defense.

- [x] **Step 2: Verify RED**

Expected: FAIL because `battle_turn_flow.h` does not exist.

- [x] **Step 3: Implement the stateless turn-flow coordinator**

`after_effects` validates `effects_resolved`, evaluates the supplied condition variant and:

- returns victory/failure/result-5 without mutating the action tail when the battle ends;
- otherwise calls `open_facing_selection`.

`complete_defense` validates `defense_select`, copies the session, calls `complete_action` on the
copy, evaluates conditions at the completed unit/side/round boundary, and only then atomically
replaces the real session. It returns both the session transition and outcome. Invalid condition
content returns a stable error while the real session remains unchanged.

- [x] **Step 4: Verify GREEN**

Compile and execute `test_battle_turn_flow` and the battle 15 integration test. Expected: PASS.

### Task 4：迁移 scenario 41 的玩家与 AI 尾部

**Files:**

- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Modify: `butano-sequel/game/tests/test_scenario_41_turns.cpp`
- Modify: `butano-sequel/game/tests/test_scenario_41_enemy_attack.cpp`
- Modify: `butano-sequel/game/tests/test_scenario_41_golden_route.cpp`
- Modify: `tests/test_butano_build.py`

**Interfaces:**

- Consumes: Task 1 tail API and Task 3 turn-flow coordinator.
- Produces: scenario 41 facade no longer simulates facing/defense outside the session.

- [x] **Step 1: Add failing source-wiring and behavior assertions**

Require:

- end-action confirmation calls `open_facing_selection`;
- facing confirmation calls `select_facing`;
- defense confirmation calls `complete_defense`;
- AI ability resolution auto-runs the same facing/defense tail;
- `scenario_41_battle.h` contains no `commit_action(` call.

- [x] **Step 2: Verify RED**

Run focused scenario 41 C++ tests and `tests.test_butano_build`. Expected: source-wiring test
fails because scenario 41 still delays all session mutation until its private `_wait`.

- [x] **Step 3: Wire the shared tail**

Move session transitions to their corresponding visible confirmations. `_combo` invokes
`after_effects`; victory interrupts the tail. `_run_enemy_turn` resolves or waits, opens facing,
selects deterministic facing, completes with no defense ability, then advances the round.
Presentation remains read-only.

- [x] **Step 4: Verify GREEN**

Run all scenario 41 host tests. Expected: existing visible route remains unchanged while session
phase and ledger now match each visible step.

### Task 5：文档与目标机验收

**Files:**

- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `tests/test_butano_research_docs.py`

**Interfaces:**

- Consumes: red/green logs, host suite, ARM ROM and mGBA route.
- Produces: persistent two-phase transaction evidence and remaining defense-effect boundary.

- [x] **Step 1: Write failing documentation assertions**

Require the architecture and evidence notes to record:

- resolver never completes a unit;
- effects-resolved can interrupt the tail;
- facing and defense are session transitions;
- defense selection is stored, while its complete incoming-attack reaction semantics remain a
  separately tracked boundary until all relevant action categories are wired.

- [x] **Step 2: Update documents and verify GREEN**

Record exact test counts, guard summaries, ROM/ELF hashes and mGBA artifact hashes. Do not claim
audio quality from muted automation.

- [x] **Step 3: Run final verification**

Run:

- all host C++ test programs under the shared heavy guard;
- targeted Python generation/build/document tests;
- `git diff --check`;
- fixed devkitARM Docker build;
- signed mGBA 2580-frame golden route with a new run ID and success marker.

Goal remains active after this plan: complete defensive reaction consumption, replenish/rest
formula/content, map collision/object initialization, chapter scripts and multi-scenario visible
routes are still required before full battle-system completion.
