# Butano Character and Action Architecture Implementation Plan

**Goal:** Make character identity, full per-character battle action lists, stats, and distinct real
skill outcomes observable through the existing battle architecture instead of scene-specific text or
screenshots.

**Architecture:** Generate a fixed identity/font content layer, project the existing action browser and
unit instances into value-only snapshots, and keep the Butano scene as a snapshot consumer. Prove the
shared flow with Naruto teleport and Sakura clone in battle row 9.

**Tech Stack:** C++20 fixed-capacity domain, Butano/devkitARM, Python 3/Pillow deterministic asset
generation, mGBA Lua state-driven acceptance.

## Global constraints

- Reuse `unit_definitions`, `battle_action_loadout`, `battle_action_catalog`,
  `battle_action_browser`, `battle_player_action_flow`, `battle_scene_controller` and existing effect
  handlers.
- No scene-side loadout construction, resolver calls, session writes, character-ID rules or screenshot
  menus.
- Follow RED → GREEN → REFACTOR for generator, host integration, source wiring and runtime script.
- Keep fixed capacities: 63 identities, 87 active actions, 19 visible battle actions, 12 battle slots.
- Run ARM builds and mGBA only through `tools/run_guarded.py`.
- Automated mGBA is muted and cannot validate audio.
- Do not stage, commit or push without separate authorization.

---

### Task 1: Generate identity content and UTF-8 sprite font

**Files:**
- Create: `tools/generate_butano_battle_identity_content.py`
- Create: `tests/test_generate_butano_battle_identity_content.py`
- Create: `butano-sequel/game/include/konoha/generated_battle_identity_content.h`
- Create: `butano-sequel/game/include/konoha/battle_identity_sprite_font.h`
- Create: `butano-sequel/graphics/battle_identity_font.bmp`
- Create: `butano-sequel/graphics/battle_identity_font.json`

- [x] Write a failing test for 63 ordered unit identities, 87 ordered active-action identities,
  confidence validation, unique UTF-8 glyph coverage and deterministic outputs.
- [x] Run the test and record RED because the generator and outputs do not exist.
- [x] Implement the deterministic generator using the two identity JSON sources, PingFang SC and the
  common 16×16 ASCII asset. Preserve raw-byte evidence only as provenance.
- [x] Generate files, run the test to GREEN, regenerate and prove byte-identical outputs.

### Task 2: Project complete action and character data

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_player_action_flow.h`
- Modify: `butano-sequel/game/include/konoha/battle_scene_controller.h`
- Modify: `butano-sequel/game/tests/test_battle_player_action_flow.cpp`
- Modify: `butano-sequel/game/tests/test_battle_scene_multi_unit.cpp`

- [x] Add failing assertions for all action menu entries and row 9 character level/stats.
- [x] Compile and run focused tests to record RED on missing snapshot fields.
- [x] Add pointer-free `battle_action_menu_view[19]`, synchronize it from the existing browser, add
  level/stats to `battle_scene_unit_view`, and clear stale action data when a new actor begins.
- [x] Run focused and full host C++ suites to GREEN; refactor duplicated snapshot-copy code only.

### Task 3: Wire real names and menus into the Butano scene

**Files:**
- Modify: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Modify: `tests/test_butano_build.py`

- [x] Add failing source-wiring tests requiring generated identity/font usage and forbidding renderer
  loadout construction plus `C# / ACTION #` identity placeholders.
- [x] Run the focused Python test to record RED.
- [x] Render selected unit name, level/stats and selected action name/index/cost/error from snapshot;
  render evidence-safe numeric names for ninja tools; extend telemetry with selected character and
  action selection fields.
- [x] Run source tests and host tests to GREEN; recompute and enforce the OAM/text budget.

### Task 4: Prove distinct skills in one shared turn flow

**Files:**
- Modify: `butano-sequel/game/tests/test_battle_scene_multi_unit.cpp`
- Create: `tools/butano/mgba_battle_09_character_actions.lua`
- Create: `tests/test_butano_battle_09_character_actions_runtime_script.py`

- [x] Add a failing controller integration route requiring Naruto's action 2 and Sakura's action 1 to
  follow the common selection/target/facing/defense path and produce different state changes.
- [x] Add a failing Lua contract test for state-driven character/menu/teleport/clone/active-9/round-2
  evidence.
- [x] Implement only missing generic flow fixes exposed by the integration test; do not add
  battle-ID or character-ID branches.
- [x] Implement the telemetry-driven Lua route with one input per event and unique evidence directory.
- [x] Run the host integration test and Lua source contract to GREEN.

### Task 5: ARM/runtime regression and durable documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `tools/README.md`

- [x] Run all host C++ programs with `-Wall -Wextra -Werror` and relevant Python tests.
- [x] Run guarded ARM build; inspect warning/error, ROM hash, ELF hash, IWRAM/EWRAM and sprite budget.
- [x] Run guarded row 9 character-action acceptance and existing row 41/43/9 regressions.
- [x] Inspect captured screenshots and manifests; persist exact hashes, state transitions, failures and
  remaining visual/audio/level boundaries.
- [x] Run `git diff --check` and report without staging, committing or pushing.

## Implementation evidence

The fixed action projection is a 10-byte `battle_action_menu_view`; the player-flow snapshot is
316 bytes and the 12-slot scene snapshot is 1,032 bytes. Returning snapshots by reference and
capturing only the selected action ID removed the ARM-only IWRAM stack overflow observed when target
confirmation nested several copied snapshots.

The guarded battle row 9 route completed at frame 994 with nine active units and round 2. It executed
Naruto action 2, Sakura action 1, browsed Sasuke actions `[2,5,16]`, and persisted evidence under
`artifacts/butano-character-actions-b09-20260725-03/`. Automated routes were muted and did not validate
audio.
