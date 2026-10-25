# W25-H3 —— 『請準備...』窗接线（wave 25 / H3 流）

> 2026-10-26 00:1x–01:2x · wave 25 / H3 流 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 独占：`graphics/battle_ui_prepare_box.bmp` · `graphics/battle_ui_prepare_box.json` ·
> `game/src/battle_runtime_scene.cpp`（**仅「prepare box」区段**）
> 上游：`W25-TASKS.md` §5 · `W23-F2-prepare-box.md` · `W24-PARENT-wrapup.md`
> lane：`build/w25-h3/butano-sequel`（`graphics/` 是**真实目录副本**）
>
> **基线（父代理 2026-10-26 00:45 更正）**：判定台 **38,047 px**（不变）；
> **25 帧固定偏移 = 54,959 px**（不是 53,364 —— 那是 wave 22 的旧数）；
> `step-20-A` 战场区残差基线 = **3,881 px**，目标 ≈ **809 px**。

---

## 0. 一句话结论

> ⭐ **原版的『請準備...』窗 = 96×32，位于屏幕 (72,48)**，**7 色全在原版 PRAM bank 14**。
> 本流把它接进重制侧：Butano **OBJ 精灵**，96×32 拆成 **3 块 32×32**（GBA 精灵宽度上限 64），
> `z_order = -1000`（低于所有单位）⇒ **窗压住角色**。
> 逐像素验证：窗矩形内 **3,072 px 全部是窗自己的像素**，没有一格角色像素穿出来。

---

## 1. 交付物

| 路径 | 内容 |
|---|---|
| `notes/s49-fidelity/W25-H3-prepare-box.md` | 本文件 |
| `build/w25-h3/butano-sequel/graphics/battle_ui_prepare_box.bmp` | F2 的 1:1 资产（96×32，sha256 `999768e5…f964`，与 `build/w23-f2/assets/` **逐字节相同**） |
| `build/w25-h3/butano-sequel/graphics/battle_ui_prepare_box.json` | `{"type":"sprite","width":32,"height":32}` |
| `build/w25-h3/butano-sequel/game/src/battle_runtime_scene.cpp` | `_add_prepare_box()` + 调用点 + 成员 |
| `build/w25-h3/` | ROM + 测量产物（`align.json` / `report.json` / `fit-original.json`） |
| `tools/s49_w25h3/fit_window.py` | 暴力对齐工具（把资产贴到每一帧的每个位置，数差多少像素） |

---

## 2. ⭐ 载体的选择：**OBJ 精灵**（不是普通 BG，不是 affine BG）

### 2.1 为什么不能用「一个 96×32 的精灵」

Butano 的精灵形状尺寸是**白名单**（`butano/tools/butano_graphics_tool.py:122`）：

```
valid sprite sizes: 8x8, 16x16, 32x32, 64x64, 16x8, 32x8, 32x16, 8x16, 8x32, 16x32, 32x64
```

⇒ **最宽 64 px**。GBA 的 OBJ 也只有 64×64。96 px 宽的窗**不可能是一个精灵**。

### 2.2 为什么选「3 块 32×32 的精灵」而不是 BG

* **普通 BG**：Butano 的 `regular_bg` 要求整屏 256×256 的 tilemap 资产；要在一张全屏 BG 的
  tilemap 里挖出 96×32 的一块并放到 (72,48)，需要**另做一张 tilemap 位图**，而且那张图要占
  **一个 BG 槽 + 一份 4bpp 调色板**。H4 正在做「overlay 与调色板解耦」来腾 BG 槽，
  两边同时动 BG 槽位会打架。
* **affine BG**：同样占一个 BG 槽，而且 affine 要额外一份仿射矩阵 + 硬件寄存器，
  为一张静止的窗完全不值。
* **OBJ 精灵**：
  * 不占 BG 槽（GBA 有 128 个 OAM 条目，窗只要 3 个）；
  * **可以精确地压住角色**（原版就是「窗盖住角色」）；
  * 有**现成的同族先例**：回合横幅 `battle_ui_turn_banner_panel` 就是 32×192 的资产
    被拆成 6 块 32×32 的精灵摆成 3×2（`battle_runtime_scene.cpp:2376` `_add_turn_banner()`）。
    本流照抄这个做法。

### 2.3 资产怎么变成 3 块

sidecar 用 **`{"type":"sprite","width":32,"height":32}`**：

* Butano 的 `SpriteItem` 支持 json 里的 `width`（`butano_graphics_tool.py:184`），
  要求 `bmp.width % width == 0` ⇒ 96 % 32 = 0 ✓；
* `graphics = int(bmp.width/width) * int(bmp.height/height)` = **3**；
* grit 命令 = `grit <bmp> -gt -pe16 -Mw 4 -Mh 4 -gB4`（Butano 自己拼的）。
  **实测**（直接跑 grit，见 §3.2）：`96x32@4, 48 tiles Metatiled by 4x4` ⇒ **3 个 32×32 metatile**，
  正好 3 块，顺序 = 左 / 中 / 右。

---

## 3. 资产落位与格式（坑）

### 3.1 格式

| 项 | 值 |
|---|---|
| BMP | **96×32、8bpp 索引、16 色调色板**（`dataoffset=118`、`imgsize=3072`） |
| 调色板 | **逐项等于原版 PRAM palette bank 14**（F2 实测） |
| 用到的像素下标 | **{3,4,5,6,9,11,12}** ⇒ **下标 0（4bpp 透明色）没被用到** |
| Butano 判定的 bpp | `parse_sprite_bpp_mode(info, 16)`：json 没写 `bpp_mode` ⇒ `colors_count > 16` = false ⇒ **`BPP_4`** |

⇒ **不需要手工改 4bpp 调色板表**：资产是 8bpp，grit 自己转 4bpp。
（同族先例 `battle_ui_turn_banner_panel.bmp` 也是 8bpp/16 色 ⇒ 生成的 header 同样是 `BPP_4`。）

### 3.2 ⭐ 坑 1：**grit 会不会重排调色板下标？** —— 不会（实测逐项解码）

直接跑一遍 Butano 用的 grit 命令，把输出的 16 个 `.hword` 逐项按 GBA 的
**5 bit BGR** 解回来，与 F2 的 BMP 调色板对：

| 下标 | grit 输出 | 解码 (R,G,B 5bit) | BMP 调色板 |
|---:|---|---|---|
| 0 | `0x7E18` | (24,16,31) | (198,132,255) ✓ |
| 1 | `0x6BDC` | (28,30,26) | (231,247,214) ✓ |
| 2 | `0x4B70` | (16,27,18) | (132,222,148) ✓ |
| 3 | `0x3AEC` | (12,23,14) | (99,189,115) ✓ |
| 4 | `0x2E6D` | (13,19,11) | (107,156,90) ✓ |
| 5 | `0x2DCC` | (12,14,11) | (99,115,90) ✓ |
| 6 | `0x335C` | (28,26,12) | (231,214,99) ✓ |
| 7 | `0x1EB7` | (23,21,7) | (189,173,57) ✓ |
| 8 | `0x6BDC` | (28,30,26) | (231,247,214) ✓ |
| 9 | `0x4ED5` | (21,22,19) | (173,181,156) ✓ |
| 10 | `0x35EE` | (14,15,13) | (115,123,107) ✓ |
| 11 | `0x1D07` | (7,8,7) | (57,66,57) ✓ |
| 12 | `0x6BDC` | (28,30,26) | (231,247,214) ✓ |
| 13 | `0x46BC` | (28,21,17) | (231,173,140) ✓ |
| 14 | `0x219C` | (28,12,8) | (231,99,66) ✓ |
| 15 | `0x007C` | (28,3,0) | (231,24,0) ✓ |

⇒ **16 项逐项相等、下标顺序不变** ⇒ 用自己的调色板 item 画出来就是**原版的颜色，零重映射**。

### 3.3 ⭐ 坑 2：**精灵位置用「左上角」写，别推「中心」偏移**

G3 的教训（误推 (+16,0) 导致模拟 0 px、真机只降到 163 px）在这里同样适用，所以：

* **屏幕位置是暴力实测出来的**，不是从注释推的：
  `tools/s49_w25h3/fit_window.py` 把 96×32 的资产贴到原版每一帧的**每一个**候选位置，
  数差多少像素 ⇒ **`step-20-A` 在 (72,48) 处差 = 0 px**（全帧唯一 0 px 的位置）。
* 落笔时**不用「中心」坐标**，用 Butano 的 `set_top_left_position(x, y)`：
  `bn_top_left_utils.h` 里 `from_top_left_x(tlx, w) = tlx - (240 - w) / 2`，
  也就是 `top_left` 就是**屏幕左上角**（0 = 屏幕左边）⇒ 直接写 (72,48)/(104,48)/(136,48)。

### 3.4 ⭐ 坑 3：**UI 精灵向量只有 16 个**

`battle_runtime_scene.h:180`：`maximum_ui_sprites = 16`。
`map_status` 层自己要画 4 个状态面板 + 2 组血条/查克拉条（track+fill）≈ 8–13 个，
再加 3 块窗就可能顶到上限，而 `_add_panel()` 里有 `if(_sprites.full()) return;` ——
**顶满时窗会被静默丢掉**（残差就不会降）。
⇒ **窗的 3 块精灵放在独立的 `_prepare_box_sprites` 向量里**，不跟 UI 抢名额。

---

## 4. 接线（`game/src/battle_runtime_scene.cpp`，只动「prepare box」区段）

| 位置 | 改动 |
|---|---|
| `:115` | `#include "bn_sprite_items_battle_ui_prepare_box.h"` |
| `:1654` `reset()` | 多两行：`_prepare_box_sprites.clear(); _prepare_box_palette.reset();` |
| `:1678` `update()` | `_prepare_box_sprites.clear();` + **条件调用** `_add_prepare_box();` |
| `:2428` 新方法 | `_add_prepare_box()`（3 块 32×32） |
| `:2600` 成员 | `_prepare_box_sprites`（容量 4）、`_prepare_box_palette` |

### 4.1 触发条件

```cpp
if(state.phase == battle_scene_phase::turn_banner &&
        state.turn_banner_stage == battle_turn_banner_stage::prepare_box)
```

⇒ **只有「請準備...」这一拍画窗**；`banner` / `camera_pan` / `camera_landed` 三段都不画。
（`battle_turn_banner_stage` 是 D1 加在 `battle_scene_controller.h` 里的四段枚举 —— **本流没有改那个文件**。）

### 4.2 位置与 z-order

```cpp
constexpr int piece_x[] = { 72, 104, 136, };
sprite.set_top_left_position(piece_x[index], 48);   // 屏幕 (72,48)-(167,79)
sprite.set_bg_priority(2);                            // 同单位；地图 BG 是 priority 3 ⇒ 窗在地图之上
sprite.set_z_order(-1000);                            // ⭐ 低于所有单位 ⇒ 窗压住角色
```

* `bg_priority = 2`：与单位相同（单位是 `sprite->set_bg_priority(2)`），
  地图 BG 是 `map->set_priority(3)` ⇒ 窗在地图之上、在 BG0/BG1 之下（那两层此刻不在场）。
* `z_order = -1000`：单位用 `battle_map_unit_z_order()` = `-visual_position.y`（0 … −18）。
  Butano 的语义是「**z_order 高的先画（因此会被后面的盖住）**」
  （`bn_sprite_ptr.h:682`：「Sprites with higher z orders are drawn first
  (and therefore can be covered by later sprites)」），
  产品自己的 `battle_map_visual_projection.h:113` 也是同一句解释
  （「a lower value is visually in front」）。
  ⇒ **数值更小 = 更靠前**，所以 −1000 < −18 ⇒ 窗盖住所有单位。**已用逐像素验证（见 §5.3）。**

### 4.3 调色板

用**资产自己的** `palette_item().create_palette()`（和 `_turn_banner_palette` 同一写法），
1 个 4bpp OBJ 调色板槽；不跟回合横幅共用（横梁调色板的下标 2/7 与 bank 14 不同，
虽然窗用到的 7 个下标碰巧一样，但共用会留下「靠巧合」的隐性依赖）。

---

## 5. 测量

### 5.1 暴力对齐（原版侧）

`tools/s49_w25h3/fit_window.py`（资产贴到每个候选位置，数差多少像素）：

| 原版帧 | 最佳位置 | 差 px | 结论 |
|---|---|---:|---|
| `step-19-A` | (0,128) | 714 | 无窗 |
| **`step-20-A`** | **(72,48)** | **0** | ⭐ **窗就在 (72,48)，逐像素 0 差** |
| `step-21-A` | (0,128) | 650 | ⭐ **窗在摇镜那一拍已经不在屏上** |
| `step-22-A` | (0,0) | 3072 | 无窗 |

⇒ **窗只在原版 step-20 这一拍出现**；`step-21`（相机已经偏移 (+40,−7)）时全帧找不到窗
⇒ **不需要把窗锚到地图空间**，钉在屏幕 (72,48) 即可（也解答了 F2 的 `U-F2-2`）。

### 5.2 两个仪器（**绑定本 lane ROM 的 sha256**）

* **本 lane ROM**：`sha256 = 6ac287943b9a02c639c09083f3f0ebbccb2d51994dc6841c4574e771afaa872c`，
  12,260,988 B。
  判定台的 `run.attempts.remake` 里 `audit_rom_sha256 = 6ac28794…a872c` ⇒ **重制侧录像就是这份 ROM 录的**。

| 仪器 | 改前 | 改后 | 差 |
|---|---:|---:|---:|
| **判定台** `s49_fidelity_report.py` 战场区总残差 | 38,047 px | **35,973 px** | **−2,074 px** ✅ 变小 |
| **25 帧固定偏移** `align_capture_steps.py`（offset **+4**） | 54,959 px | **51,887 px** | **−3,072 px** ✅ 变小 |
| **`step-20-A` 战场区残差**（判定台 arg-min） | 3,881 px | **809 px** | **−3,072 px** ✅ = 窗面积 100 % |
| **`step-20-A` 战场区残差**（固定偏移 +4） | 3,881 px | **809 px** | **−3,072 px** ✅ |
| **偏移** | 恒为 +4 | **恒为 +4** | ✅ 没漂移 |

> ⚠️ 「改前」的两个数都**用同一台仪器重测过**，不是跨 ROM 比较：
> * 判定台基线 38,047 = 已接受基线 `build/s49-package/baseline-accepted/report.json`；
> * 25 帧基线 54,959 = 用 `align_capture_steps.py` 对**基线自己的重制侧录像**
>   （`build/s49-package-w22/work/s49-report/capture-remake`）跑出来的 —— 读数 **54,959 @ +4**
>   与父代理 00:45 的更正**完全一致**（说明基线口径没跑偏）。

### 5.3 ⭐ z-order 的**逐像素**验证（不是目测）

`tools/s49_w25h3/check_window.py`（在窗矩形 `(72,48)-(168,80)` 内逐像素比）：

| 比较 | 结果 |
|---|---|
| 原版 `step-20-A` 的窗矩形 vs **资产** | diff bbox = **None** ⇒ 0 px 差 |
| 重制侧 `step-24-A` 的窗矩形 vs **资产** | diff bbox = **None** ⇒ 0 px 差 |
| **重制侧窗矩形里不是窗自己的像素数** | **0 / 3072** |

⇒ ⭐ **窗矩形内一格角色像素都没有** ⇒ `z_order = -1000` 确实让窗**压住了角色**
（若 z_order 方向搞反，角色的像素会从窗下面透出来，这个数会 > 0）。
⇒ 剩余的 809 px 在窗矩形**之外**（红箭头 + 蓝帽单位 + 左侧单位下半身），**不属本流**（F2 的 `R-F2-4`）。

### 5.4 判定台逐帧（改后）

| 原版帧 | 配对的重制帧 | 战场区 px（基线 → 改后） |
|---|---|---:|
| step-00-base | step-27-A（**配对变了**） | 1,308 → **2,306** ⚠️ |
| step-11-A | step-22-A | 305 → 305 |
| step-12-A | step-20-A | 9,520 → 9,520（H2 的活） |
| **step-20-A** | **step-24-A** | **3,881 → 809** ⭐ |
| 其余 21 帧 | — | **逐字节不变** |

⚠️ **唯一一处变差的是 `step-00-base`**（1,308 → 2,306，+998）：
它的 arg-min 配对从 `step-24-A` 变成了 `step-27-A` —— 因为重制侧的 `step-24-A` 现在带着窗，
对 `step-00-base` 不再是最优匹配。**判定台的总残差因此是 −3,072 + 998 = −2,074 px（仍然变小）**。
25 帧固定偏移仪器（不做 arg-min，只做固定偏移）**没有**这个抖动：**−3,072 px**。

### 5.5 单测

`w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w25-h3/butano-sequel`
⇒ **pass=119 / fail=20**（status=1 是那 20 条已知红的常态）⇒ **零新增红** ✅

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H3-H1 | 资产的**屏幕位置**是 (72,48) | 暴力对齐：资产贴到原版每帧的每个候选位置数差 | `step-20-A` 在 (72,48) 差 **0 px**（全帧唯一） | **已确认** |
| H3-H2 | 96×32 能做成**一个** Butano 精灵 | 读 Butano 的精灵尺寸白名单 + GBA OBJ 上限 | ⛔ **证伪**：最宽 64 px ⇒ 必须拆 | **已证伪** |
| H3-H3 | Butano 能把 96×32 拆成 3 块 32×32 | 直接跑 Butano 用的 grit 命令看产物 | `96x32@4, 48 tiles, metatiled 4x4` ⇒ 3 个 metatile | **已确认** |
| H3-H4 | grit 会重排调色板下标（⇒ 不能用资产自己的调色板） | 解码 grit 输出的 16 个 `.hword`，与 BMP 调色板逐项比 | 16/16 逐项相等、顺序不变 ⇒ 无重映射 | **已证伪** |
| H3-H5 | 窗只在原版的 `step-20` 一拍出现（后面摇镜时已消失） | 暴力对齐 `step-19/20/21/22` | `step-21` 全帧无窗 ⇒ **不必锚地图空间** | **已确认** |
| H3-H6 | `set_top_left_position` 的坐标就是屏幕左上角 | 读 `bn_top_left_utils.h` 的 `from_top_left_x/y` | `tlx - (240-w)/2`，且 `screen_center = pos + 120` ⇒ top_left = 屏幕左上角 | **已确认** |
| H3-H7 | 单位的 z_order 全都 > −1000 | 读 `battle_map_unit_z_order()` = `-visual_position.y` | 单位 z_order ∈ [0,−18] ⇒ −1000 更靠前 | **已确认** |
| H3-H8 | 窗的 z_order 必须**更低**才压住角色 | Butano 文档 `bn_sprite_ptr.h:682` + 产品 `battle_map_visual_projection.h:113` | 两处都写「高 z_order 先画（会被盖住）⇒ 低值更靠前」 | **已确认（文档）** |
| H3-H9 | 接线后 `step-20-A` 战场区残差下降 | 判定台 + 固定偏移两个仪器 | 判定台 **3,881 → 809**；固定偏移 **3,881 → 809**（−3,072 = 窗面积） | **已确认** |
| H3-H10 | 窗矩形内**一格角色像素都没有**（窗真的压住了角色） | 逐像素：重制帧窗矩形 vs 资产 | **0 / 3072** 个非窗像素；diff bbox = None | **已确认** |
| H3-H11 | 两个仪器的总残差都不上升 | 判定台 + `align_capture_steps.py` | 判定台 38,047 → **35,973**；固定偏移 54,959 → **51,887**；offset 恒为 **+4** | **已确认** |
| H3-H12 | 窗只在这一拍出现，不会拖累别的帧 | 固定偏移逐帧表 | 除 `step-20-A` 外，25 帧里**没有任何一帧变差** | **已确认** |

---

## 7. 接线请求清单（给父代理）

1. **拷两个资产文件**到共享树（父代理收口时做；本流只改了 lane）：
   * `build/w25-h3/butano-sequel/graphics/battle_ui_prepare_box.bmp`
   * `build/w25-h3/butano-sequel/graphics/battle_ui_prepare_box.json`
2. **三方合并** `game/src/battle_runtime_scene.cpp`
   （`python tools/s49_w25/merge_lanes.py --file game/src/battle_runtime_scene.cpp --lane w25-h2 --lane w25-h3 --lane w25-h4 --apply`）。
   本流只碰了 5 处，全在「prepare box」区段（include / `reset()` / `update()` / 新方法 / 成员）。
3. **无其它请求**：`battle_scene_controller.h` 的 `battle_turn_banner_stage` 枚举**不需要改**（D1 已加好）。

---

## 8. 未完成项

| # | 未完成项 | 状态 / 下一步 |
|---|---|---|
| **U-H3-1** | 承载窗的那一 BG 层的 tilemap 排布（波��� 23 / F2 的 `U-F2-1`） | **不阻塞**：本流是「贴 1:1 资产」，不是复刻绘制逻辑；原版那层怎么排布仍然没查清 |
| **U-H3-2** | 窗的字形来源（原版用哪张字表） | **不阻塞**：资产的字形就是原版 VRAM 的真像素 |
| **U-H3-3** | 窗在原版「请准备」之前/之后其它拍里是否短暂出现 | 部分回答：`step-19` / `step-21` / `step-22` 全帧无窗 ⇒ 只在 `step-20` |
