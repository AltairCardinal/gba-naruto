# Butano Battle System Implementation Plan

状态：**已否决（2026-07-23）；历史方案，不得继续执行**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scenario 41 monolithic scripted battle with a fixed-capacity, testable battle domain that supports the original game's entrance, side phases, transactional unit actions, abilities, objectives, AI, and presentation sequencing.

**Architecture:** Build platform-independent header-only domain components under `konoha/`, verify them with host C++ tests, then migrate scenario 41 through a compatibility adapter before changing Butano rendering. Domain state owns rules; presentation owns BG/OBJ/audio; scenario data owns differences.

**Tech Stack:** C++23 host tests, C++20-compatible Butano/GBA code, Butano 21.7.1, fixed-capacity `std::array`, Python unittest integration checks, guarded mGBA runtime verification.

## 纠错状态（2026-07-23）

用户验收确认，这份计划产出的 scenario 41 是截图驱动的固定路线演示，不是完整战斗架构。虽然仓库中存在 `BattleSession`、行动资格、能力、目标和 AI 等类，也有宿主测试，但运行时仍以固定两个单位、单一 80 伤害动作、硬编码菜单分支和整屏捕获帧拼接可见流程；这些类没有消费 63 条单位、87 条主动动作、45 条被动、94 条忍具或原作完整控制器语义。因此旧结论“Tasks 1–7 已实现并验证”无效。

以下 Task 1–8 仅保留为失败方案的历史记录，不得继续勾选或据此扩展代码。重新实施必须先通过 `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md` 第 0 节的证据门槛，并另写基于完整内容真值、多场 ROM checkpoint 和实时组件渲染的新计划。

## Global Constraints

- Preserve existing user changes and the old scenario 41 route until the replacement reaches equivalent runtime evidence.
- Follow red-green-refactor for every behavior change; integration wiring requires a failing integration test first.
- No runtime heap allocation in battle domain code.
- Player and AI must use the same movement, eligibility, ability, effect, and objective services.
- Automatic black presentation steps must have finite duration; only visible steps may wait for input.
- Do not commit, stage, push, or delete generated evidence without explicit user authorization.
- All mGBA and high-cost build/static commands run through `tools/run_guarded.py` with the shared heavy lock.

---

## File Structure

- `butano-sequel/game/include/konoha/battle_session.h`: units, ledgers, side/round lifecycle, active action draft, and deterministic transitions.
- `butano-sequel/game/include/konoha/battle_commands.h`: command eligibility and rejection reasons.
- `butano-sequel/game/include/konoha/battle_presentation.h`: fixed presentation queue with automatic and visible-input steps.
- `butano-sequel/game/include/konoha/battle_abilities.h`: data-driven ability definitions, target queries, costs, and effect resolution.
- `butano-sequel/game/include/konoha/battle_objectives.h`: composable objectives and event-triggered evaluation.
- `butano-sequel/game/include/konoha/battle_ai.h`: legal draft generation and deterministic scoring.
- `butano-sequel/game/include/konoha/scenario_41_definition.h`: scenario 41 units, entrance timeline, abilities, objectives, and tutorial triggers.
- `butano-sequel/game/include/konoha/scenario_41_battle.h`: compatibility facade backed by the common domain.
- `butano-sequel/game/src/scenario_41_scene.cpp`: input/presentation/render wiring only.
- `butano-sequel/game/tests/test_battle_*.cpp`: host domain tests.
- `butano-sequel/game/tests/test_scenario_41_*.cpp`: scenario adapter and integration tests.
- `tests/test_butano_build.py`: source-wiring assertions that fail when Butano scene bypasses the common domain.
- `tools/butano/mgba_scenario_41_golden_route.lua`: runtime route updated only after the new visible flow is implemented.

---

### Task 1: BattleSession, Unit Ledger, and Turn Scheduler

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_session.h`
- Create: `butano-sequel/game/tests/test_battle_session.cpp`

**Interfaces:**
- Produces `battle_session<MaxUnits>`, `battle_unit_instance`, `battle_side`, `battle_lifecycle`, `unit_action_ledger`, `action_draft`, and `battle_transition`.
- `battle_session::select_unit(id)` starts a draft only for an active, unfinished unit on the current side.
- `battle_session::preview_move(point)` changes only the draft; `cancel_action()` restores the unit-select state without mutating the unit.
- `battle_session::commit_action(facing, defense_id)` applies the draft atomically, completes the unit, and advances side/round when required.

- [ ] **Step 1: Write the failing session test**

```cpp
battle_session<4> session;
assert(session.add_unit(player_one));
assert(session.add_unit(player_two));
assert(session.add_unit(enemy_one));
assert(session.start_round() == battle_transition::unit_selection_opened);
assert(session.select_unit(1) == battle_transition::action_draft_opened);
assert(session.preview_move({ 3, 4 }) == battle_transition::move_previewed);
assert((session.unit(1)->position == grid_point{ 2, 4 }));
assert(session.cancel_action() == battle_transition::unit_selection_opened);
assert((session.unit(1)->position == grid_point{ 2, 4 }));
```

- [ ] **Step 2: Verify red**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_session`

Expected: compile failure because `konoha/battle_session.h` does not exist.

- [ ] **Step 3: Implement the minimum fixed-capacity session**

```cpp
template<std::size_t MaxUnits>
class battle_session
{
public:
    bool add_unit(const battle_unit_instance& unit);
    battle_transition start_round();
    battle_transition select_unit(battle_unit_id id);
    battle_transition preview_move(grid_point destination);
    battle_transition cancel_action();
    battle_transition commit_action(battle_facing facing, ability_id defense);
    [[nodiscard]] const battle_unit_instance* unit(battle_unit_id id) const;
};
```

- [ ] **Step 4: Verify green and refactor**

Run the Task 1 command, then run all game host tests. Expected: all pass with no compiler warnings.

### Task 2: Command Eligibility

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_commands.h`
- Create: `butano-sequel/game/tests/test_battle_commands.cpp`

**Interfaces:**
- Produces `battle_command_type`, `command_availability`, `command_rejection`, and `command_eligibility_service::query(session, unit, command)`.
- Implements Move, Ability/Item, Replenish Chakra, Rest, and End Action without UI-specific menu indexes.

- [ ] **Step 1: Write failing eligibility tests**

```cpp
assert(query(unit, move).available());
unit.ledger.moved = true;
assert(query(unit, move).hidden());
unit.chakra = 0;
assert(query(unit, ability).reason == command_rejection::insufficient_chakra);
unit.hp = unit.max_hp;
assert(query(unit, rest).reason == command_rejection::full_health);
```

- [ ] **Step 2: Verify red**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_commands`

Expected: compile failure because the command service is missing.

- [ ] **Step 3: Implement query-only rules**

The service returns values and never mutates the session. UI menu order is built from visible query results.

- [ ] **Step 4: Verify green and all host tests**

Run Task 2 and the full game host suite.

### Task 3: Presentation Queue and Input Contract

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_presentation.h`
- Create: `butano-sequel/game/tests/test_battle_presentation.cpp`

**Interfaces:**
- Produces `presentation_step`, `presentation_mode`, `presentation_cue`, and `presentation_queue<Capacity>`.
- `push_automatic(cue, frames)` rejects non-positive durations.
- `push_wait_for_input(cue, visible)` rejects invisible input waits.
- `tick()` advances only automatic steps; `confirm()` advances only visible input steps.

- [ ] **Step 1: Write failing black-screen and dialogue tests**

```cpp
presentation_queue<8> queue;
assert(! queue.push_automatic(presentation_cue::black, 0));
assert(! queue.push_wait_for_input(presentation_cue::black, false));
assert(queue.push_automatic(presentation_cue::black, 12));
assert(queue.push_wait_for_input(presentation_cue::entrance_dialogue, true));
for(int frame = 0; frame < 12; ++frame) assert(queue.tick());
assert(queue.current()->mode == presentation_mode::wait_for_input);
assert(queue.confirm());
```

- [ ] **Step 2: Verify red**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_presentation`

- [ ] **Step 3: Implement the fixed circular queue**

Queue storage is `std::array`; overflow and invalid wait steps return false without modifying queue state.

- [ ] **Step 4: Verify green and all host tests**

Run Task 3 and the full game host suite.

### Task 4: Ability and Effect Pipeline

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_abilities.h`
- Modify: `butano-sequel/game/include/konoha/battle_effects.h`
- Create: `butano-sequel/game/tests/test_battle_abilities.cpp`
- Modify: `butano-sequel/game/tests/test_production_primitives.cpp`

**Interfaces:**
- Produces `ability_definition`, `target_rule`, `ability_cost`, `effect_node`, `ability_preview`, and `ability_resolver::resolve`.
- Extends effects with summon, capture, defense, substitute, and scripted event nodes while retaining atomic failure.

- [ ] **Step 1: Write failing tests for preview, chakra failure, multi-hit, summon, and substitution**

Each test asserts the complete before/after session and that failed resolution consumes no resource.

- [ ] **Step 2: Verify red**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_abilities test_production_primitives`

- [ ] **Step 3: Implement definition lookup, target validation, preview, and atomic resolver**

```cpp
ability_result resolve(
        battle_session_view before,
        battle_unit_id source,
        ability_id ability,
        grid_point target,
        deterministic_rng& rng);
```

- [ ] **Step 4: Verify green and all host tests**

Run Task 4 and the full game host suite.

### Task 5: Objectives, Interrupts, and Outcome Priority

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_objectives.h`
- Create: `butano-sequel/game/tests/test_battle_objectives.cpp`

**Interfaces:**
- Produces fixed expression nodes for all/any/not/count and predicates for defeated, alive, captured, position, facing, completed, round, and script variable.
- Evaluates only at declared `battle_domain_event` triggers and returns explicit victory/failure priority.

- [ ] **Step 1: Write failing tests matching scenarios 44, 46, 49, and 50**

Tests cover composite position/facing completion, immediate capture victory that skips the action tail, escort survival, and loss while escort HP remains positive.

- [ ] **Step 2: Verify red**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_objectives`

- [ ] **Step 3: Implement bounded expression evaluation**

Malformed expressions return configuration errors; they never silently resolve to victory.

- [ ] **Step 4: Verify green and all host tests**

Run Task 5 and the full game host suite.

### Task 6: Deterministic AI Using Shared Rules

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_ai.h`
- Create: `butano-sequel/game/tests/test_battle_ai.cpp`

**Interfaces:**
- Produces `ai_plan`, `ai_candidate`, and `battle_ai::plan(session, unit, objective, rng)`.
- Candidate generation calls the same pathfinder, eligibility, target, and effect preview APIs used by player input.

- [ ] **Step 1: Write failing legality and occupancy tests**

Tests prove every AI output is legal, occupied tiles alter paths, escort targets affect scoring, and no legal action ends the unit safely.

- [ ] **Step 2: Verify red**

Run: `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_ai`

- [ ] **Step 3: Implement deterministic candidate generation and scoring**

Tie-breaking order is stable unit ID, destination index, then ability ID.

- [ ] **Step 4: Verify green and all host tests**

Run Task 6 and the full game host suite.

### Task 7: Scenario 41 Definition and Compatibility Migration

**Files:**
- Create: `butano-sequel/game/include/konoha/scenario_41_definition.h`
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Modify: `butano-sequel/game/tests/test_scenario_41_initial.cpp`
- Modify: `butano-sequel/game/tests/test_scenario_41_movement.cpp`
- Modify: `butano-sequel/game/tests/test_scenario_41_turns.cpp`
- Modify: `butano-sequel/game/tests/test_scenario_41_victory.cpp`
- Modify: `butano-sequel/game/tests/test_scenario_41_golden_route.cpp`

**Interfaces:**
- Scenario 41 facade preserves `snapshot()` and `dispatch()` while delegating rules to common services.
- Entrance timeline is player appearance → enemy appearance → start title → finite black → visible dialogue → shuriken transition → unit selection.
- Enemy movement/attack is planned from current state; no turn-number coordinate teleports remain.

- [ ] **Step 1: Change the initial test to require visible entrance sequencing**

Confirming “start mission” must return `intro_opened`; repeated A during an automatic step is invalid; ticks advance automatic steps; A advances visible dialogue; unit selection appears only after the final automatic transition.

- [ ] **Step 2: Verify red against the current direct jump**

Run all `test_scenario_41_*` host tests. Expected: initial/golden route fail at the direct transition to `unit_select`.

- [ ] **Step 3: Add scenario data and migrate the facade incrementally**

Retain old result/level-up/postbattle presentation states until the common outcome pipeline reaches their tests.

- [ ] **Step 4: Verify green and all host tests**

Run the full game host suite.

### Task 8: Butano Scene Wiring and Runtime Evidence

**Files:**
- Modify: `butano-sequel/game/src/scenario_41_scene.cpp`
- Modify: `tests/test_butano_build.py`
- Modify: `tools/butano/mgba_scenario_41_golden_route.lua`
- Update: `notes/butano-scenario-41-one-to-one-runtime-20260722.md`
- Update: `docs/sequel-roadmap.md`

**Interfaces:**
- Scene translates keypad input to domain intents and renders the current `presentation_step` or `battle_snapshot`; it does not mutate HP, position, side, or objectives.
- Runtime manifest records ROM hash, input sequence, state boundaries, screenshots, audio state, and mGBA version.

- [ ] **Step 1: Add failing source-wiring tests**

Assert the scene ticks automatic entrance steps, routes A only to visible waits, handles L/R unit switching, and contains no turn-number enemy coordinate assignments.

- [ ] **Step 2: Verify red**

Run: `python3 -m unittest tests.test_butano_build -v`

- [ ] **Step 3: Wire Butano rendering and audio to the common domain**

Reuse existing map, cursor, HUD, attack, victory, result, and audio assets. Generate/import missing entrance frames from hash-bound original-ROM evidence before referencing them.

- [ ] **Step 4: Build with the shared resource guard**

Run the locked Butano build through `tools/run_guarded.py`; require exit 0 and a fresh ROM hash.

- [ ] **Step 5: Run guarded mGBA acceptance**

Verify cold start, complete entrance without black-screen input dependency, player action cancel/commit, enemy response, victory, result, and postbattle return.

- [ ] **Step 6: Run final regression and update persistent evidence**

Run formatting, all game host tests, relevant Python unit/integration tests, Butano build, and guarded runtime route. Record any unimplemented architecture boundary explicitly rather than marking the full battle system complete.
