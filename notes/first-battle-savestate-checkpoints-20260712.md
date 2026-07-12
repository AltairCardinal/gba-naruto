# First-battle savestate checkpoints (2026-07-12)

## Purpose

The natural-save acceptance gate requires a genuine tutorial completion before
the postbattle caller `0x080732B4 → 0x08074F2C` can be credited.  Repeatedly
replaying the title/story path made UI experiments slow and irreproducible, so
this work established deterministic WASM savestate checkpoints and separated
screen classification, cursor state, and battle-unit state.

## Method and durable tooling

`play/_scripts/runtime-formation-probe.js` now supports:

- `PROBE_STATE_LOAD`: install an `.ss9` file in mGBA's `/data/states/` and load
  it after the ROM-ready gate;
- `PROBE_STATE_DUMP` plus `PROBE_STATE_DUMP_PHASE`: save slot 9 and export the
  exact checkpoint;
- `PROBE_MEMORY_DUMP`, `PROBE_MEMORY_ADDRESS`, and `PROBE_MEMORY_LENGTH`: dump
  a reproducible GBA memory range at the same diagnostic boundary;
- `PROBE_SKIP_NEW_GAME=1`: do not inject the normal new-game confirmation when
  starting from a checkpoint.

`tools/audit_wasm_savedata_api.js` now waits for a genuinely loaded ROM, lists
the state-related API surface, and proves both `saveState(9)` and
`saveStateSlot(9, 63)` create `naruto-sequel-dev.ss9`.  This is emulator
savestate transport only; it is not evidence that the game executed its own
SRAM save routine.

## Proven checkpoints and observations

1. `/tmp/first-battle-tail.ss9` (55,106 bytes) is the special-chest tutorial
   page.  From it, `A, Down, Down, A, A` reaches the map reproducibly.
2. `/tmp/first-battle-map-stable.ss9` (71,951 bytes) is a stable genuine map:
   battle ID 40, runtime map `[36,44,9,22]`, and the unique formation is slot 1,
   character 1 at `(4,4)`.
3. A no-input reload of that checkpoint independently passed the strict gate.
   Its measured `edgeRatio` is about `0.3435`.
4. Texture-edge density fixes the camera-dependent weakness of the old black-
   corner heuristic.  Calibrated values are about `0.3436` for the stable map,
   `0.1263` for the character panel, and `0.0806..0.0980` for tutorial pages.
5. Full EWRAM A/B dumps locate the battle cursor at `0x02026A78/79`.  Stable
   cursor `(4,11)`, left `(1,11)`, right `(7,11)`, up `(4,6)`, and down `(4,15)`
   demonstrate that a long key hold can traverse several coordinates.
6. The live unit position is instead battle slot record `+0xC4/+0xC5`
   (`0x020240C0 + slot*0x1D4`).  Slot 1 remains `(4,4)` during the cursor tests.
   Therefore `runtimePositions` is formation/unit state, not cursor state.
7. `/tmp/battle-cursor-on-naruto.ss9` places the cursor at `(4,4)`.  `SELECT`
   opens the character-detail panel.  `A` followed by one Down moves the cursor
   to `(4,8)` but does not change the unit record.  Confirming there produced
   only two unrelated bytes at `0x02031204..05` (timer-like change) and no unit
   movement.  It must not be reported as a completed tutorial move.

The temporary `/tmp/*.ss9`, screenshots, and EWRAM dumps are reproducible
experimental products rather than repository inputs; the environment-variable
pipeline above is the durable artifact.

## Conclusion and remaining acceptance gate

The strict battle-arrival gate and recoverable experiment pipeline are closed.
The natural save/load gate is **not** closed: the tutorial's unit-action
substate still has to be driven through a genuine move onto the special chest.
Only after the natural hook reports marker `0xA5`, a successful wrapper return,
and a nonzero hit count may the exported 32-KiB `.sav` be checksum-validated.
That `.sav` must then be cold-loaded and `0x08068AF0` must restore a known field.

Important addresses/files for the next experiment:

- cursor: `0x02026A78..79`;
- unit pool: `0x020240C0`, stride `0x1D4`, coordinates `+0xC4/+0xC5`;
- natural-save probe result: `0x0203FF40`;
- natural save wrapper call: `0x08074F2C`;
- stable checkpoint recipe: `play/_scripts/runtime-formation-probe.js`.
