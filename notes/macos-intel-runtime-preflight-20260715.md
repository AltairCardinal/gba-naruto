# macOS Intel runtime migration preflight (2026-07-15)

## Outcome and boundary

The shared resource guard now admits and monitors owned commands on the tested Intel
Mac. Darwin available memory is derived from `vm_stat`; process-tree RSS is derived from
a single PGID-aware `ps` snapshot. The launcher continues to create one POSIX
session/process group and cleanup targets only that owned group. No process-name cleanup
is allowed.

The official mGBA 0.10.5 Qt build has scripting support and Lua compiled in, but its CLI
does **not** support `--script`. This is an upstream 0.10.5 frontend capability boundary,
not a failed local build. This preflight does not modify the external mGBA source. A later
runtime task must use a separately proven interface (for example the existing GDB path)
or explicitly scope a different frontend/version; it must not assume `mGBA --script`.

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
