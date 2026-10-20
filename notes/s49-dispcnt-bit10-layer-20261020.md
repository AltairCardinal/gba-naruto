# DISPCNT bit 10 = BG2 启用：移动范围覆盖层是独立 BG 层，图形来自 ROM 0x080B9E94

日期：2026-10-20

## 问题

原版游戏中，把 `DISPCNT` 的 bit 10 置位对战场画面产生什么效果？置位后出现的图形由**哪个
ROM 资源**供给？特别地：既有工具 `tools/butano/analyze_s49_movegrid_mechanism.py` 把 bit 10
标注为 `bg3_char_base_10000`（CGB 语义），即「原版用同一个背景层、只切换 character base
来画出移动范围／压暗层」。本轮要回答：

1. bit 10 在**普通 GBA** 语义下到底是什么？
2. 置位时**哪一层**的渲染发生变化？变化落在 VRAM 的**哪些区间**？
3. 出现的图形来自**哪个 ROM 资源**（偏移／产物路径）？
4. 移动范围覆盖层是「独立背景层 + 自己的图块集」，还是「地图层的暗色副本」？

## 结论摘要

1. **bit 10 = BG2 启用**（GBA 语义），**不是** character base 选择位。既有用工具的 CGB 风格
   字段表对本 GBA 标题不适用（见「证据 A」）。
2. bit 10 打开的 **BG2 就是移动范围覆盖层**：它有**自己的 tilemap**、**自己的图块集**
   （网格／边框块）、**自己的调色板 bank 12**。
3. 图形 ROM 资源 = **LZ77 记录 `0x080B9E94`**（压缩 198 B → 1024 B = 32 个 4bpp 图块），
   装载目的地 **VRAM `0x06002000`**；配套调色板 = **LZ77 记录 `0x080B9F5C`**（32 B），
   装载目的地 **PRAM `0x05000180`**（= bank 12）。装载代码在 `0x080694C4` 一带。
4. **「暗色副本 + 切换 character base」假设被否定**：地图层（BG0）在两帧之间**一个字节都没变**
   （tilemap 0/1024 cell 变化，图块区 0 字节变化），bit 10 只是把一个独立的 BG2 层打开。
5. **未确立**：两份收据的 PNG 与其 VRAM/IO/PRAM dump **不自洽**（详见「未确立」第 1 条），因此「屏幕上到底
   长什么样」只能用 PNG 单独说明，不能用 dump 交叉验证。

## 方法（全部只读；逆向树未写入）

工作树 `/Users/altair/github/gba-naruto`；逆向树 `/Users/altair/github/gba-naruto-reverse`
**只读**。ROM `rom/base.gba`（SHA-256 `1198ece7…59d05b`，已复核）。Python 一律
`/usr/local/bin/python3`（3.14.3）。未运行 mGBA，未跑任何重活。

收据（同帧截图 + PRAM + VRAM + OAM + IO）：

- `artifacts/s49-original-field-frame-v1/`（walk step-17，DISPCNT=0x1940）
- `artifacts/s49-original-movegrid-frame-v1/`（walk step-19，DISPCNT=0x1D40）
- `artifacts/s49-original-grid16-frame-v1/`（walk step-16，DISPCNT=0x1D40）
- `artifacts/s49-original-banner-frame-v1/`（walk step-15，DISPCNT=0x1940）

关键步骤（`/usr/local/bin/python3 - <<'PY' … PY` 内联脚本）：

1. **IO 区逐字节比较**：`io-00.bin` 的 0x60 字节在 field / movegrid 之间只有 `0x00`（DISPCNT）
   不同：`0x1940` vs `0x1D40`，异或 = `0x0400`（仅 bit 10）。
2. **VRAM 逐字节差分**：`vram-00.bin`（0x18000 B）两两相减，合并间隔 <16 B 的碎片，得到
   §3 的区间表；同时用「同一收据内连续帧」差分区分**动画噪声**与**状态切换**。
3. **tilemap 解码**：按 BGxCNT 的 screen base / char base 解出 4 张 tilemap 的 cell 值
   （tile index、palette bank、H/V flip），统计两帧之间的 cell 差异。
4. **图块图形解码**：把 VRAM 中 4bpp 图块展开成 8×8 索引矩阵（见 §3 C）。
5. **PNG↔VRAM 一致性检验**：把 PNG 每个 8×8 cell 反解成 4bpp 索引（4bpp 与 8bpp 两种、
   32 个 palette bank、H/V 翻转 4 变体）后在 VRAM 全量图块哈希里查（`artifacts/.../vram-00.bin`）。
6. **ROM 资源检索**：对 `rom/base.gba` 做子串搜索（4bpp 原始块、8bpp 展开块、单图块）→
   未命中；随后用逆向树已签的 LZ77 清单 `reverse/artifacts/rom-pointer-lz77-inventory-v1/`
   定位记录 `0x080B9E94`，并**自行按 GBA LZ77 格式解压核对**。
7. **装载代码核对**：读 `rom/base.gba` 的 `0x080694C4..0x080694D6` THUMB 窗口与字面量池。

## 证据

### A. bit 10 的语义：BG2 enable

- mGBA 的 **GBA 核**（不是 CGB 核）声明：
  `build/macos-mgba/workspace/include/mgba/internal/gba/video.h:118-122`
  `Bg0Enable=8, Bg1Enable=9, Bg2Enable=10, Bg3Enable=11, ObjEnable=12`。
  该 GBA 核还给出 `BGCNT`：CharBase=bits2-3、ScreenBase=bits8-12（`video.h:137-142`）。
- `DISPCNT` bit 3（CGB 模式位）在本 ROM 全程为 0（0x1940 / 0x1D40），故不存在 CGB 语义。
- 反证 CGB 读法：若按 CGB 语义把 bit 8-11 当 char base 选择位，则 0x1940 会解成
  「**没有任何 BG 被启用**」，与被渲染的战场矛盾。
- 既有工具的字段表 `tools/butano/analyze_s49_movegrid_mechanism.py:49-61` 用的是 CGB 风格
  （bit 10 = `bg3_char_base_10000`、bit 12 = `obj_enable`）。**该命名对本标题是错的**，
  应改为 GBA 语义（bit 8-11 = BG0..BG3 enable）。本轮只记录，未修改该工具。
- 寄存器实测（field / banner vs movegrid / grid16）：只有 DISPCNT 一个字不同；PRAM bank 0-3
  逐字节相同（整体只有 bank 16 变化）；OAM 活跃精灵两帧都是 20 个；BLDCNT=0x0000、
  WININ=0x00F0、WINOUT=0xFFFF、MOSAIC=0x3F3F。

### B. 四层的 VRAM 归属（本次采用 mGBA GBA 渲染器的换算，见「未确立」第 4 条）

| 层 | DISPCNT 启用 | BGCNT | priority | char base | screen base | tilemap 落点 |
|---|---|---|---|---|---|---|
| BG0 | 是 | 0x0007 | 3 | block1 → 0x06004000 | block0 | VRAM 0x0000-0x07FF |
| BG1 | **否** | 0x0105 | 1 | block1 → 0x06004000 | block1 | VRAM 0x0800-0x0FFF |
| BG2 | **bit 10** | 0x0202 | 2 | block0 → 0x06000000 | block2 | VRAM 0x1000-0x17FF |
| BG3 | 是 | 0x030C | 0 | block3 → 0x0600C000 | block3 | VRAM 0x1800-0x1FFF |

四张 tilemap 的内容与层次自洽：0x0000 = 地图（210 种图块、palette bank 0-4）、
0x0800 = 备用层（125/133 交替、bank 0）、0x1000 = 全部 bank 12、0x1800 = 全部 bank 14/15（UI）。

### C. VRAM 差分（field → movegrid，逐字节）

| VRAM 区间 | 归属 | 变化 |
|---|---|---|
| 0x01198-0x014DE | **BG2 tilemap**（0x1000-0x17FF） | **212/1024 cell 变化**，新值全部 palette bank 12，图块 256-265 |
| 0x01883-0x01B4D | BG3 tilemap（0x1800-0x1FFF） | 72 cell 变化：同一张空图块 448，palette bank 字段 14 → 0（视觉无差别） |
| 0x0C460-0x0C81E | BG3 char base（0xC000-0xFFFF，tile 35..64） | 图块数据变化（这些 tile 不被 BG3 的 tilemap 引用） |
| 0x1009A-0x103CF | OBJ 图块区（0x10000-0x17FFF） | **动画噪声**：同一收据内连续帧之间同样在变 |
| 0x0000-0x07FF（BG0 tilemap） | 地图 | **0 字节变化**（0/1024 cell） |
| 0x4000-0x7FFF（BG0/BG1 char base） | 地图图块 | **0 字节变化** |

### D. BG2 覆盖层的图形

BG2 的 tilemap 只用图块 256-281，其图形在 VRAM `0x2000-0x2340`（= BG2 char base + tile 256）。
索引矩阵（4bpp 颜色索引）：

- 256/257：全 0（空）
- 258/259/260/261：1 像素边线（索引 1，右边／下边／下边／右下角）
- 262/263/264/265：实心填充 2 + 1 像素边框 3
- 270/272：实心填充 6 + 边框 7
- 278/279/280/281：实心填充 a + 边框 b

即一套**网格／高亮方块**图块（含边与角），配 palette bank 12
（bank 12 有意义项：index 1=0x45A8、2=0x7F23(青)、3=0x55A1、6=0x00FF、7=0x00B4、10=0x2529、
11=0x1084，其余为 0）。

### E. ROM 资源

1. 逆向树已签 LZ77 清单条目
   `reverse/artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json`：
   `gba_address 0x080B9E94`、`kind "graphics"`、`load_route "LZ77UnCompVram_wrapper"`、
   `destination_addresses ["0x06002000"]`、`literal_load_users ["0x080694C6"]`、
   `compressed_size 198`、`decompressed_size 1024`、
   `decompressed_sha256 0f86c803…16ce40`。
2. **自行解压核对**（GBA LZ77：byte0=0x10、size=LE24、flag byte MSB-first、距离+1）：
   `0x080B9E94` 解压出 **1024 B**，与
   `reverse/artifacts/residual-lz77-graphics-relocation-v1/graphics_080b9e94.4bpp.bin`
   **逐字节相同**，也与两份收据的 **VRAM 0x2000-0x2400** 逐字节相同（field 与 movegrid 都一样，
   说明该图块集常驻 VRAM，只有 tilemap 变）。压缩跨度 0x080B9E94..0x080B9F5A（198 B）。
3. 配套调色板：`0x080B9F5C` 是紧邻的下一条 LZ77 记录（32 B），解压结果与两份收据的
   **PRAM 0x180-0x19F（bank 12）逐字节相同**。
4. 装载代码：`rom/base.gba` 的 `0x080694C4..0x080694D6` 为
   `push {lr}; ldr r0,[pc,#0x18]; ldr r1,[pc,#0x18]; bl 0x0809C0E8; b r5;` 两次
   （callsite `0x080694CA`、`0x080694D2`）；字面量池 `0x080694E0 = 0x080B9E94`、
   `0x080694E8 = 0x080B9F5C`、`0x080694EC = 0x05000180`、`0x080694E4 = 0x06002000`。
   （目的寄存器的精确指派本轮未逐条反汇编；但两条载荷的**内容**已分别与 VRAM 0x06002000
   和 PRAM 0x05000180 对上，这是比寄存器解码更强的证据。）
5. ROM 里**没有**未压缩的同一份图形：对 832 B 原始 4bpp 块、3328 B 的 8bpp 展开块、
   以及单图块逐一搜索 `rom/base.gba` 全部未命中 → 图形只以 LZ77 形式存在。

## 结论

移动范围覆盖层是**一个独立的背景层（BG2），带自己的图块集与自己的调色板 bank 12**，
**不是**「同一张地图的暗色副本」：**地图层 BG0 的 tilemap 与图块数据在两帧之间完全没变**；
唯一被改写的是 BG2 的 tilemap（212 个 cell），而 bit 10 做的事情只是**把 BG2 这层打开**
（GBA 语义下 DISPCNT bit 10 = BG2 enable）。bit 10 与 character base 无关；
「character base 被该 bit 切换」的说法源自 CGB 语义，对本 GBA 标题不成立。

## 未确立（不当作已知）

1. ~~**收据的 PNG 与其 dump 不自洽**~~ ⇒ ⚠️ **第 20 轮更正**：**收据自洽**（从同帧 dump 重建 = PNG 38,400/38,400 一致）。当年「field 帧 PNG 的战场区 510 个 8×8 cell 中 **0 个**能在同帧
   dump 出的 VRAM 里找到对应图块（4bpp/8bpp × 32 bank × H/V 翻转全试过）；整帧 600 个 cell
   里只有 **27** 个命中，且全部落在底部状态栏（rows 128-159），命中最多的是 VRAM `0x0E880`
   的图块（bank 14/15 各 21 次）——但这些图块没有被任何 dump 出的 tilemap 引用。
   movegrid 帧 PNG 有 **55.5%** 的像素颜色**不在**该帧 PRAM 里（field/banner 帧是 100%）。→ 这两份 PNG 只能当「画面长什么样」的旁证，不能用来验证渲染机制；本轮的层判定
   只用 dump。
2. 覆盖层 32×32 tilemap 的**内容**（哪些格子被点亮）由运行时生成，**未找到**对应的 ROM 资源。
3. BG3 的两处变化未解释：72 个 cell 只是空图块的 palette bank 字段改写；`0x0C460-0x0C81E`
   的图块数据变化对应的 tile 35..64 不被 BG3 的 tilemap 引用。
4. **screen base 换算约定**存在未裁决的分歧：本轮采用 mGBA GBA 渲染器的
   `screenBase = block << 11`（`build/macos-mgba/workspace/src/gba/renderers/video-software.c:784`；
   GL 路径 `src/gba/renderers/gl.c:1598` 以 16-bit 单位等效）以及逆向树自己的工具
   （`reverse/tools/export_residual_wram_tilemap_resource_ownership.py:323-324`），
   即 block N → VRAM N×0x800；这与常见 GBATEK 表述（4 KB 单位、0x06008000 起）不一致，
   而本轮没能取到 GBATEK 原文（problemkaputt.de 抓取被截断）来裁决。在 mGBA 约定下四张
   tilemap 与 BG0..BG3 完美对应、ROM 载荷又正好落在 `0x06002000` = BG2 char base + tile 256，
   自洽；但**真机硬件是否同样如此未确立**。（注：char base 用 16 KB 单位 = 0x4000，
   两套约定一致，因此 §3 里 0x0C000-0x0FFFF 属 BG3 图块区的判断不受影响。）
5. 覆盖层在屏幕上的**确切颜色**无法用 PNG 核对（见 1）；只能从 PRAM bank 12 读出
   青绿色项（index 2 = 0x7F23 = (3,25,31)）。
6. 覆盖层是「可达范围高亮」还是「不可达范围压暗」——**语义未确立**：本轮只证明它是一层
   独立 BG、用网格块，未证明格子集合与可达性规则的关系。

## 建议下一步

- 在逆向树侧新增一条「本标题的 DISPCNT/BGCNT 语义 = GBA（非 CGB）」的记录，并把
  `reverse/tools/analyze_dialogue_render.py` 等处对 screen base 的写法统一标注来源。
- 若要闭合 (2)/(6)：在 mGBA 里断点 `0x080694C4` 之后跟 BG2 tilemap 的写入者（VRAM
  0x06001000 目标地址），即可定位「可达范围 → 格子集合」的那段运行时逻辑。
- 若要闭合 (1)/(4)：用同一收据的 PNG 与 dump 做一致性门禁，避免再把 PNG 当同帧证据。

## 引用

- mGBA GBA 核寄存器定义：`build/macos-mgba/workspace/include/mgba/internal/gba/video.h:118-142`；
  软件渲染器 screen/char base 换算：`src/gba/renderers/video-software.c:781-784`。
- 逆向树 LZ77 清单与图形迁移产物：
  `reverse/artifacts/rom-pointer-lz77-inventory-v1/rom-pointer-lz77-inventory.json`、
  `reverse/artifacts/residual-lz77-graphics-relocation-v1/`（`graphics_080b9e94.4bpp.bin`，
  `full-relocation-spec.json` 的 `source_pointer 0x080B9E94`）。
- 逆向树既有 screen base 约定：`reverse/tools/export_residual_wram_tilemap_resource_ownership.py:314-325`。
- 本轮收据：`artifacts/s49-original-{field,movegrid,grid16,banner}-frame-v1/`。
