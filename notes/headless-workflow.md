# Headless mGBA Workflow

## Runtime

- Local scripted binary: `/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA`
- Launch wrapper: `tools/run_headless_mgba.sh`
- Required environment: `QT_QPA_PLATFORM=offscreen`
- Audio policy: `tools/run_headless_mgba.sh` forces `-C mute=1 -C volume=0`

The Homebrew `mGBA 0.10.5` binary is still useful for ad-hoc GUI runs, but it does **not** accept `--script`. All repeatable automation in this repo should use the locally built Qt binary through `tools/run_headless_mgba.sh`.

## Process Hygiene

Before a new batch run, clear stale emulator processes:

```bash
pkill -f '/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA' || true
pkill -f '/usr/local/Cellar/mgba/.*/mGBA.app/Contents/MacOS/mGBA' || true
```

## Proven Headless Flows

- `tools/mgba_long_walk.lua`
  Reaches title menu and save-slot flow, including the `没有记录存档` popup.
- `tools/mgba_newgame_walk.lua`
  Reaches opening story dialogue and captures multiple dialogue frames.
- `tools/mgba_newgame_snapshot.lua`
  Reaches frame `2160` in the opening dialogue, then dumps a screenshot plus `WRAM/IWRAM/VRAM/Palette/OAM` binary snapshots.
- `tools/mgba_dialogue_io_dump.lua`
  Reaches frames `2160`, `2340`, `2520`, and `2700` in the opening dialogue and dumps `IO` register memory snapshots.

Representative outputs:

- `notes/longwalk-1080.png`: title menu with four options
- `notes/longwalk-1680.png`: `没有记录存档` popup
- `notes/newgame-1620.png`: opening dialogue scene, OCR recognizes `伊鲁卡`
- `notes/newgame-2160.png`: opening dialogue scene, OCR recognizes `是啊。是我这个班主任所承认的嘛！`
- `notes/newgame-2160-snapshot.png`: fixed dialogue reference frame used for memory snapshots
- `notes/newgame-2160-wram.bin`: `0x40000` bytes of `WRAM` from that frame
- `notes/newgame-2160-vram.bin`: `0x18000` bytes of `VRAM` from that frame
- `notes/dialogue-io-2160-io.bin`: `0x60` bytes of `IO` register state at dialogue frame `2160`
- `notes/dialogue-render-analysis.md`: combined `IO/WRAM/VRAM` interpretation for the dialogue renderer

## OCR Tooling

- Native OCR binary: `tools/bin/ocr_screenshot`
- Timeline helper: `tools/ocr_report.py`

Example:

```bash
python3 tools/ocr_report.py 'notes/newgame-*.png' --output notes/ocr-newgame-report.md
```

This gives a quick text timeline from headless screenshots and is sufficient to identify menu state and portions of early dialogue without opening the images manually.

## Exposed Memory Domains

Probe script: `tools/mgba_dump_domains.lua`

Confirmed names from this build:

- `bios`
- `cart0`
- `cart1`
- `cart2`
- `wram`
- `iwram`
- `vram`
- `io`
- `palette`
- `oam`

## Dialogue Reverse Engineering

Reference note: `notes/dialogue-memory-analysis.md`

Current state:

- Visible dialogue does not appear in RAM as plain `UTF-8/UTF-16/GBK/Big5/CP932`.
- Dialogue page flips consistently mutate `WRAM 0x00A900-0x00AA4A`.
- The same flips heavily mutate `VRAM 0x002000-0x002700`.

Current interpretation:

- `WRAM 0x00A900+` is likely a 16-bit tilemap-like dialogue work buffer.
- `VRAM 0x002000+` is likely the rendered target region for the dialogue box.

## Watchpoint Workflow

Repeatable Phase 1 capture now exists through:

- script: `tools/mgba_trace_dialogue_writes.lua`
- launcher: `tools/run_headless_mgba.sh`

Targets:

- `NARUTO_TRACE_TARGET=wram`
- `NARUTO_TRACE_TARGET=vram_tilemap`
- `NARUTO_TRACE_TARGET=vram_glyph`

Example:

```bash
NARUTO_TRACE_TARGET=wram \
tools/run_headless_mgba.sh \
  tools/mgba_trace_dialogue_writes.lua \
  build/naruto-sequel-dev.gba
```

Generated artifacts:

- `notes/dialogue-watch-*.log`
- `notes/dialogue-watch-*.summary.txt`
- `notes/dialogue-watch-*.md`
- `notes/dialogue-watch-*-first-hit.png`

Current confirmed outputs:

- `WRAM` writer PC: `0x08066D74`
- `VRAM glyph` writer PC: `0x08065F50`
- `VRAM tilemap` copy path reports non-ROM PC values and is best treated as DMA/system-side until proven otherwise

## Static Follow-Up

Headless watchpoints are now complemented by in-repo static helpers:

- `tools/disasm_thumb.py`
- `tools/find_thumb_calls.py`

These were used to confirm:

- `0x08066D74` is the post-store PC for `0x08066D70: strh r0, [r4]`
- `0x08065F50` is the post-store PC for `0x08065F4C: strh r1, [r3]`
- `0x08065EB8` is a compact glyph/tile expansion routine
- `0x08065F84` and `0x080894DE` are stronger next-step caller anchors than the generic tilemap helper at `0x08066D14`

## LLDB Runtime Caller Filter

For caller-family filtering above the static disassembly layer, use:

- `tools/trace_dialogue_callers.sh`
- `tools/lldb_trace_dialogue_callers.py`

Example:

```bash
tools/trace_dialogue_callers.sh build/naruto-sequel-dev.gba
```

Current validated behavior:

- runs headless and silent
- drives the opening new-game route with `tools/mgba_newgame_walk.lua`
- attaches `lldb` over the `mGBA` GDB stub
- logs hits for selected `0x08096168` callers

Current result:

- only `0x080968A0` was observed on the sampled opening route

See:

- `notes/dialogue-caller-runtime.md`
- `notes/lldb-dialogue-callers.log`

## Render Analysis

Renderer correlation helper:

- `tools/analyze_dialogue_render.py`

Current confirmed render model:

- dialogue scene is `Mode 0`
- active text layer is `BG3`
- `BG3` uses screen base `0x1800`
- `WRAM 0xA900+` mirrors best into `VRAM` near `0x1B0A`
- `VRAM 0x2000+` behaves like glyph/tile upload space, not the dialogue tilemap itself
