# Save descriptor layout and WASM export correction (2026-07-12)

## Corrected table semantics

The second u32 in each `0x53D848` descriptor is not an independent SRAM
offset. `0x08068684` reaches descriptor `i` by starting at SRAM base and adding
`previous_field + 0x14` for every preceding descriptor. It then uses the
selected field as the payload length and appends a NOT-sum checksum byte.

The ten lengths are:

`4732, 4732, 20, 4732, 20, 8, 24, 6084, 1404, 512`.

The save wrapper uses descriptors 3..9, whose cumulative SRAM starts are:

`0x2548, 0x37D8, 0x3800, 0x381C, 0x3848, 0x5020, 0x55B0`.

This supersedes the former fixed 19+1-byte records at `field+0x14` theory and
the old offsets `0x001C, 0x0028, ...`.

## Runtime diagnostics

`tools/build_save_group_runtime_probe.py` called groups 3..9 separately during
first-battle initialization. All seven handler calls returned 1. A complete
wrapper probe returned 0 (`saveProbeHex=a500`), confirming that natural
battle-completion preparation is still absent at that point.

The browser's `_readGbaByte(0x0E......)` result was rejected: it exposed
misleading mapped bytes. `tools/audit_wasm_savedata_api.js` found the supported
`getSave()` method, whose implementation reads `Module.saveName` from the
Emscripten filesystem. The runtime probe now uses this exported 32768-byte
`.sav` and can persist it with `PROBE_SAVE_DUMP`.

The group and wrapper diagnostics changed all seven cumulative regions from
erased bytes and inserted the game signature at their starts. However, the
out-of-context exported records did not pass checksum validation, so this is
not accepted as a natural save closure. The bank remains `code_verified`.

Artifacts from the wrapper run:

- ROM SHA-256 `2eaceb1020b1063f72851adc0482adf18629b719a27135ffcb8d7ded319a592d`;
- result SHA-256 `ebdba738d087ab927b903fcfd94082310ae4000a752c3a0b39be09c1123ce8a8`;
- `.sav` SHA-256 `1bdde329cc6a3bfa9a85b17e2db669445ba6c0f862b035bf6ad5ef7db7f2dd8c`;
- screenshot SHA-256 `42d137c191ace693306a947f0d5f23e0959be53028e05124852a9095511907dc`.

## Next acceptance gate

Reach the natural `0x08074F2C` battle-completion caller, export `.sav`, and
require wrapper return 1 plus valid checksums for every group 3..9 record.
Then cold-start/load that `.sav` and prove `0x08068AF0` restores at least one
known runtime field.

## 2026-07-12 natural-caller and postbattle experiments

The save branch is a state case inside postbattle/result controller
`0x080732B4`: dispatch state `0xF400` calls `0x08074EE6`, which requires
`0x0200A882==1` and `0x0200A880==0`, prepares formation state, then reaches the
complete wrapper call at `0x08074F2C`.

`tools/build_natural_save_runtime_probe.py` hooks only that final BL. A full
title→first-battle strict route reached battle at step 306 but recorded zero
hits, proving battle entry does not naturally save.

Controlled experiments subsequently tested the official controller rather
than calling the wrapper directly: public postbattle wrapper `0x08068DE4`,
forced dispatch `0x1000→0xF400`, the three real callers of `0x080732B4`, the
two UI gate bytes, and finally a hit marker immediately around
`0x080735C2→0x08074EE6`. Generated ROMs were disassembled and an accidental
stub overlap was detected and corrected before the final run.

Even the final non-overlapping probe did not reach the case marker or natural
wrapper observer: without an actual victory transition, the result controller
blocks in earlier synchronous UI/resource stages. This is binding negative
evidence. Forcing a state number cannot substitute for completing the battle
state machine.

Durable diagnostic builders are `tools/build_postbattle_save_probe.py`,
`tools/build_postbattle_natural_save_probe.py`, and
`tools/build_forced_save_case_probe.py`. They must not be cited as natural-save
proof. The remaining valid route is an automated real battle victory or a
genuine post-victory savestate.

The SRAM verifier now accepts the real 32 KiB `getSave()` container as well as
64 KiB dumps, provided the file covers the descriptor span. Its previous
64-KiB-only requirement contradicted the observed WASM API; checksum validation
remains mandatory.
