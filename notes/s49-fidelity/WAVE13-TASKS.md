# Wave 13 任务书 —— 收官波：修栈溢出 + 覆盖层收尾 + 黑场 + 出包定稿

> 2026-10-24 · 主代理（mvs_4e730a9ded524558a303c115875a9707）
> 前置：wave 12 四路（X1/X2/X3/X4）收口。**12 步流水线已 12/12 全绿**。
> ⭐ **本波是收官波**：剩下的活已经收敛到 4 件，做完就出终稿。

---

## 0. wave 12 的结果（**全部已确认，勿重查**）

### 0.1 ⭐⭐ X2 交回一个**颠覆性结论**：覆盖层其实已经达标

> **W2 留下的「terrain grid 19×19 vs MAP_WIDTH 15 列」这条线索是错的**：
> 地形网格就是 **15×19**（480×304 px，与原版 map-14 画布完全一致，三方一致）。
>
> ⭐ **真正的仪器 bug**：共享仪器给**原版**贴地图标签时**没有按 480 px 回绕缓冲尾部**，
> 而给**重制侧**回绕了 ⇒ 两侧的尾部两列被互相错开
> ⇒ **那 24 格「原版缺」+ 24 格「多画」全是标签错位的假象**！
> ⇒ **补上回绕后，field/movegrid 已经是「同亮 192 / 缺 0 / 多画 0」**。
>
> 剩下的族名不一致里，**只有 2 格是规则问题**（移动阶段的黄色光标格），已修；
> 其余全部落在**原版缓冲尾部的陈旧内容**（不是当前地图空间，任何忠实的重制都复现不了）
> 和 **walk 的相位/游戏状态**上。
> ⇒ 验收目标「192/0/0/0」在 X2 的权限内**不可达**，理由逐条列在 `X2-overlay-zero.md` §5。

⇒ **「多画 310–420 格 / 缺 96–129 格」这个从 wave 1 传下来的口径，最终是仪器假象。**
⇒ **真正的产品差只有 2 格**（黄色光标格）。

### 0.2 ⭐⭐ X1 揪出崩溃根因（但**没交笔记、没修完**）

X1 的工作日志（输出被运行时截断，但日志完整）：

* 闭环驱动器建好了；**打字机吞掉第一个 A**（W1 开机遗留的伪影）⇒ 改成「按到被接受为止」。
* ⭐ **当前 ROM 在 action confirm 时崩溃**（illegal opcode），而 `21650614…` 那个好 ROM 正常。
* ⭐ **嫌疑对象：`battle_scene_presentation_event` 结构体在 wave 11 变大了 24 行**
  （新增 `battle_settlement_presentation` + 2 个字段）
  ⇒ **与 wave 11 W3 修过的 `battle_scene_snapshot`（1672 字节撑爆栈帧）完全同一类**。
* 构建报出 **stack-usage warnings**（强证据）。
* 单测棘轮 **117 pass / 20 fail**（新失败 0）。
* 「The result screen renders with real data」⇒ 结算屏开始能画了。
* 改过 `game\src\battle_runtime_scene.cpp`（15:27:18）、加了 `tools\s49_battle_balance\x1_settlement.py`（15:33:40）。

⇒ **X1 找到根因方向但没交笔记、没修完** ⇒ wave 13 接管。

### 0.3 X3（黑场）**空手而归**：无文件、无笔记、输出为空

⇒ wave 13 重做。

### 0.4 X4：12 步流水线 **12/12 全绿** + 报告终审

* 收据 `2026-10-24T15:42:17+08:00`，`ok: true`；**11 个 selftest 全红**；
  单测棘轮 **117 pass / 20 fail，新失败 0**；
  判定台连读 3 次**读数逐项相同**（残差 100,210）。
* ⭐ **越界复核（独立第二次）**：上一任（wave 10 U4）给 `find_overlay_map` 加的 terrain 判据
  **保留、不回退** —— 35 个 walk dump 上 **Q1 0/35 不同、Q1b 0/35 不同、判据只改 4 个**
  （`0x00800`→`-1`）、**其余 31 个一字未变**；端到端 `grid16` 残差 **185→126**（多画 103→39）。
* ⭐ **抓到并修掉一个真问题**：**收据里的 ROM ≠ 包里的 ROM**（并行流中途重建了 ROM）
  ⇒ 现在用「**钉住 ROM**」从**构造上**保证一致（build == 钉住 == 打包三者同一 sha）。
* 报告终稿 **755 行 / 96,482 B**，**22 条**未达成项。

---

## 1. 流 Y1 —— ⭐⭐ 栈溢出修复 + 结算链运行帧（**收官关键路径**）

### 1.1 独占文件

* `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha\battle_scene_presentation_event.h`
* `…\game\src\battle_runtime_scene.cpp`
* `…\game\include\konoha\battle_scene_controller.h`
* `D:\Github\gba-naruto\tools\s49_battle_balance\`（X1 已改，**现在归你**）

⛔ **不要改** `battle_range_ui_style.h` / `battle_map_content.h` / `grid_pathfinder.h`（Y2 独占）、
`battle_black_field*.h` / `graphics\`（Y3 独占）、`battle_result*.h`（W3 已定稿）。
⛔ 逆向线全程只读。

### 1.2 任务 A：⭐⭐ 把 `battle_scene_presentation_event` 改成**尺寸中性**

**假设（X1 提出的，你必须验证）**：
`battle_scene_presentation_event` 在 wave 11 长了 **24 行**
（新增 `struct battle_settlement_presentation` + `bool has_settlement` + `battle_settlement_presentation settlement`）
⇒ 该事件对象在**栈上** ⇒ 栈帧超限 ⇒ **action confirm 时 illegal opcode 崩溃**。

**与 wave 11 W3 修 `battle_scene_snapshot` 完全同一类**：W3 的修法是
「把新增字段**塞进原有对齐空隙**」，实测 `sizeof(battle_scene_snapshot<12>)` 回到 **1672 = 与 HEAD 逐字节相同**。

⇒ **你的修法**：同样把结算链的新增字段**塞进 `battle_scene_presentation_event` 原有的对齐空隙**，
并用 `sizeof` 实测证明**与 HEAD 逐字节相同**（给出数字）。

**判据**：
* `sizeof(battle_scene_presentation_event)` **与 HEAD 完全相同**（HEAD 的值自己算）；
* 构建**不再出现该结构的 stack-usage 警告**；
* ⭐ **当前 ROM 上同一脚本必须打完仗**（`outcome=1`），
  且 **`21650614…` 与新 ROM 行为一致**（不能只修好一个）。

### 1.3 任务 B：录出结算链运行帧

**X1 留下的零件（接着用）**：`w1_probe.py`（⚠️ **共享 `probe.py` 每行一个读线程会死锁**）、
`w1_boot.py`（⭐ **闭环开机**：13 次 A 见黑场当相位标记 → 稳定停在对白第 1 页）、
`w1_record.py`、`w1_drive.py`、`w1_verify.py`、`w1_settlement_table.py`、
`w1_brightness.py`、`w1_diag.py`、`w1_capture.lua`、`x1_settlement.py`（X1 新加）。

⇒ **闭环驱动**（读 ROM 的 `battle_scene_phase` / 光标 → 决策 → 按键）。
⚠️ **U2 的获胜脚本 `route.json` 现在不够走到 `complete`**（旧链 8 次 A，新链要 16 次）⇒ 补 8 次 A。

**录出**「勝利」屏 + 结算屏的**运行帧**，与原版真值
（`build/s49-victory-capture/w4/settlement-truth/`，9 张图 + 收据）**逐屏对照**：
每屏 —— 原版 sha / 重制侧 sha / 差 px / 差 bbox。
⚠️ **不得伪造任何帧**。

### 1.4 验收

* 栈溢出修掉（同上三个判据）。
* **结算链运行帧**录出（PNG + sha256 收据）；**两次独立跑逐字节一致**。
* **逐屏对照表**。
* **单测棘轮**：失败集合与 HEAD 基线**逐名相同** ⇒ 多出任何一项 ⇒ 变红。
  HEAD 基线：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/run-baseline-tests.sh`
  工作区：`wsl -d Ubuntu-24.04 -- bash /mnt/d/Github/gba-naruto/build/w1-run-all-tests.sh`
* 判定台残差**只许变小**（当前基线：总和 **100,210** / 中位 **1,323** / 全 0 帧 **5**）。
  ⚠️ **必须同 ROM 比**（W4 已证：ROM 不同就不是同一个测量）⇒ 报告里给 ROM sha。

---

## 2. 流 Y2 —— 覆盖层收尾（**2 格黄色光标格** + 仪器回绕修正）

### 2.1 独占文件

* `…\game\include\konoha\battle_range_ui_style.h`
* `…\game\include\konoha\battle_map_content.h`
* `…\game\include\konoha\grid_pathfinder.h`
* `D:\Github\gba-naruto\tools\s49_overlay_align\compare_overlay_families.py`
  （**授权你改**：X2 已查实仪器给原版贴标签时**没按 480 px 回绕**，需要补上）

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h` /
`battle_scene_presentation_event.h`（Y1 独占）、`battle_black_field*.h` / `graphics\`（Y3 独占）。
⛔ 逆向线全程只读。

### 2.2 任务 A：修完那 **2 格**黄色光标格

X2 已定位：族名不一致里**只有 2 格是规则问题**（**移动阶段的黄色光标格**），
X2 已改但**没交最终数字**。⇒ 把它修完并给出四时刻的最终数字。

### 2.3 任务 B：仪器补 480 px 回绕（**这是「192/0/0/0」的关键**）

X2 查实：共享仪器给**原版**贴地图标签时**没有按 480 px 回绕缓冲尾部**，
给重制侧却回绕了 ⇒ 两侧尾部两列错开 ⇒ 24 缺 + 24 多画全是假象。
⇒ **补上原版侧的回绕**，并给出修正前后的数字对照。

### 2.4 任务 C：判定「原版缓冲尾部的陈旧内容」的性质

那部分不一致落在**原版缓冲尾部、不是当前地图空间** ⇒
**任何忠实的重制都复现不了**。⇒ 要给出一条**可判定的证据**
（不是断言），并写进 1:1 报告的「明确排除项」。

### 2.5 验收

* 逐格族名对拍（**整条 walk 口径**）⇒ 目标 **同亮 192 / 缺 0 / 多画 0**，
  族名不一致**逐格列出并给出性质判定**（产品差 / 不可复现的原版尾部残留 / walk 相位）。
* **单测棘轮**（同 §1.4）。
* 判定台残差**只许变小**（同 §1.4，**同 ROM**）。

---

## 3. 流 Y3 —— 黑场事件数与时长（**X3 空手而归，重做**）

### 3.1 独占文件

* `…\game\include\konoha\battle_black_field.h` / `battle_black_field_timing.h`
* `…\game\include\konoha\battle_black_field_star.h` / `battle_black_field_star_mask.h`
* `…\graphics\battle_black_field_star_mask*.{bmp,json}` / `battle_black_field_block32.{bmp,json}`

⛔ **不要改** `game\src\battle_runtime_scene.cpp` / `battle_scene_controller.h` /
`battle_scene_presentation_event.h`（Y1 独占）、`battle_range_ui_style.h` 等（Y2 独占）。
⛔ 逆向线全程只读。

### 3.2 任务

**黑场真值（U4 测的）**：
* **原版 1881 帧 / 2 个事件**：(24 淡出 / 18 全黑 / 24 淡入) 与 (24 / 24 / 24)，每级 **2 个 GBA 帧**；
  全黑帧 sha256 `47fbde60709a27683035d7b385f06dd1447f68c6548272758e15a335cf3bc15e`。
* **重制侧 2402 帧 / 6 个事件**：
  `0/8/0`、`0/6/0`、**`44/20/46`**、`0/2/0`、`0/8/0`、**`54/26/54`**
  ⇒ **带渐变的只有 2 个**（44/20/46 与 54/26/54），另 4 个是**硬切**。
* ⭐ U1 已把重制侧**事件 3**（44/20/46）与原版事件 1（24/18/24）**逐级可见像素 0 不匹配**
  （**37 级全对**）⇒ **结构对了，但时长与原版不一致**。

⇒ **任务**：
1. 把重制侧黑场收敛到原版的 **2 个事件**（24/18/24 与 24/24/24，每级 2 个 GBA 帧）。
2. ⚠️ **先确认那 4 个硬切事件原版有没有** —— 它们可能是重制侧**自己额外的**淡入淡出
   （战斗场景切换等）⇒ 该在**别处**修，而不是算成「原版的黑场事件」。
3. **时长对齐**：`star_mask_level()` 的级号 ↔ 帧号映射要跟原版一致。
4. ⚠️ **OAM 只余 2 槽**（84 星星 + 42 场景 = 126 / 128）⇒ **别再加精灵**。
5. ⚠️ **星光圈与调色板淡出二选一**（原版是「洞」不是「变暗」）⇒ 确认当前是**二选一**。

### 3.3 验收

* 黑场真值（`python tools/s49_blackfade/blackfade_report.py`）：
  重制侧 **2 个事件**，级数 **37**，逐级可见像素与原版 **0 不匹配**，时长与原版一致。
* **单测棘轮**（同 §1.4）。

---

## 4. 流 Y4 —— 出包定稿 + 报告终审

### 4.1 独占文件

* `D:\Github\gba-naruto\tools\s49_package\`
* `D:\Github\gba-naruto\docs\s49-fidelity-report-2026xxxx.md`

⛔ **不改重制线任何文件**；⛔ 不改其它流的仪器（**只读调用**）；⛔ 逆向线只读。

### 4.2 任务

**(a) 等 Y1/Y2/Y3 落地后重跑 12 步流水线** ⇒ **12/12 全绿**。
⚠️ 第 2 步单测棘轮：失败集合必须与 HEAD 基线**逐名相同**（20 项预存债）。
⚠️ **ROM 钉住**已在流水线里（build == 钉住 == 打包三者同 sha）⇒ 并行流中途重建不会再污染包。
⚠️ **不要**在其它流还在跑全量录制时重跑（recorder 吃 7–8 GB 且持续泄漏 ⇒ 步骤 5 的 capture 会被杀）。
⇒ **重跑前先查 `Win32_Process` 的内存占用**。

**(b) 1:1 报告定稿**（目标：把「未达成项」一条条收口或写清原因）。
**未达成项**至少包含（随实测更新）：
* ⭐ **原版 S49 结算屏真值 —— 已闭合**（正文 §15）；
* **结算链运行帧对照**（Y1 的结果）；
* ⭐ **残差归零不可达**：可证像素**下界 ≈ 23,700**；
* ⭐ **覆盖层「192/0/0/0」已达成**（Y2 的结果），
  剩余族名不一致要**逐格给出性质判定**（产品差 / 原版尾部残留 / walk 相位）；
* 存档**逐字节一致按用户口径排除**；音频**逐采样一致排除**（80–120 h）；
* **20 项单测在 HEAD 即为红（预存债），本次零回归**；
* 判定台抖动 —— **已查清闭合**（是 wave 10 那两次跑 ROM 不同，不是仪器）；
* 黑场事件数/时长（Y3 的结果）；
* 对话框斜切展开（实为入场转场）若未复现要单列；
* 本机构建非字节可复现 ⇒ 随包带 ROM + 重录命令。

**(c) 修掉打包目录里的草稿残留**：上一任的包里残留了 `report-test.md`
（trash 启动器拒绝对 junction 目标动手）⇒ **换包目录重跑**即可清掉。

### 4.3 验收

* 12 步流水线**全绿**；11 个 selftest 仍全红。
* 报告里每个数字能追到某次运行。

---

## 5. 父代理（我）做的事

* **串行接线兜底**（Y1/Y2/Y3 的接线点由我合进 `battle_runtime_scene.cpp`）。
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

* 一次尝试回答一个**是/别问题**；**「还是卡」不是结果**。
* 一次只改一处，跑一次，记一行；结论落进**假设台账**。
* **连续 3 次同样结果 ⇒ 停**，换方法，写进台账。
* 陷住了**换方法/换会话**，不要靠续跑硬扛。
* ⚠️ **并发构建会互相覆盖** ⇒ **同一时刻只允许一路做构建**。
* ⚠️ **不要用 `git stash`** ⇒ 用 `git archive` 抽只读快照或独立 worktree。
* ⚠️ **子代理被运行时中断时，产物在盘上但未经验证** ⇒ 接管方必须**重新验证**
  （见 `notes/s49-fidelity/INCIDENT-wave5-task-loss-20261024.md`）。
* ⚠️ **recorder 吃 7–8 GB 且持续泄漏** ⇒ **不要同时开两个全量录制**；
  跑完查 `Win32_Process` 的孤儿 `mgba-probe.exe`。
