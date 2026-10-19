# Butano Scenario 41 Mission Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make scenario 41 use reusable mission action rules and complete its original round-4 chase-and-taijutsu route through the shared battle controller.

**Architecture:** Mission rules are battle/variant data, separate from presentation scripts, AI utility configuration, and victory predicates. The shared controller stores the selected rule and passes its existing `battle_action_access_policy` into the player action flow; scenario 41 declares active action 5 as its only technique and disables ninja tools, while all unspecified battles keep unrestricted defaults.

**Tech Stack:** C++23 header-only battle domain, Python `unittest`, Butano 21.7.1/devkitARM, guarded mGBA 0.10.5 Lua acceptance.

## Global Constraints

- Do not add scenario-specific damage, coordinate, round, or victory branches.
- Reuse `battle_action_access_policy`; do not create a second action-filter implementation.
- Preserve dirty user changes and do not stage, commit, push, or reset.
- Follow red-green-refactor and verify the original round-4 result `100 + 50 + 0 = 150`.

---

### Task 1: Mission action rule data and controller wiring

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_mission_rules.h`
- Create: `butano-sequel/game/tests/test_battle_mission_rules.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_scene_controller.h`
- Modify: `butano-sequel/game/tests/test_battle_scene_controller.cpp`

**Interfaces:**
- Consumes: `battle_action_access_policy` and `battle_scene_controller::load(...)`.
- Produces: `battle_mission_rules_for(int battle_id, int variant)` and controller-owned mission rules.

- [x] **Step 1: Write failing domain and controller integration tests**

  Assert that battle 41 variant 0 allows only active action 5 and rejects ninja tools, an unrelated battle remains unrestricted, and opening the action menu through the shared controller exposes exactly action 5.

- [x] **Step 2: Run the focused tests and verify RED**

  Run:
  `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_battle_mission_rules test_battle_scene_controller`

  Expected: compile failure because `battle_mission_rules.h` and controller wiring do not exist.

- [x] **Step 3: Add the minimum rule table and pass the policy to the existing flow**

  Store the battle/variant-selected policy during `load()` and call
  `_runtime.open_action_selection(_mission_rules.action_access)` in the ability command branch.

- [x] **Step 4: Re-run focused tests and verify GREEN**

  Expected: both focused programs print `PASS`.

### Task 2: Original round-4 chase/result integration

**Files:**
- Modify: `butano-sequel/game/tests/test_battle_scene_results.cpp`
- Modify: `tools/butano/mgba_battle_41_shared_runtime.lua`
- Modify: `tests/test_butano_battle_campaign_runtime_script.py`

**Interfaces:**
- Consumes: generated formation AI config 2, shared movement/AI/action/condition/result flows.
- Produces: a deterministic round-4 route with action 5 and `150` total EXP.

- [x] **Step 1: Change the shared integration test to the original route and verify RED**

  Drive rounds 1–3 with movement/end-action choices, require round 4 before action 5, and assert bonus EXP 0, total EXP 150, level 2 EXP 0. The current round-2 fixture must fail these assertions.

- [x] **Step 2: Make only the minimum route/policy corrections**

  Do not gate victory by round. Let config-2 AI choose its positions and use the existing movement/action rules; adjust the acceptance driver to select the real route rather than attacking on round 2.

- [x] **Step 3: Verify focused C++ and Python GREEN**

  Run the focused host programs and the campaign/runtime Lua wiring tests; expected result is zero failures.

### Task 3: Full verification and durable evidence

**Files:**
- Modify: `notes/battle-result-progression-runtime-20260725.md`
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`
- Create: `notes/battle-scenario-41-mission-rules-runtime-20260727.md`

**Interfaces:**
- Consumes: Task 1–2 implementation and acceptance route.
- Produces: host/ARM/mGBA evidence linked to the persistent architecture record.

- [x] **Step 1: Run all host C++ tests and related Python tests under the resource guard**

  Expected: every selected test passes with no compiler warnings.

- [x] **Step 2: Build the ARM ROM under the resource guard**

  Expected: build exit 0 and fresh ROM/ELF SHA-256 values.

- [x] **Step 3: Run the scenario-41 route in guarded mGBA**

  Expected: battle 41, round 4, action 5, outcome/result chain, total EXP 150, remaining EXP 0, and zero controller/player errors.

- [x] **Step 4: Update architecture, evidence, and roadmap**

  Record the separation between presentation scripts, mission access rules, AI config, conditions, and result settlement, including remaining Goal boundaries.
