# Wave 12 任务书 —— 修战斗输入回归 + 覆盖层归零 + 黑场补齐 + 出包

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 前置：wave 11 四路（W1/W2/W3/W4）收口。**12 步流水线已 12/12 全绿**。

---

## 0. wave 11 的结果（**全部已确认，勿重查**）

### 0.1 ⭐ W4：判定台**本来就没有抖动**

wave 10 报的「±9,520 px 抖动」根因是**那两次跑用的 ROM 不是同一个**：
U4 自己留下的两份报告里 `captures.remake.rom_sha256` 分别是
`249217d7…`（11:15:03，残差 168,816）与 `73b74587…`（11:27:10，残差 104,784）
⇒ 差的那 9,520 px 属于**产品改动**，不是仪器抖动。
**同一个 ROM 连读 3 次：残差总和 100,210 px 三次完全相同**，
逐帧配对逐项相同，**每张采集 PNG 的 sha256 也逐张相同**。
⇒ 判定台语义一个字未改；改的是**仪器现在能自证这件事**（新增 `--repeat N`，
  棘轮收据带两侧 ROM sha256 + `changed` 标志）。

W4 顺手修了两个真 bug：① 重制侧 audit 的 `rom_sha256` 填的是**原版** ROM 的摘要；
② GBK 控制台打印 `⇒` 抛 `UnicodeEncodeError`（在棘轮 PASS **之后**抛 ⇒ 步骤 5 明明过了却 exit 1）。
**12 步流水线 12/12 全绿**（收据 `2026-10-24T13:48:50`，`ok: true`）；**11 个 selftest 全红**；
单测棘轮 **117 pass / 20 fail，新失败 0**；报告 **734 行 / 82,954 B**。

### 0.2 ⭐ W3：结算链 **7 段在产品代码里走通了**

* `battle_scene_phase` 加 `post_battle_dialogue` / `task_menu`（**追加在末尾**，现有 ordinal 保住），
  生成绑定表同步到 26 行；`_advance_level_up()` 改走 `battle_result_level_up_pages()`；
  `training` 结束不再直进 `complete`。
* **對白屏与任務菜單屏有实际画面**：
  原版任务菜单美术**本来就在仓里、运行时从未引用过**（`scenario_41_postbattle_bg/ui`），现接上；
  對白用重制自己的对话框 + **新建的 16×16 结算字体**。
* **結算屏资产级差 px = 1,968**（V4 口径，≤ 2,000 ✓）/ 4,562（真值），按 **alpha 合成**。
* ⭐ **「三张 8bpp 层 = 192 KB > 96 KB VRAM」的前提不成立** —— grit 只导出非空图块，
  三层实际 **≈ 12.5 KB**；对白侧总占用 ≈ 65.8 KB < 96 KB。
* ⭐⭐ **抓到并修掉一个会崩 ROM 的真回归**：给 `battle_scene_snapshot` 加字段会把**栈帧顶爆**
  （ROM 跑出 `Illegal opcode: 0000bb10`、判定台抓帧直接失败）
  ⇒ 改成**尺寸中性**（快照实测回到 **1672 = 与 HEAD 逐字节相同**）。
* ⚠️ 升級屏美术**没换** 1:1 层（那三层是整屏烘焙截图，换上去会显示场景 41 的死值）；
  子页结构（3 人 × 2 页）已按原版接进产品代码。
* ⚠️ **訓練页无 1:1 候选**。

### 0.3 ⭐⭐ W1：**两处重制线回归**（wave 12 的头号任务）

W1 把重制侧的开机流程**建模完成**（闭环开机：13 次 A 见黑场 → 稳定停在对白第 1 页），
**两次独立跑逐字节一致**（各 114,999 帧），
但 ⭐ **没录到「勝利」屏/结算屏** —— 开环键脚本在重制 ROM 上**打不完这场仗**：
战斗场景在第 **5,471 帧被中止**（指令菜单 → 战前准备场景，中间没有 `outcome`/`result`/`level_up` 任何一屏）。

**W1 用「只换 ROM、不换脚本」的 A/B 测出两处回归**：

| ROM sha | 构建时间 | 行为 |
|---|---|---|
| `21650614…` | 11:46 | ✅ **每键推进**，战斗正常 |
| `af0352d0…` | 13:07 | ⛔ **第 1 回合吞掉全部按键** |
| `b6c2a05f…`（**当前工作区 ROM**） | 13:38 | ⚠️ **指令菜单失步** |
| `804dd793…` | 更早 | 开机流程不同 |

⇒ **回归由 wave 11 的产品改动引入**（11:46 好 → 13:07 坏），
落在 **`battle_runtime_scene.cpp` / `battle_scene_controller.h`**（wave 10 U1 与 wave 11 W3 都改过）。

### 0.4 W1 纠正了 V4 的一条结论

V4 说「重制侧结算链已录到四屏」⇒ **错**：那四屏是**战前准备场景的装备屏**
（`队伍·装备` / `EQUIP PPE·TOOL·SLOT` / `EQUIP COMPLETE` / `UNEQUIP COMPLETE`），
对应原版的 `07-ninja-tool-list.png`；`UPGRADE RECIPE·MATERIAL·BAG` ≈ 原版 `03..06-levelup-*`（版式不同）。

### 0.5 W2（覆盖层）**未完成**

W2 的输出被运行时截断，它正在查一个关键点：
**仪器的 terrain grid 是 19×19，但 MAP_WIDTH 假设 15 个战斗列** ⇒ 两者不一致。
当前基线（U4 在**锚点 256** 口径下测的）：

| 时刻 | 同亮 | 原版缺 | 多画 | 族名不一致 |
|---|---:|---:|---:|---:|
| field | 168 | 24 | 24 | **50** |
| movegrid | 168 | 24 | 24 | **4** |
| grid16 | 153 | 22 | 39 | **65** |
| banner | **0** | **0** | **0** | **0**（exact ✔） |

目标：**同亮 192 / 缺 0 / 多画 0 / 不一致 0**。

---

## 1. 流 X1 —— ⭐⭐ 修战斗输入回归 + 闭环驱动 + 录出结算链运行帧

### 1.1 独占文件

* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\src\battle_runtime_scene.cpp`
* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_scene_controller.h`
* `D:\Github\gba-naruto\tools\s49_battle_balance\`（W1 已交付，**现在归你**）

⛔ **不要改** `battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h`（X2 独占）、
`battle_result*.h` / `battle_original_states.h` / `battle_scene_presentation_event.h`（W3 独占）、
`battle_black_field*.h` / `graphics\`（X4 独占）。
⛔ 逆向线全程只读。

### 1.2 任务 A：⭐ 定位并修掉那两处回归（**头号**）

**症状**：命令菜单处失步 / 第 1 回合吞掉全部按键。
**已排除**：枚举错位（新相位**追加在末尾**，ordinal 保住）、
快照尺寸（W3 已修成尺寸中性，1672 = HEAD 逐字节相同）。

**你要用的杠杆**：
* ⭐ **A/B 只换 ROM**（W1 的方法）：用 `21650614…`（好）与 `af0352d0…` / `b6c2a05f…`（坏）三份 ROM，
  同一脚本、同一探针、同一参数 ⇒ 差异必然来自 ROM 内容。
* ⭐ **git 二分**：`git bisect` 在**重制仓**上做（⚠️ **不要用 `git stash`**：有并行流在改同一棵树；
  用 `git archive` 抽只读快照，或 `git worktree` 到独立目录）。
  wave 11 的改动集中在：`battle_runtime_scene.cpp`、`battle_scene_controller.h`、
  `battle_original_states.h`（24→26 行生成表）、`battle_result_content.h`、
  `graphics/`（结算底板 + 结算字体）、`sequel/content/battle_controller_states.json`
  （`remake_phase_count` 24→26、`remake_only_phases` +2、`mapping` +2）。
* ⚠️ **重点怀疑对象**（自己验证，不要盲信）：
  * **输入分派的 phase 分支**：W1 观察到 ROM 的输入分派里
    `presentation_frame` / `map_movement.busy()` 分支会吞掉按键；
    结算链新增的 `post_battle_dialogue` / `task_menu` 相位、
    以及 `battle_original_states.h` 的 26 行生成表，**是否影响了分派的 phase 判定**？
  * **新增的结算屏渲染器**是否在战斗场景里也执行（抢了输入或改坏了状态机）？
  * **结算字体**的生成是否改动了**别的**字体资源表（连带影响战斗 UI 的字形）？
  * `battle_controller_states.json` 的 `remake_phase_count` 24→26 是否被**别的**代码读成
    「原版状态数」⇒ 索引越界或错位？
* **判据**：修好后 **同一脚本在当前 ROM 上必须打完仗**（`outcome=1`），
  且 **`21650614…` 与新 ROM 的行为一致**（不能只修好一个）。

### 1.3 任务 B：闭环驱动 + 录出结算链运行帧

* W1 交回的零件（**接着用**）：
  `w1_probe.py`（可靠探针客户端；⚠️ **共享 `probe.py` 每行一个读线程会死锁**）、
  `w1_boot.py`（⭐ **闭环开机**：13 次 A 见黑场当相位标记 → 稳定停在对白第 1 页）、
  `w1_record.py`、`w1_drive.py`、`w1_verify.py`、`w1_settlement_table.py`、
  `w1_brightness.py`、`w1_diag.py`、`w1_capture.lua`。
* ⇒ **改成闭环驱动**（读 ROM 的 `battle_scene_phase` / 光标 → 决策 → 按键），
  因为开环脚本在指令菜单处会失步。
* ⚠️ W3 提醒：**U2 的获胜脚本 `route.json` 现在不够走到 `complete`**（旧链 8 次 A，新链要 16 次）
  ⇒ 复用时要补 8 次 A。
* **录出**「勝利」屏 + 结算屏的**运行帧**，与原版真值
  （`build/s49-victory-capture/w4/settlement-truth/`，9 张图 + 收据）**逐屏对照**：
  每屏 —— 原版 sha / 重制侧 sha / 差 px / 差 bbox。
* ⚠️ **不得伪造任何帧**。

### 1.4 验收

* **回归修掉**：当前 ROM 上同一脚本**打完仗**（`outcome=1`），且与 `21650614…` 行为一致。
* **结算链运行帧**录出（PNG + sha256 收据）；**两次独立跑逐字节一致**。
* **逐屏对照表**（原版 vs 重制侧）。
* **单测棘轮**：失败集合与 HEAD 基线**逐名相同** ⇒ 多出任何一项 ⇒ 变红。
  HEAD 基线：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh`
  工作区：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh`
* 判定台残差**只许变小**（当前基线：总和 **100,210** / 中位 **1,323** / 全 0 帧 **5**）。

---

## 2. 流 X2 —— 覆盖层逐格族名归零（**接管 W2 的未完成分析**）

### 2.1 独占文件

* `…\game\include\konoha\battle_range_ui_style.h`
* `…\game\include\konoha\battle_map_content.h`
* `…\game\include\konoha\grid_pathfinder.h`
* 新单元测试

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h`（X1 独占）、
`battle_result*.h`（X3 独占）。
⛔ `tools\s49_overlay_align\`（U4/W4 改过）—— **只读复用**。
⛔ 逆向线只读。

### 2.2 任务

**W2 留下的关键线索（接着查）**：
> **仪器的 terrain grid 是 19×19，但 MAP_WIDTH 假设 15 个战斗列** ⇒ 两者不一致。
> W2 还在核对原版的 solid 集与地形、以及原版缓冲尾部（列 14–15）是否跨时刻稳定。

⇒ 先把这个**不一致**查清（它很可能就是 24 格「原版缺」的来源），
再修族名不一致（field 50 / grid16 65）。

**已知（勿重查）**：
* **绘制范围**：原版只画**地图行 1..12** ⇒ 多画多半来自这里。
* **受阻集** = 地形类别 ≠ plain（17984/17984 px 逐像素吻合）。
* **族名不一致**：对照 **G-H15**（原版移动阶段**完全不画绿**、目标阶段**完全不画青**）。
* ⭐ **判据口径**：
  * 真覆盖层在 VRAM **`0x09800`**；`0x00800` 是**图块数据假阳性**；
  * **重制侧覆盖层只在 walk 的 step 25、28–34 出现**
    ⇒ **25 个配对帧里一个都没有** ⇒ **拿配对帧量是退化测量**
    ⇒ **测量必须走整条 walk 的 35 个 anchor dump**
    （`compare_overlay_families.py --vram-dir <dir>`）。
* 战斗格 = **32×16 px**；16×16 只是**逻辑格**（1 战斗列 = 2 逻辑列）。
* 调色板**不用改**。
* 原版 battle-14 地形：可走 **147** / 不可走 **138**，坐标 `(bx,by)` = 碰撞网格列行、**无偏移**。

### 2.3 验收

* 逐格族名对拍（**整条 walk 口径**）⇒ **同亮 192 / 缺 0 / 多画 0 / 不一致 0**。
* **单测棘轮**（同 §1.4）。

---

## 3. 流 X3 —— 黑场 4 个硬切 + 事件数/时长对齐

### 3.1 独占文件

* `…\game\include\konoha\battle_black_field.h` / `battle_black_field_timing.h`
* `…\game\include\konoha\battle_black_field_star.h` / `battle_black_field_star_mask.h`
* `…\graphics\battle_black_field_star_mask*.{bmp,json}` / `battle_black_field_block32.{bmp,json}`

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h`（X1 独占）、
`battle_range_ui_style.h` 等（X2 独占）、`battle_result*.h`（W3 已定稿）。
⛔ 逆向线只读。

### 3.2 任务

当前黑场真值（U4 测的）：
**原版 1881 帧 / 2 个事件**（24/18/24、24/24/24）；
**重制侧 2402 帧 / 6 个事件**（0/8/0、0/6/0、**44/20/46**、0/2/0、0/8/0、**54/26/54**）
⇒ **带渐变的只有 2 个**（44/20/46 与 54/26/54），另 4 个是**硬切**。

* ⭐ W3 已把**事件 3**（44/20/46）与原版事件 1（24/18/24）**逐级可见像素 0 不匹配**（37 级全对）
  ⇒ 结构对了，但**淡出/全黑/淡入的时长与原版不一致**。
* ⇒ 把重制侧的**事件数与时长**收敛到原版的 2 个事件（24/18/24 与 24/24/24）。
* ⚠️ **OAM 只余 2 槽**（84 + 42 = 126 / 128）⇒ 别再加精灵。
* ⚠️ 4 个硬切事件可能对应**重制侧自己额外的淡入淡出**（战斗场景切换等）⇒ 先确认它们**是不是原版也有**。

### 3.3 验收

* 黑场真值：重制侧 **2 个事件**，级数 37，逐级可见像素与原版 **0 不匹配**，时长与原版一致。
* **单测棘轮**（同 §1.4）。

---

## 4. 流 X4 —— 出包 + 1:1 报告终审

### 4.1 独占文件

* `D:\Github\gba-naruto\tools\s49_package\`
* `D:\Github\gba-naruto\docs\s49-fidelity-report-2026xxxx.md`

⛔ **不改重制线任何文件**；⛔ 不改其它流的仪器（**只读调用**）；⛔ 逆向线只读。

### 4.2 任务

**(a) 等 X1/X2/X3 落地后重跑 12 步流水线** ⇒ **12/12 全绿**。
⚠️ 第 2 步单测棘轮：失败集合必须与 HEAD 基线**逐名相同**（20 项预存债）。
⚠️ 构建碰撞重试已在流水线里（5 次 / 60 s / 只认 `objcopy` 碰撞）。
⚠️ **不要**在其它流还在跑录制时重跑（内存会被吃满 ⇒ 步骤 5 的 capture 被杀）。

**(b) 1:1 报告终审**（目标：把「未达成项」一条条收口或写清原因）。
**未达成项**至少包含（随实测更新）：
* ⭐ **原版 S49 结算屏真值 —— 已闭合**（写进正文）；
* **结算链运行帧对照**（X1 的结果）；
* **残差归零的可达性**：可证像素**下界 ≈ 23,700** ⇒ 归零不可达；
* 存档**逐字节一致按用户口径排除**；音频**逐采样一致排除**（80–120 h）；
* **20 项单测在 HEAD 即为红（预存债），本次零回归**；
* 判定台抖动 —— **已查清并闭合**（不是仪器，是 wave 10 那两次跑 ROM 不同）；
* 覆盖层逐格族名（X2 的结果）；
* 黑场事件数/时长（X3 的结果）；
* 对话框斜切展开（实为入场转场）若未复现要单列；
* 本机构建非字节可复现 ⇒ 随包带 ROM + 重录命令。

### 4.3 验收

* 12 步流水线**全绿**；11 个 selftest 仍全红。
* 报告里每个数字能追到某次运行。

---

## 5. 父代理（我）做的事

* **串行接线兜底**（X1/X2/X3 的接线点由我合进 `battle_runtime_scene.cpp`）。
* 残差棘轮监督：任何流声称「残差下降」都要用判定台独立复跑确认（**同 ROM**！W4 已证：
  ROM 不同就不是同一个测量）。
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
* ⚠️ **不要用 `git stash`**（有并行流在改同一棵树）⇒ 用 `git archive` 抽只读快照或独立 worktree。
* ⚠️ **子代理被运行时中断时，产物在盘上但未经验证** ⇒ 接管方必须**重新验证**
  （见 `notes/s49-fidelity/INCIDENT-wave5-task-loss-20261024.md`）。
* ⚠️ **重制侧 recorder 会吃 7–8 GB 且持续泄漏**（W1 实测 ~10 MB/s）⇒
  **不要同时开两个全量录制**；跑完查 `Win32_Process` 的孤儿 `mgba-probe.exe`。
