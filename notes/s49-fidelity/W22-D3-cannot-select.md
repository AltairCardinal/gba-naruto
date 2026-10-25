# W22-D3 —— 「CANNOT SELECT」实跑验证（wave 22 / D3 流）

> 2026-10-25 22:18 起 · 流：D3（「CANNOT SELECT」的实跑验证）· 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 上游：`W20-EXEC-BRIEF.md` · `W21-C1-camera-pan.md` §8 · `W21-C2-press-divergence.md` · `W18-W2-confirm-yes-unselectable.md`
> 本流**不改任何产品文件**；产物：`tools/s49_w22d3/` · `build/w22-d3/` · 本笔记
> 探针：`build/mgba-probe-w22d3/mgba-probe.exe`（**私建**，绝不用 `build/mgba-probe-w4/`）

---

## 0. 状态（**全部四步完成 · 结论决定性**）

> ⭐⭐⭐ **第 1 步实测完成，结论决定性：**
> **「CANNOT SELECT」** **不是产品缺陷** —— 在 `target_selection` 相位里
> **方向键能移动光标**（(11,6) → (12,6)），**移动后 A 立刻生效**，
> **整条真实链一路走到 `facing_selection`（准备出手）**。
> ⇒ **是 walk 的按键方式问题**（那次 walk 在 `target_selection` 里一次方向键都没按）。
>
> ⭐⭐⭐ **第 4 步（原版实跑）也完成，而且是最强的一条证据：**
> **原版在 `target_selection` 相位里，光标初始就在「角色自己那一格」，**
> **A 键在非法格上按 ⇒ 原版弹出「请选择无效的场所」；**
> **方向键移动光标 + A ⇒ 原版同样进「可以嗎?」。**
> ⇒ ⭐ **重制侧与原版行为完全一致 ⇒ 产品侧无需改。**
>
> ⭐⭐ **第 3 步已判定：「CANNOT SELECT」与 wave 18 的「はい 被打回」是**两个不同的东西**。
> wave 18 那个是**栈溢出**（死在相位 20 的「はい」上）；栈溢出已修 ⇒ **现在相位 20 上的 A 完全正常**
> （实测相位 `20 → 9 facing_selection`，`ctrl_err=0 / pl_err=0`）。

---

## 1. 一句话结论

> ⭐⭐⭐ **「CANNOT SELECT」= 光标停在非法目标格（角色自己那一格 (11,6)）时按 A 的**干净拒绝**，
> 不是产品缺陷，也不是「A 键失效」。**
> 实测（`build/w22-d3/exp1-right-then-a/receipt.json`）：
> **按 1 次 Right ⇒ 光标 (11,6)→(12,6) ⇒ 按 A ⇒ 相位 `8 → 22 target_preview`（成功！）。**
> **对照（`exp3-control-a-only`）**：不按方向键直接按 A ⇒ 相位**停在 8**，
> `last_control_error=4 (player_flow_failed)` / `last_player_error=7 (action_rejected)`。
> ⇒ **C1 §8 的推断被实测证实**（机制正确），**但 C1 的结论「不是产品缺陷」也成立**。

---

## 2. 三步计划

| 步 | 做什么 | 状态 |
|---|---|---|
| ① | 带方向键的实跑（核心实验） | ✅ **完成**（exp1 / exp2 / exp3） |
| ② | 判定「产品缺陷 vs 按键方式」 | ✅ **完成**（不是产品缺陷） |
| ③ | 判定「与 wave 18 的『はい 被打回』是不是同一个」 | ✅ **完成**（两个不同缺陷） |
| ④ | 原版是否自动选目标（父代理四选一的第 4 项） | ✅ **完成**（原版**也不**自动选 ⇒ 两侧一致） |

---

## 3. ⭐⭐ 第 1 步实测数据（三次实跑）

### 3.1 仪器

| 项 | 值 |
|---|---|
| **探针** | `build/mgba-probe-w22d3/mgba-probe.exe`（**本流私建**，1,372,672 B，sha `215a2be6…`） |
| **ROM** | `build/s49-package-w20/work/pinned-rom/measured.gba`（sha **`b9a6724e93cd0aef893c6b1caaa3520fcd11cb6893a1838c574a756ff34f63cd`**） |
| **起点存档态** | `build/s49-package-w20/work/s49-report/capture-remake/step-29-A.ss9`（C2 的相位表：**`phase=8 target_selection`**，cursor=(11,6)，selected_unit=1） |
| **遥测地址** | EWRAM `0x0202A56C`（magic `0x4B42544C` 定位） |
| **驱动** | `tools/s49_w22d3/d3_target_select.py`（自写最小驱动器；`press` = 1 帧释放间隔 + N 帧按住 + 30 帧静置 + settle 轮询） |

### 3.2 ⭐⭐ exp2：带方向键的完整链（`build/w22-d3/exp2-full-chain/receipt.json`）

| # | 键 | 相位 | 相位名 | cursor | selected_unit | ctrl_err | pl_err | scene_frame |
|---:|---|---|---|---|---:|---:|---:|---:|
| 0 | （起点） | 8 | `target_selection` | (11,6) | 1 | 0 | 0 | 573 |
| 1 | **Right** | 8 | `target_selection` | **(12,6)** ⭐ | 1 | 0 | 0 | 607 |
| 2 | **A** | **22** | **`target_preview`** ⭐ | (12,6) | 1 | 0 | 0 | 632 |
| 3 | **A** | **20** | **`target_confirmation`**（「可以嗎?」） | (12,6) | 1 | 0 | 0 | 657 |
| 4 | **A** | **9** | **`facing_selection`** ⭐⭐ | (11,6) | 1 | 0 | 0 | 751 |
| 5 | A | 10 | `defense_decision` | (11,6) | 1 | 0 | 0 | 785 |
| 6 | A | 11 | `defense_selection` | (11,6) | 1 | 0 | 0 | 819 |
| 7 | A | 11 | `defense_selection` | (11,6) | 1 | **4** | **9** | 853 |

* ⭐ **第 1 行**：**方向键在 `target_selection` 相位里确实能移动光标**（(11,6) → (12,6)）
  ⇒ **「光标移动本身坏了」这个分支被排除**。
* ⭐ **第 2 行**：**移动后 A 立刻被接受**（相位 8 → 22 `target_preview`），**错误码全 0**。
* ⭐⭐ **第 4 行**：**相位 20（「可以嗎?」/「はい」）上的 A 现在完全正常** ⇒ 相位 `20 → 9 facing_selection`，
  `ctrl_err=0 / pl_err=0` ⇒ **wave 18 的栈溢出已修，「はい」这条路通了**。
* 第 7 行：`pl_err=9 (defense_rejected)` —— 这是**另一个**已知问题（U2/W2 记过：
  重制侧的防御条目全部 `unsupported_category`），**与本题无关**。

### 3.3 ⭐ exp3：对照组（不按方向键，直接按 A）

| # | 键 | 相位 | cursor | ctrl_err | pl_err |
|---:|---|---|---|---:|---:|
| 0 | （起点） | 8 `target_selection` | (11,6) | 0 | 0 |
| 1 | **A** | **8（不变）** | (11,6) | **4** | **7** |
| 2 | **A** | **8（不变）** | (11,6) | **4** | **7** |

⇒ ✅ **完全复现 C2 的现象**（`step-30..34`：`ctrl_err=4 / pl_err=7`，相位卡在 8，画面「CANNOT SELECT」）
⇒ **与 exp2 的唯一差别就是「有没有先按方向键」** ⇒ **因果链闭合**。

### 3.3.1 ⭐⭐ 画面对照（**最直观的一条**）

| | 画面 | 光标在哪 |
|---|---|---|
| **重制侧** `exp2-full-chain/00-baseline.png` | 目标选择画面（ Naruto 蓝帽 + 白角括号 + 红箭头 + 蓝色四向箭头 + 「SELECT 详细」） | ⭐ **在角色（鸣人）自己那一格** |
| **原版** `original-walk-states/04-A.png` | 目标选择画面（蓝帽角色 + 青色括号 + 红箭头 + 橙色范围 + 「SELECT 详细」） | ⭐ **同样在角色自己那一格** |

⇒ ⭐⭐⭐ **两侧进入目标选择时，光标都落在角色自己那一格** ⇒ **这根本不是重制侧特有的现象。**

### 3.4 ⭐ 错误码解码（**修正 C1 的一处措辞**）

| 遥测字段 | 值 | 枚举 | 出处 |
|---|---:|---|---|
| `last_control_error` | **4** | `battle_scene_control_error::player_flow_failed` | `battle_scene_controller.h:117-127`（枚举第 5 项，0 起） |
| `last_player_error` | **7** | `battle_player_action_flow_error::action_rejected` | `battle_player_action_flow.h` 的 `battle_player_action_flow_error`（枚举第 8 项，0 起） |

⚠️ **C1 写的是「`preview_target()` ⇒ 错误 `invalid_target`」**——
`invalid_target` 是 **`action_error`**（`battle_player_action_flow.h:930/1058/1105/1159` 里 `target_preview.error` 用的那个），
**不是** flow 层的错误码；flow 层报的是 `action_rejected`（`:1158`），
再由 `battle_scene_controller.h:882 _player_result(preview)` 映射成 `player_flow_failed`。
⇒ **C1 的机制链正确，措辞需修正（不影响结论）。**

---

## 4. ⭐ 代码定位（只读，未改任何产品文件）

### 4.1 「CANNOT SELECT」的完整链路（实测与代码逐环对上）

| # | 环节 | 出处 |
|---:|---|---|
| 1 | 战斗相位按 A ⇒ `result = controller.confirm();` | `game/src/battle_runtime_scene.cpp:9147-9159`（`:9147`） |
| 2 | `confirm()` 的 `target_selection` 分支 | `game/include/konoha/battle_scene_controller.h:875` |
| 3 | ⇒ `_runtime.preview_target(_cursor)` | `battle_scene_controller.h:879` |
| 4 | ⇒ `battle_player_action_flow::preview_target` | `battle_player_action_flow.h:1130` |
| 5 | ⇒ `battle_action_execution::preview(...)` | `battle_player_action_flow.h:1151` |
| 6 | ⇒ `! target_preview.legal()` ⇒ `action_rejected` | `battle_player_action_flow.h:1155-1161`（`:1158`） |
| 7 | ⇒ `_player_result(preview)` ⇒ `player_flow_failed` | `battle_scene_controller.h:882` → `_player_result()` |
| 8 | ⇒ 画面打出「CANNOT SELECT」 | `battle_runtime_scene.cpp:9202-9209`（`:9085`）⇒ `:4789` |

### 4.2 ⭐⭐ **光标为什么停在 (11,6)？** —— **产品内部两条入口不一致**

| 入口 | 进入 `target_selection` 时是否同步 `_cursor` | 出处 |
|---|---|---|
| **`direct_attack` 指令**（`_confirm_command`） | ✅ **同步**：`_cursor = _runtime.session().draft().preview_position;` | `battle_scene_controller.h:1973-1983`（**`:1980-1982`**） |
| **`action_selection` 选完招式**（`_sync_action_scene_phase`） | ⛔ **不同步**：只写 `_phase = target_selection;`，`_cursor` 保持原值 | `battle_scene_controller.h:1887-1888`（函数体 `:1874-1894`） |

⇒ **C2 那条 walk 走的是第二条路**（`command_selection(cmd=1 忍術) → action_selection → target_selection`）
⇒ `_cursor` 一直是**单位自己那一格 (11,6)** ⇒ `preview_target((11,6))` 必然不合法。

* 产品**内部**其实**已经算好了自动目标**：`battle_player_action_flow.h:923-931`
  进入 `target_selection` 时 `_state.target_position = session.draft().preview_position;`
  ⇒ **只是没把它同步给「场景的光标」**。

### 4.3 ⭐ 这仍然算不算「产品缺陷」？—— 分层结论

| 层 | 判定 |
|---|---|
| **「A 键在 `target_selection` 失效 / 光标动不了」** | ⛔ **不成立**（exp2 实测：光标能动，A 能用） |
| **「原版与重制侧行为一致吗」** | ✅ **一致**（§4.4 原版实跑：原版也要先移光标） |
| **「产品内部两条入口不一致」** | ✅ **是一处真实的不一致**（`battle_scene_controller.h:1980-1982` 同步 vs `:1887-1888` 不同步）—— 但**与原版行为无关**（原版也不自动选目标） |

---

## 4.4 ⭐⭐⭐ 第 4 步：**原版实跑**（决定性证据）

### 4.4.1 仪器

| 项 | 值 |
|---|---|
| **原版 ROM** | `D:\Shell\gba-naruto-butano\rom\base.gba`（sha **`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b**） |
| **探针** | `build/mgba-probe-w22d3/mgba-probe.exe`（同 §3.1） |
| **起点** | `build/s49-package-w20/work/s49-report/capture-original/step-24-A.ss9`（C2 相位表：**原版第 24 步 = `command_selection`**，指令菜单 移動/忍術/道具/直接放/休息/行動結束） |
| **走法** | `A` 按住 4 帧 + 90 帧静置（与 `tools/s49_rule_probe/capture_original.py` 的录制 walk 同节拍） |
| **原版无遥测** ⇒ 只记**截图 + sha256**，相位靠目视 |

### 4.4.2 ⭐ 原版 A-only walk（`build/w22-d3/original-walk-states/receipt.json`）

| 步 | 键 | 画面（目视） |
|---:|---|---|
| 0 | （起点） | **指令菜单**（移動/忍術/道具/直接放/休息/行動結束），光标在「移動」 |
| 1 | A | **移動格子**（蓝色可达格） |
| 2 | A | 文本框「本一 道具 行動結果」 |
| 3 | A | **忍術詳情画面**（飛燕手/影分身之术/苍蓝猛兽/十手里剑；目標数 1、距離 3、視圖 1、成功率 100 %） |
| 4 | A | ⭐ **目标选择画面**：橙色范围 + **光标（白角括号）落在角色自己那一格** |
| 5 | A | ⭐⭐ **弹窗「请选择无效的场所」**（字面如此；语义 = 「请选择一个**有效**的场所」） |
| 6 | A | 回到目标选择画面 |
| 7 | A | 弹窗「请选择无效的场所」 |
| 8 / 9 / 10 | A | 目标选择画面 / 弹窗 / 目标选择画面（**A-only 永远出不去**） |

⇒ ⭐⭐⭐ **原版的 A-only walk 在目标选择上同样出不去** ——
**与重制侧「CANNOT SELECT」完全同形。**

### 4.4.3 ⭐⭐ 原版加方向键（`build/w22-d3/original-arrow-test/receipt.json`）

起点 = 上面第 4 步的目标选择画面（`build/w22-d3/original-walk-states/04-A.ss9`）。

| 步 | 键 | 画面 |
|---:|---|---|
| 0 | （起点） | 目标选择画面，光标在角色自己那一格 |
| 1 | **Right** | 光标右移 |
| 2 | **Right** | 光标再右移 |
| 3 | **Down** | ⭐ **光标移到右下格**（白角括号在右侧壶的格子上） |
| 4 | **A** | ⭐⭐⭐ **「可以嗎?」对话框（是 / 否）** ⇒ **目标被接受！** |

⇒ ⭐⭐⭐ **原版也需要方向键** ⇒ **原版「不自动选目标」** ⇒
**父代理四选一的第 4 项（「原版自动选目标 ⇒ 产品与原版不一致」）被排除。**

### 4.4.4 ⭐ 弹窗是 **A 触发**的，不是定时提示（`build/w22-d3/original-idle-test/`）

在原版的目标选择画面上**完全不按任何键**，连拍 6 张（间隔 90 帧，共 **540 帧**）：

| 帧 | 与「无弹窗」参考帧的区域平均差 | 与「有弹窗」参考帧的区域平均差 | 判定 |
|---:|---:|---:|---|
| 04-A（无弹窗）与 05-A（有弹窗）互比 | — | **72.79** | 判别尺度 |
| idle-01 | **5.90** | 73.54 | 无弹窗 |
| idle-02 | **2.22** | 73.48 | 无弹窗 |
| idle-03 | **8.19** | 73.23 | 无弹窗 |
| idle-04 | **2.44** | 72.59 | 无弹窗 |
| idle-05 | **3.02** | 72.38 | 无弹窗 |
| idle-06 | **8.51** | 73.07 | 无弹窗 |

（区域 = 弹窗框所在处 (55,55)-(175,100)）

⇒ ⭐ **弹窗是「按 A 打在非法格上」的反馈**，与重制侧的「CANNOT SELECT」横幅**语义完全对应**。

### 4.4.5 ⭐⭐ **两侧行为对照表（最终判据）**

| 环节 | **原版**（实跑） | **重制侧**（实跑） | 一致？ |
|---|---|---|---|
| 进入 `target_selection` 时**光标在哪** | **角色自己那一格**（白角括号在角色脚下） | **角色自己那一格 (11,6)**（遥测 + 截图） | ✅ **一致** |
| 在非法格上按 A | 弹窗**「请选择无效的场所」** | 横幅**「CANNOT SELECT」**，`ctrl_err=4 / pl_err=7` | ✅ **一致（呈现不同，语义相同）** |
| 方向键能否移动光标 | ✅ 能（Right,Right,Down ⇒ 光标移动） | ✅ 能（Right ⇒ (11,6)→(12,6)） | ✅ **一致** |
| 移到合法目标后按 A | ✅ 进**「可以嗎?」** | ✅ 进相位 **22 `target_preview`** → A → 相位 **20「可以嗎?」** | ✅ **一致**（重制侧多一个 `target_preview` 拍） |
| 「可以嗎?」对话框画面 | 「可以嗎?／是／否」，光标 ▷ 在「是」 | **逐像素同形**（`build/w22-d3/remake-03-A-zoom3x.png` vs `original-arrow-test/04-A-zoom3x.png`） | ✅ **一致** |

⇒ ⭐⭐⭐ **判决：重制侧与原版在目标选择这件事上行为一致 ⇒ 「CANNOT SELECT」不是产品缺陷。**

### 4.4.6 ⭐ **给父代理的一条重要澄清：「真实链走到攻击」没有被卡住**

闭环驱动器 `tools/s49_battle_balance/v1_battle.py` 的 `do_target()`（`:799-849`）
**本来就是「先 `place_cursor(cell)` 移光标、再按 A」**（`:819` → `:821`）
⇒ 它**不会**触发「CANNOT SELECT」。
**已有收据佐证**（`build/u1/run-a-tools/battle.json` / `build/u1/run-b-punch/battle.json` 的 `decisions`）：

```json
{"do": "target-accepted", "frame": 542,  "enemy": 7, "cell": [6,6], "phase": 22}
{"do": "target-accepted", "frame": 2233, "enemy": 7, "cell": [8,7], "phase": 22}
```

⇒ ⭐ **「CANNOT SELECT」只卡住那条**盲走的 `A×32` walk**，**不卡闭环真实链**。
⇒ C2 §7 第 2 条（「重制侧这条 walk 走不到攻击 ⇒ 需要父代理决定」）**可以结案：不是产品缺陷，是 walk 的按键方式**。

---

## 5. ⭐⭐ 第 3 步：与 wave 18「はい 被打回」是不是同一个？

> ⭐ **判定：不是同一个。是两个独立的东西。**

| 判据 | wave 18 的「はい」 | 本次的「CANNOT SELECT」 |
|---|---|---|
| **出问题的相位** | **20 `target_confirmation`**（「可以嗎?」） | **8 `target_selection`** |
| **按 A 之后的相位** | **冻结**（`scene_frame` 638 不再推进） | **相位不变，仍是 8**（`scene_frame` 606→639 **在推进**） |
| **错误码** | `ctrl/player/act_err` **全 0**（处理 A 的帧没跑完 ⇒ 无处记录） | `ctrl_err=4 / pl_err=7`（**干净拒绝**） |
| **机制** | **栈溢出**：`sp=0x03002818`（低于栈底 940 B）⇒ 踩坏 `IRQ_VectorTable[0]` ⇒ 跳进野地址 | **合法判据**：预览不合法 ⇒ `action_rejected` |
| **现状** | ✅ **已修**（栈溢出修了）⇒ **实测相位 20 的 A 现在正常**（`20 → 9 facing_selection`，err 全 0） | ⛔ **仍在**（因为那条 walk 不按方向键） |

⇒ **代码行号级的区分（两个不同的入口）**：

* wave 18 的「はい」= `battle_scene_controller.h:897-905`
  （`case target_confirmation:` → `:905 return _confirm_target();`）
  ⇒ 走的是 **`_confirm_target()`**（`:2009`）→ 栈溢出。
* 本次的「CANNOT SELECT」= `battle_scene_controller.h:875-890`
  （`case target_selection:` → `:879 _runtime.preview_target(_cursor)` → `:882 _player_result(preview)`）
  ⇒ 走的是 **`preview_target()`**，**根本没进 `_confirm_target()`**。

⇒ **一句话判定：同一个「选择确认」机制（`battle_scene_controller::confirm()`）的两个不同 `case` 分支，
但**症状机理完全不同**、**修好了其中一个另一个仍在** ⇒ **两个独立缺陷**。**

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **D3-H1** | ⭐⭐ **在 `target_selection` 相位里方向键能移动光标** | exp1/exp2：按 Right 后读遥测 `cursor_x/cursor_y` | ✅ **成立**：(11,6) → **(12,6)** | **已确认** |
| **D3-H2** | ⭐⭐ **光标移到合法目标后，A 生效** | exp2：Right 后按 A，读相位 | ✅ **成立**：相位 **8 → 22 `target_preview`**，错误码全 0 | **已确认** |
| **D3-H3** | ⭐⭐ **不按方向键直接按 A ⇒ 「CANNOT SELECT」**（对照） | exp3：只按 A，读相位/错误码 | ✅ **成立**：相位卡 8，`ctrl_err=4 / pl_err=7`（= C2 的 `step-30..34`） | **已确认** |
| **D3-H4** | ⭐⭐ **「CANNOT SELECT」是产品缺陷** | exp1–exp3 三次实跑 | ⛔ **不成立**：A 与光标都正常 ⇒ **是 walk 的按键方式问题** | **已证伪** |
| **D3-H5** | ⭐⭐ **wave 18 的「はい」已修好**（栈溢出已消失） | exp2 第 4 行：相位 20 上按 A | ✅ **成立**：相位 `20 → 9 facing_selection`，`ctrl_err=0 / pl_err=0`（wave 18 是冻结 + 栈溢出） | **已确认** |
| **D3-H6** | ⭐⭐ **「CANNOT SELECT」与 wave 18 的「はい」是同一个缺陷** | 对比相位/错误码/代码分支 | ⛔ **不成立**：一个在相位 8（干净拒绝），一个在相位 20（栈溢出）；**两个不同的 `case` 分支** | **已证伪** |
| **D3-H7** | ⭐ 光标停在 (11,6) 是因为 **`_sync_action_scene_phase()` 没同步 `_cursor`** | 读 `battle_scene_controller.h:1874-1894` vs `:1973-1983` | ✅ **成立**：`:1887-1888` 只写 `_phase`；`:1980-1982` 才同步 `_cursor` | **已确认** |
| **D3-H8** | ⭐⭐ **原版在 `target_selection` 自动选目标**（父代理四选一的第 4 项） | 原版 ROM 实跑（§4.4）：A-only walk + 方向键 walk + 无输入对照 | ⛔ **不成立**：**原版光标初始也在角色自己那一格**，A-only 同样出不去（弹窗「请选择无效的场所」）；方向键 + A ⇒ 进「可以嗎?」⇒ **两侧行为一致** | **已证伪** |
| **D3-H9** | ⭐ **原版的「请选择无效的场所」弹窗是 A 触发的**（不是定时提示） | 原版目标选择画面上**完全不按键**连拍 6 帧（540 帧），把弹窗区与「有/无弹窗」参考帧比 | ✅ **成立**：6 帧全部贴近「无弹窗」（2.22–8.51）而远离「有弹窗」（72.4–73.5）⇒ 弹窗由按 A 触发 | **已确认** |
| **D3-H10** | ⭐⭐ **闭环真实链没有被「CANNOT SELECT」卡住** | 读闭环驱动器的收据 `decisions` | ✅ **成立**：`v1_battle.py:819-821` 本来就是「先移光标再按 A」；收据里 `{"do":"target-accepted","cell":[6,6],"phase":22}` | **已确认** |

---

## 7. 结论汇总（给父代理的四选一）

> ### ⭐ **四选一的判定：第 1 行 ——「加了方向键后 A 生效」⇒ 不是产品缺陷 ⇒ 产品侧无需改。**

| 父代理给的四选一 | 本流实测 | 判定 |
|---|---|---|
| ① 加了方向键后 **A 生效** | ✅ **成立**（重制侧：相位 8→22→20→9；原版：进「可以嗎?」） | ⭐⭐⭐ **就是这个** ⇒ **不是产品缺陷** |
| ② 加了方向键后 A 仍无效 | ⛔ 不成立 | 排除 |
| ③ 加了方向键后光标根本不动 | ⛔ 不成立（(11,6)→(12,6)；原版光标也动） | 排除 |
| ④ 原版自动选目标 ⇒ 产品与原版不一致 | ⛔ 不成立（**原版也不自动选**，也要方向键） | 排除 |

### 7.1 ⭐ 与 wave 18「はい 被打回」是不是同一个

> **不是同一个。是同一个 `confirm()` 机制的两个不同 `case` 分支，机理不同、状态不同。**

| | wave 18 的「はい」 | 本次的「CANNOT SELECT」 |
|---|---|---|
| 相位 | **20** `target_confirmation` | **8** `target_selection` |
| 代码分支 | `battle_scene_controller.h:897-905` → `:905 _confirm_target()`（`:2009`） | `battle_scene_controller.h:875-890` → `:879 preview_target(_cursor)` → `:882 _player_result()` |
| 机理 | **栈溢出**（`sp=0x03002818`，低于栈底 940 B） | **合法判据**（预览不合法 ⇒ `action_rejected`） |
| 错误码 | 全 0（那帧没跑完） | `ctrl_err=4 / pl_err=7` |
| 现状 | ✅ **已修**（实测相位 20 的 A → `9 facing_selection`） | ⛔ **仍在**（但**与原版一致**，不是缺陷） |

⇒ **一句话判定：同一个「选择确认」机制（`battle_scene_controller::confirm()`）的两个入口，
症状机理完全不同、修好了其中一个另一个仍在 ⇒ 两个独立的现象。**

---

## 8. 未完成项 / 接线请求

| # | 项 | 状态 |
|---|---|---|
| N-D3-1 | ⭐ **原版是否自动选目标**（D3-H8） | ✅ **已完成：不自动选**（§4.4） |
| N-D3-2 | 「CANNOT SELECT」与 wave 18 是不是同一个 | ✅ **已判定：不是**（§5、§7.1） |
| N-D3-3 | 产品缺陷 vs 按键方式 | ✅ **已判定：按键方式（不是缺陷）**（§4.3、§7） |
| N-D3-4 | ⭐⭐ **「真实链走到攻击」是否被卡住** | ✅ **没有被卡住**（闭环驱动器本来就先移光标；收据 `target-accepted` 佐证，§4.4.6） |

### 8.1 ⭐ 接线请求（**本流不改任何产品文件**，只给父代理转交）

| # | 收件人 | 内容 | 理由 |
|---|---|---|---|
| **R-D3-1** | **C2**（`W21-C2-press-divergence.md` §7 第 2 条） | 把「重制侧 `target_selection` 卡死（6 次 A 无效）⇒ 需父代理决定 (a) 产品缺陷 / (b) 按键方式」**结案为 (b) 按键方式**；并把「重制侧这条 walk 走不到攻击」改为「**只盲走的 `A×32` walk 走不到；闭环真实链不受影响**」 | §4.4.6：`v1_battle.py:819-821` 本来就 `place_cursor` + A；收据 `target-accepted` 佐证 |
| **R-D3-2** | **C1**（`W21-C1-camera-pan.md` §8） | 把 §8 的「⚠️ 本条是代码路径追踪 + 遥测读数的**推断**，**没有做「带方向键的实跑」验证**」**升级为已验证**；并修正错误码措辞：`invalid_target` 是 `action_error`，flow 层实际报 `action_rejected`（`battle_player_action_flow.h:1158`），再映射为 `player_flow_failed`（`battle_scene_controller.h:882`） | §3.2–§3.4 |
| **R-D3-3** | **父代理 / C4** | ⭐ **重制侧比原版多一个 `target_preview` 相位（22）**：原版 `目标选择 → A → 「可以嗎?」`（1 次 A）；重制侧 `目标选择 → A → 22 → A → 20「可以嗎?」`（2 次 A）。⇒ **这是 C2 的按键数差异的一个真实来源**（C2 §3.1 的偏移剖面里「重制侧少消耗」那一段需要再核） | §4.4.5 第 4 行 |
| **R-D3-4** | **父代理** | ⭐ **无需产品改动**。若父代理仍想消除产品内部的不一致（`_sync_action_scene_phase()` 不同步 `_cursor` vs `direct_attack` 路径同步），**建议不要改**：原版也不自动选目标，改了反而偏离原版（会把光标放到自动目标上 = 原版没有的行为） | §4.4.5 + §4.2 的对照 |

---

## 9. 仪器与收据

### 9.1 工具（`tools/s49_w22d3/`，**不改任何产品文件**）

| 工具 | 作用 |
|---|---|
| `d3_target_select.py` | 重制侧最小驱动器：载入存档态 → 读遥测 → 逐键按下 → 每步记遥测 + 截图 + sha256 → 写 `receipt.json` |
| `d3_original_walk.py` | 原版驱动器：同结构但**不读遥测**（原版无遥测），另支持 `--idle N`（不按键连拍 N 张）与每步存 `.ss9` |
| `check_receipts.py` | 校验 7 份收据都能解析、且 ROM / 起点存档态正确 |

### 9.2 收据（`build/w22-d3/`）

| 目录 | 内容 |
|---|---|
| **`exp1-right-then-a/`** | ⭐ **核心实验**：Right → A ⇒ 相位 8 → 22 |
| **`exp2-full-chain/`** | ⭐ **完整链**：Right,A,A,A,A,A,A ⇒ 8 → 22 → 20 → **9 `facing_selection`** → 10 → 11 |
| **`exp3-control-a-only/`** | ⭐ **对照组**：A,A ⇒ 相位卡 8，`ctrl_err=4 / pl_err=7` |
| **`original-walk/`** | 原版 A-only walk（10 步）的截图（无状态） |
| **`original-walk-states/`** | 同上 + 每步 `.ss9` 状态（第 4 步 = 原版目标选择画面） |
| **`original-arrow-test/`** | ⭐ 原版方向键 + A ⇒ 「可以嗎?」 |
| **`original-idle-test/`** | ⭐ 原版目标选择画面无输入 540 帧 ⇒ 弹窗不出现（A 触发） |
| `remake-*.png` / `original-*.png` | 4×/3×/8× 放大的对照截图 |

### 9.3 复现命令

```powershell
# ① 重制侧：带方向键的实跑（核心实验）
python tools/s49_w22d3/d3_target_select.py `
  --rom   build/s49-package-w20/work/pinned-rom/measured.gba `
  --exe   build/mgba-probe-w22d3/mgba-probe.exe `
  --state build/s49-package-w20/work/s49-report/capture-remake/step-29-A.ss9 `
  --out   build/w22-d3/exp2-full-chain --keys Right,A,A,A,A,A,A

# ② 重制侧：对照组（只按 A）
python tools/s49_w22d3/d3_target_select.py ... --out build/w22-d3/exp3-control-a-only --keys A,A

# ③ 原版：A-only walk（每步存状态）
python tools/s49_w22d3/d3_original_walk.py `
  --rom   'D:\Shell\Github\gba-naruto-butano\rom\base.gba' `
  --exe   build/mgba-probe-w22d3/mgba-probe.exe `
  --state build/s49-package-w20/work/s49-report/capture-original/step-24-A.ss9 `
  --out   build/w22-d3/original-walk-states --keys A,A,A,A,A,A,A,A,A,A

# ④ 原版：方向键 + A（⇒「可以嗎?」）
python tools/s49_w22d3/d3_original_walk.py ... `
  --state build/w22-d3/original-walk-states/04-A.ss9 `
  --out   build/w22-d3/original-arrow-test --keys Right,Right,Down,A,A,A,A --settle 40

# ⑤ 原版：无输入 540 帧（证明弹窗是 A 触发）
python tools/s49_w22d3/d3_original_walk.py ... `
  --state build/w22-d3/original-walk-states/04-A.ss9 `
  --out   build/w22-d3/original-idle-test --keys "," --idle 6 --settle 90
```

### 9.4 ⚠️ 踩坑记录（给下一棒）

* **`capture_lock.py --run` 会把带逗号的参数（`--keys ,`）搞坏** ⇒ 探针 `stdin.write` 报
  `OSError: [Errno 22] Invalid argument`（看起来像探针崩了，其实是参数被吞/改）。
  ⇒ **带逗号的参数不要过锁**，或者改用不带逗号的写法（本流第 ⑤ 步就是这样绕过锁直接跑的）。
* **原版没有遥测** ⇒ 相位只能靠目视截图；`read` 工具可以直接看 PNG，放大后再看就够清楚。
* **原版 ROM** 在 `D:\Shell\gba-naruto-butano\rom\base.gba`（不是逆向线根目录那个文件名的 gba）。
