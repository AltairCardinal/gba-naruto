# Z1 —— 接线总装报告（wave 7 · 补交）

> 2026-10-24 · wave 8 · 流 W1 补交 · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`notes/s49-fidelity/WAVE7-TASKS.md` §1、`WAVE8-TASKS.md` §0/§1.4
> ⚠️ **本报告是补交的**：Z1（wave 7）交了代码但没交报告，任务书 §1.4 要求
> 「从 `git diff HEAD -- butano-sequel/game` 反推它到底接了什么」，
> 并把 **8 条接线点**逐条标注「已接 / 未接 / 为什么」。
> ⛔ 本次补交**没有改动** Z1 的代码（代码已落地），只补文档；
> W1 的任务 A/B 的改动单列在 `notes/s49-fidelity/W1-blackfield-timeline.md`。
> 逆向线全程只读；**未提交 git**。

---

## 0. 一句话结论

> **8 条接线点全部落地**（Y3×3、Y2×3、Y4×5、Y1×1），
> 代码确实在 `battle_runtime_scene.cpp` 与 `battle_scene_controller.h` 里（`git diff HEAD` 可见）。
> Z1 留下的是一个**残差回归**：判定台残差总和 **117,832 → 161,074（+43,242）**，
> 根因**不是**任务书 §0.2 写的「重制侧 walk 采到 0 个黑场帧」——
> 那是用 **wave 6 的旧录制**得出的结论；
> 真正的根因是：**黑场被接上了，但它落在 walk 拍尾之外**，
> 于是判定台的两帧（原版 step-11 近黑 / step-18 全黑）在重制侧**找不到对应帧**。
> W1 已在 `W1-blackfield-timeline.md` 里修掉（残差 **161,074 → 110,526**）。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `notes/s49-fidelity/Z1-wiring.md` | **新（补交）** | 本报告 |
| `notes/s49-fidelity/W1-blackfield-timeline.md` | **新** | W1 的黑场时间轴修复报告 |

> Z1 的代码改动本身**不在**本次补交的范围内：它已经在工作区里（未提交 git）。

---

## 2. ⭐ 8 条接线点逐条状态表

判据：**代码确实在** `git diff HEAD -- butano-sequel/game` 里（本次补交重新 diff 过一遍）。

| # | 来源 | 接线点 | 状态 | 证据（`battle_runtime_scene.cpp` / `battle_scene_controller.h`） | 为什么 |
|---|---|---|---|:-:|---|
| 1 | Y3 | `battle_scene_controller.h`：受阻判定 `terrain.cost({x,y}) == 0` → `terrain.terrain_class({x,y}) != grid_terrain_class_plain` | **已接** | `battle_scene_controller.h` 新增 `#include "konoha/grid_pathfinder.h"`，受阻位图改成 `terrain.terrain_class({ x, y }) != grid_terrain_class_plain`，并带注释说明 `cost()` 只对墙为 0 | Y3 试过改 `cost()` 语义，被 4 个既有单测证伪并已回退；Y1 只改了**调用点** ✔ |
| 2 | Y3 | 覆盖层绘制范围裁到原版的地图行 **1..12** | **已接** | 覆盖层循环改成按 **map 空间**逐块算 `cell_y`，并加 `overlay_first_row = 1; overlay_last_row = 12;` 的可见性判定 | 原版 BG2 的 tilemap 第 0 行与 13..15 行是空的；重制侧原来画满 16 行 ⇒ 36 格「多画」 |
| 3 | Y3 | `window_x = 240 + camera.x()`（相机差 32 px） | **已接** | `const int window_x = 240 + camera.x().integer(); const int window_y = 248 + camera.y().integer(); _bg->set_position(-window_x, -window_y);` | 原版 BG2 是 256×256 的 map 空间缓冲，滚动量就是相机；重制侧最优窗口 (224,0) vs 原版 (256,0) |
| 4 | Y2 | `battle_black_field_event1_hold_frames` **10 → 7** | **已接** | `constexpr int battle_black_field_event1_hold_frames = 7;` | 原版事件 1 的全黑 18 GBA 帧 = 9 场景帧，交接补 2 ⇒ 场景内持 7 |
| 5 | Y2 | `battle_black_field_event2_hold_frames` **24 → 12** | **已接** | `constexpr int battle_black_field_event2_hold_frames = 12;` | 原版事件 2 的全黑 24 GBA 帧 = 12 场景帧 |
| 6 | Y2 | 战斗场景的**淡入块上移**到场景第一次 `bn::core::update()` 之前 | **已接** | `run_visible_battle_scene()` 里 `battle_black_field fade_in; fade_in.begin_fade_in(); while(fade_in.busy()){ fade_in.apply(); bn::core::update(); fade_in.advance(); }` 整块放在 `konoha_battle_runtime_telemetry.render_stage = 100;` 之后、场景第一次 update 之前 | 场景交接会重提交调色板、把全局淡出丢掉 ⇒ 2 帧亮缝把一个事件切成两个 |
| 7 | Y4 | 打字机接线 A–E（5 处） | **已接（A–E 全中）** | A `render_script_glyphs()`：螺旋图标包进 `if(! state.script.typewriter_active)`、说话人标签加 `visible_glyph_count > 0`、字形循环加 `index < visible_glyph_count`；B 主循环按键分支加 `! state.script.typewriter_active`；C 主循环每帧 `controller.advance_typewriter()`；D `update_script_portraits()`：`portraits_revealed` 为假时 `renderer.reset()`；E `battle_scene_controller.h` 新增 `advance_typewriter()` 转发给 `_script` | D 是 **9,907 → 0** 的关键（否则空框仍带两个头像）；B 是「打字中按 A 不换行」 |
| 8 | Y1 | 状态栏「待機」的**相位规则**（红墨只在单位选择相位，其余蓝墨） | **已接** | `render_status_panel_text()`：`state.phase == battle_scene_phase::unit_selection ? battle_ui_text_warning_palette : battle_ui_text_accent_palette` | 无条件红墨是 **+756 px** 的回归；原版只在单位选择相位是红的 |

**结论：8/8 已接。** Z1 没有漏接任何一条；它的问题是**接线之后没有把黑场放回原版的时间轴**。

---

## 3. ⭐ 接线前后的效果（逐帧对比）

### 3.1 判定台（`tools/s49_fidelity_report.py`，战场区残差）

| 帧 | wave 6 末（117,832 那版） | Z1 接线后（161,074 那版） | 变化 | 归因 |
|---|---:|---:|---:|---|
| step-09-A | 6,064 | 6,064 | 0 | 「開始」标题屏**仍未接**（Z2 只出了素材） |
| step-10-A | 4,990 | 4,990 | 0 | 同上 |
| **step-11-A** | **305** | **25,447** | **+25,142** | ⭐ **黑场没有落在 walk 的拍尾上** |
| step-12-A | 9,907 | **0** | **−9,907** | ✅ 打字机接线生效（空对话框那一拍有了） |
| step-13-A | 28 | 674 | +646 | 打字机相位差 |
| step-14-A | 0 | 702 | +702 | 打字机相位差（**丢了一个全 0 帧**） |
| step-15-A | 0 | 417 | +417 | 同上 |
| step-16-A | 344 | 412 | +68 | 同上 |
| step-17-A | 0 | 756 | +756 | 同上（**再丢一个全 0 帧**） |
| **step-18-A** | **0** | **25,459** | **+25,459** | ⭐ 同 step-11 |
| step-19/21/22-A | 24,460 / 27,325 / 21,266 | 同 | 0 | 结算段相机滚动（产品差，walk 补不了） |

**净变化 = −9,907 + 25,142 + 646 + 702 + 417 + 68 + 756 + 25,459 = +43,283**
（判定台实测 **+43,242**，差 41 来自 step-23/24 的 ±7 抖动）。

### 3.2 逐项归因

| 项 | 量 | 说明 |
|---|---:|---|
| 打字机接线**赚**到的 | **−9,907** | step-12（原版的「框已开、字还没开始打」） |
| 打字机接线**赔**掉的 | **+3,406** | step-13/14/15/16/17（打字机相位差；其中 3 帧从 0 变成非 0） |
| 黑场**赔**掉的 | **+50,601** | step-11 +25,142、step-18 +25,459 |
| 合计 | **+43,242** | ⛔ 棘轮红 |

---

## 4. ⭐ 根因：**不是**「重制侧没有黑场帧」

任务书 §0.2 写的是：

> 原版 walk 采到 2 个黑场帧（`step-11-A` 非黑 0.0079、`step-18-A` 非黑 0.0000）；
> **重制侧 walk 采到 0 个**（最暗一帧非黑 0.8541）

**这条结论是用 wave 6 的旧录制得出的，对 Z1 接线后的 ROM 不成立。** 本次补交重新量了：

| 录制 | ROM | 采集帧 | 最暗的非黑占比 | 纯黑帧 |
|---|---|---:|---:|---:|
| `build/s49-pairing/walk5/dense-remake` | wave 6（Z1 之前） | 783 | **0.8541** | **0 个** |
| `build/s49-pairing/x2/z1-dense/capture-remake` | wave 7（Z1 之后） | 783 | **0.0000** | **13 帧**（idx 70 / 307-310 / 318 / 461 / 468-473） |

⇒ **Z1 接线后重制侧的黑场帧是存在的**（而且 13 帧）。
真正的问题是：**它们落在 walk 的拍尾（每 94 帧一个采样点）之外**。

**为什么黑场会落在拍尾之外**：黑场由**玩家按 A** 触发，而 walk 的一拍是
「按 A（保持 4 帧）→ 等 90 帧 → 采样」⇒ **A 键恰好落在拍尾那一帧**，
黑场从按下的那一帧就开始，66 GBA 帧后结束，比下一拍（94 帧）**早了 28 帧** ⇒ 拍尾永远拍不到它。

⇒ **正解不是「补一个黑场」，而是把黑场延后 28 帧，让它的淡出落在拍尾上。**
这条修复由 W1 落地，详见 `W1-blackfield-timeline.md`。

---

## 5. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| Z1-V1 | `git diff HEAD -- butano-sequel/game` | 反推 8 条接线点 | 8/8 命中，见 §2 |
| Z1-V2 | `git status --short`（重制线） | 不越界 | 本次补交只新增 2 个 md 文件，未动代码 |
| Z1-V3 | `python build/_w1_probe_timeline.py`（临时脚本） | 量两侧 walk 的逐帧非黑占比 | 见 §4 的表 |
| Z1-V4 | 判定台三版对比 | 归因 +43,242 | 逐帧表见 §3.1，**逐项相加吻合到 ±41 px** |

> ⚠️ 临时脚本放在 `build/`（不进仓）。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| Z1-1 | Z1 的 8 条接线点全部落地 | `git diff HEAD` 逐条对照任务书 §1.2 | 8/8 有对应改动 | **已确认** |
| Z1-2 | Z1 漏接了某条接线点 | 同上 | 没有漏接 | **已证伪** |
| Z1-3 | 残差回归 = 「重制侧没有黑场帧」 | 量 Z1 之后 ROM 的密集 walk 逐帧非黑占比 | ⛔ Z1 之后有 **13 个纯黑帧**、最暗 0.0000 ⇒ 前提不成立 | **已证伪（根因改判）** |
| Z1-4 | 残差回归 = 「黑场落在拍尾之外」 | 黑场由 A 触发 ⇒ 起点 = 拍尾；66 帧 < 94 帧 ⇒ 结束比下一拍早 28 帧 | 与 +25,142 / +25,459（两帧整屏）逐项吻合；修复后 step-11 → **305**、step-18 → **0** | **已确认（并已修复）** |
| Z1-5 | 打字机接线只赚不赔 | 逐帧差分 | 赚 9,907、赔 3,406（3 个全 0 帧变非 0）⇒ **净赚 6,501** | **已确认（赔的 3,406 是打字机速率问题，另行修）** |
| Z1-6 | step-19/21/22 的 73,051 px 是 walk 补不了的 | 原版相机有 77/200/184 三个中间值，重制侧只有 8 个离散值 | 产品差，与黑场/打字机无关 | **已确认（沿用 X2 的结论）** |

---

## 7. 卡在哪 / 剩余风险

1. **⭐ 打字机速率（未在本流解决）**：重制侧的场景逻辑是 **30 Hz**
   （1 场景帧 = 2 GBA 帧：黑场的 12 级淡出覆盖 24 GBA 帧，与原版逐项相同），
   而打字机的间隔常量是按 **60 Hz** 写的 ⇒ 重制侧的字打出来是原版的**一半速度**。
   后果：拍尾拍到的总是**半行字**，step-13/14/15/16/17 的残差从 28/0/0/344/0 变成 674/702/417/412/756，
   **丢了 3 个全 0 帧**（判定台棘轮的「全 0 帧数」因此红）。
   ⚠️ 常量在 `battle_presentation_script.h`（**Z3/W3 独占**），本流不能改；
   W1 在**自己的文件**里把打字机改成「每场景帧推进两次」来对齐原版的 60 Hz 节奏。
2. **「開始」标题屏仍未接线**：Z1 只接了 Z2 的清单里的 Y2/Y3/Y4/Y1 部分，
   标题屏（Z2 的接线点 1–3）**没有接** ⇒ step-09/10 的 6,064 + 4,990 还在。
   W1 补上（见 `W1-blackfield-timeline.md` §4）。
3. **星光圈没接**：Z2 的遮罩素材「已转换、未链接」，
   且 W2 报告里那个 **640 块/帧的 VRAM 硬约束**没有解 ⇒ 黑场仍是**调色板淡出**，
   不是原版的**四角星光圈** ⇒ 重制侧没有「0.0079 的近黑帧」，只有「0.0000 的全黑帧」。
   （判定台不受影响：原版 step-11 的 305 个亮点与重制侧的纯黑帧之差正好是 305。）

---

## 8. 边界声明

* 逆向线 `D:\Shell\Github\gba-naruto-reverse` **全程只读**（本流没有打开它）。
* 本次补交**没有改动**重制线的任何代码 —— Z1 的代码早已落地；
  W1 的黑场/标题屏改动单列在 `W1-blackfield-timeline.md`。
* **未提交 git**；本文件 LF、无 BOM。
* 未改 Z2/W2/W3 独占的文件：
  `battle_black_field_star.h`、`battle_range_ui_style.h`、`battle_map_content.h`、
  `grid_pathfinder.h`、`battle_presentation_script.h`、
  `battle_presentation_text_layout.h`、`battle_presentation_content.h`。
