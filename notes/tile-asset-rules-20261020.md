# 单格地块替换（tile asset import）规则 —— 本仓库 ROM 实测版

> 日期：2026-10-20
> 工具：`tools/tile_asset_rules.py`（新建；只用标准库 + 仓库内 `tools/lib` 公共模块，**只读 ROM**）
> 知识来源（只读，未改动）：`third_party/konoha-workshop/源码/editor/asset_imports.js`
> 的 `P.setTileAsset` / `P.mapData` / `P.buildExtras`
>
> 工具复用仓库已有的公共模块：`tools/lib/lz77.py`（`decompress` /
> `compress_literal`，与第三方 `compressLiteral` 同一套纯字面量编码）和
> `tools/lib/io.py`（`write_text`，保证仓库文件一律 LF）。
>
> 本文件的每一条规则都在 **本仓库自己的 ROM** 上做了可判死的检验，
> 凡是只能靠第三方源码推断、无法在本 ROM 上判死的，都集中在
> §9「无法在静态层面验证的规则」里。

---

## 0. 证据基线与复现方式

```
rom     : rom/base.gba
size    : 6291456 B
sha256  : 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b
```

所有命令都从仓库根目录执行（PowerShell 5.1，不支持 `&&`，请分行运行）：

```powershell
python tools/tile_asset_rules.py rom/base.gba --stage 40
python tools/tile_asset_rules.py rom/base.gba --all
python tools/tile_asset_rules.py rom/base.gba --stage 0 --x 3 --y 5 --terrain 7
```

工具**永远不会写 ROM**；`--x/--y` 只做试算并打印计划与限制检查结果。

---

## 1. 地图描述符表

* 文件偏移 `0x53D910`（ARM `0x0853D910`），**32 字节/条**，**47 条有效条目（索引 0..46）**。
* 索引 47 起是另一张表（`raw=513×768`，宽度不能被 4 整除），不属于地图表。

> **订正说明**：本仓库 `notes/battle-config-format.md` / `notes/addresses.md` 早期把这条表
> 记成「8 条有效条目」或「47 条，字段为 ptr1..ptr5 + flags」。
> **字段顺序以本文件为准**（下方 §2 的实测），条目数实测为 47。

### 1.1 条目布局（32 字节）

| 偏移 | 类型 | 含义 | 实测校验 |
|---|---|---|---|
| `+0x00` | u16 | raw 宽 | 36..92 |
| `+0x02` | u16 | raw 高 | 30..64 |
| `+0x04` | u32 ptr | tile gfx（LZ77） | 解压长度 % 32 == 0（47/47） |
| `+0x08` | u32 ptr | palette（LZ77） | 解压长度恒为 384 B（47/47） |
| `+0x0C` | u32 ptr | 图层 0 tilemap（LZ77） | 解压长度 == 格数×4（47/47） |
| `+0x10` | u32 ptr | 图层 1 tilemap（LZ77，**可为 0**） | 同上；14 张图有图层 1 |
| `+0x14` | u32 ptr | metatile 表（LZ77） | 解压长度 % 8 == 0（47/47） |
| `+0x18` | u32 ptr | terrain 表（LZ77） | 解压长度 == 格数×2（47/47） |
| `+0x1C` | u8 | 剧情底图 ID | 1..7 |

### 1.2 「格（cell）」的坐标语义 —— 本 ROM + 游戏代码双重确认

```
cell 列数 = raw宽  >> 2
cell 行数 = raw高  >> 1
1 格 = 32 × 16 像素
```

* **数据侧**：`terrain` 解压长度 == `cellW*cellH*2`，47/47 精确吻合；
  `layer0` 解压长度 == `cellW*cellH*4`，47/47 精确吻合。
* **代码侧**（反汇编 `0x08068FB4`，战斗地图尺寸写入函数）：

  ```
  08068FBE: ldrh r1, [r0]          ; r1 = raw宽
  08068FC0: strb r1, [r3]          ; [0x0201BE28] = raw宽（只存低字节！）
  08068FC4: ldrh r0, [r0, #2]      ; r0 = raw高
  08068FC6: strb r0, [r2]          ; [0x0201BE29] = raw高（只存低字节！）
  08068FCA: ldrb r0, [r3]          ; raw宽
  08068FCC: lsrs r0, r0, #2        ; raw宽 >> 2   → [0x0201BE2A] = 格宽
  08068FD4: lsrs r0, r0, #1        ; raw高 >> 1   → [0x0201BE2B] = 格高
  ```

  → **raw 宽高必须 ≤ 255**（游戏只存 1 字节）。实测 36..92 / 30..64，全部安全。

* **与既有笔记的交叉验证**：`notes/maps-runtime-fields-20260711.md` 记录首战
  `0x02026805 = 40` 对应文件 `0x53DE10`、原始头 `24 00 2C 00`、
  运行时预期 `[36,44,9,22]`。本工具对 stage 40 输出的正是
  `raw 36 x 44 → cell 9 x 22`（descriptor 文件偏移 0x53DE10）——
  **完全吻合**，是本规则的一次独立外部验证。

---

## 2. 六个 LZ77 块的结构规则

游戏用 BIOS `SWI 0x12`（LZ77UnCompVram）与 `SWI 0x11`（LZ77UnCompWram）解压，
**BIOS 不做目标缓冲区越界检查**，所以块尺寸必须由我们自己算准。

### 2.1 各块的落点（反汇编战斗地图加载器 `0x08068FF0`）

| 块 | 描述符偏移 | 解压目标 | 备注 |
|---|---|---|---|
| tile gfx | `+0x04` | `0x06000000 \| (mode << 14)` | `mode` = WRAM `0x02022E2D`；SWI 0x12 |
| palette | `+0x08` | `0x05000000`（**BG PALRAM**） | SWI 0x12 |
| 图层 0 | `+0x0C` | EWRAM `0x0201BE2C` | SWI 0x11 |
| 图层 1 | `+0x10` | EWRAM `0x0201CE2C`（= 图层 0 + 0x1000） | 指针为 0 时整段跳过 |
| metatiles | `+0x14` | EWRAM `0x0201DE2C`（= 图层 0 + 0x2000） | SWI 0x11 |
| terrain | `+0x18` | **战斗加载器不读这一块** | 见 §9.1 |

加载器关键片段：

```
08069040: ldr  r5, [pc, #0x98]    ; r5 = 0x0853D910（地图表）
08069044: lsls r6, r2, #5         ; r6 = id * 32
08069048: adds r0, r6, r0         ; r0 = 表 + 4 + id*32 → 读 +0x04 gfx
08069050: movs r2, #0xc0
08069052: lsls r2, r2, #0x13      ; r2 = 0x06000000（VRAM）
08069054: adds r1, r1, r2         ; r1 = 0x06000000 | (mode << 14)
08069056: bl   0x809c0e8          ; SWI 0x12 = LZ77UnCompVram
08069062: movs r1, #0xa0
08069064: lsls r1, r1, #0x13      ; r1 = 0x05000000（PALRAM）
08069066: bl   0x809c0e8          ; SWI 0x12
08069074: adds r1, r4, #0         ; r1 = 0x0201BE2C（图层 0）
08069076: bl   0x809c0ec          ; SWI 0x11 = LZ77UnCompWram
08069096: adds r1, r4, r7         ; r7 = 0x1000 → 0x0201CE2C（图层 1）
080690A6: ldr  r1, [pc, #0x3c]    ; r1 = 0x0201DE2C（metatile）
080690A8: bl   0x809c0ec          ; SWI 0x11
```

### 2.2 尺寸规则

| 块 | 长度规则 | 实测 |
|---|---|---|
| tile gfx | `图块数 × 32` 字节 | 160..704 图块 |
| palette | `色卡数 × 32` 字节（16 色 × u16 BGR555） | 恒为 384 B = **12 组色卡** |
| 图层 0/1 | `格数 × 4` 字节（每格 2 个 u16 metatile 索引） | 最大 2944 B（map 0） |
| metatiles | `项数 × 8` 字节 | 106..770 项 |
| terrain | `格数 × 2` 字节（每格 2 字节） | 47/47 吻合 |

**图层网格**：图层是 `格行数 × (格列数×2)` 的 u16 metatile 索引矩阵——
每格横向占 **2** 个 metatile（因为 1 格 = 32px 宽 = 2 个 16px metatile），
纵向占 **1** 行 metatile（1 格 = 16px 高 = 1 个 metatile）。

---

## 3. metatile 编码规则

**1 个 metatile = 8 字节 = 4 个 u16**，每个 u16 是一个图块引用：

```
bits 15-12 : 色卡号 (bank, 0..15)
bit  11    : 垂直翻转
bit  10    : 水平翻转
bits  9-0 : 图块号 (tile, 0..1023)
```

* 本 ROM 实测：41/47 张地图的 metatile 用到了 bit10/bit11 翻转位；
  全部 47 张图的图层索引都指向合法 metatile（越界引用 0 处）；
  全部 metatile 都被至少一个图层引用（未被引用项 0 个）。
* 全部 47 张图中，被引用的最大图块号 **681**（map 9，该图共 704 个图块），
  每张图的被引用图块号都严格小于该图的图块总数，也都 < 1024。
  最「满」的是 map 21（160 个图块里用到了第 159 号，占用率 99.4%）。

---

## 4. 色卡（bank）规则

### 4.1 「已用色卡」的定义

> **只有被图层引用到的 metatile，其 4 个 u16 的 bits15-12 才算占用了该色卡。**

这正是第三方 `usedBanks` 的算法。本 ROM 上「全部 metatile 的色卡集合」
与「被引用 metatile 的色卡集合」在 47/47 张图上完全相同（因为没有未引用项），
但规则本身在替换后仍然重要：新追加的 metatile 立刻被图层引用，所以规则自洽。

### 4.2 16 组上限

* 色卡号占 4 bit（bits15-12）→ **最多 16 组**。
* GBA BG PALRAM 在 `0x05000000`，共 **512 字节 = 16 组 × 16 色**，硬件上 16 组都可寻址。
* 但**本 ROM 的 palette 块只有 384 字节 = 12 组**（47/47 张图全部如此）。
  → 想用第 13..16 组（bank 12..15），**必须把 palette 块从 384 B 扩写成 512 B**。
  第三方正是这么做的：`while(out.palette.length<512)out.palette.push(0)`。
* 实测全局色卡使用直方图（47 张图，按图统计使用该色卡的图数）：

  ```
  bank:  0   1   2   3   4   5   6   7   8   9  10  11..15
  图数: 47  43  29  42  43  16  13   7   9   6   1    0
  ```

  **bank 10 只有 map 7 用到；bank 11..15 在原版里一次都没用过。**

### 4.3 色卡分配规则（第三方）

* 新格独占一组色卡：取「未被使用的最小 bank 号」。
* 多个格如果 **16 色完全相同**（第三方按 palette 签名去重），**共用同一组色卡**，
  也只写一次调色板。
* 写入位置：`palette[bank*32 + i*2 .. +1] = u16(BGR555)`（每组 32 字节）。

---

## 5. 图块（tile）规则与上限

* 一个图块 = **32 字节**（8×8 像素，4bpp，每字节 2 像素）。
* 图块号占 10 bit（bits9-0）→ **最多 1024 个图块**（索引 0..1023）。
* 实测图块总数 160..704，余量至少 320 个。
* **清屏图块**：第三方在写图层 1 时需要一个「全 0 图块」来擦掉上层覆盖。
  本 ROM **47/47 张图都存在全 0 图块**，而且**第 0 号图块就是全 0**
  → 清屏 metatile 直接复用图块 0，不需要额外占用图块空间。

---

## 6. 单格替换算法（第三方规则的完整还原）

第三方 `P.mapData` 对每一格做以下动作，顺序固定：

1. **统计已用色卡**：扫描图层 0 与图层 1 的每个 u16，取其 metatile 的 4 个 u16，
   收集 bits15-12。
2. **分配色卡**：取最小未占用 bank；若 16 组全满 → 报错
   「本图 16 组色卡均已使用」。palette 块补齐到 512 字节后写入 16 个 BGR555 色。
3. **清屏 metatile（仅当存在图层 1）**：
   * 找第一个全 0 图块；找不到就追加一个（此时图块数必须 < 1024）；
   * 追加 1 个 metatile，其 4 个引用全指向该清屏图块（bank = 0，无翻转）；
   * metatile 数必须 < 1024。
4. **追加新图块**：一格 = 32×16 px = 2 个半块，每半块 = 2×2 个 8×8 图块
   → **共 8 个新图块**（每格固定消耗 8 个图块）。
   像素取样：`半块 half ∈ {0,1}` 决定列偏移 `half*16`；
   `ty ∈ {0,1}` 决定行偏移 `ty*8`；`tx ∈ {0,1}` 决定列偏移 `tx*8`。
5. **追加新 metatile**：每半块 1 个 metatile → **共 2 个**，
   其 4 个引用为 `图块号 | (bank << 12)`（不带翻转位）。
   metatile 数必须 < 1024。
6. **改写图层**：
   * 图层 0 的 u16 偏移 = `(y*格宽*2 + x*2 + h)`，`h ∈ {0,1}` 取左右两个半块；
   * 图层 1 同偏移处写清屏 metatile 索引（等于替换前的 metatile 数）。
7. **写 terrain**：`terrain[(y*格宽 + x)*2] = 地形类型(0..15)`，
   `terrain[(y*格宽 + x)*2 + 1] = 0`。

### 6.1 单格资源账（每格固定成本）

| 资源 | 成本 | 备注 |
|---|---|---|
| 色卡 | **1 组**（每种不同 16 色 1 组） | 16 组上限 |
| 图块 | **8 个** | 无全 0 图块时 +1 |
| metatile | **2 个**（有图层 1 时 **3 个**：2 + 1 清屏） | 1024 上限 |
| 图层 u16 写入 | 2 个（图层 0）+ 2 个（图层 1，若存在） | |
| terrain 字节 | 2 个 | byte1 被写成 0 |

### 6.2 试算输出示例（stage 0，格 (3,5)，terrain 7）

命令：`python tools/tile_asset_rules.py rom/base.gba --stage 0 --x 3 --y 5 --terrain 7`

```
=== stage 0 (map descriptor #0) ===
  descriptor     : file 0x53D910 (ARM 0x0853D910)
  raw size       : 92 x 64  ->  cell grid 23 x 32 (736 cells, each 32x16 px)
  background id  : 1
  structure      : OK (all size relations hold)
  gfx tiles      : 672 used / 1024   free 352   max referenced tile 659
  blank gfx tile : 0   (reusable as layer1 clear tile)
  metatiles      : 770 used / 1024   free 254
  colour banks   : 9 used [0, 1, 2, 3, 4, 5, 6, 7, 8]   free 7 [9, 10, 11, 12, 13, 14, 15]
  palette block  : 384 B = 12 banks present in ROM (writable 16)
  layer0         : 2944 B = 1472 u16 -> 0x0201BE2C
  layer1         : 2944 B = 1472 u16 -> 0x0201CE2C
  terrain        : 1472 B = 736 cells x 2 B   flag bits seen 0xC0
  headroom       : 44 cells by tiles, 84 cells by metatiles, 7 cells by colour banks  -> binding limit: banks (7)
                   (one bank per *distinct* palette; cells that reuse the same 16 colours share a bank)

--- replacement plan for cell (3,5) of stage 0 (dry run, ROM untouched) ---
  [PASS] bank_exhausted       bank 9 of 16 is free (7 free)
  [PASS] tile_space           reusing blank gfx tile 0 for the layer1 clear metatile
  [PASS] metatile_space       metatile 770 of 1024 is free
  [PASS] tile_space           8 gfx tiles needed, 352 of 1024 free
  [PASS] metatile_space       3 metatiles needed, 254 of 1024 free
  [PASS] simulated_structure  simulated blocks re-parse cleanly (indices, tiles and banks in range)
  colour bank    : 9 (palette byte offset 288, palette block -> 512 B)
  new gfx tiles  : [672, 673, 674, 675, 676, 677, 678, 679] (content tiles [672, 673, 674, 675, 676, 677, 678, 679], gfx block -> 21760 B)
  new metatiles  : [770, 771, 772] (content [771, 772], metatile block -> 6184 B)
  layer0 write   : u16 index 236 (byte 472) -> [771, 772]
  layer1 write   : u16 index 236 (byte 472) -> clear metatile 770
  terrain write  : byte 236 -> [7, 0]
  simulated blocks (raw -> LZ77 literal):
    gfx      :  21760 ->  24484 B
    palette  :    512 ->    580 B
    layer0   :   2944 ->   3316 B
    layer1   :   2944 ->   3316 B
    metatiles:   6184 ->   6961 B
    terrain  :   1472 ->   1660 B
  verdict        : OK - all limits satisfied
```

> 注意编号：清屏 metatile = **770**（替换前的 metatile 数，先追加），
> 内容 metatile = **771 / 772**（后追加）；图层 0 写 771/772，图层 1 写 770。
> 新图块 672..679 直接接在原有 672 个之后。

### 6.3 全图端到端模拟（内存里跑完整算法并重新解析结果）

工具的 `--x/--y` 会把整套算法**在内存里跑完**，再把产出的 6 个块重新解析一遍，
逐项检查：图层索引 < metatile 数、metatile 里的图块号 < 图块数、色卡号 < 16、
terrain / 图层块长度不变。`--simulate-all` 对全部 47 张地图各替换一格：

```
命令：python tools/tile_asset_rules.py rom/base.gba --simulate-all

idx  bank  new tiles  new metatiles      gfx raw->lz     meta raw->lz  re-parse
  0     9          8              3    21760-> 24484     6184->  6961  OK
  9    10          8              3    22784-> 25636     3040->  3424  OK
 40     5          8              2    12544-> 14116     1392->  1570  OK
 …
 46     2          8              2    10496-> 11812     1096->  1237  OK

simulate-all: 47/47 maps simulated cleanly
```

**结论**：本规则在**全部 47 张地图**上都可执行，且没有任何越界引用；
每格固定 +8 图块、+2 或 +3 metatile、+1 组色卡（见 §6.1）。
写回时用 `tools/lib/lz77.py` 的 `compress_literal` 编码（第三方 `buildExtras`
用的就是同一套「每 8 字节一个 0x00 标志字节」的纯字面量编码），
再把描述符 `+0x04..+0x18` 六个指针改写为新块地址。

---

## 7. 三类失败条件（工具会显式报出）

| 代码 | 触发条件 | 第三方原话 |
|---|---|---|
| `tile_space` | 图块总数会超过 1024（8 个/格；无全 0 图块时 9 个/格） | 「本图已达到 1024 个图块上限」「图块空间不足，无法清理上层覆盖」 |
| `metatile_space` | metatile 数会超过 1024（2 个/格，有图层 1 时 3 个/格） | 「本图的组合图块已达到 1024 个上限」「组合图块空间不足」 |
| `bank_exhausted` | 16 组色卡全被占用 | 「本图 16 组色卡均已使用；请减少导入素材的色卡种类，或先合并颜色」 |

工具另外还会报 `out_of_range`（格坐标越界）与 `terrain_out_of_range`（地形类型不在 0..15）。

**合成边界用例**（`python tools/tile_asset_rules.py rom/base.gba --selftest`，
构造数据驱动四条报错路径，退出码 0 表示 4/4 全部按预期被拒绝）：

```
--- case A: 1024 gfx tiles (tile space exhausted) ---
  [PASS] bank_exhausted     bank 1 of 16 is free (15 free)
  [PASS] tile_space         reusing blank gfx tile 0 for the layer1 clear metatile
  [PASS] metatile_space     metatile 16 of 1024 is free
  [FAIL] tile_space         need 8 gfx tiles, only 0 of 1024 free
  [PASS] metatile_space     3 metatiles needed, 1008 of 1024 free
  verdict: REJECTED
--- case B: 1024 metatiles (metatile space exhausted) ---
  [PASS] bank_exhausted     bank 1 of 16 is free (15 free)
  [PASS] tile_space         reusing blank gfx tile 0 for the layer1 clear metatile
  [FAIL] metatile_space     metatile table is already at the 1024 limit
  [PASS] tile_space         8 gfx tiles needed, 1014 of 1024 free
  [FAIL] metatile_space     need 3 metatiles, only 0 of 1024 free
  verdict: REJECTED
--- case C: all 16 colour banks used ---
  [FAIL] bank_exhausted     all 16 colour banks are already used by this map
  [PASS] tile_space         reusing blank gfx tile 0 for the layer1 clear metatile
  [PASS] metatile_space     metatile 16 of 1024 is free
  [PASS] tile_space         8 gfx tiles needed, 1014 of 1024 free
  [PASS] metatile_space     3 metatiles needed, 1008 of 1024 free
  verdict: REJECTED
--- case D: no all-zero gfx tile and the tile limit reached ---
  [PASS] bank_exhausted     bank 1 of 16 is free (15 free)
  [FAIL] tile_space         no all-zero gfx tile and the 1024 tile limit is reached
  [PASS] metatile_space     metatile 16 of 1024 is free
  [FAIL] tile_space         need 8 gfx tiles, only 0 of 1024 free
  [PASS] metatile_space     3 metatiles needed, 1008 of 1024 free
  verdict: REJECTED

selftest: 4/4 synthetic cases rejected as expected
```

---

## 8. 47 张地图的实测余量

`python tools/tile_asset_rules.py rom/base.gba --all`（按「还能换几格」升序）：

| 地图 | 格数 | 图块 用/余 | metatile 用/余 | 色卡 用/余 | 还能换 |
|---|---|---|---|---|---|
| **9** | 16×32 | 704 / 320 | 377 / 647 | **10 / 6** | **6 格** |
| **11** | 17×30 | 672 / 352 | 341 / 683 | **10 / 6** | **6 格** |
| **12** | 11×32 | 608 / 416 | 257 / 767 | **10 / 6** | **6 格** |
| **35** | 11×32 | 608 / 416 | 257 / 767 | **10 / 6** | **6 格** |
| 0 | 23×32 | 672 / 352 | **770 / 254** | 9 / 7 | 7 格 |
| 10 | 16×21 | 480 / 544 | 240 / 784 | 9 / 7 | 7 格 |
| 7 | 15×16 | 672 / 352 | 443 / 581 | 8 / 8 | 8 格 |
| 32 | 13×26 | 480 / 544 | 209 / 815 | 8 / 8 | 8 格 |
| … | | | | | |
| 21 / 34 | 9×16 | 160 / 864 | 106 / 918 | 3 / 13 | 13 格 |

**最紧张的是 map 9 / 11 / 12 / 35（并列）**：瓶颈全部是**色卡**（各剩 6 组），
不是图块（还剩 320..416 个）也不是 metatile（还剩 647..767 个）。
色卡余量按「每种不同 16 色占 1 组」计；若多格复用同一套 16 色，实际可换格数更多。

其它极值：
* 图块最多：map 9 = 704（余 320）；最少：map 21/34 = 160（余 864）。
* metatile 最多：map 0 = 770（余 254）；最少：map 19 = 106（余 918）。
* 格数最多：map 0 = 736；图层 0 块最大 2944 B（map 0），仍小于图层缓冲 4096 B。
* 14 张图带图层 1（0,7,8,9,10,11,12,21,22,23,31,32,34,35），其余 33 张没有。

---

## 9. 无法在静态层面验证的规则（必须上模拟器）

### 9.1 terrain（`+0x18`）的消费者没找到

战斗地图加载器 `0x08068FF0` 只读 `+0x04/+0x08/+0x0C/+0x10/+0x14`，
**不读 `+0x18`**。所以：

* 已知：terrain 块 = 每格 2 字节；byte0 是地形类型
  （全 ROM 直方图 `{0:5874, 1:288, 2:1, 3:160, 4:1, 7:308, 15:5519}`，全部 ≤ 15，
  与第三方 `terrain ∈ 0..15` 的检查一致）。
* 已知：byte1 是标志字节，直方图 `{0:11756, 0x40:4, 0x80:391}`，
  且**只有 map 0 出现非零 byte1**（391 格 0x80 + 4 格 0x40）。
* **未知**：谁读这块、byte1 的 0x40/0x80 到底表示什么。
* **风险**：第三方替换时写 `terrain[pos+1] = 0`，会**清掉 map 0 被替换格的标志位**。
  本仓库若要沿用该算法，需要先确认 byte1 语义。

### 9.2 metatile 上限 1024 的边界没闭合

* 第三方断言 `< 1024`。
* 已确认：metatile 表解压到 EWRAM `0x0201DE2C`；图层 0/1 分别在
  `0x0201BE2C` / `0x0201CE2C`（正好相隔 0x1000）。
* **未确认**：`0x0201DE2C` 之后的下一个结构在哪，因此 metatile 缓冲的真实容量
  （推测 0x2000 = 8192 B = 1024 项）没有闭环。
* BIOS `SWI 0x11` **不做目标缓冲区越界检查**，超长会静默破坏相邻 EWRAM。

### 9.3 图块上限 1024 与 VRAM 落点

* 10 bit 索引只能表达 1024 个图块（字段层面确定）。
* 但 gfx 是整块解压到 `0x06000000 | (mode << 14)`，`mode` 由运行时决定；
  原版最大 704 图块 = 22528 B 已经跨过 16 KB 的 VRAM 图块边界，
  **说明该游戏本来就允许 gfx 溢出到一个图块**。扩到 >1024 图块后的实际表现
  需要在模拟器里看。

### 9.4 512 字节 palette 块能否被游戏接受

* PALRAM 是 512 字节（16 组），硬件上 16 组都可写 ✓。
* 但游戏用的 BIOS 调用是 `SWI 0x12 = LZ77UnCompVram`，目标却是
  PALRAM `0x05000000`（非 VRAM）；原版 palette 块**永远只有 384 字节**，
  从没出现过 512 字节的情况。
* 因此「把 palette 块扩到 512 B 再解到 PALRAM」这条路径**原版游戏自己没走过**，
  必须实机验证（否则只能退回「只用 bank 0..11」）。

### 9.5 其余需要运行期确认的点

* 新 metatile 指向的图块是否真的按 bank 正确取色（渲染层验证）。
* 图层 1 被清屏后是否有视觉残留。
* VRAM 图块块号（`mode`）在替换后是否仍与新图块号匹配。

---

## 10. 与本仓库既有笔记的关系

| 既有笔记 | 关系 |
|---|---|
| `notes/battle-config-format.md` | 条目字段顺序（+0 宽/+2 高/+4 gfx/+8 pal/+C/+10 图层/+14 meta/+18 terrain/+1C 底图）**一致**；但那条记的「8 条有效条目」应为 **47 条** |
| `notes/maps-runtime-fields-20260711.md` | 提供的 `[36,44,9,22]` 运行时预期与本文件 stage 40 实测**完全吻合**，构成独立验证 |
| `notes/map-format.md` | 该文件顶部的 2026-10-20 更正已经指向 `0x53D910`，与本文件一致 |
| `third_party/konoha-workshop/源码/editor/asset_imports.js` | **只读**规则来源；本文件所有条目均已在本 ROM 上重新验证 |

---

## 11. 附：复现命令清单

```powershell
# 1. 单图占用与余量
python tools/tile_asset_rules.py rom/base.gba --stage 40

# 2. 单格替换试算（不写 ROM）
python tools/tile_asset_rules.py rom/base.gba --stage 0 --x 3 --y 5 --terrain 7

# 3. 带 32x16 素材像素（原始 512 字节调色板索引）算实际图块负载
python tools/tile_asset_rules.py rom/base.gba --stage 0 --x 3 --y 5 --asset asset32x16.bin

# 4. 47 张地图全量余量 + 最紧张地图
python tools/tile_asset_rules.py rom/base.gba --all

# 5. 三类失败条件的合成边界用例
python tools/tile_asset_rules.py rom/base.gba --selftest

# 6. 全部 47 张地图各替换一格的内存端到端模拟
python tools/tile_asset_rules.py rom/base.gba --simulate-all

# 7. 导出 JSON（用 tools.lib.io.write_text，保证 LF）
python tools/tile_asset_rules.py rom/base.gba --all --json build/tile-asset-rules.json
```
