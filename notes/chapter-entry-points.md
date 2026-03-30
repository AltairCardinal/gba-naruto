# Chapter Entry Points

## Status

Identified via static analysis (2026-03-31).

---

## Confirmed Entry Points

### Chapter/Battle Initialization Chain

| Address | Role |
|---------|------|
| `0x0808F618` | Top-level chapter start: reads struct, copies IDs, calls init |
| `0x08068DE4` | Sets IWRAM trigger flag, dispatches to battle init |
| `0x080732B4` | Reads tile slot params from WRAM, prepares display args |
| `0x08068FF0` | **Map loader**: loads tile/palette data from battle config table |
| `0x0806FD00` | Alternate chapter init (7 callers, similar pattern) |

### Map Loader Callers (0x08068FF0)

```
0x0806FD38  →  called from function at 0x0806FD00
0x08073314  →  called from function at 0x080732B4
0x080750B6  →  unknown third path
```

### Chapter State Struct Writer

`0x0808F618` clears and writes:
- `0x020311D4` (chapter state struct base)
- `0x02026804` (battle control flags region)

Literal pools within `0x0808F618` function area: `0x0808F64C` = `0x020311D4`, `0x0808F650` = `0x02026804`.

---

## Known WRAM Addresses

| Address | Purpose |
|---------|---------|
| `0x020311D4` | Chapter state struct base |
| `0x020311EA` | Chapter/battle slot 1 ID (base+0x16) — **write here to change chapter** |
| `0x020311ED` | Chapter/battle slot 2 ID (base+0x19) |
| `0x02026804` | Battle control flags |
| `0x02026805` | Chapter ID committed at init time (from struct+0x16) |
| `0x02026806` | Chapter ID 2 committed at init time (from struct+0x19) |
| `0x0202680C` | Game state flag (alternate chapter ID source when nonzero) |
| `0x0201BE2A` | Tile display slot 1 (also used in battle area — dual purpose) |
| `0x0201BE2B` | Tile display slot 2 |
| `0x03000075` | IWRAM chapter trigger flag (set to 1 by `0x08068DE4`) |

---

## Known ROM Addresses

| Address | Purpose |
|---------|---------|
| `0x0853D910` | Battle/chapter config table (8 entries × 32 bytes) |
| `0x0853F298` | Unit ID mapping table (u16[64], slot → character ID) |
| `0x0853F1C0` | Battle state machine function pointers (u32[60]) |
| `0x08068FF0` | Map loader (reads from 0x0853D910) |
| `0x0808F618` | Chapter init trigger |
| `0x080732B4` | Battle display setup |

---

## Dialogue/UI Rendering Path (previously confirmed)

- `0x080968A0` — runtime-confirmed opening dialogue caller (lr=0x08096633)
- `0x08096176-0x08096212` — shared RAM-state preparation layer
- `0x0808947C` — high-level renderer block
- `0x08066D74` — confirmed WRAM tilemap halfword writer
- `0x08065F50` — confirmed VRAM glyph upload writer
- `0x08065EB8` — glyph expansion function
- `0x080894DE` — higher-value upstream anchor

---

## Notes on Static Analysis Method

All findings above were obtained from:
1. `tools/find_pointer_refs.py` — finding literal pool references to known ROM addresses
2. `tools/find_thumb_calls.py` — finding bl/blx callers of key functions
3. `tools/disasm_thumb.py` — disassembling function bodies
4. Manual extraction of literal pool values from disassembly

The chapter flow was NOT directly observable at runtime (opening story is >15000 frames
at headless emulator speed before first battle). Static analysis was sufficient.
