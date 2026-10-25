# W3 流 —— 覆盖层逐格族名归零 + 对话框斜切展开的碎片规格

> 2026-10-24 · wave 8 · stream W3
> 独占改动：`battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h` /
> `battle_presentation_content.h` + 2 个新单元测试
> 新仪器：`D:\Github\gba-naruto\tools\s49_w3_dialogue\`（5 个探针）
> ⛔ **未改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h`（W1 独占）、
> `battle_black_field*.h` / `battle_opening_title.h`（W1/W2 独占）
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` 全程只读；⛔ **未提交 git**

---

## 0. 一句话结论

> **任务 B 的前提被实测推翻了：所谓「斜切展开的碎片」根本不是碎片，而是
> 一个四角星光窗口（就是 Z2 的星光圈）在继续长大 —— 原版的入场转场一共
> **37 级**（每级 2 帧 + 18 帧全黑），而重制侧的星光素材只有 **25 级**，
> **缺了 12 级（帧 1079–1102）**，那 12 级正是对话框「斜切展开」的真相。**
>
> **碎片规格（实测）：32×32 的碎片方案每级要 464 块 OBJ 图块 ⇒ 装不进战斗画面的
> 336 块余量；16×16 碎片 + 64×64 纯黑块的方案每级峰值 **224 块 / 87 个精灵**
> ⇒ 装得下（余 112 块）。这就是与 W2 共用的那份预算表。**
>
> **任务 A：纯逻辑侧改了三处规则**（绿只在目标阶段画 / 受阻集 = 地形类别 ≠ plain /
> 绘制范围 = 地图行 1..12），**接线点清单在 §6**，接线前可单测的部分已全部单测。

---

## 1. 任务 A —— 覆盖层逐格族名归零（纯逻辑侧）

### 1.1 基线与目标（Y3 修好仪器后的真数字，勿重查）

| 时刻 | 同亮 | 原版缺 | 多画 | 族名不一致 |
|---|---:|---:|---:|---:|
| field | 81 | 111 | 59 | **26** |
| movegrid | 81 | 111 | 59 | **10** |
| grid16 | 71 | 104 | 69 | **31** |
| banner | 0 | 0 | **117** | 0 |

目标：**同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0**。

`movegrid` 的 157 格差异成分（Y3 `diff_breakdown.py` 实测）：
`original_only 111`（相机锚点差 32 px）+ `extent 36`（绘制范围）+ `blocked 7`（受阻集）+
`highlight 3`（相位）。⇒ **三处成因，三处规则**，本流把其中**两条规则写成纯逻辑**。

### 1.2 改动 1 —— 绿色（合法目标）只在目标阶段画（G-H15）

`battle_range_ui_style.h::battle_range_ui_cell_kind()`

**原代码**：`if(legal_target) return target;`（不看阶段）
**新代码**：`if(legal_target && ! move_phase) return target;`

依据（**不是推的，是实机帧定的**）：
* 原版**目标选择帧**：1024 个 BG2 项 = edge 291 / blank 173 / line_alt 32 /
  **hatch_shift 8 / hatch 0** ⇒ 目标阶段**画绿压橙、完全不画青**；
* 原版**移动阶段帧**：**一格绿都没有**。

⇒ 原版的「移动集」和「目标集」**从不同时出现在屏幕上**。
⇒ 重制侧原来在移动阶段就画目标集 ⇒ 与原版相反。
（`notes/s49-fidelity/W1-integration.md` §5 用原版自己的目标选择存档态抓帧定论 G-H15。）

⚠️ **这是唯一一条能单测、且接线后直接命中的规则**：
接线前 `legal_target` 与 `move_phase` 同时为真的格子，重制侧画绿（`hatch_shift`），
原版画青（`hatch`）⇒ **族名不一致**；改完后画青 ⇒ 族名一致。

### 1.3 改动 2 —— 受阻集 = 地形类别 ≠ plain

* `grid_pathfinder.h`：新增 `grid_map<W,H>::overlay_blocked(grid_point)`
  （`terrain_class(value) != grid_terrain_class_plain`）。
* `battle_map_content.h`：新增 `battle_map_terrain_class_plain` 与
  `battle_map_cell::overlay_blocked()`。
* `battle_range_ui_style.h`：新增 `battle_range_ui_overlay_blocked(terrain_class)`
  与 `battle_range_ui_plain_terrain_class`。

依据：原版的灰网点（`solid` 族）= **地形类别 ≠ plain**（类 1 河 / 3 地面斑块 /
7 岩石 / 15 墙全挡），在锚点 (256,0) 下**逐像素 17984/17984 命中**。
⚠️ **不是** `terrain.cost() == 0`（那只等于墙类 15）—— 该读法被 4 个既有单测证伪
（Y3 台账 H6），本流**没有**改 `cost()` 的语义。

### 1.4 改动 3 —— 绘制范围 = 地图行 1..12 + 地图空间锚点 (256, 0)

`battle_range_ui_style.h` 新增：

```cpp
inline constexpr int battle_range_ui_overlay_buffer_width = 256;
inline constexpr int battle_range_ui_overlay_buffer_height = 256;
inline constexpr int battle_range_ui_overlay_map_anchor_x = 256;
inline constexpr int battle_range_ui_overlay_map_anchor_y = 0;
inline constexpr int battle_range_ui_overlay_first_map_row = 1;
inline constexpr int battle_range_ui_overlay_last_map_row = 12;
inline constexpr int battle_range_ui_overlay_map_row_height = 16;

[[nodiscard]] constexpr bool
battle_range_ui_overlay_row_visible(int map_row);
```

依据：原版缓冲**逐行**解码 ⇒ 行 0 与 13..15 **全空**，只画行 1..12
（Y3 台账 H10）。重制侧画满 16 行 ⇒ **36 格「多画」**。
行高 16 px ⇒ 是**逻辑行**，不是战斗行。

锚点：原版缓冲的像素 (0,0) = **地图像素 (256, 0)**；重制侧最优匹配窗口是 (224, 0)
⇒ **相机差 32 px（1 个战斗格）**。这是「原版缺 111 格」的主因，
**接���点在 `battle_runtime_scene.cpp` 的相机处**（§6 W3.3）。

### 1.5 断言（接线前能覆盖的全部）

新单测 `game/tests/test_battle_range_ui_overlay_rules.cpp`：

| 断言 | 覆盖面 |
|---|---|
| `battle_range_ui_overlay_row_visible(0) == false`、`(1)/(12) == true`、`(13)/(15) == false` | 绘制范围（36 格多画） |
| 锚点常量 == (256, 0) | 相机锚点（111 格原版缺） |
| `battle_range_ui_overlay_blocked(0) == false`、`(1/3/7/15) == true` | 受阻集（7 格） |
| `battle_map_cell::overlay_blocked()`（raw 0/1/7/15/16） | 受阻集（另一条数据源） |
| `grid_map::overlay_blocked()`（plain/1/3/7/15 + 越界） | 受阻集（越界 = 受阻） |
| `battle_range_ui_cell_kind(true, …, legal_target=true)` **≠ target** | G-H15（族名不一致） |
| `battle_range_ui_cell_kind(false, …, legal_target=true)` **== target**（压过橙） | G-H15 |
| `battle_range_ui_cell_kind(true/false, …, blocked=true)` **== blocked** | 受阻格在两个阶段都画 |

既有 `test_battle_range_ui_style.cpp` 的 12 条断言**逐条未受影响**
（其中没有任何一条同时置 `move_phase=true` 与 `legal_target=true`）。

---

## 2. 任务 B —— 对话框「斜切展开」的碎片规格

### 2.1 ⭐ 实测结论：那不是碎片，是星光圈在继续长大

Z3 的结论（「纯黑遮罩在已画完的场景上被斜切擦掉 ⇒ 遮罩来自 OBJ ⇒ 需要碎片素材 + 运行期摆放」）
**在「遮罩来自 OBJ」这一半上是对的，在「碎片」这一半上不对**。

本流用原版**每帧一采**的 1881 张帧
（`build/s49-blackfade/original-entry-v2/frames`，Z2 的采集）重测了整屏遮罩：

* 遮罩 = 屏幕上的黑；用 `star_geometry.py` 的**洪泛法**把与屏幕边界相连的黑区
  挖掉，剩下的就是**可见窗口**；
* 逐帧量可见窗口的面积 ⇒ 折叠成**级**（面积相同的一串帧为一级）。

**测得的入场转场（每级 2 帧，全黑保持 18 帧）：**

| 帧 | 级 | 可见面积 | 是什么 |
|---|---:|---:|---|
| 1013–1036 | 0–11 | 7925 → 17 | 星光圈**缩小**（12 级） |
| 1037–1054 | 12 | 0 | **全黑保持 18 帧** |
| 1055–1078 | 13–24 | 21 → 7200 | 星光圈**长回来**（12 级） |
| **1079–1102** | **25–36** | **10624 → 32630** | **⭐ 再长 12 级：四根臂伸到屏幕四角** |

* 前 25 级的面积与 `battle_black_field_star::visible_pixels`
  **逐项相同**（7925, 6561, 4677, 3705, 2109, 1477, 917, 681, 305, 173, 77, 17, 0,
  21, 81, 161, 280, 590, 744, 1147, 1703, 2844, 3980, 5561, 7200）⇒ **Z2 的模型是对的**。
* ⭐ **但原版还有 12 级，Z2 的素材没有**（25 级 vs 37 级）。
  那 12 级就是任务书里说的「斜切展开」：**星光圈的四根臂继续伸长**，
  边缘是**直斜线**（Z3 §3.1(c) 的观察），最后一级可见面积 32630 ≈ 全屏。

**可复算的证据**：

```
tools/s49_w3_dialogue/entry_levels.py       → build/s49_w3_dialogue/entry-levels.json
tools/s49_w3_dialogue/visible_area.py        → 逐帧可见面积（与上表逐项吻合）
tools/s49_w3_dialogue/render_mask_sheet.py   → build/s49_w3_dialogue/mask_sheet.png（16 帧接触印相）
```

`mask_sheet.png` 的目视结果与上表一致：0259–0264 是小星光，
0265–0273 是臂伸长，0274 全可见。

### 2.2 ⭐ 碎片规格（实测块数）

GBA 精灵最大 64×64 px，OAM 只有 128 个精灵 ⇒ 遮罩只能是**碎片网格**。
本流对 37 级**逐级**量了三种碎片粒度（`shard_plan.py` / `overlay_obj_cost.py`）：

| 碎片粒度 | 每级碎片数 | 每级精灵数 | **每级 OBJ 图块峰值** | 装得进 336 吗 |
|---|---:|---:|---:|---|
| 8×8 | 600 | 600 | 84 | ✗ 精灵爆 OAM |
| 16×16 | 150 | ≤ **87** | **224** | ✅ **余 112 块** |
| 32×32（Z2 现方案） | 40 | 40 | **464** | ❌ 差 128 块 |
| 64×64 | 12 | ≤ 12 | 832 | ❌ 差 496 块 |

**⇒ 碎片规格（结论）：**

* **碎片 = 16×16 px**（网格 15 列 × 10 行 = 150 格）；
* 每一级分两类碎片：
  * **边缘碎片**（被星光臂切开的那几格）：每格要**自己的一组 4 块图块**；
  * **实心碎片**（整格全黑）：**所有实心格共用同一组 4 块图块**，
    并且 **16 个实心 16px 格可以合并成 1 个 64×64 的纯黑精灵**（共 64 块图块）；
* **每级精灵数 = 边缘碎片数 + ⌈实心 16px 格数 / 16⌉** ⇒ 峰值 **87**（OAM 128 ✅）；
* **每级 OBJ 图块 = 4 × (不同边缘形状数 + 1)** ⇒ 峰值 **224**（336 ✅）。

**实测峰值出现在第 35 级（帧 1085，可见面积 16007）**：
55 种不同的边缘形状 ⇒ 56×4 = 224 块图块，76 个精灵。

### 2.3 ⭐ 与 W2 共用的 OBJ 预算表

| 项 | OBJ 图块 | 精灵 | 备注 |
|---|---:|---:|---|
| 战斗画面余量（Butano 分配器 `free_tiles_count`，Z2 实测） | **336** | — | 不是高水位 |
| Z2 现方案（32×32 碎片，25 级素材） | 640 | 40 | **装不下** |
| 本流测得的 32×32 碎片真实峰值 | 464 | 40 | **仍装不下** |
| **本流测得的 16×16 碎片方案** | **224** | **87** | ✅ **余 112 块** |

**⇒ 预算表（两份共用，已写进 `battle_presentation_content.h`）：**

```cpp
inline constexpr int battle_transition_battle_scene_free_obj_tiles = 336;
inline constexpr int battle_transition_overlay_peak_obj_tiles = 224;
inline constexpr int battle_transition_overlay_peak_sprites = 87;
inline constexpr int battle_transition_overlay_spare_obj_tiles = 112;
inline constexpr int battle_transition_oam_sprite_limit = 128;
```

**⭐ 关键结论（给 W2 / W1）：**

> **星光圈的淡出、全黑保持、淡入，以及对话框的「斜切展开」，是同一个连续事件，
> 不是两个效果。** 所以它们**不能各占一份预算**，
> 必须由**同一套遮罩**画完 37 级。
>
> ⇒ W2 的 32×32 碎片素材（640 块/级）**必须改成 16×16 碎片 + 64×64 纯黑块**
> （224 块/级），否则第二个黑场装不下。
> ⇒ **本流给 W2 的资产侧建议**：`battle_black_field_star.h` 的
> `tiles_per_level = 640` 应改为 **224**（16px 碎片方案），
> `blocks = 40`（32×32 网格）应改为 **150 格 + 12 个 64×64 纯黑块**。
> ⇒ **12 个缺失的级（帧 1079–1102）要补进素材**，否则最后 24 帧对不上原版。

### 2.4 顺带核验：Z3 的 48 行遮罩表是对的

本流用独立实现（`diff_shipped_mask_table.py`）从原版捕获帧**重算**了 Z3 写进
`battle_presentation_content.h` 的 48 行表（16 步 × 3 行）：

```
fresh entries: 48  shipped entries: 48
differing entries: 0
```

⇒ **Z3 那张表逐项可复现，没有错**（本流一度怀疑它有错，重测后证伪，H12）。

---

## 3. 跑了哪些验证

| # | 验证 | 命令 / 方法 | 结果 |
|---|---|---|---|
| V1 | 整屏遮罩的逐帧测量（自建仪器） | `tools/s49_w3_dialogue/measure_full_mask.py --src build/s49-pairing/walk5/dense-original` | 0262→31188、0267→10213、0270→1948、0274→0，**与 Z3 的逐帧残差表逐项相同** ⇒ 仪器可信 |
| V2 | 可见面积逐帧曲线 | `tools/s49_w3_dialogue/visible_area.py` | 0250→3705、0254..0258→0、0264→7177、0274→32891 |
| V3 | **入场转场的级表** | `tools/s49_w3_dialogue/entry_levels.py --frames build/s49-blackfade/original-entry-v2/frames` | **37 级**（12 缩 + 18 帧黑 + 24 长），前 25 级与 Z2 的 `visible_pixels` **逐项相同** |
| V4 | 遮罩形状目视 | `tools/s49_w3_dialogue/render_mask_sheet.py` | `build/s49_w3_dialogue/mask_sheet.png`：四角星光臂伸长，**不是碎片** |
| V5 | **碎片粒度 × OBJ 成本（逐级）** | `tools/s49_w3_dialogue/shard_plan.py` + `overlay_obj_cost.py` | 32px 峰值 **464 块**；16px 峰值 **224 块 / 87 精灵**；64px 峰值 832 块 |
| V6 | Z3 的 48 行表复算 | `tools/s49_w3_dialogue/diff_shipped_mask_table.py` | **differing entries: 0** |
| V7 | **新单测（覆盖层规则）** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w3-run-new-tests.sh` | `test_battle_range_ui_overlay_rules` **PASS** |
| V8 | **新单测（转场预算表）** | 同上 | `test_battle_transition_overlay_budget` **PASS** |
| V9 | **单测棘轮（工作区）** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh` | **pass=111 fail=20** |
| V10 | **单测棘轮（HEAD 基线）** | `wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh` | **pass=101 fail=20** |
| V11 | **棘轮逐名比对** | 两个失败集合求差 | baseline 20 / workspace 20；**只在 baseline 里的 = 0，只在工作区里的（新增红）= 0** ⇒ **棘轮 PASS** |
| V12 | **改过的 4 个头文件在真机工具链下编译** | `build/w3-compile-header-probe.sh`（用 butano 自己的 ARM 编译行，只编译不链接） | **compile exit=0**（只有 `battle_range_ui_tile_index` / `battle_range_ui_pixel_index` 两个**既有** switch 的 `-Wswitch-default` 警告，与本流无关） |

### 3.1 单测棘轮

```
HEAD 基线    : pass=101 fail=20
工作区       : pass=111 fail=20
只在基线里红 : 0
只在工作区红 : 0      ← 「新增红」= 0 ⇒ 棘轮 PASS
```

20 项失败与 `notes/s49-fidelity/Q-unit-test-baseline.md` 的名单**逐名相同**
（`test_battle_all_scenario_runtime` / `test_battle_campaign_route` /
`test_battle_campaign_save` / `test_battle_campaign_scenario_42..49` /
`test_battle_dynamic_deployment_turn` / `test_battle_material_pickups` /
`test_battle_presentation_controller` / `test_battle_runtime_scene_gate` /
`test_battle_s49_input_flow` / `test_battle_s49_opening` /
`test_battle_scene_character_actions` / `test_battle_scene_controller` /
`test_battle_scene_multi_unit` / `test_battle_scene_results`）。

### 3.2 ⚠️ 诚实交代：`battle_runtime_scene.cpp` **当前编译不过**（不是本流造成）

用 butano 自己的编译行单独编译这个 TU，**12 个错误全部**在
`battle_runtime_scene.cpp:7199 / 7254–7258 / 7481` —— 那是 **W1 在途的
`battle_opening_title_view`**（`bn::sprite_ptr` 没有默认构造函数、没有
`reset()` 成员）。**没有一条错误提到本流改过的任何一个头文件**
（`battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h` /
`battle_presentation_content.h`），V12 的头文件探针也是 **exit=0**。

⇒ **这是树上的既有状态（W1 的在途改动），不是 W3 的回归。**
⇒ 请父代理/ W1 收口 `battle_opening_title` 的接线后重跑 ROM 构建。

⚠️ 本流**故意没有跑完整 ROM 构建**：那会触发任务书记载的
「并发构建互相覆盖 ⇒ `objcopy: Invalid argument`」竞态，
而本流只改了头文件、不需要出包。

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| W3-H1 | 「多画 36 格」的成因是绘制范围（地图行 1..12），不是几何粒度 | 逐行解码原版缓冲 + 与重制侧绘制范围逐行比 | 行 0 与 13..15 全空，行 1..12 有内容 | **已确认**（Y3 H10 复核） |
| W3-H2 | 受阻集 = 地形类别 ≠ plain | 锚点 (256,0) 下把原版 solid 像素落回地图格 | (15,7,1,3) → 17984/17984 px | **已确认**（Y3 H2/H3 复核） |
| W3-H3 | 地图空间锚点 = map px (256, 0) | 唯一使受阻集逐像素吻合的偏移 | (256,0)，17984/17984 | **已确认**（Y3 H2） |
| W3-H4 | 重制侧在移动阶段画了目标集（G-H15） | 原版目标选择帧的族直方图 | 目标帧 hatch=0 / hatch_shift=8；移动帧无绿 | **已确认**（W1 §5） |
| W3-H5 | `battle_range_ui_cell_kind` 原有 12 条断言里有「移动阶段画绿」的用例 | 读既有单测 | **没有** ⇒ 改规则不会让既有绿测变红 | **已确认** |
| W3-H6 | 对话框的「斜切展开」是**碎片**（碎片素材 + 运行期摆放） | 逐帧洪泛量可见窗口 + 接触印相目视 | 是**四角星光窗口**在继续长大，边缘是直斜线；**不是碎片** | **已证伪**（本流） |
| W3-H7 | 原版的入场转场只有 Z2 模型的 25 级 | 逐帧可见面积折叠成级 | **37 级**：多出 12 级（帧 1079–1102） | **已证伪**（Z2 的模型不完整） |
| W3-H8 | 32×32 碎片（Z2 现方案）是唯一可行粒度 | 逐级量 8/16/32/64px 四种粒度的精灵数与图块数 | 32px 峰值 **464 > 336** ✗；**16px 峰值 224 ✅** | **已证伪**（32px 装不下） |
| W3-H9 | 16×16 碎片 + 64×64 纯黑块的精灵数会爆 OAM(128) | 逐级算精灵数 | 峰值 **87** ≤ 128 ✅ | **已证伪**（不爆） |
| W3-H10 | Z3 写进头文件的 48 行遮罩表有错（行 103 的 `[4,240]` 可疑） | 用独立实现从原版捕获帧重算 48 行 | **differing entries: 0** | **已证伪**（表是对的） |
| W3-H11 | 整屏遮罩与 Z3 的逐帧残差表口径一致 | 自建仪器测 0262/0267/0270/0274 | 31188 / 10213 / 1948 / 0，**与 Z3 逐项相同** | **已确认**（仪器可信） |
| W3-H12 | 「多画 111 格」全是相机锚点造成的 | 重制侧最优窗口 (224,0) vs 原版 (256,0) | 差 32 px = 1 个战斗列 | **已确认**（Y3 §7.3） |

---

## 5. 改动的文件（完整绝对路径）

### 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel\`）

| 文件 | 改动 |
|---|---|
| `game\include\konoha\battle_range_ui_style.h` | ① 绿色只在目标阶段画（G-H15）；② 新增绘制范围 / 锚点 / 受阻集常量与 `battle_range_ui_overlay_row_visible()` / `battle_range_ui_overlay_blocked()`；③ 新增 `battle_range_ui_logical_cell_height` |
| `game\include\konoha\grid_pathfinder.h` | 新增 `grid_map<W,H>::overlay_blocked(grid_point)`（类别 ≠ plain） |
| `game\include\konoha\battle_map_content.h` | 新增 `battle_map_terrain_class_plain` 与 `battle_map_cell::overlay_blocked()` |
| `game\include\konoha\battle_presentation_content.h` | 新增**入场转场的 37 级级表**、**每级 OBJ 成本表**、**碎片规格常量**、**与 W2 共用的预算表** |
| `game\tests\test_battle_range_ui_overlay_rules.cpp` | **新**：覆盖层规则的 20 余条断言 |
| `game\tests\test_battle_transition_overlay_budget.cpp` | **新**：转场级表与预算表的断言 |

### 主仓（`D:\Github\gba-naruto\`）

| 文件 | 改动 |
|---|---|
| `tools\s49_w3_dialogue\measure_full_mask.py` | **新**：整屏遮罩的逐帧测量（交叉验证 Z3） |
| `tools\s49_w3_dialogue\visible_area.py` | **新**：逐帧可见面积 |
| `tools\s49_w3_dialogue\render_mask_sheet.py` | **新**：遮罩接触印相（目视） |
| `tools\s49_w3_dialogue\entry_levels.py` | **新**：入场转场的级表（1 帧分辨率） |
| `tools\s49_w3_dialogue\shard_plan.py` | **新**：逐级的碎片方案（实心/边缘/不同形状）与 OBJ 成本 |
| `tools\s49_w3_dialogue\overlay_obj_cost.py` | **新**：三种碎片粒度的 OBJ 成本 |
| `tools\s49_w3_dialogue\diff_shipped_mask_table.py` | **新**：Z3 的 48 行表复算门禁 |
| `tools\s49_w3_dialogue\emit_tables.py` | **新**：把实测表生成成 C++（表不是手打的） |
| `tools\s49_w3_dialogue\check_encoding.py` | **新**：新文件的 LF / 无 BOM 门禁 |
| `build\s49_w3_dialogue\w3_header_probe.cpp` | **新**：改过的 4 个头文件的 ARM 工具链编译探针 |
| `build\w3-run-new-tests.sh` | **新**：只跑本流两个新单测 |
| `build\w3-compile-runtime-scene.sh` | **新**：用 butano 自己的编译行单独编译 `battle_runtime_scene.cpp` |
| `build\w3-compile-header-probe.sh` | **新**：用 butano 自己的编译行编译头文件探针 |
| `notes\s49-fidelity\W3-overlay-dialogue.md` | **新**：本报告 |

---

## 6. 接线点清单（**本流没有改这些文件**）

### W1（`battle_runtime_scene.cpp` / `battle_scene_controller.h`）

| # | 位置 | 现状 | 要改成 | 依据 |
|---|---|---|---|---|
| **W3.1** | `battle_scene_controller.h:2315`（`_refresh_overlay_cache()` 里构造 `_blocked_overlay_rows` 的循环） | `if(terrain.cost({x,y}) == 0)` | `if(terrain.overlay_blocked({x,y}))`（`grid_map::overlay_blocked()`，本流已加） | 原版 solid = 类别 ≠ plain（17984/17984 px） |
| **W3.2** | `battle_runtime_scene.cpp:2177–2182`（`overlay_height`/`overlay_width` 钳位）与 **2199–2223**（`cell_y_visible` / `cell_x >= overlay_width`） | 整张 256×256 缓冲都画（地图行 0..15） | 只画**地图行 1..12**：`battle_range_ui_overlay_row_visible(map_row)` | 原版行 0 与 13..15 全空 ⇒ 36 格「多画」 |
| **W3.3** | `battle_runtime_scene.cpp:2190–2191`（`window_x = 240 + camera.x()` / `window_y = 248 + camera.y()`）与**相机跟随目标** | 相机停在地图 px **224** | 相机要与原版同相停在 **256**（**差 32 px = 1 个战斗列**） | 原版缓冲锚在 map px (256,0)，不随相机滚 |
| **W3.4** | 画覆盖层的那一处（`_refresh_overlay_cache()` 的调用点） | 用 `battle_range_ui_cell_kind(move_phase, …)` | **同一个函数即可**（本流已把绿改成只在目标阶段画）⇒ 接线后直接生效 | G-H15 |
| **W3.5** | `battle_runtime_scene.cpp` 的星光圈调用点 | 只接了 Z2 的 **25 级** | 要接 **37 级**（帧 1079–1102 的 12 级缺失） | 原版实测 37 级 |

### W2（`battle_black_field_star.h` / `graphics/`）

| # | 位置 | 现状 | 要改成 | 依据 |
|---|---|---|---|---|
| **W3.6** | `battle_black_field_star.h`：`tiles_per_level = blocks * (cell/8)*(cell/8)` = **640** | 32×32 碎片、40 块/级、640 图块 | **16×16 碎片 + 64×64 纯黑块**：每级峰值 **224 图块 / 87 精灵** | 本流逐级实测；640 与 464 都 **> 336** |
| **W3.7** | `battle_black_field_star.h`：`level_count = 25` | 25 级 | **37 级**（+12 级：可见面积 10624…32630） | 原版入场转场实测 37 级 |
| **W3.8** | `battle_black_field_star.h`：`visible_pixels`（25 项） | 25 项 | **37 项**（本流的 37 项级表在 `battle_presentation_content.h::battle_transition_level_area`，前 25 项与之逐项相同） | 同上 |
| **W3.9** | `battle_black_field_star.h`：**include** `konoha/battle_presentation_content.h` | — | **共用同一份预算表**（`battle_transition_battle_scene_free_obj_tiles` 等），避免两份真值 | §2.3 |

### 父代理

| # | 事项 |
|---|---|
| **W3.10** | **同一个连续事件**：星光淡出 + 全黑保持 + 星光淡入 + 对话框「斜切展开」= **37 级**。⇒ 不要当成两个效果排期，也不要各占一份 OBJ 预算。 |
| **W3.11** | 接线完成后**必须重录密集 walk**（密集 walk 与 ROM 绑定），再跑 `tools/s49_overlay_align/compare_overlay_families.py` 看逐格数字；目标 **同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0**。 |
| **W3.12** | `docs/sequel-roadmap.md` 本轮未更新（按文件归属由主线统一更新）。 |

---

## 7. 卡在哪 / 剩余风险

1. **逐格数字本轮没有变化** —— 三处接线（W3.1–W3.3）全在 W1 独占文件里，
   本流只能交付**规则 + 单测 + 接线清单**。
   ⚠️ 本流**没有**实测「改完规则后族名不一致从 26/10/31 降到多少」——
   那一栏要等接线后重录才能填，**本报告不虚报**。
2. **W3.3（相机锚点）不是一行能改完的**：原版的缓冲锚在**地图空间**且**不随相机滚动**，
   重制侧是**相机锚定**（每帧重画整张缓冲）⇒ 两者机制不同。
   要逐格相等，重制侧的相机必须停在原版同一时刻的同一地图位置。
3. **16×16 碎片方案只过了成本核算，没有做资产**：
   峰值 224 块是**按原版像素实测**算出来的，但 Butano 的精灵 item 要求
   **「每个精灵一段连续的图块」** ⇒ 一个「不同的 16×16 边缘形状」需要**自己的一段 4 块**，
   而不同形状之间的 **8×8 子图块不能跨形状共享** ⇒ 实际图块数 = 4 × 不同形状数（+1）。
   本流的成本表用的正是这个口径（`shard_plan.py` 的 `obj_tiles`），
   **但资产仍要 W2 按此重做**。
4. **原版 37 级里，后 12 级的星形不是严格 4 重对称**（它边转边长），
   所以「旋转复用同一批图块」这条路**走不通**（已被 W2 记录为证伪的旧方案）。
5. **Z3 的 `battle_presentation_box_opening` 模型只覆盖对话框内框（3 行 × 16 步）**，
   本流没有改它（它是对的，V6 已复算）；但它与**整屏**的 37 级模型是**两套东西**，
   接线时不要混用。
6. **本流的 12 个新级没有对应的原版 `.png` 接触印相之外的可复算收据**：
   `entry-levels.json` 是收据（37 级 + 面积 + 帧号），可随时用
   `entry_levels.py` 重算。
7. ⚠️ **`battle_runtime_scene.cpp` 当前编译不过**（12 个错误，全在 W1 在途的
   `battle_opening_title_view` 里，见 §3.2）⇒ **W1 收口后必须重跑 ROM 构建**。
   本流只改了头文件、不出包，**故意没跑完整构建**（并发构建的 objcopy 竞态）。

---

## 8. 环境与纪律确认

* 新文件一律 **LF、无 BOM**（探针脚本用 `newline="\n"` 写盘）。
* **未提交 git**。
* **未改** `game\src\battle_runtime_scene.cpp`、`game\include\konoha\battle_scene_controller.h`、
  `battle_black_field*.h`、`battle_opening_title.h`。
* 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**（本流只读了原版的**捕获帧**，
  没有碰逆向线）。
* 并发构建：⛔ **本流没有跑 ROM 构建**（纯头文件改动 + 头文件级单测），
  因此**没有占用构建槽位**，也没有触发 `objcopy: Invalid argument` 的竞态。
