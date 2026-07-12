# Resource Locations

Known addresses for graphics, palette, and audio resources in the ROM.

## Battle Map Tilesets

Defined in the map header table at ROM `0x0853D910` (47 entries × 32 bytes).
Entry access: `base_file = 0x53D910 + map_id * 32`.

### Corrected Entry Field Order (32 bytes = 8 × u32)

| Offset | Field | Type | Description |
|---|---|---|---|
| +0x00 | tile_gfx_ptr | u32 ARM ptr | LZ77 compressed 4bpp tile graphics |
| +0x04 | tilemap_ptr | u32 ARM ptr | LZ77 compressed tilemap layout |
| +0x08 | tilemap_alt_ptr | u32 ARM ptr | LZ77 compressed alternate tilemap |
| +0x0C | extra_ptr | u32 ARM ptr | Optional extra data (0 = absent) |
| +0x10 | palette_ptr | u32 ARM ptr | LZ77 compressed BG palette (actual colors) |
| +0x14 | palette2_ptr | u32 ARM ptr | LZ77 compressed attribute data (all 0x8000, not colors) |
| +0x18 | flags | u32 | 0x01=normal, 0x02=alt, 0x102=special |
| +0x1C | packed_dims | u32 | u16 width_tiles (low) + u16 height_tiles (high) |

> **Note**: earlier notes had `u16+u16 dim` at +0x00 — that was wrong. Dimensions are at +0x1C.

### Palette Notes

- `palette_ptr` (fields[4]) decompresses to the actual 4bpp BG palette:
  - BGR555 u16 values, bit 15 = transparency flag (must be masked off: `bgr &= 0x7FFF`)
  - Contains 16 sub-palettes of 16 colors each = 256 colors = 512 bytes minimum
  - Entry 0 palette decompresses to 6160 bytes (may include tilemap attributes appended)
- `palette2_ptr` (fields[5]) is **not** a color palette — decompresses to all 0x8000 values, likely transparency/attribute data for the secondary layer.

### Per-Entry Addresses

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
