# Alternate chapter table runtime probe (2026-07-12)

## Objective and method

Runtime-close table `0x60D54` without changing the scenario ID or interpreter.
`tools/build_alternate_chapter_runtime_probe.py` changes the `beq` at
`0x0808F5A4` to a Thumb NOP, forcing the existing selector to fall through the
alternate-table path. It also reuses the opcode tracer at `0x08097C78`.
Only the two-byte selector branch, four-byte hook, and checked zero-filled
diagnostic stub may differ from the immutable base ROM.

That first implementation is now superseded. Static decoding proved scenario
39's alternate script is `0x08031281..0x0803142E` and contains no opcode
`0x1A`, so the old hook could never satisfy “hit inside the target script”. The
corrected probe captures `r4`/`r0` at `0x0808F5CC` and hooks generic interpreter
dispatch at `0x080977D8`.

## Attempts and result

Probe ROM SHA-256:
`c98e2d2c02e4e0235e14e584a5a423a20a079db897b85fa09adea7ef0a93e6a4`.

Corrected probe ROM SHA-256:
`d125d8965a2c4c5b25a177d4ae0b551350c976f42c455f7ebd0eba188576dd4c`.

Two automated routes were attempted:

1. 250 dialogue confirms ended in the pre-selector Kakashi conversation.
   Result SHA-256 `33bb3160704fe4bcda76dccf9f3642e54ebf442e439a476a73177b5cc4943233`.
2. 700 faster confirms reached the character page, but the fixed tail sequence
   did not exit it. Result SHA-256
   `d3ae1c436b4f0c1516a2cf613b0bdcae279db380e0415f3edcd6621d01026a51`;
   screenshot SHA-256
   `4897c8f158e6e7c1d5280ad44c9812438eed8166c4e998a93b95bf5912a5e8d0`.

Both runs had opcode hit count 0, battle ID 0, empty unit memory, and empty map
runtime. Therefore neither executed `0x0808F544`, and neither is evidence for
or against alternate table consumption. The visual classifier called these
screens `battle-map`, but the strict memory gate correctly rejected them.

## Next acceptance gate

Resume at or reproducibly reach the character page, exit with a verified B
transition, select prebattle “start mission”, then require all of:

- tracer hit count > 0;
- captured script pointer equals the pointer in `0x60D54[scenario_id]`;
- captured opcode bytes belong to that script;
- resulting chapter/battle state is nonzero or the alternate script terminates
  through another explicitly decoded opcode.

Until that gate passes, `story-b` remains `code_verified`.

## Gate closure (supersedes the pending status above)

The script SHA-256 is
`42b97435ebd486da839b23976059f8d66c2e3f8765b4493ef4baca23d0cdb976`.
Its opcode distribution is `1B×1, 02×5, 08×8, 01×8, 04×2, 00×1`. The final
`00` at `0x0803142E` dispatches to `0x08097916` and exits through `0x08097E34`
at zero interpreter call depth. The script does not write state `+0x18/+0x16`,
so no battle state is the intended result.

Starting from `alternate-mission-selection.ss9`, keyboard input
`A, Down, A, A×7` at 1.4-second spacing stopped at input step 10 with:

- selector hit count `1`, scenario `39`, selected pointer `0x08031281`;
- dispatch hit count `25`;
- final cursor `0x0803142E`, live bytes `00001b04`, equal to ROM;
- all eight evidence checks true and reason `alternate-script-terminated`.

Full result SHA-256:
`2739ff82adac85075d3b9f5e020c7391e64bbdbd92f3a613adc9699d86a9916f`.
Screenshot SHA-256:
`25e0fcc3f406b0cc7e84293a8c07ac5dd1008b85b107480d8f4b345b701001fa`.
Compact evidence is stored at
`artifacts/runtime-checkpoints/alternate-story-b-runtime-evidence.json`.
This closes all four gates and upgrades `story-b` to `runtime_verified`.

## Checkpoint replay correction

Follow-up runs proved that keyboard events advance a freshly loaded checkpoint,
whereas direct API events may not. Some later exports also replayed with every
confirm ignored, consistent with a state captured across browser keydown/keyup.
The runtime driver now explicitly unpresses every logical GBA button after
`loadState()`. This is a probe-infrastructure correction, not chapter evidence;
the alternate bank remains code-verified until the acceptance gate above.

A deeper replay check found the primary defect: state export selected the first
directory entry ending in `.ss9`, so an older same-slot file could be copied
while the screenshot represented the new state. The exporter now deletes all
same-slot candidates before `saveState(9)` and requires exactly one fresh file.
Checkpoints produced before this correction are navigation aids only and are
not accepted as durable runtime evidence.

The corrected exporter then produced and replayed the same mission-selection
screen successfully:

- checkpoint SHA-256
  `492ae012702be7488984640da968f3343670f152d189fa3628fee24b056a0308`;
- capture SHA-256
  `03210ca14a4f7284d7e551e2d1dbc58249013abaa003b4e2a099ee6f24193163`;
- independent zero-input replay capture SHA-256
  `32138d89b8873a444e4332950ddae409e73fb34be3adc3dadb5d5b9607bba4f7`.

The replay screen is the `木叶里 / 对战` mission-selection view. Keyboard A
continues forward into Kakashi dialogue; B returns to earlier dialogue. This
replaces the earlier incorrect assumption that the screen was a character page.

The subsequent 260-input replay proved another driver defect: Puppeteer was
given DOM-style codes such as the literal string `KeyZ`, while the game page
listens for browser key values such as `z`. The unchanged screenshot, zero hook
hits, and unchanged WRAM make this a rejected input run. Keyboard mode now maps
GBA input codes explicitly (`KeyZ→z`, `KeyX→x`, arrows, Shift, `a`, and `s`).

## Valid keyboard navigation after the corrections

With the browser-key mapping fixed, one A deterministically changed the
`木叶里 / 对战` mission-selection screen into Kakashi dialogue. The earlier
260-input no-op run is rejected. The following UI facts are now reproducible:

- plain A at Kakashi's prompt is ignored because the state expects a directional
  choice;
- repeated Down+A eventually loops to earlier Naruto/Kakashi dialogue;
- repeated Up+A advances through the alternate choice and reaches the equipment
  page;
- one B from equipment reaches the character-information submenu, not the
  Konoha top-level menu;
- Up+A there opens the character-information overview.

`PROBE_TAIL_REPEAT` now repeats a verified tail key sequence without manually
duplicating environment input. The old zero-hit conclusion is historical and
is superseded by the generic-dispatch closure above.
