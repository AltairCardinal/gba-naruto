# Butano ROM Map Runtime and Scenario 43 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the screenshot-derived battlefield and hard-coded obstacle list with a ROM-backed map/collision runtime that can load scenario 41 and scenario 43 through the same tested architecture.

**Architecture:** Generate one flat fixed-capacity collision-content bank from the 47 ROM map rows, preserve each original 16-bit cell word, and materialize it into the existing `grid_map` together with session-owned occupancy. Movement queries use directional passability masks and the presentation layer consumes a deterministic map image reconstructed from ROM resources; neither layer may invent terrain or unit state.

**Tech Stack:** Python 3.9 generators and `unittest`, C++20 header-only battle domain tests, Butano 21.7.1, GNU ARM toolchain, mGBA guarded runtime validation.

## Global Constraints

- Preserve all existing dirty-worktree changes; do not reset or overwrite unrelated files.
- Follow red → green → refactor for every behavior change.
- Do not commit, stage, or push without explicit user authorization.
- `rom/base.gba` SHA-256 must remain `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`.
- The ROM collision word is authoritative: low bits `1/2/4/8` describe up/right/down/left boundary directions, `0x000F` is fully closed, and runtime unit occupancy remains a separate layer.
- Rendering must never write HP, chakra, position, turn, objective, summon, or outcome state.
- Scenario-specific code may select content IDs, but may not recreate map cells, obstacles, or formations by hand.

---

### Task 1: Pin map collision semantics as durable evidence

**Files:**
- Create: `tools/analyze_battle_map_collision.py`
- Create: `tests/test_analyze_battle_map_collision.py`
- Create: `notes/battle-map-collision-semantics-20260724.json`
- Modify: `tools/README.md`

**Interfaces:**
- Consumes: `rom/base.gba`, map table `0x0853D910`, collision consumer `0x080698B4..0x08069D10`, occupancy writers `0x0806A9EC` and `0x0806AA38`.
- Produces: `analyze_collision_runtime(rom_path: Path) -> dict[str, object]`, including ROM identity, 47 row inventories, direction-bit bindings, full-block value, and occupancy overlay masks.

- [ ] **Step 1: Write a failing analyzer test**

  Assert the base ROM hash; 47 decoded rows; row 41 dimensions `9×22`; row 41 values `{0,1,3,7,15}`; direction bindings `{up:1,right:2,down:4,left:8}`; full block `15`; and occupancy masks `slot << 11` plus `side << 15`.

- [ ] **Step 2: Run the focused test and confirm red**

  Run:

  ```bash
  /usr/bin/python3 -m unittest tests.test_analyze_battle_map_collision -v
  ```

  Expected: import failure because `tools/analyze_battle_map_collision.py` does not exist.

- [ ] **Step 3: Implement the hash-gated analyzer**

  Decode each collision LZ stream through `tools.extract_tileset`, validate `width/4 × height/2 × 2`, pin the relevant Thumb halfwords and literal references, and return JSON-safe evidence. Reject any ROM whose hash, instructions, literals, row count, or decompressed length differs.

- [ ] **Step 4: Generate and verify durable evidence**

  Run:

  ```bash
  /usr/bin/python3 tools/analyze_battle_map_collision.py \
    rom/base.gba --output notes/battle-map-collision-semantics-20260724.json
  /usr/bin/python3 -m unittest tests.test_analyze_battle_map_collision -v
  ```

  Expected: all tests pass and the JSON names unresolved semantics explicitly instead of treating every nonzero value as an impassable cell.

### Task 2: Generate the 47-map collision content bank

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_map_content.h`
- Create: `butano-sequel/game/include/konoha/generated_battle_map_content.h`
- Create: `tools/generate_butano_battle_map_content.py`
- Create: `tests/test_generate_butano_battle_map_content.py`
- Create: `butano-sequel/game/tests/test_battle_map_content.cpp`
- Modify: `tools/README.md`
- Modify: `tests/test_butano_build.py`

**Interfaces:**
- Produces:
  - `battle_map_definition { battle_id, width, height, cell_offset, cell_count }`
  - `battle_map_cell { raw_attributes, directional_mask(), fully_blocked() }`
  - `battle_map_definitions[47]`
  - `battle_map_cells[N]`
  - `battle_map_cell_at(definition, point)`

- [ ] **Step 1: Write failing Python generation tests**

  Assert deterministic output, 47 contiguous definitions, exact row 41/43 equality, row 41 cell count `198`, exact values at `(3,8)=7`, `(5,8)=3`, `(1,13)=1`, border `(0,0)=15`, and total flattened cell count equal to the sum of all ROM row cell counts.

- [ ] **Step 2: Confirm Python red**

  Run:

  ```bash
  /usr/bin/python3 -m unittest tests.test_generate_butano_battle_map_content -v
  ```

  Expected: import failure for the missing generator.

- [ ] **Step 3: Implement the generator and domain types**

  Read and hash-check `rom/base.gba`; decode collision streams; emit the flat `std::array<battle_map_cell, N>` and 47 offset/count definitions. Preserve the full word while exposing only the proven low-nibble directional mask.

- [ ] **Step 4: Write and run the C++ content test**

  Assert safe bounds, exact row identities, `0xF` full blocks, partial masks remaining distinct, and no runtime allocation. Compile and run with the existing host-test flags.

- [ ] **Step 5: Regenerate and verify green**

  Run:

  ```bash
  /usr/bin/python3 tools/generate_butano_battle_map_content.py --root .
  /usr/bin/python3 -m unittest \
    tests.test_generate_butano_battle_map_content \
    tests.test_butano_build -v
  ```

  Expected: deterministic header matches the checked-in file and focused Python tests pass.

### Task 3: Materialize terrain and occupancy into the shared movement service

**Files:**
- Create: `butano-sequel/game/include/konoha/battle_map_loader.h`
- Create: `butano-sequel/game/tests/test_battle_map_loader.cpp`
- Modify: `butano-sequel/game/include/konoha/grid_pathfinder.h`
- Modify: `butano-sequel/game/tests/test_production_primitives.cpp`
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Modify: `butano-sequel/game/tests/test_scenario_41_golden_route.cpp`

**Interfaces:**
- Produces:
  - `grid_map::set_directional_mask(point, mask)`
  - `grid_map::directional_mask(point)`
  - `grid_map::can_step(from, to)`
  - `materialize_battle_map(definition, cells, map)`
  - `apply_battle_occupancy(session, map)`
- Consumes: generated row definition and active `BattleSession` unit positions.

- [ ] **Step 1: Write failing directional-path tests**

  Cover a fully closed cell, a one-sided up boundary, the reciprocal neighbor boundary check, an occupied destination, and an open alternate route. The test must fail because current pathfinding only reads `cost` and `occupied`.

- [ ] **Step 2: Confirm C++ red**

  Compile and run `test_production_primitives.cpp`; expected assertion failure on a path that crosses a directional boundary.

- [ ] **Step 3: Implement minimal directional path support**

  Add explicit direction bits and make both `compute_reachable_costs` and `find_path` call `can_step`. A step is legal only when source and target are in bounds, neither terrain cell is fully closed, the destination is not occupied, and neither side exposes the boundary bit for that edge.

- [ ] **Step 4: Write failing loader integration tests**

  Materialize scenario 41 and scenario 43 into `grid_map<9,22>`, assert terrain words are identical, then apply different sessions and assert only occupancy differs. Test invalid dimensions, units on blocked/out-of-bounds cells, and duplicate active positions as atomic failures.

- [ ] **Step 5: Implement the loader atomically**

  Build a candidate map, validate all active units, set occupancy centrally, then replace the destination map only on success. Never mutate the generated terrain bank.

- [ ] **Step 6: Replace scenario 41 hard-coded obstacles**

  `_movement_map()` must load `battle_map_definitions[41]` and apply `_session` occupancy. Remove the six-element obstacle array. Extend the golden-route test to prove a ROM `0xF` cell is unreachable and a partial boundary changes traversal without being flattened to cost zero.

- [ ] **Step 7: Run focused host tests**

  Compile and run map-content, pathfinder, loader, player-flow, AI-flow, and scenario 41 tests. Expected: all pass and no scenario source contains a hand-authored obstacle list.

### Task 4: Replace the screenshot-cleaned battlefield with ROM reconstruction

**Files:**
- Modify: `tools/generate_butano_battle_runtime_assets.py`
- Modify: `tests/test_generate_butano_battle_runtime_assets.py`
- Modify: `butano-sequel/graphics/scenario_41_clean_map.bmp`
- Modify: `butano-sequel/graphics/scenario_41_clean_map.json`
- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `docs/butano-scenario-41-battle.md`
- Modify: `docs/sequel-roadmap.md`

**Interfaces:**
- Consumes: `reconstruct_map(rom/base.gba)` from `tools/butano/generate_scenario_41_assets.py`.
- Produces: a padded `512×512` indexed Butano BG whose active `288×352` pixels come directly from ROM tile graphics, palette, layout, and metatile definitions.

- [ ] **Step 1: Write a failing asset provenance test**

  Assert every active pixel in `scenario_41_clean_map.bmp` equals `reconstruct_map(rom/base.gba)`, padding is transparent, and the known rock/shadow pixels erased by the old screenshot-cleaning process are preserved.

- [ ] **Step 2: Confirm asset test red**

  Run:

  ```bash
  /usr/bin/python3 -m unittest \
    tests.test_generate_butano_battle_runtime_assets -v
  ```

  Expected: the old screenshot-derived clean map differs from the ROM reconstruction.

- [ ] **Step 3: Generate the battlefield from ROM**

  Keep the independent unit sprite extraction path only for the sprite asset, but generate `scenario_41_clean_map.bmp` from decoded ROM resources. Record source hashes and dimensions in its JSON metadata.

- [ ] **Step 4: Verify focused assets and ARM build**

  Run the focused Python suites, regenerate graphics, and build the ROM through `tools/run_guarded.py`. Expected: exit 0, no compiler warnings, and a new deterministic ROM hash.

- [ ] **Step 5: Run guarded mGBA acceptance**

  Reuse the existing scenario 41 route, inspect screenshots at unit select, movement, target confirmation, enemy phase, and result. Verify terrain remains present while units/cursor move independently and the route no longer depends on a precomposited actor screenshot.

- [ ] **Step 6: Update durable status honestly**

  Record that the reusable map/occupancy foundation supports scenario 43 content loading, but do not claim scenario 43 visible scripting, all 47 renderer assets, or the complete battle system until those separate milestones pass runtime acceptance.

