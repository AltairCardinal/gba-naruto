# Butano Formation Runtime Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve and load the original ROM formation record's per-unit level, 15 primary action slots, 24 secondary/passive slots, and 9 ninja-tool slots so every fixed encounter uses its own real combat configuration.

**Architecture:** `tools/extract_positions.py` remains the lossless owner of the 0xB8 ROM record. The scenario generator validates and emits that data into `battle_scenario_unit_slot`; the loader applies embedded configuration for fixed-character records and keeps deployment placeholders owned by roster/progression data. Policy and progression are explicit overrides, never silent replacements for the formation defaults.

**Tech Stack:** Python 3/unittest content pipeline, C++20 constexpr domain model, Butano/GBA ARM build, mGBA Lua runtime verification.

## Global Constraints

- Preserve `rom/base.sav` SHA256 `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`.
- Use RED → GREEN → REFACTOR for every behavior change.
- Do not commit, stage, push, or roll back unrelated dirty-worktree changes.
- Run mGBA and other heavy jobs only through `tools/run_guarded.py`.
- Fixed-character records consume their embedded level/action/tool data.
- Deployment placeholders do not pretend that their zeroed embedded action arrays are real roster data.
- Keep all 9 original tool slots; the action catalog capacity is 15 primary actions + 9 tools = 24.

---

### Task 1: Lossless formation extraction

**Files:**
- Modify: `tests/test_extract_positions.py`
- Modify: `tools/extract_positions.py`
- Regenerate: `sequel/content/positions/bank.json`

**Interfaces:**
- Consumes: the 0xB8 record at `record_offset(group, variant, record)`.
- Produces: `level`, `unit_parameter`, `primary_action_slots`, `secondary_action_slots`, and `equipped_tools`.

- [ ] **Step 1: Write the failing extraction test**

```python
naruto = record(bank, 10, 0, 2)
self.assertEqual(naruto["level"], 1)
self.assertEqual(naruto["primary_action_slots"][:3], [
    {"action": 1, "state": 2, "unlock_level": 0, "reserved": 0},
    {"action": 2, "state": 2, "unlock_level": 0, "reserved": 0},
    {"action": 5, "state": 2, "unlock_level": 0, "reserved": 0},
])
self.assertEqual(naruto["equipped_tools"], [1, 19, 41, 41, 41, 0, 0, 0, 0])
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python3 -m unittest tests.test_extract_positions -v`

Expected: `KeyError: 'level'`.

- [ ] **Step 3: Parse the exact offsets**

```python
LEVEL_OFFSET = 0x0F
PRIMARY_ACTION_OFFSET = 0x10
PRIMARY_ACTION_COUNT = 15
SECONDARY_ACTION_OFFSET = 0x4C
SECONDARY_ACTION_COUNT = 24
NINJA_TOOL_OFFSET = 0xAC
NINJA_TOOL_COUNT = 9
```

Each four-byte slot is emitted as `action`, `state`, `unlock_level`, and `reserved`. Keep `raw_hex` as the round-trip source.

- [ ] **Step 4: Run extraction tests and regenerate the bank**

Run:

```bash
python3 -m unittest tests.test_extract_positions -v
python3 tools/extract_positions.py rom/base.gba --bank sequel/content/positions/bank.json
```

Expected: all extraction tests pass and the bank contains 1,728 records.

### Task 2: Generated scenario contract

**Files:**
- Modify: `tests/test_generate_butano_battle_scenario_content.py`
- Modify: `tools/generate_butano_battle_scenario_content.py`
- Modify: `butano-sequel/game/include/konoha/battle_scenario_content.h`
- Regenerate: `butano-sequel/game/include/konoha/generated_battle_scenario_content.h`

**Interfaces:**
- Consumes: Task 1's JSON fields.
- Produces: `battle_scenario_unit_runtime_config` embedded in every `battle_scenario_unit_slot`.

- [ ] **Step 1: Write failing generator assertions**

```python
enemy_naruto = scenarios[10]["variants"][0][2]
self.assertEqual(enemy_naruto["runtime_config"]["level"], 1)
self.assertEqual(enemy_naruto["runtime_config"]["primary_action_slots"][0]["action"], 1)
self.assertEqual(enemy_naruto["runtime_config"]["equipped_tools"],
                 [1, 19, 41, 41, 41, 0, 0, 0, 0])
```

Also assert a deployment placeholder has `embedded_character_config == False`.

- [ ] **Step 2: Run the generator test and verify RED**

Run: `python3 -m unittest tests.test_generate_butano_battle_scenario_content -v`

Expected: missing `runtime_config`.

- [ ] **Step 3: Add and render the fixed-capacity C++ contract**

```cpp
struct battle_scenario_unit_runtime_config
{
    bool embedded_character_config = false;
    std::uint8_t level = 1;
    std::uint8_t unit_parameter = 0;
    std::array<action_slot_definition, 15> primary_action_slots = {};
    std::array<action_slot_definition, 24> secondary_action_slots = {};
    std::array<ninja_tool_id, 9> equipped_tools = {};
};
```

The generator validates fixed-record action IDs (`0..86`), secondary IDs (`0..23`), tools (`0..93`), and levels (`1..50`). Placeholder records keep `embedded_character_config == false`.

- [ ] **Step 4: Run generator tests and regenerate the header**

Run:

```bash
python3 -m unittest tests.test_generate_butano_battle_scenario_content -v
python3 tools/generate_butano_battle_scenario_content.py --root .
```

Expected: generator tests pass and the generated header is deterministic.

### Task 3: Runtime load ownership and full tool capacity

**Files:**
- Modify: `butano-sequel/game/tests/test_battle_scenario_loader.cpp`
- Modify: `butano-sequel/game/tests/test_battle_action_catalog.cpp`
- Modify: `butano-sequel/game/include/konoha/battle_session.h`
- Modify: `butano-sequel/game/include/konoha/battle_action_catalog.h`
- Modify: `butano-sequel/game/include/konoha/battle_action_browser.h`
- Modify: `butano-sequel/game/include/konoha/battle_defense_browser.h`
- Modify: `butano-sequel/game/include/konoha/battle_player_action_flow.h`
- Modify: `butano-sequel/game/include/konoha/battle_ai_turn_flow.h`
- Modify: `butano-sequel/game/include/konoha/battle_scenario_loader.h`

**Interfaces:**
- Consumes: `battle_scenario_unit_runtime_config`.
- Produces: an instantiated battle unit whose level, primary action states, passive slots, and nine tool slots match the formation unless progression/policy explicitly overrides them.

- [ ] **Step 1: Write failing loader and catalog tests**

```cpp
const battle_unit_instance* enemy_naruto = mirror_session.unit(3);
assert(enemy_naruto->level == 1);
assert(enemy_naruto->primary_action_levels[0] == 2);
assert(enemy_naruto->primary_action_levels[1] == 2);
assert(enemy_naruto->primary_action_levels[2] == 2);
assert(enemy_naruto->equipped_tools ==
       std::array<ninja_tool_id, 9>{ 1, 19, 41, 41, 41, 0, 0, 0, 0 });
```

Add a catalog test with 15 active actions and 9 nonzero tools and assert `count == 24`.

- [ ] **Step 2: Compile/run focused tests and verify RED**

Run the repository's host C++ test runner for `test_battle_scenario_loader.cpp` and `test_battle_action_catalog.cpp`.

Expected: compile failure on four-slot tool arrays and/or runtime assertions showing template-derived states.

- [ ] **Step 3: Implement explicit precedence**

```text
level: player progression > nonzero policy level > embedded formation level > level 1
actions: initialized progression > embedded formation slots > character template
tools: explicit policy override > embedded formation tools > empty/template roster tools
```

Add `character_equipped_tools_overridden[63]` so an all-zero explicit loadout is distinguishable from “no override”. Validate before mutating the destination session. Apply fixed-record primary states directly and rebuild passive slots from the fixed-record secondary definitions.

- [ ] **Step 4: Expand all action-view capacities**

Use shared constants:

```cpp
inline constexpr std::size_t battle_primary_action_capacity = 15;
inline constexpr std::size_t battle_ninja_tool_slot_capacity = 9;
inline constexpr std::size_t battle_action_catalog_capacity = 24;
```

Replace the former literal 4/19 arrays in unit state, catalog, browser, defense browser, player snapshot, and AI action buffers.

- [ ] **Step 5: Run focused and complete host tests**

Expected: loader/catalog focused tests pass, then all C++ battle tests pass.

### Task 4: Durable evidence and runtime verification

**Files:**
- Create: `notes/battle-formation-runtime-config-20260726.md`
- Update: `docs/battle-system-architecture.md`
- Update: `docs/sequel-roadmap.md`
- Update: `tools/README.md`
- Create: `artifacts/butano-formation-runtime-config-20260726-01/manifest.json`

**Interfaces:**
- Consumes: ROM disassembly, generated data, test results, ARM symbols, mGBA telemetry.
- Produces: hash-bound evidence and explicit scope limits for the next battle-system milestone.

- [ ] **Step 1: Record static proof**

Document `0x0806ACAC..0x0806ADC2`, the 0xB8 field map, fixed-vs-placeholder ownership, ROM slice SHA256, and representative battle 10 data.

- [ ] **Step 2: Run full verification**

Run relevant Python suites, every C++ battle host test, ARM build, and the battle 9 mGBA natural route through `tools/run_guarded.py`.

- [ ] **Step 3: Bind the artifact**

Record ROM/ELF/script/save hashes, symbol addresses, final phase/round/unit telemetry, errors/traps, and the limitation that a scripted battle route proves integration stability rather than every encounter's semantic equivalence.

- [ ] **Step 4: Re-audit the next architecture gap**

Compare the now-real formation load path against the documented complete turn flow and select only the next evidence-backed missing system.
