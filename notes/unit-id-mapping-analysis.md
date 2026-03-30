# Unit ID Mapping Table - Static Analysis

## Location
- **ROM file offset**: 0x0053F298
- **ARM address**: 0x0853F298

## Structure

The table at 0x53F298 contains a mix of:

### 1. Function pointer table (file 0x53F1C0 - 0x53F2CC)
68 u32 values, all pointing to ROM functions in range 0x0812Fxxx (battle system functions).
```
0x0812F9C0, 0x0812F9CC, 0x0812F9E8, 0x0812F9F4, ... (60 function pointers)
```

### 2. Unit ID pairs (file 0x53F2CC - 0x53F358)
36 u16 values arranged as 18 pairs. Each pair is (unit_or_offset, unit_or_offset).

**Unit ID pairs** (small positive values, 1-50):
| Pos | Hi | Lo |
|-----|----|----|
| 0 | 44 | 43 |
| 1 | 46 | 45 |
| 2 | 10 | 11 |
| 3 | 36 | 35 |
| 4 | 48 | 47 |
| 5 | 12 | 13 |
| 6 | 21 | 18 |
| 7 | 23 | 22 |
| 8 | 24 | (signed) |
...more pairs

**Movement offset pairs** (signed interpretation of large values):
| Pos | Hi (signed) | Lo |
|-----|-------------|-----|
| 8 | 24 | - |
| 9 | -6 | 0 |
| 10 | -7 | 4 |
| 11 | -8 | 7 |
| 12 | -6 | 9 |
| 13 | -4 | 9 |
| 14 | -2 | 7 |
| 15 | 0 | 4 |

Interpretation: Each pair is (movement_dy, movement_dx) or (unit_id_a, unit_id_b), where signed values like 0xFFFC = -4 (tile-based movement).

### 3. ROM data pointer table (file 0x53F358 - 0x53F3E0)
u32 pairs where lo = 0x0808xxxx (ROM bank marker), hi = 0x0C3D, 0x0C4D, 0x0C5D... (incrementing indices).

Pattern: each u32 = (0x0808 << 16) | (0x0C3D + n*0x10)
This appears to be a ROM function/data index table for the battle system.

## Key Findings

1. **Unit ID range**: 1-48 (from unit ID pairs)
2. **Movement offsets**: 8-directional (-8 to +4 tiles), 15 patterns
3. **Battle system functions**: 60 function pointers in ROM bank 0x0812
4. **ROM data index**: 13 indexed entries for battle data

## Missing Information

- Exact field mapping within each unit struct (needs runtime WRAM dump during battle)
- Whether unit ID pairs are indexed by slot position or sequential
- How battle configuration is loaded from ROM (appears embedded in code as literals)
- Chapter/battle scenario mapping

## Runtime Verification Status

**BLOCKED**: The existing savestate (naruto-sequel-dev.ss1) contains all-zero WRAM, indicating the game state is pre-load (title screen or before). Cannot navigate to battle state in headless mode.

Recommended: Use mgba_battle_walk.lua with a full mGBA Qt + Xvfb setup to capture actual battle WRAM data.
