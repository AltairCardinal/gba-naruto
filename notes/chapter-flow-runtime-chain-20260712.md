# Chapter-flow runtime consumer chain (2026-07-12)

## Result

The real scenario/chapter flow tables are 56-entry script-pointer tables at
file `0x60C74` (primary) and `0x60D54` (alternate), not the five late-ROM
resource-descriptor slices formerly labeled `story*`.

## Static chain

`0x0808F544` receives a scenario ID and indexes it as `id*4`:

- when chapter state `0x020311D4 + 0x18` is zero, base `0x08060C74`;
- otherwise, base `0x08060D54`.

Entry 0 is null in both tables; entries 1..55 are ROM script pointers. The
selected script is passed to interpreter `0x080977B8`. Within the interpreter,
the handler at `0x08097C78` consumes four-byte command `0x1A`:

1. `r7[0]` is opcode `0x1A`;
2. `r7[1]` is written to chapter state `+0x16` (`0x020311EA`);
3. `0x0808CC80` derives state `+0x14` from that ID;
4. later `0x0808F618` copies `+0x16` to battle control `0x02026805`.

## Live first-battle evidence

`tools/build_chapter_script_probe.py` replaces only the two instructions at
`0x08097C78..7B` with a BL to a zero-filled diagnostic stub. The stub preserves
the original write and records the live `r7` pointer and command bytes at
`0x0203FFB0`.

The standard WASM route, using the strict battle-arrival gate, recorded:

- script cursor `r7 = 0x08031070`;
- bytes `1A 28 02 00`;
- chapter/battle operand `0x28` (40);
- hit count 1;
- final `0x02026805 = 40`;
- strict battle map arrival with map runtime `[36,44,9,22]` and formation
  group 40 / variant 0.

Pointer backtracking shows `0x08031070` is inside the script starting at
`0x08031020`, and primary table entry 39 at file `0x60D10` points to that
script. The resulting proven chain is:

```
scenario 39
  -> 0x08060C74[39] = 0x08031020
  -> opcode 0x1A at 0x08031070, operand 40
  -> 0x020311EA = 40
  -> 0x0808F618
  -> 0x02026805 = 40
```

Artifacts:

- probe ROM SHA-256 `3d9ebca68ace8a52a9a9d48edb8f71883014b75b003ca21ed22f9841d7cbbae4`;
- result SHA-256 `51ed2851bdcd33a82c0afebd27e192a10bb0405528a69d7c169fcd8a6d902cb2`;
- screenshot SHA-256 `e4b6bb23b7c4b76f1d2ab83c4e749737029fd6308aad1d9215f31b45835bf8b5`.

## Repository changes

- `tools/extract_chapter_flow_tables.py` extracts both 56-entry tables.
- `story/bank.json` now represents the primary table and is runtime verified.
- `story-b/bank.json` represents the alternate table and is code verified.
- `story-c`, `story-d`, and `story-e` remain disproved tombstones for their
  former false identities.

Semantic script editing is still disabled. Lossless pointer writeback requires
new mirrors keyed by exact table/index/base pointer; old `rom_story_b..e`
mirrors must not be reused because they describe the revoked addresses.
