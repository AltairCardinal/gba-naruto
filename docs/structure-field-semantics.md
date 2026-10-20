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

**Format:** 87 × 16-byte active-action numeric templates
**Entry Size:** 16 bytes
**Evidence:** code verified at `0x0807557E→0x0806D85C`

The consumer copies the selected record into a runtime action structure. Known
fields are `+0` cost kind, `+1` display-animation family, `+2` effect
code/flags, `+3` target policy/flags, `+4` potency, `+5` hit count, `+6`
success rate, packed range/shape bytes `+7/+8`, `+9` duration and `+A..+B`
scalar resource cost. Byte `+0x0C` chooses a level-growth destination
(`+4..+9` for types 1..6); u16 `+0x0E` is the increment multiplied by
`level-1`. Type 7 performs no growth adjustment; `+0x0D` remains unnamed.

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

### Proven dialogue glyph sources (0x53D644 and 0x53D73C)

The 26-entry SJIS table at `0x53D644` uses `<HBBI>` records:
`lower`, `range_size`, `aux`, and `source_ptr`. Entries 0-24 have `aux=0`;
entry 25 has `aux=4`. Each logical SJIS glyph is a 32-byte packed-2bpp record
containing two ordered 16-byte, 8×8 half-tiles. The source record is
layout-neutral; `0x08065EB8` expands the halves to two 4bpp tiles.

The two-entry single-byte table at `0x53D73C` uses `<BBHI>` records. Each
logical glyph is one 16-byte packed-2bpp, 8×8 source record; `0x080660A4`
expands it to one 4bpp tile. Both branches use:

`output_index = source_2bpp + (((arg1 & 1) + 2) << 2)`.

The enclosing function at `0x08089310` contains a cache/expansion path anchored
at `0x0808942C`; its exact calls at `0x080894DE` and `0x080894A8` supply
`arg1=1` for SJIS (indices 12-15) and `arg1=0` for the byte branch (indices
8-11). In the localized base
ROM, these source records already contain the Chinese replacement pixels:
known group0 codes such as `0x88CF`, `0x8FC2`, and `0x9A6A` render `什`, `么`,
and `真` according to the historical screenshot alignment. The ROM lookup
independently proves their source pointers and pixel records, not the Unicode
labels themselves. In particular, `0x8B62` is a non-empty unresolved glyph;
the following independent `0x0A` byte is the newline control.
`0x08065FEE` and `0x08065FFE` only return adjacent entries in a temporary
tile-ID pair; they do not write the final tilemap. The verified tilemap
consumers at `0x0806626C`, `0x0808CE8C`, and `0x0808CF08` place half 1 one row
below half 0 and advance one cell horizontally, proving an 8×16 vertical
layout for those consumers. Runtime RGB colors and a complete 4410-code
Unicode naming catalog remain unresolved; group0 is a text-pointer group, not
evidence of another font.

---

## 12. Function Pointers (0x53D5F4)

**Status:** runtime verified. Natural profile navigation selected callback ID 2
twice from `0x0853D5F8` and read `0x08061C99`. Replacing only that entry with
the adjacent valid wrapper changed the visible UI task transition. Arbitrary targets
remain unsafe: write-back must preserve the Thumb bit and the validated code range.

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
**Semantics:** Battle-map resource headers. All six non-null resource pointers
address GBA LZ77 streams. `0x08068FF0` consumes graphics, palette, primary
layout and 2×2 metatile definitions; `0x08069264` consumes the collision grid.
The static layout uses `(width/4)×(height/2)` little-endian u32 cells. Each
cell's low/high u16 selects the left/right 2×2 metatile; each metatile is four
standard GBA BG u16 entries in TL/TR/BL/BR order.

> **CORRECTED 2026-10-20** — 本节原先的字段顺序
> （width/height 在 +0x00/+0x04、tileset 在 +0x08、flags 在 +0x18）**与实测不符**。
> 正确布局已按 LZ77 解压长度逐字段验证：
> `+0x00 u16 原始宽 / +0x02 u16 原始高 / +0x04 tile gfx / +0x08 palette /
> +0x0C layer0 tilemap / +0x10 layer1 tilemap / +0x14 metatiles /
> +0x18 terrain / +0x1C 剧情底图ID`。
> 宽÷4、高÷2 得图块尺寸；terrain 解压长度 = 宽×高×2 精确吻合。
> 复现：`tools/probe_external_re_claims.py`；
> 详见 `notes/external-konoha-workshop-gap-20261020.md` §2.1。

| Field | Type | Description |
|-------|------|-------------|
| `+0x00` raw_width | u16 | 原始宽（÷4 = 图块宽） |
| `+0x02` raw_height | u16 | 原始高（÷2 = 图块高） |
| `+0x04` tile_gfx_ptr | u32 | Pointer to tile graphics data (LZ77) |
| `+0x08` palette_ptr | u32 | Pointer to palette data (LZ77) |
| `+0x0C` layer0_ptr | u32 | Pointer to layer 0 tilemap (LZ77) |
| `+0x10` layer1_ptr | u32 | Pointer to layer 1 tilemap (LZ77, may be 0) |
| `+0x14` metatile_ptr | u32 | Pointer to metatile table (LZ77, 8 bytes/entry) |
| `+0x18` terrain_ptr | u32 | Pointer to terrain/passability table (LZ77, u16/cell) |
| `+0x1C` background_id | u8 | Story background id |

> **命名沿革（2026-10-21 合并）**：重制侧此前用另一套名字描述同一批槽位
> —— `width` / `height`（`+0x00`/`+0x02`）、`bg_palette_ptr`（`+0x08`）、
> `primary_layout_ptr`（`+0x0C`）、`alternate_layout_ptr`（`+0x10`，
> 33 行为 null）、`metatile_attributes_ptr`（`+0x14`）、
> `collision_grid_ptr`（`+0x18`）、`flags`（`+0x1C`，u32）。
> **槽位偏移两套完全一致**，差别只在读法与宽度：
> 逆向侧按 `0x08068FF0` 加载器反汇编 + LZ77 解压长度逐字段验证，
> 确认 `+0x00/+0x02` 是**原始**宽高（÷4 / ÷2 才是图块数）、
> `+0x08` 是调色板、`+0x0C/+0x10` 是 layer0/layer1 两层 tilemap、
> `+0x18` 是通行（terrain）表、`+0x1C` 是 1 字节剧情底图 ID。
> 上表采用逆向侧的修正读法；`tools/extract_tileset.py`（重制侧）仍用
> 重制侧命名，两边指同一批槽位。

`artifacts/map-canvases-v1/` preserves all 47 primary canvases, all 14
non-null alternate candidates, expanded u16 tilemaps and 166 content-deduplicated
raw resources. Runtime selection is proven only for map 41 primary; alternate
selection, runtime scrolling/chunking and dynamic occupancy overlays remain
outside this static export.（2026-07-13 证据等级复核：maps 已是 **runtime** ——
宽度受控 row-40 36→32 A/B，row-41 严格战斗采样逐项比对 VRAM tile gfx /
BG 调色板 / primary layout / metatile 定义 / alternate-layout 跳过 / 通行性。）

---

## 17. Sprite definition/animation pairs (historical map-sprites slug, 0x53F140)

**Format:** 43 × 8-byte pointer pairs. `0x08080B08→0x08063494→0x080625A4`
indexes the selected ID and installs both pointers in a sprite task. The old
`0x53F1DC` base was pair 19 `+4`, not a 47-map table.

`definition_ptr[0]` points to a sentinel-terminated component list. Each
component is `0x14` bytes; signed `+0x00 == -1` ends the list, otherwise that
halfword is the tile offset. Fields `+0x08/+0x0A` are width/height and accept
`8/16/32/64`. The following 43-halfword table at `0x53F298` supplies the
per-ID runtime tile-base offset; it is not a character-ID table.

The pixels and palette are not stored in the pair table, but they are statically
linked by the loader at `0x08080A48`: ROM LZ77 `0x0812F298` expands to 49
4bpp OBJ tiles and `0x0812F584` expands to one 16-color palette. The 43
tile-base offsets plus component tile offsets cover all 49 tiles exactly once:

```text
ROM graphics -> 0x06010000 + u16[0x0202CA24]*32
ROM palette  -> 0x05000200 + u8[0x0202CA26]*32
task.tile_base = u16[0x0202CA24] + u16[0x53F298 + id*2]
attr2.tile = task.tile_base + component.tile_offset
attr2.palette = u8[0x0202CA26] << 12
OBJ tiles = 0x06010000 + attr2.tile*32
OBJ palette = 0x05000200 + u8[0x0202CA26]*32
```

The complete 43-entry/45-component metadata, 49-tile pixels, palette, per-ID
PNGs, and optional scene-overwrite verification boundary are recorded in
`notes/sprite-definition-runtime-chain-20260729.md`.

---

## 18. Visual variant matrix (historical menu-ui slug, 0x5A4DEC)

**Format:** 63 × five `(LZ graphics pointer, palette pointer)` variants.
`0x08096138` selects `record_id*40 + variant*8`; variant 5 uses the special
pair at `0x5A4DE4`. The former 20-u32 view was canonical records 61–62.

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

> **CONFLICT 2026-10-20 — 需重新定位**
> `0x08599634` (file `0x599634`) 实测是**忍具名称文本指针表**（u32[93]，
> 每项指向一段 SJIS 名称串），**不是**音频索引表。
> 因此 "Commands 0x80-0xE3 → 0x08599634" 这条映射存疑，
> Sappy dispatcher 的真实索引表需要重新定位。
> 复现：`tools/probe_external_re_claims.py`；
> 详见 `notes/external-konoha-workshop-gap-20261020.md` §4 C3。

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

## 24. Ninja tools / power-ups (legacy path `skills`, 0x545BE4)

**Format:** 94 × 16-byte ninja-tool/power-up numeric templates
**Entry Size:** 16 bytes
**Evidence:** runtime verified through the natural high-bit ninja-tool list and
`0x08070906→0x0806D910`

The consumer indexes `0x08545BE4 + ninja_tool_id*16` and copies bytes `+0..+9` to
the runtime structure. Bytes `+0x0A..+0x0F` are preserved losslessly but are
not copied by this initializer. Previous u16 field names derived from the
misbased `0x546100` slice are revoked. Natural ninja-tool 1 (十字手里剑) maps `+4` attack power,
`+5` hit count, `+6` success-rate percentage, packed `+7` distance/line shape,
and `+8` range. A single-byte `+4:6→7` patch changed only visible `6x3→7x3`.
Offsets `+2/+3/+9` remain unnamed.

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
`0x08031020`; bytes `1A 28 02 00` at `0x08031070` decode as the three-byte
`SetBattle(40, mode=2)` followed by the independent one-byte `End`, and wrote battle ID 40.

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

## 33. Battle effect graphics/palette pairs (0x59911C)

**Format:** 19 × 8-byte records (`u32 graphics_pointer`, `u32 palette_pointer`)
**Entry Size:** 8 bytes
**Verification:** code verified and all static payloads independently exported

Group 0 is an all-zero sentinel. Groups 1 through 18 point to valid GBA LZ77
streams. Every graphics stream decompresses to 4bpp tile-aligned bytes and every
palette stream decompresses to one 16-color BGR555 palette. The builder at
`0x0807FDCC..0x0807FE2C` consumes the selected resource pair; the selector at
`0x0807FE2C..0x080800A4` binds a sequence to a group. Group 18 is independently
bound to battlefield-object expiry sequence 7.

The complete ROM-derived binaries, indexed-color atlases and hashes are in
`artifacts/battle-effect-resource-pairs-v1/`. The complete sequence-to-group
join is separately proven in `artifacts/battle-effect-sequence-bindings-v1/`.
The resource table alone proves static pixel and palette identity; neither
artifact yet proves complete OAM composition, frame holds, blend behavior or
audio binding.

---

## 34. Battle effect sequence selector and descriptors (0x53E596 / 0x53EF30)

**Selector format:** 256 × `u8` sequence IDs
**Descriptor format:** 22 × 24-byte records
**Verification:** code verified and independently exported

The runtime-state selector at `0x0853E596` is indexed by a full u8. Its first
87 entries join active action IDs 0..86 to the same IDs used by the numeric
template table at `0x08545458`; the sequence is not derived from any template
field. Encoded action IDs `0x80..0xDD` preserve the high bit through event
`+0x0C` and runtime state `+0x770`, while their low seven bits index all 94
ninja-tool templates at `0x08545BE4`; those IDs therefore join to selector
entries 128..221. The descriptor table covers IDs 0..21 at
`0x0853EF30..0x0853F140`.

| Field | Type | Description |
|-------|------|-------------|
| resource_group_ids | `u32[4]` +0x00 | Zero-terminated group IDs indexing `0x0859911C`; current records use at most slot 0 |
| init_once_callback | Thumb pointer +0x10 | Stored at task +0xAC, invoked once, then cleared |
| tick_callback | Thumb pointer +0x14 | Stored at task +0xB0 and invoked on every scheduler pass |

The complete 256 selector entries, 87 active-action joins, 94 ninja-tool joins,
22 descriptors and 67 direct selector callsites are in
`artifacts/battle-effect-sequence-bindings-v1/`. Callback pointer identity and
scheduler roles are proven. The child animation tables selected by those
callbacks are separately closed in
`artifacts/battle-effect-sprite-animations-v1/`: 18 group definition/animation
pairs expand to 178 frame definitions, 437 components and 23 timelines with
193 exact hold keyframes. Callback spawn plans are complete, including the
14-child motion fan-out used by sequences 2, 3 and 18. For each motion-table
record, sequence 2 passes `(render_attributes << 8) | 0x400` to the child
constructor, sequence 3 passes `render_attributes << 8`, and sequence 18
passes zero. Final screen-space
mirroring, priority, affine rasterization, sequence-1 RNG coordinates and the
parent-release 0/1 scheduler-tick boundary remain unresolved.

---

## Verification Levels

- **static_verified**: Offset and format confirmed by hex analysis
- **code_verified**: Cross-referenced with Thumb disassembly
- **dynamic_verified**: Confirmed via mGBA runtime execution
