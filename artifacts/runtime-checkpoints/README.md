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

`natural-scenario-41-battle-entry-evidence.json` records the required stale-menu
activation (`A, B`) followed by `Down, Down, A`. It reaches strict battle 41
without a new selector: map 36×44, Naruto `(4,10)`, Iruka `(4,4)`. This closes
the natural route from scenario 41's story terminal to the tracked actionable
battle identity; battle completion and level-up remain separate gates.

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
