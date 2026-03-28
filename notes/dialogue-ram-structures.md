# Dialogue RAM Structures

## Scope

This note records the first direct inspection of two RAM regions that showed up in the Phase 2 dialogue renderer analysis:

- `0x02002880`
- `0x02022E30`

Reference artifacts:

- `notes/region-02002880-2160.txt`
- `notes/region-02002E30-2160.txt`
- `notes/diff-02002880-2160-2700.txt`
- `notes/diff-02002E30-2160-2700.txt`
- `notes/dialogue-watch-sb-struct.md`
- `notes/dialogue-watch-record-bank.md`
- `notes/disasm-080961D6.txt`
- `notes/disasm-0809C0D8.txt`

Source snapshots:

- `notes/dialogue-2160-wram.bin`
- `notes/dialogue-2340-wram.bin`
- `notes/dialogue-2520-wram.bin`
- `notes/dialogue-2700-wram.bin`

## 1. `0x02002880`

Observed size inspected:

- `0x140` bytes

Key observations:

- frames `2160`, `2340`, and `2520` are identical at the head of this region
- frame `2700` differs heavily across most of the same range
- the content is dominated by `16-bit` values that look like tile/palette-style entries rather than text bytes
- the back half of the region contains many byte values in the printable ASCII range, but the surrounding halfword patterns and frame-to-frame behavior still look more like rendered state or compressed lookup data than direct script text

Interpretation:

- `0x02002880` behaves like a live renderer/UI work structure, not a stable text source buffer
- this is consistent with the high-level renderer using `sb = 0x02002880`

Known offsets already implicated by code:

- `+0x16`
- `+0x82`
- `+0x96`

Current reading:

- `+0x16` is likely the start of repeated per-slot state
- `+0x82` and `+0x96` are likely auxiliary selector/resource tables used during entry rendering

## 2. `0x02022E30`

Observed size inspected:

- `0x240` bytes

Key observations:

- frames `2160`, `2340`, and `2520` are identical at the head of this region
- frame `2700` differs across nearly the entire inspected range
- byte values often fall in the printable ASCII range, but they do not decode into credible dialogue text
- the region has strong repeated-pattern structure and wide coherent changes, which is more consistent with RAM-side records or tile/glyph-related state than with encoded script lines

Interpretation:

- this region is unlikely to be a direct script-text store
- it is more likely a bank of RAM records consulted by the high-level dialogue/UI renderer
- this matches the nearby helper logic:
  - `0x080886E8` reads a slot selector and returns a byte at record offset `+4`
  - `0x08088718` reads a slot selector and returns a pointer to record data starting at `+4`

## 3. Stability Across Dialogue Frames

Both regions show the same pattern:

- stable across frames `2160`, `2340`, `2520`
- substantially different by frame `2700`

This suggests:

- the opening dialogue keeps using the same active page/speaker/render state for several sampled frames
- the state block is then refreshed or replaced on the next dialogue advance

That is useful because it means these RAM blocks can be treated as page-level renderer state, not just per-frame noise.

## Practical Conclusion

The current best model is:

- `0x02002880` is a live dialogue/UI work structure consumed by the high-level renderer
- `0x02022E30` is a related RAM-side record bank used to resolve slot/entity data for rendering
- neither region currently looks like the true upstream text source

## 4. Runtime write-path correlation

Both regions were then tracked with watchpoints during the opening dialogue flow.

Confirmed results:

- `0x02002880-0x020029C0`
  - summary: `notes/dialogue-watch-sb-struct.md`
- `0x02002E30-0x02003070`
  - summary: `notes/dialogue-watch-record-bank.md`

Shared runtime properties:

- first observed write frame: `1590`
- reported watchpoint PC: `0x0809C0F0`
- shared LR: `0x080961D7`
- observed width: `1-byte` writes

Important caution:

- `0x0809C0F0` sits inside a ROM thunk area that contains several BIOS `svc` wrappers
- that makes it unsafe to treat `0x0809C0F0` itself as the real business-logic writer
- the more useful anchor is the shared caller region around `0x080961D6`

Current interpretation:

- both RAM regions are refreshed by the same upstream preparation path
- the shared caller strongly suggests a single state-building function prepares both the dialogue work struct and the related record bank before the later high-level renderer consumes them

Practical next target:

- `0x08096176-0x08096212`

That range is currently the strongest candidate for the RAM-state preparation layer that sits above the renderer and below the true script/text source.

So Phase 2 should continue by answering:

1. who populates `0x02002880`
2. what the `0x02022E30` records represent
3. which earlier system translates script data into these RAM-side structures
