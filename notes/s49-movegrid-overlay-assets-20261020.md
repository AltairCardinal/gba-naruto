# 移动范围覆盖层的图形资产：从原版 ROM 里把 BG2 的图块集与调色板搬成机器可读形式

日期：2026-10-20

## 问题

`notes/s49-dispcnt-bit10-layer-20261020.md` 已经钉死了「移动范围覆盖层 = 一层独立的 BG2，
带自己的图块集和调色板 bank 12」，并指出图形来自 ROM 的 LZ77 记录 `0x080B9E94`（图块）、
`0x080B9F5C`（调色板），装载到 VRAM `0x06002000` / PRAM `0x05000180`。但那条记录只给了
**地址**，没有把这两份载荷变成**可复现、可校验的产物**：

1. 没有一个工具能把它们解出来并写成机器可读的形式（PNG / 原始字节 / 调色板收据 / 清单）；
2. 解压后的字节、哈希、落点没有被钉进任何可回归的断言里；
3. 没有一个**失败即停**的门禁把「ROM 变了 / 载荷变了 / 落点变了」挡住。

本轮要做的就是：做一个**失败关闭**的导出器，把这两份载荷从 ROM 里搬出来，并用**已经采到的
同帧收据**（VRAM / PRAM dump）逐字节对账，证明搬出来的东西就是当年游戏里驻留的那份。

## 结论摘要

1. **导出器**：`tools/butano/export_s49_movegrid_overlay.py`，ROM 由 SHA-256 钉死，
   LZ77 解压带严格边界检查，解压长度必须与期望一致，任何不一致一律非 0 退出。
2. **图块载荷**：`0x080B9E94` 压缩 198 B → **解压 1024 B**
   （SHA-256 `0f86c803…16ce40`），= 32 个 4bpp 图块。
3. **调色板载荷**：`0x080B9F5C` 压缩 36 B → **解压 32 B**
   （SHA-256 `d198ec85…e7e84`），= 16 条 BGR555 = 调色板 **bank 12**。
4. **逐字节对账成立**：4 份同帧收据 × 6 帧 = 24 帧，
   **VRAM `0x2000-0x2400` 与图块载荷逐字节相同**、**PRAM `0x180-0x19F` 与调色板载荷逐字节相同**。
5. **图块集结构**（由像素自己分类得出，不靠手写表）：8 个空块 + 4 个 1 像素边线块 +
   5 组「实心 + 1 像素边框」的实心块（每组 4 个变体：素 / +右边 / +下边 / +右下角）。
6. **本轮更正了两处既有说法**（见「证据 F」）：
   ① `notes/s49-dispcnt-bit10-layer-20261020.md` 里的 **LZ77 记法**按教科书写法**解不出**本 ROM 的 blob；
   ② 同一条记录里 **bank 12 的调色板下标**（`6=0x00FF、7=0x00B4、其余为 0`）与 ROM/PRAM 实读**对不上**。
7. **落点更正**：BG2 的 **tilemap 在 VRAM `0x06001000`**（不是 `0x06002000`）；
   `0x06002000` 是**字符基址 `0x06000000` + 图块 256** 的图块数据落点。

## 方法（全部只读 ROM；未运行 mGBA）

工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）。
Python 一律 `/usr/local/bin/python3`（3.14.3）。**没有运行 mGBA、没有跑重活**，
只读取了树里已经存在的同帧收据产物。

步骤：

1. **ROM 闸门**：对仓库根目录的 `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba`
   算 SHA-256，必须等于 `1198ece7…59d05b`，否则拒绝运行。
2. **按逆向树已签清单的解码器解压**（`reverse/tools/export_rom_pointer_lz77_inventory.py`
   的 `_parse_lz77`），并加边界检查：头字节必须 `0x10`、声明长度必须与期望一致、
   任何回引距离超过已产出字节数即失败关闭。
3. **对账**：从 4 份同帧收据读 `vram-*.bin` / `pram-*.bin`，
   检查 `VRAM[0x2000:0x2400] == tiles`、`PRAM[0x180:0x1A0] == palette`。
4. **解码图块**：4bpp 每行 4 字节、每字节两像素、**低半字节在前（左像素）**（⚠️ 第 26 轮更正，原写「高半字节在前」；已按原版像素反证并重导出）；
   拼成 8 列 × 4 行 = 64×32 像素的索引图，另出一张按 bank 12 上色的渲染图。
5. **图块分类**：由像素自己推出角色（空 / 竖边线 / 横边线 / 实心 + 边框），不写死每个图块。
6. **与机制收据对账**：读 `artifacts/s49-original-movegrid-mechanism-v1/mechanism.json`，
   比对它记录的可比字段。
7. **门禁**：`tests/test_s49_movegrid_overlay.py`，18 项 unittest 全绿。

## 证据

### A. ROM 源记录（字节级）

| 项 | 图块 | 调色板 |
|---|---|---|
| ROM 地址 | `0x080B9E94` | `0x080B9F5C` |
| 文件偏移 | `0x000B9E94` | `0x000B9F5C` |
| 压缩跨度 | `0x080B9E94-0x080B9F5A`（198 B） | `0x080B9F5C-0x080B9F80`（36 B） |
| 压缩体 SHA-256 | `b4e197b91b4e6a3d7650a02d785af8fc37e1083c0b67d5355966b3fd8a85c733` | `2e1e27099e8bbed038c35e677aefa9c90a754ea1423f7e653c5c1ba52585967b` |
| 解压长度 | **1024 B** | **32 B** |
| 解压 SHA-256 | `0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40` | `d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84` |

两条记录**不相邻**：图块记录结束于 `0x080B9F5A`，调色板记录起始于 `0x080B9F5C`，
中间隔 2 字节。

### B. 装载落点（ROM 字面量池，与惯例无关）

`0x080694E0..0x080694EF` 的四个字面量：

```
0x080694E0 = 0x080B9E94   (源：图块)
0x080694E4 = 0x06002000   (目的：VRAM)
0x080694E8 = 0x080B9F5C   (源：调色板)
0x080694EC = 0x05000180   (目的：PRAM = bank 12)
```

⇒ 目的地 `0x06002000` / `0x05000180` 是**游戏自己写的常量**，不依赖任何 screen-base 约定。

### C. 与同帧收据的逐字节对账（本轮的核心证据）

4 份收据 × 每份 6 帧：

| 收据 | `VRAM[0x2000:0x2400] == tiles` | `PRAM[0x180:0x19F] == palette` |
|---|---|---|
| `s49-original-field-frame-v1` | 6/6 相同 | 6/6 相同 |
| `s49-original-movegrid-frame-v1` | 6/6 相同 | 6/6 相同 |
| `s49-original-grid16-frame-v1` | 6/6 相同 | 6/6 相同 |
| `s49-original-banner-frame-v1` | 6/6 相同 | 6/6 相同 |

⇒ 图块与调色板是**常驻**的；两帧之间被改写的是 **BG2 的 tilemap**，不是图块数据。
这与既有结论「地图层一个字节都没变、动的是 BG2 的 tilemap」一致。

### D. 图块集结构（32 个 4bpp 图块，索引 256-287）

由像素自证，**不是**手写表：

| 图块索引 | 角色 | 颜色索引 |
|---|---|---|
| 256、257、282-287 | 空（全 0） | — |
| 258 | 竖边线，1 px，x = 6 | 1 |
| 259、260 | 横边线，1 px，y = 7 | 1 |
| 261 | 竖边线 x=6 + 横边线 y=7 | 1 |
| 262-265 | 实心 + 边框 | 填充 2 / 边框 3 |
| 266-269 | 实心 + 边框 | 填充 4 / 边框 5 |
| 270-273 | 实心 + 边框 | 填充 6 / 边框 7 |
| 274-277 | 实心 + 边框 | 填充 8 / 边框 9 |
| 278-281 | 实心 + 边框 | 填充 10 / 边框 11 |

每组 4 个变体依次为「素 / +右边 / +下边 / +右下角」。
⇒ 一套**网格／高亮方块**图块，与 `notes/s49-dispcnt-bit10-layer-20261020.md` §D 的读法一致。

### E. 调色板 bank 12（16 条 BGR555，PRAM `0x180-0x19F`）

8-bit 换算一律用 `(c << 3) | (c >> 2)`：

| 下标 | BGR555 | RGB5 | RGB8 | 备注 |
|---|---|---|---|---|
| 0 | `0x0000` | (0,0,0) | (0,0,0) | 透明 |
| 1 | `0x45A8` | (8,13,17) | (66,107,140) | 边线色 |
| 2 | `0x7F23` | (3,25,31) | (24,206,255) | 青（实心） |
| 3 | `0x55A1` | (1,13,21) | (8,107,173) | 青的边框 |
| 4 | `0x00FF` | (31,7,0) | (255,57,0) | 橙（实心） |
| 5 | `0x00B4` | (20,5,0) | (165,41,0) | 橙的边框 |
| 6 | `0x02FF` | (31,23,0) | (255,189,0) | 黄（实心） |
| 7 | `0x01B2` | (18,13,0) | (148,107,0) | 黄的边框 |
| 8 | `0x03F5` | (21,31,0) | (173,255,0) | 绿（实心） |
| 9 | `0x020A` | (10,16,0) | (82,132,0) | 绿的边框 |
| 10 | `0x2529` | (9,9,9) | (74,74,74) | 灰（实心） |
| 11 | `0x1084` | (4,4,4) | (33,33,33) | 灰的边框 |
| 12-15 | `0x0000` | (0,0,0) | (0,0,0) | 未用 |

### F. 两处更正（对既有记录的订正）

**F-1｜LZ77 记法**：既有记录把本 ROM 的 blob 描述为「GBA LZ77：byte0=0x10、size=LE24、
flag byte MSB-first、距离+1」。按**教科书写法**（长度在第二个字节的低半字节、
距离 = `((b2 & 0xF0) << 4) | b1`）**根本解不开**这条 blob：解到第一个匹配 token
（`0xF0 0x01`）时距离算出 496，而此时只产出了 2 字节 ⇒ 直接越界。
**能解开的是逆向树已签清单所用的记法**（`reverse/tools/export_rom_pointer_lz77_inventory.py`
的 `_parse_lz77`）：

```
头：0x10；接着 24-bit 小端解压长度
flag 字节，bit 7 → bit 0 依次消费
  bit == 0 → 1 字节字面量
  bit == 1 → 2 字节匹配 token：first / second
       length   = (first >> 4) + 3
       distance = (((first & 0x0F) << 8) | second) + 1
```

本轮按这套记法解出的 1024 B 与 VRAM `0x2000-0x2400` **逐字节相同**，
按另一套记法则无解 ⇒ 这不是风格问题，是**记错就解不出来**。

**F-2｜bank 12 的调色板下标**：既有记录写「index 1=0x45A8、2=0x7F23(青)、3=0x55A1、
**6=0x00FF、7=0x00B4**、10=0x2529、11=0x1084，**其余为 0**」。
ROM 解压结果与 PRAM `0x180-0x19F` **逐字节相同**，实读是：
`4=0x00FF`、`5=0x00B4`，而 `6=0x02FF`、`7=0x01B2`、`8=0x03F5`、`9=0x020A` **均非 0**。
⇒ 既有记录把橙/深橙那一对**下标写大了 2**，并且漏掉了黄、绿两族共 4 个非零项。
既有记录的**图块读法**（实心 6 + 边框 7、实心 a + 边框 b）本身是对的，
错的是它给调色板下标对号入座的那一步。

### G. 与机制收据的对账

`artifacts/s49-original-movegrid-mechanism-v1/mechanism.json` 里**可比**的字段：

| 收据字段 | 值 | 本轮复核 |
|---|---|---|
| `move_range_frame.registers.dispcnt` | `0x1D40` | bit 10 置位（= BG2 启用）；战场帧 `0x1940` 该位为 0 |
| `move_range_frame.registers.bgcnt[2]` | `0x0202` | 字符基址块 0、屏基址块 2、优先级 2、4bpp |
| `move_range_frame.map_layer_unchanged.bg0_tile_graphics_bytes_changed` | 0 | 复算 = 0 |
| `move_range_frame.map_layer_unchanged.bg1_tile_graphics_bytes_changed` | 0 | 复算 = 0 |
| `move_range_frame.map_layer_unchanged.bg2_region_bytes_changed` | 706 | 复算 = 706 |
| `move_range_frame.bg_tilemap_cells` | bg0 1 / bg1 0 / bg2 706 / bg3 175 | 复算完全一致 |

字段位序的来源也查清了：mGBA 的 **GBA 核**里 `BGCNT` 的位域是
`Priority = bit 0-2`、`CharBase = bit 2-3`、`Mosaic = bit 6`、`256Color = bit 7`、
`ScreenBase = bit 8-12`、`Overflow = bit 13`
（`build/macos-mgba/workspace/include/mgba/internal/gba/video.h:136-143`），
渲染器按 `charBase = CharBase << 14`、`screenBase = ScreenBase << 11` 换算
（`src/gba/renderers/video-software.c:781,784`），
而 IO 偏移 `BG0CNT = 0x008 … BG3CNT = 0x00E`
（`include/mgba/internal/gba/io.h:17-32`）。
机制收据用的字段表与偏移**与 mGBA 的 GBA 核一致**，因此它的
`char base block 0 → 0x06000000`、`screen base block 2 → 0x06001000` 是自洽的，
并且与观测到的 VRAM 布局（地图图块在 `0x4000`、BG3 图块在 `0xC000`、
四张 tilemap 在 `0x0000/0x0800/0x1000/0x1800`）逐条对得上。

### H. BG2 tilemap 的观测（本轮复算）

BG2 的 tilemap 在 **VRAM `0x06001000`**（屏基址块 2 × 2 KB），32×32 = 1024 格。

- 移动网格帧：**全部 1024 格都是 palette bank 12**；被引用的图块索引与次数为
  `256×315、257×69、258×36、259×27、260×69、261×37、262×71、263×23、264×71、265×23、
  270×1、272×1、278×96、279×29、280×120、281×36`。
- ⇒ 32 个图块里 **16 个被引用**；`266-269、271、273-277、282-287` 未被引用。
- 变动格数：**战场帧 → 移动网格帧 = 212 / 1024**；战场帧 → grid16 帧 = 164 / 1024；
  移动网格帧 → 横幅帧 = 706 / 1024（与机制收据的 706 一致）。

## 复现命令与实际输出

```bash
cd /Users/altair/github/gba-naruto
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

/usr/local/bin/python3 tools/butano/export_s49_movegrid_overlay.py \
  --rom "火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba" \
  --out-dir artifacts/s49-original-movegrid-overlay-v1 \
  --evidence-dir artifacts/s49-original-movegrid-frame-v1 \
  --evidence-dir artifacts/s49-original-grid16-frame-v1 \
  --evidence-dir artifacts/s49-original-field-frame-v1 \
  --evidence-dir artifacts/s49-original-banner-frame-v1 \
  --evidence-baseline artifacts/s49-original-field-frame-v1
```

实际输出：

```
rom            火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba  sha256=1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b
tiles          0x080B9E94 -> 1024 B  sha256=0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40
palette        0x080B9F5C -> 32 B  sha256=d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84
out-dir        artifacts/s49-original-movegrid-overlay-v1
manifest       artifacts/s49-original-movegrid-overlay-v1/manifest.json
manifest sha256 da42e2228a49e7dd81d64688641842ac7c4125fa14a20273d96021ad724f82db
```

自检（重新读回产物、重新哈希、重新解压 ROM）：

```bash
/usr/local/bin/python3 tools/butano/export_s49_movegrid_overlay.py --verify
```

```
verified 5 output files in /Users/altair/github/gba-naruto/artifacts/s49-original-movegrid-overlay-v1
manifest sha256 da42e2228a49e7dd81d64688641842ac7c4125fa14a20273d96021ad724f82db
```

门禁：

```bash
/usr/local/bin/python3 -m unittest tests.test_s49_movegrid_overlay -v
```

```
Ran 18 tests in 1.089s

OK
```

产物哈希（`shasum -a 256 artifacts/s49-original-movegrid-overlay-v1/*`）：

```
da42e2228a49e7dd81d64688641842ac7c4125fa14a20273d96021ad724f82db  manifest.json
d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84  movegrid-palette.bin
6912cb9c41b815465ec5b6c5a1cb3dfa488738aa4d8db61675b82fa1ef90d40d  movegrid-palette.json
0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40  movegrid-tiles-4bpp.bin
e1146dfc69758ffdbf39181ab722499e8708c9a2cd803cfb33286f29cd16ecc0  movegrid-tiles-index.png
e944501164e56cff65c6c3f323b728c6a52cbccb27c37dc911952c745a6ce6dd  movegrid-tiles-render.png
```

**幂等性**：清单里**不写时间戳**（`determinism.timestamp = "omitted"`），
因此同样的输入重跑得到**逐字节相同**的产物；上面的 `manifest sha256` 在重跑前后一致
（`da42e222…f82db`），测试里也用「跑两次进两个目录、逐文件比字节」把这一点钉住。

## 产物清单

`artifacts/s49-original-movegrid-overlay-v1/`

| 文件 | 内容 |
|---|---|
| `movegrid-tiles-4bpp.bin` | 解压后的 32 个 4bpp 图块原始字节（1024 B） |
| `movegrid-tiles-index.png` | 64×32 灰度索引图，像素值 = 4bpp 颜色下标（0-15） |
| `movegrid-tiles-render.png` | 同一张图按 bank 12 上色（便于肉眼核对） |
| `movegrid-palette.bin` | 解压后的 16 条 BGR555 原始字节（32 B） |
| `movegrid-palette.json` | 调色板收据（bank 号、落点、逐条 BGR555 / RGB5 / RGB8） |
| `manifest.json` | 输入哈希、图块索引 → 画面位置映射、跨检结果、`scope` 块 |

## 未确立（不当作已知）

1. **哪些格子被点亮**：BG2 tilemap 的内容是运行时生成的，**没找到**对应的 ROM 记录；
   本轮只证明了「载荷常驻、tilemap 被改写」，没有证明格子集合的来源。
2. **覆盖层的语义**：是「可达范围高亮」还是「不可达范围压暗」**未确立**。
   本轮从字节只能看到它是一层独立的、用网格块的 BG2。
3. **自然执行可达性**：收据来自脚本化 walk，**不是**覆盖率证明；
   「游戏在任何自然流程下都会画这一层」**未确立**。
4. **32 个图块是否全部被使用**：观测到的帧只引用了 16 个；其余 16 个**未确立**是否被使用。
5. **screen base 单位约定**（mGBA 的 `block << 11` vs 常见的 4 KB 表述）**本轮未裁决**。
   但载荷落点 `0x06002000` / `0x05000180` 由**装载器字面量池**与 **VRAM/PRAM dump**
   独立确认，与该约定无关。
6. **真机硬件的 `BGCNT` 字段位序**未在本轮独立验证；本轮采信 mGBA **GBA 核**的
   `GBARegisterBGCNT` 定义（`video.h:136-143`），它与既有机制收据的字段表一致。
7. ~~**不做像素级断言**：同帧收据的 PNG 与它自己的 dump **不自洽**~~ ⇒ ⚠️ **第 20 轮更正**：用 `tools/butano/render_scenario_41_gpu.py` 从同帧的 VRAM/PRAM/OAM/IO **重建**该帧，与 PNG **38,400/38,400 像素完全一致**（门禁 `tests/test_s49_receipt_self_consistency.py`）⇒ **收据完全自洽**
   （见 `notes/s49-dispcnt-bit10-layer-20261020.md`「未确立」第 1 条），
   因此本轮只做**字节级**对账，不对「屏幕上长什么样」下任何结论。
8. **其它 BG 层的归属未复核**：本轮只认 BG2（`DISPCNT` bit 10）这一层。

## 引用

- 既有层判定与字节级细节：`notes/s49-dispcnt-bit10-layer-20261020.md`。
- 逆向树已签 LZ77 清单与解码器：
  `reverse/tools/export_rom_pointer_lz77_inventory.py`（`_parse_lz77`）、
  `reverse/artifacts/rom-pointer-lz77-inventory-v1/`。
- 机制收据：`artifacts/s49-original-movegrid-mechanism-v1/mechanism.json`。
- 同帧收据：`artifacts/s49-original-{field,movegrid,grid16,banner}-frame-v1/`。
- mGBA GBA 核：`build/macos-mgba/workspace/include/mgba/internal/gba/video.h:136-143`
  （BGCNT 位域）、`.../gba/io.h:17-32`（IO 偏移）、
  `build/macos-mgba/workspace/src/gba/renderers/video-software.c:781,784`（基址换算）。
- 本轮产物：`artifacts/s49-original-movegrid-overlay-v1/`、
  工具 `tools/butano/export_s49_movegrid_overlay.py`、
  门禁 `tests/test_s49_movegrid_overlay.py`。
