# Tools

## `scan_rom.py`

Preliminary static scanner for a GBA ROM.

Current checks:

- aligned 32-bit values that point back into the ROM address space
- ASCII-like runs
- zero-filled runs that may indicate free space
- coarse byte-frequency summary

Example:

```bash
python3 tools/scan_rom.py '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba'
```

The machine-readable output is written to `notes/scan-report.json` by default.

## `find_pointer_refs.py`

Finds all aligned `32-bit` references to a target ROM offset or GBA address.

Example:

```bash
python3 tools/find_pointer_refs.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x4081 \
  --output notes/pointer-refs-004081.json
```

## `analyze_table.py`

Analyzes a ROM region as a fixed-size table and classifies each `u32` field.

Example:

```bash
python3 tools/analyze_table.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x596F98 \
  0x10 \
  16 \
  --output notes/table-596F98-10.json
```

## `inspect_block.py`

Inspects a pointed ROM block and makes a coarse guess about whether it looks like:

- nested descriptor
- palette-like data
- sparse binary
- binary or compressed data

Example:

```bash
python3 tools/inspect_block.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x17A1A4 \
  0x40 \
  --output notes/block-17A1A4.json
```

## `profile_table_blocks.py`

Walks a fixed-size pointer table and classifies the blocks referenced by each column.

Example:

```bash
python3 tools/profile_table_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x596F98 \
  0x10 \
  16 \
  --output notes/profile-596F98.json
```

## `find_sjis_blocks.py`

Scans the ROM for Shift-JIS-like text regions, useful for locating script or encoded Japanese resources.

Example:

```bash
python3 tools/find_sjis_blocks.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  --output notes/sjis-blocks.json
```

## `extract_text_block.py`

Splits a suspected text block into candidate strings using `0x00` and line breaks as separators.

Example:

```bash
python3 tools/extract_text_block.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  0x76C \
  0x1A0 \
  --output notes/text-block-00076C.json
```

## `find_similar_tables.py`

Searches the ROM for runs of `0x10`-byte rows that look like four-pointer resource tables.

Example:

```bash
python3 tools/find_similar_tables.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  --start 0x500000 \
  --min-rows 4 \
  --output notes/similar-tables.json
```

## `patch_sjis.py`

Creates a patched ROM copy by writing Shift-JIS text at a fixed ROM offset.

Example:

```bash
python3 tools/patch_sjis.py \
  '火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba' \
  'rom/experiment.gba' \
  0x76D \
  試験 \
  --expected-len 4
```

## `mgba_trace_dialogue_writes.lua`

Headless scripted watchpoint probe for the opening dialogue scene.

Supported targets through `NARUTO_TRACE_TARGET`:

- `wram`
- `vram_tilemap`
- `vram_glyph`

Example:

```bash
NARUTO_TRACE_TARGET=wram \
tools/run_headless_mgba.sh \
  tools/mgba_trace_dialogue_writes.lua \
  build/naruto-sequel-dev.gba
```

Outputs land in `notes/` as `dialogue-watch-*.log`, `dialogue-watch-*.summary.txt`, and `dialogue-watch-*.done`.

## `summarize_watch_hits.py`

Converts raw watchpoint logs into short markdown summaries.

Example:

```bash
python3 tools/summarize_watch_hits.py \
  notes/dialogue-watch-wram.log \
  --title 'Dialogue WRAM Watch Summary' \
  --output notes/dialogue-watch-wram.md
```

## `disasm_thumb.py`

Disassembles a ROM window as GBA Thumb code using the vendored `capstone` package in `tools/_vendor/`.

Example:

```bash
python3 tools/disasm_thumb.py \
  build/naruto-sequel-dev.gba \
  0x08066D74 \
  --before 0x30 \
  --size 0x80 \
  --output notes/disasm-08066D74.txt
```

## `find_thumb_calls.py`

Scans for candidate ARMv4T Thumb direct branches that target a specific ROM address.
The scanner recognizes two-halfword `bl` and unconditional `b` encodings without
constructing Capstone instruction objects. Immediate `blx` is not supported because
the GBA's ARM7TDMI uses ARMv4T, where that encoding is unavailable. Use the optional
exclusive `--start`/`--end` ROM-address bounds to limit a search region.

Example:

```bash
python3 tools/find_thumb_calls.py \
  build/naruto-sequel-dev.gba \
  0x08066D14 \
  --start 0x08060000 \
  --end 0x08070000 \
  --output notes/calls-08066D14.txt
```

## Resource guard for heavy tools and runtime probes

Long-running reverse-engineering commands must enter through `run_guarded.py`. The
literal `--` separator is required; everything after it is the one owned child command.
For example, run a bounded static scan from the repository root with:

```bash
python tools/run_guarded.py \
  --summary build/resource-guard/thumb-calls.json \
  -- python tools/find_thumb_calls.py \
  build/naruto-sequel-dev.gba 0x08066D14 \
  --start 0x08060000 --end 0x08070000 \
  --output notes/calls-08066D14.txt
```

Run the Chromium probe through its guarded package entry (from `play/_scripts`):

```bash
npm run probe:guarded
```

Both commands use the same non-blocking project `heavy` lock. Defaults are 1024 MiB
minimum available physical memory, 1536 MiB maximum owned process-tree RSS, 600 seconds
wall timeout, 60 seconds without a complete stdout/stderr progress line, 1 second RSS
sampling, and 5 seconds termination grace. Runtime probes emit parseable
`resource-progress` JSON lines at browser, page, core, checkpoint, phase, and result
boundaries.

The npm entry pins `--lock-file ../../build/resource-guard/heavy.lock`; do not remove or
relocate that argument, because the npm working directory is `play/_scripts` while static
guarded commands run from the repository root.

Exit code 75 means lock contention or admission rejection; 124 means wall/idle timeout;
125 means memory-limit, launch, or protection failure. Ordinary completion returns the
child exit code. Each run atomically writes the requested JSON summary with child PID,
peak owned-tree RSS, backend, reason, and degradation state.

Every command whose executable name is `mGBA` or starts with `mGBA-` also passes the
`mgba_runtime_safety.py` policy before launch. The policy reads every actual `--script`
file, including temporary scripts under `build/`. The scan blanks Lua strings and
comments before evaluating code tokens. Scripts may use only direct
`os.getenv(...)` and `io.open(...)` access required by the fixed runners; other
`os`, `io`, `ffi`, or `posix` access and dynamic-global loading primitives are rejected
before the child starts. Fixed
Lua callbacks must write their run-bound completion marker and then remain inert; only
the resource guard may stop the owned process group.

The same policy persists a confirmed inventory of
`~/Library/Logs/DiagnosticReports/mGBA-*.ips`, snapshots it before launch, and waits
briefly after cleanup. Preflight, launch, cleanup, and crash-report settlement all run
while the same heavy lock is held. A new or changed report—including one that appeared
after the previous settlement window—overrides a zero exit or
success-marker result with `mgba-crash-report/125` and creates
`build/resource-guard/mgba-crash-latch.json`. While that latch exists, later mGBA runs
fail before launch; non-mGBA guarded commands remain available. Clearing the latch is
an explicit acknowledgement through `clear_crash_latch()` in
`tools.mgba_runtime_safety`; it appends the previous latch and current report inventory
to `mgba-crash-latch.json.history.jsonl` before removing the latch. Do not delete the
latch directly or disable macOS crash reports to bypass this gate.

Cleanup is exact-tree only: a Windows Job Object or POSIX process group created for that
run. Never add `pkill`, `killall`, `taskkill /IM`, `Stop-Process` by name, or any other
process-name cleanup. Missing isolation or monitoring fails closed unless an explicitly
audited degraded run is requested and recorded.

On macOS, admission reads `vm_stat` and treats free, inactive, and speculative pages as
available physical memory. Owned-tree RSS comes from one `ps` PID/PGID/RSS snapshot per
sample and sums every process whose PGID equals the launched owned group. This keeps
monitoring descendants after the root exits and they are reparented. Launch and cleanup
use that same new POSIX session/process group, exactly as on other POSIX hosts; never
replace the ownership boundary with PPID ancestry or process-name matching. Empty,
malformed, failed, or owned-PGID-free `vm_stat`/`ps` responses fail closed. The Intel
runtime preflight and the guarded mGBA 0.10.5 CLI evidence are recorded in
[`notes/macos-intel-runtime-preflight-20260715.md`](../notes/macos-intel-runtime-preflight-20260715.md).

## Pinned macOS Intel mGBA Qt script backport

`build_macos_mgba.py` builds one explicitly identified local runtime:
`mGBA 0.10.5 + Qt script backport`. It accepts only a clean checkout at tag `0.10.5`
and commit `26b7884bc25a5933960f3cdcd98bac1ae14d42e2`. The versioned patch is the
two-file Qt CLI change from upstream commit
`7cacae126207de5499857439b9c7919bf8e882c2`; its repository SHA-256 is
`e76c8fc4f5451bdffe28b7f3595cd441bbb90fb1aa88a926cfbe4f1254d3d2a6`.

The builder rejects a wrong tag/commit, any source dirt, an unexpected patch path, or a
failed `git apply --check`. Before creating or deleting anything, it canonicalizes every
source, ROM, patch, workspace, build, evidence, and manifest path and rejects equality,
ancestor/descendant overlap, and symlink aliases. It reads the pinned patch exactly once,
verifies its SHA and metadata, transports those exact bytes to the guarded prepare child,
and supplies the same verified metadata to the manifest. Both `git apply --check` and
`git apply` consume that in-memory byte payload over stdin; a mutable patch pathname is
never reopened. It clones the clean cache into a new independent cache checkout, applies
the patch there, and never writes to the clean cache or the user's
`/Users/altair/github/mgba-src` tree. Prepare/copy, configure, build, `--help`, version,
and the real Lua sentinel all use `run_guarded.py` with the same heavy lock, 4096 MiB
admission floor, 1536 MiB owned-tree RSS ceiling, and non-degraded PGID ownership. An
admission rejection is reported as `BLOCKED`; the memory floor is never lowered.
The sentinel phase passes the mGBA executable directly to the guard; it must never use
an intermediate launcher that hides the real `--script` command from the safety policy.

Example (all work/build outputs remain outside the repository or under ignored
`build/` evidence):

```bash
python3 tools/build_macos_mgba.py \
  --source-cache /Users/altair/.cache/codex-tools/mgba/0.10.5-src \
  --workspace /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-src \
  --build-dir /Users/altair/.cache/codex-tools/mgba/0.10.5-script-backport-build-qt \
  --rom rom/base.gba \
  --evidence-dir build/resource-guard/mgba-0.10.5-script-backport \
  --manifest build/mgba-0.10.5-script-backport-manifest.json
```

The configure fingerprint is Release + Qt 5 at `/usr/local/opt/qt@5`, scripting ON,
Qt ON, SDL OFF, CMake policy minimum 3.5, Ninja, and build parallelism 2. Success
requires fresh guard summaries from the current wrapper invocation to be `completed/0`,
help to contain `--script`, the binary
to be Mach-O x86_64, and a Lua script to execute on the first frame of a staged copy of
`rom/base.gba` before the guard stops the owned process tree after its success marker.
ROM staging keeps mGBA save-file side effects
inside the ignored evidence directory; prior staged ROM sidecars are removed before the
copy. Help/version outputs, summaries, and the sentinel marker are removed before their
phase, and the sentinel result must carry a newly generated run ID that is also attached
to that run's manifest summary. The clean source cache is validated again after the real
sentinel. The manifest records the version/source/backport commits, patch and binary
SHA-256 values, architecture, flags, current-run sentinel, and complete summaries.

Boundary: this tool only produces and proves the Step 1 runtime. It does not perform
checkpoint replay, accept scenario evidence, update the runtime ledger, or execute any
Task 4.6 Step 2/3 behavior.

## macOS guarded checkpoint replay

`run_macos_mgba_replay.py` and `mgba_checkpoint_replay.lua` provide the Task 4.6 Step 2
checkpoint replay boundary. The Python runner requires caller-pinned SHA-256 values for
both the backport binary and its build manifest, in addition to the source ROM/state
hashes. It verifies those pins and the manifest's fixed label/version/source/backport/
patch/x86_64 fields before removing any old output. A forged self-consistent manifest
paired with an arbitrary binary therefore cannot become replay provenance.

The default `zero-input` evidence mode accepts only the repository
`mgba_checkpoint_replay.lua` at its pinned SHA-256, rejects every `--pre-script` and
custom replay before output side effects, and finalizes evidence only with
`evidence_mode=zero-input`, `zero_input_verified=true`, and `inputs=[]`.
`script-order-diagnostic` is a separate non-acceptance mode that permits repeatable
pre-scripts for Qt CLI-order testing. Every pre-script is emitted as a `--script`
argument before the replay script, but finalized evidence is explicitly marked
`zero_input_verified=false`; it must never be used for checkpoint acceptance. Missing
scripts fail before any output is removed or created.

All input and output paths are canonicalized before side effects. Final-component
symlinks, duplicate or ancestor/descendant aliases, input/output overlap, and an output
ROM beside the source ROM are rejected. Canonical system aliases such as macOS
`/var -> /private/var` are resolved instead of being hard-coded or rejected wholesale.
Existing regular outputs are removed before launch so they cannot satisfy a new run;
directories, FIFOs, and symlinks fail closed. The derived staged-ROM `.sav` path is
reserved during the same canonical uniqueness/overlap check, so it cannot alias any
input, script, state, PNG, audit, sentinel or summary. The source ROM is copied to the
declared staged path and stale staged `.sav` data is removed, so mGBA cannot create
`rom/base.sav`.

The runner verifies the caller-pinned manifest and binary identities against each other
and pins the Step 1 label, version, source commit, backport commit, patch SHA and x86_64
architecture. It launches
exactly one mGBA command through the shared heavy lock with a 4096 MiB admission floor,
1536 MiB owned-PGID RSS ceiling, caller-visible wall/idle timeouts, non-degraded POSIX
process-group ownership, and forced `QT_QPA_PLATFORM=offscreen`. Success requires the
wrapper return code and fresh summary to agree on `completed/0`, an exact command
fingerprint, `completion_trigger=success-marker`, a clean final PGID query, and fresh
non-empty PNG-container state, PNG, audit, and sentinel files. Each run derives a fresh
`<guard-summary>.done.json` marker path and binds its payload to the current 32-hex run
ID, capture frame, and `capture-complete` status.

The Lua script reads all configuration from `MGBA_REPLAY_*` environment variables,
asserts the BOOL results from checkpoint load/save, counts relative frame callbacks,
and at exactly the capture frame writes a state, screenshot, `inputs=[]` audit and
same-run sentinel, then writes the completion marker and leaves later callbacks inert.
Fixed Qt replay scripts must never call `os.exit` from the CPU-thread frame callback;
the resource guard owns process-tree termination after observing the marker. Screenshot
is a void API and is therefore checked by the fresh PNG signature/output validation.
The script contains no key injection. Both JSON records bind the run ID,
frame, input/output paths, ROM/state hashes and success state. After validation, the
runner adds output, binary, patch, staged-ROM and summary hashes plus peak RSS and the
clean PGID result to both records. Immediately before finalizing those records, the
runner rehashes the manifest, binary, source ROM, input state, staged ROM, replay script
and every pre-script; post-launch drift fails closed instead of being recorded as new
provenance. Final audit and sentinel records include the manifest, binary and replay
SHA-256 values plus `{path, sha256}` objects for pre-scripts, rather than unauthenticated
paths.

The completion marker is only a guard cleanup signal. It never substitutes for the
audit/sentinel equality and provenance checks, state/PNG signature and hash checks,
post-run input revalidation, exact-PGID cleanup, listener residue checks, or source and
staged `.sav` isolation. Missing or mismatched marker payloads and completed summaries
without the success-marker trigger fail closed. Outputs from a timeout, protection
failure, marker mismatch, Qt crash, or any run that creates an mGBA crash report remain
rejected raw artifacts and must not be consumed as a state for another replay.

Example:

```bash
python3 tools/run_macos_mgba_replay.py \
  --binary /absolute/mGBA.app/Contents/MacOS/mGBA \
  --build-manifest /absolute/mgba-build-manifest.json \
  --expected-build-manifest-sha256 9da6779d7c1ac3140e512b233f98abe754c4f11f3fbc8157af147e014661cc4d \
  --expected-binary-sha256 20859087582ad16942f37e70ea973a09671b320aa0936aa72e43e9915b1ed408 \
  --rom rom/base.gba \
  --state artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9 \
  --expected-rom-sha256 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b \
  --expected-state-sha256 b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078 \
  --staged-rom build/replay/staged-base.gba \
  --output-state build/replay/frame80.ss9 \
  --output-png build/replay/frame80.png \
  --audit build/replay/audit.json \
  --sentinel build/replay/sentinel.json \
  --guard-summary build/replay/guard-summary.json \
  --capture-frame 80 \
  --evidence-mode zero-input
```

Only a finalized `zero-input` run proves that a checkpoint can be replayed and freshly
captured without input. A `script-order-diagnostic` run proves CLI ordering only, even
when its replay payload still contains `inputs=[]`. Neither mode inspects the menu image,
task PC/unwind or WRAM, nor accepts a candidate in the checkpoint ledger; those are
separate Step 3 gates. The fixed zero-input replay never sends Down, A, or any other
input.

## Fixed zero-input cycle sampler and analyzer

`mgba_zero_input_cycle_sample.lua` is a bounded diagnostic pre-script for the existing
macOS checkpoint replay runner. Set `MGBA_CYCLE_OUTPUT_DIR` to an existing fresh frame
directory and `MGBA_CYCLE_MAX_FRAME=600`, then pass the sampler exactly once with
`run_macos_mgba_replay.py --capture-frame 600 --evidence-mode
script-order-diagnostic --pre-script tools/mgba_zero_input_cycle_sample.lua`. It writes
`frame-0001.png` through `frame-0600.png` and prints progress every 30 frames. The
sampler never loads or saves state, terminates mGBA, or sends input; the unchanged
checkpoint replay script remains responsible for the frame-600 state, PNG, audit,
sentinel, and completion marker used by the guard.

After a successful guarded diagnostic run, select the smallest exact RGB8 recurrence
with caller-pinned baseline and sampler hashes:

```bash
python3 tools/analyze_mgba_zero_input_cycle.py \
  --baseline-png build/cycle-source/after-a.png \
  --expected-baseline-png-sha256 "$BASELINE_PNG_SHA256" \
  --frame-dir build/cycle-sample/frames \
  --audit build/cycle-sample/audit.json \
  --sampler tools/mgba_zero_input_cycle_sample.lua \
  --expected-sampler-sha256 "$SAMPLER_SHA256" \
  --output build/cycle-sample/cycle-analysis.json
```

The analyzer requires a `240x160` normalized RGB8 baseline plus exactly 600 non-symlink
`240x160` `frame-%04d.png` files, reuses the strict RGB8 PNG fingerprint decoder, and
accepts only an audit with
`evidence_mode=script-order-diagnostic`, `zero_input_verified=false`, `inputs=[]`,
`capture_frame=600`, and exactly one sampler path/SHA binding. Its JSON records all 600
RGB hashes, baseline/sampler/audit provenance, and either the smallest period with
matching frames `[0,p,2p]` or `status=not-proven`.

The output must be a fresh non-symlink path outside the frame directory and must not
overlap the baseline, sampler, or audit. The analyzer revalidates those inputs and all
600 frame files before publishing the JSON through an atomic same-filesystem no-clobber
hard link;
any provenance drift fails closed without replacing input evidence.

Evidence boundary: this diagnostic can only choose a candidate period. It is not
zero-input acceptance evidence, does not accept or update a checkpoint, and does not
prove controller entry or player control. Those claims require later independent
`zero-input` replay and acceptance gates.

## Breakpoint frame trace failure history

The Qt-only mGBA 0.10.5 backport loads Lua after the one-shot `start` callback and does
not export `setBreakpoint`, `clearBreakpoint`, or `currentCycle`, so the retired Lua
path could miss the start and produce an unauditable empty trace. Precise native
addresses use the strict, guarded `mgba_gdb_probe.py` path instead.

## Fixed single-input macOS mGBA replay

`run_macos_mgba_single_input.py` and `mgba_single_input_replay.lua` provide the
separate Task 4.7 input segment. The CLI accepts exactly one `Down`, `Up`, `Left`, `Right`, `A`,
`B`, `L`, `R`, or `Start` event and
requires `0 < down-frame < up-frame < capture-frame`. It has no custom Lua or
`--pre-script` option. The fixed Lua contains one `emu:addKey`, one `emu:clearKey` and
one capture callback; the finalized audit therefore requires one matching event,
`evidence_mode=single-input`, `zero_input_verified=false`, and empty automatic and
recovery input lists.

The runner reuses the zero-input runner's canonical input/output checks, pinned mGBA
0.10.5 manifest/binary/patch/ROM/state hashes, fresh staged ROM and `.sav` isolation,
heavy resource guard (`4096 MiB` admission, `1536 MiB` tree RSS), non-degraded POSIX
process group, and post-run hash checks. `macos_mgba_runtime_residue.py` adds a shared,
read-only final probe: `ps` must show no process in the exact owned PGID and `lsof`
must show no mGBA TCP listener. Missing tools, malformed output, or probe errors fail
closed; the module never kills a process. `accept_prebattle_candidate.py` imports the
same residue functions and retains its existing API.

Like the zero-input runner, the fixed single-input Lua writes audit and sentinel before
the bound completion marker and never calls CPU-thread `os.exit`. The guard marker is
only the owned-tree cleanup trigger; all state/PNG, audit/sentinel, provenance, hash,
PGID, listener and save-residue gates remain mandatory before the candidate is usable.

Example (the caller must supply the approved state and its actual hash):

```bash
python3 tools/run_macos_mgba_single_input.py \
  --binary /absolute/mGBA.app/Contents/MacOS/mGBA \
  --build-manifest /absolute/mgba-build-manifest.json \
  --expected-build-manifest-sha256 MANIFEST_SHA256 \
  --expected-binary-sha256 BINARY_SHA256 \
  --rom rom/base.gba --expected-rom-sha256 ROM_SHA256 \
  --state artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9 \
  --expected-state-sha256 STATE_SHA256 \
  --key Down --down-frame 5 --up-frame 13 --capture-frame 80 \
  --staged-rom build/single-input/staged-base.gba \
  --output-state build/single-input/after-input.ss9 \
  --output-png build/single-input/after-input.png \
  --audit build/single-input/audit.json \
  --sentinel build/single-input/sentinel.json \
  --guard-summary build/single-input/guard-summary.json
```

This command only creates a build candidate. It does not accept a checkpoint or prove
controller entry/player control. Every reusable input boundary must pass a separate
zero-input stability run before it can authorize the next segment; a failed hash,
guard, output, PGID, or listener gate leaves the raw candidate unfinalized and forbids
that next key.

## Offline prebattle checkpoint acceptance

`inspect_mgba_savestate.py` can now bind an explicitly selected task stack chain to
the base ROM instead of treating arbitrary ROM-looking stack words as frames. Each
`--unwind-return STACK_ADDRESS:BL_TARGET` reads that exact IWRAM slot, derives the
Thumb callsite from the raw return word, and requires `thumb_branch.decode_thumb_bl`
to recover the declared target. Stack slots must be ordered at or above the selected
task SP. `--memory-byte` adds explicit WRAM/IWRAM byte observations. For example:

```bash
python3 tools/inspect_mgba_savestate.py \
  build/macos-prebattle-frame80-step2-20260715/frame80.ss9 \
  --rom rom/base.gba \
  --task-slot 2 \
  --unwind-return 0x03001220:0x08067158 \
  --unwind-return 0x03001240:0x080884DC \
  --unwind-return 0x03001278:0x08088F10 \
  --memory-byte 0x0202680C
```

`accept_prebattle_candidate.py` is the fail-closed Task 4.6 Step 3 gate. It consumes
the already captured strict frame-80 directory and does not run mGBA or inject keys.
Using only the Python standard library, it validates every PNG chunk CRC, requires
RGB8 240×160 IHDRs, rejects incomplete or trailing zlib streams, accepts only PNG row
filters 0..4, implements Sub/Up/Average/Paeth reversal, and compares normalized RGB
pixel SHA-256 values for the tracked candidate and frame-80 screenshot. Savestate
loading uses the same strict chunk parser, requires exactly one `gbAs`, and rejects bad
CRC, truncated chunks, trailing container bytes, or non-exact compressed state length.

The acceptance builder pins the caller-known Step 2 hashes and fixed paths for audit,
sentinel, guard summary, base/staged ROM, candidate, frame-80 state/PNG and replay Lua,
plus the authenticated Step 1 manifest and x86_64 binary paths. It does not accept a
self-consistent rewrite of those JSON files and hashes. The sentinel must exist at its
fixed path, match the fixed hash, and be byte-semantically identical to the audit. It
also authenticates the tracked
`tools/patches/mgba-0.10.5-qt-script-cli.patch` at its fixed repository path and requires
its actual bytes to equal the manifest's embedded base64 patch payload and hash. It
also requires a positive child PGID, POSIX process-group backend, a finite positive
peak RSS equal to the audit value, strict zero-input fields, task 2 PC/SP, the three
explicit BL frames, the negative controller boundary and `[0x0202680C]`; finally it
performs read-only exact-PGID plus mGBA-listener residue checks. Evidence is written
only if every gate succeeds:

```bash
python3 tools/accept_prebattle_candidate.py
```

The resulting acceptance proves a stable prebattle menu only. In particular it does
not prove `0x0808F952 → 0x080732B4` controller entry, player control, MOVEDONE,
victory, or postbattle. It never kills processes and must not be used to justify Down/A
input unless a later, separately reviewed task explicitly authorizes that input.

The later scenario-41 controller checkpoint is validated through the ordinary ledger
command above, not by a new acceptance tool. Its compact evidence binds the raw
`0x0808F952 → 0x080732B4` gate and two 224-frame zero-input replays. Because the current
ledger schema has no controller-entry hook token, the accepted record keeps
`allowed_evidence=[]`; do not substitute player-control, MOVEDONE, victory or postbattle
hooks. Those remain separate runtime gates.

The compact evidence intentionally preserves absolute `build/` and cache paths from
the local historical run so its origin is unambiguous. Those raw frame-80/cache files
are machine-local and are not repository-distributed artifacts. Git distributes the
tracked candidate and compact evidence JSON; re-running the builder requires the
original local Step 1/2 raw evidence at the pinned paths.

## `mgba_gdb_probe.py`

Windows/macOS mGBA 的只读 GDB 证据探针。它只接受一个 `--breakpoint` 和若干
`--read address:size` 区域。mGBA 0.10.5 的 `--gdb` 固定监听
`127.0.0.1:2345`，因此工具不提供看似可配置但无法传给 mGBA 的 `--port`。
启动前会确认 2345 未被占用；连接后还会确认 owned `Popen` 仍存活，并要求
TCP owner 查询中的 2345 listener owner 集合精确为该 PID。Windows 使用
`GetExtendedTcpTable`；macOS 使用有限超时、无 shell 的 `/usr/sbin/lsof -FpnT`
并只接受完整的 numeric IPv4 `LISTEN`/`ESTABLISHED` 记录；仅 `LISTEN` 本地端点
额外接受 `lsof` 对 bind-any 的 `*:port` 表示，`ESTABLISHED` 两端仍须精确 numeric IPv4。工具随后
读取 client socket 的 local/peer tuple，在 connection 表中反向匹配 server-side
established row，并要求唯一 owner 精确为同一 PID。Windows API 或 `lsof` 错误、无匹配、
多匹配、mixed listener owners 或 owner 查询期间子进程退出都会 fail closed；结果
只能是 `error`/`not-proven`，绝不会成为 `verified`。归属成立后，工具再将
`0x08000000` 与断点处的确定性 ROM 窗口和输入 ROM 比对。只有收到 trap 信号
5，且停止 PC 等于 Thumb 断点地址或该地址加 2 时，输出才会标记为
`verified`。

```powershell
python tools/run_guarded.py `
  --summary build/resource-guard/mgba-strict-smoke.json `
  -- python tools/mgba_gdb_probe.py `
  --mgba C:\path\to\mGBA.exe `
  --rom rom/base.gba `
  --savestate artifacts/runtime-checkpoints/actionable-move-grid.ss9 `
  --breakpoint 0x080732B4 `
  --read 0x02026804:8 `
  --output build/mgba-strict-smoke.json
```

结果 JSON 记录模拟器、ROM、可选 savestate 的路径和 SHA-256，模拟器版本、
实际命令、固定端口、listener/established-connection owner PID、client local/peer
tuple、原始停止包、预期/实际 PC、寄存器、ROM 指纹窗口、读取区域，以及最多
16 KiB 的 stdout/stderr 尾部。每个内存子块必须精确返回请求长度对应的连续
`[0-9A-Fa-f]`；零/负长度、32 位越界、空串、奇数长度、任何 ASCII 空白、其他畸形
hex、短块或长块都会让整个逻辑读取失败，且不会写入该 region 的成功 evidence。
哈希、raw stop 和每个已完成读取会增量保留；进度输出或清理失败
只能附加诊断，不能覆盖主错误。超时为 `not-proven`，不会冒充动态命中；其他
失败为 `error`，两者都保留可操作上下文。

边界：该工具不注入按键、不枚举窗口、不发送 `PostMessage`、不提供 KEYINPUT
写监视点，也不会向 GDB 远端发送 `k`。探针只终止自己创建的 mGBA `Popen`
子进程；完整进程树的所有权与超时清理由外层 `run_guarded.py` 承担：Windows
使用 Job Object，macOS 使用同一 shared heavy lock 下的 owned process group，并受
owned-tree RSS ceiling 约束。不得直接运行原生烟雾，也不得绕过 `run_guarded.py`
或按进程名做宽泛清理。

## `mgba_trace_function_entries.lua`

Experimental script-side execution breakpoint tracer for selected dialogue functions.

Targets through `NARUTO_ENTRY_TARGET`:

- `dialogue_wram_func`
- `dialogue_glyph_func`

Current status:

- useful as a recorded experiment
- not yet as reliable as watchpoint-based tracing on this project

## `mgba-headless-snapshot.py --mode probe`

可复现的 mGBA CLI 执行断点探针。它在同一调试器进程内设置 PC
断点，命中后记录寄存器并读取一个或多个 ROM/WRAM 范围。JSON 中只有出现
`Hit breakpoint ...` 时才会令 `hit=true`；普通 `status` 输出不会被误判为命中。

```bash
python3 tools/mgba-headless-snapshot.py \\
  --rom rom/base.gba --mode probe \\
  --breakpoint 0x08068FF0 \\
  --read 0x0853D910:32 --read 0x02024290:64 \\
  --frames 0 --timeout 300 \\
  --output notes/map-position-probe.json
```

边界：CLI 调试器不能注入按键。冷启动若无法自然到达该 PC，会等待超时；
此时应通过可复现的 Lua 导航或有效战斗 savestate 先建立可达状态，不能把
静态 ROM 读取本身当作 map loader 的动态命中证据。

## `inspect_wram_region.py`

Renders a region inside a WRAM dump as bytes, ASCII-like view, and halfwords.

Example:

```bash
python3 tools/inspect_wram_region.py \
  notes/dialogue-2160-wram.bin \
  0x2880 \
  0x140 \
  --output notes/region-02002880-2160.txt
```

## `compare_wram_regions.py`

Shows byte-level differences for a selected region between two WRAM dumps.

Example:

```bash
python3 tools/compare_wram_regions.py \
  notes/dialogue-2160-wram.bin \
  notes/dialogue-2700-wram.bin \
  0x2880 \
  0x140 \
  --output notes/diff-02002880-2160-2700.txt
```

## `import_dialogue.py`

Imports dialogue content from `sequel/content/dialogue/*.json` into the ROM at runtime, replacing dialogue ID entries with strings from the JSON file. Reads current dialogue entries from the running ROM and updates them in-place.

Example:

```bash
python3 tools/import_dialogue.py
```

## `import_map.py`

Imports map scene data from a JSON map definition file into the ROM build. Expects a JSON file with map tile data, dimensions, and scene metadata.

Example:

```bash
python3 tools/import_map.py sequel/content/maps/episode-01-mountain-pass.json
```

## `import_battle_config.py`

Imports battle configuration data (enemy lineups, stage parameters, wave definitions) from the `sequel/content/battles/` directory into the ROM build.

Example:

```bash
python3 tools/import_battle_config.py
```

## `build_mod.py`

Main ROM build entrypoint. Applies all patches and content imports (dialogue, maps, battle configs) to produce `build/naruto-sequel-dev.gba`. Also handles base ROM detection and patch application.

Example:

```bash
python3 tools/build_mod.py
```

## `automated_test.py`

Runs automated headless tests against the built ROM using mGBA. Verifies that dialogue, map, and battle imports are correctly reflected in the emulated game state. Outputs test results to `notes/test-results/`.

Example:

```bash
python3 tools/automated_test.py
```

## Battle content and controller evidence extractors

`extract_battle_content_catalog.py` joins the 63 unit definitions, 87 character
actions, 45 passive/training entries and 94 ninja-tool entries without treating the
legacy `skills` path as character skills. The checked action-name overlay is optional
at the Python API boundary and enabled by default in the CLI. The CLI also loads the
63-entry unit-name overlay. Every action or unit transcription is rejected if its
stored raw name bytes differ from the ROM; ambiguous visual readings remain explicitly
marked and are not promoted to canonical UI copy.

```bash
python3 tools/extract_battle_content_catalog.py rom/base.gba \
  --output notes/battle-content-catalog-20260723.json
```

`extract_battle_controller_states.py` fingerprints the original controller and its
dispatcher, then emits all 36 state values and entry addresses. Unknown semantics stay
`unresolved`; the generated inventory is evidence for later architecture work, not a
call to reproduce the original implementation byte-for-byte.

```bash
python3 tools/extract_battle_controller_states.py rom/base.gba \
  --output notes/battle-controller-states-20260723.json
```

`analyze_battle_controller_checkpoints.py` binds hash-checked mGBA checkpoint previews
to the containing original controller state. It validates the cooperative task stack,
the Thumb BL that entered the nested controller, and the outer call to `0x080732B4`;
filenames alone are never accepted as state evidence.

```bash
python3 tools/analyze_battle_controller_checkpoints.py
```

The generated `notes/battle-controller-checkpoint-bindings-20260723.json` records 18
boundaries: 14 scenario 41 player/presentation checkpoints plus four scenario 45/50
enemy planning/resolution checkpoints. The latter validate side, current-unit pointer,
character, affiliation, and action-state fields. They show that player state `0x6000`
and enemy state `0x7000` both converge on shared resolution state `0x8000`. Several
visible subphases still share one top-level state, so this manifest must not be treated
as a one-state/one-screenshot rendering table.

`analyze_battle_unit_selection.py` binds four consecutive single-L replays and one
single-R replay in a multi-unit scenario. It verifies that all checkpoints remain in player-selection
state `0x2000`, that only the source/destination units' `+0xC1` selection markers move,
and that the acting-unit pointer and battle-control region remain uncommitted.

```bash
python3 tools/analyze_battle_unit_selection.py
```

The generated `notes/battle-unit-selection-bindings-20260723.json` records the sampled
L Naruto-to-cat-to-Sakura-to-Sasuke-to-Naruto wraparound and R Naruto-to-Sasuke transition.
It proves browsing order, not command eligibility.

`analyze_battle_unit_eligibility.py` compares guarded single-A confirmations for an
unspent player unit, an action-complete player unit, and an escort/objective unit. It
verifies that browsing can select all three, while only the unspent commandable unit
enters action-menu state `0x3000` and binds the current-unit pointer.

```bash
python3 tools/analyze_battle_unit_eligibility.py
```

The generated `notes/battle-unit-eligibility-bindings-20260723.json` records that both
rejected confirmations remain in `0x2000` with zero unit-pool, battle-control, and
action-menu diffs. It does not establish every dead, disabled, summoned, affiliation,
or scenario-specific eligibility rule.

`extract_battle_ai_planner.py` hash-gates the original enemy planner, one additive tile
score function, and one bounded grid-candidate function. It inventories direct calls,
proves strict-greater best-candidate replacement, and records the facing, tile-flag,
and RNG terms visible in the closed score function.

```bash
python3 tools/extract_battle_ai_planner.py
```

The generated `notes/battle-ai-planner-static-20260723.json` does not name unresolved
helpers or claim target, damage, survival, or mission-objective weights. Those require
runtime candidate/score captures.

`analyze_battle_ai_status_policy.py` hash-binds the larger original event scorer and
its 15 direct status queries.

```bash
python3 tools/analyze_battle_ai_status_policy.py
```

The generated `notes/battle-ai-status-policy-bindings-20260723.json` records two target
status-group suppression policies, five same-family event/status policies, and two
actor event/status score penalties. It closes status-aware event contribution rules,
not visible status names or complete target, damage, survival, and mission priorities.

`analyze_battle_ai_utility_policy.py` hash-binds the seven-selector target index, the
complete event utility scorer, and all eight `0xA8` AI configuration records.

```bash
python3 tools/analyze_battle_ai_utility_policy.py
```

The generated `notes/battle-ai-utility-policy-bindings-20260723.json` records separate
same- and opposite-affiliation banks with seven target selectors, strict first-unit
ties, hostile and friendly selector weights, per-target multi-hit damage aggregation,
damage/success/coverage/range weights, four typed scenario-rule slots, active kinds
1–5, both candidate/baseline unit pools, all 34 common weight fields, the mutually
exclusive HP/chakra projection formula, outer candidate kinds 1–4, selected descriptor
kind/effect classification, target-bank gates, selector de-duplication, aggregate
damage component count, actor penalty placement, custom-rule numerator/denominator
placement (kind 1 adds two components; kinds 2–5 add one), and the final 0–9 RNG term.
The same manifest now hash-binds `0x08083AF4`, all 47×8 topology-distance records,
the map 23/24 signed lookup tables, and record kinds 0–6. This is an AI map-topology
distance model, while `grid_pathfinder` remains the movement path implementation.
Rule display names stay neutral. The event `0x11`
resource/threat penalty and the first-event
effect-low-6==7 safe-position bonus are bound to the shared candidate threat field;
the target and scoring policy no longer depend on screenshots or an uninitialized
character role.

`analyze_battle_action_template_semantics.py` hash-binds both action initializers, the
target-policy validator, event builder, scalar-resource gate, all 87 active-action rows,
all 94 ninja-tool rows, and the complete 63-entry effect resolver jump table.

```bash
python3 -m tools.analyze_battle_action_template_semantics
```

The generated `notes/battle-action-template-semantics-bindings-20260723.json` decodes
cost kind, display/animation family, effect code/flags, target policy/flags, numeric
parameters, scalar cost, and handler address without consulting screenshots or display
names. Ninja tools are normalized to the shared runtime layout with battle-local slot
cost kind 5; their source relationship bytes are never misread as scalar resource cost.
Unknown flag bits and handler display names remain neutral.

`generate_butano_battle_action_content.py` converts the two validated JSON banks into
fixed-capacity C++ arrays containing all 87 active actions and 94 ninja tools. Ninja-tool
definitions use a caller-bound battle-local equipment slot and never consume relationship
tail bytes as scalar cost.

```bash
python3 tools/generate_butano_battle_action_content.py --root .
```

`generate_butano_battle_unit_content.py` converts all 63 character definitions, including
the proven base stats, 15 primary action slots, and 24 secondary slots, into the Butano
`UnitDefinition` table.

```bash
python3 tools/generate_butano_battle_unit_content.py --root .
```

Both generated headers are host-compiled by the game-domain tests. Scenario 41 now loads
characters 1 and 30 and active action 5 from these tables; presentation assets no longer
provide combat results.

`generate_butano_battle_scenario_content.py` converts the 47 validated map records and
47×3×12 formation records into `generated_battle_scenario_content.h`.

```bash
python3 tools/generate_butano_battle_scenario_content.py --root .
```

The generator preserves fixed character selectors and the unresolved `0xFA..0xFF`
deployment selectors as different types. 部署占位符必须由关卡策略显式绑定；an unresolved
placeholder makes the atomic loader fail without mutating the destination session.
Generated map dimensions and formations do not by themselves provide chapter scripts,
initial battlefield objects, dynamic deployment UI, or result presentation.

The formation bank is version 3 and also preserves each `0xB8` record's embedded runtime
configuration: level at `+0x0F`, 15 four-byte primary slots at `+0x10`, 24 four-byte
secondary slots at `+0x4C`, and 9 ninja-tool bytes at `+0xAC`. Regenerate and compare both
artifacts with:

```bash
python3 tools/extract_positions.py rom/base.gba \
  --bank /tmp/positions-bank.json
cmp /tmp/positions-bank.json sequel/content/positions/bank.json
python3 tools/generate_butano_battle_scenario_content.py \
  --root . --output /tmp/generated-battle-scenario-content.h
cmp /tmp/generated-battle-scenario-content.h \
  butano-sequel/game/include/konoha/generated_battle_scenario_content.h
```

The loader's ownership order is progression, explicit scenario policy, formation-owned
fixed/scripted configuration, then character template. Ordinary player records and
deployment placeholders must not treat zero-filled embedded slots as an instruction to
erase the roster. The shared player/defense/AI catalog capacity is 24 (15 active actions
and 9 tools). Static evidence, the corrected battle-10 LV20 example, and the guarded ARM/mGBA
acceptance are in `notes/battle-formation-runtime-config-20260726.md`.

`analyze_battle_map_collision.py` hash-gates the original map collision consumer and
the unit occupancy set/clear routines, then inventories all 47 decompressed collision
streams.

```bash
python3 tools/analyze_battle_map_collision.py \
  rom/base.gba --output notes/battle-map-collision-semantics-20260724.json
```

The evidence keeps the complete u16 word. `0xF` is the statically proven fully closed
value; partial low-nibble values remain raw attributes until their original recursive
movement behavior is closed by differential runtime probes.

`generate_butano_battle_map_content.py` converts those same 47 ROM streams into one
fixed-capacity C++ bank containing 12,151 cells plus offset/count definitions.

```bash
python3 tools/generate_butano_battle_map_content.py --root .
```

`battle_map_loader` materializes one definition and overlays active `BattleSession`
units atomically. Scenario code must not recreate terrain or occupancy lists.

`analyze_battle_action_transactions.py` compares hash-bound before/after savestates
across scenario 45 and 50. It verifies that sampled cancel paths preserve the complete
battle unit pool, ninja-tool inventory, and battle-control region, and that the bound
teleport sample commits chakra, position, and action flags together only while crossing
controller resolution `0x8000` into facing selection `0x9000`.

```bash
python3 tools/analyze_battle_action_transactions.py
```

The generated `notes/battle-action-transaction-bindings-20260723.json` is evidence for
transaction timing in four specific samples. It is not proof that every ability,
ninja-tool, passive, linked action, or failure branch shares identical cost behavior.

`analyze_battle_resource_transactions.py` binds a battle 15 chakra exchange, a battle
13 rest command, and a battle 13 ninja-tool commit to controller states and acting-unit
HP/chakra/action fields.
It verifies that the chakra sample exchanges HP for current chakra and that the rest
sample heals, preserves chakra/inventory, and completes the unit action. The tool sample
clears the acting unit's first battle-local equipped-tool slot while leaving HP, chakra,
and the persistent inventory region unchanged.

```bash
python3 tools/analyze_battle_resource_transactions.py
```

The generated `notes/battle-resource-transaction-bindings-20260723.json` records sample
deltas, not a general recovery formula or a complete equipped-tool slot layout.

`analyze_battle_resource_command_rules.py` advances that earlier sample boundary by
cross-binding the ROM controller ranges, the transaction manifest, and two character
checkpoints. It verifies that one chakra point costs the acting unit's `hand_seals`
field while preserving at least one HP, and that base rest recovery is
`floor(max_hp / 5)`.

```bash
python3 tools/analyze_battle_resource_command_rules.py \
  --rom rom/base.gba \
  --transactions notes/battle-resource-transaction-bindings-20260723.json \
  --checkpoints artifacts/runtime-checkpoints \
  --output notes/battle-resource-command-rule-bindings-20260724.json
```

The generated rule manifest closes only the unmodified base command formula and
preview/commit boundary. Passive, status, scripted-scenario, and presentation policies
remain separate.

`analyze_battle_effect_resolution.py` compares one normal damage chain with one
substitution-reaction chain. Both are hash-bound across target confirmation `0x4100`,
shared resolution `0x8000`, and facing `0x9000`.

```bash
python3 tools/analyze_battle_effect_resolution.py
```

The generated `notes/battle-effect-resolution-bindings-20260723.json` proves that the
sampled preview/confirmation does not directly change HP, chakra cost, or action-complete
state. Normal resolution applies damage without displacement; substitution commits the
actor cost/action while preserving target HP and moving the target. In the substitution
sample, target `unit+0x154` changes `0 -> 22 -> 0`: the reaction is staged at shared
resolution entry and cleared when the domain result is committed. It does not establish
the general damage formula, hit RNG, multi-hit, defense/counter, linked-attack, status, or
substitution-destination ordering.

`analyze_battle_reaction_matrix.py` cross-checks every retained battle-15 attack audit
that has a validated `0x8000 -> 0x9000` boundary. Each audit, input state, and output
state is SHA-256 gated before target HP, position, and `unit+0x154` are compared.

```bash
python3 tools/analyze_battle_reaction_matrix.py
```

The generated `notes/battle-reaction-matrix-bindings-20260723.json` contains 29 samples:
18 damage outcomes enter resolution with code 0, while 11 substitution outcomes enter
with code 22 and clear it when displacement is committed without HP loss. This is a
sampled discriminator, not a global reaction enum or proof of trigger/priority rules.

`analyze_battle_defense_preparation.py` binds a guarded Up/A/A chain from defense prompt
state `0x9100` into shared action-list state `0x9200`, then to the visible category
rejection of an offensive action.

```bash
python3 tools/analyze_battle_defense_preparation.py
```

The generated `notes/battle-defense-preparation-bindings-20260723.json` verifies that all
three UI transitions preserve the complete unit pool and battle-control region while the
actor pointer/action flags remain stable. The screenshot-hash-bound Fire Style rejection
shows that list browsing does not imply defense eligibility.

`analyze_battle_defense_reaction.py` binds a controlled original-ROM Sharingan route. It
verifies that the setup changes only Sasuke's current chakra and the existing locked
action-15 level, then separates preview, commit, reaction consumption, and the cut-in.

```bash
python3 tools/analyze_battle_defense_reaction.py
```

The generated `notes/battle-defense-reaction-bindings-20260723.json` records chakra
`5 -> 3`, prepared code `unit+0xD4: 0 -> 16 -> 0`, action ID 15 metadata, an adjacent
enemy attack at shared state `0x8000`, the screenshot-hash-bound Sharingan cut-in, and
unchanged Sasuke HP/position. This is one sampled one-shot evasion reaction; it does not
establish counter, multi-hit, expiry, every defense action, or ninja-tool priority rules.

`analyze_battle_damage_hit_formula.py` validates the event-builder arithmetic, the
ordinary per-hit RNG gate, the queue's shared effective-hit gate before any effect
handler, and the effect-`0x3F` handler, then recomputes the queued values in a natural
three-hit ninja-tool checkpoint.

```bash
python3 tools/analyze_battle_damage_hit_formula.py
```

The generated `notes/battle-damage-hit-bindings-20260723.json` records the four damage
candidates (normal/critical crossed with defended/ignore-defense), the square-root defense
factor, agility-adjusted success rate, and one RNG comparison per hit. In the bound sample,
visible power `6x3` queues candidates `[9, 13, 11, 16]`; the 18 HP result uniquely means
two normal defended hits and one miss, so UI power times hit count is not final damage.
The same queue gate proves that opponent status/reaction effects with zero effective hits
must skip their handler; the Butano correction and its conservative boundary are recorded
in `notes/battle-nondamage-effect-accuracy-20260726.md`.

`analyze_battle_hit_modifiers.py` validates the conditional per-hit critical and
ignore-defense passive queries, RNG ordering, and flag encoding, then binds two
single-byte controlled original-ROM runs.

```bash
python3 tools/analyze_battle_hit_modifiers.py
```

The generated `notes/battle-hit-modifier-bindings-20260723.json` records critical
type `0x0C` as `min(100, passive_value + 10)` with flag 2, and ignore-defense type
`0x19` as `passive_value` with flag mask 4. The 100-percent controls resolve three
critical defended hits for 39 damage and three normal ignore-defense hits for 33 damage,
exactly selecting the queued candidates rather than applying a post-resolution bonus.

`analyze_battle_reaction_priority.py` binds the original-ROM reaction preprocessor to a
natural three-hit ninja-tool baseline, the Sharingan attack queue, and a controlled Fire
Bomb counter route.

```bash
python3 tools/analyze_battle_reaction_priority.py
```

The generated `notes/battle-reaction-priority-bindings-20260723.json` verifies blocker
and reaction lookup order, the non-zero-hit gate, Sharingan's first-effective-hit
replacement/truncation, and Fire Bomb action `0xAE` with reaction code `0x19`. The Fire
Bomb runtime sample consumes the prepared token, keeps Sasuke at 134 HP, reduces the
original attacker from 17 to 3 HP through the shared reverse-source/target resolver, and
then clears event reaction metadata. Other reaction families and expiry behavior remain
outside the verified boundary.

`analyze_battle_status_expiry.py` binds the original-ROM state `0x1100` side-end call
order to two controlled duration samples from the same checkpoint.

```bash
python3 tools/analyze_battle_status_expiry.py
```

The generated `notes/battle-status-expiry-bindings-20260723.json` verifies that
`0x0806C308` visits unit slots 1 through 12 and 16 status slots per valid unit before the
side bit toggles. A duration of 1 decrements to zero and removes the status; a duration
of 2 decrements to 1 and preserves it. This generic side-end duration tick is distinct
from resolver-time one-shot reaction consumption and does not prove status-specific
periodic effects or modifiers.

`analyze_battle_status_storage.py` hash-binds the status lookup, removal, and upsert
routines and the two contiguous per-unit 16×8 record banks.

```bash
python3 tools/analyze_battle_status_storage.py
```

The generated `notes/battle-status-storage-bindings-20260723.json` separates active
status state at unit offset `0xD4` from removed-status events at `0x154`. Expiry-mode
removal copies the full record into the first free removed-event slot when available,
then clears the active code even if that event bank is full; direct one-shot consumption
clears the active code without that copy.
It also binds low-six-bit lookup, ordinary replacement, special code `0x3F` duration
replacement, and the stored duration encoding. Raw parameter meanings and status-code-
specific gameplay effects remain outside the verified boundary.

`analyze_battle_status_consumers.py` scans all decoded Thumb direct branches to the
status lookup/upsert API and hash-binds the ordered reference-address inventories.

```bash
python3 tools/analyze_battle_status_consumers.py
```

The generated `notes/battle-status-consumer-bindings-20260723.json` records 96 direct
lookup references, 21 direct upsert references, and 95 immediate-code lookups covering
25 distinct status codes. The already-bound blocker and reaction families account for
only 12 codes; 13 remain unclassified. This is a reference inventory, not proof of each
code's gameplay semantics or of the absence of indirect/function-pointer consumers.

`analyze_battle_status_linked_resolution.py` hash-binds status code `0x0E` inside the
shared resolver and validates both the status lookup and recursive resolver calls.

```bash
python3 tools/analyze_battle_status_linked_resolution.py
```

The generated `notes/battle-status-linked-resolution-bindings-20260723.json` proves
that record byte `+4` supplies a linked unit slot. The resolver processes that unit with
the same source, action type, and amount plus recursion-guard extras `[0,0,0,1]`, then
continues the primary target's HP branch. This closes ordered propagation rather than
redirection; it intentionally does not assign status `0x0E` a visible gameplay name.

`analyze_battle_status_participant_consumption.py` hash-binds status code `0x0D` in the
resolver queue.

```bash
python3 tools/analyze_battle_status_participant_consumption.py
```

The generated `notes/battle-status-participant-consumption-bindings-20260723.json`
proves that non-reaction events directly consume status `0x0D` from source and target
with removal mode 0. Target consumption additionally clears raw unit-state bit `0x100`.
Known reaction event codes skip this block. The visible status name and meaning of that
raw bit remain unresolved.

`analyze_battle_status_hit_count_modifier.py` hash-binds the damage-event builder and
resolver-queue lifecycle for status `0x13`.

```bash
python3 tools/analyze_battle_status_hit_count_modifier.py
```

The generated `notes/battle-status-hit-count-modifier-bindings-20260723.json` proves
that effect type `0x14` adds the low byte of status-record field `+6` to the queued hit
count, then removes the source status with mode 1 after shared resolution. The original
builder has no not-found guard; new content must validate the required status path
instead of reproducing an out-of-bounds read.

`analyze_battle_status_stage_policy.py` hash-binds every remaining direct status
`0x13` query in the action-list and defense-detail paths.

```bash
python3 tools/analyze_battle_status_stage_policy.py
```

The generated `notes/battle-status-stage-policy-bindings-20260723.json` maps action
IDs 43-49 to the five checked Eight Gates opening names plus Front/Reverse Lotus and
records their exact stage predicates and disabled reason codes. It also proves that
effect type `0x14` renders the same stored u16 stage through the shared numeric writer.
Actions 43-47 produce replacement stages 1-5 through effect type `0x13` and the shared
status upsert path. The visible status label and reason-code text remain unresolved.

`analyze_battle_status_transformation.py` binds action 4, status `0x05`, both identity
helpers, the target-eligibility consumer, cleanup event `0x0B`, and the side-end
removed-event path.

```bash
python3 tools/analyze_battle_status_transformation.py
```

The generated `notes/battle-status-transformation-bindings-20260723.json` proves that
变化术 copies only the target character ID into the source unit, stores the linked
target slot in the status record, and restores the original identity on both cleanup
and ordinary duration expiry. The latter path copies the complete record into the
removed-event bank before dispatching status `0x05`. This closes the status-specific
lifecycle and reduces the original non-blocker/reaction inventory to remaining 9;
the visible status label remains unresolved.

`analyze_battle_status_attribute_modifiers.py` binds the ordered stat reducer,
producer templates, compound effect `0x26`, and side-end recomputation order.

```bash
python3 tools/analyze_battle_status_attribute_modifiers.py
```

The generated `notes/battle-status-attribute-modifier-bindings-20260723.json` proves
that statuses `0x12`, `0x1B`, and `0x1E..0x25` rebuild attack, defense, agility,
movement, and maximum HP from the original character identity in active-slot order.
It records percentage versus absolute operations, caps/floors, all active-action and
ninja-tool producer IDs, the four records created by effect `0x26`, and the
tick-to-removed-event-to-recompute side-end sequence. This leaves remaining 0 operational codes
in the original 13-code non-blocker/reaction inventory; visible labels and other
indirect status families remain separate evidence gaps.

`analyze_battle_objective_transitions.py` binds one battle 44 composite victory and one
battle 15 escort failure to controller states, result byte `0x02026807`, and the
relevant unit records. It proves the sampled position/facing goal and outcome interrupt
without treating screenshot filenames as state evidence.

```bash
python3 tools/analyze_battle_objective_transitions.py
```

The generated `notes/battle-objective-transition-bindings-20260723.json` covers these
two runtime outcome boundaries only.

`analyze_battlefield_object_runtime.py` hash-binds the 32-slot battlefield-object table,
effect `0x0C/0x18` creation paths, side-end expiry, grid metadata binding, and the type-2
sequence-7 presentation chain.

```bash
python3 tools/analyze_battlefield_object_runtime.py \
  --rom rom/base.gba \
  --output notes/battlefield-object-runtime-20260726.json
```

`generate_butano_battlefield_object_effect_content.py` follows sequence 7 to resource
group `0x12`, hash-gates the original ROM and decompressed graphics/palette, and emits
the exact seven-frame 32×32 type-2 expiry sprite sheet used by Butano.

```bash
python3 tools/generate_butano_battlefield_object_effect_content.py \
  --root . \
  --output-dir butano-sequel/graphics \
  --manifest notes/battlefield-object-effect-content-20260726.json
```

`butano/mgba_battlefield_object_type_2_runtime.lua` is the guarded Butano acceptance
route. It selects ninja tool 37 from the real action catalog, observes the domain object
before and across side boundaries, and only writes its success marker while the freed
slot's kind-2 actorless presentation event is active. The run must supply the telemetry
symbol address resolved from the exact ELF through `MGBA_OBJECT_TELEMETRY_ADDRESS`.

`analyze_battle_action_combinations.py` binds the original-ROM ordered
two-component action builder, its five replacement recipes, the unmatched
two-event fallback, and the enemy planner's optional/forced follow policies.

```bash
python3 tools/analyze_battle_action_combinations.py \
  --rom rom/base.gba \
  --output notes/battle-action-combination-bindings-20260725.json
```

The analyzer verifies the full ROM SHA-256, the table at `0x0853DFB0`, its literal
at `0x08075C0C`, the exact count-two gate, encoded ninja-tool range `0x81..0x91`,
matched output count one, and the generic branch that preserves the original
component count and initializes both events. It also hash-binds the planner,
candidate enumerator, and shared component enumerator; verifies the
`0x1800` combination flag mask, optional IDs 12/16 under `0x0800`, forced IDs
9/14/25/29 under `0x1000`, the single-candidate return versus forced loop,
and the action/tool follow-up catalog calls. Menu prompt text and the original
planner's final per-candidate integer weights remain separate evidence; see
`notes/battle-action-combination-player-flow-20260725.md`.

`analyze_battle_condition_interpreter.py` binds the original-ROM condition interpreter,
its nine-way dispatch table, and all 47 battles × 3 fixed condition variants through the
next referenced data table at `0x08596CCC`.

```bash
python3 tools/analyze_battle_condition_interpreter.py
```

The generated `notes/battle-condition-interpreter-bindings-20260723.json` distinguishes
the handlers supported by code (types 1 through 9) from those referenced by the record
bank (types 1, 2, 3, 6, 7, 8, and 9). It preserves four ordered win and four ordered loss
predicate slots per variant and binds the first-match arbitration, including result 5
for equal winning and losing slot indices. It also binds every record-used handler's
operation: unit/character absence, round limit, indexed battlefield-object-slot inactivity,
and at-limit HP sum, valid-unit-count, or behavior-9 resolved-object counter comparison.
It also hash-binds the 32-slot object allocator/free routines and the writer that frees a
behavior-9 object and increments `0x02026BC0 + side` from the resolving unit's affiliation.
Visible gameplay names for object behaviors plus unused handlers 4/5 remain outside the verified boundary. The
hash-bound caller maps condition results 1/2/5 to presentation
IDs 1/2/3 respectively and ends the battle for result 5; the visible label of presentation
ID 3 is intentionally not inferred from code alone.

`butano/mgba_scenario_43_runtime.lua`,
`butano/mgba_battle_09_multi_unit.lua`, and
`butano/mgba_battle_09_character_actions.lua` are the guarded acceptance routes for the
data-configured visible battle scene. They read the exported controller telemetry instead
of treating elapsed frames or screenshot filenames as completion evidence. Scenario 43
requires the clone to make five active units, three enemy actions, round 2 and
`presentation_busy == 0`; row 9 requires eight active units, all three player actions,
five enemy actions, round 2 and the same presentation boundary. The character-action route
additionally requires Naruto action 2 to resolve as teleport, Sakura action 1 to activate a
reserve clone, Sasuke actions 2/5/16 to be browsable, nine active units, and round 2. It
records `last_resolved_action_id` rather than accepting a menu screenshot as execution evidence.

With `MGBA_B09_ACTION_EXECUTE_SASUKE_ACTION_05=1`, the character-action route extends the
same controller session through round 3 instead of teleporting to an effect screen. Sasuke
moves to `(7,14)`, then `(7,11)`, finishes the intervening units and enemy phase, moves to
`(7,10)`, selects action 5 from the real catalog, and accepts only an adjacent active enemy.
Completion requires the action-5 impact resource, five representative impact captures,
three dust captures, the actor's target-side reentry frame, map restoration, active-unit
change `9→8`, zero controller/player errors, and an empty screenshot queue. The reentry
capture is sampled one callback after choreography step 60 because mGBA's frame callback
observes telemetry before the newly rendered frame is presented.

`analyze_original_effect_sequence.py` and
`butano/generate_battle_effect_sequence.py` form the non-screenshot asset path for original
OBJ effects. The analyzer consumes an original-ROM GPU trace plus per-frame OAM dumps,
filters by OBJ tile base/palette bank, decodes shape/size/flip/priority, and verifies every
frame's VRAM/PRAM bytes against the hash-bound ROM LZ77 resources. Use `--tiles-address`
and `--palette-address` for the exact resource pair; the trace script accepts
`MGBA_ACTION_PRESENTATION_GPU_CAPTURE_START/END` to capture the required original-frame
range and rejects an inverted range.

The generator decodes the referenced 4bpp tiles and palette directly from the ROM,
deduplicates component assets, compacts consecutive identical component configurations
into keyframes with explicit hold durations, and emits a fixed-capacity
`battle_effect_sequence`, Butano sprite items, BMP/JSON source assets, and an evidence
manifest. `--preset action-05-hit` generates original frames 148–163 as 11 keyframes,
14 unique assets and at most 8 components; `--preset action-05-dust` generates original
frames 77–135 as 26 keyframes, 8 unique assets and at most 3 components. Their durations
remain 16 and 59 frames respectively. `--preset action-16-fire-hit` generates original
frames 487–516 as 12 keyframes, 10 unique assets and at most 4 components, preserving the
30-frame duration.

`butano/generate_battle_action_16_movie.py` is the corresponding non-screenshot path for
action 16's cut-in and multi-layer movie. It consumes the hash-bound original ROM plus GPU
dumps, emits separate portrait/dialogue/actor/fire/streak BG assets and three title OBJ
assets, and preserves the per-frame palette, blend and scroll timeline. It validates the
original frame-300 spatial fade contract (`WIN0H=0x00F0`, `WIN0V=0x2070`,
`WINOUT=0x3F1F`, `BLDCNT=0x00B7`, `BLDY=0x0006`) before generating runtime content.
Neither generator accepts a composed gameplay screenshot as production input.

With `MGBA_B09_ACTION_EXECUTE_SASUKE_FIRE=1`,
`butano/mgba_battle_09_character_actions.lua` executes action 16 from the real battle-9
catalog/resolver route and captures cut-in title, cut-in fade, movie, impact and map
restoration boundaries. The route is muted and therefore signs presentation/control flow,
not audio quality.

The telemetry address is not a stable ABI. Resolve it from the exact ELF with
`arm-none-eabi-nm` after every build, then pass it through
`MGBA_S43_TELEMETRY_ADDRESS`, `MGBA_B09_TELEMETRY_ADDRESS`, or
`MGBA_B09_ACTION_TELEMETRY_ADDRESS`:

```bash
source tools/butano/toolchain.lock
docker run --rm --user "$(id -u):$(id -g)" \
  --volume "$PWD:/workspace" --workdir /workspace/butano-sequel \
  "$DEVKITARM_IMAGE" /opt/devkitpro/devkitARM/bin/arm-none-eabi-nm \
  -n butano-sequel.elf | grep konoha_battle_runtime_telemetry
```

The AI-resource acceptance build reports `0x02014FB8`; this address is build-specific,
so resolve the symbol again before every future run. All scripts record state
transitions plus PC/LR/SP/KEYINPUT,
save a final state and only create the success marker after the screenshot queue is empty.
They run muted and therefore do not validate audio quality.

The forced-AI-combination build is a concrete example of why the address must be resolved:
the previous `0x0201A3E0` address produced an idle timeout with empty telemetry files, while
the exact ELF resolved `0x0201A684` and completed battle 9 at frame 2791. The successful
run and its hashes are recorded in
`artifacts/butano-ai-forced-combination-runtime-20260726-05/manifest.json`. Since no
embedded enemy primary action slot currently contains action 9, this muted route is an
ARM scene/session regression; the forced-combination behavior itself is covered by the
host AI-flow integration test.

After restoring all optional/forced combination flags, the next exact ELF moved the
same symbol again to `0x0201A824`. The muted regression completed battle 9 at frame
2791; its inputs, outputs, and coverage boundary are recorded in
`artifacts/butano-ai-combination-policy-runtime-20260726-06/manifest.json`.

The telemetry block is now 336 bytes. Its first 112 bytes retain the generic scene/action
offsets, followed by result and structured presentation-script state through offset 204.
Five resource-presentation words are appended without moving any older field:
`resolved/type/amount/hp_delta/chakra_delta` at offsets `208/212/216/220/224`.
Later passive/object/cursor fields occupy offsets 228–328, and
`selected_action_level` is appended at offset 332 without moving older consumers.
The delta words use signed two's-complement values; Lua routes convert them with
`signed32`. The current AI-resource regression evidence is
`artifacts/butano-ai-resource-runtime-b09-20260725-03/`; it crosses battles 41, 43 and 9
and reaches round 2 with zero controller/player errors. Setting
`MGBA_B09_ACTION_REQUIRE_AI_RESOURCE=1` extends later rounds and only accepts a real
resource presentation. Battle 9 retained higher-scoring usable attacks through round 110
in the 2026-07-25 probe, so that probe is a non-trigger result, not positive resource
evidence.

For ARM-only stalls, `mgba_battle_09_character_actions.lua` also exposes optional
diagnostics:

- `MGBA_B09_ACTION_TRAP_ADDRESS`, `MGBA_B09_ACTION_TRAP_START_FRAME`, and
  `MGBA_B09_ACTION_TRAP_AFTER_HITS` install a delayed execution breakpoint and write
  `execution-trap.jsonl` plus a save-state;
- `MGBA_B09_ACTION_WATCH_ADDRESS`, `MGBA_B09_ACTION_WATCH_START_FRAME`, and
  `MGBA_B09_ACTION_WATCH_AFTER_HITS` install a delayed write-change watchpoint and write
  `memory-write-trap.jsonl` with PC/LR/SP, r0–r3, old/new value and width.

The Maxmod corruption audit must resolve `mp_mix_seg` from the same ELF
(`0x030029E0` in the 2026-07-26 action-progression build). Earlier accepted evidence in
`artifacts/butano-action-workspace-runtime-b09-audio-watch-20260725-27/` contains 20
consecutive writes, all from `PC=0x03000DFC`, width 1, alternating `00/FF`; this verifies
that battle stack writes no longer reach the mixer state in that build. The later
`artifacts/butano-action-progression-runtime-20260726-09/` route also completes player
resource, AI action and defense boundaries through the shared EWRAM transaction workspace
that previously drove SP into Maxmod, but remains muted and does not validate perceived
audio quality.

`analyze_battle_action_progression.py` hash-binds the original four-byte character
action slots to unlock, training, battle-catalog and numeric-growth semantics:

```bash
python3 tools/analyze_battle_action_progression.py \
  --rom rom/base.gba \
  --output notes/battle-action-progression-20260726.json
python3 -m unittest tests.test_analyze_battle_action_progression
```

The manifest distinguishes `0xFF` locked, `0` unlocked/unlearned and `1..254`
battle-usable states, records the six growth targets, and lists resolver-capable actions
that were previously unreachable because every primary slot initialized them to zero.

Character **level** growth is a separate runtime chain from action-rank growth. The
63×`0x10` table extracted from file `0x545068` is applied by the common scenario loader
to player progression, enemy policy levels, scripted units, and deployment placeholders.
The 2026-07-26 integration and ARM regression evidence is
`notes/battle-level-stat-runtime-20260726.md` and
`artifacts/butano-level-stats-runtime-20260726-01/`. Its telemetry symbol is
`0x020195EC` for that exact ELF only; resolve it again after every build.
The durable interpretation and ARM acceptance boundary are documented in
`notes/battle-action-progression-20260726.md`.

`analyze_battle_passive_query.py` binds the original 24-slot passive lookup and the
45×12-byte growth table, then writes
`notes/battle-passive-query-bindings-20260725.json`:

```bash
python3 tools/analyze_battle_passive_query.py
python3 tools/generate_butano_battle_passive_content.py
```

The generator emits `generated_battle_passive_content.h`; only passive target types with
separate consumer evidence may affect battle rules. `analyze_battle_passive_consumers.py`
scans every direct Thumb call to the query and hash-binds the proven formulas:

```bash
python3 tools/analyze_battle_passive_consumers.py --rom rom/base.gba \
  --output notes/battle-passive-consumer-bindings-20260725.json
```

Early consumers included `0x0C` critical, `0x14` HP-restoration bonus, `0x15` carried
battle experience percentage, and `0x19` ignore-defense. The inventory also hash-binds
the later-closed side-start, event-gate, and terrain traversal groups; it does not assign
meanings to call groups whose data flow remains unresolved. Other records remain queryable
content, not guessed effects.

`analyze_battle_passive_coverage.py` joins those two ROM manifests with the 45 catalog
rows and current Butano consumers:

```bash
python3 tools/analyze_battle_passive_coverage.py --root . \
  --output notes/battle-passive-coverage-20260726.json
```

The matrix currently proves 17 rows with direct ROM consumers and 28 without one.
Butano implements all 17 directly consumed gameplay rows. Passive IDs 21–23 / targets
`0x1A–0x1C` supply path-local traversal budgets for terrain classes `1/7/3`; they are not
visual configuration or directional collision bits. The correction, ROM hashes, path
semantics and mGBA evidence are recorded in
`notes/battle-terrain-passive-runtime-20260726.md`.

The generated battle tables are bound by
`butano-sequel/game/include/konoha/battle_content_catalog.h`. Its generic validator is
covered by `butano-sequel/game/tests/test_battle_content_catalog.cpp`, including injected
cross-table corruption. The production catalog is also checked at compile time and by
foundation self-test bit 5. Runtime scenes query one `battle_content_entry` for scenario,
map, and conditions; they must not index these generated tables independently. The
contract validates all 47 battles and 141 variants, but does not claim that every entry
already has a deployment UI or chapter script. Visual backgrounds are provided separately
by the generated background catalog described below.

`battle_deployment_flow.h` implements the pre-controller formation confirmation seen in
the original battle routes. It reuses `resolve_battle_scenario_character` from the final
scenario loader, so fixed selectors and `0xFA..0xFF` policy bindings cannot disagree
between preview and load. Generic scene telemetry uses phase `0xFFFFFFFE` for a unit
confirmation and `0xFFFFFFFD` for START. The mGBA row-9 and scenario-43 scripts advance
these states one A edge at a time and capture `deployment-unit-1.png` plus
`deployment-start.png`. Production waits for A/B release and one neutral frame before
starting the battle controller; acceptance scripts must likewise leave released frames
between confirmations.

`battle_runtime_scene_request` is the chapter-to-battle boundary for visible encounters.
It carries the battle/variant identity and one `battle_scenario_load_policy`; the same
policy is used by deployment preview and final controller loading. A
`deployment_required` entry is accepted only when every placeholder used by that variant
is explicitly bound. `run_battle_32_deployment_fixture_scene()` and
`butano/mgba_battle_32_dynamic_deployment.lua` are integration fixtures for this contract,
not canonical chapter content. Their accepted muted evidence is
`artifacts/butano-dynamic-deployment-b32-20260725-57/`.

`battle_runtime_grid.h` defines the single 23×32 fixed-capacity logical grid and controller
used by visible battles. `grid_map` stores runtime active dimensions, so map loading,
cursor movement, pathfinding and AI cannot enter padding. The host test
`test_battle_runtime_grid.cpp` materializes all 47 generated maps and loads all 85 nonempty
variants through that one controller. This is a logical-map guarantee only: original maps
wider than the GBA 512px regular-background limit still require ROM-derived chunk streaming.

`butano/mgba_battle_terrain_traversal.lua` verifies the same terrain policy through the
production campaign scene. It boots battle 41, completes deployment, rejects an untrained
move from `(4,10)` to the adjacent class-7 tile `(3,9)`, then confirms that staying at the
origin advances to the command phase. Run it only through `tools/run_guarded.py` and resolve
the current telemetry symbol after every ARM build.

`generate_butano_battle_runtime_assets.py` now provides
`plan_map_chunk_origins()`, `generate_map_chunks()` and `generate_all_map_chunks()`. The
all-map command emits 47 per-map manifests, 49 indexed regular-BG chunks,
`graphics/battle_background_catalog.json`, and
`game/include/konoha/generated_battle_background_content.h`. Each manifest records the full
map size, chunk index/count and world origin and hash-binds the ROM tile graphics, palette,
layout and metatile attributes. Battle 0 emits origins `[0,224]`; battle 11 emits `[0,32]`;
the other 45 maps use one origin-0 chunk.

The visible runtime queries `generated_battle_background_entry(battle_id)` and cross-checks
the returned pixel dimensions against the logical scenario grid before deployment. Scene
wrappers must not name a concrete `bn::regular_bg_items::battle_*` item. Having all 47
backgrounds in the ROM is a visual-content guarantee only; it does not synthesize empty
variants, dynamic deployment choices, object scripts, or chapter transitions.

Empty-tile actions must also pass the ROM map gate. AI planning and player confirmation
reject targets with cost 0, `grid_fully_closed`, or an active occupant. Omitting this check
previously allowed an AI move effect to place a unit inside battle 32's blocked `(12,13)`
cell; the next occupancy rebuild then failed and left the enemy turn retrying forever.

`generate_butano_battle_unit_visual_content.py` decodes the battle OBJ visual table at
ROM file offset `0x596D5C`. The corrected shape is 62 character IDs × 9 visual slots
(558 rows): 342 populated rows and 216 reserved empty rows. Slot zero is the ROM idle
visual for every character. The generator validates the source ROM hash and every pointer,
decodes the first 24-byte frame descriptor and 1D 4bpp OBJ tiles, then writes 62 BMP/JSON
items, `graphics/battle_unit_visual_catalog.json`, and
`game/include/konoha/generated_battle_unit_visual_content.h`:

```bash
python3 tools/generate_butano_battle_unit_visual_content.py
```

The visible runtime queries this catalog by `character_id` for both deployment and battle.
Inactive scenario slots hold no sprite resource; activation by a summon creates the sprite,
deactivation releases it, and an identity override updates the item in place. The accepted
muted runtime evidence is `artifacts/butano-unit-visual-b32-final-20260725-66/`, with fixed
route regressions in the adjacent `butano-unit-visual-regression-*` artifact directories.
The current generator decodes all frames, overlapping OAM chains and duration sequences in
all 342 populated slots. It emits 534 component/shape sprite assets and a fixed-capacity
timeline catalog. Runtime selects field/cast/throw/melee/hit slots, mirrors missing explicit
left-facing slots, and keeps affected unit IDs alive through the presentation transaction.
Accepted muted evidence is `artifacts/butano-shared-s41-runtime-20260725-84/`,
`artifacts/butano-unit-animation-b09-20260725-86/`, and
`artifacts/butano-dynamic-deployment-b32-20260725-87/`.

`butano/mgba_battle_41_shared_runtime.lua` drives the default shared scenario-41 route:
deployment, movement, AI response, action 5, target hit, return and outcome. The historical
264-frame full-screen recording assets live under
`references/scenario-41-attack-animation/` and are intentionally absent from production
`graphics/`.

Lua phase constants are checked against the current C++
`battle_scene_phase` enum by `tests/test_butano_battle_phase_contract.py`; adding or moving
a controller phase must update every affected route. When a route stops before its first
capture, `butano/mgba_s41_telemetry_trace.lua` records the telemetry magic, battle, phase,
round and selected unit every 30 frames while advancing deployment. It is a diagnostic
probe, not acceptance evidence by itself.

The original battle-presentation script bank is rebuilt from ROM data with:

```bash
python3 tools/analyze_battle_presentation_scripts.py rom/base.gba \
  --output sequel/content/battle-presentation-scripts/bank.json
python3 tools/generate_butano_battle_presentation_content.py
python3 tools/generate_butano_battle_portrait_content.py
python3 tools/generate_butano_battle_presentation_glyphs.py
```

The analyzer hash-binds both 47-entry pointer tables, the shared interpreter and all
condition handlers. Generated content contains 1,741 selector instructions, 400 cases,
3,213 commands, 48,104 presentation text bytes and 862 ROM glyphs in fixed-capacity
storage. The controller evaluates round/side, active-character, adjacent-character,
script-flag and secondary-state conditions against the live battle session; scripts block
battle input without owning HP, resources, unit positions or turn state.

The portrait generator follows the original 63×5 resource matrix and embeds the 46
portrait/expression pairs referenced by the script bank. Each 80×80 8bpp portrait is
assembled from the original six OAM components. Two visible slots share a 128-color OBJ
palette, including the original focus-dimming transform; every embedded LZ77 stream is
4-byte aligned for the GBA decompressor. The dialogue window is created at runtime from
4bpp blended sprites. Neither layer uses a full-screen scenario screenshot.

`butano/mgba_battle_41_presentation.lua` and
`butano/mgba_battle_43_presentation.lua` confirm deployment, require each battle's five
exact selector-1 text pages, assert structured window/portrait identity, expression and
focus telemetry, then accept unit selection. The accepted muted evidence is
`artifacts/butano-battle-portrait-runtime-b41-20260725-05/` and
`artifacts/butano-battle-presentation-b43-20260725-03/`; hashes, audit fields and
superseded-run reasons are recorded in
`notes/battle-presentation-script-bindings-20260725.json`. These routes prove the shared
data-driven presentation and continuation path. They do not sign off audio quality,
all original motion interpolation, or all 47 battle routes.

Set `MGBA_S41_SHARED_CONTINUE_RESULTS=1` to continue the same state-driven route through
the generic result and unified action/passive training controller. The script requires phases
outcome/result/level-up/training/complete, validates mission, carried battle EXP, round
bonus, total, before/after level, remaining EXP and HP growth, then selects the real action
8 row and requires `level 0→1` plus `training points 1→0`, then continues to the first
secondary/passive row and verifies its entry-kind telemetry before exiting. Target navigation uses cursor-unit
telemetry and a legal second-round move instead of a fixed screenshot coordinate. Current
muted evidence is `artifacts/butano-training-runtime-20260726-04/`; see
`notes/battle-primary-training-runtime-20260726.md`. The route remains muted and does not
validate audio quality.

When `MGBA_S41_SHARED_CAMPAIGN_TELEMETRY_ADDRESS` is also set to the exact ELF symbol
`konoha_battle_campaign_runtime_telemetry`, the shared route presses A after COMPLETE,
waits for the scene boundary to merge progression into the 63-character campaign, and
requires a verified SRAM write before emitting `campaign-save-complete`. The telemetry
contract includes load/save generation and slot, default/verified flags, Naruto level,
experience, training points, action-8 level, the first three equipped-tool slots, and the
adapter error. The current 72-byte layout places `naruto_tool_0/1/2` at offsets
`44/48/52`, sample owned quantities 67/68 at `56/60`, material 6 at `64`, and
`last_error` at offset `68`; always resolve the telemetry base from the
exact ELF rather than copying an older address.

Set `MGBA_S41_SHARED_CONSUME_TOOL37=1` together with
`MGBA_S41_SHARED_CONTINUE_RESULTS=1` to choose ninja tool 37 from the production action
catalog, complete its battlefield-object lifetime, then continue through result/training
and the verified SRAM save. The route requires Naruto's third equipped slot to become 0
while slots 0/1 remain 67/11.

`butano/mgba_battle_campaign_load.lua` is the separate cold-start verifier. It must run
against the same staged ROM/SAV in a new mGBA process and does not call `addKey` or
`clearKey`; completion requires a non-default generation and the exact saved character
state before any new battle input. Set `MGBA_CAMPAIGN_EXPECTED_TOOL_2=0` when verifying
the consumption route; the cold-load audit records all three tool slots. Both scripts must use an isolated staged path and
`tools/run_guarded.py`; they must never target `rom/base.sav`. Accepted muted evidence is
`artifacts/butano-campaign-persistence-20260726-03/` for the original progression
milestone and `artifacts/butano-campaign-tool-writeback-runtime-20260726-01/` plus
`artifacts/butano-campaign-tool-writeback-load-20260726-01/` for equipped-slot
consumption. They are documented in
`notes/battle-campaign-persistence-runtime-20260726.md` and
`notes/battle-campaign-tool-writeback-runtime-20260726.md`. These routes do not validate
audio quality, full bag quantities, replenishment/equipment UI, or original-save binary
compatibility.

`butano/mgba_battle_preparation_upgrade.lua` drives the live campaign preparation page,
selects the ROM-generated `67→68` recipe, and requires the shared upgrade transaction to
atomically produce equipped slot `68`, owned quantities `67=0/68=1`, material `6=0`, and
a verified generation-1 SRAM write. It then waits for battle-41 deployment telemetry and
15 additional rendered frames before capturing the map/units/cursor, so a black transition
frame cannot be mistaken for a battle black screen. Run
`butano/mgba_battle_campaign_load.lua` in a second process with its explicit
`MGBA_CAMPAIGN_EXPECTED_*` variables to verify version-2 inventory recovery without input.
Accepted muted evidence is
`artifacts/butano-ninja-tool-preparation-runtime-20260726-04/` and
`artifacts/butano-ninja-tool-preparation-load-20260726-03/`.

`butano/mgba_battle_preparation_equipment.lua` verifies the separate manual-allocation
path. Starting from an isolated base SAV, it opens the live unequip page, releases tool
67, equips the independently owned tool 1 into the first empty slot, and requires a
verified SRAM save. It does not stop at the feedback page: it completes battle-41
deployment, opens the production action catalog, and only succeeds when action ID 1 is
reported as `ninja_tool` from tool slot 0. The accepted muted evidence is
`artifacts/butano-ninja-tool-equipment-runtime-20260726-03/`; it uses the final build
that also exposes L/R party switching.

Run `butano/mgba_battle_campaign_load.lua` in a separate process against that staged SAV
with `MGBA_CAMPAIGN_EXPECTED_OWNED_TOOL_1=1` and the other explicit expected values.
`artifacts/butano-ninja-tool-equipment-load-20260726-02/` proves zero-input recovery of
the equipment allocation and owned quantities. The first equipment route
`runtime-20260726-01` stopped at the battle-41 script input gate and is superseded; it is
not acceptance evidence. Both routes are muted and do not validate audio quality.

Battle-result source tables are reproducible with:

```bash
python3 tools/extract_battle_result_content.py rom/base.gba \
  --bank sequel/content/battle-results/bank.json
python3 tools/generate_butano_battle_result_content.py
```

The reward table is 112×24 bytes at file `0x59EAE0`, the 48-byte scenario mapping is at
`0x348DAC`, and the 63×4 experience-threshold table starts at `0x59F560`. Formation
record `+0x0C` is separately extracted as carried battle EXP. See
`notes/battle-result-progression-runtime-20260725.md` for the consumer chain and boundaries.

`butano/mgba_battle_11_background_stream.lua` enters battle 43 → battle 9 → battle 11 through
the shared visible runtime, confirms all deployment records, then drives the battle 11 move
cursor from chunk 0 to chunk 1 and back to chunk 0. Completion requires telemetry chunk
sequence `[0,1,0]`, not just screenshots. The accepted muted evidence is
`artifacts/butano-all-backgrounds-b11-20260725-52/`. The same final ROM also passed battle
9, scenario 43 and scenario 41 routes in `artifacts/butano-all-backgrounds-b09-20260725-53/`,
`artifacts/butano-all-backgrounds-s43-20260725-54/`, and
`artifacts/butano-all-backgrounds-s41-20260725-55/`.

# mGBA savestate context inspection

`inspect_mgba_savestate.py` reads the zlib-compressed `gbAs` chunk embedded in an mGBA
`.ss9` without launching the emulator. It reports serialized CPU registers and the eight
game-specific cooperative task contexts at `0x03000A88`:

```powershell
python tools/inspect_mgba_savestate.py artifacts/runtime-checkpoints/actionable-move-grid.ss9
python tools/inspect_mgba_savestate.py artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9 --output build/task5-context.json
```

The memory reader intentionally supports only EWRAM and IWRAM from the fixed mGBA 0.10.5
state layout. It rejects missing, malformed, unsupported-version, and wrong-sized states.

## Battle continuation-hit passive binding

`analyze_battle_continuation_hits.py` verifies the original continuation gate, category
queries, one-roll-per-action sharing, hit-count increment and its ordering before the
ordinary per-hit generator. It also validates the scenario-41 single-byte 100-percent
control and both fixed single-input replay audits:

```bash
python3 tools/analyze_battle_continuation_hits.py
```

The generated `notes/battle-continuation-hit-bindings-20260725.json` binds current-HP,
current-chakra and ninja-tool actions to passive target types `0x16`, `0x17` and `0x18`.
It proves that success adds one ordinary hit to every queued event sharing an action ID;
the added hit still follows the normal hit/critical/ignore-defense/reaction pipeline.
The evidence deliberately leaves nonzero original event byte `+0x16` unnamed.

## Battle side-start passive binding

`analyze_battle_side_start_passives.py` hash-binds the original side-start
consumer, its only controller callsite, all four passive-query calls, threshold
instructions, status writes and the shared unit `+0xBE` latch:

```bash
python3 tools/analyze_battle_side_start_passives.py \
  --rom rom/base.gba \
  --output notes/battle-side-start-passive-bindings-20260725.json
```

The manifest closes target types `0x1D` through `0x1F`: low-HP HP/chakra
restoration, low-HP heal plus five-turn attack-up, and quarter-HP three-turn
attack-up. It also records the mechanical battle-11 gate and two status writes
for `0x20`, while marking that family `withheld_pending_semantics`; consumers
must not turn that partial evidence into guessed gameplay.

## Battle active-action reachability

`analyze_battle_action_reachability.py` classifies all 87 active-action identities by
their natural data source instead of equating a nonzero resolver definition with a
playable menu entry:

```bash
python3 tools/analyze_battle_action_reachability.py \
  --root . \
  --output notes/battle-action-reachability-20260726.json
```

The analyzer fail-closes on the 63 unit templates, 1,728 formation records, 87 action
definitions and identities, combination recipes, progression state model, resource
command evidence, and the original-ROM function/ranges/literals that prove the special
action-19 unlock. It distinguishes base catalog entries, state-0 training routes,
level-locked routes, scenario-unlock-then-training routes, catalog-accepted formation
overrides, and derived combination results. The output records action 19 as Sasuke's
battle-31 variant-0 unlock followed by normal training, action 62 as a natural battle-8
formation action, action 20 as a separate resource-command identity, and 39/40/52 as
unreferenced zero templates. It does not claim presentation or per-action semantic
completeness.

## WAV integrity and deterministic Butano audio replay

`analyze_wav_integrity.py` analyzes adjacent samples within each channel, so an ordinary
left/right stereo difference is not misclassified as a discontinuity:

```bash
python3 tools/analyze_wav_integrity.py \
  build/butano-battle-audio-runtime-20260727-02/full-route-6500f-verified.wav \
  --output build/butano-battle-audio-runtime-20260727-02/full-route-6500f-verified-analysis.json
```

`butano/mgba_audio_recorder.c` can replay the exact JSONL press/release stream captured by
an mGBA Lua route. Set `MGBA_AUDIO_INPUT_EVENTS` to that log, `MGBA_AUDIO_REPORT` to the
output JSON path, and `MGBA_AUDIO_TELEMETRY_ADDRESS` to the battle telemetry address for
the current ELF. Always compile and run mGBA through `tools/run_guarded.py` with the shared
heavy lock. A cold-start capture proves the preparation cue is reachable; a full replay
proves that music and effects remain active across deployment, commands, presentation, and
map restoration. See `notes/butano-battle-audio-runtime-20260727.md` for the accepted
6500-frame, 518/518-event route and its hashes.
