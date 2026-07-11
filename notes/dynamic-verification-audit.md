# Dynamic Verification Evidence Audit

Date: 2026-07-10

## Scope and grading rule

This audit covers the 32 `sequel/content/*/bank.json` structures and the
existing mGBA scripts, logs, screenshots, memory dumps, and reverse-engineering
notes. It does not treat a passing importer/build test as runtime evidence.

The table reports the **highest evidence level actually present**:

- `dynamic`: a recorded emulator/debugger observation directly links the named
  ROM structure (or a controlled edit to it) to a runtime read/write or visible
  behavior.
- `code`: disassembly establishes a concrete consumer/producer and field/data
  flow, but no successful runtime observation directly identifies the structure.
- `static`: shape, pointer validity, repetition, extraction, or content
  correlation only.
- `none`: no structure-specific evidence beyond an assertion/inventory entry.

Under this definition the current repository has **1 dynamic, 6 code, 24
static, and 1 none** after the positions runtime trace was closed on
2026-07-10. This is deliberately stricter than the `verification`
strings in the banks. In particular, the successful dialogue watchpoint traces
prove the dialogue render path, not the separate `fonts` bank at `0x53E5B4`.

## Evidence table

| # | Structure (important ROM offset) | Level | Strongest durable evidence and limitation |
|---:|---|---|---|
| 1 | audio (`0x53F138`) | code | `sequel/content/audio/bank.json` records dispatcher `0x08079668`, indexed table `0x08599634`, and call sites. No audio command/table access was captured live. The bank offset also collides with `palettes`, so the bank identity needs correction before a dynamic patch test. |
| 2 | battle-config (`0x545458`) | code | `notes/battle-config-format.md` records code reference `0x0806D866 -> 0x08545458`. Existing runtime section says blocked; it contains no successful hit. |
| 3 | battle-encounters (`0x542384`) | static | Pointer/value pattern and parsed entries in the bank/results document only; no encounter selection trace. |
| 4 | battle-handlers (`0x53E778`) | static | Valid Thumb handler pointers/call-shape analysis only; no breakpoint hit tied to this table. |
| 5 | character-stats (`0x54507A`) | static | Parsed table plus WRAM observations in `notes/character-stats-addresses.md`; no trace proves this ROM table populates those WRAM fields. |
| 6 | character-stats-b (`0x545200`) | static | Consistent table and pointer/reference inspection only. |
| 7 | cutscene-scripts (`0x53DF70`) | static | Valid pointers into `0x12xxxx` script-like data only; no script fetch/scene correlation trace. |
| 8 | data-table-a (`0x5A14A4`) | static | Repeating valid pointers and encoded target blocks only; semantics and consumer remain unproved. |
| 9 | data-table-b (`0x5A2120`) | static | Repeating valid pointers and encoded target blocks only; semantics and consumer remain unproved. |
| 10 | encounter-zones (`0x53D610`) | static | Parsed fields/correlation only. No controlled zone transition or table-read hit. |
| 11 | fonts (`0x53E5B4`) | static | Width-table shape in the bank. `notes/dialogue-font-table-discovery-20260703.md` and dialogue watch logs concern a different font lookup table at `0x53D644` and therefore do not dynamically verify this bank. |
| 12 | function-pointers (`0x53D5F4`) | code | Disassembly identifies 11 small Thumb functions and their common-call parameter pattern (`docs/rom-reverse-engineering-results.md`). No live hit identifies a selected entry. |
| 13 | items (`0x546100`) | none | `notes/unknown-item-inventory.md` explicitly says dynamic analysis is required and no standalone item table is confirmed. The offset duplicates `skills`, so the current bank is not evidence of an independent item structure. |
| 14 | levels (`0x5459B4`) | static | Regular progression/experience values and parsed entries only; no level-up runtime delta tied to the table. |
| 15 | map-events (`0x53EB08`) | static | 47 valid Thumb pointers and reuse by map indices only; no event dispatch hit. |
| 16 | maps (`0x53D910`) | code | `notes/chapter-flow-format.md` disassembles map loader `0x08068FF0` and its `base + 4 + id*32` access. `notes/chapter-init-trace-summary.txt` is `timeout_no_hits`, so this is not dynamic. |
| 17 | map-sprites (`0x53E1DC`) | static | Pointer-table consistency and animation-shaped targets only. |
| 18 | menu-ui (`0x5A5774`) | static | Alternating pointer pattern and UI-like targets only; no menu route/table access trace. |
| 19 | palettes (`0x53F138`) | static | Valid RGB555-looking targets only. It shares the claimed table offset with `audio`, an unresolved identity conflict. |
| 20 | positions (`0x5461C4`) | dynamic | WASM navigation reached the first battle; WRAM slot 1 x/y `(4,4)` uniquely matches group 40 / variant 0 / record 0 at ROM `0x588CA8`. Static code independently proves record `+2/+3` feeds unit coordinates. |
| 21 | resource-pointers (`0x596F0C`) | static | Twenty valid nested resource pointers only; no consumer or visible controlled edit. |
| 22 | sappy-engine (`0x079268`) | code | Handler disassembly and command ranges/callers are documented in the bank/results. No runtime command hit/audio-state change is recorded. |
| 23 | save-state (`0x086248`) | code | Deep disassembly of handler `0x08068684` establishes 19 data bytes plus checksum and EWRAM/SRAM mapping (`sequel/content/save-state/bank.json`). No before/after SRAM trace validates field semantics. |
| 24 | skills (`0x546100`) | static | Parsed skill-shaped rows and correlations only; no battle action/table-read observation. Offset collision with `items` must be resolved. |
| 25 | sprite-animations (`0x53E200`) | static | Valid 38-entry animation pointer/frame structures only; no frame traversal hit. |
| 26 | story (`0x53636C`) | static | Nine chapter-data pointers and byte-pattern similarity only. The opening-route runtime logs do not identify this table or one of its targets. |
| 27 | story-b (`0x536BC8`) | static | Eleven chapter-like pointers only; no route/table selection evidence. |
| 28 | story-c (`0x538FF0`) | static | Ten chapter-like pointers only; no route/table selection evidence. |
| 29 | story-d (`0x53AB78`) | static | Eleven chapter-like pointers only; no route/table selection evidence. |
| 30 | story-e (`0x53C3C0`) | static | Nine chapter-like pointers only; no route/table selection evidence. |
| 31 | tile-assets (`0x5A3218`) | static | Six valid pointers to tile/map-like data only; no decompressor/read hit or controlled visual change. |
| 32 | units (`0x54241C`) | code | `tools/extract_character_definitions.py` extracts 63×`0xB4` records from the code-referenced character definition table. Existing battle snapshots do not yet prove a runtime slot was populated from a specific record, so this is not runtime_verified. |

## Existing runtime assets: what they do and do not prove

- `tools/mgba_newgame_walk.lua`, `notes/mgba-newgame-walk.log`, and
  `notes/newgame-*.png` prove repeatable title-to-opening-dialogue navigation.
- `tools/mgba_trace_dialogue_writes.lua`, `notes/dialogue-watch-*.log`, and
  `notes/dialogue-write-path.md` dynamically prove WRAM/VRAM dialogue writers
  (`0x08066D74`, `0x08065F50`). Dialogue is not one of the 32 banks.
- `tools/trace_dialogue_callers.sh` and `notes/dialogue-caller-runtime.md`
  dynamically prove an opening-route hit at `0x080968A0`, but no story table
  address or target pointer was captured.
- `tools/mgba_trace_chapter_init.lua` attempted to reach battle initialization.
  `notes/chapter-init-trace-summary.txt` says `status=timeout_no_hits`; the many
  `chapter-init-*.png` files are navigation screenshots, not positive structure
  evidence.
- `notes/battle-*.json`, `notes/loaded-save-battle.json`, and WRAM dumps provide
  useful state snapshots, but lack a captured ROM source/read PC. They cannot
  upgrade `battle-config`, `positions`, `units`, or stats to `dynamic` yet.
- `tools/mgba-headless-snapshot.py` is the portable Linux debugger path. The Lua
  wrapper requires an mGBA build with `--script`; several Lua files also contain
  the historical hard-coded macOS output directory and should be parameterized
  before treating their commands as portable.

## Cheapest next dynamic-verification targets

The following are ordered by expected effort and reuse of current assets. Each
test must preserve the raw JSON/log and a short result note. `<ROM>` should be a
known-good ROM path; commands below avoid long scripted emulator runs.

### 1. Save-state: prove an SRAM write and checksum (`code` -> `dynamic`)

Start with a short debugger snapshot to confirm the SRAM domain is readable:

```sh
python3 tools/mgba-headless-snapshot.py --rom <ROM> --mode snapshot \
  --dump 0x0E000000:160 --frames 10 \
  --output notes/save-state-sram-before.json
```

Then use a prepared save/battle state (or one manual save action), repeat as
`save-state-sram-after.json`, and diff the two JSON files. The decisive record
is a 20-byte changed record whose byte 19 matches the checksum algorithm from
`0x08068684`; a boot-only unchanged dump is not a pass.

### 2. Maps: catch the already-disassembled table consumer (`code` -> `dynamic`)

The table base and loader are known, so a short breakpoint/watch attempt has a
clear success condition:

```sh
python3 tools/mgba-headless-snapshot.py --rom <ROM> --mode watch \
  --watch 0x02026805 --max-hits 1 --frames 300 \
  --output notes/maps-chapter-id-watch.json
```

Run this from a state immediately before a map transition. Record PC/LR, the
chapter ID, and dump the corresponding 32-byte entry at
`0x0853D914 + id*32`. This simultaneously creates evidence useful for `maps`;
it does **not** verify `positions` unless a source-to-unit-array write is also
captured.

### 3. Character stats: connect one ROM row to loaded WRAM (`static` -> `dynamic`)

From a state immediately before battle/unit initialization:

```sh
python3 tools/mgba-headless-snapshot.py --rom <ROM> --mode watch \
  --watch 0x02022EF0 --max-hits 4 --frames 300 \
  --output notes/character-stats-load-watch.json
```

A pass requires a non-BIOS writer PC plus register/source evidence resolving to
`0x0854507A` (or a documented intermediate copy). A mere WRAM value match is
only correlation.

### 4. Story: attach a ROM target to the proven opening route (`static` -> `dynamic`)

Reuse the proven navigation/tracer command:

```sh
tools/trace_dialogue_callers.sh build/naruto-sequel-dev.gba
```

Extend the existing LLDB breakpoint set only around the upstream
`lr=0x08096633` path and log the active ROM pointer. A pointer falling inside a
target referenced by table `0x0853636C`, together with the current screenshot
frame, upgrades `story`; a hit at `0x080968A0` alone does not.

### 5. Fonts: controlled width-byte visual test (`static` -> `dynamic`)

This is likely the cheapest visible A/B patch, but first choose a glyph known to
use the `0x53E5B4` width table (not the separate SJIS table at `0x53D644`). Build
two ROMs differing in one width byte and run the existing short opening capture:

```sh
MGBA_BIN=<script-enabled-mgba> tools/run_headless_mgba.sh \
  tools/mgba_newgame_snapshot.lua <PATCHED_ROM>
sha256sum <BASELINE_SCREENSHOT> <PATCHED_SCREENSHOT>
python3 tools/ocr_report.py 'notes/font-width-*.png' \
  --output notes/font-width-ocr-report.md
```

The result is dynamic only if the selected text route demonstrably consumes the
changed width entry and the expected horizontal placement/line-wrap changes.
Rename/copy the two emitted screenshots to the `font-width-*.png` names before
running the comparison. A different PNG hash or OCR result alone is not enough;
retain the two images and describe the expected glyph-spacing change.

## Immediate interpretation

The next work should not be a broad rerun of screenshots. The fastest path is
to add source-address logging to a prepared-state transition: one successful
map loader or stats-load trace can establish the reusable runtime method for
several neighboring battle structures. Before patch-based tests, resolve the
three bank identity/alias hazards: `audio` versus `palettes` at `0x53F138`,
`items` versus `skills` at `0x546100`, and `maps` versus `positions` at
`0x53D910/0x53D914`.
