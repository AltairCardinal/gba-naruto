# Battle Scenario Config Table

## ROM Location
- **ARM address**: `0x0853D910`
- **File offset**: `0x53D910`
- **Entry size**: 16 bytes
- **Total entries**: 16 ( ARM `0x0853D910` through `0x0853D9F0`)

## Entry Format (16 bytes each)
| Offset | Type  | Name       | Description                              |
|--------|-------|------------|------------------------------------------|
| +0x00  | u16   | tiles_x    | Battle arena width in tiles              |
| +0x02  | u16   | tiles_y    | Battle arena height in tiles             |
| +0x04  | u32   | ptr1       | ROM pointer to battle map / enemy layout |
| +0x08  | u32   | ptr2       | ROM pointer to additional data           |
| +0x0C  | u16   | flag       | Scenario flag / secondary pointer        |
| +0x0E  | u16   | extra      | Extra data / continuation                |

> Note: Entries with `tiles_x=0` are padding or empty entries.

## Parsed Table

| Entry | Tiles (WxH) | ptr1 (ROM)       | ptr2 (ROM)       | flag    | Notes     |
|-------|--------------|------------------|------------------|---------|-----------|
| 0     | 92 x 64     | `0x080B9F80`    | `0x080BD608`    | 0xD70C  |           |
| 1     | (invalid)   | `0x080BE10C`    | `0x080BF250`    | 0x0001  | padding   |
| 2     | 60 x 30     | `0x080BF318`    | `0x080C166C`    | 0x1710  |           |
| 3     | (invalid)   | `0x080C18EC`    | `0x080C1CAC`    | 0x0001  | padding   |
| 4     | 36 x 36     | `0x080C1CF8`    | `0x080C416C`    | 0x4210  |           |
| 5     | (invalid)   | `0x080C43E4`    | `0x080C4844`    | 0x0001  | padding   |
| 6     | 36 x 40     | `0x080C4880`    | `0x080C5F24`    | 0x5FC8  |           |
| 7     | (invalid)   | `0x080C6140`    | `0x080C6410`    | 0x0001  | padding   |
| 8     | 36 x 40     | `0x080C6450`    | `0x080C8454`    | 0x84F8  |           |
| 9     | (invalid)   | `0x080C86D8`    | `0x080C8ABC`    | 0x0001  | padding   |
| 10    | 36 x 46     | `0x080C8AF4`    | `0x080CAA94`    | 0xAB30  |           |
| 11    | (invalid)   | `0x080CAD38`    | `0x080CB138`    | 0x0001  | padding   |
| 12    | 60 x 32     | `0x080CB18C`    | `0x080CCB54`    | 0xCC28  |           |
| 13    | (invalid)   | `0x080CCE1C`    | `0x080CD21C`    | 0x0002  | padding   |
| 14    | 60 x 32     | `0x080CD260`    | `0x080D0054`    | 0x0154  |           |
| 15    | (invalid)   | `0x080D0638`    | `0x080D1238`    | 0x0102  | padding   |

## Valid Battle Scenarios
- Entry 0: 92×64 tiles — large arena (ptr1 → `0x080B9F80`)
- Entry 2: 60×30 tiles — medium arena (ptr1 → `0x080BF318`)
- Entry 4: 36×36 tiles — small arena (ptr1 → `0x080C1CF8`)
- Entry 6: 36×40 tiles — small arena (ptr1 → `0x080C4880`)
- Entry 8: 36×40 tiles — small arena (ptr1 → `0x080C6450`)
- Entry 10: 36×46 tiles — medium arena (ptr1 → `0x080C8AF4`)
- Entry 12: 60×32 tiles — medium arena (ptr1 → `0x080CB18C`)
- Entry 14: 60×32 tiles — medium arena (ptr1 → `0x080CD260`)

## WRAM Allocation Table
Located at ARM `0x0853D848` (file offset `0x53D848`):
- `{u16 wram_offset, u16 size}` pairs
- 8 entries total

| Entry | WRAM Address   | Size (bytes) |
|-------|---------------|-------------|
| 0     | `0x02002E30` | 514          |
| 1     | `0x020040AC` | 514          |
| 2     | `0x02002E30` | 514          |
| 3     | `0x020040AC` | 514          |
| 4     | `0x02006804` | 8            |
| 5     | `0x02006BC8` | 24           |
| 6     | `0x020040C0` | 6084         |
| 7     | `0x02002E30` | 4732         |

> Note: Some WRAM addresses overlap — the same WRAM region is reused for different purposes during battle phases.
