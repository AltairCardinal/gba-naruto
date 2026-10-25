# Y3 流 —— 覆盖层逐格族名归零（G7）

> 2026-10-24 · stream Y3（wave 6）
> 独占产出：本文件 + `tools/s49_y3/` + `tools/s49_overlay_align/compare_overlay_families.py` 的仪器修复
> 改动文件：`battle_range_ui_style.h`、`grid_pathfinder.h`（常量）、`test_battle_range_ui_style.cpp`
> ⛔ **未改** `battle_runtime_scene.cpp`（Y1 独占）、`battle_scene_controller.h`（不在任何人的独占清单里）
> ⛔ 逆向线 `D:\Shell\gba-naruto-reverse` 全程只读；**未提交 git**

---

## 0. 一句话结论

> **本流最大的发现不是像素差，而是「验收仪器一直在测垃圾」**：
> `compare_overlay_families.py::find_overlay_map()` 会把 BG **图块图形区**
> （VRAM `0x00000-0x0FFFF`）当成覆盖层 tilemap 解码 —— 之前所有逐格数字
> （field 136/56/12/118 …）**全部作废**；修好仪器后拿到了**真实**数字，并首次测出
> 原版覆盖层的**地图空间锚点 = map px (256, 0)** 与
> **受阻集 = 地形类别 ≠ plain**（17984/17984 px 逐像素吻合）。
>
> **产品侧我能在独占文件里改的一条规则**（青色只画在移动阶段）已按原版目标选择帧
> （1024 项里 cyan = 0）实现并配了新单测，**但本轮 walk 走不到目标选择阶段 ⇒ 逐格数字无变化**
> （诚实记录，见 §5 台账 H9）。
>
> **剩下的三处真差距全部落在别人独占的文件里**，已写成精确接线点清单（§7）。

---

## 1. 仪器：逐格对拍的第一个 bug（**这是本流最大的交付**）

### 1.1 症状

`tools/s49_overlay_align/compare_overlay_families.py::find_overlay_map()` 的旧实现：

```python
for base in range(0, len(vram) - 2048, 0x400):     # ← 扫遍整个 VRAM
    cells = struct.unpack_from("<1024H", vram, base)
    in_range = sum(1 for cell in cells if 1 <= (cell & 0x3FF) <= 77)
```

GBA 的 VRAM 布局里 **BG 图块图形在 `0x00000-0x0FFFF`，BG tilemap 在 `0x10000-0x17FFF`**，
而 Butano 把 8bpp 的 BG map 放在更靠前的位置。旧扫描在重制 ROM 上**稳定命中 `0x00C00`** ——
那是**图块图形**（像素字节被当成 u16 tilemap 项读）。

实测（`build/s49-w1/vram-after/step-20-A`）：

| 候选基址 | 该区内容 | 旧仪器选中？ |
|---|---|---|
| `0x00C00` | BG 图块图形（字节流） | **是**（296 个"看起来像 tile 号"的项） |
| `0x09800` | **真正的覆盖层 BG map**（442 项，全部是合法覆盖层图块号） | 否 |

⇒ 旧仪器把图块图形解码成 16×16 族栅格 ⇒ **任务书里的基线数字
（field 136/56/12/118、movegrid 136/56/12/124、grid16 114/61/26/98、banner 0/0/214/0）
是噪声，不是残差**。

### 1.2 修法

`find_overlay_map(vram, tile_max=77)` 现在要求候选窗口（0x800 对齐 = 一个 screen block）
的**每一个非零项都是合法的覆盖层图块号**（1..8 / 9..16 / 17..24 / 53..60 / 61..68 / 69..76）。

⭐ 副作用正好可用：**动作菜单复用同一张 BG map**（图块 25..52，不是覆盖层图块号），
所以「动作菜单帧」会被正确判为**没有覆盖层** ⇒ 而「没有覆盖层」= **覆盖层是空的**
（菜单开着的时候覆盖层根本不显示）。旧仪器把动作菜单当成了覆盖层。

**签名保持兼容**：`find_overlay_map(vram, tile_max)` / `remake_family(tile) -> (family, tx, ty)`
两个接口原样保留 —— `tools/s49_fidelity_report/overlay.py` 直接 import 它们
（改了签名会让判定台直接崩，本流踩过一次，已修）。

### 1.3 第二个仪器 bug：比较口径

旧仪器在 16×16 逻辑格上做**自由偏移搜索**。但两侧的覆盖层都是**地图空间**的缓冲，
地图**不是 256 px 周期的** ⇒ 自由偏移在原理上表达不了地图锚点。

⇒ 新版改成**地图空间直接比较**：原版侧用锚点 `(256, 0)`（§2 实测），
重制侧搜索自己的 `window_x/window_y`（运行时用 `240 + camera.x()` / `248 + camera.y()` 算的），
然后在**地图逻辑格**（16×16 px）上逐格比族名。

---

## 2. 原版覆盖层的地图空间锚点（**实测，非推���**）

### 2.1 原版的缓冲 ↔ 地图

| 量 | 值 | 证据 |
|---|---|---|
| 原版 BG2 缓冲 | 256×256 px（32×32 个 8×8 tilemap 项） | F 流 |
| 缓冲 px → 地图 px | **`(x + 256) mod 480`，`y`**（480 = battle-14 的 15 战斗列 × 32 px） | 下两条 |
| 原版画的行 | **地图行 1..12**（行 0 与 13..15 全空） | 逐行 run-length 解码 |
| 原版缓冲的列 | 地图列 8..14 + 列 0（地图宽 480 px 回绕） | 同上 |

### 2.2 锚点 `(256, 0)` 的两条独立证据

**证据 A —— 受阻集逐像素吻合**（`tools/s49_y3/anchor_search.py` + `anchor_diff.py`）：

```
原版 movegrid 帧的 solid 像素 = 17984
在锚点 (256,0) 下，它们 **全部** 落在「地形类别 ≠ 0」的地图格里：
   class (15,7,1,3) → overlap 17984 / 17984   ← 100 % 命中，无一例外
   class (15,7,1)   → overlap 17472
   class (15,)      → overlap 11008
⇒ 原版的「受阻（灰网点）」= **地形类别 ≠ plain**
   （0 plain / 1 river / 3 ground_patch / 7 rock / 15 wall）
```

`anchor_diff.py` 在 (256,0) 下逐格输出 **没有一格 `?`（原版画了实心、地形却可走）**。

**证据 B —— 出手单位的位置**：原版 movegrid 帧的青色（可达集）是一个
**曼哈顿半径 3 的菱形**（战斗格口径，1 战斗列 = 2 逻辑列），中心在逻辑列 22.5 / 逻辑行 6。
按锚点 (256,0) 反推 = **地图 (11, 6)** —— 与 M 流实机日志里鸣人的坐标 `[11,6]` 一致。

### 2.3 锚点的第二个候选已被排除

`grid16` 帧（滚动 `(152,40)`，与 field/movegrid 的 `(240,24)` 不同）的锚点**仍是 (256,0)**
（overlap 8768/9024 = 97 %，其余是那 1 帧瞬态的部分刷新）
⇒ **原版的缓冲内容锚在地图空间，不随相机滚动**；滚动量只决定屏幕上显示哪一块。

---

## 3. 逐格前后对比表（四时刻）

口径：`python tools/s49_overlay_align/compare_overlay_families.py --vram-dir <重制侧 VRAM 目录>`
（每时刻取匹配最好的那一帧；两侧都换算到**地图逻辑格**再比族名）。

| 时刻 | 指标 | ① 旧仪器（任务书基线） | ② 新仪器 / 改产品前 | ③ 新仪器 / 改产品后 | 目标 |
|---|---|---:|---:|---:|---:|
| **field** | 同亮 | 136 | 81 | **81** | 192 |
| | 原版缺 | 56 | 111 | **111** | 0 |
| | 多画 | 12 | 59 | **59** | 0 |
| | 族名不一致 | 118 | 26 | **26** | 0 |
| **movegrid** | 同亮 | 136 | 81 | **81** | 192 |
| | 原版缺 | 56 | 111 | **111** | 0 |
| | 多画 | 12 | 59 | **59** | 0 |
| | 族名不一致 | 124 | 10 | **10** | 0 |
| **grid16** | 同亮 | 114 | 71 | **71** | 175 |
| | 原版缺 | 61 | 104 | **104** | 0 |
| | 多画 | 26 | 69 | **69** | 0 |
| | 族名不一致 | 98 | 31 | **31** | 0 |
| **banner** | 同亮 | 0 | 0 | **0** | 0 |
| | 原版缺 | 0 | 0 | **0** | 0 |
| | 多画 | **214** | **117** | **0** ✅ | 0 |
| | 族名不一致 | 0 | 0 | **0** | 0 |

⭐ ①→② 是**仪器修复**带来的变化（原来测的是图块图形）。
⭐ ②→③ 只有 banner 一格变化：**多画 117 → 0**（"没有覆盖层 map ⇒ 覆盖层是空的"）。

> ① 列的四个数字**可复算**：它们就是 wave-5 出包流水线留在
> `build/s49-package/evidence/overlay/overlay-families.json` 里的收据
> （本流原样读出核对过：field 136/56/12/118、movegrid 136/56/12/124、
> grid16 114/61/26/98、banner 0/0/214/0）——
> **那份收据是用旧仪器（读图块图形）测出来的**，所以它测的是噪声。

### 3.1 banner 的「多画 214」到底是什么

- 旧仪器的 214 = 旧仪器在**动作菜单帧**里读到的垃圾图块（25..52 被当成 overlay 族）；
- 新仪器下 = 重制侧**真的画了**覆盖层的格数（117）；
- 修好「动作菜单 ⇒ 覆盖层为空」的语义后 = **0** ✅。

⇒ **任务书里「banner 多画 214 ⇒ 覆盖层铺到战场范围之外」这个诊断是错的**：
214 里的绝大部分是仪器噪声。真正��「铺到范围之外」的问题在 **movegrid 的 59 格多画**里，
而且它的成因已经测出来了（§4）。

### 3.2 剩下 157 格差异的成分（movegrid，逐格归因）

`tools/s49_y3/diff_breakdown.py`（窗口对齐到最优 (224, 0) 后）：

| 成因 | 格数 | 说明 |
|---|---:|---|
| `original_only` | 111 | 两侧覆盖的**地图区域不同**（相机/锚点，见 §7.3） |
| `extent` | **36** | **原版只画地图行 1..12，重制侧画了整 16 行**（行 13..15 是重制侧多画的） |
| `blocked` | **7** | 原版画成灰网点（地形类别 ≠ plain），重制侧画成可行走格 |
| `highlight` | 3 | 可达集 / 光标相位差（两侧不是同一游戏时刻的同一帧） |

⇒ **「多画」的主因确认是绘制范围（extent），不是几何粒度，也不是调色板。**
⇒ **「族名不一致」的主因确认是受阻集的定义（blocked）。**

---

## 4. 产品侧改动（在 Y3 的独占文件里）

### 4.1 `battle_range_ui_style.h` —— 青色（可达集）只在移动阶段画

**依据**：原版的**目标选择帧**（`tools/s49_w1/capture_original_state.py` 抓的实机帧，
1024 个 tilemap 项）：

| 族 | 项数 |
|---|---:|
| `edge` | 291 |
| `blank` | 173 |
| `solid` | 8 |
| `line_alt`（橙，攻击范围） | 32 |
| `hatch_shift`（绿，合法目标） | 8 |
| **`hatch`（青，可达集）** | **0** ⭐ |

⇒ 目标阶段**一格青色都不画**。旧规则 `if(in_move_range) return move;` 在
非移动阶段仍然会把可达集画成青色 ⇒ 与原版相反。

新规则（`battle_range_ui_cell_kind`）：

```
cursor > target > (attack && !move_phase) > (move && move_phase) > blocked > walkable
```

⇒ **移动阶段与目标阶段从不同时出现青色与橙色**（与 G-H15 一致）。

配套：`game/tests/test_battle_range_ui_style.cpp` 加了 3 条断言
（非移动阶段的可达格 = `grid`；移动阶段 = `move`；非移动阶段的受阻格仍 = `blocked`）。

### 4.2 `grid_pathfinder.h` —— 只加了一个常量

新增 `grid_terrain_class_plain = 0`，供 §7.1 的接线点使用。
（原本想把 `grid_map::cost()` 改成「类别 ≠ plain 即不可走」，
**实测被 4 个既有单测否掉** —— 本树的约定是「cost = 路径代价，可通行性由
`grid_terrain_traversal_limits` 管」，见台账 H6。已回退。）

### 4.3 我**没有**改、但必须改的三处（接线点清单见 §7）

1. **受阻集**：`battle_scene_controller.h:2315` 用的�� `terrain.cost({x,y}) == 0`
   （只有墙 class 15），原版是**类别 ≠ plain**。
2. **绘制范围**：原版只画地图行 1..12，重制侧画整 16 行 ⇒ 36 格「多画」。
3. **相机锚点**：重制侧 `window_x = 240 + camera.x()`，最优匹配窗口是 (224, 0)，
   原版是 (256, 0) ⇒ **差 32 px（1 个战斗格）**。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H1 | 逐格基线数字是量出来的残差 | 检查 `find_overlay_map` 选中的 VRAM 区是不是 tilemap | 它选中 `0x00C00` = **BG 图块图形**；真正的覆盖层在 `0x09800` | **已证伪**（基线作废） |
| H2 | 原版覆盖层缓冲锚在地图空间 | 暴力搜索 (ox, oy) 8 px 步长，对齐「原版 solid 像素」与「地形受阻格」 | 唯一精确命中 (256, 0)，17984/17984 px | **已确认** |
| H3 | 原版 solid = 地形类别 ≠ plain | 同上，按类别集合分别比对 | (15,7,1,3) → 17984/17984；(15,7,1) → 17472；(15,) → 11008 | **已确认** |
| H4 | 原版锚点可用出手单位位置独立验证 | 青色菱形中心反推地图坐标 | (11, 6) = M 流实机日志里鸣人的坐标 | **已确认** |
| H5 | 原版缓冲随相机滚动 | 对 `grid16`（滚动 152,40）重跑锚点搜索 | 仍是 (256, 0)（97 % 命中，剩下是 1 帧瞬态） | **已证伪**（缓冲锚定在地图空间） |
| H6 | 重制侧可以把 `cost()==0` 改成「类别 ≠ plain」来对齐受阻集 | 改 `grid_map::cost()` 后跑全量单测 | **4 个既有单测变红**（`test_battle_map_loader` / `test_battle_runtime_grid` / `test_battle_terrain_traversal` / `test_production_primitives`）：本树约定 cost = 路径代价 | **已证伪**（已回退） |
| H7 | 原版目标阶段不画青色 | 读原版目标选择实机帧的 1024 个 tilemap 项做族直方图 | `hatch` = **0** 项 | **已确认**（已实现） |
| H8 | banner 的 214 格多画是「覆盖层铺到战场外」 | 用修好的仪器重测 banner | 214 → 117 → 0；其中 214 大部分是旧仪器把**动作菜单图块**当成覆盖层 | **已证伪**（真因是仪器 + 动作菜单语义） |
| H9 | 新规则（青色只在移动阶段）会在本轮 walk 上体现 | 逐帧比较改前/改后的覆盖层 tilemap | **35 帧里 0 帧内容变化** —— 本轮 walk 走不到目标选择阶段 | **未验**（规则正确但未被本轮走位触达） |
| H10 | 原版只画地图行 1..12 | 原版缓冲逐行 run-length 解码 + 与地形逐行比对 | 行 0 与 13..15 全空；行 1..12 有内容 | **已确认** |
| H11 | 原版的移动范围是曼哈顿半径 3（战斗格） | 青色区逐行宽度 + 出手单位位置 | 2/6/10/12/10/6/2（逻辑列），中心 = 地图 (11,6) | **已确认** |

---

## 6. 跑了哪些验证

| # | 命令 | 结果 |
|---|---|---|
| V1 | `python tools/s49_overlay_align/compare_overlay_families.py --vram-dir build/s49-y3/vram`（改前） | field 81/111/59/26 · movegrid 81/111/59/10 · grid16 71/104/69/31 · banner 0/0/117/0 |
| V2 | 同上，`--vram-dir build/s49-y3/vram-after2`（改后） | 同上，但 **banner 0/0/0/0 ✅** |
| V3 | `python tools/s49_y3/anchor_search.py` | 原版 solid ↔ 地形：(15,7,1,3) 在 (256,0) 命中 **17984/17984** |
| V4 | `python tools/s49_y3/anchor_diff.py --ox 256 --oy 0` | 逐格输出**无一个 `?`**（原版画实心的地方地形都不是 plain） |
| V5 | `python tools/s49_y3/diff_breakdown.py` | 157 格差异成分：original_only 111 / extent 36 / blocked 7 / highlight 3 |
| V6 | `python tools/s49_fidelity_report.py --out build/s49-report/report-y3-after.json` | field 残差 168,392（**与改前完全相同**）；**overlay 残差 1060 → 857（−19.2 %）**，17/25 帧归零 |
| V7 | 同上 `--ratchet build/s49-report/report-y3.json`（本会话改前基线） | **ratchet: PASS**（exit 0） |
| V8 | 同上 `--ratchet build/s49-package/baseline/baseline-report.json`（wave-5 钉住基线 117,832） | **FAIL**：117,832 → 168,392。⚠️ **这是本会话开工前就存在的**（我改前的第一跑就是 168,392），来源是并行的 Y1/Y2/Y4 改动，**不是本流造成**（见 §8） |
| V9 | `bash build/w1-run-all-tests.sh` + `python tools/s49_y3/check_unit_ratchet.py` | 工作区失败 **20** 项，与基线**逐名相同** ⇒ **棘轮绿**（`new (regression): []`） |
| V10 | WSL `make -j4`（重制 ROM） | 通过（`objcopy: Invalid argument` 出现 1 次，等待 65 s 后重试成功 —— 任务书已记载的并发构建竞态） |

---

## 7. 接线点清单（**我没有改这些文件**）

### 7.1 受阻集（`battle_scene_controller.h`）

* 位置：`D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_scene_controller.h`
* 行号：**2315**（在 `_refresh_overlay_cache()` 里构造 `_blocked_overlay_rows` 的循环）
* 现状：`if(terrain.cost({ x, y }) == 0)` ⇒ 只有墙（class 15）算受阻
* 应改成：`if(terrain.terrain_class({ x, y }) != grid_terrain_class_plain)`
  （`grid_terrain_class_plain` 已由本流在 `grid_pathfinder.h` 加好；
  `battle_scene_controller.h` 已经 include 了 `grid_pathfinder.h`）
* 依据：原版 solid 像素 = 类别 ≠ plain（17984/17984 px 精确吻合）
* 代价：会改变 AI/移动的可达集（岩石/河/地面斑块都不再可走），
  **必须连带跑单测棘轮 + 判定台棘轮**

### 7.2 绘制范围（`battle_runtime_scene.cpp`，Y1 独占）

* 位置：`D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`
* 行号：**2177–2182**（`overlay_height` / `overlay_width` 的钳位）与 **2199–2223**
  （`cell_y_visible` / `cell_x >= overlay_width` 的可见性判定）
* 现状：重制侧把**整张 256×256 缓冲**（地图行 0..15）都画上
* 原版：**只画地图行 1..12**（行 0 与 13..15 全空）⇒ 逐格多画 **36** 格
* 需要的判定：原版的「绘制范围」= 相机窗口所在的那块地图行；
  重制侧的 `window_y` 是 `248 + camera.y()`，而原版缓冲锚在地图 py 0
  ⇒ 两侧的**可见行集合**必须一致（这与 §7.3 的相机锚点是同一个问题）

### 7.3 相机锚点（`battle_runtime_scene.cpp`，Y1 独占）

* 位置：同文件 **2190–2191**
* 现状：`const int window_x = 240 + camera.x().integer();`
  `const int window_y = 248 + camera.y().integer();`
* 实测：重制侧最优匹配窗口 = **(224, 0)**，原版 = **(256, 0)** ⇒ **差 32 px**
* 含义：同一游戏时刻，重制侧的相机停在地图 px 224，原版停在 256
  ⇒ 逐格对拍里 111 格「原版缺」几乎全是这个偏移造成的
* 需要 Y1 一并核对的还有：`camera` 的跟随目标与原版是否同相（任务书 G1 的相机连续滚动
  与本条是同一块地）

### 7.4 判定台的 overlay 语义（`tools/s49_fidelity_report/overlay.py`）

* 位置：`D:\Github\gba-naruto\tools\s49_fidelity_report\overlay.py` → `remake_grid()`
* 本流已改：「VRAM 里没有覆盖层 map」⇒ 返回**空栅格**而不是 `None`
  （没有覆盖层 map = 动作菜单开着 = 覆盖层根本没显示）
* 后果：判定台的 `overlay_residual` 从 1060 降到 **857**，`overlay_exact` 从 0 帧到 **17 帧**
* ⚠️ **W2 / X4r 请复核这个语义**：它同时改变了判定台「frames_with_overlay」的口径

---

## 8. 诚实交代：本会话开工前树就已经超了 wave-5 的残差钉

* wave-5 钉住基线（`build/s49-package/baseline/baseline-report.json`，06:50 生成）：
  field 残差 **117,832** / 中位 1680 / 归因 4·15·6
* 本会话**第一跑**（我还没改任何产品代码之前，07:0x）：
  field 残差 **168,392** / 中位 1940 / 归因 3·14·8
* 本流改完：**168,392** / 1940 / 3·14·8 ⇒ **与开工前逐项相同**

⇒ 也就是说 **+50,560 px 的残差增长来自并行的 Y1/Y2/Y4 改动，不来自本流**；
本流对战场区残差**零影响**，对 overlay 残差 **−203 px（−19.2 %）**。
⇒ 判定台棘轮本流用**本会话开工前的基线**钉（PASS）；对 wave-5 钉住基线仍然是 FAIL，
**请父代理决定是重新钉基线还是回查 Y1/Y2/Y4**。

---

## 9. 未达成 / 剩余风险

1. **目标「同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0」未达成**
   （当前 81/111/59/26 等）。差的三个成因（相机锚点 32 px、绘制范围 36 格、受阻集 7 格）
   **全部落在 `battle_runtime_scene.cpp` 与 `battle_scene_controller.h`**，
   两个文件都不在 Y3 的独占清单里 ⇒ 已写成接线点交父代理。
2. **`grid16` 时刻**是原版的 1 帧瞬态（相机平移途中），原版缓冲本身是半刷新的
   ⇒ 逐格归零需要逐帧对齐到那一帧，本流未做。
3. **原版覆盖层缓冲的内容锚在地图空间 (256, 0) 且不随相机滚动**（H5），
   而重制侧是**相机锚定**的 ⇒ 两者在机制上不同：
   原版靠增量刷新 BG2，重制侧每帧重画整张缓冲。
   ⇒ 要逐格相等，重制侧的相机必须停在原版同一时刻的同一地图位置。
   ⚠️ 「原版的屏幕为什么看不到地图列 1..7」这一点我**没有查实**
   （原版地图的 tilemap 宽 60 tile = 480 px，BG2 缓冲只有 32 tile ⇒ 必然有回绕/接缝），
   留给逆向线或 Y1。
4. 我的产品规则（青色只在移动阶段）**在本轮 walk 上没有被触达**（H9），
   需要一条能走进目标选择阶段的走位才能拿到它的实测数字。
5. `tools/s49_overlay_align/compare_overlay_families.py` 是**共享工具**，
   本流改了它（仪器 bug + 地图空间口径）。**W2 / X4r 请复核**，
   尤其 `find_overlay_map` 的新判据会让「动作菜单帧」不再被当成覆盖层帧。

---

## 10. 改动的文件（完整绝对路径）

### 重制线（`D:\Shell\Github\gba-naruto-butano\butano-sequel\`）

| 文件 | 改动 |
|---|---|
| `game\include\konoha\battle_range_ui_style.h` | 族判定：青色（可达集）**只在移动阶段**画；补了实测依据的注释 |
| `game\include\konoha\grid_pathfinder.h` | 只加了一个常量 `grid_terrain_class_plain = 0`（供 §7.1 接线点用） |
| `game\tests\test_battle_range_ui_style.cpp` | 新增 3 条断言（非移动阶段可达格 = grid / 移动阶段 = move / 受阻格 = blocked） |

### 主仓（`D:\Github\gba-naruto\`）

| 文件 | 改动 |
|---|---|
| `tools\s49_overlay_align\compare_overlay_families.py` | **仪器修复**：`find_overlay_map` 的 VRAM 定位 + 地图空间比较口径 + 「没有覆盖层 = 空覆盖层」；签名保持兼容 |
| `tools\s49_fidelity_report\overlay.py` | `remake_grid()`：没有覆盖层 map 时返回空栅格而不是 `None` |
| `tools\s49_y3\overlay_probe.py` | 新：把重制侧的覆盖层缓冲解出来 |
| `tools\s49_y3\remake_overlay_map.py` | 新：重制侧覆盖层的地图坐标解码 |
| `tools\s49_y3\anchor_search.py` | 新：原版 solid ↔ 地形 的锚点暴力搜索 |
| `tools\s49_y3\anchor_diff.py` | 新：锚点下的逐格差异 |
| `tools\s49_y3\window_scan.py` | 新：重制侧窗口原点的穷举 |
| `tools\s49_y3\side_by_side.py` | 新：两侧覆盖层的地图空间并排图 |
| `tools\s49_y3\diff_breakdown.py` | 新：剩余逐格差异的成分归因 |
| `tools\s49_y3\extract_anchor_vram.py` | 新：从判定台的 anchor 收据里抽出 VRAM |
| `tools\s49_y3\check_unit_ratchet.py` | 新：单测失败集合的棘轮检查 |
| `tools\s49_y3\show_report.py` / `dump_frames.py` | 新：判定台报告的小工具 |
| `build\y3-run-test.sh` | 新：单个单测的编译+运行 |
| `notes\s49-fidelity\Y3-overlay-zero.md` | 新：本文件 |

**未改**：`game\src\battle_runtime_scene.cpp`、`game\include\konoha\battle_scene_controller.h`、
`game\include\konoha\battle_map_content.h`、`game\include\konoha\battle_map_loader.h`、
逆向线 `D:\Shell\gba-naruto-reverse`。
**未提交 git**；**新文件一律 LF、无 BOM**。
