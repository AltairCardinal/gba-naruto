# X2 流 —— 覆盖层逐格族名归零（接管 wave 11 的 W2）

> 2026-10-24 · stream X2（wave 12）
> 独占产出：本文件 + `tools/s49_x2_overlay/`（新仪器，**只读复用** `tools/s49_overlay_align/`）
> 改动文件：`battle_range_ui_style.h`（一条规则）+ 两个既有单测的对应断言
> ⛔ **未改** `game/src/battle_runtime_scene.cpp` / `battle_scene_controller.h`（X1 独占）、
> `battle_result*.h`（X3 独占）、`tools/s49_overlay_align/`（U4/W4 独占）
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；**未提交 git**

---

## 0. 一句话结论

> **W2 留下的「terrain grid 19×19 vs MAP_WIDTH 15 列」这条线索是错的：地形网格是 15×19
> （与原版 map-14 画布 480×304 px 完全一致），真正的不一致在**仪器**里 ——
> 共享仪器给**原版**贴地图标签时**没有按 480 px 回绕缓冲尾部**，而给**重制侧**回绕了，
> 于是两侧的尾部两列被互相错开，量出���那 24 格「原版缺」+ 24 格「多画」**全是标签错位
> 的假象**；补上回绕后 field/movegrid 已经是 **同亮 192 / 缺 0 / 多画 0**。
>
> 剩下的族名不一致里，**只有 2 格是本流的规则问题**（移动阶段的黄色光标格），已修；
> 其余全部落在**原版缓冲尾部的陈旧内容**（不是当前地图空间，任何忠实的重制都复现不了）
> 和**walk 的相位/游戏状态**上（X1 的地盘）。**
> ⇒ 验收目标「192/0/0/0」在本流的权限内不可达**，理由逐条列在 §5。**

---

## 1. 先查清 W2 的线索（任务书 §2.2 的第一件事）

### 1.1 地形网格没有不一致

| 量 | 值 | 证据 |
|---|---|---|
| 重制侧 battle-14 地形 | **15 列 × 19 行**（战斗格） | `generated_battle_map_content.h`：`battle_map_definition{ 14, 15, 19, 4393, 285 }` |
| 仪器的 `remake_terrain()` | 19 行 × 15 列 | 实跑打印：`terrain grid: 19 rows x 15 cols (map 480 x 304 px, 30 logical cols)` |
| `MAP_WIDTH = 15 * 32 = 480` | 与 15 列一致 | 共享仪器 `compare_overlay_families.py:114` |
| **原版自己的 map-14 画布** | **480 × 304 px = 60 × 38 图块** | `artifacts/map-canvases-v1/canvases/map-14-primary.png`（逆向线，只读） |

⇒ **15 战斗列 × 32 px = 480 px、19 战斗行 × 16 px = 304 px**，三方一致。
⇒ **「19×19 vs 15 列」这条线索不成立**（台账 X2-H1）。

### 1.2 ⭐ 真正的仪器 bug：**原版侧没有按 480 px 回绕**

共享仪器 `tools/s49_overlay_align/compare_overlay_families.py`：

* **重制侧** `remake_logical_cells()`：`map_px_x = (column * 8 + anchor_x) % MAP_WIDTH` ⇒ **回绕**；
* **原版侧** `original_map_cells()`：`map_lx = (anchor_x + lx * 16) // 16` ⇒ **不回绕**。

原版的 BG2 缓冲是 256×256 px，锚在地图像素 **(256, 0)**，所以它的**尾部 32 px
（缓冲像素 224..255）装的是地图的第 0 列**（地图 px 0..31）——这正是锚点证据
（`tools/s49_y3/anchor_search.py`：**17984/17984 px @ (256,0)，wrap=True**）测出来的事实。

⇒ 不回绕 ⇒ 原版的缓冲逻辑列 14、15 被贴成**地图列 30、31**（30 列的地图里根本不存在），
而重制侧的同两列被回绕成**地图列 0、1** ⇒ **两侧在尾部比的是两个完全不同的格**：

| | 原版贴的列 | 重制侧贴的列 | 后果 |
|---|---|---|---|
| 共享仪器（现状） | 16..31 | 16..29, 0, 1 | 每时刻 **24 格「原版缺」 + 24 格「多画」**（恰好抵消，因为尾部就是 2 个逻辑列 × 12 行） |
| 两侧都回绕（正确） | 16..29, 0, 1 | 16..29, 0, 1 | **缺 0 / 多画 0** |

⇒ **那 24/24 是纯标签错位，不是产品差异**（台账 X2-H2）。

### 1.3 修法（**共享仪器是 U4/W4 的，本流没有动它**）

`tools/s49_overlay_align/compare_overlay_families.py:320` 一行：

```python
-            map_lx = (anchor_x + lx * 16) // 16
-            map_ly = (anchor_y + ly * 16) // 16
+            map_lx = ((anchor_x + lx * 16) % MAP_WIDTH) // 16
+            map_ly = ((anchor_y + ly * 16) % MAP_HEIGHT) // 16
```

（`MAP_WIDTH` / `MAP_HEIGHT` 已在该文件里定义，`anchor_y = 0` 所以第二行等价。）

⇒ 本流在**自己���目录**里实现了等价测量（`tools/s49_x2_overlay/compare_families.py`，
只 import 共享仪器、不修改它），上面这张表就是它跑出来的。

---

## 2. 逐格族名对拍（四时刻，整条 walk 35 个 anchor dump）

口径：`python tools/s49_x2_overlay/compare_families.py --vram-dir <dir>`；
两侧都换算到**地图空间 16×16 逻辑格**再比族名。

### 2.1 回绕修好之后（**尾部仍然参与比较**）

| 时刻 | 同亮 | 原版缺 | 多画 | 族名不一致 | 其中尾部 | 其余 |
|---|---:|---:|---:|---:|---:|---:|
| field | **192** | **0** | **0** | 61 | 11 | 50 |
| movegrid | **192** | **0** | **0** | 15 | 11 | 4 |
| grid16 | 175 | 0 | 17 | 85 | 22 | 63 |
| banner | 0 | 0 | 0 | **0（exact ✔）** | 0 | 0 |

⇒ **「缺 0 / 多画 0」已经达成**；剩下的全是**族名不一致**。

### 2.2 ⭐ 再把原版缓冲的**尾部**剔掉（这才是忠实的测量，见 §3）

| 时刻 | 同亮 | 原版缺 | 多画 | 族名不一致 |
|---|---:|---:|---:|---:|
| field | 168 | **0** | **0** | 50 |
| movegrid | 168 | **0** | **0** | **4** |
| grid16 | 153 | 0 | 15 | 65 |
| banner | 0 | 0 | 0 | **0（exact ✔）** |

⇒ **movegrid 只差 4 格**，其中 2 格是本流的规则（已修）。

---

## 3. ⭐ 剩余差异的归因（**三类，逐类有证据**）

### 3.1 尾部（map 列 0）= **11 格（field/movegrid）、22 格（grid16）—— 原版那一段不是当前地图空间内容**

原版缓冲的尾部（缓冲像素 224..255 = 地图 px 0..31 = 地图第 0 列）里实测到：

| 证据 | 内容 |
|---|---|
| 尾部列 29/30/31 | 恒为 `257/258/260/261`（空白/格线）—— 但地形里**地图第 0 列整列是 class 15（墙）**，应当画灰网点 |
| 尾部列 28 | `278/280`（灰网点），只覆盖地图 px 0..**7**（8 px，而不是 32 px） |
| 尾部列 28，movegrid 帧 r12/r13 | `270/272` = **黄色光标格** |
| 尾部列 28，movegrid 帧 r14..r17 | `262/264` = **青色可达集** |
| 尾部列 28，grid16 帧 r6/r7 | `270/272` = 黄色光标格 |

⇒ **墙列上不可能有光标、也不可能有可达集** ⇒ 尾部是**陈旧/半刷新的残留**，
不是当前地图空间的内容 ⇒ **任何忠实的重制都复现不了它**（台账 X2-H3）。
⇒ 处置：**测量时把尾部从两侧同时剔掉**（仪器改动，不是产品改动）。
⇒ ⚠️ 共享仪器的 `find_overlay_map()` 用 terrain 判据挑覆盖层 map 时，
尾部那 2 格「实心落在非 plain 上」的证据是成立的（`17984/17984` 只查 ⇒ 方向），
所以**剔尾部不影响仪器的定位判据**。

### 3.2 ⭐ 相位/游戏状态 —— field 与 grid16 的 50 / 65 格（X1 的地盘）

原版四个时刻的族直方图（192 个逻辑格）与重制侧 35 帧里**有覆盖层的 7 帧**：

| | solid | edge | hatch(青) | band(黄) | line_alt(橙) | hatch_shift(绿) |
|---|---:|---:|---:|---:|---:|---:|
| 原版 field | 83 | 90 | 12 | 1（**在尾部**） | 6 | 0 |
| 原版 movegrid | 83 | 63 | **46** | **0** | 0 | 0 |
| 原版 grid16 | 44 | 107 | 14 | 4（2 个在尾部） | 6 | 0 |
| 重制 step-26-A | 96 | 52 | 42 | 2 | 0 | 0 |
| 重制 step-29..34-A | 90 | 52 | 0 | 2 | 2 | **46** |

⇒ **原版的 field 是一个「青 + 橙 + 黄」同时出现的稳定态**（126 帧可复现），
而**重制侧的 walk 里没有任何一帧同时画青和橙**：
step-26-A 只有青，step-29..34 只有绿+橙。
⇒ **field 时刻在重制侧的 35 帧里没有对应帧** ⇒ 它的 50 格差异不是覆盖层规则能修的，
是**走位/相位结构**的问题（X1 的闭环驱动 + 输入回归）。
⇒ grid16 是原版的**单帧瞬态**（缓冲只刷了一半：第 1 行空、行 2..12 有内容，
且比 field 整体下移一行），同样不可复现。

### 3.3 ⭐ movegrid 的 4 格 —— **2 格是本流的规则（已修），2 格是游戏状态**

* `hatch->band` × 2：地图逻辑列 20/21、行 6（战斗格 10）——
  **原版画青，重制侧画黄**（重制侧的光标格）。⇒ **本流的规则问题**（§4）。
* `hatch->solid` × 2：地图逻辑列 18/19、行 7（战斗格 9）——
  原版画青，重制侧画灰网点：重制侧有一个**单位站在**那一格（`_blocked_overlay_rows`
  把占位格也算受阻），而原版那一格是可走的。⇒ **游戏状态差异**（占位单位的位置不同）。

---

## 4. 产品侧改动（本流独占文件里唯一的一条规则）

### 4.1 `battle_range_ui_style.h` —— **移动阶段不画黄色光标格**

**实测依据**（原版自己的帧，`tools/s49_rule_probe/overlay_ground_truth.py`）：

* 原版的**移动阶段帧（movegrid）没有任何一格黄色**：192 个点亮格 =
  solid 83 / edge 63 / **hatch 46**；
  而光标正落在出手单位自己的格（地图 (11, 6)），那一格在青色可达集里；
* 原版的黄色格只出现在**不是当前地图空间**的内容里：
  field 帧唯一的黄格在缓冲尾部（逻辑列 15 → 地图列 1），
  grid16 帧主区域的黄格按 F-rule §3.3 是**上一帧的残影**（光标精灵已经移走）；
* ⇒ 与 G-H15 同源：**青/橙/绿/黄都是相位族**，
  移动阶段只画青（G-H15 已证橙与绿不在移动阶段出现）。

**改动**（`battle_range_ui_cell_kind()`）：

```cpp
-    if(cursor_cell)
+    if(cursor_cell && ! move_phase)
     {
         return battle_range_ui_tile_kind::cursor;
     }
```

⇒ 移动阶段光标格落回 `move`（青），其它相位不变（黄格仍然优先于绿/橙/青/灰）。

⭐ **这条规则同时废掉了两个更早的假设**（都不是本流引入的，是被本流的测量推翻的）：

| 版本 | 移动阶段的光标格 | 状态 |
|---|---|---|
| **HEAD**（`git diff` 里的旧块） | `attack_range`（**橙**），注释写着「Original S49 move-selection BG2 uses palette index 4 (orange) at the destination」 | **已证伪**：原版的移动阶段帧里 `line_alt` = **0 格** |
| **wave 6 / Y3**（未提交的工作区块） | `cursor`（**黄**） | **已证伪**：原版的移动阶段帧里 `band` = **0 格** |
| **本流 X2** | `move`（**青**） | 两条实测都吻合 |

**预期效果**（对拍口径）：movegrid 的 `hatch->band` × 2 变成 `hatch->hatch` ⇒
**族名不一致 4 → 2**（field / grid16 的黄格本来就落在青/格线上，不改计数）。
⚠️ **该数字尚未在 ROM 上复测**（见 §6.4）。

### 4.2 单测（**两个既有测试文件都编码了旧规则，必须一起改，否则棘轮变红**）

| 文件 | 改动 |
|---|---|
| `game/tests/test_battle_range_ui_overlay_rules.cpp` | 「The cursor still wins in the move phase」断言改为 `move`；新增 3 条断言（移动阶段非可达的光标格 → blocked / grid；非移动阶段光标仍然优先） |
| `game/tests/test_battle_range_ui_style.cpp` | 同一条旧断言改为 `move`，并补上「非移动阶段光标仍然优先」 |

---

## 5. 验收目标「192 / 缺 0 / 多画 0 / 不一致 0」为什么在本流权限内不可达

| # | 障碍 | 归属 | 证据 |
|---|---|---|---|
| 1 | 共享仪器给原版侧贴标签时**没有 480 px 回绕** ⇒ 24/24 的假差异 | **仪器**（U4/W4 的文件，一行改动，见 §1.3） | §1.2 |
| 2 | 原版缓冲的**尾部不是当前地图空间内容**（墙列上的陈旧光标/可达集） ⇒ 11/22 格任何忠实重制都复现不了 | **仪器**（测量时剔尾部，见 §3.1） | §3.1 |
| 3 | 原版的 field 是**青+橙同现**的稳定态，重制侧 35 帧里**没有任何一帧**同现 ⇒ 50 格差异 | **X1**（走位/相位） | §3.2 |
| 4 | grid16 是原版的**单帧瞬态**（缓冲半刷新、整体下移一行） | **X1** | §3.2 |
| 5 | movegrid 剩 2 格：重制侧有一个单位占着原版可走的格 | **X1**（游戏状态） | §3.3 |
| 6 | 移动阶段的黄色光标格（2 格） | **本流（已修）** | §4 |

⇒ **本流能交付的上限**：
`field 168/0/0/50` · `movegrid 168/0/0/2（规则修后）` · `grid16 153/0/15/65` · `banner 0/0/0/0 exact`。

---

## 6. 跑了哪些验证

### 6.1 逐格族名对拍（**整条 walk 35 个 anchor dump 口径**）

输入：`build/s49-package/evidence/overlay/vram/*.vram-0000.bin`（35 个 dump，7 帧带覆盖层）
ROM sha256（重制侧）：**`b6c2a05fa50e28613ec8ab35de5306ef635819ab87917756537b248ba061c2cb`**
（= `build/s49-package/receipt.json` 的 `remake_rom_sha256`；当前盘上的
`butano-sequel.gba` 也是这个 sha）

| 口径 | field | movegrid | grid16 | banner |
|---|---|---|---|---|
| 共享仪器（父代理基线） | 168 / 24 / 24 / 50 | 168 / 24 / 24 / 4 | 153 / 22 / 39 / 65 | 0 / 0 / 0 / 0 |
| **两侧回绕** | **192 / 0 / 0 / 61** | **192 / 0 / 0 / 15** | 175 / 0 / 17 / 85 | 0 / 0 / 0 / 0 |
| **两侧回绕 + 剔尾部** | 168 / 0 / 0 / 50 | 168 / 0 / 0 / **4** | 153 / 0 / 15 / 65 | 0 / 0 / 0 / 0 |

（列的顺序：同亮 / 原版缺 / 多画 / 族名不一致）

### 6.2 单测棘轮

| 树 | 通过 | 失败 | 失败名单 |
|---|---:|---:|---|
| HEAD 基线（`build/run-baseline-tests.sh`） | 101 | **20** | 见 §6.2.1 |
| 工作区（`build/w1-run-all-tests.sh`） | **117** | **20** | **与基线逐名相同 ⇒ 棘轮绿，新红 0** |

失败名单（两侧完全一致）：
`test_battle_all_scenario_runtime` `test_battle_campaign_route` `test_battle_campaign_save`
`test_battle_campaign_scenario_42..47` `test_battle_campaign_scenario_49`
`test_battle_dynamic_deployment_turn` `test_battle_material_pickups`
`test_battle_presentation_controller` `test_battle_runtime_scene_gate`
`test_battle_s49_input_flow` `test_battle_s49_opening`
`test_battle_scene_character_actions` `test_battle_scene_controller`
`test_battle_scene_multi_unit` `test_battle_scene_results`

⇒ ⚠️ 第一次跑工作区时**多红了一项** `test_battle_range_ui_style`
（Y3 的既有测试也编码了「光标在移动阶段优先」这条旧规则）⇒ 已同步更新该断言后复跑转绿。

### 6.3 判定台残差

**本流没有跑判定台**：判定台要用 ROM 抓帧，而重制 ROM 此刻由 **X1** 在改
（`battle_runtime_scene.cpp` 的输入回归），并发构建会互相覆盖
（任务书已记载 `objcopy: Invalid argument` 的竞态），全量录制还会吃 7–8 GB。
⇒ ⇒ **本流没有新的残差数字可报**；唯一会改变画面的产品改动是 §4.1，
它把移动阶段光标格的**黄**换成**青**，而原版移动阶段帧里**没有黄色格**
⇒ 方向上只会让残差变小，但**必须由父代理在 X1 的 ROM 定稿后复跑确认**。

### 6.4 其它验证

| # | 命令 | 结果 |
|---|---|---|
| V1 | `python tools/s49_x2_overlay/diagnose.py --vram-dir …` | 地形 19×15；两侧列集合对比；确认原版尾部 = 地图列 0/1 |
| V2 | `python tools/s49_x2_overlay/blocked_vs_terrain.py` | 原版的 solid 图块数 vs 地形：列 8..14 **逐格吻合**；**列 0 只有 2/8**（尾部异常） |
| V3 | `python tools/s49_x2_overlay/dump_grids.py --vram-dir …` | 两侧地图空间逐格并排图 + diff 图 |
| V4 | `python tools/s49_x2_overlay/map_edges.py` | 原版 map-14 画布 480×304 px（60×38 图块）⇒ 15×19 战斗格坐实 |
| V5 | `python tools/s49_overlay_align/compare_overlay_families.py`（共享仪器，只读） | 复现父代理基线 168/24/24/50 等 |
| V6 | `python tools/s49_x2_overlay/compare_families.py --vram-dir … [--exclude-tail]` | §6.1 的两张表 |
| V7 | `wsl … g++ … test_battle_range_ui_overlay_rules.cpp` | PASS |
| V8 | `wsl … g++ … test_battle_range_ui_style.cpp` | PASS |
| V9 | `bash build/run-baseline-tests.sh` | pass=101 / fail=20 |
| V10 | `bash build/w1-run-all-tests.sh` | pass=117 / fail=20（名单逐名相同） |

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| X2-H1 | 地形网格 19×19 与 MAP_WIDTH 的 15 战斗列不一致 | 读 `generated_battle_map_content.h` 的 battle-14 定义 + 实跑 `remake_terrain()` + 原版 map-14 画布尺寸 | 地形 **15 列 × 19 行**；画布 **480×304 px**；三者一致 | **已证伪**（这条线索不成立） |
| X2-H2 | 24 格「原版缺」+ 24 格「多画」来自**仪器给两侧贴了不同的地图标签** | 读共享仪器的 `remake_logical_cells()`（`% MAP_WIDTH`）与 `original_map_cells()`（无回绕）；再用自己实现跑两侧都回绕 | 回绕后 field/movegrid **同亮 192 / 缺 0 / 多画 0** | **已确认** |
| X2-H3 | 原版缓冲的尾部（地图列 0）不是当前地图空间内容 | 逐图块读尾部：列 29/30/31 恒为格线/空白（但地形说那是墙）、列 28 只覆盖 8 px 且带**陈旧光标(270/272)**与**陈旧可达集(262/264)** | 墙列上出现光标与可达集 ⇒ 陈旧内容 | **已确认** |
| X2-H4 | 原版**移动阶段不画黄色光标格** | 读原版四时刻的族直方图 + 光标位置（地图 (11,6)） | movegrid 帧 **0 个黄格**（192 格 = 83/63/46）；field 的黄格在尾部；grid16 的黄格是残影 | **已确认**（已实现 + 单测） |
| X2-H5 | 原版 field 时刻的「青+橙同现」在重制侧 35 帧里没有对应帧 | 统计 7 个带覆盖层的重制帧的族直方图 | step-26-A 只有青；step-29..34 只有绿+橙；**无一帧同现** | **已确认** |
| X2-H6 | 原版 solid ≡ 地形类别 ≠ plain | `blocked_vs_terrain.py`：覆盖到的战斗格 8..14 逐格吻合 | 8..14 **逐格吻合**；列 0 只有 2/8 ⇒ 方向「solid ⇒ 受阻」成立，逆向不成立 | **部分确认**（与 H3 一致） |
| X2-H7 | 把窗口常量从 224 改成 256 就能逐格全等 | V2 流的 `scan_window.py`（[0,480) 全扫）已否；本流改为「标签口径」后重测 | 标签修好后 **缺 0 / 多画 0** 已达成，剩下的是内容/相位 | **已证伪**（不是窗口问题） |
| X2-H8 | §4.1 的规则改动能把 movegrid 的族名不一致 4 → 2 | 逐格读重制 step-26-A 的 2 个 `band` 格（地图列 20/21 行 6） | 规则改动后这 2 格变 `hatch`，与原版的 `hatch` 一致 | **未验**（需重建 ROM + 重录 walk 复测） |
| X2-H9 | HEAD 里「移动阶段的光标格 = 橙色（落点）」那条注释是对的 | 原版 movegrid 帧的族直方图 | `line_alt` = **0 格** ⇒ 移动阶段没有橙色 | **已证伪** |
| X2-H10 | wave 6 / Y3 的「光标格 = 黄色」是对的 | 同上 | `band` = **0 格** ⇒ 移动阶段没有黄色 | **已证伪** |

---

## 8. 接线点清单

### 8.1 `tools/s49_overlay_align/compare_overlay_families.py`（**U4/W4 的文件，本流只读；请代为落地**）

1. **原版侧回绕**（§1.3）—— 一行改动，去掉 24/24 的假差异；
2. **可选：把尾部从两侧同时剔掉**（§3.1）—— 原版的缓冲逻辑列 14/15 与重制侧的地图列 0/1；
   不剔的话 field/movegrid 会永远差 11 格、grid16 差 22 格。

### 8.2 `battle_runtime_scene.cpp`（**X1 独占**）

**本流不需要改它**（规则改动全在 `battle_range_ui_style.h` 里）。
若父代理要让「移动阶段光标格 = 青」在 ROM 上生效，**不需要任何接线**，
只需重建 ROM；`battle_range_ui_cell_kind()` 的调用点（`battle_runtime_scene.cpp:2324`）
已经把 `move`（= `phase == move_selection`）作为第一个参数传进去了。

### 8.3 `battle_scene_controller.h`（**X1 独占**）

本流没有改动需求。若要把「占位单位也算受阻」这一条与原版对齐
（movegrid 剩的 2 格 `hatch->solid`），改动点在 `_refresh_overlay_cache()`
里把单位占位写进 `_blocked_overlay_rows` 的那段循环（`battle_scene_controller.h:2457-2474`）。

---

## 9. 改动的文件（完整绝对路径）

### 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel\`）

| 文件 | 改动 |
|---|---|
| `game\include\konoha\battle_range_ui_style.h` | `battle_range_ui_cell_kind()`：移动阶段不再画黄色光标格（`cursor_cell && ! move_phase`）；补了实测依据注释 |
| `game\tests\test_battle_range_ui_overlay_rules.cpp` | 更新「光标在移动阶段优先」的旧断言 + 新增 3 条断言 |
| `game\tests\test_battle_range_ui_style.cpp` | 同一条旧断言更新 + 补「非移动阶段光标仍然优先」 |

### 主仓（`D:\Github\gba-naruto\`）

| 文件 | 改动 |
|---|---|
| `tools\s49_x2_overlay\compare_families.py` | **新**：两侧都回绕的逐格族名对拍 + 尾部剔除开关 + 差异归因 |
| `tools\s49_x2_overlay\diagnose.py` | **新**：地形网格 / 两侧列集合 / 两种口径并排 |
| `tools\s49_x2_overlay\dump_grids.py` | **新**：两侧地图空间逐格并排图 + diff 图 |
| `tools\s49_x2_overlay\blocked_vs_terrain.py` | **新**：原版的 solid 图块数 vs 地形类别（逐战斗格） |
| `tools\s49_x2_overlay\map_edges.py` | **新**：原版 map-14 画布的尺寸/边缘（只读逆向线） |
| `notes\s49-fidelity\X2-overlay-zero.md` | **新**：本文件 |

**未改**：`game\src\battle_runtime_scene.cpp`、`game\include\konoha\battle_scene_controller.h`、
`game\include\konoha\battle_map_content.h`、`game\include\konoha\grid_pathfinder.h`、
`game\include\konoha\battle_map_visual_projection.h`、
`tools\s49_overlay_align\*`（共享仪器）、逆向线 `D:\Shell\gba-naruto-reverse`。
**未提交 git**；**新文件一律 LF、无 BOM**。
