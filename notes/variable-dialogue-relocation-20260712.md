# Variable-length dialogue relocation (2026-07-12)

## Previous framework defects

The repository advertised variable dialogue but the active manifest used only
fixed-slot `dialogue` patches. The unused allocator had no ROM input, no upper
bound, no proof that destination bytes were free, and shared
`0x5E0000..0x5FFFFF` with DB audit records. Two importers also disagreed about
whether `text_rom_offset` was a file offset or an already mapped pointer.

## Corrected partition and algorithm

The final 128 KiB FF area now has exclusive ownership:

- `0x5E0000..0x5EFFFF`: DB audit rows, at most 1024×64 bytes
- `0x5F0000..0x5F7FFF`: variable dialogue, 32 KiB
- `0x5F8000..0x5FFFFF`: semantic chapter scripts, 32 KiB

`tools/import_dialogue_var.py` now loads the immutable base ROM and validates:

1. free-space bounds are inside ROM and the complete dialogue partition is `0xFF`;
2. content ID exists and encodes in the declared encoding without embedded NUL;
3. short content remains in place with exact base bytes and zero padding;
4. long content has a unique, in-ROM pointer-table slot;
5. the base pointer stored in that slot exactly equals `0x08000000 +
   text_rom_offset`;
6. each allocation is 4-byte aligned, NUL terminated and fits before exclusive
   end `0x600000`;
7. emitted write preconditions are the actual base-ROM FF bytes.

Editor DB overrides pass through the same allocator. The manifest now has one
active `dialogue_var` entry covering all content; the five duplicate fixed
manifest entries are disabled, preventing overlapping patch strategies.

## Real relocation proof

`group0.label2` intentionally changes a six-byte original slot to
`第二話・新たなる任務` (20 encoded bytes plus NUL):

- original pointer slot: file `0x461CF0`
- base pointer: `0x08459470` (`70 94 45 08`)
- allocated text: file `0x5F0000`
- new pointer: `0x085F0000` (`00 00 5F 08`)
- text bytes:
  `91e693f198628145905682bd82c882e9944396b100`

`python3 tools/build_mod.py` produced SHA-1
`c850a960b95dfc80eeb692e4576bd0d7f7af0a61`. Direct output-ROM verification
read pointer `0x085F0000` from `0x461CF0`, followed it, found the exact encoded
text and NUL terminator. Patch safety classified both allocation and redirect
as unique game-effective writes.

Regression coverage: `tests/test_import_dialogue_var.py` covers in-place,
relocation, pointer mismatch, non-FF partition and capacity exhaustion.

## Emulator E2E

The exact built ROM containing the redirect completed the deterministic WASM
title → new game → first battle route. Step 286 correctly remained rejected;
step 306 passed all strict factors:

- `outcome=matched`, reason `strict-battle-arrival-after-settle`
- unique complete formation group 40 / variant 0
- battle ID 40
- map runtime `[36,44,9,22]`, internally consistent
- visible screen classifier `battle-map`

Artifacts:

- `/private/tmp/variable-dialogue-e2e.json`, SHA-256
  `4c33f1bd6294760d6b14e8ee4e96237849576744e2051da91b0d14b66838ec3b`
- `/private/tmp/variable-dialogue-e2e.png`, SHA-256
  `42d137c191ace693306a947f0d5f23e0959be53028e05124852a9095511907dc`

This closes allocator → pointer redirect → ROM boot/text progression → battle
state as an end-to-end no-crash path. It does not assert that this particular
chapter label was visible during the automated route; pointer-follow and bytes
were verified directly in the output ROM.
