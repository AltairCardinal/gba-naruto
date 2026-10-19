# Butano Ninja Tool Inventory and Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and execute inline. Repository policy forbids automatic commits.

**Goal:** Add ROM-bound ninja-tool recipes, persistent campaign inventory, atomic upgrade transactions, and SRAM persistence.

**Architecture:** Keep battle action definitions independent from preparation recipes. Store direct-ID quantity arrays in a focused campaign inventory aggregate; execute upgrades against a draft campaign and commit only after all quantity and equipped-reference checks pass.

**Tech Stack:** Python content extraction/generation, C++20 constexpr domain code, Butano SRAM adapter, host C++ tests, unittest, ARM build, guarded mGBA.

## Global Constraints

- Preserve all existing dirty worktree changes.
- No commit, push, reset, checkout, or unrelated refactor.
- Every behavior change follows RED → GREEN → REFACTOR.
- mGBA and ARM/static-heavy commands use `tools/run_guarded.py` and the shared heavy lock.
- Base ROM and existing repository SAV files remain byte-identical.

---

### Task 1: Correct recipe semantics and generate C++ content

**Files:**
- Modify: `tools/extract_skill_templates.py`
- Modify: `sequel/content/skills/bank.json`
- Modify: `tools/generate_butano_battle_action_content.py`
- Modify: `butano-sequel/game/include/konoha/generated_battle_action_content.h`
- Test: `tests/test_extract_skill_templates.py`
- Test: `tests/test_generate_butano_battle_action_content.py`

**Interfaces:**
- Produces: `ninja_tool_upgrade_recipe { parent_tool_id, required_material_id, whitelist_0, whitelist_1 }`
- Produces: `ninja_tool_upgrade_recipes[94]`

- [x] Add tests requiring `required_material_id` and recipe rows 2, 5, 8.
- [x] Run focused Python tests and confirm failure because the old semantic/header remains.
- [x] Rename the extractor field, emit the independent recipe type/array, regenerate JSON/header.
- [x] Run focused tests and confirm pass.

### Task 2: Add campaign inventory and atomic upgrade service

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_campaign_inventory.h`
- Create: `butano-sequel/game/tests/test_battle_campaign_inventory.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_campaign.h`

**Interfaces:**
- Produces: `battle_campaign_inventory`
- Produces: `ninja_tool_upgrade_error upgrade_ninja_tool(battle_campaign_state&, ninja_tool_id, uint8_t equipped_character_id)`

- [x] Add domain tests for bag-only success, equipped replacement, every rejection, overflow, and no-mutation failure.
- [x] Compile the focused test and confirm missing API RED.
- [x] Implement direct-ID arrays and draft/validate/commit transaction.
- [x] Re-run focused test and confirm pass.

### Task 3: Persist inventory in save version 2

**Files:**
- Modify: `butano-sequel/game/include/konoha/battle_campaign_save.h`
- Modify: `butano-sequel/game/tests/test_battle_campaign_save.cpp`

**Interfaces:**
- Consumes: `battle_campaign_state.inventory`
- Produces: deterministic version-2 slot encoding/decoding

- [x] Extend round-trip and invalid-sentinel tests, including exact inventory offsets.
- [x] Run codec test and confirm inventory is lost or old payload constants fail.
- [x] Encode/decode both direct-ID arrays, bump version, validate index 0 and offsets.
- [x] Re-run codec and scene-result integration tests.

### Task 4: Wire defaults, telemetry, and next-battle projection

**Files:**
- Modify: `butano-sequel/src/main.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_campaign_sram.h`
- Modify: `butano-sequel/game/src/battle_campaign_sram.cpp`
- Modify: relevant Lua/Python campaign runtime tests
- Create: `butano-sequel/game/include/konoha/battle_preparation_flow.h`
- Create: `butano-sequel/game/include/konoha/battle_preparation_scene.h`
- Create: `butano-sequel/game/src/battle_preparation_scene.cpp`
- Create: `tools/butano/mgba_battle_preparation_upgrade.lua`

**Interfaces:**
- Produces: cold-load and save telemetry for one tool quantity and one material quantity

- [x] Add wiring/runtime tests that require inventory defaults and telemetry.
- [x] Confirm RED on missing fields/default quantities.
- [x] Initialize default owned quantities for default equipment and expose telemetry.
- [x] Implement the live preparation controller/renderer using the shared upgrade service.
- [x] Run host, ARM, guarded save/load two-process route.

### Task 5: Documentation and full verification

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`

- [x] Record RED/GREEN manifests, ROM/static addresses, save format, user path, boundaries and superseded semantic.
- [x] Run `git diff --check`.
- [x] Run all host C++ tests, related Python tests, clean ARM build, and guarded mGBA runtime.
- [x] Verify base ROM and repository SAV hashes remain unchanged.
