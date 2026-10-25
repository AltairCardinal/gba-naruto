# W23-F2 —— 『請準備...』窗的资产（wave 23 / F2 流）

> 2026-10-25 23:0x – 2026-10-26 00:4x · wave 23 / F2 流 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 独占：`graphics/` 下的**新资产**（本流只放在 `build/w23-f2/assets/`，**共享树未改**）+ `tools/s49_w23f2/`
> ⛔ **未改 `game/` 下任何 C++**（D1 的 `battle_runtime_scene.cpp` / `battle_scene_controller.h`、
> C4 的 `battle_scene_presentation.h` 都不是本流的文件）⇒ 下面给的是**接线请求**。
> 上游：`W20-EXEC-BRIEF.md` · `W22-D1-transition.md` · `W22-D4-reward-truth.md` · `W21-C4-original-presentation.md`

---

## 0. 一句话结论

> ⭐⭐⭐ **『請準備...』窗的资产已做出，是原版的**逐像素**真图（不是手绘、不是重打字形）**，
> 并且**能把 D1 留下的 3,881 px 残差打掉 3,072 px（−79.2 %），残留 809 px**。
>
> ⭐ 关键突破：**`.ss9` 文件里的 IO 块不能用来读显示寄存器**（`DISPCNT` 读出 `0x1940` ⇒ 一个 BG 都不开，
> 与实拍矛盾）；**改成用探针自己渲染出的真值帧当尺子**，窗口矩形由**调色板**量出来。

---

## 1. 交付物

| 路径 | 内容 |
|---|---|
| `notes/s49-fidelity/W23-F2-prepare-box.md` | 本文件 |
| ⭐ **`build/w23-f2/assets/battle_ui_prepare_box.bmp`** | **窗的资产：96×32，8-bit 索引 BMP，16 色调色板 = 原版 PRAM palette bank 14**（3,190 B） |
| ⭐ **`build/w23-f2/assets/battle_ui_prepare_box.json`** | sidecar：`{"type": "sprite", "height": 32}`（与 `battle_ui_turn_banner_panel.json` 同格式） |
| `build/w23-f2/assets/prepare-box-report.json` | 机器可读的验证数字 |
| `build/w23-f2/assets/prepare-box-contact-sheet.png` | 原版 / 重制侧 / 贴上资产后 三联图（240×480） |
| `build/w23-f2/assets/prepare-box-zoom.png` | 资产 4 倍放大 |
| `build/w23-f2/probe/gt-f1.raw` | 原版真值帧（探针 `rawshot`） |
| `tools/s49_w23f2/gba_frame.py` | 从 `.ss9` 渲染 BG 层 / OBJ 层 |
| `tools/s49_w23f2/find_bg.py` / `scan_bg.py` / `fit_window.py` | 反推 BG 配置（三件） |
| `tools/s49_w23f2/find_window_tiles.py` | 在 VRAM 里按像素找窗的图块 |
| ⭐ `tools/s49_w23f2/extract_prepare_box.py` | **抠资产 + 算残差**（一条命令出全部数字） |
| `build/mgba-probe-w23f2/mgba-probe.exe` | 本流私建探针（1,372,672 B） |

---

## 2. ⭐ 窗的规格（本流实测，非推断）

| 项 | 实测 |
|---|---|
| 矩形 | **x 72..167, y 48..79 ⇒ 96 × 32 px**（12 × 4 个 8px 格） |
| 形态 | **圆角矩形**：外圈**编织纹深绿边框** → 一道**黄绿细线** → **米白底板** |
| 文字 | 「**請準備...**」**1 行**，**近黑色**（`(57,66,57)`），在米白底偏左 |
| 颜色 | **只有 7 种**，且**全部落在原版 PRAM palette bank 14** 里（`0 outside`） |
| 所在层 | 原版是 **BG 层**；角色（OBJ）被这个 BG **盖住**（见 §4.3） |
| 屏幕位置 | 原版 `step-20` 帧的 **(72, 48)**，此时相机在**战斗位**（= 重制侧 `step-24` 的相机） |

> ⭐ **D1 记的「约 92×26」不准**：实测 **96×32**（92 是把内框当成外框量出来的）。
> ⭐ **C4 记的「蓝边」也不准**：边框是**绿**的（`(99,189,115)` / `(107,156,90)`），没有蓝。

### 2.1 7 个颜色的出处（原版 PRAM palette bank 14）

| 用途 | RGB | PRAM bank 14 下标 |
|---|---|---|
| 米白底 | `(231,247,214)` | 1 / 8 / 12 |
| 编织纹深绿 | `(99,189,115)` | 3 |
| 外框绿 | `(107,156,90)` | 4 |
| 内框绿 | `(99,115,90)` | 5 |
| 黄绿细线 | `(231,214,99)` | 6 |
| 阴影 | `(173,181,156)` | 9 |
| 文字（近黑） | `(57,66,57)` | 11 |

⇒ 资产的像素值**直接用 bank 14 的下标**，调色板**原样照抄 bank 14** ⇒ 颜色零重映射。
（顺带实测：重制侧 `graphics/battle_ui_turn_banner_panel.bmp` 的调色板就是 bank 14 改了 2 项
——下标 2 与 7；两者**不是**同一份，别混用。）

### 2.2 ⭐ 资产格式与 Butano 的既有约定**完全一致**（本流实测）

* 重制侧 `graphics/battle_ui_turn_banner_panel.bmp` 的头：`bits=8`、`clrused=16`、
  `dataoffset=118`、`imgsize = w*h`；Butano 生成的 `bn_sprite_items_battle_ui_turn_banner_panel.h`
  写的是 **`32x192@4` / `bpp_mode::BPP_4` / 96 tiles**
  ⇒ **Butano 吃「8bpp BMP + 16 色调色板」，由 grit 转成 4bpp 图块**。
* 本流资产的实测头：**`96x32 bits=8 clrused=16 dataoff=118 imgsize=3072`** ⇒ **同一约定**。
* 资产的调色板**逐项等于原版 PRAM palette bank 14**（实测 `palette == bank14 → True`）。
* 资产用到的像素下标 = **{3, 4, 5, 6, 9, 11, 12}** ⇒ **下标 0（4bpp 的透明色）没被用到**
  ⇒ 不会有「某个颜色被当成透明」的问题。
* ⚠️ 顺带实测：重制侧 `battle_ui_turn_banner_panel.bmp` 的调色板**不是**原版 bank 14 原样
  （**下标 2 与 7 被改过**）⇒ 两者的调色板**不能互换**，接线时别混用。

---

## 3. ⭐ 验证数字（全部由 `tools/s49_w23f2/extract_prepare_box.py` 一条命令算出）

| 判据 | 数字 |
|---|---|
| **资产写回 BMP 后再读回，与原图的差** | **0 px**（96×32 全部一致） |
| **资产贴回原版 `step-20-A.png` 原位后的差** | **0 px** ⇒ 资产**就是原版的像素**，1:1 |
| **重制侧 `step-24-A` vs 原版 `step-20-A`（贴资产前）** | **3,881 px** ⭐ **与 D1 判定台的读数逐位相同** ⇒ 本流口径与判定台一致 |
| **重制侧 `step-24-A` vs 原版 `step-20-A`（贴资产后）** | **809 px** |
| **净减少** | **−3,072 px（−79.2 %）**，而 96×32 = **3,072 px** ⇒ **窗的面积 100 % 归零** |
| 残留 809 px 的位置 | 两簇：**(120..144, 32..48)**（红指示箭头 + 蓝帽单位）与 **(24..40, 56..88)**（左侧单位下半身）⇒ **都不是窗** |

> ⭐ **口径说明**：`3,881` 与 D1 的 `align-v4.json` 里 `step-20-A` 的读数**完全一致**
> ⇒ 本流用的是同一个口径（整帧 240×160 逐像素、任一通道不同即算不同）。
> 残留 809 px 属 D1 的 **R-D1-2（红箭头 / 覆盖层 / HUD 时机）**，**不属本流**。

---

## 4. 怎么做到的（方法论，复用价值最高的部分）

### 4.1 ⭐⭐ 「`.ss9` 的 IO 块不可信」——本流踩过的最大的坑

* `.ss9` 文件里的 IO 块读出 `DISPCNT = 0x1940` ⇒ 按 GBA 定义**一个 BG 都不开、OBJ 也不开**
  ⇒ 可实拍画面满屏是地图 ⇒ **这个值与该帧无关**。
* 探针**实时**读同一段（`0x10` 起）返回常量填充 `0x4338` ⇒ 就是 AGENTS.md 规则 13 那个老坑。
* ⇒ **显示寄存器（`DISPCNT` / `BGxCNT` / 滚动）在本场景一律不可读**。
  ⇒ **对策：用探针自己渲染出的帧当尺子，反推一切。**

### 4.2 ⭐⭐ 「原版 `.ss9` 与 walk PNG 是同一时刻」——已证实

* 探针 `load step-20-A.ss9` → `frames 1` → `shot`，与 `capture-original/step-20-A.png`
  **只差 51 px**，且全部落在 `x 116..140, y 35..47`（红箭头）与 `y 80..85`（单位的脚）——
  也就是**会动的那几个像素**。
* ⇒ **`.ss9` 的 VRAM / PRAM / OAM 就是那一帧的**，可以放心当尺子用。

### 4.3 ⭐⭐ 窗在原版是 **BG 层**，而且 **BG 压在角色上面**

* 把 OAM 里 17 个活动精灵全渲染出来，**窗的位置上是空的**（只有红箭头、单位的脚）⇒ 窗只能来自 BG。
* 但 OBJ 的不透明像素里有 **689 px 落在窗的矩形内**，而真值帧那里**一格角色像素都没有**
  ⇒ 只能解释成：**窗所在的那个 BG 的优先级高于这些 OBJ 精灵**，即 **BG 把角色盖住了**。
* ⇒ ⭐ **D1 §0.1.4 记的「框在角色身后（角色压在上面）」是反的：原版是窗压住角色。**
  ⇒ 这条要在接线时定清楚（见 §6 R-F2-3）。

### 4.4 怎么把窗口矩形量出来（不用任何寄存器）

1. 读原版 PRAM，列出 16 个调色板；
2. 在真值帧里找**由某一个调色板bank 的颜色**构成的像素 ⇒
   本流用 **bank 14**（窗口的全部 7 种颜色都在里面），在区域 `(40,30)-(200,80)` 里求包围盒
   ⇒ **(72,48)-(168,80)**；
3. 逐行检查：**y 48..79 每行都恰好是 x 72..167（96 px 一个不缺）** ⇒ 这是一个干净的 96×32 矩形
   （不是包围盒的近似）；
4. 该矩形内**没有一个像素不属于 bank 14** ⇒ 框内**既没有草也没有角色** ⇒ 裁出来就是干净资产。

> ⚠️ 注意：第一次跑时区域给到了 `y=100`，结果把**底部 HUD** 里同属 bank 14 的颜色也框了进来
> （高度变成 39）。⇒ **区域必须限制在战场区（y < 128）内**。

### 4.5 图块级溯源（做到了一半，留给下一轮）

* 在 VRAM 里按像素匹配，**窗的米白底板图块找到了**：
  **character base block 0、4bpp、palette bank 14**，图块号 274 / 294 / 297 / 307 / 313 / 449 / 458。
* 这些图块出现在 **BG0 的 tilemap**（screen base 0）的行 19 与 BG3 的 tilemap 里。
* ⛔ **但没能把滚动偏移拟合出来**（`fit_window.py` 跑了 4 层 × 5 种屏幕尺寸 × 全部偏移，
  窗矩形内的最优差仍是 **1,072 px**＝「空层」的底噪）。
  ⇒ ⇒ **结论：窗的图块确实在 VRAM 里，但承载它的那一层的 tilemap 排布（screen base / 屏幕尺寸 /
  字符基址）与本流枚举的组合都不吻合** —— 本流没有找到它的地图坐标。
  ⇒ **这不影响资产本身**（资产是从真值帧裁的，已经 1:1），但如果以后要**复刻窗的绘制逻辑**
  （而不只是贴一张图），这一条还得再查。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| F2-H1 | 原版 VRAM 里能干净分离出窗 | 读 `.ss9` 的 BG tilemap + 调色板重建屏上像素 | **成立**（VRAM 读法已验证：`tools/s49_w21c4/overlay_vram_census.py` 在同一批 `.ss9` 上**复现 C4 的全部数字**，如 `step-20 lit=1`、`step-22 lit=512`） | **已确认** |
| F2-H2 | 窗在原版是 BG 层 | 渲染全部 17 个活动 OBJ 精灵 + 4 个 BG 层 | **成立**：OBJ 层在窗的位置上是空的 | **已确认** |
| F2-H3 | 窗的规格：绿边圆角 + 米白底 + 1 行字 | 真值帧逐像素量 + 4 倍放大 | **成立**：**96×32 @ (72,48)**，7 色，全部在 bank 14 | **已确认** |
| F2-H4 | `.ss9` 与 `.png` 同一时刻 | 探针 `load`+`frames 1`+`shot` vs walk PNG | **成立**：差 **51 px**，全在会动的像素上 | **已确认** |
| F2-H5 | ⭐ **`.ss9` 的 IO 块能读出显示寄存器** | 读 `DISPCNT`/`BGxCNT`/滚动并与真值帧对照 | ⛔ **证伪**：`DISPCNT=0x1940` ⇒ 全关；实时读 `0x10` 起是常量 `0x4338` | **已证伪** |
| F2-H6 | ⭐ 窗可从 BG 图块重建 | 反推 BG 配置（层/尺寸/字符基址/色彩模式/滚动）后与真值帧逐像素比 | ⛔ **未成立**：最优仍是空层底噪（1,072 px）⇒ **承载窗的那层的 tilemap 排布还没找到** | **已证伪（改为「从真值帧裁」）** |
| F2-H7 | ⭐⭐ **窗的像素可直接从真值帧裁出**（角色没有污染它） | 框内逐像素查调色板归属 + 与 OBJ 渲染求交 | **成立**：框内 **3,072 px 全部属于 bank 14**；角色被 BG 盖住 ⇒ 裁出来即干净资产 | **已确认** |
| F2-H8 | ⭐⭐ **贴上资产能打掉 D1 的 3,881 px** | 重制侧 `step-24-A` vs 原版 `step-20-A`，贴前后各测一次 | **成立**：**3,881 → 809（−3,072 = 窗面积 100 %）** | **已确认** |

---

## 6. ⭐ 接线请求（**本流不改任何产品文件**）

### R-F2-1 —— 资产落位（父代理拷，或由流自己拷）

```powershell
Copy-Item build/w23-f2/assets/battle_ui_prepare_box.bmp  D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\battle_ui_prepare_box.bmp
Copy-Item build/w23-f2/assets/battle_ui_prepare_box.json D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\battle_ui_prepare_box.json
```

* sidecar 格式与同族资产一致：`{"type": "sprite", "height": 32}`。
* 但ano 会据此生成 `bn_sprite_items_battle_ui_prepare_box.h`（**与其它 `battle_ui_*` 同理**）。

### R-F2-2 —— 在 D1 的过场里画这个窗（D1 的文件，**要 D1 或父代理改**）

* 文件：`game/src/battle_runtime_scene.cpp`
* 参照点：`battle_runtime_scene.cpp:2376` 的 `void _add_turn_banner()`（横幅画法）
  与 `:9820-9830` 的相位分流
  （`state.phase == battle_scene_phase::turn_banner && state.turn_banner_stage != battle_turn_banner_stage::banner` ⇒ 换成 `battle_ui_layer::map_status`）。
* 改成什么：

  1. 加 `#include "bn_sprite_items_battle_ui_prepare_box.h"`；
  2. 加一个 `void _add_prepare_box()`，照 `_add_turn_banner()` 的写法建一个精灵：
     **96×32**，`bn::sprite_ptr::create(...)`，`set_z_order(...)` **低于单位**（见 R-F2-3），
     `set_bg_priority(0)`；
  3. 触发条件：**`state.phase == battle_scene_phase::turn_banner` 且
     `state.turn_banner_stage == battle_turn_banner_stage::prepare_box`**
     ⇒ 这一拍画窗，**其它三段（`banner` / `camera_pan` / `camera_landed`）不画**；
  4. **位置**：原版窗在 `step-20` 帧的屏幕位置是 **(72, 48)**，
     而那时**相机在战斗位**（重制侧 `step-24` 的相机，原版 `step-20` 与重制侧 `step-24` 的
     最佳重叠位移实测 = **(0,0)**，见 D1 §0.1.1）⇒ **准备框那一刻放在屏幕 (72, 48)** 即可。
  5. ⭐ **但要跟着相机走**：原版的窗是 BG 层，**后面摇镜时它会随地图滚走**
     （D1 的相机表：`step-20` 相机偏移 (0,0) → `step-21` (+40,−7)）。
     ⇒ 建议**把精灵锚在地图空间**（和其它单位同一套锚点），而不是钉死在屏幕坐标；
     口径：**内容位移 = −相机偏移**（D1 的符号约定）。

### R-F2-3 —— ⭐ **原版是「窗压住角色」，不是「角色压住窗」**（D1 的结论要更正）

* D1 §0.1.4 写「框在蓝帽角色身后（BG 层，角色压在上面）」。
* **本流实测**：原版 `step-20` 里，窗的矩形内 **1 个角色像素都没有**，
  而这些位置**有 689 px 的 OBJ 不透明像素** ⇒ **窗所在的那个 BG 优先级高于角色精灵**。
* ⇒ **接线时必须让窗的精灵 `z_order` 低于单位**（否则角色会盖住窗，残差会反弹）。

### R-F2-4 —— 剩余 809 px **不属本流**

* 位置两簇：**(120..144, 32..48)**（红指示箭头 + 蓝帽单位）与 **(24..40, 56..88)**（左侧单位下半身）。
* ⇒ 属 **D1 的 R-D1-2**（过场期间的红箭头 / 覆盖层 / HUD 时机，C4 的 R-C4-1/2/3）。

### R-F2-5 —— 仪器坑，建议写进 AGENTS.md

1. ⭐ **`tools/s49_pairing/savestate.py::io_registers` 的滚动寄存器步长仍是错的**：
   它写的是 `values[0x10 // 2 + 4 * index]` ⇒ 读成 `0x10/0x18/0x20`，
   而 GBA 正确布局是 `0x10/0x14/0x18`（**2 字节步长**）。
   ⇒ 它的 `bg_hofs[1]` 其实是 `BG2HOFS`，`bg_hofs[2]` **根本不是滚动寄存器**。
   实测：原版 `step-20-A` 真值 **240/240/240**，该函数报 **240/240/256**。
   （`BGxCNT` 的步长它修对了；**滚动寄存器没修**。）
2. ⭐ **GBA `DISPCNT` bit 4 = OBJ 1D/2D 映射，bit 11 = OBJ extended（仿射）** —— 极易搞混
   （本流一开始用 bit 11 判 1D ⇒ OBJ 层整层渲染不出来）。
3. ⭐ **`.ss9` 的 IO 块与该帧不对应**（见 §4.1）；**显示寄存器一律以「探针渲染的真值帧」为准**。
4. ⭐ **GBA 2D 映射的图块排布**：16×8 与 32×16 用 **16 格宽**的块，其余用 **32 格宽**；
   8bpp 图块是 **64 字节**（4bpp 是 32 字节）。

---

## 7. 未完成项

| # | 未完成项 | 状态 / 下一步（最小动作） |
|---|---|---|
| **U-F2-1** | ⭐ **承载窗的那一 BG 层的 tilemap 排布没找到** | 资产已经 1:1，**不影响交付**；若要复刻「绘制逻辑」而不只是贴图：下一步在原版 ROM 里定位写 `DISPCNT`/`BGxCNT` 的代码，或枚举**全部 32 个 screen base block**（本流只试了各层自己那一个）|
| **U-F2-2** | 窗在**摇镜那两拍**里是否还在屏上、滚到哪 | 本流只做了 `step-20` 这一拍。**下一步**：用原版密集捕获 `step-20-to-21/f001..f090` 逐帧定位窗 ⇒ 得出窗在地图空间的位置与可见帧数 |
| **U-F2-3** | 窗的**红箭头**（原版 `step-20` 在 (113,37)-(118,42)） | 属 **D1 的 R-D1-2**，本流未做 |
| **U-F2-4** | 资产**没有进共享树**，也**没有在重制侧真正画出来** | 本流无 `game/` 所有权。**父代理**：按 R-F2-1 拷两个文件、按 R-F2-2 接线，然后重跑判定台（`step-20-A` 预期 **3,881 → ~809 px**）|
| **U-F2-5** | 窗的**字体来源**没查 | 资产的字形是原版 VRAM 的真像素，不需要重打；但「原版用的是哪张字表」没查（若以后要复用这套字，得查）|
| **U-F2-6** | git | **未提交**（按纪律）；共享树**未改**；本流产物全在 `build/w23-f2/` |

---

## 8. 复现命令

```powershell
# 1) 造探针（本流私建，**不要用 build/mgba-probe-w4/**）
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe-w23f2'
python tools/mgba_probe/build.py

# 2) 原版真值帧（载入 step-20-A.ss9，跑 1 帧，rawshot）
python tools/mgba_probe/probe_client.py `
  --rom 'D:\Shell\Github\gba-naruto-butano\rom\base.gba' `
  --exe 'build/mgba-probe-w23f2/mgba-probe.exe' `
  --cmd "load build/s49-package-w22/work/s49-report/capture-original/step-20-A.ss9" `
  --cmd "frames 1 0x000" `
  --cmd "rawshot build/w23-f2/probe/gt-f1.raw" `
  --out 'build/w23-f2/probe/probe5.json'

# 3) 抠资产 + 算残差（一条命令出全部数字）
python tools/s49_w23f2/extract_prepare_box.py `
  --state   build/s49-package-w22/work/s49-report/capture-original/step-20-A.ss9 `
  --raw     build/w23-f2/probe/gt-f1.raw `
  --original build/s49-package-w22/work/s49-report/capture-original/step-20-A.png `
  --remake   build/w22-d1/capture-remake-v4/step-24-A.png `
  --out-dir  build/w23-f2/assets --region '40,30,200,80'
```
