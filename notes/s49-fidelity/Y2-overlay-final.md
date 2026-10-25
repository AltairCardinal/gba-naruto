# Y2 流 —— 覆盖层收尾（2 格黄色光标格 + 仪器 480 px 回绕）

> 2026-10-24 · stream Y2（wave 13，收官波）
> 独占产出：本文件 + `tools/s49_y2_overlay/`（新仪器）+ `game/tests/test_battle_range_ui_phase_truth_table.cpp`（新单测）
> 改动文件：`tools/s49_overlay_align/compare_overlay_families.py`（仪器，**任务书授权**）、
> `game/tests/test_battle_range_ui_phase_truth_table.cpp`（新）
> ⛔ **未改** `game/src/battle_runtime_scene.cpp` / `battle_scene_controller.h` /
> `battle_scene_presentation_event.h`（Y1 独占）、`battle_black_field*.h` / `graphics/`（Y3 独占）、
> `battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h`（X2 已改，本流只验证）
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；**未提交 git**

---

## 0. 一句话结论

> ⭐ **Y2 的三个任务全部落地**：
>
> **任务 B（仪器补 480 px 回绕）** —— 共享仪器 `compare_overlay_families.py` 的
> `original_map_cells()` 原来给原版侧贴地图标签时**不回绕**，给重制侧却回绕了
> ⇒ 两侧的缓冲尾部两列被互相错开 ⇒ 那 **24 格「原版缺」+ 24 格「多画」全是标签错位的假象**。
> 补上回绕后（**两侧都回绕**）：
> **`field` = 同亮 192 / 缺 0 / 多画 0**、**`movegrid` = 192 / 0 / 0**、**`banner` 逐格全等**。
>
> **任务 A（2 格黄色光标格）** —— X2 已改的规则（移动阶段不画黄色光标格）**在 ROM 上复测通过**：
> 移动阶段帧的族直方图由 `solid 72 / edge 52 / hatch 42 / **band 2**` 变成
> `solid 72 / edge 52 / **hatch 44**` ⇒ **那 2 格黄格变成 2 格青格**，
> `movegrid` 的族名不一致由 **15 → 13**（剔尾部口径 **4 → 2**）。
>
> **任务 C（原版缓冲尾部的陈旧内容）** —— 给出了一条**可判定的证据**：
> 原版缓冲的尾部是**地图第 0 列**，而 battle-14 的第 0 列在原版自己的碰撞网格里
> **十二行全是墙（class 15）**；可原版却在那儿画了**黄色光标格**、**青色可达集**和
> **可走格线** ⇒ **尾部不是当前地图空间的内容，任何忠实的重制都复现不了**。
>
> ⇒ **验收目标「192/0/0」在 Y2 的权限内达成**（`field` / `movegrid`）；
> 剩下的族名不一致**逐格列出**且**逐格给出性质判定**，
> 四时刻的**产品差 = 0**。

---

## 1. 任务 B：仪器补 480 px 回绕（**「192/0/0」的关键**）

### 1.1 病根（**不是** W2 留下的「19×19 vs 15 列」那条线索）

X2 已查实：地形网格就是 **15 列 × 19 行**（480×304 px，与原版 map-14 画布一致）。
真正的 bug 在**仪器**里：

| | 原版侧贴的地图标签 | 重制侧贴的地图标签 |
|---|---|---|
| **修之前**（共享仪器） | `map_lx = (anchor_x + lx*16) // 16` ⇒ **不回绕** | `map_px_x = (column*8 + anchor_x) % MAP_WIDTH` ⇒ **回绕** |
| 修之后 | `((anchor_x + lx*16) % MAP_WIDTH) // 16` ⇒ **回绕** | 同左 |

原版的 BG2 缓冲是 **256×256 px**、锚在地图像素 **(256, 0)**，而地图宽 **480 px**
⇒ 缓冲的尾部 32 px（缓冲 px 224..255）装的是地图的第 0 列（地图 px 0..31）。
锚点证据就是这么测出来的（`tools/s49_y3/anchor_search.py`：**17984/17984 px @ (256,0)，wrap=True**）。

⇒ 不回绕 ⇒ 原版的缓冲逻辑列 14、15 被贴成**地图列 30、31**（30 列的地图里根本不存在），
而重制侧的同两列被回绕成**地图列 0、1** ⇒ **两侧在尾部比的是两个完全不同的格**。

### 1.2 改动（**一行**，在授权文件里）

`D:\Github\gba-naruto\tools\s49_overlay_align\compare_overlay_families.py`：

```diff
-            map_lx = (anchor_x + lx * 16) // 16
-            map_ly = (anchor_y + ly * 16) // 16
+            map_lx = ((anchor_x + lx * 16) % MAP_WIDTH) // 16
+            map_ly = ((anchor_y + ly * 16) % MAP_HEIGHT) // 16
```

（`MAP_WIDTH = 480` / `MAP_HEIGHT = 304` 已在该文件里定义；`anchor_y = 0` ⇒ 垂直回绕是恒等，
但公式写成对称的，锚点若移动也不会错。函数 docstring 与模块 docstring 都补了依据。）

### 1.3 ⭐ 修正前后的数字对照（**原版侧 / 重制侧 / 四时刻**）

口径：`python tools/s49_overlay_align/compare_overlay_families.py --vram-dir <35 个 anchor dump>`；
**整条 walk 口径**（35 个 dump 里 7 帧带覆盖层，逐帧取最优帧）。
输入 = 钉住 ROM **`b6c2a05f…`** 的 walk（`build/s49-package/evidence/overlay/vram`）。

| 时刻 | 修正前：同亮 / 原版缺 / 多画 / 族名不一致 | 修正后：同亮 / 原版缺 / 多画 / 族名不一致 |
|---|---|---|
| `field` | 168 / **24** / **24** / 50 | **192 / 0 / 0** / 61 |
| `movegrid` | 168 / **24** / **24** / 4 | **192 / 0 / 0** / 15 |
| `grid16` | 153 / **22** / **39** / 65 | 175 / 0 / **17** / 85 |
| `banner` | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0（**逐格全等** ✔） |

**两侧各自的「点亮格数」不变**（改动的是**标签**，不是**格子**）：

| | 原版点亮格（field/movegrid/grid16/banner） | 重制侧点亮格 |
|---|---|---|
| 修正前 | 192 / 192 / 175 / 0 | 192 / 192 / 192 / 0 |
| 修正后 | 192 / 192 / 175 / 0 | 192 / 192 / 192 / 0 |

⇒ **「同亮 192 / 缺 0 / 多画 0」在 `field` 与 `movegrid` 上达成**；
那 24/24 的「原版缺 + 多画」**是纯标签错位**，不是产品差异。

### 1.4 交叉验证

X2 的私有仪器 `tools/s49_x2_overlay/compare_families.py`（**独立实现**了同一口径），
在改完之后与共享仪器**逐项相同**（见 §2 的两张表）⇒ 结论不依赖单一实现。

---

## 2. 任务 A：那 2 格黄色光标格（**修完并给出四时刻的最终数字**）

### 2.1 产品规则（X2 已改，本流**只验证**）

`battle_range_ui_style.h` 的 `battle_range_ui_cell_kind()`：

```cpp
if(cursor_cell && ! move_phase)   // ← 移动阶段不画黄色光标格
{
    return battle_range_ui_tile_kind::cursor;
}
```

依据（原版自己的帧）：**移动阶段帧（movegrid）192 个点亮格 = solid 83 / edge 63 / hatch 46
—— 一个黄格都没有**；光标正落在出手单位自己的格，那一格在青色可达集里 ⇒ 移动阶段它是青的。
（与 **G-H15** 同源：橙与绿也不在移动阶段出现；见 `F-rule.md` §2、`X2-overlay-zero.md` §4。）

### 2.2 ⭐ ROM 上的复测（**X2 没交的那份最终数字**）

第一个含这条规则的 ROM 是 **`3f1e9caa…`**（`battle_range_ui_style.h` 改于 15:31:42，
ROM 构建于 15:35:56）。用它的 walk 重跑逐格族名对拍：

| 时刻 | 同亮 | 原版缺 | 多画 | 族名不一致（**修规则前**） | 族名不一致（**修规则后**） |
|---|---:|---:|---:|---:|---:|
| `field` | 192 | 0 | 0 | 61 | 61 |
| `movegrid` | 192 | 0 | 0 | **15** | **13** |
| `grid16` | 175 | 0 | 17 | 85 | 85 |
| `banner` | 0 | 0 | 0 | 0（逐格全等 ✔） | 0（逐格全等 ✔） |

**剔掉缓冲尾部后的「忠实口径」**（两侧同时剔）：

| 时刻 | 同亮 | 原版缺 | 多画 | 族名不一致（修规则前） | 族名不一致（**修规则后**） |
|---|---:|---:|---:|---:|---:|
| `field` | 168 | 0 | 0 | 50 | 50 |
| `movegrid` | 168 | 0 | 0 | **4** | **2** |
| `grid16` | 153 | 0 | 15 | 65 | 65 |
| `banner` | 0 | 0 | 0 | 0 | 0 |

### 2.3 ⭐ 最直接的证据：**移动阶段帧里一个黄格都没有了**

重制侧最优帧（`step-26-A`）的**非尾部**族直方图：

| ROM | 族直方图 |
|---|---|
| `b6c2a05f…`（修规则前） | `solid 72 / edge 52 / hatch 42 / **band 2**`（band = 黄） |
| `3f1e9caa…`（修规则后） | `solid 72 / edge 52 / **hatch 44**`（**band = 0**） |

⇒ **那 2 格黄色光标格变成了 2 格青色可达格**，别的族一个都没动。
⇒ `movegrid` 的族名不一致由 **15 → 13**（忠实口径 **4 → 2**），
且**减少的正好就是 `hatch → band` × 2**（旧 ROM 的 `movegrid` 差异对里
`hatch→band × 2` 消失，新 ROM 只剩 `hatch→solid × 2`）。

---

## 3. 任务 C：「原版缓冲尾部的陈旧内容」的性质 —— **可判定的证据**

### 3.1 尾部是哪里

原版的 BG2 覆盖层缓冲是 **256×256 px**，锚在地图像素 **(256, 0)**，地图宽 **480 px**
⇒ 缓冲覆盖 **地图 px 256..479（战斗列 8..14）** 与 **地图 px 0..31（战斗列 0，= 尾部）**，
**战斗列 1..7 根本不在缓冲里**。
（⇒ 原版的缓冲其实伸到了地图 px 511，**越过 480 px 的地图右边界 32 px**。）

### 3.2 ⭐ 判据（原版自己的不变量，可证伪）

原版自己的覆盖层规则（`F-rule.md` §1）加上两条硬约束：

* **I1**：`solid`（灰网点 = 受阻）**恰好**画在地形类别 ≠ plain 的格上；
* **I2**：可走但没高亮的格画格线 `edge`；
* **I3**：**高亮族**（`hatch` = 可达、`band` = 光标、`line_alt` = 攻击范围、`hatch_shift` = 合法目标）
  **绝不画在受阻格上** —— 光标不可能站在墙上，可达格按定义可走。

**用的地形是原版自己的碰撞网格**（`tools/s49_orig_map/battle-14-map-truth.json`，
从逆向线 `map-canvases-v1` 的清单抄出来的，**不依赖重制侧的地图**）。

### 3.3 ⭐ 实测结果（`tools/s49_y2_overlay/tail_residue.py`）

| 时刻 | 主区（战斗列 8..14）画了 / 违反 | **尾部（战斗列 0）画了 / 违反** |
|---|---|---|
| `field` | 521 / **1** | 77 / **47** |
| `movegrid` | 566 / **1** | 74 / **44** |
| `grid16` | 434 / 44 | 63 / **59** |
| `banner` | 0 / 0 | 1 / 1 |

* 主区的**唯一**一次违反在缓冲的角上：战斗格 **(14, 12)** 的 8 个 8×8 项里
  7 个是 `solid`，只有右下角那一项是 `edge`（**格线角**，不是「这一格可走」的断言）。
* 尾部则是**成片的违反**：29 / 38 / 35 个项是**墙格上的格线**（I1 违反），
  18 / 6 / 24 个项是**墙格上的高亮**（I3 违反）。

### 3.4 ⭐ 最硬的一条：**原版把黄色光标格画在墙上**

battle-14 的**第 0 列**在原版自己的碰撞网格里，**第 1..12 行全是 `15`（墙）**
（地图的边框）。而原版在尾部画的是：

| 时刻 | 黄色光标格的位置 | 该格的地图战斗格 | 原版地形类别 |
|---|---|---|---|
| `field` | 缓冲项 (29..31, 12..13) | **(0, 6)** | **15 = 墙** |
| `movegrid` | 缓冲项 (29, 12..13) | **(0, 6)** | **15 = 墙** |
| `grid16` | 缓冲项 (28..31, 12..13) | **(0, 6)** | **15 = 墙** |

⇒ **光标站在墙上** ⇒ 尾部**不是当前地图空间的内容** ⇒
**任何忠实的重制都复现不了它**（照抄也只会得到一个「站在墙上的光标」）。
（`grid16` 另外 4 个黄格在主区的战斗格 (14, 7)，也是墙 —— 但 `grid16` 本身就是
原版的**单帧瞬态**（F-rule §3.3：光标精灵已移走，地面真相是上一帧的残影），
所以那一格是**残影**，不是「当前地图空间的内容」。）

### 3.5 结论（**要写进 1:1 报告的「明确排除项」**）

> **明确排除项 —— 原版覆盖层缓冲的「回绕尾部」（地图第 0 列 / 战斗列 0）**
>
> 原版的 BG2 覆盖层缓冲是 256×256 px、锚在地图 px (256, 0)，地图宽 480 px，
> 所以缓冲的最后 32 px（战斗列 0）**落在地图右边界之外 / 落在一整列墙上**。
> 用**原版自己**的 battle-14 碰撞网格判定：那一列在第 1..12 行**全是墙（class 15）**，
> 而原版却在那里画了**黄色光标格**、**青色可达集**和**可走格线**，
> 违反了原版自己的覆盖层不变量（在主区 521 个画项里只违反 1 个格线角，
> 在尾部 74 个画项里违反 44 个）。
> ⇒ **尾部不是当前地图空间的内容，是原版把自己的（越界）绘制折回缓冲的残留，
> 任何忠实的重制都复现不了** ⇒ **逐格族名对拍时必须把尾部从两侧同时剔掉**，
> 否则那 11 / 22 格差异会被误判成产品差。

---

## 4. 逐格族名对拍的**最终数字** + **逐格性质判定**

### 4.1 四时刻最终数字（**产品 ROM `3f1e9caa…`**，整条 walk 口径）

| 时刻 | 同亮 | 原版缺 | 多画 | 族名不一致 | ⇒ 残差 |
|---|---:|---:|---:|---:|---:|
| `field` | **192** | **0** | **0** | 61 | 61 |
| `movegrid` | **192** | **0** | **0** | 13 | 13 |
| `grid16` | 175 | 0 | 17 | 85 | 102 |
| `banner` | 0 | 0 | 0 | 0（**逐格全等** ✔） | 0 |

> `grid16` 的残差 102 = **族名不一致 85** + **点亮/不点亮不一致 17**
> （原版那一帧只点亮 175 格：缓冲半刷新，第 1 行空、行 2..12 有内容，且整体下移一行）。

**剔掉尾部后的忠实口径**： `field` 168/0/0/50 · `movegrid` 168/0/0/**2** ·
`grid16` 153/0/15/65 · `banner` 0/0/0/0。

### 4.2 ⭐ 逐格性质判定（`tools/s49_y2_overlay/classify_mismatches.py`）

| 时刻 | 尾部残留（不可复现） | walk 相位 / 游戏状态 | **产品差** |
|---|---:|---:|---:|
| `field` | 11 | 50 | **0** |
| `movegrid` | 11 | 2（单位占位） | **0** |
| `grid16` | 22 | 80 | **0** |
| `banner` | 0 | 0 | **0** |

判定方法（**逐条可查**）：

* **尾部残留**：地图逻辑列 ∈ {0, 1}（= 战斗列 0，缓冲的尾部）⇒ §3 的证据。
* **walk 相位**：该时刻**在重制侧的 walk 里根本不存在**。判据 = **族集合**：
  原版 `field` 时刻同时画**青**（`hatch`）与**橙**（`line_alt`），
  而重制侧 35 帧里**没有任何一帧同现**（`step-26-A` 只有青；
  `step-29..34` 只有绿 + 橙）⇒ 50 格差异是**相位/游戏状态**，不是覆盖层规则。
  `grid16` 同理（原版那一帧是**半刷新的单帧瞬态**：第 1 行空、整体下移一行）。
* **单位占位**：`movegrid` 剩的 2 格（地图逻辑列 20/21、行 7 = 战斗格 10、行 7）——
  原版画**青**（可达），重制侧画**灰网点**（受阻）；该格在原版自己的碰撞网格里是
  **plain（class 0）**，所以重制侧的灰网点**只能来自「有单位站在那儿」**
  （重制侧把占位格也算受阻）⇒ **单位站位不同**（游戏状态），不是绘制规则。

⇒ **四时刻的产品差 = 0。** 剩下的每一格都有归属：
**不可复现的原版尾部残留** 或 **walk 的相位/游戏状态**。

---

## 5. 跑了哪些验证

| # | 命令 | 结果 |
|---|---|---|
| V1 | `python tools/s49_overlay_align/compare_overlay_families.py --vram-dir build/s49-package/evidence/overlay/vram`（**修仪器前**） | `field` 168/24/24/50 · `movegrid` 168/24/24/4 · `grid16` 153/22/39/65 · `banner` 0/0/0/0 |
| V2 | 同上（**修仪器后**） | `field` **192/0/0**/61 · `movegrid` **192/0/0**/15 · `grid16` 175/0/17/85 · `banner` 0/0/0/0 |
| V3 | `python tools/s49_x2_overlay/compare_families.py --vram-dir … [--exclude-tail]`（**独立实现**的交叉验证） | 与共享仪器**逐项相同**；剔尾部 `field` 168/0/0/50 · `movegrid` 168/0/0/2（新 ROM） |
| V4 | `python tools/s49_x2_overlay/compare_families.py --vram-dir build/s49-package-y4/evidence/overlay/vram`（**产品 ROM** 的 walk） | `movegrid` 族名不一致 **15 → 13**；`step-26-A` 族直方图 `band 2 → band 0` |
| V5 | `python tools/s49_y2_overlay/tail_residue.py`（**任务 C 的可判定证据**） | 主区违反 1 / 521、1 / 566；**尾部违反 47 / 44 / 59**；**光标在战斗格 (0,6) = 墙** |
| V6 | `python tools/s49_y2_overlay/classify_mismatches.py --vram-dir …`（产品 ROM） | 四时刻 **product-diff = 0**；逐格性质判定见 §4.2 |
| V7 | `python tools/s49_fidelity_report.py --out …/bench-baseline-rom/report.json --remake-rom …/rom-baseline-b6c2a05f.gba --ratchet build/s49-package/baseline/baseline-report.json` | **判定台没崩**（exit 0）；**同 ROM** 棘轮 **PASS**；残差 **100,210 / 中位 1,323 / 全 0 帧 5** |
| V8 | `python tools/s49_fidelity_report.py --out …/bench-product-rom/report.json --remake-rom …/rom-product-3f1e9caa.gba --ratchet …` | exit 0；残差 **100,210 / 中位 1,323 / 全 0 帧 5**（与基线**逐项相同**）；棘轮 PASS（**但 ROM 与基线不同 ⇒ 工具自己标注为 void**） |
| V9 | `wsl … build/run-baseline-tests.sh`（HEAD 基线） | **pass=101 / fail=20**，失败名单见 §5.2 |
| V10 | `wsl … build/w1-run-all-tests.sh`（工作区） | **pass=118 / fail=20**，失败名单与基线**逐名相同** ⇒ **新红 0** |
| V11 | `wsl … g++ … test_battle_range_ui_phase_truth_table.cpp`（新单测） | **PASS** |

### 5.1 ⭐ 判定台残差（**同 ROM**）

| 读数 | 重制侧 ROM sha256 | 残差总和 | 中位 | 全 0 帧 | 归因（一致/产品差/配对差） |
|---|---|---:|---:|---:|---|
| **HEAD 基线**（`build/s49-package/baseline/baseline-report.json`） | `b6c2a05fa50e28613ec8ab35de5306ef635819ab87917756537b248ba061c2cb` | **100,210** | **1,323** | **5**/25 | 5 / 17 / 3 |
| **本流，同 ROM**（V7，**修仪器后**） | `b6c2a05fa50e28613ec8ab35de5306ef635819ab87917756537b248ba061c2cb` | **100,210** | **1,323** | **5**/25 | 5 / 17 / 3 |
| **本流，产品 ROM**（V8） | `3f1e9caa11805b5e53bc053f2840d0a5d8f94d33f53956554675c8c305ccdde3` | **100,210** | **1,323** | **5**/25 | 5 / 17 / 3 |

**残差没有变大** ✔（两处都是 **100,210 / 1,323 / 5**，与基线逐项相同）。

⭐ **「仪器改动会不会影响判定台」已查实**：
判定台 `tools/s49_fidelity_report/overlay.py` 只 import 共享仪器的
`find_overlay_map` / `remake_family` / `LOGICAL_COLS` / `LOGICAL_ROWS`，
**不 import `original_map_cells`**（它有自己的一套实现）。
⇒ V7 的读数与 HEAD 基线的报告**逐字段相同**（25 帧全同、summary 全同），
**唯一**的差别是 `captures.remake.rom` 这个**路径**字符串
（所以 `content_sha256` 必然不同：`c25bc555…` vs 基线的 `d389d289…`）。
⇒ **仪器改动对判定台是测量中性的**。

⚠️ **同 ROM 的诚实说明**：基线的 100,210 是在 ROM `b6c2a05f…` 上测的。
**V7 用的就是同一个 ROM** ⇒ 那是**有效**的棘轮比较。
V8 用的是产品 ROM `3f1e9caa…` ⇒ **跨 ROM**，按 W4 的结论**不能**当作棘轮证据
（工具自己也打印了 void 提示）；它只说明**产品 ROM 上的读数同样是 100,210 / 1,323 / 5**。
⇒ **父代理在最终 ROM（Y1+Y2+Y3 合并后重建）定稿时，必须再在那个 ROM 上连读 3 次**，
才能给出有效的棘轮结论。

### 5.2 单测棘轮

| 树 | 通过 | 失败 | 失败集合 |
|---|---:|---:|---|
| HEAD 基线（`build/run-baseline-tests.sh`） | 101 | **20** | 见下 |
| 工作区（`build/w1-run-all-tests.sh`） | **118** | **20** | **与基线逐名相同** ⇒ **新红 0** ✔ |

（失败集合用 `Compare-Object` 逐名比对过：**20 vs 20，完全一致**，
连 `FAIL(compile)` 与 `FAIL(run)` 的分布也一致 ——
`test_battle_campaign_save` 与 `test_battle_runtime_scene_gate` 两边都是**编译期**红
（`sizeof(battle_scene_snapshot<12>) <= 1120` 的静态断言：1672 > 1120）。
工作区比 HEAD 基线多 17 个通过项 = wave 10..13 新增的测试文件都在工作区里；
本流新增的 `test_battle_range_ui_phase_truth_table` 是其中之一，**单独跑 PASS**。）

失败名单（两侧完全一致，20 项预存债）：

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

（工作区比基线多 1 个通过项 = 本流新增的 `test_battle_range_ui_phase_truth_table`。）

---

## 6. 新单测：`test_battle_range_ui_phase_truth_table.cpp`

**为什么还要加一个**：被推翻过两轮的那条规则（移动阶段光标格 = 橙 / = 黄）
**通过了当时所有的采样断言** —— 采样只能证明**一格**，
而原版自己的帧证明的是**一个相位**。所以新单测断言的是**相位性质**，不是单格：

* **移动阶段**：结果**绝不**是 `cursor` / `target` / `attack_range`；
  `move` ⟺ 可达，否则 `blocked` / `grid`。
* **非移动阶段**：结果**绝不**是 `move`；优先级 `cursor > target > attack_range > blocked > grid`。
* **完整真值表**：6 个布尔输入的 **2⁶ = 64** 种组合**全部**走一遍。

依据：原版**移动阶段帧** 192 个点亮格 = `solid 83 / edge 63 / hatch 46`（**零黄、零绿、零橙**）
与**目标选择帧零青**（`F-rule.md` §2、G-H15、X2-H4）。

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Y2-H1 | W2 的「terrain grid 19×19 vs MAP_WIDTH 15 列」是错的，地形网格是 15×19 | 读 `generated_battle_map_content.h` 的 battle-14 定义 + 实跑 `remake_terrain()` + 原版 map-14 画布 | 15 列 × 19 行 = 480×304 px，三方一致 | **已证伪**（沿用 X2-H1） |
| Y2-H2 | 24 格「原版缺」+ 24 格「多画」是**仪器给两侧贴了不同的地图标签** | 读共享仪器 `original_map_cells()`（无回绕）vs `remake_logical_cells()`（`% MAP_WIDTH`）；补回绕后复跑 35 个 dump | 补回绕后 `field`/`movegrid` **同亮 192 / 缺 0 / 多画 0** | **已确认**（本流落地） |
| Y2-H3 | X2 改的「移动阶段不画黄色光标格」规则在 ROM 上真的把那 2 格黄格变成青格 | 在第一个含该规则的 ROM（`3f1e9caa…`）上重录 walk，比 `step-26-A` 的族直方图 | `band 2 → band 0`、`hatch 42 → 44`；`movegrid` 族名不一致 **15 → 13**（忠实口径 **4 → 2**） | **已确认**（X2 的 X2-H8 从「未验」升为已确认） |
| Y2-H4 | 原版缓冲的尾部**不是**当前地图空间的内容 | 用**原版自己的** battle-14 碰撞网格查原版自己的覆盖层不变量（`solid` ⟺ 类别 ≠ plain；高亮族绝不画在受阻格上），主区与尾部分开统计 | 主区违反 1/521、1/566（还只是一个格线角）；**尾部违反 47、44、59**；**黄色光标格画在战斗格 (0,6)，而那一列在原版地图里十二行全是墙** | **已确认**（可判定） |
| Y2-H5 | 剩余的族名不一致里**没有**产品差 | 逐格分类：尾部 / 相位不可达（族集合判据）/ 单位占位（地形 plain 却画 solid）/ 其余 | 四时刻 **product-diff = 0** | **已确认** |
| Y2-H6 | 仪器改动不会影响判定台的读数 | 判定台只 import `find_overlay_map` / `remake_family`；同 ROM 复跑一次并逐字段 diff | 25 帧与 summary **逐字段相同**，唯一差别是 ROM 的**路径**字符串 | **已确认** |
| Y2-H7 | 「同亮 192 / 缺 0 / 多画 0」在 Y2 权限内可达 | 补回绕后逐时刻读数 | `field` 192/0/0 ✔、`movegrid` 192/0/0 ✔、`banner` 逐格全等 ✔；`grid16` 175/0/17（原版的单帧瞬态） | **部分确认**（`grid16` 见 §8） |
| Y2-H8 | 判定台残差不会变大 | 同 ROM（`b6c2a05f…`）复跑 + 产品 ROM（`3f1e9caa…`）复跑 | 两处都是 **100,210 / 1,323 / 5**，与基线逐项相同 | **已确认**（同 ROM 有效；跨 ROM 已标注） |

---

## 8. 没达成的 / 剩余风险（**不粉饰**）

1. **`grid16` 不是 192/0/0**：原版那一帧是**单帧瞬态**（缓冲半刷新：第 1 行空、
   行 2..12 有内容，且整体比 `field` 下移一行）⇒ 它只点亮 **175** 格，
   重制侧是 192 ⇒ 多画 17。这是**原版的瞬态**，不是产品差（该帧在重制侧 walk 里不存在）。
2. **`movegrid` 剩 2 格是**单位站位**：原版战斗格 (10, 7) 可达，重制侧那一格被一个
   单位占着 ⇒ 画成受阻。**改点在 `battle_scene_controller.h`（Y1 独占）**
   `_refresh_overlay_cache()` 把占位格写进 `_blocked_overlay_rows` 的那段。
   ⛔ 本流无权改，也不该改（那是**游戏状态**，不是覆盖层规则）。
3. **`field` 剩 50 格是**相位**：原版 `field` 是**青 + 橙同现**的稳定态，
   重制侧 35 帧里**没有任何一帧**同现 ⇒ 需要 Y1 的闭环驱动走到那个相位。
4. **判定台棘轮目前只有「同 ROM」那一次有效**（V7）。
   产品 ROM `3f1e9caa…` 的读数与基线逐项相同，但那是**跨 ROM**比较；
   **父代理必须在最终 ROM 上连读 3 次**才能给出有效的棘轮结论。
5. **本机构建非字节可复现** ⇒ 我钉的是**字节副本**
   （`build/s49-y2/rom-product-3f1e9caa.gba` / `rom-baseline-b6c2a05f.gba`），
   报告里给的 sha 就是这两个文件的 sha。
   ⚠️ **交回时盘上的 ROM 已经被 Y1 重建过**（`2c2b48d9…`，
   `battle_scene_presentation_event.h` 于 16:08 被 Y1 改过）⇒
   **本流的每一个数字都对应上面那两个钉住的字节**，不是现在盘上的那个 ROM；
   父代理在最终 ROM 上必须**重跑**逐格族名对拍与判定台。
6. **尾部到底折回哪里，本流只判定了「不可复现」，没有判定它的来源**：
   可判定的是「它违反原版自己的不变量」；至于原版为什么把越界的绘制折回缓冲
   （缓冲 256 px vs 地图 480 px 的模运算），那是逆向线的问题，本流未查。

---

## 9. 接线点清单（**本流不需要改 `battle_runtime_scene.cpp`**）

| # | 位置 | 内容 |
|---|---|---|
| 1 | `battle_runtime_scene.cpp` | ⛔ **本流不需要改**。产品规则全在 `battle_range_ui_style.h` 里，调用点已经把 `move`（= `phase == move_selection`）作为第一个参数传进去 ⇒ 只需重建 ROM。 |
| 2 | `battle_scene_controller.h`（Y1 独占） | `movegrid` 剩的 2 格 `hatch → solid`：**单位占位格也被算成受阻**。若要与原版对齐，改 `_refresh_overlay_cache()` 里把占位格写进 `_blocked_overlay_rows` 的那段（X2 §8.3 给的行号：`battle_scene_controller.h:2457-2474`）。 |
| 3 | `tools/s49_overlay_align/compare_overlay_families.py` | **已改**：原版侧补 480 px 回绕（§1.2）。判定台不 import 这个函数 ⇒ 判定台读数不变（§5.1）。 |
| 4 | 1:1 报告（Y4 独占） | **「明确排除项」** 段落照抄 §3.5。 |

---

## 10. 改动的文件（完整绝对路径）

### 共享仪器（**任务书授权**）

| 文件 | 改动 |
|---|---|
| `D:\Github\gba-naruto\tools\s49_overlay_align\compare_overlay_families.py` | `original_map_cells()`：原版侧贴地图标签**按 480 px 回绕**（一行）+ 函数 docstring 与模块 docstring 补依据 |

### 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel\`）

| 文件 | 改动 |
|---|---|
| `game\tests\test_battle_range_ui_phase_truth_table.cpp` | **新**：移动阶段 / 非移动阶段的**相位性质**断言 + **2⁶ = 64** 完整真值表 |

### 主仓（`D:\Github\gba-naruto\`）

| 文件 | 改动 |
|---|---|
| `tools\s49_y2_overlay\tail_residue.py` | **新**：尾部残留的**可判定证据**（用原版自己的碰撞网格查原版自己的不变量） |
| `tools\s49_y2_overlay\classify_mismatches.py` | **新**：逐格族名不一致的**性质判定**（尾部残留 / walk 相位 / 单位占位 / 产品差） |
| `notes\s49-fidelity\Y2-overlay-final.md` | 本文件 |

**未改**：`game\src\battle_runtime_scene.cpp`、`game\include\konoha\battle_scene_controller.h`、
`game\include\konoha\battle_scene_presentation_event.h`、
`game\include\konoha\battle_range_ui_style.h`（X2 已改，本流只验证）、
`game\include\konoha\battle_map_content.h`、`game\include\konoha\grid_pathfinder.h`、
`game\include\konoha\battle_black_field*.h`、`graphics\`、逆向线 `D:\Shell\gba-naruto-reverse`。
**未提交 git**；**新文件一律 LF、无 BOM**。
