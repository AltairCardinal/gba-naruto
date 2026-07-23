# Butano Scenario 41 Battle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a playable Butano recreation of Konoha Senki scenario 41, from battle intro through natural combo victory, result screen, and restart.

**Architecture:** A header-only, platform-independent `scenario_41_battle` owns all deterministic rules and is tested with the host C++ compiler. A thin Butano scene translates keypad input into commands and renders a generated 4bpp forest map, unit sprites, cursor, menus, feedback, and result pages. Existing benchmark pathfinding/effect semantics are promoted into production headers and retained through compatibility aliases.

**Tech Stack:** C++23, Butano 21.7.1, fixed-capacity STL/Butano containers, Python 3 deterministic 4bpp BMP generation, unittest, host clang++/g++, devkitARM Docker.

## Global Constraints

- Scenario facts are battle ID 41, grid 9×22, Naruto `(4,10)`, Iruka `(4,4)`.
- Functional equivalence is required; pixel-perfect graphics and original Japanese text are not.
- No heap allocation, exceptions, RTTI, filesystem access, or Butano types in the domain core.
- Every production behavior follows a witnessed RED → GREEN → REFACTOR cycle.
- Reuse existing pathfinder/effect semantics; do not introduce parallel algorithms.
- All heavy builds and mGBA runs use `tools/run_guarded.py` and `build/resource-guard/heavy.lock`.
- Do not commit or push without explicit user authorization.

---

## File Map

- `butano-sequel/game/include/konoha/grid_pathfinder.h`: production fixed-grid and deterministic pathfinder.
- `butano-sequel/game/include/konoha/battle_effects.h`: production transactional effect chain.
- `butano-sequel/game/include/konoha/scenario_41_battle.h`: complete platform-independent level state machine.
- `butano-sequel/game/tests/test_scenario_41_initial.cpp`: authoritative initial state and intro.
- `butano-sequel/game/tests/test_scenario_41_movement.cpp`: range, blocking, preview, commit, cancel.
- `butano-sequel/game/tests/test_scenario_41_turns.cpp`: WAIT and deterministic enemy phase.
- `butano-sequel/game/tests/test_scenario_41_victory.cpp`: invalid/valid combo, result, restart.
- `tools/butano/run_cpp_benchmark_tests.py`: host runner reused with `--root butano-sequel/game`.
- `tools/butano/generate_scenario_41_assets.py`: deterministic 4bpp BMP generator.
- `tests/test_butano_scenario_41_assets.py`: generated asset contract.
- `butano-sequel/graphics/scenario_41_map.{bmp,json}`: 256×512 tiled forest background.
- `butano-sequel/graphics/scenario_41_units.{bmp,json}`: 16×48 Naruto/Iruka/cursor sprite sheet.
- `butano-sequel/game/include/konoha/scenario_41_scene.h`: Butano scene interface.
- `butano-sequel/game/src/scenario_41_scene.cpp`: keypad mapping and rendering.
- `butano-sequel/src/main.cpp`: launch scene after embedded self-test assertion.
- `butano-sequel/Makefile`: add game sources/includes/graphics.
- `tests/test_butano_build.py`: ROM/ELF integration contract.
- `docs/butano-scenario-41-battle.md`: controls, behavior, limits, build and acceptance guide.
- `docs/sequel-roadmap.md`: durable status update.

---

### Task 1: Promote the Reusable Grid and Effect Core

**Files:**
- Create: `butano-sequel/game/include/konoha/grid_pathfinder.h`
- Create: `butano-sequel/game/include/konoha/battle_effects.h`
- Modify: `butano-sequel/benchmark/include/konoha_bench/grid_pathfinder.h`
- Modify: `butano-sequel/benchmark/include/konoha_bench/battle_effects.h`
- Test: existing `butano-sequel/benchmark/tests/test_grid_pathfinder.cpp`
- Test: existing `butano-sequel/benchmark/tests/test_battle_effects.cpp`

**Interfaces:**
- Produces `konoha::grid_point`, `konoha::grid_map<W,H>`, `konoha::find_path<W,H,C>()`.
- Produces `konoha::unit_state`, `konoha::effect`, and `konoha::apply_effect_chain()`.
- Preserves all existing `konoha_bench` names as aliases/usings.

- [x] **Step 1: Write a failing production-namespace compile test**

Create `butano-sequel/game/tests/test_production_primitives.cpp`:

```cpp
#include "konoha/battle_effects.h"
#include "konoha/grid_pathfinder.h"
#include <array>
#include <cassert>

int main()
{
    konoha::grid_map<3, 3> map;
    auto path = konoha::find_path<3, 3, 8>(map, {0, 0}, {2, 0}, 2);
    assert(path.found && path.total_cost == 2);

    konoha::unit_state source{20, 20, 4, 0, 0, 0, true};
    konoha::unit_state target{10, 10, 0, 1, 0, 0, true};
    std::array effects = {konoha::effect{konoha::effect_kind::damage, 10, 0}};
    assert(konoha::apply_effect_chain(source, target, effects).success());
    assert(target.hp == 0);
}
```

- [x] **Step 2: Verify RED**

Run:

```sh
python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_production_primitives
```

Expected: compile failure because both production headers are missing.

- [x] **Step 3: Move the existing implementations into `namespace konoha`**

Copy the already tested implementation bodies without semantic changes. Replace each benchmark header with a production include and explicit compatibility names:

```cpp
#include "konoha/grid_pathfinder.h"
namespace konoha_bench {
using konoha::grid_map;
using konoha::grid_point;
using point = konoha::grid_point;
using konoha::find_path;
using konoha::path_result;
}
```

Apply the corresponding `using` declarations for effect types and `apply_effect_chain`.

- [x] **Step 4: Verify GREEN and compatibility**

Run:

```sh
python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_production_primitives
python3 tools/butano/run_cpp_benchmark_tests.py test_grid_pathfinder test_battle_effects
```

Expected: all three executables print PASS.

---

### Task 2: Define Scenario 41 Initial State and Intro

**Files:**
- Create: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Create: `butano-sequel/game/tests/test_scenario_41_initial.cpp`

**Interfaces:**
- Produces `scenario_41_battle`, `battle_snapshot`, `battle_phase`, `battle_command`, `battle_event`, `unit_id`, and `team`.
- `dispatch(battle_command)` is the only mutation entrypoint.

- [x] **Step 1: Write the failing initial-state test**

```cpp
#include "konoha/scenario_41_battle.h"
#include <cassert>

int main()
{
    konoha::scenario_41_battle battle;
    auto state = battle.snapshot();
    assert(state.phase == konoha::battle_phase::intro);
    assert(state.turn == 1);
    assert((state.cursor == konoha::grid_point{4, 10}));
    assert((state.naruto.position == konoha::grid_point{4, 10}));
    assert((state.iruka.position == konoha::grid_point{4, 4}));
    assert(state.naruto.hp == 80 && state.naruto.max_hp == 80);
    assert(state.iruka.active);

    assert(battle.dispatch({konoha::command_kind::confirm}) ==
           konoha::battle_event::intro_dismissed);
    assert(battle.snapshot().phase == konoha::battle_phase::unit_select);
}
```

- [x] **Step 2: Verify RED**

Run `python3 tools/butano/run_cpp_benchmark_tests.py --root butano-sequel/game test_scenario_41_initial`.

Expected: compile failure because the battle API is absent.

- [x] **Step 3: Implement the minimal types and intro transition**

The snapshot contains value copies of both units, cursor, committed player position, preview position, phase, turn, menu index, last event, and victory flag. Initialize the exact facts above. In intro, accept only `confirm`; all other commands return `invalid` without mutation.

- [x] **Step 4: Verify GREEN**

Run the initial test and Task 1 tests. Expected: all pass with no warnings.

---

### Task 3: Implement Cursor, Reachability, Preview, Commit, and Cancel

**Files:**
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Create: `butano-sequel/game/tests/test_scenario_41_movement.cpp`

**Interfaces:**
- Consumes `konoha::grid_map<9,22>` and `find_path<9,22,64>`.
- Produces `reachable(grid_point)`, movement preview state, and reversible phase transitions.

- [x] **Step 1: Write failing tests for map bounds and unit selection**

Test that cursor movement clamps to `[0,8]×[0,21]`, A on empty space returns `invalid`, and A on Naruto enters `move_select`.

- [x] **Step 2: Verify RED**

Run the movement test. Expected: missing movement behavior assertions fail.

- [x] **Step 3: Implement cursor and selection**

Use four-direction commands. Mark scenario-specific tree/rock cells as cost 0 and both active units as occupied. Naruto has move range 3.

- [x] **Step 4: Verify GREEN**

Run the movement test. Expected: bounds and selection pass.

- [x] **Step 5: Add failing tests for preview and invalid movement**

Assert a reachable unoccupied target enters `action_menu` with a changed preview but unchanged committed Naruto position. Assert obstacle, occupied, and over-budget targets return `invalid` with snapshot equality.

- [x] **Step 6: Implement preview and menu entry**

Calculate deterministic paths from the committed position. Store preview separately until `WAIT` or a successful combo commits it.

- [x] **Step 7: Add failing cancel-stack tests**

Assert B performs `target_select → action_menu → move_select → unit_select`, and every cancel restores the correct preview/cursor without changing committed position, turn, HP, or victory.

- [x] **Step 8: Implement cancel behavior and verify GREEN**

Run all game tests. Expected: all pass.

---

### Task 4: Implement WAIT, Enemy AI, and Turn Progression

**Files:**
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Create: `butano-sequel/game/tests/test_scenario_41_turns.cpp`

**Interfaces:**
- `WAIT` commits preview and enters `enemy_turn`.
- `tick` resolves one deterministic enemy action and begins the next player turn.

- [x] **Step 1: Write a failing WAIT test**

Select Naruto, preview a valid target, choose WAIT, and assert the committed position changes exactly once while phase becomes `enemy_turn`.

- [x] **Step 2: Verify RED, then implement minimal WAIT**

Run the turns test; observe the expected phase/position failure. Implement commit and event `waited`, then rerun to green.

- [x] **Step 3: Write failing deterministic AI tests**

Assert `tick` moves Iruka at most two orthogonal cells along a shortest path, never enters Naruto's cell, and increments the turn before returning to `unit_select`. When already adjacent, assert event `enemy_attacked` and no movement.

- [x] **Step 4: Implement AI with the shared pathfinder**

Temporarily mark Naruto occupied, request a path toward each unoccupied neighbor of Naruto, choose minimum total cost with stable direction order up/left/right/down, and advance at most two path steps.

- [x] **Step 5: Verify GREEN and refactor duplicate commit logic**

Run all game tests. Extract one private `_commit_preview()` used by WAIT and later combo without changing behavior.

---

### Task 5: Implement Combo Victory, Result, and Restart

**Files:**
- Modify: `butano-sequel/game/include/konoha/scenario_41_battle.h`
- Create: `butano-sequel/game/tests/test_scenario_41_victory.cpp`

**Interfaces:**
- Action menu index 0 is COMBO; index 1 is WAIT.
- A legal combo requires Manhattan distance 1 from preview position to active Iruka.
- `tick` advances combo feedback to victory; confirm advances victory→result→restart.

- [x] **Step 1: Write a failing invalid-combo invariance test**

From a non-adjacent preview, choose COMBO and confirm an empty/non-adjacent cell. Assert event `invalid` and exact equality for units, turn, committed position, HP, and victory.

- [x] **Step 2: Verify RED and implement target validation**

Run the victory test, observe the wrong transition, implement Manhattan/target/active checks, rerun green.

- [x] **Step 3: Write a failing natural-victory test**

Drive only public commands through repeated WAIT/enemy ticks and legal movement until Naruto previews an adjacent cell. Submit COMBO at Iruka and assert `combo_hit`, committed movement, Iruka inactive, and `combo_feedback`; after `tick`, assert `victory` and `victory=true`.

- [x] **Step 4: Implement combo using the production effect chain**

Apply one lethal damage effect transactionally, deactivate Iruka when HP reaches zero, and set victory only after feedback tick.

- [x] **Step 5: Write failing result and restart tests**

Confirm from victory to result, then confirm again. Assert event `restarted` and field-for-field equality with a fresh `scenario_41_battle` snapshot.

- [x] **Step 6: Implement and verify GREEN**

Run every game and benchmark test with `-Werror` through the runner.

---

### Task 6: Generate Deterministic Butano Graphics

**Files:**
- Create: `tests/test_butano_scenario_41_assets.py`
- Create: `tools/butano/generate_scenario_41_assets.py`
- Create: `butano-sequel/graphics/scenario_41_map.bmp`
- Create: `butano-sequel/graphics/scenario_41_map.json`
- Create: `butano-sequel/graphics/scenario_41_units.bmp`
- Create: `butano-sequel/graphics/scenario_41_units.json`

**Interfaces:**
- Generator function `generate_assets(output_dir: Path) -> dict[str, str]` returns SHA-256 by filename.
- Map BMP is Windows 4bpp 256×512 with <=16 colors.
- Unit BMP is Windows 4bpp 16×48, `height: 16`, with Naruto, Iruka, cursor frames.

- [x] **Step 1: Write a failing Python asset test**

Load the generator by file path, generate into a temporary directory, parse BMP headers, and assert dimensions, 4 bits-per-pixel, deterministic hashes across two directories, plus JSON types `regular_bg` and `sprite`.

- [x] **Step 2: Verify RED**

Run `python3 -m unittest tests.test_butano_scenario_41_assets -v`.

Expected: generator module missing.

- [x] **Step 3: Implement a minimal indexed-BMP writer and assets**

Use one fixed 16-color BGR palette. Draw 16×16 grid cells into the 9×22 play region, pad the remaining 256×512 canvas with dark forest, and render distinct orange/blue Naruto, green/gray Iruka, and yellow cursor frames. No randomness or timestamps are allowed.

- [x] **Step 4: Verify GREEN and materialize assets**

Run the test, then `python3 tools/butano/generate_scenario_41_assets.py --output-dir butano-sequel/graphics`. Rerun the test and record hashes in its expectations.

---

### Task 7: Build the Butano Battle Scene

**Files:**
- Create: `butano-sequel/game/include/konoha/scenario_41_scene.h`
- Create: `butano-sequel/game/src/scenario_41_scene.cpp`
- Modify: `butano-sequel/src/main.cpp`
- Modify: `butano-sequel/Makefile`
- Modify: `tests/test_butano_build.py`

**Interfaces:**
- `void run_scenario_41_scene()` owns a `scenario_41_battle` until the program exits.
- Renderer consumes snapshots only; keypad handler dispatches commands only.

- [x] **Step 1: Write a failing wiring contract**

Extend `test_benchmark_rom_wiring_is_declared` or add a focused test asserting:

```python
self.assertIn("game/src", makefile)
self.assertIn("game/include", makefile)
self.assertIn("graphics", makefile)
self.assertIn("konoha/scenario_41_scene.h", main)
self.assertIn("konoha::run_scenario_41_scene()", main)
```

- [x] **Step 2: Verify RED**

Run `python3 -m unittest tests.test_butano_build.ButanoBuildTest.test_scenario_41_rom_wiring_is_declared -v`.

Expected: all new wiring assertions fail against the benchmark screen.

- [x] **Step 3: Implement scene shell and launch wiring**

Initialize Butano once, assert embedded self-tests, and call `run_scenario_41_scene()`. Add game source/include and graphics paths to Makefile.

- [x] **Step 4: Add rendering in independently compiling slices**

Implement in this order, running a Docker build after each slice:

1. background plus camera;
2. Naruto/Iruka/cursor sprites bound to grid coordinates;
3. intro/objective text;
4. bottom status and action menu;
5. range overlay sprites and invalid feedback;
6. enemy-turn/combo feedback timing;
7. victory/result/restart pages.

Each slice must clear and rebuild fixed-capacity sprite vectors instead of retaining stale UI objects.

- [x] **Step 5: Extend the integration binary contract**

Assert the ELF contains `scenario_41_battle`, `DEFEAT IRUKA`, `COMBO`, `VICTORY`, `EXP +110`, and no longer uses the benchmark results as its visible main screen.

- [x] **Step 6: Verify GREEN from a clean build**

Run guarded `make clean`, then guarded `RUN_BUTANO_INTEGRATION=1 python3 -m unittest tests.test_butano_build -v`. Expected: exit 0 and no compiler warnings.

---

### Task 8: Document and Verify the Playable Level

**Files:**
- Create: `docs/butano-scenario-41-battle.md`
- Modify: `docs/sequel-roadmap.md`
- Create: `notes/butano-scenario-41-runtime-20260721.md`
- Create or modify: `tests/test_butano_research_docs.py`

**Interfaces:**
- Documents expose controls, user feedback, loading/empty/error behavior, limits, build command, ROM path, and exact acceptance route.

- [x] **Step 1: Write a failing documentation contract**

Require `scenario 41`, `9×22`, `(4,10)`, `(4,4)`, `COMBO`, `WAIT`, `VICTORY`, `EXP +110`, `B 取消`, `START`, `非法目标`, and the guarded runtime evidence path.

- [x] **Step 2: Verify RED, then write the user guide and roadmap update**

Run the focused docs test, observe missing report failure, add the documents, and rerun green.

- [x] **Step 3: Run final host verification**

Run all game C++ tests, benchmark C++ tests, Butano Python scope tests, `py_compile`, `bash -n`, `git diff --check`, asset regeneration/hash comparison, and setup verification.

- [x] **Step 4: Run guarded ROM verification**

Build from clean state under the shared heavy lock. Verify ROM title/code, hash, ELF strings, and resource guard summary. Attempt one cold-start mGBA acceptance route only through `tools/run_guarded.py`; preserve a unique run directory and never claim runtime completion if input or screenshots are unavailable.

- [x] **Step 5: Completion audit**

Check every design requirement against a test, build output, ROM artifact, or runtime screenshot. Keep the Goal active for every missing user-visible step; call `update_goal(status="complete")` only when the full playable route is proven.
