# Butano Scenario 42 Campaign Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use the repository TDD and
> verification workflow. Execution is inline because the user already selected
> inline execution. Repository policy forbids automatic commits.

**Goal:** Prove and, where the proof exposes a production mismatch, fix the
scenario 42 campaign stage from persisted scenario 42 through the shared battle
controller, victory settlement, verified SRAM save, and scenario 43.

**Architecture:** Reuse `battle_campaign_route`, `battle_runtime_controller`,
generated battle 42 formation/condition/reward content, campaign scene policy,
and the existing SRAM transaction. Extend the existing campaign-route mGBA
driver instead of adding a scenario-owned battle FSM. The driver may press
buttons and read telemetry, but it may not write battle or campaign memory.

**Tech Stack:** C++23 fixed-capacity domain code, Butano GBA runtime, Python
wiring tests, host `clang++`, devkitARM Docker build, mGBA Lua runtime probe.

## Global Constraints

- Scenario ID 42 resolves to battle ID 42 variant 0 through the existing route.
- Formation, conditions and reward values come from generated ROM-derived
  content; the test must not duplicate them as production constants.
- Victory must be produced by accepted player actions and the condition
  interpreter, never by telemetry or memory writes.
- The original-ROM evidence expects Naruto to remain level 2 and gain exactly
  110 EXP in this stage; the route must save scenario 43 only after SRAM
  verification.
- Existing scenario 41 behavior and save compatibility remain unchanged.
- Production changes follow a failing test for the intended behavior.

---

### Task 1: Host scenario 42 vertical slice

**Files:**
- Create:
  `butano-sequel/game/tests/test_battle_campaign_scenario_42.cpp`

**Interfaces:**
- Consumes: `battle_campaign_stage_for`,
  `battle_campaign_scene_policy`, `battle_runtime_controller`,
  `battle_condition_variants[42][0]`, and
  `battle_reward_record_for_scenario(42, 0)`.
- Produces: an executable regression that proves battle 42 loads from a
  level-2 Naruto campaign, executes real movement/action/condition transitions,
  settles 110 EXP, and advances the route to scenario 43.

- [x] Write the test with a controller driver that uses only public semantic
  operations (`confirm`, `move_cursor`, `tick`, `cancel`) and drains
  presentation events.
- [x] Run the isolated test and retain its first failing phase as evidence.
- [x] Fix only the production contract exposed by the failure; do not add
  scenario-specific HP writes or forced outcome APIs.
- [x] Re-run the isolated test until every assertion passes.

### Task 2: Extend the campaign-route ROM driver

**Files:**
- Modify: `tools/butano/mgba_battle_campaign_route.lua`
- Modify: `tests/test_butano_battle_campaign_route_runtime_script.py`

**Interfaces:**
- Adds optional environment variable
  `MGBA_BATTLE_CAMPAIGN_ROUTE_COMPLETE_STAGE=1`.
- Entry mode retains the existing scenario/battle 42 deployment assertion.
- Completion mode drives deployment, scripts, movement, action 5, facing,
  defense, enemy turns, result pages and training dismissal through GBA keys.

- [x] Add a failing Python contract test for completion mode, zero memory
  writes, scenario 43, 110 EXP and verified save assertions.
- [x] Run it and confirm failure because the driver has no completion mode.
- [x] Implement the state-driven input path using live telemetry rather than
  fixed-frame blind input.
- [x] Run the Python contract test and retain the passing result.

### Task 3: ARM and two-process campaign evidence

**Files:**
- Create runtime artifacts under a unique
  `artifacts/butano-battle-campaign-s42-complete-20260727-*` run ID.
- Modify:
  `notes/butano-battle-campaign-route-runtime-20260727.md`
- Modify:
  `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`

**Interfaces:**
- First process reuses the verified scenario-42 SAV, completes battle 42 and
  saves scenario 43.
- Second process cold-loads the resulting SAV and proves the visible controller
  is battle 43.

- [x] Run relevant Python tests and the isolated/full host C++ suites.
- [x] Build the final ARM ROM through `tools/run_guarded.py`.
- [x] Resolve telemetry symbols from that exact ELF and run both guarded mGBA
  processes.
- [x] Record ROM/SAV hashes, input/result telemetry, save verification, limits
  and any remaining fidelity mismatch in persistent documentation.
