# Dynamic Verification Evidence Audit

Date: 2026-07-11

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

Under the current bank-level grading the repository has **9 runtime/dynamic,
3 code, 15 static, and 5 disproved aliases** after the 2026-07-12 identity
corrections. This is deliberately stricter than treating extraction success as
runtime proof. The `maps` bank now has same-boundary runtime buffer matches for
its dimensions and resource streams. In particular, the successful dialogue watchpoint traces
prove the dialogue render path, not the separate `fonts` bank at `0x53E5B4`.

## Evidence table

| # | Structure (important ROM offset) | Level | Strongest durable evidence and limitation |
|---:|---|---|---|
| 1 | audio (`0x465B70`) | runtime | `0x0809AAC0` indexes the sound-ID master table and initializes m4a tracks; a live wrapper probe captured ID 118 resolving to descriptor `0x53D06C`. All 217 tracks structurally decode; 80 one-loop MIDIs execute 17,202 events. Instrument coverage resolves 16,180/16,180 notes: 16,169 DirectSound notes reach all 79 waves (5,340 through drum tables), and 11 are explicit PSG/noise. Pitch/envelope/mixer fidelity and audible cue names remain open. |
| 2 | battle-effect templates (`0x545458`) | runtime | A live caller consumed effect 2. A controlled level-2 A/B changed only record 2 growth `+0x0E:1→2`; the type-4 runtime destination byte `+7` changed `4→5`, while other output bytes remained stable. |
| 3 | battle-encounters (historical slug; real base `0x54229C`) | code | Corrected to 24 visual descriptors. Story opcode chain `0x0808FA2C→0x0808A69C→0x08087C9C` indexes all records and decompresses three LZ77 streams; no encounter semantics remain. |
| 4 | battle-handlers (`0x53E778`) | static | Valid Thumb handler pointers/call-shape analysis only; no breakpoint hit tied to this table. |
| 5 | character-stats / growth (`0x545068`) | runtime | `0x0806D964` computes `0x08545068 + id*0x10` and applies seven growth fields as `value*(level-1)/100` to template destinations. A two-factor first-battle probe changed character 1 physical record `+4` from 100 to 200 and changed only template/battle-slot `+2` from 15 to 16. See `notes/character-growth-runtime-chain-20260711.md`. |
| 6 | character-stats-b (`0x545200`) | disproved | Not an independent structure: `0x545200 = 0x545068 + 25*0x10 + 8`, halfway through physical growth record 25. Bank retained only as a tombstone; legacy bytes write-back is disabled. |
| 7 | cutscene-scripts (`0x53DF70`) | code | Corrected to two adjacent four-record visual-resource tables. `0x08072EDC` indexes compressed gfx/palette pairs and passes the second pair table to the sprite allocator; direct callers use IDs 0..3. Historical slug only. |
| 8 | data-table-a (`0x5A14A4`) | static | Repeating valid pointers and encoded target blocks only; semantics and consumer remain unproved. |
| 9 | data-table-b (`0x5A2120`) | static | Repeating valid pointers and encoded target blocks only; semantics and consumer remain unproved. |
| 10 | encounter-zones (`0x53D910`) | disproved | The former 47 rows duplicate the complete maps table. Runtime resource tracing identifies `+0x1C` as map flags, with byte `+0x1D` consumed at `0x0806922A`; no independent encounter-zone identity remains. |
| 11 | fonts (`0x53E5B4`) | static | Width-table shape in the bank. `notes/dialogue-font-table-discovery-20260703.md` and dialogue watch logs concern a different font lookup table at `0x53D644` and therefore do not dynamically verify this bank. |
| 12 | function-pointers (`0x53D5F4`) | code | `0x08061D8C` indexes one-based callbacks from sentinel base `0x0853D5F0`; `0x08061DD4..DC` loads the selected entry and stores it in a 0x4C-byte task. All 11 wrappers pass IDs 1..11 to `0x08061C58`. No live hit identifies a selected entry. |
| 13 | items (`0x546100`) | disproved | The former bank was byte-for-byte identical to `skills` and had no independent consumer. It is now a tombstone; legacy item writes remain diagnostic-only. |
| 14 | levels (`0x5459B4`) | static | Regular progression/experience values and parsed entries only; no level-up runtime delta tied to the table. |
| 15 | map-events (historical slug; real base `0x53E698`) | code | Corrected to 256 primary/secondary handler pairs. `0x0807F934..0x0807F964` indexes both halves from runtime byte `sb+0x770` and dispatches nonzero callbacks through `0x0809C114`. |
| 16 | maps (`0x53D910`) | runtime | Width has a controlled row-40 36→32 A/B. A strict row-41 battle capture then matched tile gfx in VRAM, BG palette after transparent-color normalization, primary layout and metatile definitions exactly, null alternate-layout skip, and collision low-byte passability under two runtime occupancy overlays. |
| 17 | map-sprites (`0x53E1DC`) | static | Pointer-table consistency and animation-shaped targets only. |
| 18 | menu-ui (`0x5A5774`) | static | Alternating pointer pattern and UI-like targets only; no menu route/table access trace. |
| 19 | palettes (`0x53F138`) | static | Valid RGB555-looking targets only. The former conflict is resolved: audio moved to its real master table at `0x465B70`; palette consumer/runtime A/B is still missing. |
| 20 | positions (`0x5461C4`) | dynamic | WASM navigation reached the first battle; WRAM slot 1 x/y `(4,4)` uniquely matches group 40 / variant 0 / record 0 at ROM `0x588CA8`. Static code independently proves record `+2/+3` feeds unit coordinates. |
| 21 | resource-pointers (`0x596F0C`) | static | Twenty valid nested resource pointers only; no consumer or visible controlled edit. |
| 22 | sappy-engine (`0x09AE3C`) | code | Disassembly proves FIFO/DMA sound initialization and connects the public wrapper, dispatcher and track initializer. No controlled engine-code A/B is required or enabled. |
| 23 | save-state (`0x53D848`) | runtime | Genuine tutorial victory followed by UI Save wrote a valid 32-KiB slot-1 image: active descriptors 0/2 have `Naruto-KONOHASENKI\0` headers and valid payload checksums; erased records remain all-FF. A cold restart recognized and restored Konoha. Physical records are 19-byte header + payload + checksum. Tutorial/title paths bypass the optional group 3..9 wrappers. |
| 24 | skills (`0x545BE4`) | code | `0x0806D910` indexes `0x08545BE4 + skill_id*16` and copies bytes `0..9` into a runtime skill structure. The corrected table is 94 records ending at positions base `0x5461C4`; field UI meanings and a live selected-skill capture remain pending. |
| 25 | sprite-animations (`0x53E200`) | static | Valid 38-entry animation pointer/frame structures only; no frame traversal hit. |
| 26 | story (`0x60C74`) | dynamic | `0x0808F544` selected primary entry 39 → script `0x08031020`; live hook at `0x08097C78` captured opcode `1A 28 02 00` at `0x08031070`, which writes battle ID 40 through state `+0x16` to `0x02026805`. |
| 27 | story-b (`0x60D54`) | runtime | A forced-alternate causal probe captured selector scenario 39 choosing table entry `0x08031281`, then 25 generic interpreter dispatches ending at `0x0803142E` opcode `00`; live opcode bytes matched ROM. Static control flow proves `00` normally returns at zero call depth, explaining the intentional zero battle state. |
| 28 | story-c (`0x538FF0`) | disproved | Descriptor `0x538FEC + 4`, header `0x80000009`; resource-set slice. |
| 29 | story-d (`0x53AB78`) | disproved | Descriptor `0x53AB74 + 4`, header `0x8000000A`; resource-set slice. |
| 30 | story-e (`0x53C3C0`) | disproved | Descriptor `0x53C3BC + 4`, header `0x80000008`; resource-set slice. |
| 31 | tile-assets (`0x5A3218`) | static | Six valid pointers to tile/map-like data only; no decompressor/read hit or controlled visual change. |
| 32 | units (`0x54241C`) | dynamic | `tools/extract_character_definitions.py` extracts 63×`0xB4` records from the character definition table. `notes/character-definition-source-20260711.md` records a WASM first-battle sample where runtime template slot 1 (`characterId=1`) is copied byte-for-byte into battle slot 1, plus a controlled `PROBE_ROM` A/B changing file `0x5424D1` from `0x0e` to `0x0f`; the runtime template payload changes from `010e0d...` to `010f0d...` on the same route. This dynamically proves at least one raw record field enters the template and unit slot. Remaining per-field semantics and safe semantic writeback are not yet proven. |

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
  upgrade `battle-config` or stats to `dynamic` yet; `positions` and `units`
  have separate WASM runtime evidence in `notes/wasm-formation-probe-result-20260710.md`.
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

The table and checksum invariants are now executable before any runtime dump is
available:

```sh
python3 tools/verify_save_state_records.py \
  --bank sequel/content/save-state/bank.json --rom rom/base.gba
```

When a 64KB SRAM dump is available, add `--sram-dump <FILE>` to validate the 7
unique 20-byte records at the documented offsets.

Battle-config also has an executable static boundary check for the separate
`0x08545458` u16[8] x 32 data table:

```sh
python3 tools/verify_battle_config_records.py \
  --bank sequel/content/battle-config/bank.json --rom rom/base.gba
```

This proves the bank matches immutable ROM bytes and keeps it separate from the
legacy `0x0853D910` scenario descriptor path, but it does not upgrade
`battle-config` to `dynamic`; that still requires a runtime hit at the
`0x0806D866` consumer path.

The corrected character-growth bank has an executable byte-fidelity check:

```sh
python3 tools/verify_character_stats_records.py --rom rom/base.gba
```

This now validates the single 63-record table at `0x08545068`. The former
`0x0854507A` and `0x08545200` bases were misaligned slices and are not separate
tables; runtime consumption is proven separately by the two-factor probe.

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

### 3. Character growth: completed (`runtime`)

The prior exact-address scan failed because both guessed bank bases were
misaligned. A range scan found literal `0x08545068` at `0x0806D998`; disassembly
and controlled A/B then closed the table to template slot 1 and battle slot 1.

If a new candidate write target is found, use a state immediately before
battle/unit initialization:

```sh
python3 tools/mgba-headless-snapshot.py --rom <ROM> --mode watch \
  --watch 0x02022EF0 --max-hits 4 --frames 300 \
  --output notes/character-stats-load-watch.json
```

Do not rerun the obsolete watch command as the primary next action. The next
stats work is field naming and editor migration; retain the existing two-factor
probe as the regression method.

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
