# 忍者问答表格式（Quiz Format）

> **2026-10-24 更正标题与措辞**：这份文件原先叫 `dialogue-format.md`，
> 里面的「Pointer Table / Group Structure」两节描述的**不是剧情对白**，
> 而是游戏里的**忍者问答（quiz）** —— 一道题 + 三个选项。
> 真正的剧情对白**内联在剧情脚本的字节流里**（见 `notes/story-script-vm.md`），
> 不在这张表里。
> 文件名与标题按事实改了（`notes/quiz-format.md`），
> 里面的**地址、编码、结构、解码样例一字未动** —— 它们一直是准的，
> 错的只是「这叫对白」这个叫法。

## Overview

游戏里有一块问答小游戏的文本：**指针表 + 一段字形码文本**。
指针表本身不含文字，只指向文本区；每一组是「一道题 + 三个选项」。

> **CORRECTED 2026-10-20 — 编码结论是错的**
>
> 本文件原先写"Encoding: cp932 (Shift-JIS with extensions)"，并据此给出乱码样例
> （`著畔愃榔撒誼「吶責」米候扮坦级？`）。
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
- **Null markers**: `0x00000000` entries separate the question groups

## Group Structure

The pointer table is divided into **305 question groups**, each separated by one null entry.

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
> 同理，把这张表叫成「对白表」也是那次误读的延续 —— 2026-07 的文件里
> 「dialogue group」这个说法一直用到了 2026-10-24。

Some groups have different entry counts (not always 4).

## 这张表的原生读者：尚未定位（2026-10-24 实测）

**扫全 ROM 的结果**：

| 找什么 | 结果 |
|---|---|
| 指向指针表 `0x08591CE8` 的字面量 | **0 处** |
| 指向第 0 题文本 `0x08599414` 的字面量 | **0 处** |
| 指向指针表区间（`0x08591CE8`+6096）的任何 32 位字 | 1 处，落在 `0x3F7C98` 的代码/数据里，**不是指针表**（前后邻居都不是 ROM 指针） |

⇒ 这张表**没有已证实的原生读者**。它要么是被算出来的地址访问的，
要么走的不是我们已知的几条路径。

**此前记在这张表上的两个地址是错的**：

| 地址 | 此前记成 | 实际是什么 |
|---|---|---|
| `0x080968A0` | 「打开对白的运行时路径」 | **剧情脚本 VM 的「普通画法」指令**（`notes/evidence/story-vm-opcodes-20261020.md`：`0x080968A0: bl #0x8096168`）—— 读的是**脚本里内联的对白** |
| `0x08096633` | 「调用者」 | 上面那条指令的调用点（`lr=0x08096633`，见 `notes/dialogue-caller-runtime.md`） |

这两个地址来自 2026-07 的「开场对白」运行时追踪 ——
那时**误以为这张表就是对白**，所以把命中它的画框指令挂到了这张表上。
2026-10-20 的 VM 指令考证拆穿了这一点：画框指令读的是脚本内联文本，
与这张问答表没有关系。

⇒ 内容包里**不再**把它写成「原生读者」（那是假的宣称）。
剧情 VM 自己的读者已经在**说话人名表**上（12 个地址，机器扫描得来）。

## How Dialogue Reaches the Screen

> 这一节讲的是**剧情对白**的渲染链（VM → 记录库 → 字形展开 → tilemap → DMA），
> 与上面的问答表无关。问答表的屏幕呈现路径**还没有查**。

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

To add a new question longer than the existing entries:

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

After the pointer table at `0x4634B8`, the next section of ROM data begins immediately. Free space for new text must be located by scanning for zero-filled regions or by appending to the end of the ROM (within the 6 MiB limit).

Current ROM size: 6 MiB (0x600000 bytes). Pointer table ends at 0x4634B8, leaving ~1.6 MiB of ROM after the table, though most of this is other game data.

## References

- `notes/font-encoding.md` — **字形码编码说明（本文的核心依据）**
- `notes/story-script-vm.md` — 剧情脚本 VM（**真正的剧情对白**在这里）
- `notes/story-vm-opcodes-20261020.md` — VM 指令逐条考证（`0x080968A0` = 普通画法）
- `notes/sjis-blocks.json` - full scan of SJIS text blocks in ROM
- `notes/dialogue-function-analysis.md` - render chain analysis
- `notes/dialogue-write-path.md` - WRAM/VRAM write paths
- `notes/dialogue-writer-addresses.md` - confirmed writer PCs
