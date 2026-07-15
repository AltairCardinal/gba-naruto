# Resource Locations

Known addresses for graphics, palette, and audio resources in the ROM.

## Battle Map Tilesets

Defined in the map header table at ROM `0x0853D910` (47 entries × 32 bytes).
Entry access: `base_file = 0x53D910 + map_id * 32`.

### Consumer-proven entry field order (32 bytes)

| Offset | Field | Type | Description |
|---|---|---|---|
| +0x00 | width/height | u16+u16 | map dimensions |
| +0x04 | tile_gfx_ptr | u32 ARM ptr | LZ77 gfx → VRAM buffer |
| +0x08 | bg_palette_ptr | u32 ARM ptr | LZ77 BG palette → `0x05000000` |
| +0x0C | primary_layout_ptr | u32 ARM ptr | coarse layout → `0x0201BE2C` |
| +0x10 | alternate_layout_ptr | u32 ARM ptr | optional coarse layout → `0x0201CE2C` |
| +0x14 | metatile_attributes_ptr | u32 ARM ptr | metatile definitions → `0x0201DE2C` |
| +0x18 | collision_grid_ptr | u32 ARM ptr | passability grid → `0x02021E2C` |
| +0x1C | flags | u32 | byte `+0x1D` selects a display-register value |

> **2026-07-12 correction**: the earlier shifted `base+4` view was wrong.
> `0x08068FB4/0x08068FF0/0x08069264` all agree on the unshifted row above.

### Palette Notes

- header `+8` decompresses to the actual 4bpp BG palette:
  - BGR555 u16 values, bit 15 = transparency flag (must be masked off: `bgr &= 0x7FFF`)
  - Contains 16 sub-palettes of 16 colors each = 256 colors = 512 bytes minimum
  - Entry 0 palette decompresses to 6160 bytes (may include tilemap attributes appended)
- header `+14` is metatile/attribute data, not colors; header `+18` is the
  collision/passability grid.

### Historical per-entry addresses (revoked shifted IDs)

The table below predates the 47-row correction and is retained only to explain
old artifact names. Do not use its IDs or palette column for new probes.

| chapter_id | tile_gfx_ptr (file) | palette_ptr (file) | tiles | map dims |
|---|---|---|---|---|
| 0 | 0x0B9F80 | 0x0BE10C | 672 | 60×30 |
| 1 | 0x0BF318 | 0x0C18EC | 320 | 36×36 |
| 2 | 0x0C1CF8 | 0x0C43E4 | 352 | 36×40 |
| 3 | 0x0C4880 | 0x0C6140 | 224 | 36×40 |
| 4 | 0x0C6450 | 0x0C86D8 | 288 | 36×46 |
| 5 | 0x0C8AF4 | 0x0CAD38 | 320 | 60×32 |
| 6 | 0x0CB18C | 0x0CCE1C | 256 | 60×32 |
| 7 | 0x0CD260 | 0x0D0638 | 672 | 60×32 |

## Tile Descriptor Table

- **Location**: ROM file `0x596D5C`
- **Entries**: 312 × 16 bytes
- **Purpose**: Sprite/animated tile descriptors (character sprites, UI elements)
- **Structure**: 4 × u32 ARM pointers per entry:
  - col0: nested descriptor → sprite rendering sub-blocks
  - col1: layout attributes
  - col2: secondary attribute data
  - col3: palette pointer (BGR555, raw uncompressed, 16 colors)
- **Shared palettes**: rows 0–8 → `0x13E070`, rows 9–17 → `0x14FD78`, rows 18–26 → `0x16068`0, etc.
- **Analysis tool**: `tools/analyze_tile_table.py`

## Tilemap Data

Multiple 32×32 grid tilemaps (1024 u16 entries, 2048 bytes each):

| File offset | Description |
|---|---|
| `0x14D000` | Battle map A |
| `0x195000` | Battle map B |
| `0x1CB000` | Battle map C |
| `0x1C2000` | Battle map D |
| `0x1F1000` | Battle map E |

Format: u16 per tile — bits 9-0 = tile ID (0-311), bit 10 = H-flip, bit 11 = V-flip, bits 12-15 = sub-palette.

## Audio

**Status**: real engine, 159-ID master domain, 80 non-empty descriptors and one
live sound ID are located. The former 10 heuristic PCM hits are revoked.

### Proven locations

- sound-ID master: `0x465B70`, IDs 0..158
- non-empty IDs: 1..18, 51..54, 101..158
- descriptor/data range currently important: `0x536368..0x53D58B`
- public wrapper: `0x08061E6C`
- ID dispatch: `0x0809AAC0`
- song/track initialization: `0x0809B1F4`
- sound/FIFO/DMA initialization: `0x0809AE3C`

The heuristic `tools/extract_audio.py` scan found byte patterns resembling
DirectSound headers, but neither those headers nor their `+12` data addresses
have aligned pointer references. They are false-positive candidates and must
not be presented as samples, BGM, durations, or successful WAV extraction.
Real extraction now follows the m4a SongHeader voicegroup and track pointers.
`tools/extract_audio_assets.py` exports 217 bounded track blobs and 79 unique
pointer-reachable DirectSound WAV files under `build/audio-v2/`; the 16-byte
wave header and signed-to-unsigned PCM conversion are tested. Full chain and
runtime evidence: `notes/audio-engine-runtime-chain-20260712.md`.
