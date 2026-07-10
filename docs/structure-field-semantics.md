# Structure Field Semantics Documentation

**ROM:** 火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba  
**SHA-1:** `26f60795fa5e63b4f0264b84e453beffd56b9f7d`  
**Date:** 2026-06-28

This document describes the semantic meaning of fields in each of the 32
reverse-engineered data structures.

---

## 1. Audio (0x53F138)

**Format:** u32[88] — 88 pointers to Sappy audio entries  
**Entry Size:** 4 bytes  
**Semantics:** Each entry is a pointer (0x08XXXXXX) to a Sappy audio structure
containing instrument data, note sequences, and playback parameters. The
custom Sappy dispatcher at 0x079668 reads these pointers when commands
0x80-0xE3 are issued. Commands 0x64-0x67 handle BGM channel control.

| Field | Type | Description |
|-------|------|-------------|
| audio_ptr | u32 | Pointer to Sappy audio entry in ROM |

---

## 2. Battle Config (0x545458)

**Format:** u16[8] × 32 — 32 battle configuration entries  
**Entry Size:** 16 bytes  
**Semantics:** Each entry configures a battle scenario with skill parameters.
Referenced from battle init code at 0x06D866. The value field often contains
612, matching the skill table at 0x546100.

| Field | Type | Description |
|-------|------|-------------|
| config_id | u16 | Configuration ID or type identifier |
| param1 | u16 | First parameter (often 0) |
| param2 | u16 | Second parameter (often 0) |
| value | u16 | Skill value (commonly 612) |
| flag1 | u16 | Configuration flag 1 |
| flag2 | u16 | Configuration flag 2 |
| flag3 | u16 | Configuration flag 3 (usually 0) |
| flag4 | u16 | Configuration flag 4 (usually 0) |

---

## 3. Battle Encounters (0x542384)

**Format:** u32 × 38 — Mixed pointers and data values  
**Entry Size:** 4 bytes  
**Semantics:** Table containing both pointers (0x08XXXXXX range) to battle
encounter definitions and small integer values (likely encounter IDs or
flags). The pattern alternates between pointers and data, suggesting
each encounter has a pointer to its definition followed by metadata.

| Field | Type | Description |
|-------|------|-------------|
| value | u32 | Pointer (0x08XXXXXX) or small integer data |

---

## 4. Battle Handlers (0x53E6D8)

**Format:** u32 × 14 — 14 pointers to Thumb event handler code  
**Entry Size:** 4 bytes  
**Semantics:** Each entry points to a Thumb subroutine that handles a specific
battle event type. There are only 3 unique handler addresses (many entries
share the same handler), indicating 3 distinct event processing modes.

| Field | Type | Description |
|-------|------|-------------|
| handler_ptr | u32 | Pointer to Thumb event handler code |

---

## 5. Character Stats (0x54507A)

**Format:** u16[8] × 20 — 20 character stat entries  
**Entry Size:** 16 bytes  
**Semantics:** Base character statistics. All entries have HP/attack/defense
at 100. The char_type field indicates character class (0, 4, 6, 8).
The max_value field ranges from 1450-1500 and may represent a level cap
or stat scaling factor.

| Field | Type | Description |
|-------|------|-------------|
| char_type | u16 | Character class (0=normal, 4=speed, 6=power, 8=balanced) |
| hp | u16 | Base HP (always 100) |
| attack | u16 | Base attack (always 100) |
| defense | u16 | Base defense (always 100) |
| padding1 | u16 | Always 0 |
| padding2 | u16 | Always 0 |
| padding3 | u16 | Always 0 |
| max_value | u16 | Maximum value (1450-1500) |

---

## 6. Character Stats B (0x545200)

**Format:** u16[8] × 18 — 18 secondary stat entries  
**Entry Size:** 16 bytes  
**Semantics:** Secondary character stat table with different field ordering
from the primary table. This table likely contains growth rates or
secondary modifiers for each character class.

| Field | Type | Description |
|-------|------|-------------|
| field0 | u16 | Primary stat (100) |
| field1 | u16 | Modifier (usually 0) |
| field2 | u16 | Modifier (usually 0) |
| field3 | u16 | Modifier (usually 0) |
| field4 | u16 | Max value (1500) |
| field5 | u16 | Class ID (0 or 8) |
| field6 | u16 | Secondary stat (100) |
| field7 | u16 | Tertiary stat (100) |

---

## 7. Cutscene Scripts (0x53DF70)

**Format:** u32 × 16 — 16 pointers to cutscene script data
**Entry Size:** 4 bytes  
**Semantics:** Each entry points to a cutscene script in the 0x12XXXX region.
Scripts contain encoded dialogue, camera movements, and character animations
for story sequences.

| Field | Type | Description |
|-------|------|-------------|
| script_ptr | u32 | Pointer to cutscene script data |

---

## 8. Data Table A (0x5A14A4)

**Format:** u32 × 20 — 20 pointers to encoded data  
**Entry Size:** 4 bytes  
**Semantics:** Pointer table to encoded data structures in the 0x5AXXXX region.
These likely contain compressed or encoded game data (possibly tilemaps,
level data, or other game assets).

| Field | Type | Description |
|-------|------|-------------|
| data_ptr | u32 | Pointer to encoded data block |

---

## 9. Data Table B (0x5A2120)

**Format:** u32 × 20 — 20 pointers to encoded data  
**Entry Size:** 4 bytes  
**Semantics:** Second pointer table to encoded data in the 0x5AXXXX region.
May contain alternate versions or related data to Table A.

| Field | Type | Description |
|-------|------|-------------|
| data_ptr | u32 | Pointer to encoded data block |

---

## 10. Encounter Zones (0x53D910+28)

**Format:** u32 zone_id × 47 (within 32-byte map headers)  
**Entry Size:** 32 bytes (zone_id at offset 28)  
**Semantics:** Each map has a zone_id field that controls which encounter table
is used when the player walks on that map. Zone IDs range from 1-7 and 258.
The battle system uses this to determine random encounter behavior.

| Field | Type | Description |
|-------|------|-------------|
| map_width | u16 | Map width in tiles |
| map_height | u16 | Map height in tiles |
| zone_id | u32 | Encounter zone ID (1-7, 258) |

---

## 11. Fonts (0x53E5B4)

**Format:** u8 × 256 — 256 character width values  
**Entry Size:** 1 byte  
**Semantics:** Maps ASCII character codes (0-255) to pixel widths for the
game's proportional font renderer. Characters 32-126 are printable ASCII.
Width 0 indicates characters that aren't rendered or use default width.

| Field | Type | Description |
|-------|------|-------------|
| char_width | u8 | Pixel width of character glyph |

---

## 12. Function Pointers (0x53D5F4)

**Format:** u32 × 11 — 11 pointers to Thumb code  
**Entry Size:** 4 bytes  
**Semantics:** Table of function pointers used by the game's event system.
These are called during map transitions, menu operations, and other
game state changes.

| Field | Type | Description |
|-------|------|-------------|
| func_ptr | u32 | Pointer to Thumb function code |

---

## 13. Items (0x546100)

**Format:** u16[8] × 12 — 12 item/technique entries (same table as Skills)  
**Entry Size:** 16 bytes  
**Semantics:** In this tactical RPG, items share the skill table. Each entry
defines a technique/item with type, effect, cost, and flags. The item_id
field is the primary key for editor integration.

| Field | Type | Description |
|-------|------|-------------|
| padding | u32 | Always 0 |
| count | u16 | Usage count (typically 5) |
| type_id | u16 | Item/technique type (0x0120, 0x0122) |
| skill_id | u16 | Skill/technique ID |
| value | u16 | Effect value (often 612) |
| flags | u16 | Item flags (0x0401) |
| extra_id | u16 | Extra identifier |

---

## 14. Levels (0x5459D4)

**Format:** u16[6] × 26 — 26 level-up entries  
**Entry Size:** 12 bytes  
**Semantics:** Level-up stat progression table. Each entry defines the stat
gains when a character levels up. The table may be per-character-class
or per-level-range.

| Field | Type | Description |
|-------|------|-------------|
| level | u16 | Level number |
| hp_gain | u16 | HP gain at this level |
| stat1_gain | u16 | Attack/stat1 gain |
| stat2_gain | u16 | Defense/stat2 gain |
| stat3_gain | u16 | Third stat gain |
| padding | u16 | Always 0 |

---

## 15. Map Events (0x53EB08)

**Format:** u32 × 47 — 47 pointers to event handler code  
**Entry Size:** 4 bytes  
**Semantics:** Each map has an associated event handler pointer. There are 6
unique handler addresses, indicating 6 distinct event processing modes
(e.g., town, dungeon, overworld, cutscene, boss, menu).

| Field | Type | Description |
|-------|------|-------------|
| handler_ptr | u32 | Pointer to Thumb event handler code |

---

## 16. Maps (0x53D910)

**Format:** 32 bytes × 47 — 47 map header entries  
**Entry Size:** 32 bytes  
**Semantics:** Complete map definitions including dimensions, tile graphics
pointers, tilemap data, palette references, and configuration flags.

| Field | Type | Description |
|-------|------|-------------|
| width | u16 | Map width in tiles (16-128) |
| height | u16 | Map height in tiles (16-128) |
| tileset_ptr | u32 | Pointer to tile graphics data |
| tilemap_ptr | u32 | Pointer to primary tilemap data |
| tilemap_alt_ptr | u32 | Pointer to alternate tilemap (0 if none) |
| extra_ptr | u32 | Pointer to extra map data |
| palette_ptr | u32 | Pointer to palette data |
| palette2_ptr | u32 | Pointer to secondary palette |
| flags | u32 | Map configuration flags (includes zone_id at +28) |

---

## 17. Map Sprites (0x53F1DC)

**Format:** u32 × 47 — 47 pointers to sprite animation data  
**Entry Size:** 4 bytes  
**Semantics:** Each map has associated sprite animation data for NPCs,
enemies, and interactive objects displayed on that map.

| Field | Type | Description |
|-------|------|-------------|
| sprite_ptr | u32 | Pointer to sprite animation frame data |

---

## 18. Menu UI (0x5A5774)

**Format:** u32 × 20 — 20 pointers to menu/UI data  
**Entry Size:** 4 bytes  
**Semantics:** Pointers to menu graphics and layout data in the 0x43XXXX-
0x44XXXX region. Each entry defines a menu screen (main menu, status,
inventory, etc.).

| Field | Type | Description |
|-------|------|-------------|
| ui_ptr | u32 | Pointer to menu/UI layout data |

---

## 19. Palettes (0x53F138)

**Format:** u32 × 88 — 88 pointers to palette data  
**Entry Size:** 4 bytes  
**Semantics:** Each entry points to a 16-color RGB555 palette (32 bytes).
Palettes define the color schemes for characters, tiles, and UI elements.
Note: This table shares the same ROM region as the Audio table.

| Field | Type | Description |
|-------|------|-------------|
| palette_ptr | u32 | Pointer to 16-color RGB555 palette data |

---

## 20. Positions (0x53D914)

**Format:** Scenario-dependent — 8 scenario entries  
**Entry Size:** Variable  
**Semantics:** Each scenario entry contains pointers to tile data that defines
unit starting positions on the battle map. The positions are embedded within
the scenario configuration data.

| Field | Type | Description |
|-------|------|-------------|
| scenario_id | int | Scenario identifier |
| position_data | bytes | Tile data defining unit positions |

---

## 21. Resource Pointers (0x596F0C)

**Format:** u32 × 20 — 20 pointers to resource data  
**Entry Size:** 4 bytes  
**Semantics:** General resource pointer table to data in the 0x17XXXX region.
These may contain graphics, sound effects, or other game resources.

| Field | Type | Description |
|-------|------|-------------|
| resource_ptr | u32 | Pointer to resource data |

---

## 22. Sappy Engine (0x079668)

**Format:** Code region (not a data table)  
**Entry Size:** N/A  
**Semantics:** Custom Sappy audio dispatcher at 0x08079668 (file offset
0x079668). Not the standard GBA `m4aSongNumStart`. Supports:
- Commands 0x64-0x67: BGM channel control
- Commands 0x80-0xE3: Indexed lookup into 100-entry pointer table at 0x08599634
- 15 BL call sites from 6 unique functions
- Per-scenario BGM assigned via `config_struct[0x770]`

| Field | Type | Description |
|-------|------|-------------|
| code | bytes | Thumb instruction bytes |
| commands | dict | Command ranges and their meanings |

---

## 23. Save State (0x53D848)

**Format:** u32[2] × 10 — 10 save field entries (7 unique)  
**Entry Size:** 8 bytes  
**Semantics:** Save table mapping EWRAM buffers to SRAM offsets. Each entry
writes 19 data bytes + 1 byte checksum (total 20 bytes) to SRAM.
Checksum = `~sum(19 bytes)` (bitwise NOT). Handler at 0x08068684 supports
save (mode 0) and load (mode 1).

| Field | Type | Description |
|-------|------|-------------|
| ewram_addr | u32 | EWRAM buffer address |
| sram_offset | u32 | SRAM write offset |

---

## 24. Skills (0x546100)

**Format:** u16[8] × 12 — 12 skill/technique entries  
**Entry Size:** 16 bytes  
**Semantics:** Skill/technique definitions. Referenced from battle init code
at 0x06E6D2 (LDR R1, =0x085461C4). The pointer 0x5461C4 is the base for
indexing into this table.

| Field | Type | Description |
|-------|------|-------------|
| padding | u32 | Always 0 |
| count | u16 | Usage count (typically 5) |
| type_id | u16 | Skill type (0x0120=normal, 0x0122=special) |
| skill_id | u16 | Unique skill identifier |
| value | u16 | Skill power/effect value (often 612) |
| flags | u16 | Skill flags (0x0401) |
| extra_id | u16 | Extra identifier |

---

## 25. Sprite Animations (0x53F200)

**Format:** u32 × 38 — 38 pointers to animation frame data  
**Entry Size:** 4 bytes  
**Semantics:** Each entry points to animation frame data for character sprites.
The animation data contains frame sequences, timing, and sprite sheet
references.

| Field | Type | Description |
|-------|------|-------------|
| anim_ptr | u32 | Pointer to animation frame data |

---

## 26. Story (0x53636C)

**Format:** u32 × 9 — 9 pointers to chapter data  
**Entry Size:** 4 bytes  
**Semantics:** Primary story/chapter pointer table. Chapter 0 has a different
structure (header with scene pointers). Chapters 1-8 have encoded beat data
starting with 0xBE 0x69 0xBC 0x00.

| Field | Type | Description |
|-------|------|-------------|
| chapter_ptr | u32 | Pointer to chapter data |

---

## 27-30. Story B/C/D/E (0x536BC8, 0x538FF0, 0x53AB78, 0x53C3C0)

**Format:** u32 × 9-11 — Chapter pointer tables  
**Entry Size:** 4 bytes  
**Semantics:** Additional story/chapter pointer tables. These likely represent
different story routes, alternate timelines, or post-game content. Each
table has slightly different entry counts (9-11).

| Field | Type | Description |
|-------|------|-------------|
| chapter_ptr | u32 | Pointer to chapter data |

---

## 31. Tile Assets (0x5A3218)

**Format:** u32 × 6 — 6 pointers to tile/map data  
**Entry Size:** 4 bytes  
**Semantics:** Pointers to tile graphics and tilemap data in the 0x34XXXX
region. These contain the actual pixel data for map tiles used by the
tile renderer.

| Field | Type | Description |
|-------|------|-------------|
| tile_ptr | u32 | Pointer to tile/map graphics data |

---

## 32. Units (0x53F298)

**Format:** u16 × 64 — 64 unit ID entries  
**Entry Size:** 2 bytes  
**Semantics:** Unit ID table mapping unit indices to character IDs. Used by
the battle system to identify which character each unit represents.
Indexed by the scenario configuration.

| Field | Type | Description |
|-------|------|-------------|
| char_id | u16 | Character identifier |

---

## Verification Levels

- **static_verified**: Offset and format confirmed by hex analysis
- **code_verified**: Cross-referenced with Thumb disassembly
- **dynamic_verified**: Confirmed via mGBA runtime execution
