# Resource Locations

Known addresses for graphics, palette, and audio resources in the ROM.

## Battle Map Tilesets

Defined in battle config table at ROM `0x0853D910` (8 entries × 32 bytes).
Entry access: `base_file = 0x53D914 + chapter_id * 32`.

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

**Status**: 10 PCM samples located and exported as WAV.

### DirectSound Sample Format

```
+0x00  u8   type        0x00 = uncompressed signed 8-bit PCM
+0x01  u8   loop_flag   0x00 = no loop, 0x40 = loop
+0x02  u16  freq        natural pitch / frequency (Hz)
+0x04  u32  loop_start  sample index where loop begins
+0x08  u32  size        total sample count
+0x0C  s8[] data        signed 8-bit mono PCM
```

GBA m4a base playback rate: **13379 Hz**. Exported WAV uses this rate by default.

### Found Samples

| # | File offset | Freq | Size | Loop | Notes |
|---|---|---|---|---|---|
| 0 | `0x09E208` | 12284 Hz | 12284 | no | Short SFX/instrument |
| 1 | `0x0A1F5C` | 16383 Hz | 16383 | no | Short SFX/instrument |
| 2 | `0x0ED268` | 8202 Hz | 129040 | **YES** (pos 15) | BGM loop layer |
| 3 | `0x177560` | 8944 Hz | 65520 | no | Medium SFX |
| 4 | `0x1AA5A4` | 8176 Hz | 983040 | no | Large BGM track (~2 min) |
| 5 | `0x2DA7F8` | 26495 Hz | 4081 | no | Short SFX |
| 6 | `0x2DDBD8` | 3840 Hz | 61815 | no | Medium SFX |
| 7 | `0x2ED2FC` | 21573 Hz | 1911 | no | Very short SFX |
| 8 | `0x2F333C` | 4671 Hz | 999713 | no | Large BGM (~3.5 min) |
| 9 | `0x3ED624` | 4120 Hz | 850944 | no | Large BGM (~3.4 min) |

Total extracted: ~3 MB PCM data. Extraction tool: `tools/extract_audio.py`.

### Notes

- No standard sound driver signature found (MP2000/Sappy/GAX not present)
- Likely uses a custom or early Nintendo sound driver
- Samples 4, 8, 9 are long background music tracks at low sample rates (4–8 kHz)
- WAV export quality is limited by the original low sample rate; expected to sound rough
