# Dialogue Font Table Discovery (2026-07-03)

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
| 3      | 1 byte  | padding | Always 0x00 |
| 4-7    | 4 bytes | tile_ptr | Tile data base address (32-bit LE) |

### Tile Data Calculation

For SJIS byte `S` (16-bit):
1. Find entry where `lower <= S < lower + range_size`
2. Compute: `tile_addr = tile_ptr + (S - entry.lower) * 32`
3. Tile data is 32 bytes at that GBA cart address (= 8x8 4bpp pixel graphics)

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

### Second Font Table (8-bit byte 2 lookup)

- **Address**: GBA 0x0853D73C
- **Function**: 0x0806606C (lui r4, [pc, #0x14])
- **Used for**: byte 2 of SJIS pair (8-bit value)
- **2 entries**: lower=0x20 (ASCII range), lower=0xA0 (high byte range)

## Tile Graphics Mismatch (CRITICAL FINDING)

The breakthrough's existing 20-char mapping (`sjis-to-tile-mapping.json`) was
derived from group0 dialogue at 0x459414. Those SJIS bytes (e.g., 0x88CF, 0x8FC2)
are NOT in the new font table at 0x53D644. This means:

1. **Two separate font systems** exist in the ROM:
   - **Group0 dialogue** (existing 20-char mapping) - uses different font system
   - **Chapter 1 intro dialogue** (records at 0x8DF0+) - uses the new font table at 0x53D644

2. **The dev ROM tile graphics are Japanese kanji/hiragana**:
   - Tile graphics at computed addresses show Japanese characters (ぐ, し, り, ち, etc.)
   - This is BEFORE 熊组汉化 tile replacement
   - The game loads these Japanese tiles, then REPLACES them with Chinese tiles at runtime
   - Replacement mechanism likely uses DMA or CPU writes from compressed tile data elsewhere in ROM

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
   → reads tile data at tile_ptr + (sjis - lower) * 32
5. Tile graphics copied to VRAM 0x6002000+
6. Tilemap entries in WRAM 0x0200A900 (with tile indices 304-309 etc.)
7. Rendered on screen via BG3 screen block 3 (0x06001800)
```

## Files Created

- `sequel/content/text/sjis-to-tile-addr-20260703.json` (50KB)
  - Complete font table
  - 517 SJIS byte → tile_addr mappings (from chapter 1 intro records)
  - Frequency counts (count = occurrences in 30 records)

## Next Steps (Beyond This Session)

The breakthrough's existing 20-char mapping was for **group0 dialogue font**,
not chapter 1 intro. To extend it, need to:

1. **Find group0 dialogue font table** - probably different location
2. **Find 熊组汉化 tile replacement data** - where the Chinese tile graphics come from
3. **Decompress/replace runtime tile data** - to map tile_idx → Chinese char

For chapter 1 intro dialogue, the 517 SJIS→tile_addr mappings now provide a clear
path forward - just need to identify what Chinese char each tile graphics shows.
