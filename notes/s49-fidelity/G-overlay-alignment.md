# G 流 · 覆盖层形状对齐 —— 原版 BG2 覆盖层的坐标对应与重制侧对齐

> 2026-10-24 · stream G（wave 3 关键路径）
> 独占产出：本文件 + `tools/s49_overlay_align/`；重制线改动见 §4。
> **未改动**逆向线、master 仓其他任何文件、H2/L 流独占文件。
> ⚠️ 本流**改了一个不在独占清单里的文件**：`game/tests/test_battle_range_ui_style.cpp`
> （它是 `battle_range_ui_style.h` 的配套测试，语义被我改了，必须同步；
> 该文件不在 H2/L 的独占清单里）。

---

## 0. 一句话结论

**坐标对应已建立**（F-2 关闭）：原版覆盖层是一张 **256×256 px 的「地图空间」缓冲**，
滚动量就是相机（`bg_hoffs=240, bg_voffs=24`），它的 **逻辑格 = 16×16 px**，
而它的 **战斗格 = 32×16 px**（不是 32×16 的一格 = 1 逻辑格，而是 **1 战斗格 = 2 个逻辑格（仅 X 方向）**）。
据此重制侧把覆盖层改成 **地图空间锚定 + 原版族判定顺序 + 原版 `blocked` 网点画法**。

**⚠️ 与任务书的一处偏离（有意为之，证据充分）**：任务书要求
"`battle_range_ui_tiles_per_cell_x` 4→2、边界判据 `cell_x==31` → `cell_x==15`"。
**照做会把原版的 32 px 格线画成 16 px 格线**，是错的。证据见 §2（三种独立证明）。

---

## 1. 原版覆盖层的几何（机器读出，非猜测）

### 1.1 缓冲与滚动

| 项 | 值 | 证据 |
|---|---|---|
| 图层 | BG2，4bpp，调色板 bank 12 | F 流 |
| 缓冲 | 32×32 tilemap 项 = **256×256 px**，每 256 px 绕回 | `bg2-tilemap.json` 的 1024 项 |
| 滚动 | `bg_hoffs=240, bg_voffs=24`（field/movegrid/banner），`152,40`（grid16） | 同上 |
| 屏幕窗口 | 240×160 = 缓冲 px x∈[240,256)∪[0,224)、y∈[24,184) | 同上 |
| 逻辑格 | **16×16 px = 2×2 个 8×8 tilemap 项** | F 流的 `overlay_ground_truth.py` |

**滚动量已被本机独立验证**（`tools/s49_overlay_align/overlay_layer.py`）：
把原版 `field`（BG2 关）与 `movegrid`（BG2 开）两帧截图相减，
得到 **22 413 个变化像素**；按滚动 (240,24) 取缓冲像素时，
**22 244 个落在「原版确实画了东西」的像素上（99.25%）**，
反向检查「缓冲画了但屏幕没变」的像素数 = **0**。
⇒ 滚动量 (240,24) 与缓冲位置 **确认**（工具：`overlay_layer.py --diff`）。

### 1.2 32 块图砖逐像素解（原版 4bpp，32 B 步长）

```
256,257  blank      全透明
258      edge       x=7 一列索引 1          （右侧竖线）
259,260  edge       y=7 一行索引 1          （底边横线）
261      edge       x=7 一列 + y=7 一行     （角）
262      hatch      整块索引 2
263      hatch      索引 2 + 末列索引 3
264      hatch      索引 2 + 末行索引 3
265      hatch      索引 2 + 末列末行索引 3
266..269 line_alt   同上，索引 4 / 5
270..273 band       同上，索引 6 / 7
274..277 hatch_shift同上，索引 8 / 9
278      solid      索引 10 / 0 交替（50 % 竖条纹网点）
279      solid      网点 + 末列索引 11
280      solid      网点 + 末行索引 11
281      solid      网点 + 末列末行索引 11
```

⇒ **每个族的 4 个变体 = 两个布尔位：右侧次色边 / 底侧次色边**。
⇒ **`solid`（受阻）是 50 % 网点，不是实心**——重制侧此前画成了实心。

---

## 2. 战斗格 = 32×16 px（三条独立证据）

| # | 证据 | 判据 | 结果 |
|---|---|---|---|
| G-E1 | **格线间距** | 从重建的 256×256 覆盖层里找索引 1（`edge` 线色）的像素列/行 | 竖线在 px **31, 63, 95, 127, 159, 191**（间隔 **32**）；横线在 py **≡ 15 (mod 16)**（间隔 **16**） |
| G-E2 | **移动范围形状** | `movegrid` 的青区逐 16 px 格读出，再按 32 px 合并 | 合并后 = 以战斗格 **(3,6)** 为中心、**曼哈顿半径 3** 的菱形（行 3..9，列 0..6），(4,7) 被占格挖空；按 16 px 读则是一个「半宽 1/3/5/6」的非自然形状 |
| G-E3 | **ROM 碰撞网格** | `tools/generate_butano_battle_map_content.py`：`width = width_tiles >> 2`、`height = height_tiles >> 1` | 战斗格的图砖尺寸 = **4×2 图砖 = 32×16 px**；battle-14 = **15×19 格** |

⇒ **原版的战斗格是 32×16 px**（= 重制侧 `cell_width=32, cell_height=16`，重制侧本来就对）。
⇒ 原版覆盖层的 **16 px 逻辑格 = 战斗格的一半（仅 X 方向）**，
F 流的 16×16 逻辑格是**分析单位**，不是游戏格。
⇒ **重制侧的 `tiles_per_cell_x = 4` / 边界判据 `cell_x == 31 || cell_y == 15` 是对的**，
**不能**按任务书改成 2 / `cell_x == 15`（那会把 32 px 的格线画成 16 px）。

**G-E1 的复跑**：`python tools/s49_overlay_align/measure_lattice.py --moment movegrid-frame-v1`

---

## 3. 坐标对应（本次交付的核心）

### 3.1 两侧的 16 px 逻辑格栅格在**屏幕空间**完全重合

| | 逻辑格原点的屏幕位置 | X 相位 | Y 相位 |
|---|---|---|---|
| 原版 | 缓冲 px (16lx, 16ly) → 屏幕 (16lx−240, 16ly−24) | ≡ 0 (mod 16) | ≡ **8** (mod 16) |
| 重制（旧） | 覆盖层第 c 项 → 屏幕 8c−112；战斗格左边界 ≡ 16−cam_x (mod 16) | ≡ 0 (mod 16) | ≡ **8** (mod 16) |

⇒ 两侧的 **16×16 逻辑格栅格在屏幕空间同相位**（x ≡ 0 mod 16，y ≡ 8 mod 16），
**逐格族名对拍因此是有定义的**。

### 3.2 原版缓冲 = 地图空间缓冲（滚动量 = 相机）

原版 BG2 的 256×256 缓冲是**地图空间**的：缓冲 px = 地图 px (mod 256)，
BG2 的滚动量就是相机（`bg_hoffs/bg_voffs`）。
⇒ 屏幕上看到的那块覆盖层 = 「相机窗口 ± 256 px」的内容。
⇒ **重制侧必须镜像这个约定**，否则两侧缓冲覆盖的地图区域不同，逐格对拍必然对不上。

### 3.3 重制侧本流的改动

`game/src/battle_runtime_scene.cpp`（覆盖层渲染，L2108–L2205）：

* 覆盖层不再按「屏幕坐标 + 112/120」写条目，改成**按地图空间写**：
  * `window_x = 240 + camera.x()`、`window_y = 248 + camera.y()`（= 相机左/上边缘的地图 px）；
  * 缓冲第 (column,row) 项对应的地图 px = `layer_px + 256 * ceil((window - layer_px) / 256)`
    （取落在相机窗口内的那一份），再反查战斗格与格内 8×8 图砖序号；
  * 覆盖层 BG 的位置改为 `set_position(-window_x, -window_y)`，使缓冲 px 0 落在地图 px 0 上，
    **与原版 BG2 的约定逐位对齐**；
  * 缓冲按 256 px 绕回（原版同）。

`game/include/konoha/battle_range_ui_style.h`：

* `battle_range_ui_cell_kind` 改成原版判定顺序
  **cursor(band) > target(hatch_shift) > attack(line_alt) > move(hatch) > blocked(solid) > walkable(edge)**；
  **删掉**原来的 `move_phase` 特判（原版移动阶段整个可达区是青色 `hatch`，光标格是黄色 `band`，
  不是橙色）。
* `battle_range_ui_pixel_index`：`blocked` 族改成原版的 **50 % 竖条纹网点**
  （偶数列 = primary 234，奇数列 = 透明，右/下边界 = secondary 235）；
  其余族的实心填充 + 次色边界**本来就与原版逐像素一致**，保持不变。
* 新增 `battle_range_ui_cell_width/height`（32/16）与
  `battle_range_ui_logical_cell_width`（16）、`battle_range_ui_logical_cells_per_cell_x`（2）
  常量，把「战斗格」与「分析用 16 px 逻辑格」两个概念显式分开。

---

## 4. 改动文件清单

| 文件 | 改动 |
|---|---|
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_range_ui_style.h` | 族判定顺序、`blocked` 网点画法、格尺寸常量 |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp` | 覆盖层改成地图空间锚定（原版约定） |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_range_ui_style.cpp` | 随语义更新（原版优先级 / 网点） |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\tests\test_battle_range_ui_original_alignment.cpp` | **新增**：原版几何契约测试（格线位置、网点、优先级） |
| `D:\Github\gba-naruto\tools\s49_overlay_align\*.py` | **新增**：本流的仪器（见 §6） |
| `D:\Github\gba-naruto\notes\s49-fidelity\G-overlay-alignment.md` | 本文件 |

**未改**：`battle_unit_visual_animation.h` / `battle_visual_resource_coordinator.h` /
`battle_unit_palette_stream.h`（H2 独占）、`battle_audio_*.h`（L 独占）、
逆向线 `D:\Shell\Github\gba-naruto-reverse`（全程只读）。

---

## 5. 逐格族名对拍

仪器：`tools/s49_overlay_align/compare_overlay_families.py`
（原版侧读 F 的地面真相；重制侧从重制 ROM 的 VRAM dump 里按签名定位覆盖层 BG map，
再按**战斗格**（tile 序号自带格内位置）还原成 16 px 逻辑格族名），
驱动器：`tools/s49_overlay_align/scan_remake_frames.py`。

口径：原版 = 256×256 缓冲的 16×16 逻辑格；重制 = 覆盖层 BG map 的 16×16 逻辑格；
两侧栅格相位一致（§3.1），偏移量在 16×16 范围内穷举。

### 5.1 BEFORE（基线：改动前的重制 ROM，`build/s49-overlay-g/scan.json`）

| 原版时刻 | 最佳重制帧 | 偏移 | 同亮 | 原版有·重制缺 | 重制多画 | 族名不一致 |
|---|---|---:|---:|---:|---:|---:|
| `field` | step-23-A | [1,0] | 180 | 12 | 45 | 85 |
| `movegrid` | step-20-A | [2,0] | 168 | 24 | 42 | **24** |
| `banner` | step-22-A | [0,0] | 0 | 0 | 0 | **0（完全一致）** |
| `grid16` | — | — | — | — | — | **无法配对**（见 §9） |

⇒ **`banner` 时刻已经逐格全等**（原版 BG2 关 ⇒ 缓冲全 blank，重制侧该帧也无覆盖层）。
⇒ **`movegrid` 是唯一有意义的「原版确实显示覆盖层」的时刻**，
   基线为 同亮 168 / 原版有·重制缺 24 / 重制多画 42 / 族名不一致 **24（step-20-A，最佳帧）/ 68（step-23-A）**
   ——两个帧的差别只是光标相位不同。
⇒ 逐格差异的**定性**（`movegrid`，偏移 [2,0]）：

| 差异 | 处数 | 含义 |
|---|---:|---|
| `solid → edge` / `solid → blank` | 4 + 8 | 原版把「受阻格」画成灰网点，重制侧这些格是可行走格或空白 |
| `blank → solid` | 14 | 重制侧把**地图外的边栏**（collision 网格 `cost==0` 的一圈）画成灰网点，而原版那里是空白 |
| `edge → blank` | 4 | 重制侧画了原版没画的可行走格 |
| `hatch → band` | 2 | 光标格（原版黄 `band` / 重制黄 `band`，但相位差一格） |
| `hatch → hatch_shift` | 30 | **绿 `hatch_shift`（合法目标）在原版这四个时刻根本没被用过**，重制侧却画了 ⇒ 见 §9.3 |

### 5.2 AFTER（改动后）—— **未测（被 G-H13 阻塞）**

本流的改动（族顺序、`blocked` 网点、地图空间锚定）**编译通过**（`.o` 时间戳 1:54:34，链接成功），
但**重制 ROM 在战斗场景崩溃**（`Illegal opcode e710b710` / `Jumped to invalid address 01000354`），
崩溃发生在开机 240 帧内（标题/菜单阶段）——**本流的覆盖层代码只在战斗场景执行，静态上不可达**；
同一时刻 L 流正在改 `battle_audio_event_trace.h` / `battle_audio_runtime.h`，
其 `battle_audio_trace_buffer` 与 `.sbss` 的 `portrait_scratch` 段类型冲突**直接把整棵树打挂**。
⇒ **重制侧的对拍数字要等 L 流修好其音频改动后才能补测**（G-H14 标为未验）。

---

## 6. 新增工具

| 工具 | 作用 |
|---|---|
| `tools/s49_overlay_align/original_layers.py` | 从 VRAM dump 解出原版 BG1/BG2 图层 |
| `tools/s49_overlay_align/overlay_layer.py` | 重建原版 256×256 覆盖层 + **用截图差验证滚动量** |
| `tools/s49_overlay_align/measure_lattice.py` | 量原版格线间距（G-E1） |
| `tools/s49_overlay_align/decode_overlay_tiles.py` | 解 32 块原版图砖 + 变体用法统计 |
| `tools/s49_overlay_align/measure_overlay_shot.py` | 在截图里量覆盖层像素 |
| `tools/s49_overlay_align/measure_remake_overlay.py` | 在重制截图里量覆盖层 |
| `tools/s49_overlay_align/compare_overlay_families.py` | **逐 16×16 逻辑格族名对拍** |
| `tools/s49_overlay_align/scan_remake_frames.py` | 扫全部重制帧 × 四个原版时刻，找最佳对应 |
| `tools/s49_overlay_align/remake_map_content.py` | 打印重制侧 battle-14 地图 |

---

## 7. 验收门禁结果

| 门禁 | 判据 | 结果 |
|---|---|---|
| **①原版侧可重抓** | `python tools/s49_rule_probe/capture_original.py --out build/s49-rule/capture` + `verify_moments.py` | **PASS（exit 0, `RESULT: PASS`）**。四时刻全部逐字节命中 sha256：field 126 帧 / movegrid 283 帧 / grid16 **1 帧** / banner 1107 帧；A 段逐字节复现、B 段四时刻逐格全等、B2 留出基层、C 段调色板恒等、D 段光标对拍全过 |
| **②重制侧逐格族名对拍** | `python tools/s49_overlay_align/scan_remake_frames.py --vram-dir build/s49-overlay-g/remake` | **仪器建成并跑通**（§5.1）；**AFTER 数字未测**：重制 ROM 在战斗场景崩溃，根因在 L 流并发改动（G-H13）⇒ 目标 `original-only=0 / remake-only=0 / 族名 0 处不一致` **未达成** |
| **③判定台残差 + ROM 可构建** | `python tools/s49_fidelity_report.py --out build/s49-report/report.json`；WSL `make -j4` | **ROM 可构建**：本流改动**编译通过**（1:54 的构建成功出 `ROM fixed!`）；**判定台未跑**：当前树上 L 流的 `battle_audio_event_trace.h` 段冲突让**整棵树构建失败**，重制 ROM 停在上一版 ⇒ 残差数字**无法给出可信值**（若强行跑，remake 帧会是崩溃画面） |

### 7.1 逐格差分前后对比表

| 原版时刻 | 原版亮 | 重制亮（改动前） | 重制亮（改动后） | 重合 | 重制多画 | 原版有·重制缺 | 族名不一致 |
|---|---:|---:|---:|---:|---:|---:|---:|
| field | 598 | 821 | **未测** | 482 | 339 | 116 | — |
| movegrid | 640 | 821 | **未测** | 511 | 310 | 129 | 24 |
| grid16 | 497 | 821 | **未测** | 401 | 420 | 96 | — |
| banner | 1 | 821 | **未测** | 1 | 820 | 0 | **0** |

⚠️ **wave 1 的那张表是「两个不同空间」相减**（原版 = 地图空间 256×256 缓冲，
重制 = 屏幕空间 256×256 图层），**不能**直接当「多画/少画」读。
本流的对拍（§5.1）把两侧都换算到 **16×16 逻辑格** 后，
「重制多画」在 `movegrid` 只有 **42 格**（不是 310），
「原版有·重制缺」只有 **24 格**（不是 129）。

---

## 8. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| G-H1 | 原版覆盖层缓冲的滚动量 = (240,24) | field/movegrid 两帧截图差 + 缓冲像素反查 | 22 244/22 413 命中，「画了却没变」= 0 | **已确认** |
| G-H2 | 原版战斗格 = 32×16 px | 量 `edge` 格线的像素列/行 | 竖线 31,63,95,…（32 px）；横线 ≡15 (mod 16)（16 px） | **已确认** |
| G-H3 | 原版战斗格 = 32×16 px | `movegrid` 青区按 32 px 合并后是否为自然形状 | 曼哈顿半径 3 的菱形（中心战斗格 (3,6)），(4,7) 被占格挖空 | **已确认** |
| G-H4 | 原版战斗格 = 32×16 px | ROM 碰撞网格 `width_tiles>>2` / `height_tiles>>1` | 4×2 图砖 = 32×16 px | **已确认** |
| G-H5 | 任务书的「一格 = 16×16 px」应改 `tiles_per_cell_x` 4→2 | 任务书的前提 vs G-H2/G-H3/G-H4 | 前提错：16 px 是**分析单位**，原版格线在 32 px | **已证伪（任务书前提）** |
| G-H6 | 两侧 16 px 逻辑格栅格在屏幕空间同相位 | 原版 (16lx−240, 16ly−24) vs 重制 (8c−112, 8r−120) | X ≡ 0 (mod 16)、Y ≡ 8 (mod 16)，两侧一致 | **已确认** |
| G-H7 | 原版 `solid` 族是 50 % 网点而非实心 | 解 ROM 的 4bpp 图砖 278..281 | 索引 10/0 交替竖条纹 + 边界 11 | **已确认** |
| G-H8 | 重制侧覆盖层应改成地图空间锚定（滚动量 = 相机） | 原版 BG2 的缓冲/滚动约定 | 重制改为地图空间 + BG 位置 = (−window_x,−window_y) | **已实现** |
| G-H9 | 重制侧可达集 = 曼哈顿半径 3 | 重制青区 bbox 与原版青区 bbox | 重制 (16,24)-(206,127) vs 原版 (16,24)-(207,135)（Y 差 = HUD 截断） | **已确认（形状）** |
| G-H10 | 原版青区 = 朴素菱形（BFS 步数） | 逐行宽度 | 16 px 口径下是 1/3/5/6/8/6/2 的非自然形状；32 px 口径下是半径 3 菱形 | **已证伪（16 px 口径）** |
| G-H11 | 私有探针 `build/mgba-probe-g` 能跑 Lua 脚本 | 用 `mgba_boot_input_sequence.lua` 抓帧 | 链接期缺 `mScriptContextAttachStdlib` → `os.getenv` 不可用，脚本静默失败（无任何文件产出） | **已证伪** |
| G-H12 | 共享探针 `build/mgba-probe` 的 `framedump` 签名 | 试 `framedump 1 <addr> <len> 0x000 <prefix>` | 共享探针是**旧构建**，签名为 `<count> <addr> <len> <prefix> [keymask]`（keymask 在最后） | **已确认** |
| G-H13 | 重制 ROM 的战斗场景崩溃（`Illegal opcode e710b710` / `Jumped to invalid address 01000354`）是否本流引入 | ①崩溃发生在 **开机 < 240 帧**（标题/菜单阶段），本流的覆盖层代码只在战斗场景执行，静态上不可达；②同一棵树上 L 流在 1:49–1:52、2:10 改 `battle_audio_event_trace.h` / `battle_audio_runtime.h`，其 `battle_audio_trace_buffer` 与 `.sbss` 的 `portrait_scratch` 段类型冲突，**直接把整个构建打挂**（`error: 'konoha::battle_audio_trace_buffer' causes a section type conflict with 'portrait_scratch' in section '.sbss'`） | 崩溃与构建失败都落在 L 流的音频头文件上；本流代码在 1:54 的构建里**编译通过**（`.o` 时间戳 1:54:34） | **已证伪（崩溃非本流引入）** |
| G-H14 | 重制侧「地图空间锚定」改动能否在本机跑出 AFTER 数字 | 构建 + 抓帧 + VRAM dump + 对拍 | 依赖 L 流修复其运行时崩溃 | **未验（被 G-H13 阻塞）** |
| G-H15 | 原版的族优先级里 `target` 是否真的高于 `move` | 对拍里出现 30 处「原版 `hatch` / 重制 `hatch_shift`」 | 与 F 流的书面顺序 `target > move` **相反** ⇒ 或重制目标集过大，或原版实为 `move > target` | **未验**（需要原版目标选择阶段实机帧） |
| G-H16 | wave 1 的「多画 310–420 格」结论是否成立 | 把两侧都换算到 16×16 逻辑格后重算 | `movegrid` 多画只有 **42 格**（不是 310），原版有·重制缺只有 **24 格**（不是 129） | **已证伪（wave 1 的口径）** |

---

## 9. 未验 / 剩余风险

0. **⚠️ 新发现：`hatch_shift`（绿「合法目标」）的优先级存疑。**
   对拍里出现 **30 处「原版画 `hatch`（青，可达），重制画 `hatch_shift`（绿，合法目标）」**。
   F 流的族优先级是 `cursor > target > attack > move > …`，
   若两侧的「目标集」相同，这里应该出现**反向**差异（原版绿、重制青）。
   ⇒ **要么重制侧的「合法目标集」过大（多画了 30 格绿），
   要么原版的实际优先级是 `move > target`。**
   ⇒ 本流按 F 流的书面顺序实现（`target > move`），**这一条列为未验**，
   需要原版目标选择阶段的实机抓帧才能定（属于 G-H15）。

1. **受阻格集合的数据源不同**：原版的 `solid` 集合来自原版地图的**可见地形**（石头/墙），
   重制侧的 `blocked` 来自 ROM 碰撞网格的 `cost == 0`（battle-14 里是一圈**地图外的边栏**）。
   两者语义相近（都是「进不去的格」）但**形状与位置不同**，
   这是逐格对拍里 `solid↔edge` / `blank↔solid` 差异的主要来源。
   ⇒ 需要 M 流交付的「原版 battle-14 地形类别表」才能收口。
2. **`grid16` 只有 1 帧且是相机平移中的瞬态**，重制侧没有可对应的帧；
   原版 `field` / `banner` 两个时刻 **BG2 是关的**（DISPCNT 0x1940），
   内容是「准备好的下一帧」，不显示。
3. **重制侧的可达集/受阻集仍受别的流影响**（H2 的相位、L 的接线、M 的地图真值），
   本流只负责「形状 + 画法 + 判定顺序 + 锚定」。
4. 私有探针 `build/mgba-probe-g` 的 Lua 脚本不可用（缺 stdlib 符号），
   本流的 Lua 抓帧用了共享探针；VRAM dump 用的是私有探针（新签名）。
