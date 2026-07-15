# Task 4.7 Step 1 implementation report

## Scope

Implemented the fixed single-input native mGBA runner only. No ROM was launched, no
input was sent, and no checkpoint or OpenSpec/plan checkbox was changed.

## TDD RED

Command:

```bash
python3 -m unittest tests.test_run_macos_mgba_single_input \
  tests.test_macos_mgba_runtime_residue -v
```

Result: expected failure (14 tests, 15 errors). The failures were caused by the missing
`mgba_single_input_replay.lua`, `run_macos_mgba_single_input` module, and
`macos_mgba_runtime_residue` module.

## GREEN and refactor

- Added a fixed Lua contract with one Down/A event and one capture.
- Added a runner that reuses the existing replay provenance, path, guard, output, and
  exact-PGID helpers while keeping the zero-input runner unchanged.
- Extracted the existing acceptance `ps`/`lsof` checks into a shared read-only,
  fail-closed residue module; compatibility imports and acceptance tests remain green.
- Added explicit rejection of wrong/multiple/automatic/recovery input payloads,
  custom/pre Lua CLI surfaces, input drift, guard failure, and runtime residue.
- Parsed both Lua files with `luac -p`; the fixed single-input Lua SHA-256 is
  `ca0ec91d17f28c67f79f0f94d4aef215ab5417650e4bc90291db938a2429c884`.
- Confirmed the untouched zero-input Lua SHA-256 remains
  `d1d1dbcce947f6a9149963cc947ef76944e5ac9065cb9906e12bd1a2dda173af`.

Focused GREEN after refactor: 16 tests passed. The combined single-input, residue,
acceptance, zero-input replay, and resource-guard regression run passed 71 tests with
one expected Windows-only skip. Python compilation, both Lua syntax checks, pinned
hash checks, and `git diff --check` also passed.

## User-visible boundary

The new command can later produce one guarded Down or A build candidate with one
audited event. It does not itself accept the candidate, prove controller/player
control, or authorize A before a separately accepted Down snapshot.
