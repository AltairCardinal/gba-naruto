# macOS Intel runtime migration preflight (2026-07-15)

## Outcome and boundary

The shared resource guard now admits and monitors owned commands on the tested Intel
Mac. Darwin available memory is derived from `vm_stat`; process-tree RSS is derived from
a single PGID-aware `ps` snapshot. The launcher continues to create one POSIX
session/process group and cleanup targets only that owned group. No process-name cleanup
is allowed.

The official, unpatched mGBA 0.10.5 Qt build has scripting support and Lua compiled in,
but its CLI does **not** support `--script`. This remains the official 0.10.5 frontend
capability boundary, not a failed local build. Task 4.6 Step 1 has now separately proven
an explicitly identified `mGBA 0.10.5 + Qt script backport` runtime. Callers must use its
recorded patch/binary identity and must not treat an arbitrary official 0.10.5 binary as
script-capable.

## Task 4.6 Step 1 Qt script backport (2026-07-15)

The upstream two-file change was recovered from official commit
`7cacae126207de5499857439b9c7919bf8e882c2` and saved as
`tools/patches/mgba-0.10.5-qt-script-cli.patch`. It changes only:

- `src/platform/qt/ConfigController.cpp`, which registers and parses repeatable
  `--script FILE` arguments and advertises them in Qt frontend help;
- `src/platform/qt/Window.cpp`, which opens the scripting controller and loads the
  requested scripts after a game controller starts.

Patch SHA-256 is
`e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6`.
`git apply --check` succeeded against the clean cached 0.10.5 commit
`26b7884bc25a5933960f3cdcd98bac1ae14d42e2`; the clean cache remained unchanged, while
the independent backport workspace reported exactly those two modified paths.

The guarded build used Qt 5 `/usr/local/opt/qt@5`, Release, scripting ON, Qt ON, SDL
OFF, CMake policy minimum 3.5, Ninja, and parallelism 2. All phases used the project
heavy lock, a 4096 MiB admission floor, a 1536 MiB owned-tree RSS ceiling, and
non-degraded POSIX process-group ownership:

| Phase | Result | Peak RSS | Child/PGID | Final exact PGID query |
|---|---|---:|---:|---|
| prepare/local clone + apply check/apply | completed/0 | 73.09765625 MiB | 80958 | clean |
| configure | completed/0 | 12.9140625 MiB | 81096 | clean |
| build (`--parallel 2`) | completed/0 | 10.80859375 MiB | 82069 | clean |
| `--help` | completed/0 | 0.796875 MiB | 83519 | clean |
| `--version` | completed/0 | 0.91796875 MiB | 83524 | clean |
| staged base-ROM Lua sentinel (final) | completed/0 | 0.8984375 MiB | 83529 | clean |

The produced binary is:

- path:
  `/Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-fix1-20260715/qt/mGBA.app/Contents/MacOS/mGBA`;
- version: `mGBA 0.10.5 (26b7884bc25a5933960f3cdcd98bac1ae14d42e2-dirty)`, where
  `-dirty` records the intentional two-file uncommitted backport in the isolated clone;
- identity label: `mGBA 0.10.5 + Qt script backport`;
- binary SHA-256:
  `20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408`;
- file identity: `Mach-O 64-bit executable x86_64`;
- help capability: `--script FILE Script file to load on start`.

The final sentinel copied `rom/base.gba` into the ignored guarded evidence directory,
loaded a generated Lua script through the patched Qt CLI, observed its first frame and
PC (`140299572`), wrote a marker with fresh run ID
`41af6df222612f6bd22f0f5499be1fdd`, and exited 0. The same run ID is attached to the
sentinel summary in the manifest, so an old successful marker cannot satisfy a new run.
The source and staged ROM hashes both remained
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`. Staging
is important: the first diagnostic run opened the repository ROM directly and mGBA
created `rom/base.sav`; the generated file was identified from the before/after status,
removed, and a RED/GREEN regression now confines this save side effect to `build/`.

The review-fix run additionally rejects all canonical path overlap before side effects,
passes one SHA-verified patch byte payload through check/apply/manifest without reopening
the source path, deletes stale phase outputs and staged-ROM sidecars, requires wrapper
return code and fresh summary to agree, and revalidates the clean source cache after the
sentinel. The final cache status was empty; the isolated workspace changed exactly the
two declared Qt files, and all six owned PGIDs above were absent after completion.

This result proves only the backported Qt script interface and base-ROM execution. It
does not prove checkpoint replay, frame-80 capture, or acceptance of the scenario-41
prebattle candidate; those remain outside Step 1.

## Task 4.6 Step 2 guarded frame-80 replay (2026-07-15)

The new `tools/run_macos_mgba_replay.py` runner and
`tools/mgba_checkpoint_replay.lua` script replayed the repository prebattle candidate
for 80 relative frames with `inputs=[]`. The real run used the Step 1 fresh binary and
manifest, a staged copy of `rom/base.gba`, the shared heavy lock, a 4096 MiB admission
floor, a 1536 MiB owned-PGID RSS ceiling, non-degraded POSIX process-group protection,
and `QT_QPA_PLATFORM=offscreen`.

The final fresh run is retained under the ignored directory
`build/macos-prebattle-frame80-step2-20260715/` for direct reuse by Step 3:

- run ID: `b1cd4bb851a2be94c60bc48f4a28d82c`;
- input state SHA-256:
  `b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078`;
- staged ROM SHA-256:
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`;
- frame-80 state SHA-256:
  `525c05c967ee7daa74f008d195dc3ec7595110167916bacf0c1051d750610c4d`;
- screenshot SHA-256:
  `6a4a715a35072b0a5d68b8a33de4076598fc67fb435e816516a9b211bb76e5f0`;
- audit and sentinel SHA-256:
  `bd0665741b3770988744eab7d57e73214f8921d5aa3003ef04d53b294e35e259`;
- guard summary SHA-256:
  `c9c08e2274687a4d1a42895565deb08719172cd36bf34c1cf0f4ac326afab42c`;
- guard result: `completed/0`, peak owned RSS `52.0234375 MiB`, child/PGID
  `7013`, `degraded=false`, and a clean exact final PGID query.

Both the state and screenshot are 240x160 PNG containers. The runner was deliberately
rerun over earlier regular outputs; they were removed before launch and replaced with a
new run ID and state hash. The source ROM directory still has no `base.sav` sidecar.

During integration testing, rejecting every ancestor symlink incorrectly rejected the
normal macOS `/var -> /private/var` path used by `tempfile`. The durable rule is now to
canonicalize ancestor aliases, reject final-component symlinks and unsafe resolved
overlap, and fail closed on directory/FIFO outputs. This preserves alias safety without
hard-coding an operating-system path exception.

Three additional fail-closed boundaries were verified before the final smoke. Lua now
asserts both `emu:loadStateFile` and `emu:saveStateFile` BOOL results; screenshot remains
a void API and is checked through the fresh PNG output. The derived staged `.sav` is
reserved in canonical uniqueness/overlap validation. After mGBA exits, the runner
rehashes binary, source ROM, input state and staged ROM before writing final provenance.

Repeatable Qt `--script` order was also proven in the real backported frontend, not only
at argv construction. Two no-input pre-scripts wrote `1` and then asserted that value
before appending `2`; the retained
`build/macos-prebattle-frame80-step2-order-20260715/order-proof.txt` contains exactly
`12` with SHA-256
`6b51d431df5d7f141cbececcf79edf3dd861c3b4069f0b11661a3eefacbba918`.
The guarded command order was pre-1, pre-2, replay; the run completed/0 with run ID
`67e2a24e11f8f74067d80ac758877591`, peak RSS `52.03125 MiB`, child/PGID `6062`,
non-degraded protection and a clean exact PGID query. Both pre-scripts contain no key
API call and the replay audit remained `inputs=[]`.

This Step 2 result proves only the replay and fresh-output chain. It does **not** inspect
or accept the prebattle menu, task 2 resume PC, unwind chain, or `[0x0202680C]`; it does
not update the checkpoint ledger and must not be used as evidence for controller entry.
No Down, A, or other input was sent.

## Test host and guard behavior

- Host: macOS 14.8.4 (23J319), `MacBookPro16,1`, `x86_64`.
- Admission source: `vm_stat`; available pages are `Pages free`, `Pages inactive`, and
  `Pages speculative`, multiplied by the page size reported in the header.
- RSS source: `ps -axo pid=,pgid=,rss=`; every row in the launched owned PGID is summed,
  including reparented descendants after the root exits, while unrelated groups are
  excluded.
- Ownership backend: `posix-process-group`. The child starts a new session, and timeout,
  memory-limit, interruption, and final cleanup address only that exact group.
- Failure behavior: missing/malformed Darwin counters, an empty/all-malformed snapshot,
  a snapshot without the owned PGID, or a failed `vm_stat`/`ps` command fails closed
  through the existing protection-failure path (exit 125).

The TDD RED was reproduced without rolling back the shared worktree: a temporary
`git archive HEAD` received the current two modified test modules while retaining the
HEAD production guard. The three focused tests then failed for the intended reasons:

1. Darwin available memory raised `physical memory reader is unsupported on darwin`.
2. Darwin RSS attempted `/proc` and raised `FileNotFoundError`.
3. The old real Darwin CLI integration returned 125 at Darwin admission because
   `available_physical_memory_mib()` was unsupported; it did not reach RSS wiring. The
   focused RSS unit RED independently proved the `/proc` implementation gap.

Running those same three tests against the current worktree passed. The complete guard
suite also passed (commands and counts are in the task report).

The real current-tree smoke launched a Python child through `tools/run_guarded.py`, wrote
its marker, slept long enough for sampling, and completed with:

- reason `completed`, exit code 0;
- backend `posix-process-group`, degraded `false`;
- peak owned-tree RSS `9.23828125 MiB`;
- child/PGID `31095`, with no row left in an exact `ps` PGID query after completion.

The review-fix integration additionally lets the launched root exit, waits before a
grandchild in the same owned PGID allocates 48 MiB, and enforces a 32 MiB limit. The real
guard result was `memory-limit`/125 with peak owned-group RSS `57.23828125 MiB`; root PID
and PGID `45851`, grandchild PID `45853`, and the final exact PGID query was clean.

## Official mGBA 0.10.5 provenance

The source and build caches are deliberately outside the repository and are not project
artifacts to commit:

- official source: `https://github.com/mgba-emu/mgba.git`;
- tag: `0.10.5`;
- commit: `26b7884bc25a5933960f3cdcd98bac1ae14d42e2`;
- read-only source cache: `/Users/altair/.cache/codex-tools/mgba/0.10.5-src`;
- build directory: `/Users/altair/.cache/codex-tools/mgba/0.10.5-build-qt`;
- binary: `/Users/altair/.cache/codex-tools/mgba/0.10.5-build-qt/qt/mGBA.app/Contents/MacOS/mGBA`.

`git status --short` was empty in the source cache after investigation. The source tag
and commit were checked with `git describe --tags --exact-match HEAD` and
`git rev-parse HEAD`; no external source file was edited.

### Guarded clone, configure, and build

The non-committed `build/resource-guard/*.json` summaries captured these owned commands:

| Phase | Owned command/result | Peak RSS | Final exact PGID check |
|---|---|---:|---|
| clone | `git clone --branch 0.10.5 --depth 1 https://github.com/mgba-emu/mgba.git /Users/altair/.cache/codex-tools/mgba/0.10.5-src`; completed/0 | 50.0078125 MiB | clean |
| configure attempt | Same configure below without `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`; child-exit/1 | 1.31640625 MiB | clean |
| configure | `cmake -S .../0.10.5-src -B .../0.10.5-build-qt -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/usr/local/opt/qt@5 -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DENABLE_SCRIPTING=ON -DBUILD_QT=ON -DBUILD_SDL=OFF`; completed/0 | 64.58203125 MiB | clean |
| build | `cmake --build /Users/altair/.cache/codex-tools/mgba/0.10.5-build-qt --parallel 2`; completed/0 | 553.62109375 MiB | clean |

The first configure and the successful retry differed by the CMake compatibility-policy
override. The successful configure reported Release, Qt ON, SDL OFF, scripting ON, Lua
5.5.0 found, and AppleClang 16.0.0. The build completed all 367 Ninja edges. It emitted
upstream compiler/linker warnings, including old deployment availability and several
unused/sign/qualifier warnings; none stopped the build. These warnings remain a concern
for any future distribution-quality package but do not invalidate this local preflight.

## Binary identity and CLI capability

The pinned binary was inspected directly:

```text
--version: mGBA 0.10.5 (26b7884bc25a5933960f3cdcd98bac1ae14d42e2)
file: Mach-O 64-bit executable x86_64
SHA-256: 30b2ed9065123405463ab6e372cf43e1e6febfaa9598d77cc8684cde61cdaae2
```

`--help` exits successfully and lists the generic debugger/GDB, ROM, graphics, `--ecard`,
and `--mb` options. It contains no `--script`. Running
`mGBA --script /tmp/nonexistent-task45.lua` reproducibly exits 1 and prints
`mGBA: unrecognized option '--script'` plus usage. These three capability checks were
rerun through `tools/run_guarded.py` after the PGID fix:

| Guarded command | Guard result | Peak owned-PGID RSS | Child/PGID | Final exact PGID check |
|---|---|---:|---:|---|
| `mGBA --version` | completed/0 | 4.03125 MiB | 44642 | clean |
| `mGBA --help` | completed/0 | 0.16796875 MiB | 45016 | clean |
| `mGBA --script /tmp/nonexistent-task45.lua` | child-exit/1 | 0.171875 MiB | 45390 | clean |

The `--script` result is the expected child capability rejection, not a guard failure;
all summaries report `posix-process-group` and `degraded: false`. The ignored evidence
files are `build/resource-guard/mgba-{version,help,script}-darwin-fixed.json` and are not
committed.

Systematic source tracing explains the mismatch:

- top-level `CMakeLists.txt` makes `ENABLE_SCRIPTING` build the scripting library and
  enables Lua;
- `src/platform/qt/CMakeLists.txt` conditionally compiles the Qt
  `ScriptingController`/`ScriptingView` files;
- `src/platform/qt/Window.cpp` exposes scripting through the GUI Tools menu;
- `src/feature/commandline.c` has no `script` entry in the generic option table;
- `src/platform/qt/ConfigController.cpp` registers only graphics plus the Qt frontend
  `ecard` and `mb` sub-options.

Therefore `ENABLE_SCRIPTING=ON` means library/Qt GUI scripting support in official
0.10.5; it does not imply a script-loading CLI switch. The important future-maintenance
files are the repository guard implementation/tests and this note; the external source
locations above are evidence only and must remain unmodified.
