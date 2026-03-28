# Debugging Record

## Emulator Setup

- Homebrew `mGBA 0.10.5` was installed at `/usr/local/bin/mGBA`
- Homebrew binary does not support `--script`
- Upstream source was built locally to enable script CLI support:
  - source: `/Users/altair/github/mgba-src`
  - binary: `/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA`

Confirmed frontend option:

- `--script FILE`

## Runtime Policy

All repeatable runs should use:

- `tools/run_headless_mgba.sh`

This wrapper enforces:

- `QT_QPA_PLATFORM=offscreen`
- `-C mute=1`
- `-C volume=0`

So future automated debug runs are headless and silent by default.

## ROM Patch Validation

Patch experiment:

- target offset: `0x00076D`
- original bytes: `89 DF 95 D1`
- patched bytes: `8E 8E 8C B1`
- copied ROM: `rom/experiment-00076d.gba`

Results:

- byte-level writeback succeeded
- mGBA scripted probe confirmed emulated memory at `0x0800076C` contains:
  - `00 8E 8E 8C B1 81 40 0A`
- title screen screenshots showed the patch does not appear on that route

Conclusion:

- patching pipeline is valid
- that text bank is real
- but `0x00076C` is not used by the title screen path

## Headless Automation

### Boot/menu flow

Scripts:

- `tools/mgba_auto_title.lua`
- `tools/mgba_boot_walk.lua`
- `tools/mgba_long_walk.lua`

Confirmed states reached:

- Bear Team splash
- disclaimer screen
- TOMY splash
- title screen
- title menu
- save-slot screen
- `没有记录存档` popup

### Story flow

Scripts:

- `tools/mgba_newgame_walk.lua`
- `tools/mgba_newgame_snapshot.lua`
- `tools/mgba_dialogue_diff_snapshots.lua`

Confirmed states reached:

- opening dialogue scenes
- stable fixed snapshot at frame `2160`
- four dialogue snapshots with matching `WRAM/IWRAM/VRAM` dumps

## OCR

Native OCR toolchain:

- source: `tools/ocr_screenshot.swift`
- binary: `tools/bin/ocr_screenshot`
- timeline wrapper: `tools/ocr_report.py`

Generated reports:

- `notes/ocr-longwalk-report.md`
- `notes/ocr-newgame-report.md`

OCR is good enough to identify menu state and early dialogue lines.

## Memory Findings

See also:

- `notes/dialogue-memory-analysis.md`
- `notes/dialogue-write-path.md`
- `notes/dialogue-writer-addresses.md`

Current conclusions:

- visible dialogue is not present in RAM as plain `UTF-8/UTF-16/GBK/Big5/CP932`
- dialogue flips consistently modify `WRAM 0x00A900-0x00AA4A`
- dialogue flips also heavily modify `VRAM 0x002000-0x002700`
- dialogue scene register state is stable across sampled frames: `DISPCNT=0x1940`, `BG3CNT=0x0300`
- `WRAM 0xA8C0-0xAA7F` best matches `VRAM` near `0x1B0A`, inside the `BG3` screen block region

Working interpretation:

- `WRAM 0x00A900+` is a `BG3` tilemap-like dialogue work buffer
- `VRAM 0x1800+` holds the copied `BG3` tilemap region
- `VRAM 0x002000+` is likely glyph/tile upload space for dialogue characters

## Watchpoint Capture

Phase 1 watchpoint capture is now repeatable with:

- script: `tools/mgba_trace_dialogue_writes.lua`
- launcher: `tools/run_headless_mgba.sh`

Confirmed targets and outcomes:

- `NARUTO_TRACE_TARGET=wram`
  - stable writer PC: `0x08066D74`
  - dominant LR: `0x08066D67`
  - target: `WRAM 0x0200A900-0x0200AA4A`
- `NARUTO_TRACE_TARGET=vram_tilemap`
  - reported PC: `0x000002A0`
  - reported LR: `0x000000A4`
  - target: `VRAM 0x06001800-0x06002000`
  - interpretation: likely DMA/system copy into the live `BG3` screen block region near `0x06001B00+`
- `NARUTO_TRACE_TARGET=vram_glyph`
  - stable writer PC: `0x08065F50`
  - stable LR: `0x08065EDF`
  - target: `VRAM 0x06002000-0x06002800`

Artifacts:

- `notes/dialogue-watch-wram.log`
- `notes/dialogue-watch-wram.md`
- `notes/dialogue-watch-vram-tilemap.log`
- `notes/dialogue-watch-vram-tilemap.md`
- `notes/dialogue-watch-vram-glyph.log`
- `notes/dialogue-watch-vram-glyph.md`
- `notes/dialogue-function-analysis.md`
- `notes/dialogue-watch-sb-struct.md`
- `notes/dialogue-watch-record-bank.md`
- `notes/dialogue-ram-structures.md`

Practical conclusion:

- the dialogue path is no longer a single unresolved blur
- WRAM tilemap generation, VRAM tilemap copy, and glyph upload are now separable stages
- the RAM work struct at `0x02002880` and the related record bank at `0x02002E30` are refreshed together through the same upstream caller region near `0x080961D7`

## Breakpoint Attempt

Tried script-side execution breakpoints through:

- `tools/mgba_trace_function_entries.lua`

Targets:

- `0x08066D14`
- `0x08065EB8`

Observed result:

- both runs ended as `timeout_no_hits`

Conclusion:

- watchpoints are currently the reliable script-side capture method
- script-side execution breakpoints should not be treated as stable until proven otherwise
- static disassembly and caller scans were used instead to continue Phase 2

## LLDB Caller Trace

Reusable runtime caller trace now exists through:

- `tools/trace_dialogue_callers.sh`
- `tools/lldb_trace_dialogue_callers.py`

Method:

- headless silent `mGBA`
- `-g` enabled
- `tools/mgba_newgame_walk.lua` drives the opening route
- `lldb` attaches and logs hits for selected `0x08096168` callers

Generated artifacts:

- `notes/lldb-dialogue-callers.log`
- `notes/lldb-dialogue-callers-session.log`
- `notes/lldb-dialogue-callers-mgba.log`
- `notes/dialogue-caller-runtime.md`

Current confirmed result:

- among the sampled caller family, only `0x080968A0` was hit on the opening route
- it was hit twice
- both hits reported `lr=0x08096633`

Practical conclusion:

- the opening dialogue path is currently better anchored in the compact state-transition cluster near `0x080967E8-0x080969F2`
- the broader callers `0x08077D0E`, `0x08089B36`, `0x0809159C`, and `0x08093842` should now be treated as secondary until proven live on a dialogue route

## Next Reverse-Engineering Target

Do not return to blind string scanning as the primary path.

Instead:

1. walk backward from `0x08066D74` to the dialogue data source
2. walk backward from `0x08065F50` to the glyph generation source
3. determine whether the tilemap copy path is DMA-driven and whether its source buffer is exactly the captured `WRAM` region

## In-Progress Debug Branches

### LLDB over GDB stub

Attempt:

- Qt frontend with `-g`
- `lldb` attached to `localhost:2345`
- expression watchpoints on `0x0200A904` and `0x0200A940`

Result:

- transport connection succeeded
- `lldb` expression watchpoints failed on this remote target
- observed failure in `IRMemoryMap.cpp` with watchpoint resolving to `0x00000000`

Conclusion:

- keep the GDB stub path available for memory reads
- do not rely on `lldb` expression watchpoints for this target

Artifacts:

- `tools/lldb-watch-a9xx.cmds`
- `notes/lldb-watch-a9xx.txt`

### Headless script/debugger convergence

Attempt:

- enabled local `BUILD_HEADLESS`
- built `/Users/altair/github/mgba-build/mgba-headless`
- patched local `mgba-src` so SDL gains `--script`
- patched local `headless-main.c` to auto-attach a debugger when scripts are present

Status:

- build and launch succeeded
- reliable script-side execution signal is still not confirmed
- this branch is promising because `headless-main` exposes `emu:setWatchpoint` / `emu:setRangeWatchpoint`

Conclusion:

- do not treat this path as validated yet
- if resumed, start with the smallest possible script-side execution probe before adding watchpoints
