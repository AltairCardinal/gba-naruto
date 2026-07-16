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
`rom/base.gba` before exiting normally. ROM staging keeps mGBA save-file side effects
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

## Read-only breakpoint frame trace pre-script

`mgba_breakpoint_frame_trace.lua` records the frame and CPU context for each execution
of one caller-selected PC. Set `MGBA_BREAKPOINT_TRACE_TARGET` to exactly `0x` plus eight
hex digits and `MGBA_BREAKPOINT_TRACE_OUTPUT` to the JSONL output path before passing it
as a pre-script. `MGBA_BREAKPOINT_TRACE_MAX_HITS` is optional and defaults to 256.

Each JSONL row contains the hit number, frame, cycle, target, PC, LR, and SP. After the
limit, the script clears only its breakpoint and stops recording; it does not send
input or terminate mGBA, so the fixed replay and guard remain responsible for normal
completion. Missing or invalid configuration and an output path that cannot be opened
fail closed before tracing starts.

## Fixed single-input macOS mGBA replay

`run_macos_mgba_single_input.py` and `mgba_single_input_replay.lua` provide the
separate Task 4.7 input segment. The CLI accepts exactly one `Down`, `A`, or `B` event and
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
并只接受完整的 numeric IPv4 `LISTEN`/`ESTABLISHED` 记录。工具随后
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
