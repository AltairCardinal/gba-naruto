# Dialogue Caller Runtime Trace

## Scope

This note records a first runtime filter over the known `0x08096168` caller family.

The goal was to separate:

- callers that are only generic window or record setup
- callers that actually appear on the opening story dialogue route

## Method

Runtime path:

- emulator: local scripted Qt `mGBA`
- mode: headless, silent, `-g` enabled
- navigation script: `tools/mgba_newgame_walk.lua`
- tracer:
  - `tools/trace_dialogue_callers.sh`
  - `tools/lldb_trace_dialogue_callers.py`

Tracked caller addresses:

- `0x08077D0E`
- `0x08089B36`
- `0x0809159C`
- `0x08093842`
- `0x0809678A`
- `0x080968A0`
- `0x0809698E`

Artifacts:

- `notes/lldb-dialogue-callers.log`
- `notes/lldb-dialogue-callers-session.log`
- `notes/lldb-dialogue-callers-mgba.log`

## Result

During the sampled opening new-game route, the only traced caller that actually hit was:

- `0x080968A0`

Observed hits:

- hit 1:
  - `pc=0x080968A0`
  - `lr=0x08096633`
  - `r0=0x00000000`
  - `r1=0x00000001`
  - `r2=0x00000001`
  - `r3=0x00000000`
- hit 2:
  - `pc=0x080968A0`
  - `lr=0x08096633`
  - `r0=0x00000001`
  - `r1=0x0000002C`
  - `r2=0x00000000`
  - `r3=0x00000000`

No runtime hits were captured for:

- `0x08077D0E`
- `0x08089B36`
- `0x0809159C`
- `0x08093842`
- `0x0809678A`
- `0x0809698E`

## Interpretation

This is the strongest current evidence that the opening story route is not using the richer multi-window callers such as:

- `0x08077D0E`
- `0x0809159C`
- `0x08093842`

Those callers still look relevant, but they now read more like:

- menu windows
- battle/status panels
- event UI blocks

The live opening-dialogue branch is instead passing through the compact state-transition cluster around:

- `0x080967E8`
- `0x080968A0`
- `0x0809698E`

Within that cluster, `0x080968A0` is now the best runtime-confirmed Phase 2 anchor.

## Static classification of the current caller family

### Likely generic panel/window setup callers

- `0x08077D0E`
  - allocates a `0x28 x 0x60` style block
  - immediately performs multiple `0x8066AE8` / `0x80667A0` style layout calls
  - looks like a large composite panel path
- `0x08093842`
  - same broad shape as `0x08077D0E`
  - appears to create several stacked UI rows and icon/text fields
- `0x08089B36`
  - begins from slot/entity lookup helpers `0x080886E8` / `0x08088718`
  - copies `0xBC`-byte records and compares values
  - looks more like a status/comparison panel than direct script dialogue
- `0x0809159C`
  - performs setup around `0x8090564`, `0x8090584`, and several layout calls
  - still looks event/UI related, but not yet proven as the opening route

### Likely compact record-state callers

- `0x0809678A`
  - seeds bytes in a `record + 0x2c` area and marks the record active
- `0x080968A0`
  - commits staged bytes from `[+4/+5]` into `[+2/+3]`
  - clears staging bytes
  - calls `0x08096DD4`
  - was the only caller in this family confirmed at runtime on the sampled opening route
- `0x0809698E`
  - performs a two-record loop and pushes bytes into `[+2/+3/+4/+5]`
  - likely another state-preparation or transition helper, but not hit on this sampled path

## Practical conclusion

For Phase 2, the search priority should move from the broad `0x08096168` caller list to:

1. `0x080968A0`
2. the enclosing compact state-transition family near `0x080967E8-0x080969F2`
3. the upstream caller indicated by runtime `lr=0x08096633`

The broad panel builders remain useful background references, but they are no longer the best primary target for the opening dialogue path.
