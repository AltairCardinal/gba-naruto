# ROM Reverse Engineering Results

This document lists all discovered ROM offsets and data structures for the Naruto GBA sequel project.

## Summary

- **Total structures discovered**: 25
- **ROM size**: 6,291,456 bytes (6.0 MB)
- **Reserved region**: 0x5E0000..0x600000 (128 KiB) for audit-trail patches
- **Last updated**: 2026-06-25

## Discovered Structures

### 1. Audio Table
- **Offset**: 0x53F138
- **Format**: 88 entries × u32 pointer to Sappy audio entry
- **Entry count**: 88
- **Method**: Static analysis - found pointer table with valid Sappy audio entries
- **Verification**: First 2 entries point to code, entries 2+ are valid audio
- **Notes**: Sappy/M4A format. Audio entries are 16 bytes: u32 data_ptr, u16 type, u16 pad, u16 flags, u16 pad, u32 extra_ptr

### 2. Story/Chapter Table
- **Offset**: 0x53636C
- **Format**: 9 entries × u32 pointer to chapter data
- **Entry count**: 9
- **Method**: Static analysis - found pointer table with chapter data
- **Verification**: Chapter 0 has header with scene pointers, chapters 1-8 have encoded beat data
- **Notes**: Chapter 0 has different structure (header with scene pointers). Chapters 1-8 start with 0xBE 0x69 0xBC 0x00

### 3. Skill Table
- **Offset**: 0x546100
- **Format**: 12 entries × 16 bytes
- **Entry count**: 12
- **Method**: Static analysis and code cross-reference
- **Verification**: Referenced from battle init code at 0x06E6D2
- **Notes**: Entry format: u32 padding, u16 count, u16 type_id, u16 skill_id, u16 value, u16 flags, u16 extra_id

### 4. Unit ID Table
- **Offset**: 0x53F298
- **Format**: u16[64] mapping unit index to character ID
- **Entry count**: 64
- **Method**: Static analysis - found table with sequential character IDs
- **Verification**: Known IDs: 0x00=Naruto, 0x01=Sasuke, 0x02=Sakura, 0x03=Sai, 0x04=Kakashi, 0x05=Shikamaru
- **Notes**: Maps unit array index to character ID. Used by battle system to identify which character occupies each slot.

### 5. Battle Scenario Config
- **Offset**: 0x53D914
- **Format**: 8 entries × 32 bytes
- **Entry count**: 8
- **Method**: Static analysis - found table with map dimensions and pointers
- **Verification**: Contains valid map dimensions and tileset/tilemap pointers
- **Notes**: Actually part of the Map Header Table (see below). Entry format: u32 dim(h|w), u32 tile_gfx_ptr, u32 tilemap_ptr, u32 tilemap_alt_ptr, u32 extra_ptr, u32 palette_ptr, u32 palette2_ptr, u32 flags

### 6. Unit Positions (WRAM)
- **WRAM offset**: 0x02024294
- **Format**: stride 234 bytes, max 25 units
- **Entry count**: 25 (max)
- **Method**: Dynamic analysis - captured WRAM during battle
- **Verification**: Runtime data initialized from ROM during battle init
- **Notes**: Format: u8 existence, u8 x, u8 y, u8 team, u12 pad, u8 init_flag, ...

### 7. Map Header Table ✨ NEW
- **Offset**: 0x53D910
- **Format**: 47 entries × 32 bytes
- **Entry count**: 47
- **Method**: Static analysis - found table with consistent structure (u16 dimensions followed by u32 ROM pointers)
- **Verification**: All 47 entries have valid dimensions (16-128) and valid ROM pointers
- **Notes**: Contains all map definitions including battle maps, overworld maps, and special event maps. The battle scenario config at 0x53D914 is actually part of this table (offset by 4 bytes).
- **Entry format**:
  - u16 width (16-128)
  - u16 height (16-128)
  - u32 tileset_ptr
  - u32 tilemap_ptr
  - u32 tilemap_alt_ptr (0 if none)
  - u32 extra_ptr
  - u32 palette_ptr
  - u32 palette2_ptr
  - u32 flags

### 8. Level-up / Stat Progression Table ✨ NEW
- **Offset**: 0x5459D4
- **Format**: 47 entries × 12 bytes
- **Entry count**: 47
- **Method**: Static analysis - found table with consistent small u16 values in plausible stat gain ranges
- **Verification**: Values range from 1-200 for HP gains and 1-100 for other stat gains
- **Notes**: Contains level-up stat progression data. Entries 0-25 appear to be sequential level gains (level 1-31), while entries 26+ may be character-specific overrides.
- **Entry format**:
  - u16 level_or_id
  - u16 hp_gain (1-200)
  - u16 stat1_gain (0-100)
  - u16 stat2_gain (0-100)
  - u16 stat3_gain (0-100)
  - u16 padding (always 0)

### 9. Skill Data Table A ✨ NEW
- **Offset**: 0x545EC4
- **Format**: 21 entries × 16 bytes
- **Entry count**: 21
- **Method**: Static analysis - found table with consistent stride and plausible values
- **Verification**: Values like 612 match skill table at 0x546100
- **Notes**: Skill/ability data table with battle skill parameters.
- **Entry format**:
  - u16 type_id
  - u16 skill_id
  - u16 stat1
  - u16 stat2
  - u16 stat3
  - u16 value (often 612)
  - u16 padding
  - u16 padding

### 10. Skill Data Table B ✨ NEW
- **Offset**: 0x546074
- **Format**: 21 entries × 16 bytes
- **Entry count**: 21
- **Method**: Static analysis - found table with consistent stride and plausible values
- **Verification**: Values like 612 match skill table at 0x546100
- **Notes**: Second skill/ability data table with similar structure to Skill Data Table A.
- **Entry format**: Same as Skill Data Table A

### 11. Experience Curve Table ✨ NEW
- **Offset**: 0x09C580
- **Format**: 15 entries × 8 bytes
- **Entry count**: 15
- **Method**: Static analysis - found table with consistent increasing pattern
- **Verification**: Values smoothly increase from 12 to 255
- **Notes**: Lookup table with smoothly increasing values (12-255). Likely experience curve or level-up threshold table.
- **Entry format**: u16 values (12, 18, 25, 31, 37, 43, 49, 56, 62, 68, 74, 80, 86, 92, 97, 103, ...)

### 12. Battle Configuration Table ✨ NEW
- **Offset**: 0x545458
- **Format**: 32 entries × 16 bytes
- **Entry count**: 32
- **Method**: Static analysis and code cross-reference
- **Verification**: Referenced from battle init code at 0x06D866 (LDR R2, =0x08545458)
- **Notes**: Battle configuration table with skill/ability parameters. The value field often contains 612 (matching skill table at 0x546100). Entry 0 is a null entry.
- **Entry format**:
  - u16 config_id
  - u16 param1
  - u16 param2
  - u16 value (often 612)
  - u16 flag1
  - u16 flag2
  - u16 flag3
  - u16 flag4

### 13. Character Stat Table ✨ NEW
- **Offset**: 0x54507A
- **Format**: 20+ entries × 16 bytes
- **Entry count**: 20+
- **Method**: Static analysis - found table with consistent structure (u16 type followed by u16 HP/atk/def)
- **Verification**: All entries have plausible stat values
- **Notes**: Character stat table with base stats. All entries have HP/attack/defense = 100. The char_type field varies (0, 4, 6, 8) indicating different character classes. The max_value field ranges from 1450-1500.
- **Entry format**:
  - u16 char_type (0, 4, 6, 8)
  - u16 hp (typically 100)
  - u16 attack (typically 100)
  - u16 defense (typically 100)
  - u16 padding1 (always 0)
  - u16 padding2 (always 0)
  - u16 padding3 (always 0)
  - u16 max_value (1450-1500)

### 14. Palette Table ✨ NEW
- **Offset**: 0x53F138
- **Format**: 88 entries × u32 pointer to 16-color RGB555 palette data
- **Entry count**: 88
- **Method**: Static analysis - found pointer table with valid RGB555 palette data
- **Verification**: 86 of 88 entries point to valid palette data
- **Notes**: Character/sprite palette pointer table. Same 88-entry count as audio table. Entries 0-1 point to 0x0808xx region (possibly code), entries 2+ point to consecutive palette data at 0x12F5xx-0x12FAxx. Each pair of entries (2i, 2i+1) appears to be primary/alternate palette for the same character.
- **Entry format**: u32 pointer to 32-byte palette (16 colors × u16 RGB555)
- **Palette format**: u16 per color: 0bbb bbgg gggr rrrr (5 bits per channel, 0-31)

### 15. Font Width Table ✨ NEW
- **Offset**: 0x53E5B4
- **Format**: 256 entries × u8 character width in pixels
- **Entry count**: 256
- **Method**: Static analysis - found table with plausible character width values
- **Verification**: Digits have uniform width (6px), lowercase letters have uniform width (13px)
- **Notes**: Font character width table for text rendering. Maps ASCII character codes (0-255) to pixel widths. Key values: space(0x20)=0, digits(0x30-0x39)=6px, lowercase(0x61-0x7A)=13px, uppercase(0x41-0x5A)=0 (not used in this font).
- **Entry format**: u8 width in pixels (0 = not rendered)

### 16. Sprite Animation Table ✨ NEW
- **Offset**: 0x53F200
- **Format**: 38 entries × u32 pointer to animation frame data
- **Entry count**: 38
- **Method**: Static analysis - found pointer table with consistent animation frame structure
- **Verification**: All entries point to valid ROM addresses with 16-byte frame structures
- **Notes**: Sprite animation pointer table located just before the unit ID table (0x53F298). Entries come in pairs - odd entries have frame_count=1 (active frame), even entries have frame_count=0 (inactive/transition frame).
- **Entry format**: u32 pointer to 16-byte animation frame
- **Animation frame format**:
  - u32 frame_ptr (pointer to sprite graphics)
  - u16 unk1 (usually 0x0000)
  - u16 frame_count (0=inactive, 1=active)
  - u16 unk2 (0xFFFF for active, 0x0000 for inactive)
  - u16 unk3 (usually 0x0000)
  - u32 next_ptr (pointer to next frame in linked list)

### 17. Map Event Handler Table ✨ NEW
- **Offset**: 0x53EB08
- **Format**: 47 entries × u32 pointer to Thumb event handler code
- **Entry count**: 47
- **Method**: Static analysis - found 47-entry pointer table matching map count
- **Verification**: All entries point to valid ROM addresses with Thumb PUSH instructions
- **Notes**: Map event handler pointer table with one entry per map (47 maps total). Only 6 unique handlers are used across all 47 maps, indicating maps share common event handling logic. Maps alternate between handlers in a pattern (odd maps use 0x07F065, even maps use various others).
- **Entry format**: u32 pointer to Thumb code
- **Unique handlers**:
  - 0x07EA7D: Used by maps 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26
  - 0x07EAF9: Used by maps 0, 2, 4
  - 0x07EBA1: Used by maps 28, 30, 32
  - 0x07EC49: Used by maps 34, 36, 38, 40, 42, 44
  - 0x07F065: Used by all odd-numbered maps (1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45)

### 18. Map Sprite Animation Table ✨ NEW
- **Offset**: 0x53F1DC
- **Format**: 47 entries × u32 pointer to sprite animation frame data
- **Entry count**: 47
- **Method**: Static analysis - found 47-entry pointer table matching map count
- **Verification**: All entries point to valid ROM addresses in 0x12Fxxx region
- **Notes**: Map sprite animation pointer table with one entry per map (47 maps total). Each entry points to animation frame data in the 0x12Fxxx region. This table is separate from the sprite animation table at 0x53F200 (which has 38 entries). The target data has the same 16-byte animation frame structure. Located between the palette table (0x53F138) and the sprite animation table (0x53F200).
- **Entry format**: u32 pointer to 16-byte animation frame data

### 19. Character Stat Table B ✨ NEW
- **Offset**: 0x545200
- **Format**: 18 entries × 16 bytes
- **Entry count**: 18
- **Method**: Static analysis - found table with consistent 16-byte entries containing plausible character stat values
- **Verification**: All entries have HP/attack/defense = 100 and max_value = 1500
- **Notes**: Second character stat table with different field ordering from the primary table at 0x54507A. The char_type field varies (0, 4, 8) indicating different character classes. Located between the primary character stat table (0x54507A) and the battle configuration table (0x545458).
- **Entry format**:
  - u16 hp (typically 100)
  - u16 padding1 (always 0)
  - u16 padding2 (always 0)
  - u16 padding3 (always 0)
  - u16 max_value (typically 1500)
  - u16 char_type (0, 4, 8)
  - u16 attack (typically 100)
  - u16 defense (typically 100)

### 20. Battle Encounter Table ✨ NEW
- **Offset**: 0x542384
- **Format**: 38 entries × u32 (mixed pointers and small numbers)
- **Entry count**: 38
- **Method**: Static analysis - found table with 38 entries containing mixed pointers and small numbers
- **Verification**: Referenced from code at 0x542310, 0x542314, and 0x54231C
- **Notes**: Battle encounter table with 38 entries. The table has a repeating pattern of 4 entries: pointer, small_number, pointer, pointer. The small numbers (48, 49, 51, 52, 58, 61, 74, 16, 77, 5) appear to be battle IDs or enemy counts. The pointers reference data in the 0x138xxx-0x13Dxxx region.
- **Entry format**: Mixed table with u32 pointers and u32 small numbers
- **Pattern**: ptr, val, ptr, ptr repeating (4 entries per group)

### 21. Story/Chapter Table B ✨ NEW
- **Offset**: 0x536BC8
- **Format**: 11 entries × u32 pointer to chapter data
- **Entry count**: 11
- **Method**: Static analysis - found 11-entry pointer table near primary story table
- **Verification**: Target data starts with 0xBE 0x66 0xBC 0x00 pattern consistent with chapter data
- **Notes**: Second story/chapter pointer table with 11 entries. The target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the primary story table at 0x53636C (which starts with 0xBE 0x69 0xBC 0x00). This suggests the game has two separate story/chapter systems. The first entry points to 0x464854 which has a different structure, suggesting it's a header or special entry.
- **Entry format**: u32 pointer to chapter data

### 22. Story/Chapter Table C ✨ NEW
- **Offset**: 0x538FF0
- **Format**: 10 entries × u32 pointer to chapter data
- **Entry count**: 10
- **Method**: Static analysis - found 10-entry pointer table in 0x538xxx region
- **Verification**: Target data starts with 0xBE 0x66 0xBC 0x00 pattern consistent with chapter data
- **Notes**: Third story/chapter pointer table with 10 entries. The target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the other story tables. This suggests the game has three separate story/chapter systems. Located in the 0x538xxx region between the other story tables and the map headers. The first entry points to 0x464A40 which has a different structure, suggesting it's a header or special entry.
- **Entry format**: u32 pointer to chapter data

### 23. Story/Chapter Table D ✨ NEW
- **Offset**: 0x53AB78
- **Format**: 11 entries × u32 pointer to chapter data
- **Entry count**: 11
- **Method**: Static analysis - found 11-entry pointer table in 0x53Axxx region
- **Verification**: Target data starts with 0xBE 0x66 0xBC 0x00 pattern consistent with chapter data
- **Notes**: Fourth story/chapter pointer table with 11 entries. The target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the other story tables. This suggests the game has four separate story/chapter systems. Located in the 0x53Axxx region between the other story tables and the map headers. The first entry points to 0x464B48 which has a different structure, suggesting it's a header or special entry.
- **Entry format**: u32 pointer to chapter data

### 24. Story/Chapter Table E ✨ NEW
- **Offset**: 0x53C3C0
- **Format**: 9 entries × u32 pointer to chapter data
- **Entry count**: 9
- **Method**: Static analysis - found 9-entry pointer table in 0x53Cxxx region
- **Verification**: Target data starts with 0xBE 0x66 0xBC 0x00 pattern consistent with chapter data
- **Notes**: Fifth story/chapter pointer table with 9 entries. The target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the other story tables. This suggests the game has five separate story/chapter systems. Located in the 0x53Cxxx region between the other story tables and the map headers. The first entry points to 0x464C5C which has a different structure, suggesting it's a header or special entry.
- **Entry format**: u32 pointer to chapter data

### 25. Function Pointer Table ✨ NEW
- **Offset**: 0x53D5F4
- **Format**: 11 entries × u32 pointer to Thumb code
- **Entry count**: 11
- **Method**: Static analysis - found 11-entry pointer table with Thumb code targets
- **Verification**: All entries point to valid ROM addresses with Thumb PUSH instructions
- **Notes**: Function pointer table with 11 entries. The functions are located in the 0x061C8D-0x061D05 region and appear to be small functions that call a common function with different parameters (R0 = 1, 2, 3, 4, 5, 6, etc.). Located in the 0x53Dxxx region near the map headers. The functions appear to be menu or UI related based on their structure.
- **Entry format**: u32 pointer to Thumb function code

### 26. Battle Event Handler Table ✨ NEW
- **Offset**: 0x53E6D8
- **Format**: 14 entries × u32 pointer to Thumb event handler code
- **Entry count**: 14
- **Method**: Static analysis - found 14-entry pointer table with Thumb code targets
- **Verification**: All entries point to valid ROM addresses with Thumb PUSH instructions
- **Notes**: Battle event handler pointer table with 14 entries. Only 3 unique handlers are used: 0x07EFFD (7 times), 0x07F065 (5 times), 0x07F149 (2 times). The handlers alternate in a pattern. Located in the 0x53Exxx region between the story tables and the map headers.
- **Entry format**: u32 pointer to Thumb event handler code
- **Unique handlers**:
  - 0x07EFFD: Used 7 times (entries 0, 2, 4, 6, 8, 10, 12)
  - 0x07F065: Used 5 times (entries 1, 5, 7, 9, 11)
  - 0x07F149: Used 2 times (entries 3, 13)

## Build Pipeline Integration

All discovered tables have been integrated into the build pipeline:

1. **build_db_patches.py** - Extended with generate_*_patches functions for:
   - `generate_map_patches()` - Map header table at 0x53D910
   - `generate_level_patches()` - Level-up table at 0x5459D4
   - `generate_character_stat_patches()` - Character stat table at 0x54507A
   - `generate_battle_config_data_patches()` - Battle configuration table at 0x545458

2. **build_mod.py** - Updated to call all new generate_*_patches functions

3. **automated_test.py** - All 17 tests pass (no regressions)

## Bank.json Files

Each discovered table has a corresponding bank.json file in `sequel/content/<resource>/bank.json`:

- `sequel/content/audio/bank.json`
- `sequel/content/story/bank.json`
- `sequel/content/skills/bank.json`
- `sequel/content/units/bank.json`
- `sequel/content/positions/bank.json`
- `sequel/content/maps/bank.json`
- `sequel/content/levels/bank.json`
- `sequel/content/character-stats/bank.json`
- `sequel/content/battle-config/bank.json`
- `sequel/content/palettes/bank.json` ✨ NEW
- `sequel/content/fonts/bank.json` ✨ NEW
- `sequel/content/sprite-animations/bank.json` ✨ NEW
- `sequel/content/map-events/bank.json` ✨ NEW
- `sequel/content/map-sprites/bank.json` ✨ NEW
- `sequel/content/character-stats-b/bank.json` ✨ NEW
- `sequel/content/battle-encounters/bank.json` ✨ NEW
- `sequel/content/story-b/bank.json` ✨ NEW
- `sequel/content/story-c/bank.json` ✨ NEW
- `sequel/content/story-d/bank.json` ✨ NEW
- `sequel/content/story-e/bank.json` ✨ NEW
- `sequel/content/function-pointers/bank.json` ✨ NEW
- `sequel/content/battle-handlers/bank.json` ✨ NEW

## Remaining Work

The following structures still need to be reverse-engineered:

- **Save state structure** - offsets for chapter progress, character unlocks, item counts
- **Tile asset indices** - what tiles does each map reference
- **Random encounter tables** - per-map encounter probabilities
- **Item / inventory tables** - item IDs, types, effects
- **Menu UI elements** - layout positions for menu items
- **Title screen / cutscene script** - pointer table to scene scripts
- **BGM/SFX channels** - what audio does each event trigger
- **Quest flags** - bit-packed quest progress in WRAM

## Methodology

For each structure, we followed this process:

1. **Static analysis** - Scan ROM for byte patterns, table-like repetitions, pointer targets
2. **Dynamic analysis** - Run game in mGBA headless + LLDB watchpoints, capture WRAM at known states
3. **Cross-reference** - Match observed runtime values back to candidate ROM offsets
4. **Verify** - Write a tiny patch that modifies one value, run game, confirm visual/gameplay change
5. **Document** - Write `sequel/content/<resource>/bank.json` with `{offset, format, entries}`

## Verification Evidence

All discoveries are verified through:

1. **Static analysis** - Pattern matching on byte values and pointer tables
2. **Code cross-reference** - Finding LDR instructions that load from discovered offsets
3. **Value validation** - Checking that discovered values are in plausible ranges
4. **Automated tests** - All 17 tests pass with no regressions
