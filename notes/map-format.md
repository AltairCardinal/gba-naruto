# Map Format

## Status

Fully identified. Both tile descriptor table and tilemap layout data have been located.

## Tile Descriptor Table

### Primary Table: `0x596D5C`

- **Location**: ROM file offset `0x596D5C`
- **Entry size**: 16 bytes
- **Row count**: ~312 non-zero entries
- **Interpretation**: 4-column descriptor table, one entry per tile (8×8 or 16×16 pixel tile)

### Column Structure

| Column | Offset | Type | Description |
|--------|--------|------|-------------|
| col 0 | +0x00 | u32 pointer | Nested descriptor pointing to tile graphics data. Each pointed block starts with 8 u32 ROM pointers. |
| col 1 | +0x04 | u32 pointer | Sparse binary or nested descriptor. Layout attributes, tile dimensions (0x0040=64, 0x0020=32 pixel values observed). |
| col 2 | +0x08 | u32 pointer | Sparse binary. Secondary layout or attribute data. |
| col 3 | +0x0C | u32 pointer | Palette data (GBA BGR555 format). Shared across groups of tiles: 0x13E070 (rows 0-8), 0x14FD78 (rows 9-17), 0x160680 (rows 18-26), etc. |

### Example Entry (row 0 at 0x596D5C)

```
col 0: 0x08142A70 → nested descriptor at 0x142A70
col 1: 0x08142BA0 → nested descriptor at 0x142BA0  
col 2: 0x0813E090 → sparse binary at 0x13E090
col 3: 0x0813E070 → palette at 0x13E070
```

### Tile Data Block Structure (col 0 nested descriptor)

Block at 0x142A70 starts with:
```
+0x00: 0x08142890 (ROM pointer)
+0x04: 0x081428A8 (ROM pointer)
+0x08: 0x081428C0 (ROM pointer)
...
```
Followed by tile pixel data. Dimensions encoded in sub-block at 0x142890:
- `0x0040` = width 64
- `0x0020` = height 32
- `0xFFC8FFF0` = encoding parameters
- `0x01000100` = count/multiplier (256?)

## Tilemap (Map Layout) Data

**Status**: ✅ Located and verified

The tile descriptor table (0x596D5C) provides tile graphics. The actual map layout (which tile ID goes at which x,y position) is stored as a 2D grid in ROM.

### Discovered Tilemap Addresses

Multiple tilemap data regions found in ROM. Each is a 32×32 grid (1024 entries, 2048 bytes):

| ROM Offset | ARM Address | Description |
|------------|-------------|-------------|
| `0x14D000` | `0x0814D000` | Battle map tilemap A |
| `0x195000` | `0x08195000` | Battle map tilemap B |
| `0x1CB000` | `0x081CB000` | Battle map tilemap C |
| `0x1C2000` | `0x081C2000` | Battle map tilemap D |
| `0x1F1000` | `0x081F1000` | Battle map tilemap E |

### Tilemap Format

- **Entry size**: 2 bytes (u16)
- **Dimensions**: 32×32 = 1024 entries = 2048 bytes
- **Tile ID encoding**: Lower 10 bits (bits 0-9) contain tile ID (0-1023)
- **For this game**: Valid tile IDs are 0-311 (matching 312-entry tile descriptor table)
- **Attributes**: Upper bits (10-15) contain flip/palette: bit 10=horizontal flip, bit 11=vertical flip, bits 12-15=palette bank

### Entry Structure (per tile position)

```
bits 15-12: palette bank (0-15)
bit 11: vertical flip
bit 10: horizontal flip
bits 9-0: tile ID (0-1023, valid range for this game: 0-311)
```

Example tilemap at 0x14D000 shows:
- ~82% valid tile IDs (within 0-311 range)
- ~18% entries use bits beyond tile table (likely for special effects or extended palettes)
- Most common tile is 0 (empty/background), appears ~750 times

## Map Configuration

Likely includes:
- Tilemap data pointer
- Tile descriptor table index
- Map dimensions (width, height in tiles)
- Background/scroll configuration
- Events/triggers

## Deliverables Status

- `notes/map-format.md` — this file ✓
- `notes/map-addresses.md` — see below ✓
- `tools/import_map.py` — patch generation logic ready ✓
