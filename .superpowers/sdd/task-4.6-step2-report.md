# Task 4.6 Step 2 implementation report

Status: DONE

## Scope

Implemented only the parameterized, zero-input frame-80 replay chain. No Step 3
inspector/acceptance work, ledger/evidence/roadmap updates, or controller input was
performed.

Changed files:

- `tools/mgba_checkpoint_replay.lua`
- `tools/run_macos_mgba_replay.py`
- `tests/test_run_macos_mgba_replay.py`
- `tools/README.md`
- `notes/macos-intel-runtime-preflight-20260715.md`
- `.superpowers/sdd/task-4.6-step2-report.md`

## TDD evidence

Initial RED:

```text
python3 -m unittest tests.test_run_macos_mgba_replay -v
Ran 2 tests
FAILED (errors=2)
```

The failures were the intended missing Lua file and missing Python module. The minimal
GREEN then passed 2/2.

The second RED expanded the runner contract:

```text
python3 -m unittest tests.test_run_macos_mgba_replay -v
Ran 14 tests
FAILED (errors=12)
```

The 12 intended failures were missing manifest/hash/script-order/guard/path/freshness/
PGID/payload/output/main-wiring interfaces. After the minimal implementation, one
integration failure remained because macOS `tempfile` traverses the system
`/var -> /private/var` alias. Evidence showed this was an ancestor-alias classification
bug, not a replay failure. Canonical resolution plus final-object symlink rejection and
resolved overlap checks fixed the root cause; the full 14-test suite passed.

A final RED required the validated audit to persist binary, patch, manifest, replay
script, pre-script order and staged-ROM identities. It failed with
`KeyError: 'binary_sha256'`; the minimal GREEN added those provenance fields and the full
suite passed again.

The final boundary RED contained three focused failures: missing Lua BOOL assertions for
state load/save, no derived staged `.sav` reservation in output overlap checks, and no
post-run critical hash revalidation. The focused command failed 3/3 for those intended
reasons. Minimal GREEN added the assertions, reserved the derived sidecar against every
input/script/output, and rehashed binary/ROM/input-state/staged-ROM after the run. The
focused command then passed 3/3 and the complete suite passed 16/16.

## Real guarded smoke

Command: `python3 tools/run_macos_mgba_replay.py ... --capture-frame 80` using:

- binary:
  `/Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-fix1-20260715/qt/mGBA.app/Contents/MacOS/mGBA`;
- manifest:
  `/Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-manifest-fix1-20260715.json`;
- ROM: `rom/base.gba`;
- input: `artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9`;
- outputs: `build/macos-prebattle-frame80-step2-20260715/`.

Final evidence:

- run ID `b1cd4bb851a2be94c60bc48f4a28d82c`;
- state SHA-256 `525c05c967ee7daa74f008d195dc3ec7595110167916bacf0c1051d750610c4d`;
- PNG SHA-256 `6a4a715a35072b0a5d68b8a33de4076598fc67fb435e816516a9b211bb76e5f0`;
- audit/sentinel SHA-256 `bd0665741b3770988744eab7d57e73214f8921d5aa3003ef04d53b294e35e259`;
- guard summary SHA-256 `c9c08e2274687a4d1a42895565deb08719172cd36bf34c1cf0f4ac326afab42c`;
- `completed/0`, peak RSS `52.0234375 MiB`, child/PGID `7013`, non-degraded
  POSIX process group, exact final PGID query clean;
- `inputs=[]`, capture/frame `80`, staged ROM hash equals the source ROM, and no
  `rom/base.sav` exists.

A separate real backport smoke supplied two no-input pre-scripts. The guard summary
command preserved pre-1, pre-2, replay order; pre-2 asserted pre-1's marker before
appending, and `order-proof.txt` contains exactly `12` (SHA-256
`6b51d431df5d7f141cbececcf79edf3dd861c3b4069f0b11661a3eefacbba918`).
That run completed/0 with run ID `67e2a24e11f8f74067d80ac758877591`, peak RSS
`52.03125 MiB`, child/PGID `6062`, non-degraded protection and a clean final PGID
query. Its audit remained `inputs=[]`.

Boundary: the smoke proves only fresh replay outputs. Menu image equivalence, resume PC,
unwind, WRAM and candidate acceptance remain Step 3 work.
