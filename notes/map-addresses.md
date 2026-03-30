# Map Addresses

## Status

Tilemap layout data (2D tile ID grid) has been located and documented below.

## Confirmed Addresses

| ROM File Offset | ARM Address | Description |
|----------------|-------------|-------------|
| `0x596D5C` | `0x0896D5C` | Primary tile descriptor table (312 rows × 16 bytes) |
| `0x13E070` | `0x0813E070` | Palette data (shared, rows 0-8 of tile table) |
| `0x13E090` | `0x0813E090` | Sparse binary/tile attribute data |
| `0x142890` | `0x08142890` | Tile data sub-block (dimensions: 64×32, encoding params) |
| `0x142A70` | `0x08142A70` | Nested tile descriptor (row 0 col 0) |
| `0x142BA0` | `0x08142BA0` | Nested tile descriptor (row 0 col 1) |
| `0x14FD78` | `0x0814FD78` | Palette data (shared, rows 9-17) |
| `0x160680` | `0x08160680` | Palette data (shared, rows 18-26) |

## Related Tables

| ROM File Offset | ARM Address | Rows | Entry Size | Description |
|----------------|-------------|------|-----------|-------------|
| `0x596FA8` | `0x0896FA8` | ~100+ | 16 | Visual resource descriptor table |
| `0x5A4E14` | `0x085A4E14` | 155 | 16 | Visual resource bank |
| `0x5A2B08` | `0x085A2B08` | 62 | 16 | Compressed tile/binary blocks |
| `0x599280` | `0x0899280` | 37 | 16 | Compressed binary blocks |
| `0x5995AC` | `0x08995AC` | 32 | 16 | Compressed binary blocks |

## Tilemap Layout Data (2D Tile Grid)

**Status**: ✅ Located

Tilemap data stores the 2D grid of which tile IDs appear at each x,y position.

| ROM Offset | ARM Address | Size | Description |
|------------|-------------|------|-------------|
| `0x14D000` | `0x0814D000` | 2048 bytes | Battle map tilemap #1 (32×32) |
| `0x195000` | `0x08195000` | 2048 bytes | Battle map tilemap #2 (32×32) |
| `0x1CB000` | `0x081CB000` | 2048 bytes | Battle map tilemap #3 (32×32) |
| `0x1C2000` | `0x081C2000` | 2048 bytes | Battle map tilemap #4 (32×32) |
| `0x1F1000` | `0x081F1000` | 2048 bytes | Battle map tilemap #5 (32×32) |

Each tilemap is a flat 2D array. Access tile at (row, col) as:
- byte_offset = (row * 32 + col) * 2
- tile_id = read_u16LE[offset] & 0x3FF

## Map Configuration (To Discover)

- Map configuration struct (dimensions, scroll bounds, events)
- Map script/trigger data
