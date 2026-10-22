# Free ROM Space

## Summary

The ROM contains approximately **129 KB of unallocated space** at the end of the file,
verified by scanning for contiguous 0xFF-filled bytes after all known game data.

## Confirmed Region

| Property | Value |
|---|---|
| Start offset (file) | `0x5DFBEC` |
| End offset (file) | `0x5FFFFF`（ROM 的最后一个字节） |
| Size | **132,116 字节**（~129 KB）—— 第十七轮复核；原写的「~131,092 字节」少 1024 字节 |
| Fill value | `0xFF` (GBA cartridge erased state) |
| ROM file size | `0x600000` (6 MiB) |

### 实测复核：那段 0xFF 一直连到 ROM 末尾（第十七轮补记）

重新扫描的结果（扫全 ROM 找 ≥4 KB 的 0xFF 段）：

- **全 ROM 只有这一段** ≥4 KB 的 0xFF：`0x5DFBEC` → **`0x600000`**（ROM 末尾），
  共 **132,116 字节**。没有第二段。
- ⇒ 本笔记「Start `0x5DFBEC` / End `0x5FFFFF`」这一对**边界是对的**
  （`0x5FFFFF` 就是 ROM 的最后一个字节）；
  但本笔记 **Size 那一栏写的「~131,092 字节」比实际少 1024 字节** —— 那一栏的数字过时了。
  实际跨度 `0x5DFBEC..0x5FFFFF`（含两端）是 **132,116 字节**，
  正好等于「从 `0x5DFBEC` 到 ROM 末尾 `0x600000`（不含）」的长度 ⇒ 统一按 **132,116 字节**记。

**编辑器按本笔记的 `0x5FFFFF` 收口**
（`rom-editor/js/rom.js::FREE_SPACE_END = 0x5fffff`），理由是**两条链路边界一致**：

| | 常量 | 怎么用 | 实际可用范围 |
|---|---|---|---|
| `tools/import_dialogue_var.py` | `FREE_SPACE_END = 0x5FFFFF`（注释写「last byte of ROM」） | **含端点** | `0x5DFBEC..0x5FFFFF`（132,116 字节） |
| `rom-editor/js/rom.js` | `FREE_SPACE_END = 0x5fffff`（注释写「上界（不含）」） | **不含端点** | `0x5DFBEC..0x5FFFFE`（132,115 字节） |

- 两者**收在同一个位置**，差的只是「端点算不算」那 **1 个字节** ——
  编辑器保守地**不用**最后一个字节 `0x5FFFFF`。
- 编辑器**主动放弃这 1 个字节**，是为了让两条链路的边界完全一致；
  代价是末尾少用 1 字节。

## Usage

This region is used by the variable-length dialogue pipeline (`import_dialogue_var.py`)
to store new text that is longer than the original slot, with the dialogue pointer table
updated via `pointer_redirect` patches to point to the new location.

### Allocation strategy

- Text is 4-byte aligned before writing.
- Each entry occupies `len(encoded_text) + 1` bytes (null-terminated).
- The cursor advances sequentially; no deallocation is performed.
- `FREE_SPACE_START = 0x5DFBEC` and `FREE_SPACE_END = 0x5FFFFF` are defined as
  constants in `tools/import_dialogue_var.py`.

## Verification Method

Performed a linear scan of the ROM file looking for the first 0xFF byte after
offset `0x5D0000`. The scan found a contiguous 0xFF run starting at `0x5DFBEC`
and continuing to the end of the 6 MiB file (`0x5FFFFF`), confirming ~128 KB of
free space. No game code or data was found in this range.

**第十七轮复核**（扫**全 ROM** 找所有 ≥4 KB 的 0xFF 段）：**只有这一段** ——
`0x5DFBEC` → `0x600000`（ROM 末尾），**132,116 字节**。全 ROM 没有第二段。

## 与编辑器的关系（Relationship to the editor）

编辑器**现在也会用这一段空闲区**（第十七轮起）：

| 用途 | 谁做 | 落点 |
|---|---|---|
| 文本表**变长搬迁**（9 张指针表驱动的表：正文搬到空闲区、指针改掉） | `rom-editor/js/rom.js::rebuildTextTable` | 早就有的能力，本轮补了逐表验收 |
| **剧情剧本搬迁**（对白变长 → 整个剧本搬到空闲区、内部绝对地址全部重基、根表指针改掉） | `rom-editor/js/rom.js::applyScriptRelocations` + `rom-editor/js/storyvm.js::planRelocation` | 第十七轮新增 |
| 变长对白文本 | `tools/import_dialogue_var.py` | 既有的老链路 |

⚠️ **`tools/import_dialogue_var.py` 与 `rom-editor/js/rom.js::allocate` 是两个
互不知情的分配器，却共用同一段区域。**

- 两个分配器**各自从 `0x5DFBEC` 开始顺序分配**，**都不登记对方写过的字节**。
- 谁先谁后都会踩到对方：后跑的会**覆盖**先跑写进去的内容（两边都没有「已占用」检查）。
- ⇒ **要混用这两条链路，必须人工协调**（例如先跑一条、把结果落盘并重新扫描空闲区，
  再跑另一条；或者让其中一条只做等长改动）。
- 编辑器这一侧只避开**自己**的分配（`rom.js::allocate` 会跳过「内容包声称占用」与
  「本次构建已分配」的字节），它**不知道** Python 那条链路写过什么。
- 结论写在代码注释里：`rom-editor/js/rom.js::FREE_SPACE_END` 与
  `rom-editor/js/rom.js::allocate` 的注释各写了一份。
