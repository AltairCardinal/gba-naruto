# 覆盖层 1:1 接线施工单（第 26 轮，基于已闭合的屏幕地面真相）

日期：2026-10-21
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
基线 ROM `02bf3573118f4b43d58189db6816a5d0d2d47190f23e0f1d3c6abd5dbb217803`
基线残差 **2,917** 像素（对照 `artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-19-A.png`，战场区 (0,0,240,128)）
**当前 ROM 已重录确认**：`artifacts/s49-remake-walk-20261021-v1/`（35 张 PNG 与旧录像**逐字节相同**）

依据：`notes/s49-overlay-screentruth-20261021.md`（屏幕地面真相 + 残差归因）、`artifacts/s49-original-overlay-screentruth-v1/`。

## 0. 结论先行

残差 2,917 **只**由两件事构成，与颜色、混合、位深、调色板、优先级**全都无关**：

| 残差 | 像素 | 性质 |
| --- | ---: | --- |
| **受阻区暗化没画** | 2,317 | 重制侧**完全没画**原版那一层（42 个 8×8 格，底图逐像素一致） |
| **透镜描边粒度不同** | 600 | 原版逻辑格 **16×16 px**，重制格点 **32×16 px** ⇒ 描边每隔一条就少画一次 |

⇒ **两条都不是「调色板/混合没调对」，而是「画哪一格、格多粗」没对齐。**
⇒ 而且**颜色侧已经 1:1**：重制的 `move_primary RGB5(3,25,31)`=(24,205,255)=原版调色板 2，
`move_secondary RGB5(1,13,21)`=(8,106,172)=3，`grid_secondary RGB5(8,13,17)`=(65,106,139)=1，
`blocked_primary/secondary RGB5(9,9,9)/(4,4,4)`=(74,74,74)/(32,32,32)=10/11。**混合 10/16 也已经一致。**

## 1. 两侧结构对照（都已实测）

| | 原版 | 重制 |
| --- | --- | --- |
| 层 | BG2（DISPCNT bit 10） | `battle_range_overlay` 的 regular BG（优先级 2、8bpp） |
| 屏幕位置 | 整屏，滚动 hoff=240 / voff=24 | `(0,0)`，**无滚动**，32×32 图块 = 256×256 px |
| 可见窗口 | 30×20 图块 | 32×32 图块左上角的 30×20 |
| 图块 | 4bpp、bank 12、256..287 | 8bpp、`battle_range_ui_*_color` 逐色同号 |
| 内容 | **烘焙好的一张静态布局图**（field/movegrid 两态，差 212 项） | 按战斗规则逐格点算 |

⇒ 两层的**结构已经同构**，只差「滚动」与「内容」。
⇒ 因为重制层没有滚动，**原版的滚动可以等价地折进索引换算**：
**重制 map 格 (c,r) ← 原版 tilemap 格 ((c+30)%32, (r+3)%32)**（只对 0≤c<30、0≤r<20 填，其余填 0）。

## 2. 施工单（三步，按顺序做，每步都必须「构建 + 测量」，更差就回滚）

### 第 ① 步：把覆盖层图块换成原版的 32 块（4bpp → 8bpp 展开）

**为什么**：现在的图块是重制自造的（4×2 铺一格，描边在 32×16 格的右/下边），
而原版的图块是 **2×2 = 16×16 逻辑格**（描边在逻辑格右/下边）⇒ 粒度不一致直接产生那 600 px。

**做什么**
1. `tools/generate_butano_movegrid_overlay_assets.py`（或新工具）增加一个 **8bpp 展开产物**：
   原版 4bpp 像素值 `v` → 8bpp 索引 `v == 0 ? 0 : (v <= 11 ? 224 + v : 0)`
   （原版调色板 12..15 也是 0x0000 ⇒ 透明 ⇒ 映射到 0；原版 1..11 对应重制的 225..235）。
2. 新的块预算：**每个族 2×2 = 4 块**（原版的 4 个变体），6 个族 = **24 块**；
   再加菜单字形 28 块（原 25..52）⇒ **52 个逻辑块 = 104 个存储块 = 3,328 B**。
   （现在是 77 块 / 154 存储块 / **4,928 B** ⇒ **净省 1,600 B**，VRAM 不是约束。）

**VRAM 账**（`artifacts/s49-overlay-plan-20261021-v1/capacity.json`）：
map 32×32 = 2,048 B（不变）＋ 图块 3,328 B（原 4,928 B）⇒ **总量 5,376 B，比现在少 1,600 B**。

### 第 ② 步：移动/目标选择阶段直接装原版烘焙布局

**为什么**：原版的受阻区暗化、网格网、透镜**都是烘焙进 tilemap 的**；
直接把原版的窗口装进去 ⇒ 2,317 px 的漏画和 600 px 的粒度**一起消失**。

**做什么**
1. `butano-sequel/game/include/konoha/generated_battle_battlefield_overlay_content.h`
   **已经有**原版 field/movegrid 两张 32×32 tilemap（`std::array<std::uint16_t, 1024>`，
   由 `tools/generate_butano_battlefield_overlay.py` 对着已签 manifest 失败关闭地生成）⇒ **不用再生成数据**。
2. 在 `battle_range_overlay::update` 的移动/目标分支里，把 map 的 30×20 可见窗口按
   `map[(r*32)+c] ← 原版 tilemap[((r+3)%32)*32 + ((c+30)%32)]` 写进去（块号换成第 ① 步的新块号）。
3. 动作/命令菜单分支**保持现状**（它写 `_status_cells`／`_populate_action_cells`），
   但要注意：**菜单字形与布局图共用同一套图块与同一张 map**，改块预算时不能覆盖 25..52。
4. 混合、优先级、调色板**一个字都不动**。

**验收（必须实跑）**
```bash
bash tools/butano/build.sh
/usr/local/bin/python3 tools/butano/capture_s49_advance.py --out-dir <新目录> \
  --rom butano-sequel/butano-sequel.gba --keys "Down,Down,A*32" \
  --zero-input-frames 240 --settle-frames 90 --hold-frames 4 --label <名>
# 差分：对照 artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-19-A.png，
#      战场区 (0,0,240,128) 逐像素不等计数，取 walk 内最小值
```
基线 **2,917**。**更差就立刻回滚**（`git restore` 源码 + `bash tools/butano/build.sh`，
ROM 必须回到 `02bf3573…`）。

### 第 ③ 步：把「烘焙图」换回「按状态重算的等价规则」（长线）

**为什么**：第 ② 步装的是**某一个光标位置**的原版烘焙图；光标一动，原版会重写那 212 项。
要做成通用机制，得把原版的烘焙规则反推出来：
- 受阻区（`B`）是烘焙布局的一部分（含 HUD 带、左右边界、若干竖带）——**它到底是规则还是随地图烘焙的，尚未闭合**；
- 网格网（`#`）的 1 px 线规则已部分闭合（偶/奇列变体）。

**门禁要跟着改**：`tests/test_s49_overlay_screentruth.py` 里
`PINNED_RESIDUAL_BY_FAMILY` 会因第 ② 步而变 ⇒ **必须改成新的实测值**，
不允许为了让测试变绿而放宽断言。

## 3. 风险清单

| 风险 | 处置 |
| --- | --- |
| 菜单字形（块 25..52）与布局图共用图块预算 | 重新编号时把菜单块单独留出区间 |
| `battle_range_overlay` 同时服务移动/目标/动作/命令四种相位 | 每相位分别验证；命令菜单门禁 `tests/test_s49_command_menu_*` 必须保持绿 |
| 装原版 tilemap 后，`map` 里可见窗口之外的 2 行 2 列仍是旧内容 | 填 0 并在门禁里钉住 |
| VRAM | 不增反减 1,600 B ⇒ 不是约束 |

## 4. 尚未闭合（不阻塞第 ① ② 步）

- 原版受阻区是**规则**还是**随地图烘焙的产物**（第 ③ 步要做）；
- 描边色三角波的**相位对齐**：原版 `global` 从上电起每帧 +1（上电读数 0、战斗入口 998,060 ≡ 44 (mod 64)），
  重制要逐帧一致就必须与原版**在同一游戏时刻同相位**，不只是波形相同。
  见 `notes/s49-outline-triangle-counter-20261021.md`；
- 屏①结算 / 屏②升级仍未录到（`round_limit = 8`）。

## 5. 【可执行级规格】第 ①② 步的精确改法（第 26 轮已把数据侧做完）

### 5.1 ✅ 数据侧已完成（不用再做）

`tools/generate_butano_battlefield_overlay.py` 现在**同时**产出两个头文件：

| 产物 | 内容 | 状态 |
| --- | --- | --- |
| `generated_battle_battlefield_overlay_content.h` | 原版 field/movegrid 两张 32×32 tilemap（`std::array<std::uint16_t,1024>`） | ✅ 已有 |
| `generated_battle_battlefield_overlay_tiles.h` | **原版 32 块展开成 8bpp**：`battle_battlefield_overlay_tiles_8bpp`（`std::array<std::uint8_t,2048>`，32 块 × 64 B） | ✅ **本轮新增** |

展开规则（已逐块复核）：原版调色板索引 `v` → 重制调色板索引
`0`（v=0 透明）、`224+v`（v=1..11，即 **225..235**）、`0`（v=12..15）。
实测：块 262 全 226、块 279 = 234 填充 + x=7 处 235、块 258 = 透明 + x=7 处 225 ✔
⇒ **低半字节 = 左像素**（第 26 轮更正）。

### 5.2 块预算：**原版 6 族 × 4 变体 = 24 块，正好等于重制现有的 24 块**

原版每族 4 个变体 = 该 16×16 逻辑格的 4 个 8×8 块（无边 / 右边 / 下边 / 两边）：

| 原版块 | 族 | 变体 | 重制 kind | 重制块号 |
| --- | --- | --- | --- | --- |
| 258..261 | 网格网（透明 + 1 px 线） | 4 | `grid` | 1..4 |
| 262..265 | 移动透镜（青 + 深蓝边） | 4 | `move` | 5..8 |
| 266..269 | 攻击/光标（橙） | 4 | `attack_range` | 9..12 |
| 270..273 | 光标（黄） | 4 | `cursor` | 13..16 |
| 274..277 | 目标（绿） | 4 | `target` | 17..20 |
| 278..281 | 受阻区（深灰 + 暗边） | 4 | `blocked` | 21..24 |

原版块 **256/257/282..287** 全透明 ⇒ 一律映射到重制块 **0**。

⇒ **菜单字形 25..52 原样不动**（`battle_range_ui_action_first_tile=25`、
`battle_range_ui_action_end_tile=53`、`battle_action_ui_map_tile` 枚举的 25/26/27/28 **都不用改**）。
⇒ 新块预算：**52 个逻辑块 = 104 个存储块 = 3,328 B**（现在是 77 块 / 154 存储 / 4,928 B）
⇒ **VRAM 净省 1,600 B**。

### 5.3 要改的代码（三个文件）

**(1) `butano-sequel/game/include/konoha/battle_range_ui_style.h`**
- `battle_range_ui_logical_tile_count`：77 → **52**
- `battle_range_ui_storage_tile_count`：154 → **104**
- 新增：族的首块号表（grid=1, move=5, attack_range=9, cursor=13, target=17, blocked=21）
  与 `battle_range_ui_original_tile_index(int original_tile)`：
  `original_tile` 在 258..281 → `first_tile[family] + (original_tile - family_first)`；
  否则 → 0。
- 旧的 `battle_range_ui_tile_index(kind, tx, ty)`（按 4×2 排布）与 `battle_range_ui_cell_kind(...)`
  **在新的「装原版烘焙窗口」路径下不再使用**；可以保留定义，但
  `tests/test_butano_battle_ui_runtime_wiring.py` 里有三处断言
  （第 221/242/656 行附近）钉着它们出现在场景源码里
  ⇒ **要么保留一次调用点，要么同步改这三处断言**（改动架构时改断言是合法的，
  但必须写清「为什么」，不许为了绿而弱化）。

**(2) `butano-sequel/game/src/battle_runtime_scene.cpp` 的 `_prepare_tiles`**
- 改成：从 `battle_battlefield_overlay_tiles_8bpp` 把 6 族 × 4 变体写进块 1..24
  （每块 64 B，块 k = 原版 256+k' 家族映射后）；
- 菜单字形那段（写 25..52）**保持原样**。

**(3) `battle_runtime_scene.cpp` 的 `update()` 移动/目标分支**
- 现在的「按格点算 kind 再写 4×2 块」整段换成**装原版烘焙窗口**：
  对屏幕格 (col, row)（0..29 × 0..19），
  原版 tilemap 格 = `((row + 3) % 32, (col + 30) % 32)`
  （hoff=240/8=30、voff=24/8=3 折进索引，因为重制层没有滚动），
  该项的块号 = `battle_range_ui_original_tile_index(entry & 0x3FF)`；
  写进 `_cells[row * columns + col]`；可见窗口之外的格填 0。
- 动作/命令菜单分支**保持原样**（它们写 `_status_cells` / `_populate_action_cells`）。
- 混合权重、优先级、调色板**一个字都不动**。

### 5.4 验收与门禁更新

- 基线 **2,917**（当前 ROM `02bf3573…`，录像 `artifacts/s49-remake-walk-20261021-v1/`）。
- 装原版烘焙窗口后，**2,317 px 的漏画与 600 px 的粒度问题应当同时消失**；
  残差应当大幅下降（若降到 0 附近，说明 1:1 达成）。
- `tests/test_s49_overlay_screentruth.py` 里
  `PINNED_RESIDUAL_BY_FAMILY` / `PINNED_RESIDUAL_TOTAL` / `PINNED_RESIDUAL_CELLS`
  **必须改成新实测值**（只能改成真测出来的数；不许放宽）。
- 还要新增/更新一条门禁，钉住「重制覆盖层在移动相位画出的图块集合 == 原版烘焙窗口的图块集合」。

## 6. ⚠️ 第 26 轮末：第 ①② 步**已实施并被实测否证**（已回滚）

按 §5 的规格实施了三处改动（块预算 77→101、原版 24 块放 77..100、移动相位装原版烘焙窗口），
实测 **2,917 → 16,533（变差 13,616）**，且没有任何一帧变好 ⇒ **已回滚**，
源码回到基线，ROM 逐字节回到 `02bf3573…`。

失败实验的收据保留在 `artifacts/s49-remake-walk-20261021-v2/`（含 `baseline.json` 逐帧数），
完整分析见 `notes/s49-overlay-1x1-implementation-20261021.md`。

**已排除**：install 公式错、8bpp 展开数据错、滚动折进索引错（三者都用 Python 复算/逐块核对过）。
**症状**：整个战场被一层 16 px 间距的青色网格覆盖 ⇒ 网格网族被画到了所有格上。
**下一步**：**先读重制侧 VRAM**（`tools/butano/capture_s49_gpu_state.py`）核对
(a) 槽 77..100 的图块字节、(b) 可见窗口 30×20 的 tile index、(c) 8bpp 图块区的上传长度/基址对齐；
再据结果修。门槛不变：**≤ 2,917 且任何一帧都不得变差**。
