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
| prepare/local clone + apply check/apply | completed/0 | 68.7578125 MiB | 60856 | clean |
| configure | completed/0 | 13.4765625 MiB | 61147 | clean |
| build (`--parallel 2`) | completed/0 | 10.90234375 MiB | 62291 | clean |
| `--help` | completed/0 | 0.95703125 MiB | 64862 | clean |
| `--version` | completed/0 | 0.81640625 MiB | 64886 | clean |
| staged base-ROM Lua sentinel (final) | completed/0 | 18.12109375 MiB | 67483 | clean |

The produced binary is:

- path:
  `/Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-qt-20260715-1/qt/mGBA.app/Contents/MacOS/mGBA`;
- version: `mGBA 0.10.5 (26b7884bc25a5933960f3cdcd98bac1ae14d42e2-dirty)`, where
  `-dirty` records the intentional two-file uncommitted backport in the isolated clone;
- identity label: `mGBA 0.10.5 + Qt script backport`;
- binary SHA-256:
  `af6ab51a2ff63d6067908938aa74181fe2bbad0c441e231f3c4dbc80e7d6fe5d`;
- file identity: `Mach-O 64-bit executable x86_64`;
- help capability: `--script FILE Script file to load on start`.

The final sentinel copied `rom/base.gba` into the ignored guarded evidence directory,
loaded a generated Lua script through the patched Qt CLI, observed its first frame and
PC (`140299572`), wrote `{"script_loaded":true,"frame":1,...}`, and exited 0. Staging
is important: the first diagnostic run opened the repository ROM directly and mGBA
created `rom/base.sav`; the generated file was identified from the before/after status,
removed, and a RED/GREEN regression now confines this save side effect to `build/`.

This result proves only the backported Qt script interface and base-ROM execution. It
does not prove checkpoint replay, frame-80 capture, or acceptance of the scenario-41
prebattle candidate; those remain outside Step 1.

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
