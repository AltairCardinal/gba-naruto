# Butano Battle Campaign Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use the repository TDD and verification workflow. This plan is executed inline because the user explicitly selected inline execution. Repository policy forbids automatic commits, so commit steps are intentionally omitted.

**Goal:** Replace the production-only `41 → 43 → 9 → 11 → 32` fixture chain with a data-driven battle campaign route whose scenario-to-battle mapping and transitions are limited to the original-ROM sequence already proven by runtime checkpoints.

**Architecture:** `battle_campaign_route.h` owns a fixed-capacity, pure C++ table of scenario IDs, battle IDs, variants, successor scenarios and party policies. The visible scene adapter resolves the current stage into the existing `battle_runtime_scene_request`; the main loop applies a victory-only transition after the battle transaction commits, then saves the updated scenario ID. Diagnostic battle wrappers remain available to focused tests but have no production route ownership.

**Tech Stack:** C++23 fixed-capacity domain code, Butano GBA runtime, Python wiring tests, host `clang++`, devkitARM Docker build, mGBA Lua state probe.

## Global Constraints

- `battle_campaign_state.chapter_id` means original scenario ID, never battle ID.
- Only `battle_runtime_scene_exit::victory` advances the route.
- `defeat`, `draw` and `aborted` leave both the route and campaign transaction at the entry checkpoint.
- The route contains only mappings supported by existing original-ROM checkpoints:
  `41/41, 42/42, 43/43, 44/44, 45/45, 46/9, 47/13, 49/14, 50/15`.
- Scenario 48 is pure story and therefore has no battle node; the battle-only route advances from scenario 47 to scenario 49 without pretending to implement its dialogue.
- Scenario 56 is an out-of-table terminal sentinel after the currently evidenced slice. It must not silently restart or replay scenario 50.
- Team 7 activation at scenario 44 adds missing Sasuke and Sakura level-1 records without overwriting any existing progression, then selects party `{1, 2, 3}`.
- Existing unrelated working-tree changes are preserved.
- Production code is written only after the corresponding test has failed for the intended reason.

---

### Task 1: Pure campaign route contract

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_campaign_route.h`
- Create: `butano-sequel/game/tests/test_battle_campaign_route.cpp`

**Interfaces:**
- Produces: `battle_campaign_stage_definition`, `battle_campaign_route_result`, `prepare_battle_campaign_stage`, `resolve_battle_campaign_stage`, `advance_battle_campaign_stage`.
- Consumes: `battle_campaign_state`, `battle_runtime_scene_exit`.

- [x] Write a failing host test for the nine proven scenario/battle pairs, initialization `0 → 41`, scenario 47 skipping the non-battle scenario 48, victory-only advancement, terminal scenario 56, and Team 7 activation at scenario 44.
- [x] Run the isolated test and confirm failure because `battle_campaign_route.h` does not exist.
- [x] Implement the minimal constexpr route table and transactional helpers.
- [x] Run the isolated test and confirm all assertions pass.

### Task 2: Production scene adapter and main-loop ownership

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/src/main.cpp`
- Modify: `butano-sequel/game/src/scenario_43_scene.cpp`
- Modify: `tests/test_butano_battle_result_routing_wiring.py`
- Create: `tests/test_butano_battle_campaign_route_wiring.py`

**Interfaces:**
- Produces: `run_battle_campaign_stage(battle_campaign_state&)`.
- Consumes: `resolve_battle_campaign_stage`, the existing generic `run_battle_scene(request)`, and `advance_battle_campaign_stage`.

- [x] Write failing wiring tests requiring `main.cpp` to call the route adapter, forbidding the fixture chain from `main.cpp`, and requiring stage advancement before verified SRAM save.
- [x] Run the wiring tests and confirm they fail against the hard-coded fixture path.
- [x] Add the generic route adapter, migrate the main loop, and remove sequential route ownership from `scenario_43_scene.cpp`.
- [x] Run the wiring tests and the affected host tests.

### Task 3: Observable persistence and ROM proof

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_campaign_sram.h`
- Modify: `butano-sequel/game/src/battle_campaign_sram.cpp`
- Modify: `tools/butano/mgba_battle_41_shared_runtime.lua`
- Create: `tools/butano/mgba_battle_campaign_route.lua`
- Modify: `tests/test_butano_battle_campaign_runtime_script.py`
- Create: `tests/test_butano_battle_campaign_route_runtime_script.py`

**Interfaces:**
- Extends the campaign telemetry at the tail with `scenario_id` and `route_complete`, preserving all existing offsets.
- The first probe proves battle 41 victory saves scenario 42.
- The second probe cold-loads that SRAM, leaves preparation, and proves the next visible controller is battle 42 rather than any fixture.

- [x] Write failing tests for the new telemetry fields and Lua assertions.
- [x] Run them and confirm the missing fields/scripts are the failure reason.
- [x] Add telemetry capture and both runtime assertions.
- [x] Run Python tests, the full host suite and the ARM build.
- [x] Resolve fresh ELF telemetry addresses, run both guarded mGBA probes, and retain unique artifacts.

### Task 4: Persistent evidence

**Files:**
- Create: `notes/butano-battle-campaign-route-runtime-20260727.md`
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`

- [x] Record the original-ROM mapping evidence, TDD red/green commands, hashes, telemetry addresses and runtime manifests.
- [x] State explicitly that story presentation, scenario 48 dialogue, later scenario mappings, per-skill presentation and audio remain outside this milestone.
- [x] Run documentation tests and `git diff --check`.
