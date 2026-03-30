# Dialogue Format

## Overview

The game stores dialogue text in a contiguous SJIS-encoded block with a separate pointer table for random access.

## Text Bank

- **Location**: ROM offset `0x459414` - `0x461CE0`
- **Size**: ~35 KB
- **Encoding**: cp932 (Shift-JIS with extensions)
- **Terminator**: null byte (`0x00`)
- **Newline**: `0x0A`

Text strings are stored as null-terminated byte sequences. Newlines are `0x0A`. Full-width spaces are `0x81 0x40`.

## Pointer Table

- **Location**: ROM offset `0x461CE8` - `0x4634B8`
- **Size**: 6096 bytes (1524 entries, 4 bytes each)
- **Format**: little-endian 32-bit pointers with ROM base `0x08000000`
- **Null markers**: `0x00000000` entries separate dialogue groups

## Group Structure

The pointer table is divided into **305 dialogue groups**, each separated by one null entry.

Most groups contain **4 non-null pointer entries**:

| Entry index | Typical role |
|-------------|-------------|
| [0] | Main dialogue text (longest string) |
| [1] | Speaker label or short menu text |
| [2] | Secondary label / choice text |
| [3] | Third label / continuation |

Example group (table entries 15-18):

```
[15] 0x08459594 -> "著畔愃榔撒誼「吶責」米候扮坦級？"
[16] 0x084595C4 -> "征着砿"
[17] 0x084595D0 -> "申悲級"
[18] 0x084595DC -> "差韻淫級"
```

Some groups have different entry counts (not always 4).

## How Dialogue Reaches the Screen

The render chain (from earlier Phase 1 analysis):

1. **Script/UI state** prepares RAM struct at `0x02002880`
2. **Record bank** at `0x02022E30` holds entity/slot records
3. **Renderer** at `0x0808947C` reads per-slot metadata and calls glyph/tilemap functions
4. **Glyph expansion** at `0x08065EB8` decodes compact bytes into VRAM tile data
5. **Tilemap materialization** at `0x08066D14` writes tilemap entries to WRAM buffer
6. **DMA copy** transfers WRAM buffer to VRAM BG3 screen block at `0x06001B00+`

The runtime path for opening dialogue confirmed: `0x080968A0` (caller `lr=0x08096633`)

## Known Text Entry Points

| ID | Table index | ROM pointer offset | Text start | Content |
|----|------------|-------------------|-----------|---------|
| `proof.menu.same_length_00076d` | (before table) | - | `0x00076D` | 過篇 (Chinese patched: 过篇) |
| Group 0 entry 0 | 0 | `0x461CE8` | `0x459414` | Long dialogue text |
| Group 1 entry 0 | 5 | `0x461CFC` | `0x459488` | Battle-related dialogue |

## Variable-Length Import Strategy

To add new dialogue longer than existing entries:

1. **Write new text** to free ROM space (end of ROM or gap)
2. **Update pointer table entry** to point to new text location
3. **Pad old text location** or leave as-is (other pointers may reference it)

Required for Phase 2 completion:
- `pointer_redirect` patch type in build pipeline
- Free space management (write new text to end of ROM)
- Pointer table update (write new 4-byte pointer value)

## Free Space

After the pointer table at `0x4634B8`, the next section of ROM data begins immediately. Free space for new dialogue text must be located by scanning for zero-filled regions or by appending to the end of the ROM (within the 6 MiB limit).

Current ROM size: 6 MiB (0x600000 bytes). Pointer table ends at 0x4634B8, leaving ~1.6 MiB of ROM after the table, though most of this is other game data.

## References

- `notes/sjis-blocks.json` - full scan of SJIS text blocks in ROM
- `notes/dialogue-function-analysis.md` - render chain analysis
- `notes/dialogue-write-path.md` - WRAM/VRAM write paths
- `notes/dialogue-writer-addresses.md` - confirmed writer PCs
