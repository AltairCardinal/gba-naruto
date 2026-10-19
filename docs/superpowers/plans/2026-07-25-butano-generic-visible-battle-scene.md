# Butano Generic Visible Battle Scene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the row-43-specific visible battle adapter with one fixed-capacity, data-configured scene runner and prove it with ROM row 9's 3v5 encounter.

**Architecture:** A compile-time `run_visible_battle_scene<Width, Height>` preserves exact GBA workspace sizes while taking battle/variant/condition/resource data from a scene config. ROM map reconstruction becomes battle-ID parameterized, and scenario wrappers contain no battle logic.

**Tech Stack:** C++20 header-only battle domain, Butano/devkitARM, Python 3 deterministic asset generation, mGBA Lua acceptance.

## Global Constraints

- Use the existing `battle_scene_controller`, `battle_encounter_runtime`, generated scenario/map/condition tables, action flows and AI flow.
- No heap allocation, dynamic containers, scene-side resolver calls or scene-side HP/position/resource writes.
- Every behavior change follows RED → GREEN → REFACTOR.
- Runtime/controller instances reside in EWRAM.
- mGBA and ARM builds run through `tools/run_guarded.py`.
- Automated mGBA is muted and cannot validate audio.
- Do not commit, stage or push unless separately authorized.

---

### Task 1: Parameterized ROM battle-map reconstruction

**Files:**
- Modify: `tools/butano/generate_scenario_41_assets.py`
- Modify: `tools/generate_butano_battle_runtime_assets.py`
- Modify: `tests/test_generate_butano_battle_runtime_assets.py`

**Interfaces:**
- Consumes: ROM map header rows from `tools.extract_tileset.read_map_entries`.
- Produces: `reconstruct_map(rom_path: Path, battle_id: int = 41) -> dict[str, object]` and deterministic row 9/41 BMP metadata.

- [x] **Step 1: Write the failing generator test**

Add assertions that `reconstruct_map(BASE_ROM, 9)` returns width/height 512×512, row 9 source hashes,
and that generated `battle_09_clean_map.json` identifies `map-row-9` and collision row 9. Retain the
existing no-argument row 41 assertions.

- [x] **Step 2: Run test to verify RED**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_generate_butano_battle_runtime_assets
```

Expected: FAIL because `reconstruct_map` does not accept battle ID and the row 9 files are not generated.

- [x] **Step 3: Implement generic reconstruction and row 9 generation**

Use the selected row's `width_tiles // 4` and `height_tiles // 2` for layout validation and tilemap
dimensions. Keep two metatile halves per coarse cell and the existing tile/palette bounds checks. Add a
small asset-spec loop in `generate_butano_battle_runtime_assets.py` that writes row 41 and row 9 clean
maps with the correct JSON provenance.

- [x] **Step 4: Verify GREEN and generated artifacts**

Run the focused unittest, generator, and unittest again. Expected: PASS and deterministic files:

```text
butano-sequel/graphics/battle_09_clean_map.bmp
butano-sequel/graphics/battle_09_clean_map.json
```

---

### Task 2: Multi-unit controller integration

**Files:**
- Create: `butano-sequel/game/tests/test_battle_scene_multi_unit.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_scene_controller.h` only if the failing test exposes a generic-controller defect.

**Interfaces:**
- Consumes: `battle_scene_controller<12, 16, 32>` and generated row 9 data.
- Produces: proven 3-player/5-enemy roster and phase behavior without a scene adapter.

- [x] **Step 1: Write the failing integration test**

Load row 9 variant 0 with twelve fixed slots. Assert 8 active units, P1/P2/P3 roster order, and that
ending one player's action leaves player phase while ending all three enters enemy phase. Tick E4–E8
sequentially and assert the final tick starts player round 2.

- [x] **Step 2: Run test to verify RED**

Compile with `-Wall -Wextra -Werror`, ad-hoc sign and execute. Expected: FAIL on any controller
assumption that only one player or three enemies exist; if it passes immediately, strengthen the test
with the missing semantic-input boundary before production changes.

- [x] **Step 3: Implement the minimal generic fix**

If RED exposes a defect, change only controller selection/phase code and retain runtime ownership.
Do not add battle-ID conditionals. If the existing controller already satisfies the stronger contract,
record it as reused behavior and make no production-domain edit.

- [x] **Step 4: Verify GREEN**

Recompile and execute the focused test, then run all host C++ programs.

---

### Task 3: Generic Butano scene runner and wrappers

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_runtime_scene.h`
- Create: `butano-sequel/game/src/battle_runtime_scene.cpp`
- Modify: `butano-sequel/game/src/scenario_43_scene.cpp`
- Modify: `butano-sequel/game/include/konoha/scenario_43_scene.h`
- Modify: `tests/test_butano_build.py`

**Interfaces:**
- Consumes: generated row data, `battle_scene_controller<12, Width, Height>`, Butano background/sprite items.
- Produces: `battle_runtime_scene_exit run_battle_09_scene()` and a row-43 wrapper using the same renderer/input loop.

- [x] **Step 1: Write failing source-wiring tests**

Require the generic scene files, `battle_runtime_scene_config`, `run_visible_battle_scene`, row 9 and
row 43 wrappers, row 9 background item, EWRAM controller storage, X/Y camera clamping and snapshot-only
rendering. Reject resolver/session ownership and reject a battle-logic-sized `scenario_43_scene.cpp`.

- [x] **Step 2: Run test to verify RED**

Run the focused `tests.test_butano_build` methods. Expected: FAIL because the generic scene does not exist.

- [x] **Step 3: Extract the common scene**

Move input routing, AI tick cadence, labels, sprite lifecycle, camera and presentation consumption into
`battle_runtime_scene.cpp`. Parameterize title, battle/condition IDs, dimensions, seed, load policy and
background item. Preserve row 43 behavior exactly. Add the row 9 wrapper and SELECT transition.

- [x] **Step 4: Verify GREEN and refactor**

Run focused source tests and the 57 host programs. Confirm scenario wrappers do not call resolver or
write unit state. Run `git diff --check`.

---

### Task 4: ARM and three-route runtime acceptance

**Files:**
- Create: `tools/butano/mgba_battle_09_multi_unit.lua`
- Create: `tests/test_butano_battle_09_runtime_script.py`
- Modify: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: built ROM and row 41/43/9 developer route.
- Produces: guarded evidence for actual 3v5 roster selection, side transition, five AI units and round 2.

- [x] **Step 1: Write failing Lua source test**

Require SELECT transition to row 9, screenshots for P1/P2/P3 selection, player completion boundary,
`AI DONE 1/5` through `4/5`, player round 2, final state, register audit and success marker.

- [x] **Step 2: Run test to verify RED**

Run the focused Python test. Expected: FAIL because the script does not exist.

- [x] **Step 3: Implement the guarded route**

Add only single-input frame events. Keep audio muted, save unique artifacts, record PC/LR/SP/KEYINPUT,
and do not infer success solely from elapsed frames.

- [x] **Step 4: Build and verify runtime**

Run guarded ARM build and inspect warning/error plus IWRAM/EWRAM sections. Run row 41, row 43 and row 9
mGBA routes with unique artifact directories. Confirm row 9 uses the ROM-reconstructed map and visible
`ACTIVE 8/12`, three distinct player selections, enemy progress out of five, and player round 2.

- [x] **Step 5: Persist evidence and run final suites**

Update architecture, roadmap, domain record and tool docs with exact hashes, guard summaries and
remaining boundaries. Run 57 host programs with `-Wall -Wextra -Werror`, focused Python suites, ARM
build, `git diff --check`, and inspect final screenshots.
