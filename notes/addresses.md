# Address Notes

This file records confirmed and suspected ROM offsets.

## Confirmed

- `0x0000A0`: internal title area contains `NARUTOKONOHA`
- `0x09E6EE`: starts a zero-filled run at least `1100` bytes long; candidate free space for experiments
- `0x596F98` and nearby region: contains dense pointer-table-like structures referencing `0x17A1A4` and related `0x17xxxx`/`0x18xxxx` assets
- `0x596FA8`: appears to begin a regular `0x10`-byte resource table entry sequence
- `0x17ED7C`: points to a secondary structured block containing internal pointers and small numeric fields
- `0x17A1A4`: palette-like block; first 32 bytes decode cleanly as 16 little-endian values within GBA BGR555 range
- `0x596FA8` table columns now have a working role model:
  - col 0: palette-like/shared base block
  - col 1: nested descriptor block
  - col 2: sparse binary or secondary resource block
  - col 3: sparse binary or mask/attribute block
- `0x00076C`: large low-ROM Shift-JIS-like text block; likely menu/help/tutorial-adjacent string bank
- `0x5A4E14`: another confirmed `0x10`-byte four-pointer table, but with a different profile from `0x596FA8`; probably a flatter visual resource bank

## Suspected

- `0x004081`: heavily referenced target (`557` aligned in-ROM pointers point here); likely shared data block, possibly text or table data
- `0x17A1A4`: heavily referenced target (`97` hits); looks structured and may be graphics, palette, or table data rather than executable code
- `0x596F90-0x59xxxx`: likely one or more resource pointer tables with repeated `16-byte` entry spacing
- `0x17A1A4`: likely base resource or shared header block reused across multiple entries in the `0x596FA8` table
- `0x5A4E14` table columns may map to mostly palette-like blocks plus one more variable binary resource column

## Confirmed Resource Tables (2026-06-24)

### Audio Table
- **Offset**: 0x53F138
- **Format**: 88 entries × u32 pointer to Sappy audio entry
- **Audio Entry Format**: 16 bytes: u32 data_ptr, u16 type, u16 pad, u16 flags, u16 pad, u32 extra_ptr
- **Notes**: First 2 entries point to code, entries 2+ are valid audio

### Story/Chapter Table
- **Offset**: 0x53636C
- **Format**: 9 entries × u32 pointer to chapter data
- **Chapter 0**: Header with pointers to scene/dialogue data
- **Chapters 1-8**: Encoded beat data starting with 0xBE 0x69 0xBC 0x00

### Skill Table
- **Offset**: 0x546100
- **Format**: 12 entries × 16 bytes
- **Entry Format**: u32 padding, u16 count, u16 type_id, u16 skill_id, u16 value, u16 flags, u16 extra_id
- **Notes**: Referenced from battle init code at 0x06E6D2

### Unit ID Table
- **Offset**: 0x53F298
- **Format**: u16[64] mapping unit index to character ID
- **Known IDs**: 0x00=Naruto, 0x01=Sasuke, 0x02=Sakura, 0x03=Sai, 0x04=Kakashi, 0x05=Shikamaru

### Battle Scenario Config
- **Offset**: 0x53D914
- **Format**: 8 entries × 32 bytes
- **Entry Format**: u32 dim(h|w), u32 tile_gfx_ptr, u32 tilemap_ptr, u32 tilemap_alt_ptr, u32 extra_ptr, u32 palette_ptr, u32 palette2_ptr, u32 flags
- **Notes**: Actually part of the Map Header Table (see below)

### Unit Positions
- **WRAM**: 0x02024294, stride 234 bytes, max 25 units
- **Format**: u8 existence, u8 x, u8 y, u8 team, u12 pad, u8 init_flag, ...
- **Notes**: Runtime data initialized from ROM during battle init

### Map Header Table
- **Offset**: 0x53D910
- **Format**: 47 entries × 32 bytes
- **Entry Format**: u16 width, u16 height, u32 tileset_ptr, u32 tilemap_ptr, u32 tilemap_alt_ptr, u32 extra_ptr, u32 palette_ptr, u32 palette2_ptr, u32 flags
- **Notes**: Contains all map definitions including battle maps, overworld maps, and special event maps. The battle scenario config at 0x53D914 is actually part of this table (offset by 4 bytes).
- **Verification**: Static analysis - found table with consistent structure (u16 dimensions followed by u32 ROM pointers). All 47 entries have valid dimensions (16-128) and valid ROM pointers.
- **Discovered**: 2026-06-25

### Level-up / Stat Progression Table
- **Offset**: 0x5459D4
- **Format**: 47 entries × 12 bytes
- **Entry Format**: u16 level_or_id, u16 hp_gain, u16 stat1_gain, u16 stat2_gain, u16 stat3_gain, u16 padding
- **Notes**: Contains level-up stat progression data. Entries 0-25 appear to be sequential level gains (level 1-31), while entries 26+ may be character-specific overrides. Values range from 1-200 for HP gains and 1-100 for other stat gains.
- **Verification**: Static analysis - found table with consistent small u16 values in plausible stat gain ranges.
- **Discovered**: 2026-06-25

### Skill Data Table A
- **Offset**: 0x545EC4
- **Format**: 21 entries × 16 bytes
- **Entry Format**: u16 type_id, u16 skill_id, u16 stat1, u16 stat2, u16 stat3, u16 value, u16 padding, u16 padding
- **Notes**: Skill/ability data table with values like 612 (matching skill table at 0x546100). Contains battle skill parameters.
- **Verification**: Static analysis - found table with consistent stride and plausible values.
- **Discovered**: 2026-06-25

### Skill Data Table B
- **Offset**: 0x546074
- **Format**: 21 entries × 16 bytes
- **Entry Format**: u16 type_id, u16 skill_id, u16 stat1, u16 stat2, u16 stat3, u16 value, u16 padding, u16 padding
- **Notes**: Second skill/ability data table with similar structure to Skill Data Table A. Contains battle skill parameters.
- **Verification**: Static analysis - found table with consistent stride and plausible values.
- **Discovered**: 2026-06-25

### Experience Curve Table
- **Offset**: 0x09C580
- **Format**: 15 entries × 8 bytes
- **Entry Format**: u16 values (12, 18, 25, 31, 37, 43, 49, 56, 62, 68, 74, 80, 86, 92, 97, 103, ...)
- **Notes**: Lookup table with smoothly increasing values (12-255). Likely experience curve or level-up threshold table.
- **Verification**: Static analysis - found table with consistent increasing pattern.
- **Discovered**: 2026-06-25

### Battle Configuration Table
- **Offset**: 0x545458
- **Format**: 32 entries × 16 bytes
- **Entry Format**: u16 config_id, u16 param1, u16 param2, u16 value, u16 flag1, u16 flag2, u16 flag3, u16 flag4
- **Notes**: Battle configuration table with skill/ability parameters. The value field often contains 612 (matching skill table at 0x546100). Entry 0 is a null entry. Referenced from battle init code at 0x06D866 (LDR R2, =0x08545458).
- **Verification**: Static analysis - found table with consistent stride and plausible battle parameters. Referenced from battle init code.
- **Discovered**: 2026-06-25

### Character Stat Table
- **Offset**: 0x54507A
- **Format**: 20+ entries × 16 bytes
- **Entry Format**: u16 char_type, u16 hp, u16 attack, u16 defense, u16 padding1, u16 padding2, u16 padding3, u16 max_value
- **Notes**: Character stat table with base stats. All entries have HP/attack/defense = 100. The char_type field varies (0, 4, 6, 8) indicating different character classes. The max_value field ranges from 1450-1500.
- **Verification**: Static analysis - found table with consistent structure (u16 type followed by u16 HP/atk/def). All entries have plausible stat values.
- **Discovered**: 2026-06-25

### Palette Table
- **Offset**: 0x53F138
- **Format**: 88 entries × u32 pointer to 16-color RGB555 palette data
- **Palette Format**: 32 bytes = 16 colors in GBA RGB555 format (u16: 0bbb bbgg gggr rrrr)
- **Notes**: Character/sprite palette pointer table. Same 88-entry count as audio table. Entries 0-1 point to 0x0808xx region (possibly code), entries 2+ point to consecutive palette data at 0x12F5xx-0x12FAxx. Each pair of entries (2i, 2i+1) appears to be primary/alternate palette for the same character. Primary palette has transparency at index 4 (31,31,31 = white), alternate has different structure.
- **Verification**: Static analysis - found 88 consecutive u32 pointers, 86 of 88 entries point to valid RGB555 palette data.
- **Discovered**: 2026-06-25

### Font Width Table
- **Offset**: 0x53E5B4
- **Format**: 256 entries × u8 character width in pixels
- **Notes**: Font character width table for text rendering. Maps ASCII character codes (0-255) to pixel widths. Key values: space(0x20)=0, digits(0x30-0x39)=6px, lowercase(0x61-0x7A)=13px, uppercase(0x41-0x5A)=0 (not used?), punctuation varies (6-17px). Used by dialogue and menu text rendering code.
- **Verification**: Static analysis - found 256-byte table with plausible character width values. Digits have uniform width (6px), lowercase letters have uniform width (13px).
- **Discovered**: 2026-06-25

### Sprite Animation Table
- **Offset**: 0x53F200
- **Format**: 38 entries × u32 pointer to animation frame data
- **Animation Frame Format**: 16 bytes: u32 frame_ptr, u16 unk1, u16 frame_count, u16 unk2, u16 unk3, u32 next_ptr
- **Notes**: Sprite animation pointer table located just before the unit ID table (0x53F298). Entries come in pairs - odd entries have frame_count=1 (active frame with 0xFFFF flag), even entries have frame_count=0 (inactive/transition frame). Each animation frame is a 16-byte structure containing a pointer to graphics data and a linked-list pointer to the next frame.
- **Verification**: Static analysis - found 38 consecutive u32 pointers, all pointing to valid ROM addresses. Target data has consistent 16-byte structure.
- **Discovered**: 2026-06-25

### Map Event Handler Table
- **Offset**: 0x53EB08
- **Format**: 47 entries × u32 pointer to Thumb event handler code
- **Notes**: Map event handler pointer table with one entry per map (47 maps total). All entries point to Thumb code (PUSH instructions). Only 6 unique handlers are used across all 47 maps, indicating maps share common event handling logic. Maps alternate between handlers in a pattern (odd maps use 0x07F065, even maps use various others).
- **Verification**: Static analysis - found 47 consecutive u32 pointers, all pointing to valid ROM addresses with Thumb instructions.
- **Discovered**: 2026-06-25

### Map Sprite Animation Table
- **Offset**: 0x53F1DC
- **Format**: 47 entries × u32 pointer to sprite animation frame data
- **Notes**: Map sprite animation pointer table with one entry per map (47 maps total). Each entry points to animation frame data in the 0x12Fxxx region. This table is separate from the sprite animation table at 0x53F200 (which has 38 entries). The target data has the same 16-byte animation frame structure.
- **Verification**: Static analysis - found 47 consecutive u32 pointers, all pointing to valid ROM addresses in 0x12Fxxx region.
- **Discovered**: 2026-06-25

### Character Stat Table B
- **Offset**: 0x545200
- **Format**: 18 entries × 16 bytes
- **Entry Format**: u16 hp, u16 padding1, u16 padding2, u16 padding3, u16 max_value, u16 char_type, u16 attack, u16 defense
- **Notes**: Second character stat table with different field ordering from the primary table at 0x54507A. All entries have HP/attack/defense = 100 and max_value = 1500. The char_type field varies (0, 4, 8) indicating different character classes.
- **Verification**: Static analysis - found table with consistent 16-byte entries containing plausible character stat values.
- **Discovered**: 2026-06-25

### Battle Encounter Table
- **Offset**: 0x542384
- **Format**: 38 entries × u32 (mixed pointers and small numbers)
- **Entry Format**: Pattern of 4 entries: pointer, small_number, pointer, pointer
- **Notes**: Battle encounter table with 38 entries. Small numbers (48, 49, 51, 52, 58, 61, 74, 16, 77, 5) appear to be battle IDs or enemy counts. Pointers reference data in 0x138xxx-0x13Dxxx region. Referenced from code at 0x542310, 0x542314, and 0x54231C.
- **Verification**: Static analysis - found table with 38 entries containing mixed pointers and small numbers. Referenced from code.
- **Discovered**: 2026-06-25

### Story/Chapter Table B
- **Offset**: 0x536BC8
- **Format**: 11 entries × u32 pointer to chapter data
- **Notes**: Second story/chapter pointer table with 11 entries. Target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the primary story table at 0x53636C (which starts with 0xBE 0x69 0xBC 0x00). This suggests the game has two separate story/chapter systems. Located near the primary story table in the 0x536xxx region.
- **Verification**: Static analysis - found 11 consecutive u32 pointers, all pointing to valid ROM addresses. Target data starts with 0xBE 0x66 0xBC 0x00 pattern.
- **Discovered**: 2026-06-25

### Story/Chapter Table C
- **Offset**: 0x538FF0
- **Format**: 10 entries × u32 pointer to chapter data
- **Notes**: Third story/chapter pointer table with 10 entries. Target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the other story tables. This suggests the game has three separate story/chapter systems. Located in the 0x538xxx region between the other story tables and the map headers.
- **Verification**: Static analysis - found 10 consecutive u32 pointers, all pointing to valid ROM addresses. Target data starts with 0xBE 0x66 0xBC 0x00 pattern.
- **Discovered**: 2026-06-25

### Story/Chapter Table D
- **Offset**: 0x53AB78
- **Format**: 11 entries × u32 pointer to chapter data
- **Notes**: Fourth story/chapter pointer table with 11 entries. Target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the other story tables. This suggests the game has four separate story/chapter systems. Located in the 0x53Axxx region between the other story tables and the map headers.
- **Verification**: Static analysis - found 11 consecutive u32 pointers, all pointing to valid ROM addresses. Target data starts with 0xBE 0x66 0xBC 0x00 pattern.
- **Discovered**: 2026-06-25

### Story/Chapter Table E
- **Offset**: 0x53C3C0
- **Format**: 9 entries × u32 pointer to chapter data
- **Notes**: Fifth story/chapter pointer table with 9 entries. Target data starts with 0xBE 0x66 0xBC 0x00 which is similar to the other story tables. This suggests the game has five separate story/chapter systems. Located in the 0x53Cxxx region between the other story tables and the map headers.
- **Verification**: Static analysis - found 9 consecutive u32 pointers, all pointing to valid ROM addresses. Target data starts with 0xBE 0x66 0xBC 0x00 pattern.
- **Discovered**: 2026-06-25

### Function Pointer Table
- **Offset**: 0x53D5F4
- **Format**: 11 entries × u32 pointer to Thumb code
- **Notes**: Function pointer table with 11 entries. All entries point to Thumb code (PUSH instructions). The functions are located in the 0x061C8D-0x061D05 region and appear to be small functions that call a common function with different parameters. Located in the 0x53Dxxx region near the map headers.
- **Verification**: Static analysis - found 11 consecutive u32 pointers, all pointing to valid ROM addresses with Thumb instructions.
- **Discovered**: 2026-06-25

### Battle Event Handler Table
- **Offset**: 0x53E6D8
- **Format**: 14 entries × u32 pointer to Thumb event handler code
- **Notes**: Battle event handler pointer table with 14 entries. Only 3 unique handlers are used: 0x07EFFD (7 times), 0x07F065 (5 times), 0x07F149 (2 times). The handlers alternate in a pattern. Located in the 0x53Exxx region between the story tables and the map headers.
- **Verification**: Static analysis - found 14 consecutive u32 pointers, all pointing to valid ROM addresses with Thumb instructions.
- **Discovered**: 2026-06-25

### Resource Pointer Table
- **Offset**: 0x596F0C
- **Format**: 20 entries × u32 pointer to resource data in 0x17xxxx region
- **Notes**: Resource pointer table with 20 entries. All entries point to data in the 0x17xxxx region, which is the resource pointer table area. The target data includes pointers to other resources and structured data blocks. Some entries point to 0x170F90 which appears to be a null or default resource. Located in the 0x59xxxx region which is known to contain dense pointer-table-like structures.
- **Verification**: Static analysis - found 20 consecutive u32 pointers, all pointing to valid ROM addresses in the 0x17xxxx resource region.
- **Discovered**: 2026-06-25

### Data Table A
- **Offset**: 0x5A14A4
- **Format**: 20 entries × u32 pointer to encoded data in 0x5Axxxx region
- **Notes**: Data pointer table with 20 entries. All entries point to encoded data in the 0x5Axxxx region. The target data appears to be encoded content (possibly text or compressed data). The data starts with bytes like 0x9A, 0x5F, 0x9A, 0x69 which don't match standard text encoding. Located in the 0x5Axxxx region which is known to contain resource data tables.
- **Verification**: Static analysis - found 20 consecutive u32 pointers, all pointing to valid ROM addresses in the 0x5Axxxx region.
- **Discovered**: 2026-06-25

### Data Table B
- **Offset**: 0x5A2120
- **Format**: 20 entries × u32 pointer to encoded data in 0x5Axxxx region
- **Notes**: Data pointer table with 20 entries. All entries point to encoded data in the 0x5Axxxx region. The target data appears to be encoded content (possibly text or compressed data). The data starts with bytes like 0x9C, 0x6E, 0x9C, 0x6A which don't match standard text encoding. Located in the 0x5Axxxx region which is known to contain resource data tables. This table is separate from Data Table A at 0x5A14A4.
- **Verification**: Static analysis - found 20 consecutive u32 pointers, all pointing to valid ROM addresses in the 0x5Axxxx region.
- **Discovered**: 2026-06-25

### Tile Asset Pointer Table
- **Offset**: 0x5A3218
- **Format**: 6 entries × u32 pointer to tile/map data in 0x34xxxx region
- **Notes**: Tile asset pointer table with 6 entries. All entries point to data in the 0x34xxxx region. The target data starts with patterns like 0x10 0x00 which could be map dimensions (16x0) or tile data headers. Some entries contain what appears to be tilemap data (0xF0, 0x01 patterns). Located in the 0x5Axxxx region which is known to contain resource data tables.
- **Verification**: Static analysis - found 6 consecutive u32 pointers, all pointing to valid ROM addresses in the 0x34xxxx region.
- **Discovered**: 2026-06-25

### Menu UI Pointer Table
- **Offset**: 0x5A5774
- **Format**: 20 entries × u32 pointer to menu/UI data in 0x43xxxx-0x44xxxx region
- **Notes**: Menu UI pointer table with 20 entries. Entries alternate between two pointers (0x43FC78 and 0x440738) for the first 10 entries, then switch to another pair (0x4407B8 and 0x441324) for the last 10 entries. The target data starts with patterns like 0x10 0x00 which could be UI element dimensions or layout data. Located in the 0x5Axxxx region which is known to contain resource data tables.
- **Verification**: Static analysis - found 20 consecutive u32 pointers, all pointing to valid ROM addresses in the 0x43xxxx-0x44xxxx region.
- **Discovered**: 2026-06-25

## Workflow

For each new finding, record:

- ROM offset
- virtual address if relevant
- confidence level
- why it matters
- how it was verified
