# U4 —— 真实打完仗验证 + 结算链真实版逐屏对照（wave 17）

> 流 U4 · 驾驶/仪器侧 · 2026-10-24
> 上游：`notes/s49-fidelity/V1-real-victory.md`（闭环驱动器、7 个诊断器、D4 的复现数据、逐屏对照工具）
> 独占：`tools/s49_battle_balance/`（V1 交付，本波归 U4）、`tools/s49_victory_align/`（**只读复用**）、本文件
> ⛔ 重制线 **零改动**（只读）；`tools/s49_package/` 未动；逆向线未访问；**未提交 git**。

---

## 0. 一句话结论

**仍然没有真打赢** —— **U1 的修复在本会话末尾落地了（ROM `16bf746f…`），
D4 的「招式确认 ⇒ 状态被写坏 + 场景停住」已经消失**（看门狗复测 **0/3 冻住**），
**但拦路的缺陷往前挪了一步**：现在玩家的攻击能一路走到
`target_selection → target_preview → target_confirmation`，
**却在「可以嗎?」对话框上停住** —— 对话框的光标在「はい」上，
**按 A 会被产品自己回一句 `CANNOT SELECT`**（原版 `w4_play.py` 的做法就是按 A）
⇒ **玩家的攻击仍然永远打不中**，所以 `outcome=1` 仍不可达、护送仍会失败。
驾驶侧与仪器侧本波全部做完并自证（逐屏对照表、两次独立跑逐字节一致），
并额外查出**两个仪器/驱动缺陷**（逐屏对照的**真值配对错位**、驱动器的**射程口径不一致**）
和**D4 的确切签名 + 它被修掉后的下一个卡点**。

> ⚠️ 本波有两个时间点，结论要分开看：
> **A. ROM `3973adcd…` / `a52c6424…`（U1 修复前）**：D4 在，状态被写坏。
> **B. ROM `16bf746f…`（U1 修复后）**：D4 的写坏消失，**卡点变成「可以嗎?」的「はい」选不了**。

---

## 1. 改动文件（完整绝对路径）

### 1.1 本仓库（`D:\Github\gba-naruto`）—— 本流独占

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_battle.py` | **改** | ⭐ 闭环驱动器升级：① **射程口径修正**（计划按 (敌人 × 招式) 组合打分，招式的射程决定站位；`find_attack_cell` 优先「原地已在射程内」）；② `--use-tools`（原版 `w4_play.py` 就是用十字手里剑）；③ ⭐ **只按键走结算链**（`play_settlement_chain`：按帧 sha256 认页、按钮不回则换键、**绝不 poke**）；④ 收据新增 `entry`（自报 method/poke）与 `acceptance`（outcome/蜂 HP/护送/poke 计数）**机器可判**块；⑤ `--poke-settlement`（**仅工具自检**，收据自报 poke=true、acceptance=false） |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_compare.py` | **改** | ⭐ **逐屏对照的配对修正**：先按 **sha256 相同**配对（唯一不依赖文件名的配对），剩下的再按相位顺序配对；`TRUTH_BY_PHASE` 的升级屏顺序改成**按像素 sha 验证过的**顺序 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_freeze.py` | **改** | 参数化（`--rom/--exe/--out/--index/--cells`），并落 `freeze-report.json` |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_probe.py` | **改** | 记录发往探针的**每一条命令** ⇒ 收据能自报 `poke_commands`，「不是 poke」变成**可验证**的事实 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_d4_watch.py` | **新增** | ⭐ **ROM 看门狗**：盯重制 ROM 的 sha，等它**稳定**（连续两次同 sha）就自动重测 D4 并落报告；U1 一落地就自动复测 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_active.py` | **新增** | ⭐ **D4 的细粒度定位器**：用真驱动器走到「招式在射程内」，确认后**逐 50 帧轮询**遥测 3 000 帧，并把**遥测结构体的头 32 字节**在故障前后各转储一次 ⇒ 分清「冻住」「输入死」「状态被写坏」 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_confirm.py` | **新增** | ⭐ **「可以嗎?」对话框的逐输入定位器**：走到对话框、把它**拍下来**（`confirm-00.png`），然后**逐个试** A / Up+A / Down+A / Left+A / B / 无输入 ⇒ 分清「产品拒绝」与「按键错」 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_repeat.py` | **新增** | ⭐ **两次独立跑逐字节一致**的判定器：逐文件 sha + 收据归一化摘要（剔除路径/时长） |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_accept.py` | **新增** | ⭐ **一条命令出全部验收证据**：两跑 + 逐屏对照 + 逐字节一致 → `acceptance.json` |
| `D:\Github\gba-naruto\notes\s49-fidelity\U4-real-victory-verify.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\build\v1-u4\**` | 产物 | 钉住的 ROM、两次跑的收据与 48 张结算帧、逐屏对照表、逐字节一致报告、D4 复测报告、看门狗报告、私有探针 `build\mgba-probe-u4\mgba-probe.exe`。 |

### 1.2 没有改的

* **重制线 `D:\Shell\Github\gba-naruto-butano\butano-sequel` 零改动**（只读地看了
  `battle_combat_presentation.h` / `battle_scene_presentation.h` / `battle_runtime_scene.cpp` 的 mtime 与 git 状态）；
* `tools\s49_victory_align\align_settlement.py` **只读复用**（未改一行）；
* `tools\s49_package\`（U3 独占）零改动；
* 共享的 `build/mgba-probe/mgba-probe.exe` **未动**（用的是私有的 `build/mgba-probe-u4/`）；
* 逆向线 `D:\Shell\gba-naruto-reverse` 未访问。

---

## 2. ⭐ 本波真正改变结论的五件事

### 2.0 ⭐⭐ U1 的修复落地了：**D4 的「写坏状态」消失**，但卡点前移到「可以嗎?」

* 看门狗在会话末尾抓到 ROM 变成 **`16bf746fc254de37…`**（U1 改了 `battle_runtime_scene.cpp`，mtime 23:11:55），
  自动复测 ⇒ **D4 present = False（0/3 冻住）**：
  离蜂 3 格 / 2 格 / 5 格确认忍具 1 ⇒ 场景帧 **全部继续推进**（511→555 / 520→564 / 490→534），相位 **6 → 8**。
* ⇒ **U1 修掉了「确认招式 ⇒ 战斗状态被写坏 + 场景停住」**（§2.1.1 记的那个签名
  `phase → 0x0029F001` 不再出现）。
* ⇒ **但玩家的攻击仍然打不中**，卡点往前挪了一步：

| 阶段 | 相位 | 现象（ROM `16bf746f…` 实测） |
|---|---|---|
| 招式确认 | 6 → **8** `target_selection` | ✅ **通了**（之前在这里就写坏状态） |
| 目标确认 | 8 → **22** `target_preview` | ✅ **通了**（收据里有 `target-accepted`，目标格 (6,6)） |
| 「可以嗎?」 | 22 → **20** `target_confirmation` | ⛔ **停在这里**：场景帧不再推进 |

* ⭐ **停住的原因由产品自己说出来了**：屏幕上是原版的 **「可以嗎?」** 对话框
  （`はい` / `いいえ`），**光标在「はい」上**，**按下之前没有任何报错**；
  **按 A ⇒ 产品自己显示 `CANNOT SELECT`**（截图 `build/v1-u4/diag-confirm2/after-trials.png`）。
* ⭐ **原版的做法就是按 A**：`w4_play.py::try_attack` 的注释写着
  `forecast -> 可以嗎? -> resolution`，实现是 `if screen in ("message","confirm"): press("A")`。
  ⇒ **重制侧「はい」这个条目选不了 ⇒ 玩家的攻击永远无法结算** ⇒ **产品的缺陷，不是驾驶器的按键错**。
* 逐个试过对话框上的输入（`build/v1-u4/diag-confirm5/`）：

| 输入（相位 20） | 结果 |
|---|---|
| 什么都不按 | 场景**正常推进**（657 → 709），对话框一直挂着 ⇒ **不是卡死，是等待输入** |
| **A**（「はい」） | 产品回 **`CANNOT SELECT`**，随后场景停住 |
| **Up+A** | 回到相位 **22**（预览）⇒ 等于取消 |
| **Down+A** | 回到相位 **22**（预览）⇒ 等于取消 |
| **Left+A / Right+A** | 相位不变，`control_error = 3` ⇒ **左右动的是地图光标，不是对话框光标**（对话框光标是上下） |
| **B** | 场景停住 |

* ⇒ **结论（交给 U1 的下一个待修点）**：
  **重制侧的「可以嗎?」对话框里，「はい」这个条目在「射程内有活敌人」的确认时选不了
  （产品自报 `CANNOT SELECT`）**，⇒ 攻击无法结算。
  驾驶侧已排除：对话框本身正常（无输入时场景照常推进）、光标在「はい」上、
  原版的按键口径就是 A。
* ⇒ ⚠️ 这个卡点 **U1 的这次修复没有覆盖**（它修的是「状态被写坏」）。

### 2.1.0 ⭐ D4 的**修前状态**（历史记录：ROM `3973adcd…` / `a52c6424…`）

看门狗对**两个** ROM 各测一次「离蜂 ≤3 格确认忍具 1」：

| ROM sha | 落点 | 离蜂 | 确认忍具 1 之后 | scene_frame | 判读 |
|---|---|---:|---|---|---|
| `3973adcd4b329d89…`（wave 16 V3 定稿） | (9,6) | 3 | ⛔ 冻住 | 515 → 516 | 场景不再推进 |
| 同上 | (8,6) | 2 | ⛔ 冻住 | 527 → 528 | 场景不再推进 |
| 同上 | (11,6) | 5 | ✅ 正常（相位 6 → 8） | 495 → 541 | 出了目标选择 |
| `a52c64246e337877…`（U2 22:34 重建） | (9,6) | 3 | ⛔ 冻住 | 515 → 516 | 同上 |
| 同上 | (8,6) | 2 | ⛔ 冻住 | 526 → 527 | 同上 |
| 同上 | (11,6) | 5 | ✅ 正常（相位 6 → 8） | 494 → 540 | 同上 |

⇒ **判据仍是「射程内有活着的敌人」，与落点/方向/步数无关**（与 V1 的结论一致）。
⇒ **U1 的两个独占头文件 `battle_combat_presentation.h` / `battle_scene_presentation.h` 至今
mtime = 2026-10-20 14:03、未被修改** ⇒ **D4 的修复尚未落地**。

### 2.1.1 ⭐⭐ D4 的**确切签名**（本流新测，U1 可直接用）

V1 把 D4 记成两种现象（「忍具冻住 ROM」+「普通招式输入死」）。
本流用 `v1_diag_active.py` 在**当前 ROM** 上逐 50 帧轮询 ⇒ **两种现象是同一个 bug**，
而且**不是「卡住」，是「状态被写坏」**：

| 招式 | 确认前 | 确认后（轮询） | 故障后的遥测结构体头 32 字节 |
|---|---|---|---|
| **忍具 1**（action 1，range 3，鸣人落到 (9,6)） | 相位 6、scene_frame **515**、`c_stage=8 c_frame=0 c_impact=-1` | scene_frame **停在 516**；约 150 帧后 **相位字变成 2752561 = 0x0029F001**；光标跳到 (15,6)（越界） | 同下 |
| **忍者组合拳**（action 5，range 1，鸣人落到 (8,6)，蜂在 (8,7)） | 相位 6、scene_frame **2123**、`c_frame=0`、`c_impact=-1` | scene_frame **停在 2123**；轮询第 4 次（约 150 帧后）**相位字变成 2752561 = 0x0029F001**、`act_err=7`、`ctrl=7` | 见下表 |

遥测结构体（基址 `0x02025EF0`）故障前 → 故障后：

| 字 | 故障前 | 故障后（+120 帧再读，**不变** ⇒ 一次写完） |
|---|---|---|
| `magic` | `0x4B42544C` | **`0x4B6C5476`** |
| `battle_id` | `0x0000000E` | `0x0000000E`（未动） |
| `phase` | `0x00000006` | **`0x002A0031`** |
| `round` | `0x00000002` | `0x00000002`（未动） |
| `current_side` | `0x00000000` | **`0x002A002B`** |
| `selected_unit` | `0x00000001` | `0x00000001`（未动） |
| `active_unit_count` | `0x00000009` | **`0x002A0034`** |
| `unit_count` | `0x0000000C` | `0x0000000C`（未动） |

⇒ **结论（交给 U1 的事实，不含猜测）**：
1. 触发条件：**确认一个射程内有活敌人的招式**；
2. 后果：**约 100–150 帧后战斗状态在 EWRAM 里被写坏**（遥测结构体头 32 字节里有 4 个字被覆盖），
   **同时场景帧停止推进**；
3. 覆盖是**一次性**的（+120 帧再读不变），不是失控循环；
4. 被覆盖的字的**高 16 位都是 `0x002A`**、低 16 位变成 `0x31/0x2B/0x34`，
   `magic` 变成 `"vTlK"`（原 `"LTBK"`）⇒ **像是把一段文本/格式化缓冲写到了战斗状态上**
   （与 wave 15 记的结算段「Invalid UTF-8 character」崩溃可能是同一族：文本缓冲越界）；
5. ⇒ V1 的「现象 A / 现象 B」是**同一个 bug**，不是两个；
6. ⇒ **驱动器侧无法绕过**：只要射程内有活敌人，确认就会毁掉战斗状态。

> ⚠️ 第 4 点是**形状相似**的观察，不是结论；源码侧的定位（谁在写、写到哪）是 U1 的活。

### 2.1.2 附带发现：`--max-turns` 是**相位步数**预算，不是回合数

`play_battle()` 的 `for turn in range(max_turns)` 每次相位切换就 `continue` 一次
⇒ `--max-turns 12` 只够走 12 个相位（≈1 个回合），驱动器会「看起来卡住」。
**V1 的运行用的是 `--max-turns 400`** ⇒ 复现时请用同样的量级。

### 2.2 ⭐ 仪器缺陷（**本流修**）：逐屏对照的**真值配对是错位的**

把 W1 的 poke 链（`build/w1/chain-d/shots`，90 页）与原版真值目录按 **sha256** 对撞：

| remake 链页 | remake 的 sha256 | 命中真值 | 旧配对（按文件名顺序） | 旧数字 | **正确数字** |
|---|---|---|---|---:|---:|
| level_up #1 | `a876f32d…` | `03-levelup-naruto.png` | 03-levelup-naruto ✓ | 0 | **0** |
| level_up #2 | `daac884a…` | `05-levelup-sasuke-jutsu-name.png` | 04-levelup-konohamaru ✗ | 5 870 | **0** |
| level_up #3 | `ef0808ae…` | `04-levelup-konohamaru.png` | 04-levelup-sasuke ✗ | 5 946 | **0** |
| level_up #4 | `c5a8440b…` | `05-levelup-sasuke.png` | 05-levelup-sasuke-jutsu-name ✗ | 5 229 | **0** |
| level_up #5 | `a0db87e9…` | `06-levelup-sakura.png` | 05-levelup-sasuke ✗ | 5 639 | **0** |
| level_up #6 | `455acc43…` | `07-ninja-tool-list.png` | 06-levelup-sakura ✗ | 841 | **0** |
| training #1 | `b012f605…` | （无对应真值） | 07-ninja-tool-list ✗ | 14 795 | **无对应** |

⇒ **结论**：**重制侧的升级屏 6 屏本来就是逐像素全对的（6/6 = 0 px）**；
旧的 5 870 / 5 946 / 5 229 / 5 639 / 841 / 14 795 是**配错真值帧**造出来的数，
**不是重制线的残差** ⇒ **U2/U3 的「升级屏残差」这一项可以直接销账**。
⇒ 同时查实：真值目录里的 `07-ninja-tool-list.png` 是**升级链的第 6 屏**（刚学会的忍具），
**不是**「忍具一览」相位 ⇒ 真值**没有**「training」相位的对应帧。

**修法**：`v1_compare.py` 改成**先按 sha256 配对**（唯一不依赖文件名的配对），没配上的再按相位顺序配对；
`TRUTH_BY_PHASE` 的升级屏顺序改成**按像素 sha 验证过的**顺序。

### 2.3 ⭐ 仪器改进：**结算链可以「只按键」走完**，而且旧数字里有一张是**拍到黑场**

V1 的结算链沿用了 `y1_play.play_settlement`（**按固定帧数盲按 A**），
⇒ 拍到的是**黑场淡入**，不是屏幕本身 ⇒ wave 15/16 的「**胜利屏 37 462 px**」是**仪器假象**。

本流新增 `play_settlement_chain()`（只按键，**绝不 poke**）：
* **按帧的 sha256 认页**（training 相位有 6 个子页，共用一个相位 ⇒ 相位不足以认页）；
* 画面稳定后才拍（**连续两帧相同**才算稳定）⇒ 不会拍到黑场；
* 按键没反应就**换下一个键**（A → B → Right → Down → Left → Up），最后一张 training 子页会吞掉 A。

在当前 ROM（`a52c6424…`）上实测：**48 页，outcome → task_menu 走完，训练段不再崩**
（wave 15 记的「training 段 UTF-8 崩溃」已不复现）。

⇒ **逐屏对照表（当前 ROM，真值收据 sha `9a60a89b…`）**：

| remake 链页 | 相位 | 原版真值 | 原版 sha256（前 16） | 重制侧 sha256（前 16） | 差 px | 差 bbox |
|---|---|---|---|---|---:|---|
| `page-000-outcome.png` | outcome | `01-victory.png` | `d60a1d35e45736db` | `d60a1d35e45736db` | **0** | — |
| `page-001-result.png` | result | `02-settlement-exp-power-turns.png` | `e34e116c7ed3a55e` | `337661386808…` | **2 582** | `[84,49,236,154]` |
| `page-002-level_up.png` | level_up | `03-levelup-naruto.png` | `a876f32dbe100a65` | `a876f32dbe100a65` | **0** | — |
| `page-003-level_up.png` | level_up | `05-levelup-sasuke-jutsu-name.png` | `daac884a6415577b` | `daac884a6415577b` | **0** | — |
| `page-004-level_up.png` | level_up | `04-levelup-konohamaru.png` | `ef0808aea763ff31` | `ef0808aea763ff31` | **0** | — |
| `page-005-level_up.png` | level_up | `05-levelup-sasuke.png` | `c5a8440b451ef6a1` | `c5a8440b451ef6a1` | **0** | — |
| `page-006-level_up.png` | level_up | `06-levelup-sakura.png` | `a0db87e9fd8ec358` | `a0db87e9fd8ec358` | **0** | — |
| `page-007-level_up.png` | level_up | `07-ninja-tool-list.png` | `455acc43c9ace553` | `455acc43c9ace553` | **0** | — |
| `page-008…013-training.png` ×6 | training | **真值无对应帧** | — | — | — | — |
| `page-014-post_battle_dialogue.png` | post_battle_dialogue | `08-postbattle-dialogue-1.png` | `2741dbc3fbf6e838` | `5fece4f6952f78b0` | **26 819** | `[0,0,240,160]` |
| `page-015…020-post_battle_dialogue.png` ×6 | post_battle_dialogue | 真值只有 1 帧 | — | — | — | — |
| `page-021-task_menu.png` | task_menu | `09-task-menu-map.png` | `cda07a18be60a1ea` | `3814df2825813f89` | **37 694** | `[0,0,240,160]` |
| `page-022…047-task_menu.png` ×26 | task_menu | 真值只有 1 帧 | — | — | — | — |

> ⚠️ **上表是「工具自检链」**（进链方式见 §3 的 U4-6），**不是真实战斗链**：
> 它的**胜利屏/升级屏**已经与原版逐像素相同，**结算屏只差数值**（2 582 px，bbox 正好在数字区 `[84,49,236,154]`），
> 这与 wave 16 V2 的「結算屏 35 859 → 2 582 px」**逐项相同** ✓ ⇒ **工具是对的**。
> **真实战斗链**要等 D4 修好才有（§5）。

---

## 3. 驾驶侧：驱动器为什么还打不中（**这次修的是我自己的缺陷**）

### 3.1 ⭐ 找到一个**驾驶侧**缺陷：计划的射程口径与实际确认的招式不一致

* **旧计划**：`reach = max(所有可用招式的射程)` = **3**（忍具的射程），
  于是它走到**离蜂 2–3 格**的格子；
* **旧执行**：只会确认 **active** 招式（忍者组合拳，射程 **1**）⇒
  `definition["range"] >= gap` 恒假 ⇒ 「**no attack reaches the target**」⇒ **整回合空过**。
* ⇒ 旧驱动器**即使 D4 修好也打不中**：它站的位置离蜂 2–3 格，而它唯一肯用的招式射程是 1。
  （V1 记的 run-a 里「gap=2 ⇒ chosen=null」就是这件事。）

**修法**（照抄原版 `w4_play.py::act` 的口径）：
* 计划把**招式**当成候选的一部分：`(敌人 × 招式)` 组合各自算站位、伤害、分数；
* `find_attack_cell` **先看原地**：原地已在射程内就**不移动**（原版也是先试 origin）；
* 执行阶段按**招式在招式表里的下标**走光标（活的招式表顺序 = 目录顺序），
  读回 `(source, action_id, target_kind, error)` **自证**落在正确的条目上。

**修完的实测**（当前 ROM `a52c6424…`，`--use-tools`）：

```
plan   : want = {index 3, source 1(忍具), action_id 1, range 3, potency 6, hits 3, rate 90}
         gap = 3   damage = 27          ← 与原版 w4_play.py 的 ATTACKS 表「十字手里剑 27 伤害」逐字相同 ✓
walk   : chosen = {index 3, action_id 1, source 1, target_kind 2(敌), error 0}   ← 精确落在忍具条目上 ✓
confirm: action-refused（相位没离开 action_selection）→ scene-input-dead（光标再也不动）
```

⇒ **驾驶侧已经能「选中正确的招式、站到正确的位置、按下确认」**；
**唯一剩下的是产品的 D4**（确认后战斗演出不结束 ⇒ 输入全死 / ROM 冻住）。

### 3.2 结算链：**只按键、绝不 poke**

* `play_settlement_chain()`：按帧 sha256 认页 + 稳定后拍 + 按钮不回就换键；
* **不使用**任何 `poke`（收据里 `entry.poke_commands` 就是证据）；
* 收据里另有 `--poke-settlement`（**仅工具自检**）：它 poke 控制器的相位/结局来进链，
  但收据会自报 `entry.poke = true`、`entry.method = "TOOL VALIDATION: …"`、
  且 `acceptance.from_real_battle = false` ⇒ **poked 链永远冒充不了真实链**。

---

## 4. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 / 判读 |
|---|---|---|
| **U4-1** | `python tools/s49_battle_balance/v1_d4_watch.py --rom <重制ROM> --out build/v1-u4/watch --minutes 180 --poll 45` | 看门狗：对 ROM `3973adcd…` 与 `a52c6424…` 各测一次 ⇒ **D4 仍在**（2/3 冻住），报告 `build/v1-u4/watch/watch.json` |
| **U4-2** | `python tools/s49_battle_balance/v1_diag_freeze.py --rom build/v1-u4/rom-pinned.gba --exe build/mgba-probe-u4/mgba-probe.exe --out build/v1-u4/diag-freeze-current --index 3 --cells "9,6;8,6;11,6"` | (9,6) 515→516 冻住；(8,6) 527→528 冻住；(11,6) 495→541 正常（相位 6→8） |
| **U4-3** | `python tools/s49_battle_balance/v1_battle.py … --out build/v1-u4/smoke-notools --boot --max-turns 12` | 改造后的驱动器在当前 ROM 上跑通回合链，收据含 `acceptance` 块（`from_real_battle=false`，`poke_commands=0`） |
| **U4-4** | 同上 `--out build/v1-u4/smoke-tools --use-tools` | ⭐ 计划选中**忍具 1（伤害 27，与原版表相同）**，光标**精确落在 index 3**（`error 0`）⇒ 确认后 **D4**（`action-refused` → `scene-input-dead`） |
| **U4-5** | `python tools/s49_battle_balance/v1_battle.py … --out build/v1-u4/chain-toolcheck --boot --poke-settlement` | **48 页**，outcome → task_menu 走完，训练段不崩；**0 次业务 poke**（只有进链那 27 条） |
| **U4-6** | 同上 `--out build/v1-u4/chain-toolcheck2 --poke-settlement` | 第二次独立跑（用于 U4-7） |
| **U4-7** | `python tools/s49_battle_balance/v1_repeat.py --a build/v1-u4/chain-toolcheck --b build/v1-u4/chain-toolcheck2 --out build/v1-u4/repeat-chain-toolcheck.json` | ⭐ **72/72 文件逐字节相同**（含 48 张结算帧 + 开机帧），收据归一化摘要两边同为 `a7c25ab8142a6e18…` ⇒ `identical: true` |
| **U4-8** | `python tools/s49_battle_balance/v1_compare.py --remake build/v1-u4/chain-toolcheck/shots --out build/v1-u4/compare-chain-toolcheck.json` | ⭐ **胜利屏 0 px**、结算屏 **2 582 px**、**升级屏 6/6 = 0 px**、战后对白 26 819、任务菜单 37 694（见 §2.3 全表） |
| **U4-9** | `python tools/s49_battle_balance/v1_compare.py --remake build/w1/chain-d/shots --out build/v1-u4/compare-poke-corrected.json` | **对旧 poke 链重算**：旧 5 870 / 5 946 / 5 229 / 5 639 / 841 / 14 795 **全部归 0 / 无对应** ⇒ 旧数字是配对错位造出来的 |
| **U4-10** | `python -c "…v1_battle.acceptance(…)"`（单元级） | `acceptance()` 的四个判据（胜利/蜂掉血/护送存活/poke=0）逐条断言通过；人为把 `poke_commands` 设成 3 ⇒ `from_real_battle=false` ✓ |
| **U4-11** | `python tools/s49_battle_balance/v1_accept.py --rom … --out … --use-tools` | **一条命令出全部验收证据**（两跑 + 对照 + 逐字节一致 → `acceptance.json`）——**D4 修好后直接跑这一条即可** |
| **U4-12** | `python tools/s49_battle_balance/v1_diag_active.py --rom build/v1-u4/rom-pinned.gba --out build/v1-u4/diag-active4 --max-turns 400 --observe-polls 60 --poll-frames 50` | ⭐ **D4 的确切签名**（§2.1.1）：普通招式在射程内确认 ⇒ 场景帧停在 **2123**、约 150 帧后**相位字变 `0x0029F001`**；遥测头 32 字节里 **4 个字被写坏**（§2.1.1 表），+120 帧再读**不变** |
| **U4-13** | `python tools/s49_u1_d4/u1_diag.py --rom build/v1-u4/rom-pinned.gba --exe build/mgba-probe-u4/mgba-probe.exe --out build/v1-u4/u1-diag --move-cell 9,6 --action-index 3 --target 6,6 --observe 600 --poll 60` | ⭐ **U1 的工具在我改过的 `v1_battle` 上照常工作**（未被我改坏）；忍具路径给出**同一个** `2752561` 签名 ⇒ 两个现象同一 bug |
| **U4-14** | 同上 `--out build/v1-u4/u1-diag-active --move-cell 7,6 --action-index 2 --target 6,6` | ⚠️ 该次**移动被 ROM 拒绝**（(11,6)→(7,6) 是 4 步 > 移动力 3）⇒ 鸣人仍在 (11,6)、招式超程（`act_err=9`）⇒ **该次不构成 D4 的反例**；也顺带证明「驱动器选的落点一定在移动力之内」（我的 `reachable()` 限 3 步） |
| **U4-15** | `python tools/s49_battle_balance/v1_battle.py … --out build/v1-u4/det-a / det-b --max-turns 12 --use-tools` + `v1_repeat.py` | **战斗阶段也逐字节一致**：23/23 文件 + 收据摘要同为 `a4f28983abc3d993…` ⇒ 战斗里的随机（忍具 90 % 命中）是**确定性的**（固定种子） |
| **U4-16** | `python tools/s49_battle_balance/v1_accept.py --rom build/v1-u4/rom-pinned.gba --exe build/mgba-probe-u4/mgba-probe.exe --out build/v1-u4/accept --use-tools --max-turns 1200`（ROM `16bf746f…`） | ⭐ **验收流水线端到端跑通**：`poke_commands=0` ✓、`two_runs_identical=true` ✓、`compare_returncode=0` ✓、**`passed=false`**（只差 `real_victory`/`bee_hp_dropped` ⇒ **就是「可以嗎?」的卡点**）；`screens=0`（没打赢 ⇒ 没有结算链可对照） |
| **U4-17** | 看门狗自动复测 ROM `16bf746fc254de37…` | ⭐ **D4 已修**：离蜂 3/2/5 格确认忍具 1 ⇒ 场景帧 **全部继续推进**（511→555 / 520→564 / 490→534）、相位 6→8 ⇒ `d4_present = False`（0/3） |
| **U4-18** | `python tools/s49_battle_balance/v1_diag_confirm.py --rom build/v1-u4/rom-pinned.gba --out build/v1-u4/diag-confirm5 --move-cell 9,6 --action-index 3 --target 6,6 --trials "Up+A"` | ⭐ 「可以嗎?」对话框：**不按任何键时场景照常推进**（657→709）；**A** ⇒ 产品自报 `CANNOT SELECT`；**Up+A / Down+A** ⇒ 回到相位 22（取消）；**Left/Right** ⇒ 动的是地图光标（`control_error=3`）；**B** ⇒ 场景停住 |
| **U4-19** | `python tools/s49_battle_balance/v1_battle.py … --out build/v1-u4/plain-battle2 --no-tools --max-turns 1200` | ⭐ **普通招式**同样走到 `target_confirmation` 并停住；冻结屏 `shot-001-rom-frozen-phase20.png` 上是「可以嗎?」对话框（预览面板显示 **16 伤害 / 92 %**，与 `preview_damage(10,1,18,6)=16` 一致）⇒ **不是忍具专属** |
| **U4-20** | `python tools/s49_battle_balance/v1_battle.py … --out build/v1-u4/accept/run-a`（同一 ROM，`--use-tools`） | ⭐ 收据里有 **`target-accepted`**（目标格 (6,6)、蜂 slot 7）⇒ **驾驶侧的目标选择是对的**；之后卡在 `target_confirmation` |

> 说明：U4-5/U4-6/U4-8 是**工具自检链**（进链方式 poke，收据自报），
> **不是真实战斗链**；它们证明的是**仪器**（逐屏对照 + 只按键走链 + 逐字节一致）是对的。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **U4-1** | D4 已在本波被 U1 修好（ROM 会变） | 看门狗盯 ROM sha，稳定即重测 `v1_diag_freeze.py` | **不成立**：ROM 从 `3973adcd…` 变成 `a52c6424…`（U2 重建），**D4 仍在**（2/3 冻住）；U1 的两个独占头文件 mtime 仍是 10-20 | **已证伪** |
| **U4-2** | ⭐ 驾驶侧打不中只是因为 D4 | 重读 V1 的 run-a 决策日志 | **不成立（部分）**：**另有驾驶侧缺陷**——计划射程 3、执行只用射程 1 的招式 ⇒ 整回合空过；已修（§3.1） | **已证伪并已修** |
| **U4-3** | ⭐ 修好射程口径后，驱动器会「选中忍具并站到位」 | 在当前 ROM 上跑 `--use-tools`，读 `action-list` 决策 | **成立**：`want = {index 3, source 1, action_id 1, range 3}`、`damage 27`（= 原版 `w4_play.py` 的表）、`chosen.error = 0` ⇒ 光标精确落在忍具条目上 | **已确认** |
| **U4-4** | ⭐ 结算链的「升级屏残差 5 870/5 946/… 是产品差」 | 把 remake 链页与真值目录按 sha256 对撞 | **不成立**：升级屏 **6/6 逐字节相同**（旧数字来自**配对错位**）；真值的 `07-ninja-tool-list.png` 其实是**升级链第 6 屏**，training 相位**没有**真值帧 | **已证伪并已修** |
| **U4-5** | ⭐ 「胜利屏 37 462 px」是产品差 | 用「按 sha 认页 + 等画面稳定」的走链器重拍胜利屏 | **不成立**：稳定后拍到的胜利屏与真值 **sha 相同、差 0 px** ⇒ 旧数字是**拍到黑场**的仪器假象 | **已证伪并已修** |
| **U4-6** | 结算链**不能**只按键走完（training 段会崩） | 在当前 ROM 上只按键走 48 页 | **不成立**：训练段不崩，链走到 task_menu（wave 15 记的 UTF-8 崩溃已不复现） | **已证伪** |
| **U4-7** | 两次独立跑不逐字节一致（战斗里有随机） | `v1_repeat.py` 比两次跑的 72 个文件 + 收据 | **不成立**：72/72 + 收据摘要相同 ⇒ **逐字节一致** | **已证伪（已确认一致）** |
| **U4-8** | ⭐ `outcome=1` 只能在「战斗真的打赢」时出现 | 收据的 `acceptance` 块：outcome / 蜂 HP / 护送 / `poke_commands` | **可判定、已实现**：`from_real_battle = decided && outcome==1 && poke_commands==0`；**当前 ROM 上仍为 false**（D4） | **待验（等 U1）** |
| **U4-9** | 蜂的 HP 在真实战斗里会下降 | 同上（`bee_hp_dropped`） | **可判定、已实现**；当前 ROM 上 bee 全程 25/25 | **待验（等 U1）** |
| **U4-10** | 护送木叶丸能活到胜利 | 同上（`escort_alive`） | **可判定、已实现**；当前 ROM 上护送 40 HP 起步 | **待验（等 U1）** |
| **U4-11** | 忍具的伤害是 27（原版 `w4_play.py` 的表） | 驱动器的 `preview_damage(6, 3, 18, 6)` | **成立**：`(6*18//10) * (100-5*isqrt(6))//100 * 3 = 9*3 = 27` ✓ | **已确认** |
| **U4-12** | ⭐ D4 是「两个现象」（忍具冻 ROM / 普通招式输入死） | `v1_diag_active.py` 逐 50 帧轮询 + 故障前后转储遥测头 32 字节 | **不成立**：**两者同一签名** —— 场景帧停住 + **战斗状态被写坏**（相位字 → `0x0029F001` / `0x002A0031`）；「输入死」只是「相位字段已成垃圾」的表象 | **已证伪（已修正 V1 的表述）** |
| **U4-13** | ⭐ D4 是「场景卡住 / 演出不结束」 | 同上，看故障后 +120 帧的再次转储 | **不成立**：被覆盖的字**不再变化** ⇒ 是一次性写坏；而且写坏的是**战斗状态本身**（magic/phase/current_side/active_unit_count 四个字） | **已证伪（已修正 V1 的表述）** |
| **U4-14** | 驱动器在射程内确认招式后会「卡住」 | 逐 50 帧轮询 3 000 帧 | **不成立**：不是驱动器卡住，是**产品在确认后写坏了状态**；轮询里场景帧停在 2123 不动、错误码 7/7 | **已证伪** |
| **U4-15** | 驱动器「看起来卡住」是驱动器的问题 | 读决策日志 | **不成立**：`--max-turns` 是**相位步数**预算（§2.1.2）；给够 400 就能继续走 | **已证伪（已记录）** |
| **U4-16** | ⭐ U1 的修复会连带把「可以嗎?」也修好 | 看门狗复测 + 跑真实战斗 | **不成立**：D4 的写坏消失（0/3 冻住）、攻击能走到 `target_confirmation`，但**「はい」选不了**（产品自报 `CANNOT SELECT`）⇒ **新的卡点** | **已证伪** |
| **U4-17** | ⭐ 停在 `target_confirmation` 是「ROM 卡死」 | 不按任何键地观察 300 帧 | **不成立**：**场景照常推进**（657→709）⇒ 是**等待输入**，不是死循环；「按 A ⇒ CANNOT SELECT ⇒ 场景停住」才是致命的那一步 | **已证伪（已修正）** |
| **U4-18** | 停在对话框是**驾驶侧按键错** | 逐个试 A / Up+A / Down+A / Left+A / Right+A / B / 无输入；比对原版 `w4_play.py` 的口径 | **不成立**：原版的口径就是**按 A**；其它键分别是取消 / 动地图光标 / 停住 ⇒ **「はい」选不了是产品缺陷** | **已证伪（驾驶侧已排除）** |

---

## 6. 卡在哪 / 剩余风险

1. ⛔ **卡点 = 重制侧「可以嗎?」对话框的「はい」条目选不了**（**U1 的这次修复没有覆盖它**）：
   * U1 的修复（ROM `16bf746f…`）**修掉了 D4 的「状态被写坏」**（§2.0）；
   * ⇒ 现在的链路能走到 `target_confirmation`（相位 20），**对话框正常、光标在「はい」上**、
     **不按任何键时场景照常推进**；
   * ⇒ **按 A 会被产品自己回 `CANNOT SELECT`**（原版 `w4_play.py` 的口径就是按 A）
     ⇒ **玩家的攻击无法结算** ⇒ **蜂打不死** ⇒ `outcome=1` 仍不可达、护送仍会在第 5 回合被护送失败；
   * 驾驶侧已排除按键问题（逐个试过 A / Up+A / Down+A / Left+A / Right+A / B / 无输入，§2.0 的表）；
   * ⇒ **这是产品的缺陷**，修好之后**不用改驾驶侧**，直接跑下面的命令就能出验收证据：
     ```powershell
     # 0) 先把 ROM 钉住（并行流随时会重建 ROM）
     Copy-Item <重制ROM> build/v1-u4/rom-pinned.gba -Force
     python tools/s49_battle_balance/v1_accept.py --rom build/v1-u4/rom-pinned.gba `
            --exe build/mgba-probe-u4/mgba-probe.exe --out build/v1-u4/accept --use-tools --max-turns 1200
     # ⇒ 一次跑完：两跑 + 逐屏对照 + 逐字节一致 ⇒ build/v1-u4/accept/acceptance.json
     ```
     判据：`acceptance.json` 的 `passed = true`
     （`real_victory` ∧ `bee_hp_dropped` ∧ `escort_alive` ∧ `two_runs_identical`），
     且 `poke_commands = 0`。
   * **定位用的小工具**（本流新增，只读）：
     `python tools/s49_battle_balance/v1_diag_confirm.py --rom <ROM> --move-cell 9,6 --action-index 3 --target 6,6 --trials "A"`
     ⇒ 会把「可以嗎?」对话拍下来（`confirm-00.png`）并逐个试输入。
2. ⚠️ **ROM 会变**（并行流在改重制线）：本流的结论都绑在 sha 上；
   看门狗会把每个新 ROM 钉进 `build/v1-u4/watch/rom-<sha8>.gba` 并自动复测 D4
   （本波它抓到了 U1 的修复 ⇒ `d4_present=false`）。
3. ⚠️ **`--use-tools` 的安全边界**：忍具的悬停/确认在 D4 未修时会让 ROM 冻住 ⇒
   **D4 复测没过之前不要带 `--use-tools` 跑长局**。
4. ⚠️ **`v1_compare.py` 的数字变了**（§2.2）：旧的「升级屏残差」是配对错位 ⇒
   **U2/U3 若引用了旧数字，需要按 §2.3 的表更新**（升级屏 6/6 = 0 px）。
5. ⚠️ **本流对判定台残差零影响**：没有改任何产品代码，也没有改判定台/流水线。
6. ⚠️ **`v1_battle.py` 的默认行为变了**（工具默认**不开**、射程口径改了）⇒
   **V1 笔记里的旧数字（run-a / run-passive 的 sha）不再由新代码复现**；这是**有意的**，
   本笔记 §3.1 记录了改动理由。

---

## 7. 确认

* **新文件一律 LF、无 BOM**（`v1_d4_watch.py` / `v1_repeat.py` / `v1_accept.py` /
  `v1_diag_active.py` / `v1_diag_confirm.py` / 本文件；改动的 `.py` 也保持 LF）；
* **未提交 git**（两个仓都没有 `git add/commit`）；
* **未改重制线任何文件**（只读：看了 mtime 与 git 状态）；
* **未改 `tools\s49_package\`**（U3 独占）、**未改 `tools\s49_victory_align\`**（只读复用）；
* **逆向线只读**（未访问 `D:\Shell\gba-naruto-reverse`）；
* **未覆盖共享的 `build/mgba-probe/mgba-probe.exe`**（用的是私有的 `build/mgba-probe-u4/`）；
* **未同时开两个全量录制**（只跑探针，不跑 recorder）。
