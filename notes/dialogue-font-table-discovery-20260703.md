# Dialogue Font Table Discovery (2026-07-03; corrected 2026-07-29)

> **Correction:** visual QA and the Thumb consumers at `0x08065EB8` and
> `0x080660A4` disproved the original “8×8 4bpp tile” interpretation. The
> pointers below address packed 2bpp source records. The SJIS branch expands a
> 32-byte, 16×8 source into two horizontal 8×8 4bpp tiles; the byte branch
> expands a 16-byte, 8×8 source into one 8×8 4bpp tile. The address formula
> remains valid.

## THE KEY FINDING

The breakthrough in dialogue mapping research: **located the game's font table** in ROM.

### Font Table Location

- **Address**: GBA 0x0853D644 = ROM file 0x53D644
- **Searched by**: function at 0x08065E80 (`search_font_table`)
- **Callers**: 0x08065EB8 (glyph expansion), 0x08065F84 (outer caller)
- **Entry count**: 26 entries (each 8 bytes)

### Entry Layout (8 bytes each)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0-1    | 2 bytes | lower | SJIS lower bound (16-bit LE) |
| 2      | 1 byte  | range_size | Number of SJIS codes in this group |
| 3      | 1 byte  | aux | `0x00` for entries 0-24; `0x04` for entry 25 |
| 4-7    | 4 bytes | source_ptr | Packed 2bpp source base address (32-bit LE) |

### Tile Data Calculation

For SJIS byte `S` (16-bit):
1. Find entry where `lower <= S < lower + range_size`
2. Compute: `source_addr = source_ptr + (S - entry.lower) * 32`
3. Read 32 bytes as a 16×8 packed-2bpp record: the first 16 bytes are the
   left 8×8 half and the next 16 bytes are the right 8×8 half.
4. `0x08065EB8` expands each 2-bit source pixel into a 4bpp index:
   `source_2bpp + (((arg1 & 1) + 2) << 2)`.

### Font Table Entries

| Idx | Lower SJIS | Range | Tile Data Base (GBA) | Covers |
|-----|-----------|-------|---------------------|--------|
| 0   | 0x8140    | 109   | 0x0809D954          | 0x8140-0x81AC |
| 1   | 0x8240    | 178   | 0x0809E954          | 0x8240-0x82F2 |
| 2   | 0x8340    | 151   | 0x080A0154          | 0x8340-0x83D7 |
| 3   | 0x8740    | 32    | 0x080A1554          | 0x8740-0x8760 |
| 4   | 0x889F    | 94    | 0x080A2154          | 0x889F-0x88FD |
| 5-19 | 0x8940..0x9740 | 189 each | various | Each entry 0x100 wide |
| 20  | 0x9840    | 51    | 0x080B9554          | 0x9840-0x9872 |
| 21  | 0x9873    | 138   | 0x085AE800          | 0x9873-0x98FD |
| 22-25 | ... | ... | ... | ... |

### Second Font Table (single-byte lookup)

- **Address**: GBA 0x0853D73C
- **Function**: 0x0806606C (lui r4, [pc, #0x14])
- **Used for**: the renderer's single-byte branch
- **2 entries**: lower=0x20 (ASCII range), lower=0xA0 (high byte range)
- **Source record**: 16-byte packed 2bpp, expanded to one 8×8 4bpp tile

## Corrected scope of the earlier group0 hypothesis

The earlier note claimed that group0 examples `0x88CF` and `0x8FC2` were absent
from this table and therefore proved a second font system. That claim is false:
`0x88CF` is in entry 4 (`0x889F..0x88FC`) and `0x8FC2` is in entry 11
(`0x8F40..0x8FFC`). The table can resolve both codes.

The ROM sources decoded here visually contain original Japanese glyphs. This
alone does not prove how the localized runtime obtains Chinese glyphs, nor does
it prove that group0 uses a separate table. Those questions require a runtime
consumer/write trace and remain open.

## Renderer Chain (VERIFIED)

```
1. SJIS bytes in records (ROM 0x8D99+) 
   → loaded to EWRAM at runtime
2. Renderer function 0x0808942C (THUMB)
   - r0 = dialogue data pointer (r6 = r0)
   - r6 = 0x0201BD48 (literal pool at 0x0808955C)
3. 0x08065E80 search_font_table(sjis_byte) 
   → returns entry index OR 0xff
4. 0x08065EB8 glyph_expansion 
   → reads packed source at source_ptr + (sjis - lower) * 32
   → expands it into two horizontal 8×8 4bpp tiles
5. Tile graphics copied to VRAM 0x6002000+
6. Tilemap entries in WRAM 0x0200A900 (with tile indices 304-309 etc.)
7. Rendered on screen via BG3 screen block 3 (0x06001800)
```

## Files Created

- `sequel/content/text/sjis-to-tile-addr-20260703.json`
  - Complete font table
  - 517 SJIS code → packed-2bpp source-address mappings (from chapter 1 intro
    records)
  - Frequency counts (count = occurrences in 30 records)

## Next Steps (Beyond This Session)

1. Trace group0 rendering to determine whether it reuses `0x53D644` or a
   different source; do not assume a second font table.
2. Trace the localized runtime's glyph-source reads and VRAM writes to locate
   any Chinese replacement data.
3. Preserve source code, VRAM destination, palette, and frame evidence before
   assigning tile indices to Chinese characters.

For chapter 1 intro dialogue, the 517 SJIS→source-address mappings provide the
original Japanese glyph sources. Runtime Chinese replacement, group0 font data,
runtime RGB palettes, and character naming remain separate unresolved scopes.
