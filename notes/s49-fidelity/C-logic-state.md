# Stream C — S49 逻辑状态对齐

**日期**：2026-10-23
**口径**：「完全一致」＝玩家看得见的画面 ＋ **游戏逻辑状态**（寄存器不算）。
本 stream 只管后半条：把逻辑状态从「没测过」变成「逐项有红绿」。

**一句话结论**：**逻辑状态这一半现在有 60 条可判定的项：绿 51 / 红 5 / 灰 4。**
七个检查里三个全绿（等价性、朝向、0xFBFF），两个有红（待机帧序、移动网格染色），
两个有灰（名册里重制侧运行时单位池、状态栏重制侧红 結束 帧）。
**名册这条最要紧的已经闭合了**：battle 14 的九名单位在原版 EWRAM 里重新 dump 出来的
字节与 macOS 的捕获**逐字节相同**，重制侧九槽的角色／阵营／坐标／等级／当前与最大 HP／
携带经验**逐项无差异**。

---

## 1. 做了什么

重制线有五个针对这场战斗的规则测量器
（`D:\Shell\Github\gba-naruto-butano\tools\butano\measure_s49_rule_*.py`）
和名册门禁 `s49-battle-14-roster`。它们在 macOS 上写的，路径假设是
`/Users/altair/github/gba-naruto/...`，在本机跑不动 —— 更根本的是：
**2026-10-19 的清理把原版 25 帧 PNG 带走了，只剩 JSON 收据**。

本 stream 的工作就是让这些规则**在本机重新变得可判定**：

1. **重录证据**：用无头 mGBA 探针（`build/mgba-probe/mgba-probe.exe`）＋ 重制线自己的
   Lua 探针脚本，按 macOS 收据里钉死的配方重新录下原版与重制侧。
2. **证明重录 == macOS 那份**：四个独立基准（EWRAM 单位池逐字节、录制配方哈希、
   幸存的原版像素、门禁钉住的规则数值）。
3. **把五个测量器移植到本机**：不按帧序号定位画面，改为**按测量定位**。
4. **名册逐项比对**：原版内存 ↔ 重制侧数据表 ↔ 逆向侧两份独立记录。

---

## 2. 改了哪些文件

### 2.1 新增（独占目录，本 stream 独占）

| 路径 | 说明 |
|---|---|
| `tools/s49_logic_checks/README.md` | 怎么跑、退出码、产物、与重制线五个测量器的关系 |
| `tools/s49_logic_checks/s49_logic_common.py` | 共用路径、区域表、覆盖层统计、状态字分类、判定框架 |
| `tools/s49_logic_checks/record_evidence.py` | 八段录制的驱动器 |
| `tools/s49_logic_checks/check_original_equivalence.py` | 本机重录 == macOS 那份？ |
| `tools/s49_logic_checks/check_battle_roster.py` | battle 14 名册逐槽逐字段 |
| `tools/s49_logic_checks/check_rule_standby_state.py` | 結束 / 待機 切换时机 |
| `tools/s49_logic_checks/check_rule_ai_facing.py` | AI 移动后的朝向 |
| `tools/s49_logic_checks/check_rule_move_grid.py` | 移动网格染色规则 |
| `tools/s49_logic_checks/check_rule_idle_sequence.py` | 待机帧序与相位 |
| `tools/s49_logic_checks/check_rule_fbff.py` | 0xFBFF 缺陷语义 |
| `tools/s49_logic_checks/run_all.py` | 一条命令出红绿表 |

临时产物（录制、收据、接触印像表、诊断脚本）：`build/s49-logic/`

* `build/s49-logic/receipts/*.json` —— **收据**（交付物的证据）
* `build/s49-logic/{original-walk,original-walk-long,remake-walk,original-idle-sweep,roster-pool,field-frame,field-frame-step23,palette-probe}/` —— **录制**
* `build/s49-logic/*.py`、`build/s49-logic/sheet-*.png` —— **排查用的草稿**（不是交付物；
  草稿脚本是一次性诊断，可以直接删掉，不影响任何一条结论）
* `build/s49-logic/{field-frame-check,palette-probe-bios}/` —— 早期手工实验的残留目录
  （其中 `palette-probe-bios` 是「换真实 BIOS 重测节奏」那次实验的产物），
  **不是** `record_evidence.py` 产出的录制，可以直接删掉。

### 2.2 **没有**改的东西

* **重制线里的任何文件**（`D:\Shell\Github\gba-naruto-butano\**`）：一个字节都没动。
  那五个测量器是**只读参照**。
* 逆向线（`D:\Shell\Github\gba-naruto-reverse\**`）：只读。
* master 仓的其他文件：只新增了本目录与 `notes/s49-fidelity/C-logic-state.md`。

### 2.3 移植时相对原版测量器改了什么（以及为什么）

| # | 原版测量器 | 本目录的移植 | 为什么 |
|---|---|---|---|
| 1 | `measure_s49_rule_move_grid.py` 用 `PINNED_ORIGINAL_HASHES` 钉 **PNG 文件字节** | 不钉文件字节；改钉**解码后的像素**，并把原版的数值当作「macOS 侧参考值」记进收据 | macOS mGBA 与本机探针的 PNG 编码器不同，**同一张画面文件字节不同**（本机 25 帧全部与 macOS 哈希不同）。规则是关于画面的，钉像素才对 |
| 2 | `measure_s49_rule_idle_sequence.py` 用 `PINNED_FIRST_FRAME_SHA256` 钉**第一帧的 PNG 文件字节** | 同上：改成像素；原版侧的数值改从重制线**门禁里记录的 macOS 参考值**取 | 同上 |
| 3 | 五个测量器按**帧序号**定位画面（`step-18-A.png` / `step-19-A.png` / `step-20-A.png`） | 全部改成**按测量定位**：朝向用「暗色化单位最左列的**众数**」；移动范围用「**连成一片**的青色覆盖格最多的相邻帧对，且该帧没有对话框」 | 本机与 macOS 的 mGBA 走 UI 的节奏不同，**同样 24 次 A 落在不同画面上**（本机第 17 步还在对话，macOS 已经在战场）。按序号配对＝按项目自己的教训「把名字差异误读成渲染差异」 |
| 4 | 从 macOS 的 `region-diff-banner2/*.json` 收据里读「声明的帧对」 | 两侧各用自己的录制，帧对由各自走位内部定位 | 那些收据里的帧对指向 macOS 的帧，在本机不存在 |
| 5 | `measure_s49_rule_fbff.py` 的 `DEFAULT_REVERSE_ROOT = "/Users/altair/github/gba-naruto-reverse"` | 改成本机路径 `D:\Shell\Github\gba-naruto-reverse`（**原文件没动**） | macOS 路径在本机不存在；逆向线在本机**是有的**，所以运行时越界轨迹这条也能判 |
| 6 | `verify_s49_battle_roster.py` 会重新哈希捕获的输入，包括 macOS 的 mGBA 二进制 | 改成：**在本机重新 dump 一份单位池**，与 macOS 捕获逐字节比；再与逆向侧两份独立记录交叉核对 | macOS 的 mGBA 二进制在本机不存在，原版验证器会 fail-closed 退出 |
| 7 | 测量器只打印 JSON，判定交给 unittest 门禁 | 每个检查自己输出**逐条**「通过 / 未通过 / 无法判定」，并把判定依据、原版值、重制值、差异写进收据 | 本机没有 pytest；而且要的是「逐项有红绿」，不是「一堆 JSON」 |

---

## 3. 跑了什么验收

### 3.1 录证据

```powershell
cd D:\Github\gba-naruto
$env:PYTHONIOENCODING='utf-8'
python tools\s49_logic_checks\record_evidence.py
```

| 录制 | 脚本 | 结果 |
|---|---|---|
| `original-walk` | `mgba_original_s49_ui_boundaries.lua` | 25 帧（battle 14 入口存档起，zero=90 settle=90 hold=4，A×24） |
| `original-walk-long` | 同上 | 41 帧（A×40，用来够到移动范围画面） |
| `remake-walk` | `mgba_boot_input_sequence.lua` | 63 帧（上电起，真实 BIOS，zero=900，Down,Down,A×60） |
| `original-idle-sweep` | `mgba_original_input_frame_sequence.lua` | 200 帧零输入扫描 |
| `roster-pool` | `mgba_battle_roster_dump.lua` | 6084 字节 EWRAM 单位池 |
| `field-frame` / `field-frame-step23` | `mgba_frame_palette_sequence.lua` | 6 / 32 帧画面 + PRAM/VRAM/OAM/IO |
| `palette-probe` | `mgba_frame_palette_sequence.lua` | 12 帧 + 调色板转储 |

### 3.2 出红绿表

```powershell
python tools\s49_logic_checks\run_all.py
```

结果：**共 60 条：绿 51 / 红 5 / 灰 4，退出码 1**（有红）。

收据（sha256 前 16 位）：

| 收据 | sha256 | 判定 |
|---|---|---|
| `equivalence-original-recording.json` | `a2268a3f442da7ed` | 通过 |
| `battle-14-roster.json` | `5344ff383f0a2947` | 无法判定（1 条灰） |
| `rule-standby-state.json` | `816c6877494491c2` | 无法判定（3 条灰） |
| `rule-ai-facing.json` | `b51898e79bf56e0f` | 通过 |
| `rule-move-grid.json` | `bffbb531183ae433` | 未通过（2 条红） |
| `rule-idle-sequence.json` | `2552f04de50387a5` | 未通过（3 条红） |
| `rule-fbff.json` | `fd08ade40114a5f6` | 通过 |

---

## 4. 逐项结论表

### 4.1 本机重录 == macOS 那份？（5 条，全绿）

| # | 项 | 原版 | 本机 | 差异 | 判定 |
|---|---|---|---|---|---|
| 1 | `roster-pool-bytes` | sha256 `9d508d99…`（6084 B） | sha256 `9d508d99…`（6084 B） | **0 字节** | 🟢 |
| 2 | `recording-recipe` | 存档 `a3628723…` / ROM `1198ece7…` / 脚本 `e14f7979…` | 同上 | 三个哈希全同 | 🟢 |
| 3 | `recording-parameters` | zero=90 settle=90 hold=4，A×24 | 同上 | 一致 | 🟢 |
| 4 | `surviving-original-pixels` | macOS 遗留的单位选择画面 | 本机 step-23 序列里最接近的一帧 | 整帧差 **273 px**，其中战场区 273 px、**状态栏 0 px** | 🟢 |
| 5 | `rule-values-reproduced` | 結束 107 px / 待機 150 px（门禁钉的值） | 結束 {51, **107**} / 待機 {104, **150**} | 逐值相同 | 🟢 |

> 注（不是判定项）：本机 25 帧的 **PNG 文件字节**与 macOS 的 `image_sha256`
> 25 帧全部不同 —— 两端 PNG 编码器不同，文件字节不可比；画面是否相同由第 4 条（像素）判定。
> 残差 273 px 全部落在单位自己的画面上：原版每帧重画描边调色板，macOS 留下的六帧彼此也差 134..756 px，就在同一区域。

### 4.2 battle 14 名册（15 条：14 🟢 / 1 ⚪）—— **重点确认项**

原版侧：从 battle 14 入口存档**重新 dump** 的 EWRAM 单位池，与 macOS 捕获逐字节相同。
重制侧：`sequel/content/positions/bank.json`（编队表）＋`units/bank.json`（基础 HP）＋
`character-stats/bank.json`（成长表），按原版成长公式 `max_hp = base + growth*(level-1)/100` 算。

| 槽 | 单位 | 阵营 | 坐标 | 等级 | 当前/最大 HP | 携带 EXP | 差异 |
|---|---|---|---|---|---|---|---|
| 1 | 鸣人 (1) | 我方 | (11,6) | 5 | 138/138 | 0 | 无 |
| 2 | 佐助 (2) | 我方 | (10,14) | 4 | 104/104 | 0 | 无 |
| 3 | 小樱 (3) | 我方 | (8,14) | 5 | 110/110 | 0 | 无 |
| 4 | 木叶丸 (30) | 我方 | (8,7) | 3 | 40/40 | 0 | 无 |
| 5 | 蜜蜂 (55) | 敌方 | (3,4) | 5 | 25/25 | 50 | 无 |
| 6 | 蜜蜂 (55) | 敌方 | (4,8) | 5 | 25/25 | 50 | 无 |
| 7 | 蜜蜂 (55) | 敌方 | (3,11) | 5 | 25/25 | 50 | 无 |
| 8 | 蜜蜂 (55) | 敌方 | (6,6) | 5 | 25/25 | 50 | 无 |
| 9 | 蜜蜂 (55) | 敌方 | (5,13) | 5 | 25/25 | 50 | 无 |

| # | 项 | 判定 |
|---|---|---|
| 1 | `original-pool-capture`（本机重 dump == macOS 捕获，0 字节差） | 🟢 |
| 2 | `unit-count`（9 vs 9） | 🟢 |
| 3 | `party-level-source`（队友等级 5/4/5 来自 `battle_campaign_route.h`，不是注释） | 🟢 |
| 4–12 | `slot-1` … `slot-9`（逐槽逐字段） | 🟢 ×9 |
| 13 | `reverse-note-cross-check`（逆向侧自然流程记录 vs 原版内存，逐槽一致） | 🟢 |
| 14 | `reverse-bindings-cross-check`（逆向侧签名的单位绑定 + 单位池哈希，一致） | 🟢 |
| 15 | `remake-runtime-pool` | ⚪ **无法判定** |

**⚪ `remake-runtime-pool` 缺什么**：重制侧运行时的单位结构体在 EWRAM 里的地址与字段偏移。
上面的比对是**数据表**层面（编队表 + 属性表），也就是重制侧生成战斗的输入；
重制侧**运行中的**那份单位数组没有 dump，所以「运行时实际值」这条判不了。
不猜。

### 4.3 状态栏 結束 / 待機 切换时机（10 条：7 🟢 / 3 ⚪）

| # | 项 | 原版 | 重制 | 判定 |
|---|---|---|---|---|
| 1 | `原版-two-inks` | 红 8 帧 / 蓝 20 帧 | — | 🟢 |
| 2 | `原版-ink-values` | 結束 **107** px / 待機 **150** px（macOS 钉值） | 实测同值 | 🟢 |
| 3 | `原版-word-columns` | 列 104..118 | 同上 | 🟢 |
| 4 | `原版-follows-unit` | 状态字列固定；排除状态字列后，单位名区域在红帧与蓝帧之间差 **291 px** ⇒ 状态字跟着**显示出来的那个单位**走 | — | 🟢 |
| 5 | `重制-two-inks` | 红 結束 / 蓝 待機 | 蓝 45 帧，**红 0 帧** | ⚪ |
| 6 | `重制-ink-values` | 107 / 150 | 待機 **150** ✓、結束 **0**（没录到） | ⚪ |
| 7 | `重制-word-columns` | 104..118 | **104..118**（同一位置） | 🟢 |
| 8 | `重制-follows-unit` | 同上判据 | — | ⚪ |
| 9 | `remake-source-criterion` | 判据＝单位是否已行动 | `render_status_panel_text` 里按 `unit->completed` 判，**没有**按 `battle_scene_phase::unit_selection` 判 | 🟢 |

**⚪ 三条灰缺什么**：重制侧的录像**没有走到敌方回合**（目标选择卡在 `CANNOT SELECT`，
A 键在目标光标上被吃掉），所以录不到**红 結束**那一帧 ⇒ 像素上判不了「红/蓝成对出现」。
重制侧的源码判据（第 9 条）已经是绿的。

### 4.4 AI 移动后的朝向（9 条，全绿）

| # | 项 | 原版 | 重制 | 判定 |
|---|---|---|---|---|
| 1 | `原版-locate` | 众数列 **80**（macOS 钉值） | 同 | 🟢 |
| 2 | `重制-locate` | 80 | **80** | 🟢 |
| 3 | `original-cell` | 场景列 **10**（macOS 钉值） | 由列 80 与相机 (240,24) 算出 **10** | 🟢 |
| 4 | `original-walked-east` | 从部署列 8 走了 **2 格向东**，朝向 east | 同 | 🟢 |
| 5 | `focus-would-differ` | 面向焦点 ⇒ north ≠ east ⇒ 朝向可判定 | 同 | 🟢 |
| 6 | `original-art-is-asymmetric` | 非双侧对称 | 翻转前后差 6204 px | 🟢 |
| 7 | `remake-orientation` | 直接差 **1174** px / 镜像差 **6203** px | 1174 < 6203/2 ⇒ 朝向一致 | 🟢 |
| 8 | `remake-orientation-residual` | < 2000 px（macOS 钉值） | 1174 px ⇒ 在动画相位差范围内 | 🟢 |
| 9 | `remake-source-criterion` | 朝向＝移动方向 | `facing_toward` 在 `battle_ai.h` / `battle_map_movement.h` 等 | 🟢 |

### 4.5 移动网格的染色规则（8 条：6 🟢 / 2 🔴）

| # | 项 | 原版 | 重制 | 判定 |
|---|---|---|---|---|
| 1 | `原版-locate` | macOS 是 step-19→20 | 本机 **step-25→26**，覆盖格 145、最大连通块 144 | 🟢 |
| 2 | `重制-locate` | — | 本机 **step-20→21**，覆盖格 135、最大连通块 55 | 🟢 |
| 3 | `original-is-dither-mask` | **19** 个底色各对应多于一种覆盖色（macOS 钉值） | 本机 **37** 个 | 🟢 |
| 4 | `original-cyan-palette` | 18 种青色覆盖色 / 8536 青色像素 / 22735 变化像素（macOS 钉值） | 本机 **25 种 / 8785 / 23218** | 🟢 |
| 5 | `remake-uses-fixed-palette` | 37 个底色 | 重制 **15** 个底色 ⇒ 也是抖动遮罩 | 🟢 |
| 6 | `remake-cyan-colour-count` | **25** 种 | 重制 **20** 种 | 🔴 差 −5 |
| 7 | `remake-blend-model` | 固定的一小套青色调色板 ＋ 抖动遮罩 | 源码 `battle_range_ui_style.h`：`move_primary` + `blend 10/16`（把一种颜色按比例混进地图色） | 🔴 |

> 注 1：两侧的计数是在**各自**的帧对上量的（原版 step-25→26，重制 step-20→21），
> 可达格集合与相机都不同，数字本身不必相等；**逐格**比对是覆盖层那条线
> （`notes/s49-fidelity/F-overlay-ground-truth.md`）的事，这里只判「规则」不判「每一格」。
> 注 2：像素测量说重制侧的输出也是「同一底色落到多于一种覆盖色」（15 个底色），
> 而重制侧源码写的是「把一种颜色按比例混进地图色」—— 这两件事不矛盾：
> 混色本身带抖动，所以输出不是单一颜色，但覆盖色**不固定**，仍不是原版那套固定调色板。

### 4.6 单位待机帧序与相位（8 条：5 🟢 / 3 🔴）

| # | 项 | 原版 | 重制 | 判定 |
|---|---|---|---|---|
| 1 | `original-redraw-cadence` | 183/191 次帧间变化（macOS 钉值） | 本机 **91/191** | 🔴 差 −92 |
| 2 | `original-distinct-images` | 30 张不同图像 / 1 帧重复（macOS 钉值） | 本机 **16 张 / 16 帧重复** | 🟢（仍 ≫ 3） |
| 3 | `original-changed-region` | 包围盒 **[109,32,146,90]**（macOS 钉值） | 本机 **[109,32,146,90]** | 🟢 |
| 4 | `local-emulation-cadence` | macOS 侧每帧改一次调色板 | 本机 **每 2.2 帧改一次**（PRAM 转储实测） | 🟢**（订正后）** |
| 5 | `rom-field-slot` | 62 个角色有 field 槽 | 62 | 🟢 |
| 6 | `rom-cycle-holds-three` | 原版实测 30 张 | ROM 的 32 帧周期最多 **3** 张 | 🟢 |
| 7 | `rom-model-cannot-explain` | 原版 32 帧内 16 张 | ROM 模型最多 3 张 ⇒ **矛盾仍在** | 🟢 |
| 8 | `remake-can-match-cadence` | 原版 32 帧内 16 张（macOS 30 张） | 重制侧（照 ROM 模型）最多 **3** 张 | 🔴 |

> ⭐ **2026-10-24 订正（wave 2 H 流证伪，原第 1/4 条的红是误判）**：
> 「本机模拟器把游戏的动画推进速度放慢了一倍」**不成立** —— 实为**采集重复**
> （探针 Lua `frame` 回调每 GBA 帧触发两次，相邻偶/奇对 12/12 逐字节相同）。
> ⇒ **绝对计数现在可以直接跨模拟器比**（本机采集帧数 ÷2 即得 GBA 帧）；
> 第 1 条与第 4 条的红**随之撤销**（两边调色板改写节奏其实一致）。
> 证据：`notes/s49-fidelity/H-idle.md` §1（假设 H1/H2 均**已证伪**）。
> ⚠️ **「一律按内容定位」仍然有效**（`grid16` 只有 1 帧瞬态）。
> 第 8 条**仍是真产品差**，但 H 流已查明根因：**不是「跟不上节奏」**，
> 而是**重制侧没实现逐帧调色板改写**（原版每 1 帧改 OBJ 调色板 index 15，重制从不改）
> —— 姿态节奏两侧其实**完全一致**（每 8 帧换一次，9→10→11→10/32）。
> **这是既有缺口，未被填上。**

### 4.7 0xFBFF 损坏终止符的缺陷语义（7 条，全绿）

| # | 项 | 原版 | 重制 | 判定 |
|---|---|---|---|---|
| 1 | `rom-trailer` | `fffb0000`，有符号值 **−1025**（不是 −1 ⇒ 渲染器不会停） | 同 | 🟢 |
| 2 | `rom-renderer-windows` | 两段指令窗口哈希与逆向侧签名一致 | 重新算出来一致 | 🟢 |
| 3 | `rom-control-rom` | 对照 ROM sha256 `3f55e607…`（逆向侧签名） | 重新算出来一致 | 🟢 |
| 4 | `runtime-overrun` | 基线读 4 个指针、步长 20；语义 `not_a_terminator_renderer_overrun` | 逆向侧签名轨迹一致 | 🟢 |
| 5 | `runtime-control-stops` | 对照轨迹在 `0x0825A8E4 = 0xFFFF`（−1）就停 | 一致 | 🟢 |
| 6 | `catalog-records-defect` | 逆向侧导出器记 `frame_trailer_raw_hex` + `renderer_terminator` | 重制侧目录记了 `fffb0000` + `renderer_terminator: false` | 🟢 |
| 7 | `catalog-keeps-corrupt-value` | 0xFBFF（损坏值，渲染器越界是原版画面的一部分） | `fbff` | 🟢 |

> 这一条在本机能**全判**，是因为逆向线在本机存在
> （`D:\Shell\gba-naruto-reverse\artifacts\character-fbff-runtime-v1\`）。

---

## 5. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| H1 | 本机能把重制线的五个测量器跑起来 | 逐个跑，看是否 exit 0 且给出数值 | **否** —— 五个测量器都依赖 macOS 的 `artifacts/s49-fidelity-20261019-v1/` 里的 PNG 帧，而那些帧已被 2026-10-19 的清理带走；`measure_s49_rule_fbff.py` 的 `DEFAULT_REVERSE_ROOT` 也是 macOS 路径 | **已证伪** |
| H2 | 原版走位可以用 macOS 的配方在本机重录 | 用 `walk-original-a24/inputs.json` 钉的存档/ROM/脚本/参数重录 | **是** —— 25 帧录出，且逐帧与另一条 stream 的本机录制（`build/s49-original-walk`）**像素相同** | **已确认** |
| H3 | 本机重录 == macOS 录制的原版 | 四个基准：EWRAM 单位池逐字节、配方哈希、幸存的原版像素、门禁钉住的规则数值 | **是** —— 单位池 0 字节差；幸存的像素残差 273 px 且状态栏 0 px；規則数值 107/150 逐值相同 | **已确认** |
| H4 | 本机与 macOS 的走位是同一条路径（可以按序号配对帧） | 比对本机第 17 步与 macOS 遗留的第 17 步画面 | **否** —— 本机第 17 步还在对话（鸣人/佐助头像），macOS 第 17 步已经在战场；本机第 25 步才是移动范围画面，macOS 是第 19 步 | **已证伪** |
| H5 | 可以靠「亮文字像素数」定位指令菜单画面 | 数右侧竖条里的白色像素 | **否** —— 对话框把那个区域整片填满（(231,247,214) 一万多个像素），分数反而最高 | **已证伪** |
| H6 | 可以靠「暗色化单位最左列的众数」定位朝向画面 | 在整段录制里统计众数 | **是** —— 两侧众数都是 **80**（其余列只在一两帧里出现）；与 macOS 钉的 80 一致 | **已确认** |
| H7 | 可以靠「连成一片的青色覆盖格」定位移动范围画面 | 在相邻帧对里找最大连通块 | **是** —— 原版 step-25→26（144 格）、重制 step-20→21（55 格）；但**只加连通块不够**：重制的 step-03→04（菜单→部署）会赢，**必须再加「该帧没有对话框」** | **已确认** |
| H8 | 本机模拟器与 macOS 的 mGBA 推进游戏的速度一样 | 带调色板转储地录 12 帧，数 PRAM 变化次数 | **否** —— 本机**每 2 帧**才改一次调色板（12 帧里改 5 次），macOS 是每帧改一次 | **已证伪** |
| H9 | 真实 BIOS 会改变这个节奏 | 同一段录制加 `--bios recomp/bios/gba_bios.bin` 再测 | **否** —— HLE BIOS 与真实 BIOS 的结果**完全一样**（每 2 帧改一次） | **已证伪** |
| H10 | 重制侧的覆盖层是单一平涂（门禁的说法） | 读重制侧源码 + 在重制侧走位里量覆盖层统计 | **一半** —— 源码写的是 `blend 10/16`（平涂），但**像素实测**得到 15 个底色各对应多于一种覆盖色 ⇒ 混色本身带抖动，输出不是单一颜色；但覆盖色**不固定**（20 种 vs 原版 25 种），仍不是原版那套固定调色板 | **部分确认** |
| H11 | 重制侧的战斗单位池能像原版那样 dump 出来 | 用重制侧的 ROM 跑，dump EWRAM | **未验** —— 重制侧的单位是 C++ 结构体，布局与原版的 0x1D4 记录不同；定位结构体地址不在本 stream 的范围内，也没有现成工具 | **未验** |

---

## 6. 剩下什么

按「离「逻辑状态完全一致」还有多远」排：

| # | 缺口 | 现在差多少 | 谁该做 |
|---|---|---|---|
| 1 | **重制侧运行时单位池** | 名册在数据表层面全绿（9 槽 × 8 字段无差异），但重制侧**运行时**那份单位数组没 dump ⇒ 「运行时实际值」判不了。差一步：定位 `battle_unit` 结构体在 EWRAM 的地址与字段偏移，然后照原版的办法 dump + 同样解码 | 逻辑 state 线（本 stream 的下一轮） |
| 2 | **重制侧的红 結束 帧** | 重制侧录像走不到敌方回合（目标选择卡 `CANNOT SELECT`）⇒ 状态栏「红/蓝成对出现」这条在像素上判不了。差一次能走到敌方回合的输入序列（或者一条会认 `CANNOT SELECT` 的按键序列） | 逻辑 state 线（与覆盖层那条线协同：覆盖层那条已经在做重制侧走位） |
| 3 | **重制侧跟不跟得上原版的待机节奏** | 这是**真产品差**：原版 32 帧周期 16 张（macOS 30 张）不同图像，重制侧照 ROM 的 hold 模型最多 3 张。差的是逆向侧还没闭合的**原版帧序**（`notes/s49-field-frame-order-20261020.md` 那条线），不是重制侧的代码 | 逆向线（帧序）+ 产品线（实现帧序） |
| 4 | **覆盖层的逐格一致** | 本 stream 只判了「规则」（是不是抖动遮罩）；两侧的青色覆盖色数量 25 vs 20 不等。逐格比对要用原版导出的逐单元答案（`s49-original-movegrid-tilemap-v1/`），那是覆盖层那条线的事 | 覆盖层那条线 |
| 5 | **macOS 门禁的「逐帧计数」类数字** | 183/191、30 张这类数字**不能跨模拟器直接比**（本机是 91/191、16 张，差一倍）。要保留这些门禁，就得把它们改成「相对」判据，或者把原版侧的数字改成在本机重录的 | 逆向线（门禁口径） |

**一句话**：**逻辑状态这一半现在差 2 项真缺口 + 3 项未判**：
①重制侧运行时单位池（1 步可做）；②重制侧敌方回合的红 結束 帧（1 次走位可做）；
③待机节奏的产品差（卡在逆向线的帧序没闭合）。
名册、朝向、状态字判据、0xFBFF 缺陷语义这四块**已经是绿的**。

---

## 7. 卡在哪

* **卡点 1：跨模拟器的帧计数不可比。** ~~本机模拟器把游戏的动画推进放慢了一倍
  （PRAM 实测：每 2 帧改一次调色板；HLE BIOS 与真实 BIOS 都一样）。~~
  ⭐ **2026-10-24 订正（wave 2 H 流证伪）**：本卡点的**前提不成立** ——
  「慢一倍」实为**采集重复**（探针 Lua `frame` 回调每 GBA 帧触发两次，
  相邻偶/奇对 12/12 逐字节相同）。⇒ **绝对计数现在可以直接跨模拟器比**
  （本机采集帧数 ÷2 即得 GBA 帧）。
  证据：`notes/s49-fidelity/H-idle.md` §1（假设 H1/H2 均**已证伪**）。
  ⚠️ **「一律按内容定位」仍然有效**（`grid16` 只有 1 帧瞬态，帧序号不可靠）。
  另：本卡点里「原版 ≫ ROM 模型的 3 张」这个**规则性矛盾仍然成立**，
  但它的根因已被 H 流查明：**重制侧没实现逐帧调色板改写**（不是「跟得慢」）。
* **卡点 2：重制侧走位到不了敌方回合。** 目标选择画面在 `CANNOT SELECT` 上卡住，
  A 键被光标吃掉。已排除：零输入帧数、按键序列长度（63 帧都试过）。
  **没解决**：需要一条会移动光标 / 确认目标的按键序列（或覆盖层那条线已经做出来的走位）。
* **卡点 3：重制侧运行时单位池的内存布局未知。** 原版的池是定长 0x1D4 记录，
  位置固定；重制侧是 C++ 结构体，地址与字段偏移都要先找。
  **没解决**：本 stream 没有做这个定位（超出「让测量器在本机跑起来」的范围）。
* **卡点 4：原版 macOS 的 25 帧 PNG 已被清理。** 因此**逐帧**的 macOS ↔ 本机比对做不了，
  只能用幸存的像素基准（`s49-original-field-frame-v1` 六帧）＋ 规则数值。
  这不是本 stream 能解决的。

---

## 8. 复跑

```powershell
cd D:\Github\gba-naruto
$env:PYTHONIOENCODING='utf-8'

# 1) 重录证据（约 30 秒）
python tools\s49_logic_checks\record_evidence.py

# 2) 出红绿表（约 2 分钟）
python tools\s49_logic_checks\run_all.py

# 3) 只跑一项
python tools\s49_logic_checks\check_battle_roster.py
python tools\s49_logic_checks\check_rule_standby_state.py
python tools\s49_logic_checks\check_rule_ai_facing.py
python tools\s49_logic_checks\check_rule_move_grid.py
python tools\s49_logic_checks\check_rule_idle_sequence.py
python tools\s49_logic_checks\check_rule_fbff.py
python tools\s49_logic_checks\check_original_equivalence.py

# 4) 机器可读
python tools\s49_logic_checks\run_all.py --json
```

退出码：0 全绿 / 1 有红 / 2 缺输入 / 3 有灰（无红）。
