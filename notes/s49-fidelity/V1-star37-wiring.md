# V1 —— 星光圈 37 级接线（**补交**，wave 9 · 流 V1）

> 2026-10-24 · wave 10 · 流 U1 **补交** wave 9 流 V1 的报告
> 原始任务：`notes/s49-fidelity/WAVE9-TASKS.md` §1（流 V1）
> 反推方法：`git -C D:\Shell\Github\gba-naruto-butano diff HEAD -- butano-sequel/game`
> + 未跟踪文件清单 + 运行时实测
> ⛔ V1 未改任何本流以外的文件；本补交由 U1 写，**逆向线全程只读**；**未提交 git**

---

## 0. 一句话结论

> **V1 交了「资产 + 接口 + 接线点」三件套，但接错了坐标：**
> `battle_black_field_star_mask.h` 用**屏幕绝对坐标**调 Butano 的 `create_sprite()`，
> 而 Butano 的 `create_sprite()` 是**屏幕中心相对**的 ⇒ 整个遮罩整体偏出 (120, 80)，
> **只盖住屏幕的右下角** ⇒ 原版黑场从来没有变黑 ⇒ 判定台残差从 **109,597 回归到 159,697**。
> 第二个缺陷：37 级里的**生长 12 级（25..36）做成了「默认关」的开关**，
> 于是重制侧的黑场比原版短 24 GBA 帧，过渡整体错位。
> **两个缺陷在 wave 10 由 U1 修掉（U1 报告），残差回到 100,210、全 0 帧 2 → 5。**

---

## 1. V1 的任务（`WAVE9-TASKS.md` §1.2 / §1.3）

| # | 任务 | 交付要求 |
|---|---|---|
| A1 | 星光圈 **37 级**资产 | 补上缺的 12 级（帧 1079–1102） |
| A2 | 16×16 碎片 + 32×32 纯黑块布局 | 每级 ≤ 224 块 OBJ 图块 / ≤ 87 精灵 |
| A3 | **接线** | include + 场景成员 + 每级 `set_level()` + 结束 `clear()` |
| A4 | 调色板淡出与星光圈**二选一** | 原版是「洞」不是「变暗」⇒ 淡出要关 |
| A5 | 生长 12 级 | **最终必须是打开且残差不回归** |
| B1 | 覆盖层：**只画地图行 1..12** | `battle_runtime_scene.cpp` |
| B2 | 覆盖层：相机锚点 224 → 256 | 与 V2 协同（V2 负责机制） |
| B3 | 覆盖层：`overlay_blocked()` | 归 V2，V1 只写交接清单 |

---

## 2. 接线点逐条状态（从 `git diff HEAD -- butano-sequel/game` 反推）

### 2.1 已接 ✔

| # | 接线点 | 落在哪里 | 状态 |
|---|---|---|---|
| A1 | 37 级的级别表 | `game/include/konoha/battle_black_field_star.h`：`level_count = fade_levels*2 + 1 + growth_levels = 37`、`visible_pixels` 37 项、`black_level = 12` | **已接**（文件是 W2 产的，V1 只引用） |
| A2 | 摆放表 | `game/include/konoha/battle_black_field_star_table.h`（W2 生成，37 级 × `max_blocks` 40 / `max_cells` 94 补齐） | **已接** |
| A3-a | include | `battle_runtime_scene.cpp:120` `#include "konoha/battle_black_field_star_mask.h"` | **已接** |
| A3-b | 场景成员 | 部署场景 `star_mask`（`battle_runtime_scene.cpp:7487`）+ 战斗场景 `star_mask`（`:7885`） | **已接**（两处都要：黑场跨场景交接） |
| A3-c | 换级 | 部署场景 `star_mask.set_level(black_field.star_mask_level())`（`:7572`）、战斗场景淡入 `set_level(fade_in.star_mask_level())`（`:7923`）、战斗主循环 `set_level(black_field.star_mask_level())`（`:8901`） | **已接** |
| A3-d | 收尾 | `star_mask.clear()`（`:7576` / `:7927` / `:8909`） | **已接** |
| A4 | 调色板淡出**关掉** | `game/include/konoha/battle_black_field.h`：`apply()` 变成空函数、`clear()` 变成空函数 | **已接** ✔（这一条 V1 做对了） |
| A5 | 生长 12 级的**接口** | `battle_black_field_timing.h`：`star_mask_level()` 的 `stage::growth` 分支 = `black_level + 1 + fade_in_levels + _frame / frames_per_level` ⇒ 25..36 | **接口已接** |
| B1 | 只画地图行 1..12 | `battle_runtime_scene.cpp`：`overlay_first_row = 1` / `overlay_last_row = 12` | **已接** |

### 2.2 未接 / 接错 ✘

| # | 接线点 | 状态 | 原因 / 证据 |
|---|---|---|---|
| **A3-e** | ⭐ **遮罩的屏幕坐标** | **接错（致命）** | `battle_black_field_star_mask.h` 的 `set_level()` 调 `create_sprite(placement.x + 16, placement.y + 16)`，而 `placement` 是**屏幕绝对**的表格坐标；Butano 的 `create_sprite(x, y)` 把精灵格中心放在 **(120 + x, 80 + y)** ⇒ 整个遮罩偏出 (120, 80)。**实测**：黑场帧里只有右下角是黑的（`build/s49-u1/bench/capture-remake/step-14-A.png`），原版那一帧是**全屏四角星光圈**。⇒ 遮罩只盖住屏幕右下角 ⇒ **黑场从来没有变黑**。 |
| **A5** | ⭐ **生长 12 级打开** | **未接（做成了默认关的开关）** | `battle_runtime_scene.cpp`：`constexpr bool battle_black_field_event1_growth = false;`，只在战斗场景的淡入里 `if(battle_black_field_event1_growth) fade_in.enable_growth();`。注释写明「growth 打开后残差从 109,597 涨到 159,310 ⇒ 做成开关」。**wave 10 的验收要求「不许拿『默认关』当最终交付」**。 |
| **A2'** | 37 级**素材进 ROM** | 已接 ✔ | `nm butano-sequel.elf \| grep star_mask` ⇒ `battle_black_field_star_mask16_bn_gfxTiles` / `_block32_bn_gfxTiles` 都在。 |
| **B2** | ⭐ 覆盖层**相机锚点 224 → 256** | **未接** | V1 交付的树里，2221–2266 仍是**相机派生窗口**（`window_x = 240 + camera.x()`、`map_px_x = layer_px_x + 256 * ceil_div(window_x - layer_px_x, 256)`）。V2 在 wave 9 另落了 `battle_map_visual_projection.h` 的地图空间锚点 API（锚点 256,0），但**没有人把它接到运行时** ⇒ 覆盖层的内容仍然跟相机滑。**wave 10 由 U1 接线**（接线点 ④）。 |
| **B3** | `terrain.overlay_blocked()` | 已接 ✔（V2 代做） | `battle_scene_controller.h` 已改用 `terrain.overlay_blocked({x, y})`（V2 落的地，V1 只该写清单）。 |

### 2.3 V1 完全没碰的

* `battle_presentation_script.h` / `battle_presentation_content.h` / `battle_presentation_text_layout.h` / `battle_opening_title.h`（V3 独占）—— V1 未碰 ✔
* `battle_map_visual_projection.h` / `battle_scene_controller.h`（V2 独占）—— V1 未碰 ✔
* 逆向线 —— V1 未碰 ✔

---

## 3. 前后对比表（判定台 `s49_fidelity_report.py`，原版侧复用同一份捕获）

| # | 状态 | 残差总和 | 全 0 帧 | 变化 |
|---|---|---:|---:|---|
| 0 | **HEAD**（wave 9 之前：调色板淡出、无遮罩、无对话字形、标题出屏） | **109,597** | **2** | 钉住的基线 |
| 1 | **V1 交付的树**（遮罩接线但位置错、生长关）+ U1 的标题/对话修复 | **159,697** | 3 | **+50,100** ⇦ **V1 的回归** |
| 2 | + **遮罩坐标修正**（`create_sprite` 减屏幕中心） | 114,304 | 3 | −45,393 |
| 3 | + **生长 12 级打开**（37 级全用） | 104,784 | 3 | −9,520 |
| 4 | + 事件 2 引线 24 → 19 场景帧 | 100,314 | 3 | −4,470 |
| 5 | + 事件 1 引线 36 → 38 场景帧 | **100,210** | **5** | −104 |

**全屏残差（full residual，含对话框里的文字）**：
基线 **209,745** → 第 5 行 **197,875**（−11,870）；
对话的 5 屏（判定台步骤 12/13/14/15/17）的 full residual **全部为 0**
（基线是 1265 / 1365 / 781 / 635 / 1449）⇒ **对话框里的文字也逐像素等于原版**。

> **V1 引入的回归 = 第 1 行与第 0 行之差 = +50,100 px。**
> 根因不是 V1 注释里写的「生长阶段移位了时间轴」，而是**遮罩画在了屏幕外**
> ⇒ 黑场不黑 ⇒ 判定台的两个黑场帧（原版 step 11 / step 18）与重制侧差 25,000 px 量级。
> 生长开关只是**第二**个缺陷（第 3 行 −9,520 px 是把它打开后**赚回来**的）。

**V1 注释里记的 159,310 与上表第 1 行的 159,697 不是同一棵树**：
V1 的 159,310 是**生长打开**时测的（wave 10 任务书 §0.3 转述），
159,697 是 U1 接手时测的（生长**关**、且已含标题/对话修复）。

---

## 4. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| V1-1 | V1 把遮罩接线点全部落到位了 | `git diff HEAD -- butano-sequel/game` 逐条比对 §1.2 的清单 | include / 成员 / 换级 / 收尾 / 淡出关闭 / 行 1..12 **都在**；**遮罩坐标与生长开关是缺的** | **部分确认** |
| V1-2 | V1 的 159,310 是「生长打开」造成的 | 读 V1 留下的注释 + wave 10 任务书 §0.3 | 注释明写是 growth ⇒ 但真正的 +50,100 是**遮罩出屏** | **已证伪（主因不是生长）** |
| V1-3 | 遮罩的 `placement` 是屏幕绝对坐标 | 读 `battle_black_field_star_table.h` 的注释「the top left corner of the cell, in pixels」+ `set_level()` 的加法 | 绝对坐标 ✔ | **已确认** |
| V1-4 | Butano 的 `create_sprite()` 是屏幕中心相对 | 对照消息窗黑条 `create_sprite(-90 + i*60, 12)` 铺满全屏宽、推进图标 `create_sprite(105, 67)` → 屏框 (217,139) | 中心相对 ✔（V3 对标题的同一结论） | **已确认** |
| V1-5 | 遮罩整体偏出 (120,80) ⇒ 黑场不黑 | 录一帧黑场看像素 | `step-14-A.png` 里只有右下角黑，屏框 (41,49)-(205,112) 全亮 | **已确认（根因）** |
| V1-6 | 修正坐标后 25 级（淡出 12 + 黑 1 + 淡入 12）逐级可见像素与原版一致 | `build/s49-u1/compare_levels.py`（新仪器） | **37 级全部对上，最大偏差 104 px**（偏差来自重制侧战场内容与原版不同） | **已确认** |
| V1-7 | 生长 12 级打开后残差不回归 | 判定台复跑 | 104,784（比 V1 的 159,697 好 55k） | **已确认（生长该开）** |
| V1-8 | 黑场两个引线常量是黑场对齐的唯一旋钮 | 把引线各改一档复跑判定台 | 事件 2：24→19 得 −4,470；事件 1：36→38 得 −104 且全 0 帧 3→5 | **已确认** |

---

## 5. 交付物（本流 V1 的产物，全部在盘上）

| 路径 | 性质 | 说明 |
|---|---|---|
| `…/butano-sequel/game/include/konoha/battle_black_field.h` | 改 | 调色板淡出**关掉**（`apply()` 空函数）、`clear()` 空函数、`star_mask_level()` |
| `…/butano-sequel/game/include/konoha/battle_black_field_timing.h` | 改 | 37 级的 `star_mask_level()` 映射（含 `stage::growth`） |
| `…/butano-sequel/game/include/konoha/battle_black_field_star.h` | 改 | 37 级的常量 / 计数 / `visible_pixels`（W2 产的表，V1 引用） |
| `…/butano-sequel/game/include/konoha/battle_black_field_star_table.h` | 新（生成） | 37 级的摆放表 |
| `…/butano-sequel/game/include/konoha/battle_black_field_star_mask.h` | 新 | `battle_black_field_star_mask` 接口 ⚠️ **本流有坐标缺陷（wave 10 修）** |
| `…/butano-sequel/graphics/battle_black_field_star_mask16.{bmp,json}` | 新 | 371 个 16×16 单元（4bpp） |
| `…/butano-sequel/graphics/battle_black_field_star_block32.{bmp,json}` | 新 | 1 个全黑 32×32 块 |
| `…/butano-sequel/game/src/battle_runtime_scene.cpp` | 改 | include / 成员 / 换级 / 收尾 / 生长开关 / 覆盖层行 1..12 |

---

## 6. 未达成 / 剩余风险（**不粉饰**）

1. **V1 的报告直到 wave 10 才补交**，wave 9 的「残差回归 159,310」因此**没有被定位**，
   被当成「生长阶段移位了时间轴」记了一路。真正的根因是遮罩的坐标系。
2. **V1 没有留下任何可复跑的验证记录**（没有捕获、没有 JSON 收据），
   本补交的每一个数字都是 U1 重新测的。
3. **生长 12 级在 V1 交付时是关的**，所以 wave 9 的「37 级」其实只跑了 25 级。
4. V1 的注释里「遮罩画在场景精灵之后 ⇒ 压在前面」的推理是错的但无害：
   遮罩的 `z_order = -1000`（最低 ⇒ 最后画 ⇒ 在最前）才是它压住场景精灵的原因。
5. **覆盖层的相机锚点（B2）V1 没接**，wave 10 才接上。

---

## 7. 边界声明

* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**。
* **未提交 git**；新文件一律 **LF、无 BOM**。
* 本补交只写 `notes/s49-fidelity/V1-star37-wiring.md` 一个文件；
  产品的两处修正（遮罩坐标、生长开关）记在 `notes/s49-fidelity/U1-wiring.md`。
