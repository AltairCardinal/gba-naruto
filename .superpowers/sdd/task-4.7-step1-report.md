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

## Review fix round 1

### Evidence provenance and reconstructed pre-implementation RED

The original historical RED above remains the contemporaneous record: its command
reported 14 tests and 15 errors. It does not cover the final committed 16-test suite,
so this round does not treat it as evidence for those two later tests and does not
backdate or rewrite it.

This round reconstructed the missing verification in an isolated archive of base
commit `b5ab04f515789aedcdc143dfc0c790bfe037020e`, overlaying only the two committed
test files from `f252dbd922062294b51fa3da58f4b157751b43ef`:

```bash
tmp=$(mktemp -d /tmp/gba-naruto-task47-base-red.XXXXXX)
git archive b5ab04f515789aedcdc143dfc0c790bfe037020e | tar -x -C "$tmp"
git archive f252dbd922062294b51fa3da58f4b157751b43ef \
  tests/test_run_macos_mgba_single_input.py \
  tests/test_macos_mgba_runtime_residue.py | tar -x -C "$tmp"
(
  cd "$tmp"
  python3 -m unittest tests.test_run_macos_mgba_single_input \
    tests.test_macos_mgba_runtime_residue -v
)
rc=$?
printf 'EXIT_CODE=%s\n' "$rc"
```

Observed result: exit code 1; `Ran 16 tests`; `FAILED (errors=17)`. The extra
error count comes from the two subtests in the drift/residue case. The failures
were for the correct pre-implementation reasons: `mgba_single_input_replay.lua`
was absent, and imports of `tools.run_macos_mgba_single_input` and
`tools.macos_mgba_runtime_residue` raised `ModuleNotFoundError`.

### Post-run source-save gate mutation RED and real GREEN

Added
`test_post_run_source_save_creation_fails_without_finalizing_payload`, whose fake
wrapper creates the source ROM `base.sav` during the simulated execution. The test
requires a `ReplayError` mentioning `source ROM save` and verifies that neither the
audit nor sentinel receives `build_manifest_sha256` or `runtime_residue` finalization
fields.

For mutation verification, an isolated archive of current `HEAD` was given the new
test and the single post-run line below was removed only in that temporary copy:

```diff
-    _require_absent(args.source_save, "source ROM save sidecar")
```

Exact mutation test command:

```bash
python3 -m unittest \
  tests.test_run_macos_mgba_single_input.SingleInputRunnerIntegrationTests.test_post_run_source_save_creation_fails_without_finalizing_payload \
  -v
```

Observed mutation result: exit code 1; `Ran 1 test`; `FAILED (failures=1)` with
`AssertionError: ReplayError not raised`. The mutated runner also printed an
incorrectly finalized audit, confirming that the test detects removal/bypass of the
post-run gate. The mutation was never applied to the real production file.

The same command against the real repository produced exit code 0, `Ran 1 test`,
and `OK`. No production fix was necessary. The production runner remained
byte-identical with SHA-256
`9e9a66468197bb4764c095a2210e57bbb3762d504a9ce9f9c3f37c8c9ae4c04f`.

### Current GREEN and regression verification

Focused single-input and residue command:

```bash
python3 -m unittest tests.test_run_macos_mgba_single_input \
  tests.test_macos_mgba_runtime_residue -v
```

Observed result: exit code 0; `Ran 17 tests`; `OK`.

Combined regression command from the original report, now including the new test:

```bash
python3 -m unittest \
  tests.test_run_macos_mgba_single_input \
  tests.test_macos_mgba_runtime_residue \
  tests.test_accept_prebattle_candidate \
  tests.test_run_macos_mgba_replay \
  tests.test_run_guarded -v
```

Observed result: exit code 0; `Ran 72 tests`; `OK (skipped=1)`. The skip was the
expected Windows Job Object failure-path test. The original 71-test count increased
only because this round added one test.

Python compilation command:

```bash
python3 -m py_compile \
  tests/test_run_macos_mgba_single_input.py \
  tests/test_macos_mgba_runtime_residue.py \
  tests/test_accept_prebattle_candidate.py \
  tests/test_run_macos_mgba_replay.py \
  tests/test_run_guarded.py \
  tools/run_macos_mgba_single_input.py \
  tools/macos_mgba_runtime_residue.py \
  tools/accept_prebattle_candidate.py \
  tools/run_macos_mgba_replay.py \
  tools/run_guarded.py
```

Observed result: exit code 0, no diagnostics.

Lua syntax command:

```bash
luac -p tools/mgba_single_input_replay.lua tools/mgba_checkpoint_replay.lua
```

Observed result: exit code 0, no diagnostics.

Exact hash command and output:

```bash
shasum -a 256 tools/mgba_single_input_replay.lua tools/mgba_checkpoint_replay.lua
```

```text
ca0ec91d17f28c67f79f0f94d4aef215ab5417650e4bc90291db938a2429c884  tools/mgba_single_input_replay.lua
d1d1dbcce947f6a9149963cc947ef76944e5ac9065cb9906e12bd1a2dda173af  tools/mgba_checkpoint_replay.lua
```

Pre-commit fix-scope whitespace command:

```bash
git diff --check -- tests/test_run_macos_mgba_single_input.py \
  .superpowers/sdd/task-4.7-step1-report.md \
  tools/run_macos_mgba_single_input.py
```

Observed result: exit code 0, no diagnostics. The committed fix range will also be
checked as `git diff --check HEAD^..HEAD` after the new local commit.

### Changed files, commit, and concerns

- Changed: `tests/test_run_macos_mgba_single_input.py` and this report.
- Unchanged: `tools/run_macos_mgba_single_input.py` and every other production file.
- Commit: `PENDING` (one new local commit; no amend and no push).
- Concern: the original 14-test historical RED cannot be upgraded retroactively;
  the isolated 16-test reconstruction above is the honest replacement evidence.
- No ROM/mGBA session was launched, no input was sent, and no candidate, checkpoint,
  plan, OpenSpec task, or roadmap state was changed.
