# Wave 7 任务书 —— 接线总装（把三路的模块真正接上）+ 图形侧补齐 + 出包终审

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 前置：wave 6 四路（Y1/Y2/Y3/Y4）全部交付。
> ⭐ **wave 6 的形状**：Y2/Y3/Y4 三路都交付了「纯逻辑模块 + 精确接线点清单」，
> **所有接线点都落在 `battle_runtime_scene.cpp` 与 `battle_scene_controller.h`** ⇒
> wave 7 的第一件事就是**把它们接上**。

---

## 0. wave 6 交回了什么（**全部已确认，勿重查**）

| 流 | 交付 | ⭐ 关键结论 |
|---|---|---|
| **Y1 崩点必修 + 相机 + 状态栏** | `battle_runtime_scene.cpp` 里的 **per-component 调色板释放**（不再泄漏） | ⭐ **崩点已修**：A/B 复现 X3r 的发现（未打补丁 R×8 崩 / 打补丁 R×9 存活）；⭐ **修复是 pixel-neutral**（25/25 帧逐帧相同，残差加不加都一样）；4096 帧冒烟通过；**单测棘轮 PASS**（20 项失败集合逐名相同，new red = 0） |
| **Y2 「開始」标题屏 + 黑场** | `battle_black_field.h`（重写）+ `battle_black_field_timing.h`（新）+ `battle_opening_title.h`（新）+ 2 个单测；字形美术 `tools/s49_opening_title/*.png` | ⭐ **原版的「淡出/淡入」不是亮度渐变，是四角星光圈的收缩/扩张**（修正上游前提）；黑场已补成 **淡出 24 帧（12 级 × 2 GBA 帧）/ 全黑 / 淡入 24 帧**，**全黑帧 sha256 两侧逐字节相同**；⭐ **标题屏残差投影 5,869 → 264、4,699 → 333**（−95.5 % / −92.9 %）；标题是 **OBJ sprite**（BG 寄存器全同） |
| **Y3 覆盖层** | `battle_range_ui_style.h`（青色只在移动阶段）+ `grid_pathfinder.h`（新增常量）+ 3 条断言；**仪器修复** `tools/s49_overlay_align/compare_overlay_families.py` 与 `tools/s49_fidelity_report/overlay.py` | ⭐⭐ **逐格对拍的验收仪器一直在测垃圾**：`find_overlay_map()` 把 BG **图块图形区**（VRAM `0x00000-0x0FFFF`）当覆盖层 tilemap 解码 ⇒ **此前所有基线数字作废**；修好后首次测出 **地图空间锚点 = map px (256, 0)**、**受阻集 = 地形类别 ≠ plain**（17984/17984 px 逐像素吻合）、**「多画」真因是绘制范围**（原版只画地图行 1..12，重制侧画满 16 行 ⇒ 36 格）；判定台 **overlay 残差 1060 → 857（−19.2 %）**，17/25 帧归零 |
| **Y4 对话打字机** | `battle_presentation_script.h`（打字机本体）+ `battle_presentation_text_layout.h` + `battle_presentation_content.h` + 1 个单测 + **接线补丁** `Y4-dialogue-typewriter-wiring.patch`（`git apply --check` exit 0） | ⭐ 原版 **1 字 / 4 帧**；重制侧整段一次出现（59 帧 / 3 签名）vs 原版 133 帧 / 60 签名；⭐ **缺的那一屏（step-12，9,907 px）不是内容缺、是时序缺** —— 原版那是「框已开、字还没开始打」的**空对话框**（签名 0.805），重制侧从未有过这个时刻；接线后预测签名 **≈48–55**（与原版同量级） |

---

## 1. ⭐ 流 Z1 —— 接线总装（**关键路径**）

### 1.1 独占文件（**只能改这两个**）

* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`
* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_scene_controller.h`

⚠️ `battle_scene_controller.h` **无人独占**（Y3/Y4 都点名要改它）⇒ **归你**。

⛔ **不要改** `battle_range_ui_style.h` / `grid_pathfinder.h`（Y3 已定稿）、
`battle_black_field*.h` / `battle_opening_title.h`（Z2 独占）、
`battle_presentation_script.h` / `battle_presentation_text_layout.h` / `battle_presentation_content.h`（Z3 独占）。
⛔ 逆向线只读。

### 1.2 要接的线（**逐条照抄清单，Y2/Y3/Y4 的报告里有完整细节**）

**Y3（覆盖层，3 处）**
1. `battle_scene_controller.h:2315`：`terrain.cost({x,y}) == 0`
   → `terrain.terrain_class({x,y}) != grid_terrain_class_plain`
   （常量已由 Y3 加好；⚠️ Y3 试过改 `cost()`，**被 4 个既有单测证伪并已回退** ⇒ 不要动 `cost()` 语义）
2. `battle_runtime_scene.cpp:2177-2182 / 2199-2223`：覆盖层**绘制范围**裁到原版那 **12 行**
   （否则 36 格「多画」）
3. `battle_runtime_scene.cpp:2190-2191`：`window_x = 240 + camera.x()`
   —— 重制侧最优窗口 **(224, 0)** vs 原版 **(256, 0)** ⇒ **相机差 32 px**
   （与 Y1 的 G1 相机滚动是同一块地；Y1 的相机工作是否已落地请自己核对）

**Y2（黑场，3 处）**
4. `:189` `battle_black_field_event1_hold_frames` **10 → 7**
   （原版全黑 18 GBA 帧 = 9 场景帧，交接补 2）
5. `:190` `battle_black_field_event2_hold_frames` **24 → 12**（原版 24 GBA 帧）
6. `:7935-7943`：把战斗场景的**淡入块上移**到场景第一次 `bn::core::update()`（约 `:7713`）之前
   —— 否则场景交接时调色板被重提交，**2 帧亮缝**仍在（1521…1522），一个事件仍被切成两个

**Y4（打字机，5 处；补丁已生成，直接 apply）**
7. 补丁 `D:\Github\gba-naruto\notes\s49-fidelity\Y4-dialogue-typewriter-wiring.patch`
   （`git apply --check` 已过）：
   * **A** `render_script_glyphs()`：螺旋图标包进 `if(! typewriter_active)`；
     说话人标签加 `visible_glyph_count > 0`；字形循环加 `index < visible_glyph_count`
   * **B** 主循环按键分支：加 `! state.script.typewriter_active`
     ⇒ **打字中按 A 不换行**（否则整行永远不出现，判定台 0 残差会爆）
   * **C** 主循环（`state = controller.snapshot();` 之前）：每帧调 `controller.advance_typewriter()`
   * **D** `update_script_portraits()`：`portraits_revealed` 为假时 `renderer.reset()`
     ⇒ **这是 9,907 → 0 的关键**（否则空框仍带两个头像，残差 ≈6,000）
   * **E** `battle_scene_controller.h`：加 `advance_typewriter()` 转发给 `_script`

**Y1（状态栏，若 Y1 未完成）**
8. 状态栏「待機」字：Y1 实测原版的「待機」是**红墨 (231,24,0)**，
   但**无条件红是回归（+756 px）** —— 原版只在**单位选择阶段**是红的（别的相位是蓝的）。
   ⇒ 要加**相位规则**，不是无条件改色。

### 1.3 验收

* **构建干净通过**（WSL `make -j4`）；**ROM 4096 帧冒烟不崩**；**R×9 不崩**（Y1 的修法别被破坏）。
* **重录密集 walk**（X2r 的仪器：`tools/s49_pairing/`，⚠️ 密集 walk 的重制侧**与 ROM 绑定，必须重录**）
  ⇒ 判定台残差**必须下降**（当前：总和 **168,392** / 中位 **1940** / 归因 3·14·8）。
  ⇒ 目标：**step-12 残差 9,907 → 0**、**step-09/10 残差 5,869 / 4,699 → 0 附近**、
  **step-19/21/22 残差 24,460 / 27,322 / 20,627 → 0 附近**。
* **逐格族名对拍**：`python tools/s49_overlay_align/compare_overlay_families.py`
  ⇒ 目标 **同亮 192 / 原版缺 0 / 多画 0 / 族名不一致 0**（Y3 的仪器已修好，这次的数字是**真的**）。
* **打字机签名序列**：同一句对话在两侧的签名数与原版同量级（**≈48–55**，原版 60）。
* **单测棘轮**：失败集合与 HEAD 基线**逐名相同**（20 项预存债）⇒ 多出任何一项 ⇒ 变红。
  HEAD 基线：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh`
  工作区：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh`
* ⚠️ **并发构建会互相覆盖** ⇒ 构建若报 `objcopy: Invalid argument` ⇒ 等 60 秒重试（最多 5 次）。

### 1.4 交付物

* `D:\Github\gba-naruto\notes\s49-fidelity\Z1-wiring.md`：报告 + 台账 + **逐项接线前后对比表**。

---

## 2. 流 Z2 —— 「開始」标题屏素材 + 四角星光圈（图形侧）

### 2.1 独占文件

* `D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\`（新素材）
* `…\game\include\konoha\battle_opening_title.h`
* `…\game\include\konoha\battle_black_field.h` / `battle_black_field_timing.h`
* 资源清单 / Makefile 相关（**只新增**，不改既有条目语义）

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h`（Z1 独占）
⇒ **你的接线点写成清单交父代理/Z1**。
⛔ **不要改** `battle_presentation_script.h` / `battle_presentation_text_layout.h` /
`battle_presentation_content.h`（Z3 独占）。
⛔ 逆向线只读。

### 2.2 任务 A：「開始」标题屏素材

* Y2 已把字形抽出来：`D:\Github\gba-naruto\tools\s49_opening_title\{kai,shi,kai-phase1,shi-phase1}.png`。
* 要做的：**转成 Butano sprite item**（⚠️ 「始」高 **70 > 64** ⇒ 需拆两块），
  **先实测 VRAM 余量再放进 `graphics/`**（Y2 故意没放，怕把构建弄挂）。
* 接线清单：Y2 给出的两点 —— 在 `render_deployment_text()` **跳过 READY 四行**
  （原版该处无文字；投影正是靠抹掉这 631 px 才到 264），
  在 `deployment.complete()` 分支改成「**画标题 → 等 A → 走黑场**」。
* 判据：接线后 **step-09 / step-10 残差 5,869 / 4,699 → 0 附近**（Y2 的投影是 264 / 333）。

### 2.3 任务 B：四角星光圈（**真 1:1 的关键**）

* ⭐ **Y2 的决定性发现：原版的「淡出/淡入」不是亮度渐变，是四角星光圈的收缩/扩张**，
  窗口内亮度不变 ⇒ 只做调色板淡出只能做到**结构等价**，**逐帧均值曲线与原版不同**。
* 真 1:1 需要**星形遮罩**：BG 覆盖层 + 对角边 tile 集（缩放/扩张用不同的 tile 排布）。
* 判据：黑场三段（淡出 / 全黑 / 淡入）的**逐帧均值曲线**与原版对齐（不只是段数与级数）。

### 2.4 验收

* 素材已转成 Butano 资源，**VRAM 余量实测**（给出数字）。
* 星形遮罩的逐帧曲线与原版对齐（给出曲线对照）。
* **单测棘轮**（同 §1.3）。
* 交付**接线点清单**。

### 2.5 交付物

* `D:\Github\gba-naruto\notes\s49-fidelity\Z2-title-art-starfield.md`。

---

## 3. 流 Z3 —— 对话框展开动画 + 换行等待

### 3.1 独占文件

* `…\game\include\konoha\battle_presentation_script.h`
* `…\game\include\konoha\battle_presentation_text_layout.h`
* `…\game\include\konoha\battle_presentation_content.h`

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h`（Z1 独占）
⇒ 接线点写清单交父代理/Z1。
⛔ **不要改** `battle_black_field*.h` / `battle_opening_title.h` / `graphics/`（Z2 独占）。
⛔ 逆向线只读。

### 3.2 任务 A：对话框展开动画

* Y4 实测：原版 **0267–0271** 是**斜切展开**的对话框动画（重制侧没有）。
* 判据：重录后那一段与原版逐帧对齐（残差降到 0 附近）。

### 3.3 任务 B：换行等待参数

* 原版换行后**先等 56~92 帧**再打下一行（Y4 未复现，因为它是按画面残差对齐、不是按时刻对齐）。
* ⇒ **先取真值**：逆向线有逐行等待参数（**只读**），
  或用原版密集 walk 的帧号反推。
* 判据：多行对话的签名序列长度与原版对齐（原版 60 / 目标 ≈48–55）。

### 3.4 验收

* 展开动画逐帧对齐。
* 多行对话的等待参数有**实测来源**（不是猜的）。
* **单测棘轮**（同 §1.3）。

### 3.5 交付物

* `D:\Github\gba-naruto\notes\s49-fidelity\Z3-dialogue-box.md`。

---

## 4. 流 Z4 —— 1:1 报告终审 + 出包复跑

### 4.1 独占文件

* `D:\Github\gba-naruto\tools\s49_package\`（流水线 + 打包）
* `D:\Github\gba-naruto\docs\s49-fidelity-report-2026xxxx.md`（报告）

⛔ **不改重制线任何文件**；⛔ 不改任何已有仪器（**只读调用**）；⛔ 逆向线只读。

### 4.2 任务

**(a) 等 Z1/Z2/Z3 落地后重跑 12 步流水线**（`tools/s49_package/run_pipeline.py`），
产出新收据 + 新 manifest。
⇒ ⚠️ **流水线第 2 步的路径 bug 父代理已修**（`git archive --output` 相对路径落在重制仓 ⇒ 改绝对路径）。
⇒ 若 Z1 改动了单测，**棘轮基线要重钉**。

**(b) 更新 1:1 报告**：残差前后对比、逐格族名、音频 event_diff、存档字段表、12 条边界表、
黑场真值表、假设台账索引、**未达成项**（不许粉饰）。

**(c) 未达成项必须包含**：
* 原版 **S49 结算屏真值仍不存在**（四次尝试都没打赢，**未伪造任何帧**）；
* **残差归零的可达性**：X2r 的**可证像素下界 ≈ 23,700**（任何配对都不可能低于此数）
  ⇒ 归零在当前录制上**不可达**；补齐产品缺口后可望降到 **≤ 23,700**；
* 存档**逐字节一致按用户口径排除**（理由：存档字节不是玩家看得见的画面/逻辑状态）；
* 音频**逐采样一致排除**（80–120 h）；
* **20 项单测在 HEAD 即为红（预存债），本次零回归**；
* 四角星光圈 / 对话框展开动画若未补齐，要单列。

### 4.3 验收

* 一条命令跑完流水线，**12 步全绿**，收据 JSON 完整。
* **故意破坏一项 ⇒ 流水线变红**（11 个 selftest 要仍然全红）。
* 报告里每个数字能**追到某次运行**。

### 4.4 交付物

* `tools/s49_package/` + `docs/s49-fidelity-report-2026xxxx.md`（终稿）

---

## 5. 父代理（我）做的事

* **串行接线兜底**：Z2/Z3 若给出接线点而 Z1 没来得及接，我串行合进。
* 残差棘轮监督：任何流声称「残差下降」都要用判定台独立复跑确认。
* 同步 `docs/sequel-roadmap.md` / `docs/s49-three-day-plan.md` / `docs/butano-fidelity-roadmap.md`。

---

## 6. 交回格式

1. **一句话结论**。
2. **改动的文件**（完整绝对路径）。
3. **跑了哪些验证**（命令 + 关键数字）。
4. **假设台账**（表格）。
5. **接线点清单**。
6. **卡在哪**。
7. **新文件一律 LF、无 BOM**；**不提交 git**。

---

## 7. 反循环守则（复述）

* 一次尝试回答一个**是/否问题**；**「还是卡」不是结果**。
* 一次只改一处，跑一次，记一行；结论落进**假设台账**。
* **连续 3 次同样结果 ⇒ 停**，换方法，写进台账。
* 陷住了**换方法/换会话**，不要靠续跑硬扛。
* ⚠️ **并发构建会互相覆盖**（同一个 `butano-sequel.gba`）⇒ **同一时刻只允许一路做构建**。
* ⚠️ **子代理被运行时中断时，产物在盘上但未经验证** ⇒ 接管方必须**重新验证**
  （见 `notes/s49-fidelity/INCIDENT-wave5-task-loss-20261024.md`）。
