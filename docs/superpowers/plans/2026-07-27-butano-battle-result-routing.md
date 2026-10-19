# Butano Battle Result Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixture-style `back/next_battle` escape hatch with a battle-owned result protocol so campaign state and later battle routing are driven only by resolved combat outcomes.

**Architecture:** `battle_scene_controller` remains the single-battle domain owner. The visible Butano scene translates only a completed controller outcome into `victory`, `defeat`, or `draw`; START is an explicit abort and SELECT is no longer a hidden level-skip command. `run_battle_scene` uses the result as a transaction boundary: only victory may merge battle progression and consumed tools into campaign state, and callers route forward only on victory.

**Tech Stack:** C++20 host tests, Butano GBA runtime, existing `battle_scene_controller`, `battle_campaign_scene_progression`, guarded ARM build and mGBA Lua probes.

## Global Constraints

- Preserve all unrelated dirty-worktree changes.
- Follow red-green-refactor; no production behavior change before a failing test.
- Do not commit, stage, push, or use destructive Git commands.
- Run mGBA and ARM builds only through `tools/run_guarded.py`.
- Keep scenario content data-driven; do not add scenario-specific screenshots or scene state machines.

---

### Task 1: Battle-owned result protocol

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_runtime_result.h`
- Create: `butano-sequel/game/tests/test_battle_runtime_result.cpp`

**Interfaces:**
- Consumes: `battle_condition_outcome`.
- Produces: `battle_runtime_scene_exit`, `battle_runtime_exit_for_outcome(outcome)`, `battle_runtime_exit_resolved(exit)`, `battle_runtime_exit_commits_campaign(exit)`, and `battle_runtime_exit_advances_campaign(exit)`.

- [x] **Step 1: Write the failing host test**

Test the exact truth table:

```cpp
assert(battle_runtime_exit_for_outcome(battle_condition_outcome::win) ==
       battle_runtime_scene_exit::victory);
assert(battle_runtime_exit_for_outcome(battle_condition_outcome::loss) ==
       battle_runtime_scene_exit::defeat);
assert(battle_runtime_exit_for_outcome(
               battle_condition_outcome::equal_slot_result) ==
       battle_runtime_scene_exit::draw);
assert(battle_runtime_exit_for_outcome(battle_condition_outcome::none) ==
       battle_runtime_scene_exit::aborted);
assert(battle_runtime_exit_commits_campaign(
        battle_runtime_scene_exit::victory));
assert(! battle_runtime_exit_commits_campaign(
        battle_runtime_scene_exit::defeat));
assert(! battle_runtime_exit_commits_campaign(
        battle_runtime_scene_exit::draw));
assert(! battle_runtime_exit_commits_campaign(
        battle_runtime_scene_exit::aborted));
```

- [x] **Step 2: Run RED**

Run:

```bash
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game test_battle_runtime_result
```

Expected: FAIL because `battle_runtime_result.h` and the result protocol do not exist.

- [x] **Step 3: Implement the minimal constexpr protocol**

Define four explicit exits:

```cpp
enum class battle_runtime_scene_exit : std::uint8_t
{
    aborted,
    victory,
    defeat,
    draw,
};
```

Map only resolved outcomes to resolved exits; `none` maps to `aborted`. Campaign commit and advancement return true only for `victory`.

- [x] **Step 4: Run GREEN**

Run the same command. Expected: PASS.

### Task 2: Make the visible battle scene obey the result protocol

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Create: `tests/test_butano_battle_result_routing_wiring.py`

**Interfaces:**
- Consumes: Task 1 result helpers and `battle_scene_snapshot::outcome`.
- Produces: A returns the resolved outcome only from `battle_scene_phase::complete`; START returns `aborted`; SELECT cannot skip battles; campaign merge happens only when `battle_runtime_exit_commits_campaign(exit)` is true.

- [x] **Step 1: Write the failing wiring test**

The test must assert:

```python
assert "allow_next_battle" not in runtime_header
assert "bn::keypad::select_pressed()" not in runtime_source
assert "battle_runtime_exit_for_outcome(state.outcome)" in runtime_source
assert "battle_runtime_exit_commits_campaign(exit)" in runtime_source
```

It must also reject an unconditional `scene_progression.commit`.

- [x] **Step 2: Run RED**

Run:

```bash
python3 -m unittest tests.test_butano_battle_result_routing_wiring -v
```

Expected: FAIL on the current `allow_next_battle`, SELECT gate, `back` completion, and unconditional commit.

- [x] **Step 3: Implement the minimal runtime wiring**

- Move `battle_runtime_scene_exit` ownership to Task 1’s header.
- Remove `allow_next_battle` and `battle_runtime_scene_next_gate`.
- Return `aborted` from invalid setup, deployment cancellation, and START.
- On A in `complete`, return `battle_runtime_exit_for_outcome(state.outcome)`.
- Merge scene progression into campaign only when `battle_runtime_exit_commits_campaign(exit)` is true.

- [x] **Step 4: Run GREEN and related host tests**

Run:

```bash
python3 -m unittest tests.test_butano_battle_result_routing_wiring -v
python3 tools/butano/run_cpp_benchmark_tests.py \
  --root butano-sequel/game \
  test_battle_runtime_result \
  test_battle_scene_results \
  test_battle_all_scenario_runtime
```

Expected: all PASS.

### Task 3: Route the fixture chain only from victory

**Files:**
- Modify: `butano-sequel/src/main.cpp`
- Modify: `butano-sequel/game/src/scenario_43_scene.cpp`
- Modify: `tests/test_butano_battle_result_routing_wiring.py`
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`
- Create: `notes/butano-battle-result-routing-runtime-20260727.md`

**Interfaces:**
- Consumes: `battle_runtime_exit_advances_campaign`.
- Produces: No later battle starts after abort, defeat, or draw; SRAM is saved only after a victory transaction changes campaign state.

- [x] **Step 1: Extend the wiring test and verify RED**

Require `main.cpp` and `scenario_43_scene.cpp` to call `battle_runtime_exit_advances_campaign` before any next battle. Run the Python test and confirm it fails on the old `next_battle` comparisons and unconditional fixture entry.

- [x] **Step 2: Implement minimal caller routing**

Capture the battle result in `main`; save and enter the later fixture chain only on victory. Update the chained fixture runner to continue only when each battle returns victory.

- [x] **Step 3: Run host verification**

Run:

```bash
python3 -m unittest tests.test_butano_battle_result_routing_wiring -v
python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game
git diff --check
```

Expected: all host tests PASS and no whitespace errors.

- [x] **Step 4: Build and verify the ROM**

Run the ARM build through `tools/run_guarded.py`, then run a guarded mGBA route that reaches battle 41 and confirms the battle remains interactive without SELECT acting as a skip command. Record ROM/ELF hashes and guard manifests in the note.

- [x] **Step 5: Persist the architecture boundary**

Document that:

- single-battle domain state comes from controller snapshots;
- presentation consumes events but cannot decide outcomes;
- campaign merge is a victory-only transaction;
- chapter routing consumes result protocol and never a hidden input shortcut;
- defeat/draw rollback remains the conservative policy until original-ROM evidence proves another persistence rule.
