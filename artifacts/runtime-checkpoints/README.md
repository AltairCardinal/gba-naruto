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
`c98e2d2c02e4e0235e14e584a5a423a20a079db897b85fa09adea7ef0a93e6a4`.

## Checkpoints

| File | SHA-256 | State |
|---|---|---|
| `alternate-mission-selection.ss9` | `492ae012702be7488984640da968f3343670f152d189fa3628fee24b056a0308` | independently replayed `木叶里 / 对战` mission-selection page |
| `alternate-kakashi-prompt.ss9` | `b78cc6826751d29cd8751d5b379c2af3d26ab664a8b800cbec52cdf7e3d4737e` | after one valid A; Kakashi directional-choice prompt |
| `alternate-equipment-page.ss9` | `b410703bf0bcec6135286df17b5686d9200380a8e0ff2ca14ac35aa9fb786e02` | equipment page reached through the forward Up+A branch |
| `alternate-character-submenu.ss9` | `b692ebabfa80773debb0685d2589c02fbeda04102f799b37221e72e3941184a8` | one B from equipment; character-information submenu |
| `alternate-character-overview.ss9` | `209bf3c7321fedc93a6c957fb2c7b46f0d48aa56ea5c4bb3858fce93d0a336f6` | character-information overview |
| `tutorial-ui-save.sav` | `9fedf6bf1c43ad08f7c821c76914726801f9a96147b64b181baed7562e0a972b` | natural 32-KiB UI save used for cold-load proof |

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

The command intentionally exits nonzero because no formation is expected. The
screenshot must show the mission-selection page and the JSON must show chapter
hook hit count 0. Continue from a selected checkpoint with keyboard input only;
the fixed driver maps `KeyZ→z`, `KeyX→x`, and clears latched buttons after load.

## Current acceptance gate

`story-b` remains `code_verified`. Do not upgrade it until a run records:

1. chapter opcode tracer hit count greater than zero;
2. captured script pointer belonging to alternate table entry
   `0x60D54[scenario_id]` (scenario 39 points to `0x08031281`);
3. opcode bytes inside that alternate script;
4. a resulting nonzero chapter/battle state, or a decoded alternate termination
   opcode explaining why no battle state is created.

Investigation log: `notes/alternate-chapter-runtime-probe-20260712.md`.
