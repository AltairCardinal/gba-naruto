# Structure Field Semantics Documentation

**ROM:** 火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba  
**SHA-1:** `26f60795fa5e63b4f0264b84e453beffd56b9f7d`  
**Date:** 2026-06-28

This document describes the semantic meaning of fields in each of the 32
reverse-engineered data structures.

---

## 1. Message command table (legacy `audio` slug, 0x599634)

**Format:** u32[100] — pointers selected by command bytes `0x80..0xE3`
**Entry Size:** 4 bytes  
**Evidence:** code verified at `0x08079668 → 0x08066758 → 0x0806626C`

Each entry points to zero-terminated encoded message data. The former audio
identity was false: `0x53F138` belongs to palettes, while the actual music/SFX
engine and tables remain unresolved. The directory slug is retained only for
compatibility and must not be treated as an audio serializer.

| Field | Type | Description |
|-------|------|-------------|
| message_ptr | u32 | Pointer to encoded message data in ROM |

---

## 2. Battle Effect Templates (0x545458)

**Format:** 32 × 16-byte effect templates
**Entry Size:** 16 bytes
**Evidence:** code verified at `0x0806D85C`

The consumer copies the selected record byte-for-byte into a runtime effect
structure. Byte `+0x0C` chooses a level-growth destination (`+4..+9` for types
1..6); u16 `+0x0E` is the increment multiplied by `level-1`. Type 7 performs
no growth adjustment. Bytes `+0x00..+0x0B` and `+0x0D` remain conservatively
unnamed pending action-specific runtime tests.

---

## 3. Story visual descriptors (historical battle-encounters slug, 0x54229C)

**Format:** 24 × 16 bytes. Each record contains three LZ77 pointers at
`+0/+4/+8` and a visual/configuration ID at `+0x0C`. Story opcode loader
`0x08087C9C` decompresses the streams to graphics VRAM, palette RAM, and
tilemap VRAM. The old `0x542384` base was descriptor 14 `+8`, not an
independent encounter table.

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

## 5. Character Growth (0x545068)

**Format:** 63 × 16-byte records, indexed by character ID
**Evidence:** runtime verified

`0x0806D964` computes the ordinary source as
`0x08545068 + character_id*0x10`. Each consumed u16 is multiplied by
`level-1`, divided by 100, then added to a base field from the character
definition record. The table ends exactly at `0x545458`, the next known table.

| ROM field | Runtime template destination | Proven operation |
|---|---:|---|
| `+0x00` | `+0x0E` | `base_u16 + growth*(level-1)/100` |
| `+0x02` | `+0x08` | `base_u8 + growth*(level-1)/100` |
| `+0x04` | `+0x02` | same; runtime A/B verified |
| `+0x06` | `+0x03` | same |
| `+0x08` | `+0x04` | same |
| `+0x0A` | `+0x05` | same |
| `+0x0C` | `+0x06` | same |
| `+0x0E` | — | not read by the known path |

IDs 57 and 58 are special: they use character-definition records 57/58 but
growth records 8/15. A diagnostic first-battle A/B changed character 1 record
`+0x04` from 100 to 200 and changed only template and battle-slot `+0x02`
from 15 to 16.

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

## 6. Character Stats B (0x545200) — disproved

This is not an independent table. `0x545200` equals
`0x545068 + 25*0x10 + 8`, so the old bank began halfway through physical
growth record 25. Its write-back generator is disabled and the bank is retained
only as a migration tombstone.

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

## 7. Cutscene visual resources (historical slug, 0x53DF70)

**Format:** 8 × 8-byte pointer pairs. The first four are compressed graphics
and palette resources; the second four are sprite-definition and animation
pairs for the same IDs 0..3. Consumer `0x08072EDC` proves this is not a script
opcode table. See `notes/cutscene-visual-resource-consumer-20260712.md`.

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

## 10. Encounter Zones (disproved alias of 0x53D910)

The former bank was a second view of all 47 map descriptors, not an independent
encounter table. Its alleged `zone_id` at `+0x1C` is the map `flags` field;
runtime map-resource evidence and the byte consumer at `0x0806922A` establish
that identity. The bank is retained as an empty, write-disabled migration
tombstone. Random encounters still require discovery of an independent table
and consumer chain.

---

## 11. Fonts (disproved catalog at 0x53E5B4)

The claimed 256-byte width range has no xref and crosses into the canonical
handler-pair table. It is an empty, write-disabled tombstone. The proven
dialogue glyph lookup is the separate `0x53D644` chain.

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

**Status:** disproved independent alias. The former bank duplicated Skills
byte-for-byte and is retained only as a tombstone. No separate item table has
been located; `0x546100` must not be written through an item schema.

The 12×16-byte data previously shown here belongs solely to the unresolved
technique/skills candidate. Sharing an address does not create an item schema.

---

## 14. Effect/stat progression (historical levels slug, 0x5459C8)

**Format:** 45 × 12 bytes: target type, reserved byte, two base values, two
per-level values, and a reserved u16. Consumers calculate
`base + per_level*(slot_level-1)`. The old base was record 1 and crossed into
the skills table.

---

## 15. Runtime handler pairs (historical map-events slug, 0x53E698)

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

## 17. Sprite definition/animation pairs (historical map-sprites slug, 0x53F140)

**Format:** 43 × 8-byte pointer pairs. `0x08080B08→0x08063494→0x080625A4`
indexes the selected ID and installs both pointers in a sprite task. The old
`0x53F1DC` base was pair 19 `+4`, not a 47-map table.

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

## 19. Motion/effect parameters (historical palettes slug, 0x53EE98)

**Format:** 15 × five signed halfwords. Three task consumers use stride 10 and
pass the fields to `0x08080218`; record 14 begins with `-1` and terminates the
chain. The old `0x53F138` RGB555 interpretation is revoked.

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

## 21. Nested resource descriptors (0x596F0C)

**Format:** 5 × 16 bytes, four resource pointers per descriptor. The 16-byte
path through `0x080625A4` indexes ID×16 and installs/copies the fields into a
runtime sprite object. The old 20-u32 view merely flattened the records.

---

## 22. Message dispatcher code (legacy `sappy-engine` slug, 0x079668)

**Format:** Code region (not a data table)  
**Entry Size:** N/A  
**Semantics:** Message-selection dispatcher at `0x08079668` (file offset
`0x079668`). Values `0x80..0xE3` index the 100-entry table at `0x08599634`;
the selected pointer is passed to message-object setup at `0x08066758` and
text parsing at `0x0806626C`. Values `0x64..0x67` select four pointers from the
caller's state. The former Sappy/audio interpretation is revoked.

| Field | Type | Description |
|-------|------|-------------|
| code | bytes | Thumb instruction bytes |
| commands | dict | Command ranges and their meanings |

---

## 23. Save State (0x53D848)

**Format:** u32[2] × 10 — 10 save field entries (7 unique)  
**Entry Size:** 8 bytes  
**Semantics:** Save table mapping EWRAM buffers and variable payload lengths to
cumulative SRAM records. Each record is a 19-byte identity header, the payload,
and one `~sum(payload)` checksum byte. Handler `0x08068684` supports save/load;
an in-game slot-1 save and cold restore are runtime verified.

| Field | Type | Description |
|-------|------|-------------|
| ewram_addr | u32 | EWRAM buffer address |
| payload_length | u32 | Payload bytes; next SRAM record advances by this value + 0x14 |

---

## 24. Skills (0x545BE4)

**Format:** 94 × 16-byte skill/technique templates
**Entry Size:** 16 bytes
**Evidence:** code verified at `0x0806D910`

The consumer indexes `0x08545BE4 + skill_id*16` and copies bytes `+0..+9` to
the runtime structure. Bytes `+0x0A..+0x0F` are preserved losslessly but are
not copied by this initializer. Previous u16 field names derived from the
misbased `0x546100` slice are revoked pending runtime UI/action correlation.

---

## 25. Sprite Animations (disproved alias at 0x53F200)

The former 38 u32 words exactly flatten sprite definition/animation pair
records 24..42. This bank is an empty, write-disabled tombstone superseded by
the canonical `map-sprites` bank.

---

## 26. Primary chapter-flow scripts (0x60C74)

**Format:** 56 × u32 script pointer; entry 0 is null

`0x0808F544` indexes this table by scenario ID when chapter state `+0x18` is
zero and passes the script to `0x080977B8`. Runtime scenario 39 selected
`0x08031020`; opcode `1A 28 02 00` at `0x08031070` wrote battle ID 40.

---

## 27. Alternate chapter-flow scripts (0x60D54)

Same 56-entry format and consumer, selected when state `+0x18` is nonzero.
The table identity is code verified; an alternate-route live sample is pending.

## 28-30. Disproved Story C/D/E slices

These also begin at real descriptor `+4`. Their `0x800000NN` headers at
`0x538FEC`, `0x53AB74`, and `0x53C3BC` exactly account for the
former pointer counts. `0x0809AAC0`-family consumers select them through the
`0x465B70` object/resource master table. These three banks are write-disabled
tombstones. The equivalent old `story`/`story-b` slices are also disproved, but
their catalog slugs have been reused for the real flow tables above.

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

## 32. Units / Character Definitions (0x54241C)

**Format:** 63 × 0xB4 byte character definition records
**Entry Size:** 180 bytes
**Semantics:** Character definition table indexed by character ID. Code at
`0x0806D4A0` reads `0x0854241C + character_id*0xB4` while creating WRAM
character templates. The old `0x53F298` unit-ID interpretation was revoked;
that table is a separate u16 object/rendering offset lookup.

| Field | Type | Description |
|-------|------|-------------|
| character_id | derived | Table index, not stored as a record byte |
| active_flag | u8 +0 | 0 for sentinel row 0, 1 for active definitions |
| template_02/03/04/05/06/08_base | u8 +1..+6 | Base values consumed by `0x0806D964`; names preserve proven template destinations |
| template_0a_base | u16 +8 | Copied to runtime template +0x0A |
| template_0e_base | u16 +0x0A | Added to growth result and written to template +0x0E |
| primary_slots | 15×4 bytes +0x0C | ID, initial state, unlock level, reserved; copied to template +0x14 array |
| secondary_slots | 24×4 bytes +0x48 | Same layout; copied to template +0x50 array |
| filtered candidate IDs | 9 bytes +0xA8 | Filtered through `0x0808FA34` into template +0xB1 list |
| raw_hex | bytes | Complete 0xB4 record retained losslessly and guarded for writeback |

Player-facing stat labels remain intentionally unset. The persistent
`rom_character_definitions` mirror supports exact-record writes only after
immutable-base, offset, length, sentinel and active-flag checks.

---

## Verification Levels

- **static_verified**: Offset and format confirmed by hex analysis
- **code_verified**: Cross-referenced with Thumb disassembly
- **dynamic_verified**: Confirmed via mGBA runtime execution
