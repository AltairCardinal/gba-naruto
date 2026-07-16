# Runtime checkpoint handoff

These files preserve the live state needed to continue the current reverse-
engineering experiments without replaying the entire prologue. They are small
binary evidence artifacts and are intentionally tracked in Git.

## Required ROMs

- `rom/base.gba` is the immutable base ROM already tracked in this repository.
- Rebuild the alternate-table diagnostic ROM; do not retain a generated 6-MiB
  copy:

```bash
python3 tools/build_alternate_chapter_runtime_probe.py \
  rom/base.gba /tmp/alternate-chapter-runtime.gba
```

Expected probe-ROM SHA-256:
`d125d8965a2c4c5b25a177d4ae0b551350c976f42c455f7ebd0eba188576dd4c`.

For the production-relocation runtime proof, build:

```bash
python3 tools/build_relocated_chapter_runtime_probe.py \
  rom/base.gba \
  sequel/content/story-b/scenario-39-relocation.json \
  /tmp/relocated-chapter-runtime.gba
```

Expected SHA-256:
`392bfcd2570be007d0413da5d9d5d626d245ee6e911d5f3aebb83ec3d9443b50`.

## Checkpoints

| File | SHA-256 | State |
|---|---|---|
| `alternate-mission-selection.ss9` | `492ae012702be7488984640da968f3343670f152d189fa3628fee24b056a0308` | independently replayed `木叶里 / 对战` mission-selection page |
| `alternate-kakashi-prompt.ss9` | `b78cc6826751d29cd8751d5b379c2af3d26ab664a8b800cbec52cdf7e3d4737e` | after one valid A; Kakashi directional-choice prompt |
| `alternate-equipment-page.ss9` | `b410703bf0bcec6135286df17b5686d9200380a8e0ff2ca14ac35aa9fb786e02` | equipment page reached through the forward Up+A branch |
| `alternate-character-submenu.ss9` | `b692ebabfa80773debb0685d2589c02fbeda04102f799b37221e72e3941184a8` | one B from equipment; character-information submenu |
| `alternate-character-overview.ss9` | `209bf3c7321fedc93a6c957fb2c7b46f0d48aa56ea5c4bb3858fce93d0a336f6` | character-information overview |
| `tutorial-ui-save.sav` | `9fedf6bf1c43ad08f7c821c76914726801f9a96147b64b181baed7562e0a972b` | natural 32-KiB UI save used for cold-load proof |
| `actionable-move-grid.ss9` | `4821a3a6694d32871a23bbea6a93ba1724663cb4a3c6e5f691d4fd48a5635fac` | real actionable tutorial battle target-selection grid; base-ROM replay passes the strict battle gate |
| `skill-list-pre-controller.ss9` | `b5e26b7bfeb765b7f50a77fe4a6513abf206159695f61a02af19cfb55ce60d1a` | Naruto submenu before the natural high-bit technique-list controller and initializer |
| `scenario-41-prebattle-menu-candidate.ss9` | `b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078` | accepted stable scenario 41 prebattle menu after strict mGBA 0.10.5 zero-input frame-80 replay; still before controller entry |
| `scenario-41-prebattle-down.ss9` | `c1a16fa3fd505c5a4aeb3e593f639c26342c5048d5d506771aa9a6ad6418e449` | one audited Down from the accepted prebattle menu, independently stable for 80 zero-input frames; still not controller/player-control evidence |

## Scenario 41 checkpoint ledger

`scenario-41-checkpoints.json` is the durable lineage and acceptance ledger for
the scenario 41 player-control through postbattle proof. Validate it from the
repository root with:

```bash
python tools/runtime_checkpoint_ledger.py artifacts/runtime-checkpoints/scenario-41-checkpoints.json
```

The ledger accepts the tracked `tutorial-ui-save.sav` as its immutable cold-load
root. `scenario-41-start-row.ss9` is the accepted scenario 41 “开始任务” row:
two guarded base-ROM replays with zero start, advance, tail, adaptive-back and
settle-confirm input stayed on the same selected row for eight settle polls.
Both runs kept battle/map/formation absent, every declared non-visual WRAM field
identical, both player observer records zero and the input audit empty. Their
ignored raw reports are `build/task5-zero-replay-1.json` and
`build/task5-zero-replay-2.json`; the accepted checkpoint SHA-256 is
`e5039f21675dde00f3bc78e7dad08bf7cbd4ce8bff2944ea108a92bbf25b9e81`.
The browser chrome/FPS pixels are not part of the game-state identity check.
This acceptance proves only the stable visible start row and its lineage. It
does **not** claim that the state is dynamically known to precede
`0x08073946`/`0x080739D8`, so the ledger leaves `before_hooks` and
`allowed_evidence` empty. A single audited A reached stable battle 41 on both
the observer and base ROM, but neither published observer produced a fresh
sample. The compact `scenario-41-player-control-evidence.json` therefore
records `not-proven`, and no `scenario-41-player-turn.ss9` exists.
`build/natural-s41-start-prompt.ss9` remains explicitly rejected because
inspection showed the team/equipment page rather than the scenario 41
start-confirm prompt.

`scenario-41-prebattle-menu-candidate.ss9` is now accepted without replaying the
prologue again. Strict run `be8e11738e43f276b0c31798061e63fc` held it for 80 frames
with `inputs=[]`; strictly decoded, normalized RGB pixel hashes are identical before
and after. The frame-80 task 2 resumes at `0x08067D02`, SP `0x030011D8`. Only the
explicit stack slots `0x03001220/0x03001240/0x03001278` are in the accepted unwind;
their raw returns `0x080885C1/0x08088F9F/0x0808F92D` each decode as the expected
Thumb BL in `rom/base.gba`. The controller return `0x0808F957` is absent and
`[0x0202680C]=0`. `scenario-41-prebattle-menu-evidence.json` authenticates all inputs,
outputs, emulator/manifest/patch provenance, `completed/0` non-degraded guard result,
and a fresh clean PGID/listener check. This is reusable prebattle-menu state only; it
does not prove controller entry, player control, MOVEDONE, victory, or postbattle.
Absolute `build/` and `.cache/` paths in the compact JSON identify the historical local
raw evidence; those raw files are not distributed by the repository. The tracked
candidate and compact JSON are the durable handoff. Revalidation from raw bytes needs
the original machine-local Step 1/2 files at their pinned paths. Unlike those raw
files, the exact Qt backport patch is tracked at
`tools/patches/mgba-0.10.5-qt-script-cli.patch`; compact evidence records both its
repository-relative and absolute path, and verifies its bytes equal the manifest's
embedded patch payload.

`scenario-41-prebattle-down.ss9` is the next accepted rung. Single-input run
`e32c5a6229aeec9e406b1d126695799d` sent exactly one Down from frame 5 through
frame 13 and no A, automatic, or recovery input. Independent zero-input run
`7d378580de56bea13a3d0e09b8bea185` then held the resulting state for 80 frames.
All four normalized RGB sources are identical at SHA-256
`1e68324b6496cda1dc4cff6821a1c6b86dbfc422ac15fdfd1bcdfd0a9246352d`.
Task 2 still resumes at `0x08067D02`; explicit slots
`0x03001220/0x03001240/0x03001278`, raw returns and statically decoded Thumb BL
targets are unchanged, and `[0x0202680C]=0`. The compact
`scenario-41-prebattle-down-evidence.json` binds both runs and their guard/resource
checks. This checkpoint proves only a stable Down-selected prebattle row. It does not
prove controller entry or player control and does not independently authorize A;
Step 4 remains a separate gate.

Every record carries its ROM hash, parent, input suffix, observed screen,
zero-input status, pre-hook boundary and permitted evidence scope. Candidate
and rejected `build/` paths may be absent in another checkout; accepted state
paths and every ROM path must be repo-relative regular files inside the checkout
and match their hashes. Candidate/rejected state paths are restricted to
repo-relative `build/` sources; they may be absent, but an existing directory is
never a valid state. The validator accepts only `schema_version: 1` and canonical
eight-digit uppercase hook addresses. Evidence requires these exact pre-hooks:

- `player-control`: `0x08073946`, `0x080739D8`
- `movedone`: `0x0807443C`, `0x08074918`
- `victory`: `0x0807444E`, `0x08074458`
- `postbattle`: `0x080735C2`

Unknown evidence names are rejected. This boundary prevents a later checkpoint
from being used to claim player control, MOVEDONE, victory or postbattle events
that occurred before capture.

Compact JSON evidence also includes `chapter-semantic-codec-evidence.json`, which records
the codec-authored primary scenario 39 script `1A 28 02 | 00` being selected at
`0x0809E800`, dispatched exactly twice, and changing chapter/battle state from 39 to 40.
It deliberately does not claim strict battle-map arrival.

`chapter-relocated-runtime-evidence.json` records the production allocator
writing the same complete 430-byte alternate scenario 39 script at
`0x085F8000`, the selector consuming that relocated pointer, 25 dispatches,
and terminal opcode `00` at `0x085F81AD`.

`natural-scenario-41-runtime-evidence.json` records an unforced selector run
from the genuine Konoha save state. Move/Battle naturally selected primary
`0x60C74[41] -> 0x08031A12`, executed 44 captured opcodes and terminated at
`0x08031D5F` opcode `00` without SetBattle. The outer-state transition proves
the following preparation UI belongs to scenario 41, not the title encyclopedia.

`natural-scenario-41-transient-battle-false-positive.json` revokes an early-stop
false positive. `A, B, Down, Down, A` briefly exposed battle-41 memory/map, but
a forced full settle returned to battle/map zero and the team/equipment panel;
the transient checkpoint's first A also opened team UI, not a battle action
menu. It must not be used as a battle-start checkpoint. A valid replacement
must remain a strict battle after settle and accept an actionable battle input.

scenario-41-battle-entry-evidence.json records the corrected preparation-menu
route Down,Down,A to the “开始任务？” prompt and one A to a battle-41
presentation that remains a strict 36×44 battle for six polls. Its scope stops
before player-control, victory, EXP and level-up proof; it must not be used to
promote the levels bank by itself.

`visual-variant-runtime-evidence.json` records the controlled record 7 /
variant 0 resource-pair A/B that changed the same `ShowPortrait(1,7,0)` frame
from Kakashi to Sakura without changing scenario, script cursor, or dispatch count.

`profile-text-runtime-evidence.json` records a natural title-menu character-
encyclopedia A/B for the 46-entry profile text table. The save file was supplied
but later replay proved this input sequence did not load it. Both runs hit
`0x0808B1A4` once for character
0 / entry `0x085A143C`; the single four-byte pointer change selected entry 7's
text and visibly changed the multi-line profile description.

`actionable-battle-runtime-evidence.json` authenticates the clean actionable
battle checkpoint independently on `rom/base.gba`: battle ID 41, map 36×44,
Naruto `(4,10)`, Iruka `(4,4)`, and all strict-arrival checks true. It replaces
the need to replay the Start overlay and tutorial dialogue for later battle-bank probes.

`action-detail-renderer-evidence.json` records the three-layer writer trace that
locates the battle action detail renderer at `0x080708BC`, proves the tutorial
“忍者组合拳” row is low-bit effect ID 2 rather than a skills row, and preserves
the explicitly forced skill-2 diagnostic A/B without promoting it to natural
runtime evidence.

`adjacent-tutorial-action-evidence.json` records the minimal battle-41
formation diagnostics that move Iruka adjacent to Naruto. It preserves both
the rejected enemy-target route and the ally-triggered tutorial-dialogue false
positive, including the zero-hit skill-relation scratch.

`skill-detail-runtime-evidence.json` records the natural Naruto technique-list
high-bit action and the one-byte skill-1 attack-power A/B (`6x3` to `7x3`).

The old `/tmp/first-battle-map-stable.ss9` is deliberately excluded: it is a
prebattle “view battlefield” false-positive and is unsafe as a combat checkpoint.

## One-time setup

```bash
npm install --prefix play/_scripts
```

Use Chrome or Chromium and set `PROBE_BROWSER` to its executable. The current
macOS path is `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
The probe page defaults to `https://sh.kibox.com.cn/gba-naruto/play/`, so the
machine needs network access unless `PROBE_URL` points to a local equivalent.

## Replay smoke test

```bash
env \
  PROBE_BROWSER='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  PROBE_ROM=/tmp/alternate-chapter-runtime.gba \
  PROBE_STATE_LOAD=artifacts/runtime-checkpoints/alternate-mission-selection.ss9 \
  PROBE_SKIP_NEW_GAME=1 \
  PROBE_INPUT_MODE=keyboard \
  PROBE_START_COUNT=0 \
  PROBE_ADVANCE_COUNT=0 \
  PROBE_TAIL_KEYS='' \
  PROBE_SETTLE_COUNT=1 \
  PROBE_RESULT=/tmp/handoff-replay.json \
  PROBE_SCREENSHOT=/tmp/handoff-replay.png \
  node play/_scripts/runtime-formation-probe.js
```

The command intentionally exits nonzero because no formation or new chapter
dispatch is expected. The screenshot must show the mission-selection page.
Continue from a selected checkpoint with keyboard input only;
the fixed driver maps `KeyZ→z`, `KeyX→x`, and clears latched buttons after load.

## Alternate-table runtime closure

The 2026-07-12 run satisfied the gate and upgraded `story-b` to
`runtime_verified`:

1. selector hit count 1, runtime scenario 39, selected pointer `0x08031281`;
2. 25 generic interpreter dispatches;
3. last cursor `0x0803142E`, with live bytes `00 00 1B 04` matching ROM;
4. opcode `00` is the decoded normal interpreter return at zero call depth, so
   this dialogue-only alternate script intentionally creates no battle state.

The compact durable evidence is
`artifacts/runtime-checkpoints/alternate-story-b-runtime-evidence.json`.

Investigation log: `notes/alternate-chapter-runtime-probe-20260712.md`.
