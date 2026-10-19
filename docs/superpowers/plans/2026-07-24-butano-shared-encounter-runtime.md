# Butano Shared Encounter Runtime and Visible Scenario 43 Plan

> **Execution mode:** inline, red → green → refactor, no commit or push.

**Goal:** Replace scenario-owned battle orchestration with one data-driven encounter runtime used by both scenario 41 and scenario 43, then expose scenario 43 as a component-rendered runtime route whose units, clone, resources, turns, and outcome all come from the authoritative session.

**Architecture:** `battle_encounter_runtime<MaxUnits, Width, Height>` owns the session, immutable terrain, player action flow, AI turn flow coordination, condition variant, and RNG. `battle_scene_controller` converts semantic input into runtime operations and fixed-capacity snapshots. `battle_scene_presentation` consumes one-shot domain presentation events and produces movement/action poses. Scenario adapters provide generated scenario/map/condition IDs and optional command/action policies only. A Butano scene reads snapshots and poses and renders every active unit slot independently; it never writes combat state.

## Reuse decision

1. Reuse `battle_scenario_loader`, `battle_map_loader`, `battle_player_action_flow`, `battle_ai_turn_flow`, `battle_turn_flow`, and `battle_condition_interpreter` directly.
2. Extract ownership/orchestration only; do not duplicate action, movement, resource, AI, condition, or summon rules.
3. Append the runtime between generated content and scene adapters. Scenario 41 remains a story/presentation adapter but no longer owns a separate session/map/flow/RNG set.
4. Scenario-specific presentation remains separate because scenario 41 has tutorial/story cues and scenario 43 does not yet have recovered chapter scripts. This is a presentation boundary, not a second battle implementation.

## User-visible behavior

- Existing scenario 41 route remains the default and retains its current tutorial/ending flow.
- A documented developer route opens scenario 43 without replacing the default route.
- Scenario 43 shows one player and three enemies from generated formation data.
- Selecting action 7 and a legal empty tile creates a fifth active unit in a reserve slot; the renderer discovers it from the session snapshot.
- Enemy turns are executed one eligible unit at a time by the shared AI flow.
- HP, chakra, selected unit, command/action list, phase, round, and outcome are rendered from runtime state.
- Missing final character art uses an explicit side/slot marker; no actor screenshot is treated as authoritative game state.
- Story scripts and final art are outside this milestone and must remain labeled incomplete.

## Task 1: Shared runtime contract

- [x] Add a failing host test loading scenario 41 and 43 through the same type.
- [x] Assert atomic load failure, immutable terrain, centralized occupancy, fixed reserve slots, lifecycle, player flow, clone creation, three sequential enemy turns, and condition outcome propagation.
- [x] Implement the smallest runtime API that makes the test pass.

## Task 2: Migrate scenario 41 ownership

- [x] Add a failing source-wiring/host test that rejects direct scenario ownership of `BattleSession`, terrain, player flow, and RNG.
- [x] Replace those fields with `battle_encounter_runtime<2, 9, 22>`.
- [x] Preserve the existing golden route and presentation behavior.

## Task 3: Generic component scene for scenario 43

- [x] Add failing controller tests for semantic inputs and fixed-capacity snapshots.
- [x] Implement a controller that maps buttons to runtime operations without mutating units directly.
- [x] Add a Butano route and renderer that iterates active unit slots, including newly summoned clones.
- [x] Add a guarded mGBA script proving formation → clone → enemy unit sequence → next player round without screenshot-driven state.

## Task 4: Verification and durable evidence

- [x] Run focused and full host C++ suites.
- [x] Run focused Python/wiring/docs tests.
- [x] Run ARM build and inspect warnings/errors.
- [x] Run guarded mGBA acceptance and save screenshots/state/audit.
- [x] Update architecture, domain correction record, scenario guide, tool docs, and roadmap with exact evidence and remaining boundaries.

## Completion evidence

The shared-runtime milestone is complete, not the full restoration Goal. Scenario 43 now proves a second visible encounter on the same runtime: generated formation and map, action 7 clone creation, fixed reserve activation, three AI unit turns, presentation events, and return to player round 2. The final guarded evidence is `artifacts/butano-shared-runtime-scenario43-20260724-17/`; scenario 41 separately completes its 2,580-frame tutorial-to-postbattle golden route in `artifacts/butano-shared-runtime-scenario41-20260724-02/`. The final ARM build is `build/resource-guard/butano-shared-runtime-arm-build-s41-ewram-20260724-109.json`, ROM SHA-256 `8085dffcd7df4aeae0d6b07a31d27885f5f0f292ac4a67510596f95594e7aa5c`.

The planner is intentionally a non-inlined boundary on ARM. Inlining it produced a `0x2CE4`-byte turn executor whose return address became layout-sensitive; the stable split produces a `0x2054` planner and a `0x0AE8` turn executor. The runtime/controller objects are also static EWRAM residents and are reconstructed in place on encounter entry; placing scenario 41's runtime facade on the GBA call stack reproduced an entry hang. The final ELF uses 8,840 bytes of `.iwram`, 2,168 bytes of IWRAM `.bss`, and 70,748 bytes of EWRAM `.sbss`. Final art, scenario 43 chapter scripting, dynamic deployment UI, complete partial-collision semantics, AI resource/defense policies, and all 47 visible encounters remain outside this milestone.
