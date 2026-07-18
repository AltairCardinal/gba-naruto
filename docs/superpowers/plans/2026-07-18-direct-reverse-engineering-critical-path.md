# Scenario 41 Direct Critical-Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Do not use Comet or per-input subagent dispatch.

**Goal:** Close scenario 41's first natural turn, victory/result, controller exit, and stable `0xF400` postbattle with auditable native-mGBA evidence, then continue the remaining reverse-engineering completion gates.

**Architecture:** Treat existing OpenSpec tasks, accepted checkpoints, ledger, and runtime evidence as facts, but execute directly in milestone-sized batches. Transient UI states receive one bounded run and parent audit; only durable turn/victory/postbattle checkpoints receive stability replay, persistence tests, and one independent review.

**Tech Stack:** Python 3, Node.js, native mGBA 0.10.5 script backport, Lua replay scripts, GDB RSP probes, SS9 checkpoints, JSON evidence, project heavy resource guard.

## Global Constraints

- Do not invoke Comet or write `.comet` dispatch/progress records.
- Keep one writer. Use subagents only for an independent final milestone review or a genuinely parallel read-only analysis.
- A transient prompt must not receive cycle sampling or p/2p replay.
- A durable checkpoint may receive one zero-input stability sample and, only if animation requires it, one serial p/2p confirmation.
- Batch up to five statically justified single-input runs before reporting; stop immediately on an unexpected task, unit, result, MOVEDONE, resource, or residue transition.
- Every mGBA/GDB run uses `tools/run_guarded.py`, a unique run root, preflight memory checks, and the shared heavy lock.
- No push, publication, destructive Git operation, forced WRAM outcome, adaptive input recovery, or unrelated cleanup.
- Cost gate: no diagnostic branch may exceed 15 minutes or three runs without producing a new state transition or falsifying a concrete hypothesis.

---

### Task 1: Close the first natural turn from the shortest reviewed boundary

**Files:**
- Consume: `build/scenario-41-facing-confirm-a-20260717/output.ss9`
- Consume: `tools/run_macos_mgba_single_input.py`
- Consume: `tools/mgba_single_input_replay.lua`
- Inspect: `play/_scripts/scenario-41-runtime-evidence.js`
- Create only after acceptance: `artifacts/runtime-checkpoints/scenario-41-turn-1-complete.ss9`
- Modify only after acceptance: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Modify only after acceptance: `notes/scenario-41-movedone-runtime-20260717.md`
- Test only after acceptance: the existing Scenario 41 checkpoint/evaluator tests, adding one focused persistence test if no test covers the new record.

**Interfaces:**
- Consumes reviewed state SHA `54cf5eca...4101`, task `0x0806810C`, cursor row 1 `否`, counter 1, and primary MOVEDONE record at `0x0807443C`.
- Produces either a proved first-turn checkpoint with a real action/round transition, or a bounded negative result naming the exact missing acceptance gate.

- [ ] Run one guarded `A@5/13`, hold 8, capture 128 directly from the reviewed facing-confirm output to select the already-highlighted `否` branch.
- [ ] Audit task stack, full acting-unit record, action/round fields, MOVEDONE counter/records, battle/map, screenshot, guard, RSS, and residue before choosing another input.
- [ ] Continue at most four additional statically justified single inputs in the same parent batch, always consuming the immediately previous accepted output and stopping on the first true turn boundary or contradiction.
- [ ] If a stable turn boundary is reached, perform only the minimum zero-input stability proof needed for a persistent checkpoint.
- [ ] Use TDD to persist the accepted checkpoint/evidence/ledger record; run the focused persistence tests, evaluator tests, ledger validation, and `git diff --check`.
- [ ] Create one focused local commit only after all acceptance evidence passes.

### Task 2: Close victory, result write, controller exit, and postbattle

**Files:**
- Consume: `artifacts/runtime-checkpoints/scenario-41-turn-1-complete.ss9`
- Reuse/modify if required under TDD: `tools/build_battle_completion_runtime_probe.py`
- Reuse/modify if required under TDD: `play/_scripts/scenario-41-runtime-evidence.js`
- Create: `artifacts/runtime-checkpoints/scenario-41-victory.ss9`
- Create: `artifacts/runtime-checkpoints/scenario-41-postbattle.ss9`
- Create: `artifacts/runtime-checkpoints/scenario-41-completion-evidence.json`
- Modify: `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- Create or update: `notes/scenario-41-completion-runtime-20260718.md`

**Interfaces:**
- Consumes the proved turn-1 state and the known completion chain `0x0807444E -> 0x080777FC -> 0x08073068`, result byte `0x02026807`, exit `0x08074FDA`, and controller state `0xF400`.
- Produces ordered fresh evidence for outcome, result, exit, and postbattle plus base-ROM controls.

- [ ] Reuse existing completion observer/evaluator code and tests; add code only when a concrete missing observation is demonstrated by a failing test.
- [ ] Execute the second natural turn in milestone-sized input batches, stopping separately at result victory, controller exit, and stable postbattle.
- [ ] Persist victory immediately after the result transition and postbattle only after `0xF400` is stable.
- [ ] Replay the same decisive input on base ROM and zero-replay the final postbattle checkpoint; forbid forced result writes or formation cheats.
- [ ] Run focused Python/Node tests, ledger validation, base-control checks, resource/residue checks, and `git diff --check`.
- [ ] Request one independent read-only review for the complete milestone, fix only Critical/Important findings, and create one focused local commit.

### Task 3: Finish the remaining repository-wide reverse-engineering gates

**Files:**
- Inspect and update from evidence: `docs/sequel-roadmap.md`
- Inspect and update from evidence: `docs/reverse-engineering-macos-intel-handoff-20260715.md`
- Update: `docs/final-completion-report.md`
- Use existing OpenSpec task files only as checklists; do not invoke their Comet workflow.

**Interfaces:**
- Consumes accepted Scenario 41 postbattle evidence.
- Produces verified levels runtime, upgraded remaining runtime banks, closed completion gaps, and the final machine-audited completion report.

- [ ] Reconcile remaining task files against current evidence and order work by the first missing machine gate, not by checkbox order.
- [ ] Execute levels, remaining-bank, and completion-gap work in milestone batches with the same transient-versus-persistent evidence policy.
- [ ] Run the repository-wide completion audit, all required tests/builds/runtime replays, and verify every explicit final-report claim against retained artifacts.
- [ ] Mark the Goal complete only when all requirements are proved and `docs/final-completion-report.md` agrees with machine evidence.

## Self-Review

- Scope coverage: first turn, victory, result, exit, postbattle, remaining levels/banks/gaps, and final audit are all represented.
- Reuse: existing runners, observers, evaluators, checkpoints, and ledger are mandatory; no parallel implementation is planned.
- Cost control: transient prompts are batched and not independently stabilized/reviewed; only durable milestones receive persistence and review.
- Safety: heavy lock, owned-tree memory guard, unique run roots, residue checks, and no forced outcome remain mandatory.
