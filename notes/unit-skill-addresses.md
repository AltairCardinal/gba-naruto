# Unit & Skill Addresses

## Status

**Substantially identified.** Unit ID mapping table, battle scenario config table, and WRAM battle data layout all confirmed. ROM data format for battle maps partially decoded (ptr1 tilemap header + ptr2 LZ77 palette data). Patch generation operational.

## Unit ID Mapping Table

- **ROM ARM**: `0x0853F298`
- **File offset**: `0x53F298`
- **Format**: u16[64] (128 bytes, little-endian)
- **Referenced by**: Battle init function at `0x0806E654-0x0806E672`

### Table Layout

| Index | Value | Character |
|---|---|---|
| 0 | 0x00 | Naruto |
| 1 | 0x01 | Sasuke |
| 2 | 0x02 | Sakura |
| 3 | 0x03 | Sai |
| 4 | 0x04 | Kakashi |
| 5 | 0x05 | Shikamaru |
| 6 | 0x06 | Sasuke (Naruto) |
| 7 | 0x07 | Sakura (NPC) |
| 8 | 0x08 | Naruto (NPC) |
| 9 | 0x09 | Sasuke (NPC) |
| 10-29 | 0x19-0x2E | Special/enemy units |
| 30-42 | 0x0A-0x18 | Additional characters |
| 43-55 | signed i16 | Movement offsets (-8 to +4 tiles) |
| 62 | 0x0C3D | ROM data index (lo) |
| 63 | 0x0808 | ROM data index (hi) |

### Movement Offsets (indices 43-55)

Signed (dy, dx) tile offsets for 8-directional movement:
```
(-4, 0), (-6, 4), (-7, 7), (-8, 9), (-6, 9), (-4, 7), (-2, 4)
```

## Battle Scenario Config Table

- **ROM ARM**: `0x0853D910`
- **File offset**: `0x53D910`
- **Format**: 16 bytes per entry, 8 valid scenarios
- **Entry format**: u16 tiles_x, u16 tiles_y, u32 ptr1, u32 ptr2, u16 flag, u16 extra

See `battle-scenario-config.md` for full entry list.

## Battle State Machine Functions

- **ROM ARM**: `0x0853F1C0`
- **File offset**: `0x53F1C0`
- **Format**: u32[60] function pointers
- **Target range**: ROM bank 0x0812Fxxx

## Unit Stats Table

**Not found as a separate ROM table.** Unit stats (HP, ATK, DEF) are likely:
- Hardcoded in the battle system code
- Stored in BSS and populated at runtime
- Or referenced through the unit lookup mechanism

## Skill/Effect Table

**Not found.** Battle state machine function pointers (0x0853F1C0) may reference skill handling code.

## Enemy Character Table

Character IDs used for enemies (from unit ID table analysis):
| ID | Name |
|---|---|
| 0x0A | Zabuza |
| 0x0B | Haku |
| 0x23 | Masked Scouter |
| 0x24 | Ambush Member |
| 0x25-0x2E | Other enemy types |

## Battle Configuration Data (WRAM)

| WRAM Address | Size | Description |
|---|---|---|
| 0x0201BE2A | variable | Unit count + team count |
| 0x02021E2C | 234*N | Unit lookup table base |
| 0x02024294 | 234*25 | Unit array |
| 0x020240C0 | 6084 bytes | Main battle data |
| 0x02022E30 | 4732 bytes | Battle state |
| 0x02026804 | 8 bytes | Battle control flags |

## ROM Data Format Summary

### ptr1 (Tilemap) Format
12-byte header + raw u16 tile data:
- Header: u16 stride, u16 height, u16 type, u16 0xF000, u16 0x9001, u16 subtype
- Data: u16 per tile (lower 10 bits = tile ID, bits 10-15 = flip/palette)

### ptr2 (Palette/Attribute) Format
LZ77-compressed, 384 bytes decompressed:
- GBA LZ77 header (byte 0 = 0x10)
- Decompressed data contains BGR555 color values and attribute flags

## Patch Generation

`tools/import_battle_config.py` generates:
1. **ROM patches**: Unit ID table modifications, scenario config modifications
2. **WRAM patches**: Runtime battle data overrides (cheat codes)

## Investigation Gaps

- Unit stats (HP, ATK, DEF): **not found** — likely in BSS or hardcoded
- Skill table: **not found** — may be in function pointer table handlers
- Enemy placement: **partially decoded** — ptr2 LZ77 data format needs runtime verification
- Chapter-to-battle mapping: **not found** — requires runtime analysis

## Next Steps

1. Capture a savestate during active battle for WRAM analysis
2. Decompress and map ptr2 LZ77 data to unit placement fields
3. Identify unit stats structure referenced by character ID
4. Find the skill/effect lookup table in ROM
