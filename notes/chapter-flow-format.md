# Chapter Flow Format

## Status

**Not yet reverse-engineered.** This document records what has been investigated and what the next steps are.

## Investigation Summary

### What has been tried

1. **ASCII string search**: Found `BATTLEFINISH` (0x12F0F8) and `BATTLESTAT` (0x12FEA0) — these are event/state labels used by the scripting engine, not chapter configuration data.

2. **Chapter ID sequence search**: Searched for u16 sequences like (1, 2, 3, 4, ...) at regular intervals in 0x0C0000-0x0E0000. Found no matches.

3. **Battle unit config search**: Searched for patterns like (count, type, x, y, team, hp) in battle-relevant areas. Found candidate data at 0x4BF000 with unit-like coordinates (x≤31, y≤23), but structure is unclear.

4. **Similar-tables analysis**: The 38 late-ROM table candidates found by `find_similar_tables.py` are mostly visual/resource descriptor tables:
   - `0x596D5C`: 312 rows × 16 bytes — tile/map descriptor table (visual)
   - `0x596FA8`: visual resource descriptor (confirmed)
   - `0x5A4E14`: visual resource bank (confirmed)
   - `0x5A2B08`: compressed binary blocks (visual/map)
   - `0x599280`, `0x5995AC`: compressed binary blocks

5. **Japanese keyword search**: "戦" (battle) found only in the text block at 0x00076C. The Chinese-patched ROM has replaced most Japanese text.

6. **Unit placement pattern search**: Found no clear battle unit placement table with consistent (type, x, y, team, hp) 4-byte records.

### What the chapter configuration likely contains

Based on typical GBA tactical RPG structure:

```
struct ChapterConfig {
    u16 chapter_id;       // Chapter number
    u16 map_id;           // Map tilemap index
    u32 map_ptr;          // Pointer to map tile data
    u32 enemy_unit_table; // Pointer to enemy unit array
    u32 ally_unit_table;  // Pointer to allied unit array
    u32 objective_text;   // Pointer to objective string
    u32 script;           // Pointer to chapter event script
    u16 turn_limit;       // Turn limit (if any)
    u16 win_condition;     // Win condition type
    u16 lose_condition;   // Lose condition type
    u8 terrain_id;        // Terrain/map variant
    u8 music_track;       // Battle BGM
};
// Entry size: likely 32-40 bytes
```

### Most promising next steps

1. **Runtime analysis with mGBA**: Set a watchpoint on `0x0200A900` (WRAM dialogue buffer) and `0x0200B000-0x0200C000` (game state area) during chapter transitions. This would reveal which ROM addresses are accessed.

2. **Battle start trace**: Navigate to the first battle in the game using `mgba_newgame_walk.lua` and capture memory access during the battle initialization. The PC at battle start would reveal the chapter configuration reader.

3. **Save data analysis**: The game's save data ( SRAM at 0x0E000000 in ARM space) contains chapter progress. Reading a save file from mid-game might reveal chapter IDs and map pointers.

4. **Code reference search**: Search the code section (0x08000000-0x08300000) for references to `0x596D5C` or similar tables, then trace backward to find which code reads from the chapter config table.

### Deliverable status

- `notes/chapter-flow-format.md` — this file
- `notes/chapter-entry-points.md` — see below
- Minimum flow change experiment — **pending** (requires runtime analysis)
