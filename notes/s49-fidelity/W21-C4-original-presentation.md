# W21-C4 —— 原版呈现时机取证（移动格线 / 红色指示箭头 / 「SELECT 詳細」HUD）

> 2026-10-25 21:2x–23:4x · wave 21 / C4 流 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> lane 副本：`D:\Github\gba-naruto\build\w20-e3\butano-sequel`（**唯一改动地**）
> 共享树：**未改**；`battle_runtime_scene.cpp`：**未碰**（C1 流的 lane）
> 独占文件：`battle_map_visual_projection.h` · `battle_map_content.h` ·
> `battle_scene_presentation.h` · `battle_original_states.h`
> 上游：`W20-EXEC-BRIEF.md` · `W20-E3-camera-mapping.md` §3–§6 · `W20-E1-camera.md` ·
> `W20-PARENT-round2.md` · **wave 21 C2 的 `build/w21-c2/press-phase-table.json`**

---

## 0. 一句话结论

> ⭐⭐⭐ **原版这三样东西**全部**存在**——E3 的前提
> 「重制侧在原版对应时刻多画了 3 样东西」**只对了 1 样，而且极性是反的**：
> **箭头与 HUD 是相位常驻**（跟着相位走），**移动格线是过场瞬态**（只在 26 帧里画）：
>
> | 东西 | 原版 | 重制侧 | 差异 |
> |---|---|---|---|
> | **红色指示箭头** | 存在，**两款**：24 px / 6×6 / 精确 RGB (255,0,0)，与 30 px / 10×5 | 存在，**同两款、同颜色** | ⚠️ **30 px 那款原版只画 2 拍（`step-01/02`），重制侧画了 9 拍（`step-04…12`）** ⇒ **重制侧把宽箭头画太久** |
> | **「SELECT 詳細」HUD** | 存在，**140 个亮像素，框 (193,13)-(231,22)**，与重制侧**逐像素相同** | 存在（同框同像素） | 重制侧**画得太早、也画得太多** |
> | **移动格线（移動格子）** | 存在，但**只在过场瞬态里画 26 帧**（`f052..f077` / `f005..f030`），**25 个 settled beat 里一帧都没有** | **settled beat 一帧都没有**；VRAM 里 `remake step-26` 才有 move range | 原版的格线是**瞬态**，不是相位常驻 |
>
> ⇒ **「重制侧多画了移动格线」是误判**：E3 的 `sbs_step-22-A.png` 是**非等比缩放**（970×256 → 2.0×/1.6×）的图，
> 重制侧那半边顶上的「青色格线」其实是**水带（terrain 水纹）**，不是格线；
> 逐像素检查 `capture-remake/step-26-A.png`：**mint 0 px / 无晶格**。
>
> ⇒ ⭐⭐ **真正的相位断裂在别处**（与 C2 的结论吻合）：
> **原版 `step-19/20/21/22` 有 3 次 A 被「回合横幅 →『請準備...』→ 相机摇镜落到战斗位」这段过场吃掉**，
> 重制侧**没有这段过场** ⇒ 重制侧的相位整体**错位 1–3 拍**，
> 于是「SELECT 詳細」HUD **提前**出现、原版的**瞬态移动格线**在重制侧**根本没有对应物**。

---

## 1. 仪器（全部自建，全部可复现）

| 工具 | 作用 | 关键点 |
|---|---|---|
| ⭐ `tools/s49_w21c4/detect_presentation.py` | **逐帧 × 三样东西的布尔检测**（原版 273 帧 + 原版 25 beat + 重制侧 35 beat） | 检测器全部是**实测出来的签名**，不是猜的 |
| ⭐ `tools/s49_w21c4/overlay_vram_census.py` | **VRAM 覆盖层普查**（不跑模拟器，直接读 `.ss9`） | 原版读 BG2 tilemap @ `0x06001000`；重制侧按签名定位覆盖层 BG map |
| `build/w21-c4/original-presentation-timing.json` | **交付物**：逐帧 × 三样东西 + 相位标注 | 机器可读 |
| `build/w21-c4/overlay-vram-census.json` | VRAM 覆盖层族名普查（两侧） | 机器可读 |

### 1.1 三个检测器的**实测来源**

| 检测器 | 签名 | 来源 |
|---|---|---|
| **红箭头** | 精确 RGB `(255,0,0)` 的 4-连通块，**≥ 10 px**（箭头本体 24 px / 6×6；1 px 的散点是单位衣服的红） | 读 `dense/step-20-to-21/f001.png` |
| **移动格线** | mint 族 `(123,236,190) (138,252,200) (97,246,190) (91,226,185) (112,255,200) (107,221,180)` | 读 `f077 → f078`（覆盖层消失那一帧）的像素差 |
| **攻击范围 / 光标** | `(255,143,30)` / `(255,226,30) (255,241,41)` | 同上 |
| **「SELECT 詳細」HUD** | 框 `(190,10)-(236,26)` 内**亮像素数 ≥ 100** + 与模板的精确比对 | 模板取自**原版自己的 `step-23-A.png`** |

> ⭐ **模板等价性（硬证据）**：原版 `step-23-A.png` 与重制侧 `step-26-A.png` 的
> HUD **亮像素数都是 140、框都是 (193,13)-(231,22)、4×4 块图案逐格相同**
> ⇒ 两侧画的是**同一个精灵**，只是**出现的拍不同**。

---

## 2. ⭐ Q1 —— 原版逐帧 × 三样东西（**机器可读**）

### 2.1 逐帧（273 帧 = 3 个过场窗口 × 91 帧）

窗口语义（`tools/s49_w20e/dense_camera_curve.py capture`）：
`load step-X-A.ss9` → `frames 4 1`（按 A） → 90 帧 → 逐帧截图。
⇒ **窗口 `step-X-to-Y` 里，第 43 帧 = beat X+1，第 90 帧 = beat X+2**（用 PNG 的 sha256 精确配对得到）。

| 窗口 | **移动格线** | **红箭头** | **「SELECT 詳細」HUD** |
|---|---|---|---|
| `step-19-to-20` | **无**（0 帧） | `f010 … f090`（81 帧） | **无** |
| `step-20-to-21` | ⭐ **`f052 … f077`（26 帧）** | `f001 … f060`（60 帧） | **无** |
| `step-21-to-22` | ⭐ **`f005 … f030`（26 帧）** | `f001 … f013` + `f058 … f090` | ⭐ **`f085 … f090`（6 帧）** |

**逐帧全表**：`build/w21-c4/original-presentation-timing.json` → `windows.<win>.per_frame[]`
（每行含 `move_grid` / `cursor_cell` / `attack_range` / `red_arrow` / `select_hud` / `hud_any`
+ `mint_cell_px` / `yellow_cell_px` / `orange_cell_px` / `lattice_px` / `red_arrow_clusters` / `hud_bright_px`）。

### 2.2 逐 beat（原版 25 拍 + 重制侧 35 拍）—— **过场 4 帧的重点**

| 原版 beat | 相位（C2） | 移动格线 | **红箭头** | **SELECT 詳細** | VRAM 覆盖层（原版 BG2） |
|---|---|:--:|:--:|:--:|---|
| `step-18` | turn_banner | ✘ | ✘ | ✘ | lit=1（空） |
| **`step-19`** | turn_banner（回合横幅） | ✘ | ✘ | ✘ | lit=1 |
| **`step-20`** | turn_banner（「請準備...」框） | ✘ | **✔ 24 px @ (113,37)-(118,42)** | ✘ | lit=1 |
| **`step-21`** | deployment_unit（相机落到战斗位） | ✘ | **✔ 24 px @ (81,46)-(86,51)** | ✘ | lit=1 |
| **`step-22`** | deployment_unit | ✘ | **✘** | ✘ | **lit=512**（solid 148 / edge 268 / **hatch 56** / band 16 / line_alt 24） |
| **`step-23`** | unit_selection | ✘ | **✔ 24 px @ (111,37)-(116,42)** | ⭐ **✔ 140 px @ (193,13)-(231,22)** | lit=598 |
| **`step-24`** | command_selection | ✘ | **✔ 24 px @ (113,37)-(118,42)** | ✘ | lit=598 |

**重制侧对照（同样的检测器）**：

| 重制侧 beat | 相位（C2） | 移动格线 | **红箭头** | **SELECT 詳細** | VRAM 覆盖层 |
|---|---|:--:|:--:|:--:|---|
| `step-22` | turn_banner | ✘ | ✘ | ✘ | 无 |
| `step-23` | turn_banner（回合横幅） | ✘ | ✘ | ✘ | 无 |
| `step-24` | unit_selection | ✘ | ✔ 24 px | ⭐ **✔ 140 px**（**原版此刻没有**） | 无 |
| `step-25` | command_selection | ✘ | ✔ 24 px | ✘ | 无 |
| **`step-26`** | move_selection | ✘ | ✔ 24 px | ✔ 140 px | ⭐ **有：solid 96 / edge 52 / hatch 44** |
| `step-29…34` | target_selection | ✘ | ✔ 24 px | ✔ 140 px | 有：solid 90 / edge 52 / hatch_shift 46 / band 2 / line_alt 2 |

### 2.3 ⇒ Q1 的三个答案

1. ⭐ **红箭头**：**相位常驻**，两侧**同两款**精灵（24 px / 6×6 与 30 px / 10×5，精确 `(255,0,0)`）。
   * 原版：24 px 版出现在 `step-00`、`step-03…08`、`step-20`、`step-21`、`step-23`、`step-24`；
     **30 px 版只出现在 `step-01`/`step-02`**；
     `step-09…19` 与 `step-22` **完全没有**。
   * 重制侧：24 px 版出现在 `step-24…27`、`step-29…34`；
     **30 px 版出现在 `step-04…12`（9 拍！）**。
   ⇒ **差异 = 30 px 宽箭头的持续拍数**（原版 2 拍 vs 重制侧 9 拍），
   **不是**「重制侧多画了一个原版没有的精灵」。
   ⇒ 红箭头**跟着行动单位走**（原版 `step-20/21` 的箭头位置随相机移动），
   **不是**「移动格线的同时出现」。
2. ⭐ **「SELECT 詳細」HUD**：**相位常驻**，但**只在 `unit_selection` 相位**（原版 `step-23`）。
   重制侧在 `unit_selection`（`step-24`）**和** `move_selection`（`step-26`）**都画**，
   在 `target_selection`（`step-29…34`）**也画** ⇒ **重制侧画得太早、也画得太多**。
3. ⭐ **移动格线**：**不是相位常驻，是瞬态**。原版只在
   **`step-20-to-21` 窗口的 `f052..f077`** 和 **`step-21-to-22` 窗口的 `f005..f030`**
   这 **26 帧**里画（两次是同一次事件的两次观测：一次从 `step-20` 按 A 之后看到，
   一次从 `step-21` 存档起看到），**原版 25 个 settled beat 里一帧都没有**。
   ⇒ 重制侧在 settled beat 上同样没有 ⇒ **这一项两侧一致，不是差异来源**。

---

## 3. ⭐ Q2 —— 「請準備...」框是什么？和「回合 1 玩家」横幅是同一个东西吗？

> **答：不是同一个东西。原版有**两个**不同的框，重制侧只有其中一个。**

| | 原版 `step-19` | 原版 `step-20` | 重制侧 `step-23` |
|---|---|---|---|
| 内容 | 「回合 1 / 玩家 / 行動中」 | 「**請準備...**」 | 「回合 1 / 玩家 / 行動中」 |
| 形态 | 圆角矩形，**蓝边**，3 行字，**居中偏上** | 圆角矩形，**蓝边**，**1 行字**，**左上** | 圆角矩形，蓝边，3 行字，居中偏上 |
| 相机 | 不动 | **相机开始左摇** | 不动 |
| 红箭头 | ✘ | ✔（单位在框上方，箭头在 (113,37)） | ✘ |
| 相位（C2） | `turn_banner` | **`turn_banner`（链上预测 `unit_selection`，实际仍是 `turn_banner`）** | `turn_banner` |

* 两者**都是 BG 层的文字窗口**（圆角 + 蓝边 + 米白底 + 深色字），**不是 OBJ 精灵**；
  但**内容不同、位置不同、长度不同**。
* 原版 `step-19` 与重制侧 `step-23` 是**同一个画面语义**（回合横幅）；
  原版 `step-20` 的「請準備...」**在重制侧完全没有对应物**。
* ⇒ **重制侧缺的不是「HUD 画早了」，而是整段过场**：
  `回合横幅 →「請準備...」→（3 次 A 被吃掉）→ 相机摇镜落到战斗位 → unit_selection`。

**形态对比的可复现证据**：`build/w21-c2/montage-original-17-24.png`（原版 17–24 拼图）
vs `build/w21-c2/montage-remake-21-28.png`（重制侧 21–28 拼图）。

---

## 4. Q2 附带 —— 原版移动格线**是什么**（格族名 / 亮度 / 线宽 / 颜色）

### 4.1 格族名（原版 BG2 的 tile 族，权威口径）

`tools/s49_rule_probe/overlay_ground_truth.py` 的族词表 + `overlay_vram_census.py` 的实测：

| 族名 | tile index | 角色 | 原版 `step-22` 实测计数 | 原版 `step-23/24` |
|---|---|---|---:|---:|
| `blank` | 256, 257 | 空 | 512 | 426 |
| `edge` | 258–261 | **格线（晶格）** | **268** | 235 |
| `hatch` | 262–265 | **移动范围（移動格子填充）** | **56** | 52 |
| `hatch_shift` | 274–277 | 目标位移 | 0 | 0 |
| `line_alt` | 266–269 | **攻击范围（橙）** | **24** | 24 |
| `band` | 270–273 | **光标格（黄）** | **16** | 6 |
| `solid` | 278–281 | 障碍格（50 % 灰点阵） | 148 | 281 |

⇒ **原版的「移动格线」= `edge`（晶格）+ `hatch`（青色移动范围填充）**，
`band`（黄光标）和 `line_alt`（橙攻击范围）同层共存。

### 4.2 屏幕上的颜色 / 亮度（逐像素实测，原版）

| 角色 | 屏幕 RGB | 说明 |
|---|---|---|
| 移动范围填充（mint） | `(123,236,190) (138,252,200) (97,246,190) (91,226,185) (112,255,200) (107,221,180)` | `hatch` 与草地混合后的 6 个实际取值 |
| 攻击范围（橙） | `(255,143,30)` | `line_alt` 主色，纯色不混 |
| 光标格（黄） | `(255,226,30) (255,241,41)` | `band` 主色 |
| 晶格线 | `(118,159,190) (97,133,154)` | `edge` 与草地混合（**1 px 宽**） |
| 红箭头 | `(255,0,0)` | 24 px / 6×6 |

### 4.3 几何

* 一个战斗格 = **32 × 16 px**；一个**逻辑格**（族统计的单位）= **16 × 16 px**（X 方向 2 个 / Y 方向 1 个）。
* 晶格线落在逻辑格的**右边界 `x == 31`** 与**下边界 `y == 15`**（`battle_range_ui_pixel_index` 已如此实现）。
* 覆盖层缓冲区 **256 × 256 px**，**锚在 map 空间** `(256, 0)`（`battle_map_visual_projection.h` 已是这个口径）。

---

## 5. ⭐ Q3 —— 重制侧该怎么改

### 5.1 已在**我的独占文件**里落地的改动（可执行）

**文件**：`game/include/konoha/battle_scene_presentation.h`（lane 副本
`build/w20-e3/butano-sequel/game/include/konoha/battle_scene_presentation.h`）

新增（纯 `constexpr`、无 Butano 依赖）：

| 符号 | 内容 |
|---|---|
| `enum class battle_presentation_moment` | 原版的 7 个实测时刻：`none / round_banner / prepare_box / camera_landed / range_transient / unit_selection / command_menu` |
| `struct battle_presentation_overlay_visibility` | 三个布尔：`range_grid` / `facing_indicator` / `select_detail_hud` |
| `battle_presentation_overlay_visibility_table` | **实测表**（见 §2.2） |
| `battle_presentation_overlays_of(moment)` | 取表函数 |
| `battle_presentation_range_transient_frames` | **26** |
| `battle_presentation_facing_indicator_pixels/width/height/red/green/blue` | **24 / 6 / 6 / 255 / 0 / 0** |
| `battle_presentation_select_hud_x/y/width/height/bright_pixels` | **193 / 13 / 39 / 10 / 140** |

**为什么放这个文件**：`battle_scene_presentation.h` 是**呈现层**的归属文件，
`battle_original_states.h` 是**生成文件**（`Do not edit`）不能手改，
`battle_map_visual_projection.h` 只管覆盖层的**几何**（锚点/缓冲区）不管**时刻**。

### 5.2 ⭐ 接线请求（给 C1 流 / 父代理 —— 我**不能**改 `battle_runtime_scene.cpp`）

| # | 文件 | 位置 | 改成什么 | 为什么（实测依据） |
|---|---|---|---|---|
| **R-C4-1** ⭐ | `game/src/battle_runtime_scene.cpp` | 覆盖层绘制处（`:9444` 的 `if(! map_movement.busy())` → `update_range_overlay(...)`） | 覆盖层的**可见性**改由 `battle_presentation_overlays_of(moment).range_grid` 决定；**只在 `range_transient` 相位画**，且**连续 26 帧**；`move_selection` 相位**不画** | 原版的移动格线**只在过场瞬态 `f052..f077` / `f005..f030` 画 26 帧**，25 个 settled beat **一帧都没有**（§2.2）。重制侧 `move_selection`（`step-26`）把 move range 放进了 VRAM，但**屏幕上没画** ⇒ 现状是对的，**不要**把它提到 `move_selection` |
| **R-C4-2** ⭐ | `game/src/battle_runtime_scene.cpp` | 「SELECT 詳細」HUD 的绘制处 | HUD **只在 `unit_selection` 相位画**；**`move_selection` / `target_selection` 不画** | 原版只有 `step-23`（`unit_selection`）有 HUD（140 px）；重制侧在 `step-24/26/29…34` 都有 ⇒ **提前 + 画太多**（§2.2） |
| **R-C4-3** | `game/src/battle_runtime_scene.cpp` | 红箭头绘制处（`:9379-9384`，`battle_facing_indicator_graphics_index(...)`） | 箭头**必须用原版的两款**：24 px / 6×6 与 30 px / 10×5，精确 `(255,0,0)`；**30 px 那款只画 2 拍**（原版 `step-01/02`），重制侧现在画了 **9 拍**（`step-04…12`）⇒ **缩短宽箭头的持续拍数** | 原版全程两款精灵，24 px 版出现在 `step-00/03…08/20/21/23/24`，**30 px 版只在 `step-01/02`**（§2.2） |
| **R-C4-4** ⭐⭐ | `game/src/battle_runtime_scene.cpp`（相位机） | 相位推进 | **补上原版那段过场**：`round_banner` →（按 A）→ `prepare_box`（「請準備...」）→（再按 A）→ **相机摇镜落到战斗位** →（再按 A）→ `unit_selection`。原版 `step-19/20/21/22` 就是这 4 拍 | C2 的相位链断点 = 原版 `step-20`（预测 `unit_selection`，实际仍 `turn_banner`）；重制侧**从回合横幅直接进 `unit_selection`** ⇒ 少 3 次 A ⇒ 后面所有相位**错位 1–3 拍** |
| **R-C4-5** | `notes/s49-fidelity/W20-E3-camera-mapping.md` §3.4 | 「重制侧多了 3 样东西」那句 | 更正为：「重制侧多画了**一个 30 px 红色精灵**；『SELECT 詳細』HUD **提前且过多**；**移动格线两侧在 settled beat 都没有**（原版只在过场瞬态画 26 帧）」 | E3 的 `sbs_step-22-A.png` 是**非等比缩放**（970×256 ⇒ 2.0×/1.6×），重制侧那半边顶上的「青色格线」是**水带**，逐像素复核 `capture-remake/step-26-A.png`：**mint 0 px、无晶格** |
| **R-C4-6** | `notes/s49-fidelity/W20-E1-camera.md` §3.1 | 「移动格线 f049→f069」 | 更正为 **`f052..f077`**（26 帧） | E1 是目视读的；机器可读检测给出 `f052` 首次出现、`f078` 首次消失（`f049`/`f051` 逐像素确认**没有格线**） |

---

## 6. ⚠️ 两个必须记下来的口径坑

1. ⭐ **`capture-original` 的 PNG 与 `.ss9` 不是同一时刻**。
   把原版 `step-22-A.ss9` 的 BG2 tilemap 按该存档的 BG2 滚动 `(hofs=184, vofs=40)`
   投影到屏幕上，落点的 PNG 像素是**普通草地** `(173,173,49)/(198,198,66)`，
   **不是** mint ⇒ **VRAM 里已经有的覆盖层，屏幕上还没画**。
   ⇒ **屏幕级读数（本文 §2.1/§2.2）是权威的**；VRAM 普查只记录「游戏在存档那一刻的**意图**」，
   **不能**当作「屏幕上画了」。
2. ⚠️ **`bg_hofs` 还是读不到**（E3 的 P-41）：本流用 `s49_state` 直接读存档的 IO 块，
   原版 `BG2HOFS/VOFS` 读得到（`(184,40)` / `(240,24)`），但**重制侧 35 个存档全部相同**
   ⇒ 两侧的 BG2 滚动**不能**直接比。

### 6.1 ⭐ 交叉验证：混合模型检测器（重制侧自己的调色板）

mint 族是从**原版**的帧差里读出来的，可能对重制侧不适用。
⇒ 又做了一个**与调色板无关**的交叉验证：用**重制侧自己的调色板**
（`battle_range_ui_style.h` 的 `grid_secondary` / `move_primary` / `attack_primary` /
`cursor_primary` / `target_primary`）按产品自己的混合比 `10/16` 展开，
再和**帧里实际出现的背景色**组合，枚举所有可能的**渲染后**颜色并统计。

| 帧 | 命中 |
|---|---|
| 原版 `step-20-to-21/f052, f060, f070, f077` | ⭐ **有**（`grid` 族 4/18/22 px、`attack` 族 12/54/93/97 px、`cursor` 族 30 px） |
| 原版 `f048` / `f078` | **无**（格线消失前 / 出现前） |
| **原版 25 个 settled beat** | **全部无** |
| ⭐ **重制侧 30 个 settled beat**（含 `step-26` 的 `move_selection`） | **全部无** |

⇒ ⭐ **独立确认**：「移动格线在 settled beat 上两侧都没有」这条结论**不是**原版调色板造成的假象。

> ⚠️ 唯一的「噪声命中」已定位：重制侧 `step-26-A.png` 有 **7 px** 的 `move_primary@10/16 over black`
> ⇒ 位置是 **x 0..19, y 0..6**（**画面左上角的水带**），另有 1 px 孤立点 ⇒ **不是移动范围**。
> ⇒ 结论不变：**重制侧 `step-26`（`move_selection`）屏幕上没有画移动格线。**

---

## 7. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **P-70** | 原版的红箭头是 `(255,0,0)` 的一个小精灵 | 逐帧连通块分析（273 帧 + 60 个 settled beat） | 成立：**24 px / 6×6**（偶见 30 px / 10×5 的另一款）；1 px 散点是衣服 | **已确认** |
| **P-71** | 原版的「SELECT 詳細」HUD 与重制侧是同一个精灵 | 原版 `step-23-A` vs 重制 `step-26-A`：亮像素数 + 框 + 4×4 块图案 | 成立：**都是 140 px @ (193,13)-(231,22)，块图案逐格相同** | **已确认** |
| **P-72** | 原版的移动格线是**相位常驻**（在某个 beat 上一直画） | 25 个 settled beat 的 mint 计数 | ⛔ **不成立**：**25 个 beat 全是 0** | **已证伪** |
| **P-73** | 原版的移动格线是**过场瞬态** | 273 帧逐帧 mint 计数 | 成立：**`step-20-to-21` 的 `f052..f077`**、**`step-21-to-22` 的 `f005..f030`**，各 **26 帧** | **已确认** |
| **P-74** | E1 目视的「格线 f049→f069」 | 逐像素复核 `f049`/`f051`（无格线）与 `f052`（有格线） | ⛔ **不成立**：起点应是 **f052**，终点 **f077**（f078 起消失） | **已证伪（更正 E1）** |
| **P-75** | 重制侧在对应时刻**多画了移动格线**（E3 §3.4 的前提） | `capture-remake/step-26-A.png` 的 mint/黄/橙/晶格逐像素 + ASCII 图 + VRAM 覆盖层普查 | ⛔ **不成立**：settled beat 上**两侧都没有**格线；E3 看到的「青色格线」是**水带**（`sbs` 是非等比缩放的图） | **已证伪** |
| **P-76** | 重制侧**提前**画了「SELECT 詳細」 | 两侧 beat 表 + C2 的相位 | 成立：重制 `step-24`（`unit_selection`）就有，原版 `step-23` 才有 ⇒ **重制侧早 1 拍**；且重制侧在 `move_selection`/`target_selection` 也画，原版不画 | **已确认** |
| **P-77** | 重制侧的红箭头**多一款**原版没有的精灵 | 两侧红连通块尺寸统计 | ⛔ **不成立**：**两侧都有两款**（24 px/6×6 与 30 px/10×5）；差异是**持续拍数**（30 px 版：原版 2 拍 vs 重制侧 9 拍） | **已证伪（更正为「持续拍数」）** |
| **P-78** | 原版 `capture-original` 的 PNG 与 `.ss9` 同一时刻 | 把 `step-22-A.ss9` 的 BG2 `hatch` 按该存档滚动投影到 PNG 上比对 | ⛔ **不成立**：落点是普通草地 | **已证伪（记为口径坑）** |
| **P-79** | 原版 `step-20` 的「請準備...」框与 `step-19` 的回合横幅是同一个东西 | C2 的拼图 + 逐帧/逐 beat 表 | ⛔ **不成立**：两个不同的框（内容/位置/长度都不同）；原版多一个 | **已证伪** |
| **P-80** | 原版覆盖层的格族名 | `overlay_ground_truth.TILE_FAMILY` + `overlay_vram_census.py` 读原版 BG2 tilemap @ `0x06001000` | 成立：`edge`(晶格) + `hatch`(移动填充) + `band`(黄光标) + `line_alt`(橙攻击) + `solid`(障碍) | **已确认** |

---

## 8. 收据

| 路径 | 内容 |
|---|---|
| ⭐ `notes/s49-fidelity/W21-C4-original-presentation.md` | 本文件 |
| ⭐ `build/w21-c4/original-presentation-timing.json` | **逐帧 × 三样东西** + 相位标注 + 逐 beat 表 + 两侧对照 |
| ⭐ `build/w21-c4/overlay-vram-census.json` | 两侧 VRAM 覆盖层族名普查（60 个存档态） |
| `tools/s49_w21c4/detect_presentation.py` | 逐帧 / 逐 beat 检测器 |
| `tools/s49_w21c4/overlay_vram_census.py` | VRAM 覆盖层普查（不跑模拟器） |
| `build/w20-e3/butano-sequel/game/include/konoha/battle_scene_presentation.h` | **Q3 的可执行改法**（+118 行 constexpr 表） |
| ⭐ `build/w21-c4/c4-presentation-timing.patch` | **接线补丁**：lane 相对共享树的差异（**1 hunk / +104 行 / 删 0 行**）⇒ 父代理可直接 `git apply` |

### 8.2 构建 / 验证

| 项 | 结果 |
|---|---|
| lane 构建（`make -j4`，WSL） | ✅ **成功**（`ROM fixed!`）；**只有既有的告警**，无新增 |
| lane ROM | `sha256 = 33d5e3e70aa2b185c5258ddb683ff80593c82acd28aeb83db284ed82321d3062`（12,257,820 B） |
| 改动文件 | **只有** `game/include/konoha/battle_scene_presentation.h`（lane 副本）；共享树未动；`battle_runtime_scene.cpp` 未碰 |
| 单测 | ✅ **pass=118 / fail=20**（**lane 的既定基线**：`W20-EXEC-BRIEF.md` §4 写的就是 118/20；20 项失败是预存债，**逐名未变**）。⚠️ lane 里**没有** E2 的 `test_battle_experience_award.cpp`（共享树有）⇒ 共享树口径仍是 **119/20**。**零回归**。 |

> ⚠️ 本流的改动是**纯 constexpr 数据表**（`battle_scene_presentation.h` 里新增的枚举 + 数组 + 常量），
> **没有任何调用方** ⇒ 不可能改变任何运行时行为；单测的 118/20 与改动前逐名一致。

### 8.1 复现命令

```powershell
# 1) 逐帧 / 逐 beat 检测（273 帧 + 60 个 beat）
python tools/s49_w21c4/detect_presentation.py --out build/w21-c4/original-presentation-timing.json
python tools/s49_w21c4/merge_phases.py            # 把 C2 的相位标注并进同一份 JSON

# 2) VRAM 覆盖层普查（直接读存档，不需要模拟器）
python tools/s49_w21c4/overlay_vram_census.py \
  --original build/s49-package-w18/work/s49-report/capture-original \
  --remake  build/w20-e3/capture-remake \
  --out     build/w21-c4/overlay-vram-census.json

# 3) 调色板无关的交叉验证（§6.1）
python tools/s49_w21c4/blend_cross_check.py
```

---

## 9. 未完成项

1. ⭐ **没有做产品改动**（`battle_runtime_scene.cpp` 归 C1 流）。
   本流只在 `battle_scene_presentation.h` 里放**实测规格表**，
   **接线在 R-C4-1…R-C4-4**，其中 **R-C4-4（补那段过场）体量最大**，需要 C1 流排期。
2. ⭐ **重制侧没有逐帧录相** ⇒ 「重制侧的移动格线瞬态有多长、在哪个相位」只有
   **VRAM 普查**（`step-26` 有 move range、`step-29…34` 有 target 集）这一个口径，
   **没有屏幕级逐帧证据**。
   ⇒ 若要闭环，需要**重制侧**的逐帧录制（要全局锁）。
3. ⭐ **没有加单测**：本流的表是数据（`constexpr`），加测试会把单测账从
   `pass=119/fail=20` 变成 120 ⇒ **故意不加**，等父代理收口时统一加。
4. **原版 `step-24` 之后的覆盖层可见性**没查（原版 walk 只到 `step-24`）。
5. **「請準備...」框的逐像素指纹**没做（C2 有 `tools/s49_w21c2/fingerprint.py`，
   本流只做了形态对比，没跑它）。
