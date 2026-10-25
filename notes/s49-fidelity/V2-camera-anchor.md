# V2 流 —— 相机锚定机制（地图空间 vs 相机空间）

> 2026-10-24 · stream V2（wave 9）
> 独占产出：本文件 + `tools/s49_v2_anchor/`（仪器）+ `battle_map_visual_projection.h` 的地图空间锚点 API
> 改动文件：`battle_map_visual_projection.h`、`battle_scene_controller.h`、`game/tests/test_battle_map_overlay_anchor.cpp`
> ⛔ **未改** `game/src/battle_runtime_scene.cpp`（V1 独占）、`battle_black_field*.h`、`graphics/`
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` 全程只读；**未提交 git**

---

## 0. 一句话结论

> **两种锚定机制已经查实并量化：原版的覆盖层缓冲「内容锚在地图空间 map px (256, 0)、屏幕位置跟相机」，
> 重制侧是「内容跟相机滑」——所以 32 px 不是一行常量，是内容映射本身。
> 本流已在独占文件里落成可单测的地图空间锚点 API（`battle_map_overlay_*`），
> 并把 W3 的接线点 1（`terrain.cost()==0` → `terrain.overlay_blocked()`）一并改完；
> 剩下的接线在 `battle_runtime_scene.cpp`（V1 独占），§6 给了逐行清单。**

⭐ **另有一个必须先说的坏消息**：共享仪器 `tools/s49_overlay_align/compare_overlay_families.py`
**在数学上表达不了原版的锚点**（`best_window` 只在 `[0,256)` 里搜，而原版的锚点是 256）
⇒ 即使产品侧改对了，「最优窗口 = 原版锚点」这条判据也**必须同时改仪器**（§6 接线点 3）。

---

## 1. 查实的事实（全部实测，勿重查）

### 1.1 原版：内容锚在地图空间，屏幕位置跟相机

| 量 | 值 | 证据 |
|---|---|---|
| 覆盖层缓冲 | 256×256 px（32×32 个 8×8 tilemap 项） | 原版 BG2 tilemap |
| **内容锚点** | **map px (256, 0)**：缓冲像素 (x, y) 持有地图像素 `((x+256) mod 480, y)` | `tools/s49_y3/anchor_search.py`（本流复跑）：`classes=(15,7,1,3) wrap=True` ⇒ **overlap 17984/17984 @ (256,0)**，次优 (264,0) 只有 17216 |
| 屏幕位置 | **跟相机**：`bg2_hoffs = 240` 与地图 BG 的 `bg_hoffs[0..2] = 240` 相同；`bg2_voffs = 24` 与 `bg_voffs = 24` 相同 | 原版真值 `registers` 字段（`bg2_hoffs`/`bg2_voffs` 独立导出） |
| 格线格栅 | **32×16 px**，且落在战斗格边界（格边界 = map px ≡ 0 mod 32 / ≡ 0 mod 16） | 8×8 粒度 dump：竖线画在 entry 列 7/11/15/19/23/27 的**最后 1 px**（即格线的最后一列）⇒ 格边界落在 32 的倍数；横线画在 entry 行 7/9/… 的最后 1 px ⇒ 格边界落在 16 的倍数 |
| 绘制范围 | **只画地图行 1..12** | 8×8 粒度 dump：buffer 行 0..2 与 26..31 全空 |
| 受阻集 | 地形类别 ≠ plain | 17984/17984 px 精确吻合 |

⇒ **机制**：原版的 BG2 是一张**固定的 256×256 地图空间窗口**（锚在 map px 256），
相机滚动只决定「窗口的哪一块在屏幕上」；内容**不随相机滑**。

### 1.2 重制侧：内容跟相机滑

`game/src/battle_runtime_scene.cpp`（wave 8 已改成地图空间口径，但窗口仍是相机派生）：

```cpp
const int window_x = 240 + camera.x().integer();
const int window_y = 248 + camera.y().integer();
_bg->set_position(-window_x, -window_y);
...
const int map_px_y = layer_px_y + 256 * ceil_div(window_y - layer_px_y, 256);
const int map_px_x = layer_px_x + 256 * ceil_div(window_x - layer_px_x, 256);
```

⇒ 内容窗口原点 = **相机的地图位置** ⇒ 相机一动，缓冲里的地图内容就跟着滑 ⇒ **与原版是两种机制**。

### 1.3 ⭐ 关键否定：单靠「把窗口常量改成 256」修不好

本流新写的仪器 `tools/s49_v2_anchor/scan_window.py`
（把共享仪器的窗口搜索从 `[0,256)` 放宽到 `[0,480)`）：

```
=== field-frame-v1: original lit 192
  window (224,  0)  both  81  orig-only 111  remake-only  36  mismatch  26  exact False
  window (232,  0)  ... 同上
  window (240,  0)  ... 同上
  window (248,  0)  ... 同上
  window (256,  0)  ... 同上
  window (264,  0)  ... 同上
  NO exact window in [0,480) x [0,256)
```

⇒ **没有任何一个地图空间窗口能让重制侧当前缓冲内容与原版逐格相等**；
而且分数在 224..264 区间**完全不变** ⇒ 窗口不是唯一（也不是主要的）差距。
⇒ **⇒ 差距在「内容画的是哪一格 + 画哪些行」，不在窗口常量。**

---

## 2. 为什么 32 px 是「机制」而不是「常量」

把原版的缓冲和它的屏幕位置放在一起看：

* 原版缓冲像素 `p` 持有地图像素 `(p + 256) mod 480` ⇒ 缓冲**只覆盖**地图列 8..14 + 回绕的列 0；
* 原版 BG2 滚动 = 240 ⇒ 屏幕左边显示缓冲像素 240 ⇒ 那里持有地图像素 `(240+256) mod 480 = 16`；
* 而原版的地图 BG 在屏幕左边显示地图像素 240。

⇒ **原版的覆盖层格线比它的地图格线偏 32 px**（224 ≡ −32 mod 256），
⇒ 这正是「原版 (256,0) vs 重制 (224,0) ⇒ 差 32 px」的来源：**重制侧把覆盖层钉在了地图上，原版没有**。
⇒ 忠实复刻就必须让重制侧也用原版的机制（内容锚地图空间、屏幕位置跟相机），
⇒ 于是覆盖层与地图自然差 32 px —— **不是把 224 改成 256**。

---

## 3. 产品侧改动（在本流的独占文件里）

### 3.1 `battle_map_visual_projection.h` —— 地图空间锚点 API（新增）

纯整数、无 Butano 依赖、可单测：

| 符号 | 含义 |
|---|---|
| `battle_map_overlay_anchor_x / _y` | **256 / 0** —— 原版实测锚点 |
| `battle_map_overlay_buffer_size` | 256 |
| `battle_map_overlay_map_width / _height` | 480 / 304（15 战斗列 × 32 px，19 战斗行 × 16 px） |
| `battle_map_cell_width / _height` | 32 / 16（一战斗格 = 32×16 px；16×16 只是逻辑格） |
| `battle_map_overlay_map_x(p)` / `_map_y(p)` | 缓冲像素 p 持有的**地图像素** |
| `battle_map_overlay_cell_x(p)` / `_cell_y(p)` | 缓冲像素 p 持有的**战斗列 / 行** |
| `battle_map_overlay_buffer_px(map_px, anchor, size)` | 锚点的逆映射 |
| `battle_map_overlay_screen_x(camera_x)` / `_screen_y(camera_y)` | **原版的屏幕放置**：`240 + camera.x()` / `24 + camera.y()` |

### 3.2 `battle_scene_controller.h` —— W3 接线点 1（顺手改完）

`battle_scene_controller.h:2334` 附近，Y3 留下的 `terrain.cost({x,y}) == 0` 已被改成裸的
`terrain.terrain_class(...) != grid_terrain_class_plain`；本流改成**唯一真源**：

```cpp
if(terrain.overlay_blocked({ x, y }))
```

`grid_map::overlay_blocked()` 在 `grid_pathfinder.h:211`（W3 已实现），语义 = 类别 ≠ plain。
⚠️ **没有动 `terrain.cost()` 的语义**（Y3 台账 H6：4 个既有单测证伪，已回退）。

### 3.3 `game/tests/test_battle_map_overlay_anchor.cpp` —— 新单测（通过）

覆盖：锚点常量 / 缓冲↔地图像素映射 / **480 回绕后格线仍落在战斗格边界** /
缓冲能画到的地图列（8..14 + 0，**列 1..7 永远画不到**）/ 行 0..15 /
锚点逆映射逐像素精确 / 原版的屏幕放置 / 垂直差 224 px 的记录。

---

## 4. 跑了哪些验证

| # | 命令 | 结果 |
|---|---|---|
| V1 | `python tools/s49_y3/anchor_search.py`（复跑原版锚点暴力搜索） | `classes=(15,7,1,3) wrap=True` ⇒ **overlap 17984/17984 @ (256,0)**，次优 (264,0) 17216 ⇒ 锚点复现 |
| V2 | `python tools/s49_v2_anchor/dump_grids.py --vram build/s49-y3/vram-after2/step-21-A.vram-0000.bin` | 原版 32×32 的 8 px 族图 + 重制侧同粒度族图 + 地形：确认原版格线 = 32×16、绘制行 1..12、重制侧内容在 buffer 列 11..27 且行 0..5/12..31 有洞 |
| V3 | `python tools/s49_v2_anchor/scan_window.py --vram …` | **NO exact window in [0,480)×[0,256)**；分数在 224..264 恒定 ⇒ 窗口不是唯一差距 |
| V4 | 原版真值 `registers` 字段 | `bg2_hoffs = 240 == bg_hoffs[0..2]`，`bg2_voffs = 24 == bg_voffs[0..2]` ⇒ 屏幕位置跟相机 |
| V5 | `wsl … g++ -std=c++23 -Wall -Wextra -Werror -pedantic … test_battle_map_overlay_anchor.cpp` ⇒ 运行 | **PASS** |
| V5b | `python tools/s49_v2_anchor/compare_at_anchor.py --vram build/s49-y3/vram-after2/step-21-A.vram-0000.bin` | **把仪器改成「显式锚点 256,0」后**，数字与搜索版**完全相同**（field 81/111/36/26、movegrid 81/111/36/10）⇒ ⭐ **残差不在窗口上，在内容上**；目标仍是 192/0/0/0 |
| V6 | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | HEAD 基线：**pass=101 / fail=20**（失败名单见 §7） |
| V7 | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | 工作区：**pass=113 / fail=20**，失败名单**与基线逐名相同** ⇒ **棘轮绿，无新增红项** |
| V8 | WSL `make -j4`（重制 ROM，带 `LIBBUTANOABS`） | **通过**（exit 0，`Linking ROM... / ROM fixed!`；只有既有警告：`append_combatant_hp` 未使用、`battle_scene_controller.h:948/961` 的 null-dereference 警告、`battle_turn_flow.h` 的 stack-usage 警告 —— **都不是本流引入的**） |

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H1 | 原版的覆盖层内容锚在 map px (256, 0) | 8 px 步长暴力搜索「原版 solid 像素 × 地形受阻像素」的重叠 | **17984/17984**，次优 17216 | **已确认**（复跑 V1） |
| H2 | 原版覆盖层的**屏幕位置**跟相机（内容不跟） | 读原版真值 `registers`：`bg2_hoffs/bg2_voffs` vs `bg_hoffs/bg_voffs` | **240/24 完全相同**；且 grid16 时刻（滚动 152,40）内容锚点仍是 (256,0) | **已确认** |
| H3 | 重制侧的 32 px 差是「窗口常量」造成的 | 把窗口搜索放宽到 `[0,480)×[0,256)`，逐窗比族名 | **没有任何窗口精确**；分数在 224..264 恒定 | **已证伪**（是内容映射 + 绘制范围/受阻集，不是窗口常量） |
| H4 | 原版覆盖层的格线格栅是 32×16 px 且落在战斗格边界 | 8 px 粒度族图：竖线/横线所在 entry 的位置 | 竖线在 entry 列 7/11/15/19/23/27 的最后 1 px ⇒ 格边界 = map px 的 32 的倍数；横线在 entry 行 7/9/… ⇒ 16 的倍数 | **已确认** |
| H5 | 原版只画地图行 1..12 | 同上，行 0..2 与 26..31 全空 | 一致（重制侧 wave 8 已改） | **已确认** |
| H6 | 原版的覆盖层格线比它的地图格线偏 32 px | 缓冲内容锚点 (256,0) + BG2 滚动 240 ⇒ 屏幕左边缓冲 px 240 持地图 px 16，而地图 BG 屏幕左边是地图 px 240 ⇒ 差 224 ≡ −32 mod 256 | 成立 ⇒ 「原版没把覆盖层钉在地图上」 | **已确认** |
| H7 | 把重制侧改成「内容锚地图空间 + 屏幕位置跟相机」即可逐格全等 | 只做内容映射改造后的逐格对拍 | **未跑**（接线在 V1 的文件里，本流无权改） | **未验** |
| H8 | 原版的垂直放置（bg2_voffs = 24）比重制侧（248 + camera.y()）高 224 px | 两个常数的直接相减 | 224 px = 14 战斗行 | **已确认（差值）/ 未验（哪个才对）** |

---

## 6. 接线点清单（**V1 / 父代理**）

### 6.1 `battle_runtime_scene.cpp` —— 覆盖层内容映射（V1 独占，**核心**）

位置：**2221–2230**（窗口常量 + `_bg->set_position`）与 **2237–2266**（内容映射循环）。

```cpp
// 现状（wave 8）
const int window_x = 240 + camera.x().integer();
const int window_y = 248 + camera.y().integer();
_bg->set_position(-window_x, -window_y);
...
const int map_px_y = layer_px_y + 256 * ceil_div(window_y - layer_px_y, 256);
const int cell_y   = map_px_y / cell_height;
const int tile_y   = cell_y_visible ? (map_px_y - cell_y * cell_height) / 8 : 0;
...
const int map_px_x = layer_px_x + 256 * ceil_div(window_x - layer_px_x, 256);
const int cell_x   = map_px_x / cell_width;
const int tile_x   = (map_px_x - cell_x * cell_width) / 8;
```

改成（**用本流新增的 API，include `konoha/battle_map_visual_projection.h`——该头文件已被 include**）：

```cpp
// 内容锚在地图空间：缓冲像素 p 持有地图像素 ((p + 256) mod 480, p)
// —— 原版的锚点，17984/17984 px 实测。
const int map_px_y = battle_map_overlay_map_y(layer_px_y);
const int cell_y   = battle_map_overlay_cell_y(layer_px_y);
const int tile_y   = cell_y_visible ? (map_px_y - cell_y * cell_height) / 8 : 0;
...
const int map_px_x = battle_map_overlay_map_x(layer_px_x);
const int cell_x   = battle_map_overlay_cell_x(layer_px_x);
const int tile_x   = (map_px_x - cell_x * cell_width) / 8;
```

⚠️ **注意 `cell_x >= overlay_width` 的钳位**：`battle_map_overlay_cell_x()` 已经把缓冲尾部的
回绕段（地图列 0）映成 `cell_x == 0`，所以 `cell_x` 的取值是 `{0, 8..14}`，
**全部 < `overlay_width`（= 地形宽 15）** ⇒ 钳位不用放宽。
（若改写时把尾部映成 `cell_x == 15`，就必须同时放宽钳位并把地形取列 0 ——
两种写法都可以，但别忘了回绕段也要画出来：原版行 1..2 的整行 solid 就是它。）

⚠️ **垂直放置待定**：`window_y = 248 + camera.y()` 比原版的 `bg2_voffs = 24` 低 **224 px**。
本流**没有**判定该往哪边改（台账 H8）——它取决于重制侧的地图取景是否与原版一致（wave 9 G1「相机」项）。
先只改内容映射（水平机制），垂直等 G1 结论；或按原版改成 `24 + camera.y()`，
但那样覆盖层会相对重制侧地图整体上移 224 px，**必须**同时核对地图取景。

### 6.2 `battle_runtime_scene.cpp` —— 绘制范围（V1 独占）

**2208–2220** 已经按原版改成 `overlay_first_row = 1 / overlay_last_row = 12` ✔（wave 8 已落地）。
但要注意：改成地图空间锚点后，`cell_y` 的来源变了
（原版：buffer 行 3..25 有内容 ⇒ 地图行 1..12；重制侧：buffer 行 2..25 ⇒ 地图行 1..12）⇒ 行集合一致 ✔。

### 6.3 ⭐ 共享仪器（**必须同时改，否则判据无法成立**）

`D:\Github\gba-naruto\tools\s49_overlay_align\compare_overlay_families.py`：

* `remake_logical_cells(entry_map, window_x, window_y)`（167–194 行）
  现在按「相机派生的窗口」给缓冲像素贴地图标签 ⇒ **表达不了锚点 256**
  ⇒ 需改成「缓冲像素 p 的地图标签 = `(p + 256) mod 480`」（与 `battle_map_overlay_map_x` 同口径）。
* `best_window()`（197–223 行）只在 `[0,256)` 里搜窗口 ⇒ **锚点 256 落在搜索区间外**
  ⇒ 需改成固定锚点 256（或把区间放宽到 `[0,480)`）。
* `original_map_cells()`（226–240 行）已经用 `ORIGINAL_MAP_ANCHOR = (256, 0)` ✔，不用动。

⚠️ 这个文件是 **Y3/W2 共用的共享仪器**，本流**没有改**（怕越权），请父代理裁决。

### 6.4 已在本流独占文件里改完的

* `battle_scene_controller.h`：`terrain.cost({x,y}) == 0` → `terrain.overlay_blocked({x,y})` ✔

---

## 7. 单测棘轮

| 树 | 通过 | 失败 | 失败名单 |
|---|---:|---:|---|
| HEAD 基线（`run-baseline-tests.sh`） | 101 | **20** | 见下 |
| 工作区（`w1-run-all-tests.sh`） | **113** | **20** | **与基线逐名相同** |

⇒ **new red = 0 ⇒ 棘轮绿 ✔**（+12 个通过项来自并行流在树上的改动，**不是本流**；
本流新增的 `test_battle_map_overlay_anchor` 是其中之一，单独跑也是 PASS）。

失败名单（两侧完全一致）：

```
test_battle_all_scenario_runtime      test_battle_s49_input_flow
test_battle_campaign_route             test_battle_s49_opening
test_battle_campaign_save              test_battle_scene_character_actions
test_battle_campaign_scenario_42       test_battle_scene_controller
test_battle_campaign_scenario_43       test_battle_scene_multi_unit
test_battle_campaign_scenario_44       test_battle_scene_results
test_battle_campaign_scenario_45       test_battle_dynamic_deployment_turn
test_battle_campaign_scenario_46       test_battle_material_pickups
test_battle_campaign_scenario_47       test_battle_presentation_controller
test_battle_campaign_scenario_49       test_battle_runtime_scene_gate
```

⚠️ `test_battle_scene_controller` 与 `test_battle_runtime_scene_gate` 在基线里就红
（后者是 `sizeof(battle_scene_snapshot<12>) <= 1120` 的静态断言：1672 > 1120）
⇒ **本流改 `battle_scene_controller.h` 的受阻集判定后，它仍然以**同名**红着，没有变绿也没有变红**
（失败点不变：`escort_controller.tick().success()`）。

---

## 8. 未达成 / 剩余风险（**不粉饰**）

1. **判据（同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0）本流没有跑到。**
   原因：内容映射的接线在 `battle_runtime_scene.cpp`（V1 独占），本流无权改；
   且**共享仪器表达不了锚点 256**（§6.3）⇒ 两边都得改才能验。
2. **垂直放置（224 px）未判定。** 原版 `bg2_voffs = 24`，重制侧 `248 + camera.y()`。
   这不是覆盖层的问题，是**地图取景**的问题（wave 9 G1 相机项）⇒ 本流只记录，不改。
3. **缓冲尾部（回绕段，32 px = 1 个战斗列）的绘制**：本流的 API 已经把它映成地形列 0，
   钳位不用动；但**要确认 V1 的接线确实画了这一段**（原版行 1..2 的整行 solid 就是它），
   否则会残留 1 列 × 12 行 ≈ 12 格差异。
4. **重制侧相机与原版相机在同一时刻是否停在同一地图位置**没有查实。
   逐格对拍（缓冲内容）与相机无关，但**屏幕残差**与它有关（G1）。
5. `tools/s49_overlay_align/compare_overlay_families.py` 的口径若被改，
   会同时改变判定台的 `overlay_residual` 口径（Y3 §7.4 已提醒过）⇒ 请 W2/X4r 复核。

---

## 9. 改动的文件（完整绝对路径）

### 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel\`）

| 文件 | 改动 |
|---|---|
| `game\include\konoha\battle_map_visual_projection.h` | 新增地图空间锚点 API（锚点常量、缓冲↔地图像素、战斗列/行、锚点逆映射、原版的屏幕放置） |
| `game\include\konoha\battle_scene_controller.h` | 受阻集判定改用 `terrain.overlay_blocked({x,y})`（W3 接线点 1） |
| `game\tests\test_battle_map_overlay_anchor.cpp` | **新增**单测（锚点 / 格线 / 覆盖范围 / 逆映射 / 屏幕放置） |

### 主仓（`D:\Github\gba-naruto\`）

| 文件 | 改动 |
|---|---|
| `notes\s49-fidelity\V2-camera-anchor.md` | 本文件 |
| `tools\s49_v2_anchor\scan_window.py` | **新增**：把窗口搜索放宽到 `[0,480)`，判定「有没有窗口能逐格全等」 |
| `tools\s49_v2_anchor\compare_at_anchor.py` | **新增**：**显式锚点 256,0** 的逐格对拍（共享仪器表达不了这个锚点）—— V1/父代理可直接照它改共享仪器 |
| `tools\s49_v2_anchor\dump_grids.py` | **新增**：原版 / 重制侧 / 地形三方 8 px 粒度 dump |

**未改**：`game\src\battle_runtime_scene.cpp`、`battle_black_field*.h`、`graphics/`、
`battle_presentation_*.h`、`battle_opening_title.h`、逆向线。
