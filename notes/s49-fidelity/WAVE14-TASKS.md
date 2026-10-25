# Wave 14 任务书 —— 补两份笔记 + 黑场 + 下界重算 + 出包定稿

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 前置：wave 13 四路（Y1/Y2/Y3/Y4）收口。**12 步流水线已 12/12 全绿**。

---

## 0. wave 13 的真实状态（**全部已确认，勿重查**）

### 0.1 ✅ Y2：覆盖层收尾完成 —— **产品差 = 0**

* 仪器补上**原版侧 480 px 回绕**（一行）⇒ `field`/`movegrid` **同亮 192 / 缺 0 / 多画 0**；
  `banner` **0/0/0/0 exact**；`grid16` 175/0/17/85（原版该帧是单帧瞬态）。
* 移动阶段黄色光标格的规则在 ROM 上**复测确认生效**（`band 2 → 0`，族名不一致 15 → 13，
  忠实口径 4 → 2）。
* ⭐ **尾部性质的可判定证据**：原版把**黄色光标格画在战斗格 (0, 6) 上，
  而那一列在原版自己的碰撞网格里十二行全是墙** ⇒ 原版缓冲尾部**不是当前地图空间的内容**。
* ⭐ **逐格性质判定**（Y4 用自建判定器独立复现）：尾部残留 **44** / walk 相位 **130** /
  **产品差 2**（`movegrid` 剩的 2 格 = `hatch→solid`，**单位占位**）⇒ **四时刻 product-diff = 0**。

### 0.2 ✅ Y4：出包定稿完成

* **12 步流水线 12/12 全绿**（收据 `2026-10-24T16:10:20+08:00`，`ok: true`、`failed_step: null`）；
  **11 个 selftest 全红**；单测棘轮 **118 pass / 20 fail（新失败 0）**；
  判定台连读 3 次**读数逐项相同**（残差 **100,210 px**）；
  **构建 == 钉住 == 打包三者同 sha**（`2c2b48d9…`）。
* 报告 **1069 行 / 117,711 B**，**23 条**未达成项；新增 §3.3「逐格性质判定」（176 行明细）。
* ⭐ **打包草稿残留已清**（换包目录重跑，包里没有 `report-test.md`）。
* ⭐ **一个命名坑**：`Y3-overlay-zero.md` 是 **wave 6** 的旧笔记（`X2-overlay-zero.md` 是 wave 12 的）
  ⇒ 报告的「本波已交付」判定已改成**以 `WAVE13-TASKS.md` 的 mtime 为界**。

### 0.3 ⭐ Y1 的栈溢出修复**其实落地了**（父代理亲自复测）

`sizeof(battle_scene_presentation_event)`：

| | 工作区 | HEAD |
|---|---:|---:|
| `battle_scene_presentation_event` | **148** | **148** |
| `battle_scene_snapshot<12>` | 1672 | 1672 |

⇒ **尺寸中性达成**（那 +53 行是塞进了原有对齐空隙）⇒
**崩溃根因已被处理**，且 Y4 的 12/12 全绿就是在含此修复的 ROM `2c2b48d9…` 上测的。
⇒ **Y1 缺的是「笔记」和「结算链运行帧」**（它的工具全在盘上：
`y1_size_probe.cpp`、`y1_stack_watch.py`、`y1_addr2line.sh`、`y1_big_bss.sh`、
`y1_play.py`、`y1_phase_offset.sh`、`y1_settlement_table.py`、
`notes/evidence/probe-reader-thread-growth-20261024.md`）。

### 0.4 ❌ Y3（黑场）**未交笔记、未落地**（输出被运行时截断）

Y3 的日志显示它**查实了关键机理**：
* Butano 的 `core::update()` 语义：部署场景每次迭代 = **2 个模拟帧**（实测 frames 1506–1526）
  ⇒ **24 帧渐变 = 12 级 × 2 GBA 帧，时序常量是对的**，多出来的帧来自别处；
* 怀疑 Butano **按 sprite 逐个解压整个 sprite item** ⇒ 每帧成本高；
* ROM 被并行流重建过 ⇒ 要钉住 ROM 重测。

⇒ **本波重做黑场**。

---

## 1. 流 Z1 —— ⭐ 补 Y1 的笔记 + 录出结算链运行帧

### 1.1 独占文件

* `D:\Github\gba-naruto\notes\s49-fidelity\Y1-stack-fix-and-settlement.md`（**新建**）
* `D:\Github\gba-naruto\tools\s49_battle_balance\`（Y1 留下的工具都在这，**现在归你**）
* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`
* `…\game\include\konoha\battle_scene_controller.h`

⛔ **不要改** `battle_scene_presentation_event.h`（尺寸已中性，别再动）、
`battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h`（Y2 已定稿）、
`battle_black_field*.h` / `graphics\`（Z2 独占）。
⛔ 逆向线全程只读。

### 1.2 任务 A：⭐ 补交 Y1 的笔记（**它欠的**）

从 `git diff HEAD -- butano-sequel/game` + Y1 留下的 8 个工具反推它做了什么，
写 `Y1-stack-fix-and-settlement.md`：
* 栈溢出修复的**手法**（怎么塞进对齐空隙的）+ **`sizeof` 与 HEAD 逐字节相同**的证据；
* 三个判据的达成情况（sizeof / 无 stack-usage 警告 / 当前 ROM 上打完仗）；
* **假设台账**（Y1 的日志里有 14 条假设的结论，把它们落盘）。

### 1.3 任务 B：录出结算链运行帧

**Y1 留下的工具（接着用，别重做）**：
`w1_probe.py`（⚠️ **共享 `probe.py` 每行一个读线程会死锁**）、
`w1_boot.py`（⭐ **闭环开机**：13 次 A 见黑场当相位标记 → 稳定停在对白第 1 页）、
`w1_record.py`、`w1_drive.py`、`w1_verify.py`、`w1_settlement_table.py`、
`w1_brightness.py`、`w1_diag.py`、`w1_capture.lua`、`x1_settlement.py`、
`y1_size_probe.cpp`、`y1_stack_watch.py`、`y1_addr2line.sh`、`y1_big_bss.sh`、
`y1_play.py`、`y1_phase_offset.sh`、`y1_settlement_table.py`
（都在 `D:\Github\gba-naruto\tools\s49_battle_balance\`）。

⇒ **闭环驱动**（读 ROM 的 `battle_scene_phase` / 光标 → 决策 → 按键）。
⚠️ **U2 的获胜脚本 `route.json` 不够走到 `complete`**（旧链 8 次 A，新链要 16 次）⇒ 补 8 次 A。

**录出**「勝利」屏 + 结算屏**运行帧**，与原版真值
（`build/s49-victory-capture/w4/settlement-truth/`，9 张图 + 收据）**逐屏对照**：
每屏 —— 原版 sha / 重制侧 sha / 差 px / 差 bbox。
⚠️ **不得伪造任何帧**。

### 1.4 验收

* `Y1-stack-fix-and-settlement.md` 交上来（**含假设台账**）。
* **结算链运行帧**录出（PNG + sha256 收据）；**两次独立跑逐字节一致**；**逐屏对照表**。
* **单测棘轮**：失败集合与 HEAD 基线**逐名相同** ⇒ 多出任何一项 ⇒ 变红。
  HEAD 基线：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh`
  工作区：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh`
* 判定台残差**只许变小**（当前基线：总和 **100,210** / 中位 **1,323** / 全 0 帧 **5**）。
  ⚠️ **必须同 ROM 比**（W4 已证：ROM 不同就不是同一个测量）⇒ 报告里给 ROM sha。

---

## 2. 流 Z2 —— 黑场：2 个事件 + 时长（**重做**）

### 2.1 独占文件

* `…\game\include\konoha\battle_black_field.h` / `battle_black_field_timing.h`
* `…\game\include\konoha\battle_black_field_star.h` / `battle_black_field_star_mask.h`
* `…\graphics\battle_black_field_star_mask*.{bmp,json}` / `battle_black_field_block32.{bmp,json}`

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h` /
`battle_scene_presentation_event.h`（Z1 独占）、`battle_range_ui_style.h` 等（Y2 已定稿）。
⛔ 逆向线全程只读。

### 2.2 已查实的机理（Y3 的日志，**接着用**）

* Butano `core::update()`：部署场景每次迭代 = **2 个模拟帧**（实测 frames 1506–1526）
  ⇒ **24 帧渐变 = 12 级 × 2 GBA 帧，时序常量是对的**；多出来的帧来自别处。
* 怀疑 Butano **按 sprite 逐个解压整个 sprite item** ⇒ 每帧成本高。
* ⇒ **先测**：重制侧黑场期间**每场景迭代实际消耗几个模拟帧**（探针可读 Butano 的
  `static_data` 里的 `missed_frames`）。
* ⇒ 再决定是「时间常量不对」还是「每迭代帧数被别的开销拖慢」。

### 2.3 任务

**黑场真值（U4 测的）**：
* **原版 1881 帧 / 2 个事件**：(24 淡出 / 18 全黑 / 24 淡入) 与 (24 / 24 / 24)，每级 **2 个 GBA 帧**；
  全黑帧 sha256 `47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e`。
* **重制侧 2402 帧 / 6 个事件**：`0/8/0`、`0/6/0`、**`44/20/46`**、`0/2/0`、`0/8/0`、**`54/26/54`**
  ⇒ **带渐变的只有 2 个**（44/20/46 与 54/26/54），另 4 个是**硬切**。
* U1 已把重制侧**事件 3**（44/20/46）与原版事件 1（24/18/24）**逐级可见像素 0 不匹配**（37 级全对）
  ⇒ **结构对了，长度不对**。

⇒ **任务**：
1. **先分类那 4 个硬切事件原版有没有** —— 它们可能是重制侧**自己额外的**淡入淡出
   （战斗场景切换等）⇒ 该在**别处**修，而不是算成「原版的黑场事件」。
2. 把重制侧收敛到原版的 **2 个事件**（24/18/24 与 24/24/24，每级 2 个 GBA 帧）。
3. **时长对齐**：`star_mask_level()` 的级号 ↔ 帧号映射跟原版一致。
4. ⚠️ **OAM 只余 2 槽**（84 星星 + 42 场景 = 126 / 128）⇒ **别再加精灵**。
5. ⚠️ **星光圈与调色板淡出二选一**（原版是「洞」不是「变暗」）⇒ 确认当前是**二选一**。

### 2.4 验收

* 黑场真值（`python tools/s49_blackfade/blackfade_report.py`）：
  重制侧 **2 个事件**，级数 **37**，逐级可见像素与原版 **0 不匹配**，时长与原版一致。
* **单测棘轮**（同 §1.4）。

---

## 3. 流 Z3 —— 残差下界为当前 ROM 重算 + 130 格「walk 相位」归因

### 3.1 独占文件

* `D:\Github\gba-naruto\tools\s49_pairing\`（X2r 的配对流，**只读复用 + 你自己的新目录**）
* `D:\Github\gba-naruto\tools\s49_z3_bound\`（新）
* `D:\Github\gba-naruto\notes\s49-fidelity\Z3-bound-and-phase.md`（新）

⛔ **不改重制线任何文件**；⛔ 不改其它流的仪器（**只读调用**）；⛔ 逆向线全程只读。

### 3.2 任务 A：把**可证像素下界**为**当前 ROM** 重算

报告 §11 第 2 项写的「下界 ≈ 23,700」是**在 wave 6 的录制上测的**，
**没有为当前 ROM（`2c2b48d9…`）重算** ⇒ 口径要更新。
⇒ 重录密集 walk（`tools/s49_pairing/record.py`），
按 X2r 的算法（每拍内原版全部帧 × 重制全部帧逐对取最小，25 拍求和）重算下界。

⚠️ **录制吃 7–8 GB 且持续泄漏**（~10 MB/s）⇒ **不要同时开两个全量录制**；
跑完查 `Win32_Process` 的孤儿 `mgba-probe.exe`。

### 3.3 任务 B：130 格「walk 相位」的不一致归因

Y2/Y4 已把剩余 176 格分成三类：尾部残留 **44** / walk 相位 **130** / 产品差 **2**。
⇒ 那 **130 格「walk 相位」**到底是什么？
原版 `field` 是**「青+橙同现」的稳定态**，而重制侧 35 帧**无一帧同现**；
原版 `grid16` 是**单帧瞬态**（半刷新、175 格）。
⇒ 要给出**可判定的证据**（不是断言）：是「重制侧缺一个相位」还是「原版那一帧是瞬态」？

### 3.4 验收

* 新的可证下界（**当前 ROM**）+ 与旧值的对照。
* 130 格的归因结论 + 证据。
* 两次跑逐字节一致。

---

## 4. 流 Z4 —— 出包定稿 + 报告定稿

### 4.1 独占文件

* `D:\Github\gba-naruto\tools\s49_package\`
* `D:\Github\gba-naruto\docs\s49-fidelity-report-2026xxxx.md`

⛔ **不改重制线任何文件**；⛔ 不改其它流的仪器（**只读调用**）；⛔ 逆向线只读。

### 4.2 任务

**(a) 等 Z1/Z2/Z3 落地后重跑 12 步流水线** ⇒ **12/12 全绿**。
⚠️ 第 2 步单测棘轮：失败集合必须与 HEAD 基线**逐名相同**（20 项预存债）。
⚠️ **ROM 钉住**已在流水线里（build == 钉住 == 打包三者同 sha）。
⚠️ **不要**在其它流还在跑全量录制时重跑（recorder 吃 7–8 GB ⇒ 步骤 5 的 capture 会被杀）。
⇒ **重跑前先查 `Win32_Process` 的内存占用**。

**(b) 1:1 报告定稿。**「未达成项」逐条收口或写清原因，至少包含：
* ⭐ **原版 S49 结算屏真值 —— 已闭合**；
* **结算链运行帧对照**（Z1 的结果）；
* ⭐ **残差归零不可达**：**为当前 ROM 重算过的**可证像素下界（Z3 的结果）；
* ⭐ **覆盖层「192/0/0」已达成**；剩余族名不一致**逐格性质判定**（尾部 44 / 相位 130 / 产品差 2）；
* 存档**逐字节一致按用户口径排除**；音频**逐采样一致排除**（80–120 h）；
* **20 项单测在 HEAD 即为红（预存债），本次零回归**；
* 判定台抖动 —— **已查清闭合**；
* 黑场事件数/时长（Z2 的结果）；
* 对话框斜切展开（实为入场转场）若未复现要单列；
* 本机构建非字节可复现 ⇒ 随包带 ROM + 重录命令；
* ⭐ **注意笔记同名坑**：`Y3-overlay-zero.md` 是 **wave 6** 的旧笔记
  ⇒ 「本波已交付」判定继续以 `WAVE13-TASKS.md` / `WAVE14-TASKS.md` 的 mtime 为界。

**(c) 清理中间目录的草稿残留**（`build\s49-package-y4\` 里的 `cell-classification-dev.json`）
⇒ 换包目录重跑即可（最终包目录不受影响）。

### 4.3 验收

* 12 步流水线**全绿**；11 个 selftest 仍全红。
* 报告里每个数字能追到某次运行。

---

## 5. 父代理（我）做的事

* **串行接线兜底**（Z1/Z2 的接线点由我合进 `battle_runtime_scene.cpp`）。
* 残差棘轮监督：任何流声称「残差下降」都要用判定台独立复跑确认（**同 ROM**）。
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
* ⚠️ **并发构建会互相覆盖** ⇒ **同一时刻只允许一路做构建**。
* ⚠️ **不要用 `git stash`** ⇒ 用 `git archive` 抽只读快照或独立 worktree。
* ⚠️ **子代理被运行时中断时，产物在盘上但未经验证** ⇒ 接管方必须**重新验证**
  （见 `notes/s49-fidelity/INCIDENT-wave5-task-loss-20261024.md`）。
* ⚠️ **recorder 吃 7–8 GB 且持续泄漏** ⇒ **不要同时开两个全量录制**。
