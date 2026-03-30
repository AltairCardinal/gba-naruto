# Chapter Flow Format

## Status

**RESOLVED** via static analysis (2026-03-31). Runtime trace used to confirm call chain.

---

## Summary

The chapter/battle initialization flow has been fully traced through static disassembly. The key WRAM struct, the battle config table entry format, and the complete call chain are now documented.

---

## Chapter State Struct (WRAM 0x020311D4)

Base: `0x020311D4`

| Offset | Size | Purpose |
|--------|------|---------|
| +0x00  | 4    | Cleared on chapter start |
| +0x04  | 4    | Cleared on chapter start |
| +0x08  | 4    | Cleared on chapter start |
| +0x0C  | 4    | Cleared on chapter start |
| +0x16  | 1    | **Chapter/battle slot 1 ID** (copied to `0x02026805`) |
| +0x19  | 1    | **Chapter/battle slot 2 ID** (copied to `0x02026806`) |
| +0x1B  | 1    | Cleared on chapter start |

To change which chapter loads, **write to `0x020311EA`** (= base + 0x16).

---

## Battle Config Table (ROM 0x0853D910)

- File offset: `0x53D910`
- Entry count: 8 valid entries (indices 0–7)
- **Entry size: 32 bytes** (previously documented as 16 bytes — CORRECTED)
- Index formula: `entry_ptr = 0x0853D910 + 4 + chapter_id * 32`

> Note: offset +4 skips an unknown 4-byte header at the table base.

### Entry Structure (32 bytes = 8 × u32)

| Word | Offset | Content |
|------|--------|---------|
| [0]  | +0x00  | Map dimensions: `u16 height` (low) ‖ `u16 width` (high) |
| [1]  | +0x04  | ROM ptr → tile graphics data |
| [2]  | +0x08  | ROM ptr → tilemap layout data |
| [3]  | +0x0C  | ROM ptr → tilemap layout variant |
| [4]  | +0x10  | ROM ptr → optional extra data (0 = absent) |
| [5]  | +0x14  | ROM ptr → palette / attribute data |
| [6]  | +0x18  | ROM ptr → secondary palette / compressed data |
| [7]  | +0x1C  | Flags (0x01 = normal, 0x02 = alt mode, 0x102 = special) |

### Known Entries

| ID | Dimensions (H×W) | Notes |
|----|------------------|-------|
| 0  | 64×92  | Large outdoor map (confirmed first battle map) |
| 1  | 30×60  | |
| 2  | 36×36  | |
| 3  | 40×36  | |
| 4  | 40×36  | Same dimensions as 3 |
| 5  | 46×36  | |
| 6  | 32×60  | flags=0x02 |
| 7  | 32×60  | flags=0x102; has extra data at word[4] |

---

## WRAM Battle Control Area (0x02026804)

Written by `0x0808F618` during chapter start from values in `0x020311D4`:

| WRAM Addr  | Source from struct | Purpose |
|------------|-------------------|---------|
| 0x02026804 | cleared to 0      | battle control flags[0] |
| 0x02026805 | struct[+0x16]     | **chapter/battle slot 1 ID** |
| 0x02026806 | struct[+0x19]     | chapter/battle slot 2 ID |

Also: `0x0202680C` is a game state flag checked by `0x080732B4`.

---

## Chapter Init Call Chain

```
0x020311D4[+0x16]  ← chapter ID stored here
       ↓
0x0808F618         ← reads struct, copies IDs to 0x02026804 area
                     clears 0x020311D4 fields
                     calls 0x8075184 (pre-chapter setup)
       ↓
0x08068DE4         ← sets IWRAM[0x03000075] = 1, calls chapter init
       ↓
0x080732B4         ← reads 0x0202680C / 0x0201BE2A+B
                     computes tile display params
       ↓
0x08068FF0         ← map loader: takes (chapter_id, r1, r2, r3=1)
                     entry = 0x0853D910 + 4 + chapter_id * 32
                     loads tile graphics + tilemap + palette via DMA
                     calls 0x8068FB4 for map dimension setup
```

### Additional Callers of 0x0806FD00 (another chapter init path)

```
0x0806DF24, 0x0806F8A2, 0x08072C2A, 0x08073786,
0x08074EC6, 0x080814CE, 0x08081F6E
```

---

## Map Loader Function (0x08068FF0)

Args on call: `(chapter_id: r0, tileset_param: r1, tileset_param: r2, r3=1)`

Internal operation:
1. Extracts low 8 bits of r0 as chapter_id
2. Loads battle config table base `0x0853D910` from literal pool
3. Computes entry ptr: `table + 4 + chapter_id * 32`
4. Loads map data pointers from entry (words 1–5)
5. Calls `0x809c0e8` (DMA/VRAM copy) for each data block
6. Calls `0x8068FB4` with chapter_id for map dimension setup

---

## WRAM Tile Slots (0x0201BE2A–0x0201BE2B)

Used by `0x080732B4` as tile display slot indices (not unit count as previously assumed).
These control how the map tiles are displayed (not the chapter ID itself).

---

## Experiment: Minimum Flow Change

To force a specific battle to load, write the desired entry index (0–7) to:
- WRAM `0x020311EA` before chapter init triggers, **OR**
- WRAM `0x02026805` directly after it is written by `0x0808F618`

A Lua watchpoint on `0x02026805` (WRITE_CHANGE) during gameplay would confirm
the exact frame when the chapter ID is committed.

---

## References

- `notes/battle-config-format.md` — WRAM battle data layout (CORRECTED entry size)
- `notes/map-format.md` — tilemap layout data format
- `notes/unit-skill-addresses.md` — unit ID table and state machine functions
- `tools/import_battle_config.py` — patch generation for battle config entries
