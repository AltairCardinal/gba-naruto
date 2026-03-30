# Chapter Entry Points

## Status

Not yet identified. This document records the investigation state and recommended path forward.

## Known Entry Points

### Dialogue/UI Rendering Path (confirmed)
- `0x080968A0` — runtime-confirmed opening dialogue caller (lr=0x08096633)
- `0x08096176-0x08096212` — shared RAM-state preparation layer for page-level renderer
- `0x0808947C` — high-level renderer block (consumes `0x02002880` state struct)

### WRAM/VRAM Rendering Path (confirmed)
- `0x08066D74` — confirmed WRAM tilemap halfword writer
- `0x08065F50` — confirmed VRAM glyph upload writer
- `0x08065EB8` — glyph expansion function
- `0x08065F84` — glyph→tilemap wrapper
- `0x080894DE` — external caller of glyph expansion (higher-value upstream anchor)

### Visual Resource Tables (identified but not chapter config)
- `0x596D5C`: 312-row × 16-byte tile/map descriptor table
- `0x596FA8`: 4-pointer resource descriptor table
- `0x5A4E14`: visual resource bank (155 rows × 16 bytes)
- `0x461CE8`: dialogue pointer table (305 groups)

### Battle Event Strings
- `0x12F0F8` — `BATTLEFINISH` event label
- `0x12FEA0` — `BATTLESTAT` event label

## Investigation Gaps

1. **Chapter configuration table**: Not found
2. **Battle unit placement table**: Not found  
3. **Enemy/unit stats table**: Not found
4. **Map tilemap data**: Not located
5. **Event/script engine entry points**: Not identified

## Recommended Path Forward

### Immediate (requires mGBA)
1. Run `mgba_newgame_walk.lua` through the first battle
2. Set a range watchpoint on `0x0200C000-0x0200E000` (game state) during battle start
3. Capture PC of the first code that writes battle configuration to RAM
4. Use that PC to find the chapter config reader in the ROM

### Medium-term (requires static analysis + runtime validation)
1. Use the confirmed dialogue pointer table (0x461CE8) as a template to find similar pointer tables nearby
2. Search for tables that reference both map data and dialogue text
3. Look for tables that have a consistent entry count matching typical chapter count (8-20 entries)

### Data-driven approach
1. Look for data structures that combine unit placement data (x, y coordinates) with unit type IDs
2. The 0x4BF000 area showed unit-like patterns but structure is unclear
3. Search for u16 values in range 1-50 repeated 10+ times consecutively — these could be chapter or unit ID sequences

## Reference: What a Chapter Entry Point Looks Like

A typical chapter configuration struct for a GBA tactical RPG:

```c
struct ChapterEntry {
    u16 id;           // 1-indexed chapter number
    u16 map_tile_id;  // Index into map tile descriptor table (e.g., 0x596D5C)
    u32 map_data;     // Pointer to tilemap data
    u32 enemy_table;  // Pointer to enemy unit array
    u32 ally_table;  // Pointer to allied unit array
    u32 script;      // Pointer to event/script data
    u16 objective;    // Text index for objective
    u16 turns;        // Turn limit (0 = no limit)
    u8 bgm;           // Music track index
    u8 padding;
};
```

Entry size would be 28-32 bytes. A 20-chapter game would have a ~600 byte table.
