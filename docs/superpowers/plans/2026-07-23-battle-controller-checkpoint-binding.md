# Original Battle Controller Checkpoint Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace screenshot-named battle phases with hash-bound mappings from visible mGBA checkpoints to the original ROM controller stack.

**Architecture:** Read the game’s cooperative task context from each `.ss9`, validate Thumb BL frames against the checked ROM, and accept a controller-state binding only when an inner controller frame precedes a validated outer call to `0x080732B4`. Keep manual visual observations separate from generated control-flow evidence.

**Tech Stack:** Python 3 standard library, existing mGBA savestate parser, existing Thumb BL decoder, `unittest`, checked `rom/base.gba`.

## Global Constraints

- Do not launch mGBA; all checkpoint work is offline.
- Do not infer a state from a filename or screenshot alone.
- Reject ROM, dispatcher, or checkpoint hash mismatches.
- Preserve unresolved states and shared nested subphases.
- Do not modify the rejected Butano battle implementation.

---

### Task 1: Hash-bound checkpoint analyzer

**Files:**
- Create: `tools/analyze_battle_controller_checkpoints.py`
- Create: `tests/test_analyze_battle_controller_checkpoints.py`
- Create: `notes/battle-controller-checkpoint-observations-20260723.json`
- Generate: `notes/battle-controller-checkpoint-bindings-20260723.json`

**Interfaces:**
- Consumes `rom/base.gba`, `notes/battle-controller-states-20260723.json`, task 2 context at `0x03000A88 + 0x4C`, and hash-bound observation records.
- Produces `analyze_checkpoint(...)` and `build_checkpoint_manifest(...)`.
- A nested binding is valid only when its controller frame stack address is lower than a BL frame targeting `0x080732B4`.

- [x] **Step 1: Write the failing analyzer tests**

Tests require direct state `0x0000`, nested states `0x3110/0x9200/0x1220/0x8000`, hash rejection, and an 18-checkpoint manifest. The final four checkpoints extend the original scenario 41 set with scenario 45/50 enemy planning and resolution.

- [x] **Step 2: Verify red**

Run: `python3 -m unittest tests.test_analyze_battle_controller_checkpoints`

Expected: import error because the analyzer does not exist.

- [x] **Step 3: Implement task-context, BL, stack-order, and hash validation**

The implementation exposes only values proven from the serialized state and checked ROM; `_state_for_address` maps a validated resume address to the sorted dispatcher-entry interval.

- [x] **Step 4: Add and pass direct CLI integration coverage**

Run: `python3 -m unittest tests.test_analyze_battle_controller_checkpoints`

Expected: 5 tests pass, including direct script invocation and generated JSON parsing.

### Task 2: Correct persistent controller semantics

**Files:**
- Modify: `tools/extract_battle_controller_states.py`
- Modify: `tests/test_extract_battle_controller_states.py`
- Update: `notes/battle-controller-states-20260723.json`
- Update: `notes/battle-system-restoration-evidence-20260723.md`
- Update: `docs/superpowers/specs/2026-07-22-butano-battle-system-architecture-design.md`
- Update: `docs/sequel-roadmap.md`
- Update: `tools/README.md`
- Modify: `docs/superpowers/plans/2026-07-22-butano-battle-system-implementation.md`
- Modify: `tests/test_butano_research_docs.py`

**Interfaces:**
- Consumes the generated 14-checkpoint binding manifest.
- Produces evidence-backed semantics for `0x3000`, `0x3110`, `0x4000`, `0x4100`, `0x8000`, `0x9000`, `0x9100`, and `0x9200` while leaving unrelated states unresolved.

- [x] **Step 1: Write failing semantic and rejected-plan tests**

The state test rejects the old `0x4100` action-tail label. The documentation test rejects any claim that the screenshot-driven plan is implemented.

- [x] **Step 2: Verify red**

Run:

```bash
python3 -m unittest \
  tests.test_extract_battle_controller_states.BattleControllerStateTests.test_exposes_evidence_backed_turn_and_action_boundaries \
  tests.test_butano_research_docs.ButanoResearchDocsTest.test_rejected_battle_plan_cannot_claim_architecture_is_implemented
```

Expected: both assertions fail against the old semantics/status.

- [x] **Step 3: Update only the evidence-backed labels and persistent docs**

Keep target selection and attack confirmation as nested subphases of `0x4100`; keep combat dialogue, popup, and victory as nested subphases of `0x8000`. Mark the 2026-07-22 plan rejected and non-executable.

- [x] **Step 4: Run the complete relevant regression**

Run the controller/content tests, Butano host tests, configuration verifier, Python compilation, and `git diff --check`. Expected: all commands exit 0; no claim is made about a new Butano battle implementation.

The full regression passed after the controller binding changes; after adding the unit-identity overlay, the affected controller/content/documentation tests (25 tests), catalog regeneration, Python compilation, and `git diff --check` were repeated and also passed.
