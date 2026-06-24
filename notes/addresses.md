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

### Unit Positions
- **WRAM**: 0x02024294, stride 234 bytes, max 25 units
- **Format**: u8 existence, u8 x, u8 y, u8 team, u12 pad, u8 init_flag, ...
- **Notes**: Runtime data initialized from ROM during battle init

## Workflow

For each new finding, record:

- ROM offset
- virtual address if relevant
- confidence level
- why it matters
- how it was verified
