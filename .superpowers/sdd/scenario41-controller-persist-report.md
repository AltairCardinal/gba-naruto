# Scenario 41 controller-entry checkpoint persistence report

## Status

- Result: `DONE_WITH_CONCERNS`
- Commit: this focused local commit, `docs(re): persist scenario 41 controller entry`.
- Runtime: not run; this persistence task reused the independently accepted p1 artifact.
- Push: not performed.

## TDD evidence

RED command:

```bash
python3 -m unittest tests.test_scenario41_controller_checkpoint_persistence
```

Expected RED: 3 failures. The canonical checkpoint was absent, compact evidence returned
`not-proven` instead of `accepted`, and the ledger contained zero controller-entry records.

GREEN command:

```bash
python3 -m unittest tests.test_scenario41_controller_checkpoint_persistence
```

GREEN result: 3 tests passed. The test binds the canonical SHA, accepted compact evidence,
raw callsite/target/return, task-2 context, three explicit raw returns, A880/A882/2680C,
p1/p2 zero-input lineage, exact RGB, guard completion, superseded history, scope boundary,
and the single accepted ledger record.

## Persisted acceptance

- Canonical checkpoint:
  `artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9`
- Checkpoint SHA-256:
  `4569846c1bf2cfcc2b6ad8848266bd02d2ada332eeca7acf74456f7a762e7cd6`
- Compact evidence SHA-256:
  `64cd93f97786da4612f7c73e4ed9735c0fe7d13742923b1c240488798eeadd98`
- Raw positive run: `9c4631126d8302ae32bc4f0cc0e487db`
- p1: `89a882a2ede41a4ab06f4f2cccc36906` → canonical checkpoint SHA
- p2: `ad079170d922c5297f6556d2a9672a85` →
  `31337b507f2337fa9cc4946f88ffc16230a8d16bcbf427688efec2a0302add33`
- Exact normalized RGB8 SHA-256:
  `094b2c4f94ae1bac4141019c559fb06983386ba9b2ad09faa2e723fe8ac97dec`
- Accepted boundary: stable controller entry only. Player control, first turn, MOVEDONE,
  victory and postbattle remain unproven.

The old B/B/Down evidence and the wrong outer-B/direct-outer-A hypotheses remain referenced
as `superseded`; they are excluded from current acceptance lineage rather than deleted.

## Files

- `artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9`
- `artifacts/runtime-checkpoints/scenario-41-controller-entry-evidence.json`
- `artifacts/runtime-checkpoints/scenario-41-checkpoints.json`
- `artifacts/runtime-checkpoints/README.md`
- `tools/README.md`
- `notes/scenario-41-prebattle-to-controller-macos-20260715.md`
- `docs/reverse-engineering-macos-intel-handoff-20260715.md`
- `docs/sequel-roadmap.md`
- `tests/test_scenario41_controller_checkpoint_persistence.py`
- `.superpowers/sdd/scenario41-controller-persist-report.md`

The pre-existing dirty hunk in `docs/sequel-roadmap.md` was preserved; this task appended
only the 2026-07-17 controller-entry statement. No OpenSpec task, Comet state, AGENTS.md,
raw build output or unrelated dirty file was modified by this task.

## Verification

- Ledger validator: `accepted=7 candidate=0 rejected=1 errors=0`
- Unit/integration tests: 15 passed across `tests.test_runtime_checkpoint_ledger` and the
  new focused persisted-artifact test.
- Evidence and ledger JSON parse: passed.
- Source/destination/checkpoint/ledger SHA contract: passed.
- `git diff --check`: passed.

## Concern

The current ledger validator has no `controller-entry` hook token and the brief forbids
changing it. The accepted record therefore conservatively uses `allowed_evidence=[]`.
The compact evidence proves controller entry through the raw/static gate and independent
zero-input stability; no player-control/MOVEDONE/victory/postbattle token is fabricated.

## Review finding follow-up

- Result: `DONE`
- Commit: focused local commit `test(re): close controller checkpoint persistence gaps`;
  the immutable hash is reported from `git log` after creation because a commit cannot
  embed its own hash.
- Runtime: not run; this follow-up changed only ledger wording/status and regression tests.
- Push: not performed.

### RED evidence

The old `scenario-41-pre-controller-after-a` record had no explicit status for its old
bounded controller attempt. The new focused test failed with:

```text
AssertionError: None != 'superseded'
```

The compact evidence coverage gap was independently checked with an in-memory minimal
fixture break that changed only
`zero_input_stability.exact_controller_state.task_2.resume_pc` to `0xDEADBEEF`. The new
test failed against the expected exact value `0x08073616`; the temporary mutation was
then removed before GREEN. No evidence artifact was modified.

### GREEN evidence

- Focused persistence suite: 5 tests passed.
- Focused persistence plus ledger integration suite: 17 tests passed.
- Ledger validator: `accepted=7 candidate=0 rejected=1 errors=0`.
- Ledger JSON parse: passed.
- Focused `git diff --check`: passed.

The old record now preserves its accepted status, canonical pre-controller path and its
own pre-controller evidence boundary, while explicitly marking the obsolete bounded
attempt as `superseded`. Its runtime boundary records that a corrected subsequent child
captured raw return `0x0808F957` and passed two independent 224-frame zero-input replays
to create the canonical controller checkpoint. The compact evidence test now binds the
raw positive guard (`completed`, exit 0, success marker, non-degraded) and the exact p1/p2
controller state (task-2 resume/SP/LR, all three raw returns, and A880/A882/2680C).
