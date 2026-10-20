# Dialogue Format

## Overview

The game stores dialogue text in a contiguous block with a separate pointer table for random access.

> **CORRECTED 2026-10-20 — 编码结论是错的**
>
> 本文件原先写"Encoding: cp932 (Shift-JIS with extensions)"，并据此给出乱码样例
> （`著畔愃榔撒誼「吶責」米候扮坦級？`）。
>
> **实际编码是游戏自带的双字节字形码**：首字节在 `0x80..0x9F` 时
> `code = 首字节*256 + 次字节`，对应 ROM 内置字库里的一个字形。
> 按 cp932 解必然乱码。完整说明与可复现工具见 **`notes/font-encoding.md`**。
>
> 修正后同一段字节的解码结果：
> `把九尾妖狐封印在鸣人体内的 / 是第几代火影？`

## Text Bank

- **Location**: ROM offset `0x459414` - `0x461CE0`
- **Size**: ~35 KB
- **Encoding**: **自定义双字节字形码**（见 `notes/font-encoding.md`），不是 Shift-JIS
- **Terminator**: null byte (`0x00`)
- **Newline**: `0x0A`
- **全角空格**: `0x81 0x40`

Text strings are null-terminated. The bytes are *font codes*, not encoded Unicode.

## Pointer Table

- **Location**: ROM offset `0x461CE8` - `0x4634B8`
- **Size**: 6096 bytes (1524 entries, 4 bytes each; 1220 non-null)
- **Format**: little-endian 32-bit pointers with ROM base `0x08000000`
- **Null markers**: `0x00000000` entries separate dialogue groups

## Group Structure

The pointer table is divided into **305 dialogue groups**, each separated by one null entry.

Each group is **one question plus three answer choices** (the in-game Naruto quiz):

| Entry | Role |
|---|---|
| [0] | Question text |
| [1] | Answer choice 1 |
| [2] | Answer choice 2 |
| [3] | Answer choice 3 |

Example group (table entries 0-3), decoded with the font-code mapping:

```
[0] 0x08459414 -> "把九尾妖狐封印在鸣人体内的\n是第几代火影？"
[1] 0x08459464 -> "第４代"
[2] 0x08459470 -> "第３代"
[3] 0x0845947C -> "第１代"
```

> The pre-2026-07 reading of these entries as "main dialogue / speaker label /
> secondary label / third label" was a mis-read caused by decoding the bytes
> as cp932.

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
| Group 0 entry 0 | 0 | `0x461CE8` | `0x459414` | "把九尾妖狐封印在鸣人体内的 / 是第几代火影？" |
| Group 1 entry 0 | 5 | `0x461CFC` | `0x459488` | "忍者在使用术的时候 / 需要的能源叫什么名字？" |

## Variable-Length Import Strategy

To add new dialogue longer than existing entries:

1. **Write new text** to free ROM space (end of ROM or gap)
2. **Update pointer table entry** to point to new text location
3. **Pad old text location** or leave as-is (other pointers may reference it)

Required for Phase 2 completion:
- `pointer_redirect` patch type in build pipeline
- Free space management (write new text to end of ROM)
- Pointer table update (write new 4-byte pointer value)

> **2026-10-20**: the new text must be encoded with **font codes**
> (`tools/konoha_font.encode_text`), not `cp932`. Writing cp932 bytes
> produces a corrupt ROM that still passes a position check.

## Free Space

After the pointer table at `0x4634B8`, the next section of ROM data begins immediately. Free space for new dialogue text must be located by scanning for zero-filled regions or by appending to the end of the ROM (within the 6 MiB limit).

Current ROM size: 6 MiB (0x600000 bytes). Pointer table ends at 0x4634B8, leaving ~1.6 MiB of ROM after the table, though most of this is other game data.

## References

- `notes/font-encoding.md` — **字形码编码说明（本文的核心依据）**
- `notes/story-script-vm.md` — 剧情脚本 VM（对白挂载在场景脚本上）
- `notes/sjis-blocks.json` - full scan of SJIS text blocks in ROM
- `notes/dialogue-function-analysis.md` - render chain analysis
- `notes/dialogue-write-path.md` - WRAM/VRAM write paths
- `notes/dialogue-writer-addresses.md` - confirmed writer PCs
