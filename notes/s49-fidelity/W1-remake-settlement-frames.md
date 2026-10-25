# 流 W1 —— 重制侧开机流程建模 + 录「勝利」屏/结算屏运行帧

> 工具：`tools/s49_battle_balance/w1_{probe,boot,record,drive,verify,settlement_table,brightness,diag}.py`、
> `tools/s49_battle_balance/w1_capture.lua`
> 产物：`build/s49-battle-balance/w1/`
> 2026-10-24 · stream W1（wave 11）。**所有数字都是本机实测。**
> 逆向线 `D:\Shell\gba-naruto-reverse` **全程只读**；重制线 **零改动**；**未提交 git**。

---

## 0. 一句话结论

**开机流程建模完成（U2 留下的卡点已解决），但「勝利」屏与结算屏运行帧没有录到 ——
原因不在开机、不在数值，而是「U2/V4 的开环键脚本在重制 ROM 上根本打不完这场仗」：
重制侧的战斗在第 1 回合的指令菜单处**失步**，战斗场景在第 5 471 帧被**中止**
（指令菜单 → 战前准备场景，中间没有 `outcome` / `result` / `level_up` 任何一屏），
游戏于是在「战斗 ⇄ 战前准备场景 ⇄ 战前简报」之间循环，
**战斗永远不会打完** ⇒ `outcome → result → level_up` 这三屏在 ROM 上不可达。**

已交付的部分：

* ⭐ **重制侧开机流程的完整按键模型**（读重制线自己的 `battle_preparation_flow` /
  `battle_deployment_flow` 得出，逐屏在真机上验过），
  以及一个**闭环开机驱动器**（`w1_boot.py`：用「黑场」当相位标记，
  停在战斗开场对白第 1 页且打字机跑完）；
* ⭐ **两次独立跑逐字节一致**的完整录制（各 **114 999 帧**，`identical: true`，
  ROM sha 与脚本 sha 都进收据）；
* ⭐ **逐屏对照表**（重制侧每一屏 × 原版真值每一图：原版 sha / 重制侧 sha / 差 px / 差 bbox）；
* ⛔ **未达成**：「勝利」屏与结算链（`outcome` / `result` / `level_up`）的运行帧。

---

## 1. 改动文件清单

### 1.1 本仓库（`D:\Github\gba-naruto`）—— 本流新建

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_probe.py` | **新增** | ⭐ **探针客户端**（单后台读线程 + 队列）。共享的 `tools/s49_victory_capture/probe.py` **每行开一个读线程**，长 `frames` 命令后会乱序吃掉 sentinel，客户端随后等一条永远不会来的输出 ⇒ 录制看起来「卡住」（实测 CPU 5 %、6 分钟只走 5 841 帧）。本流**不改**那个共享工具，只自己带一个可靠的。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_boot.py` | **新增** | ⭐ **闭环开机**：用重制侧自己的 `battle_preparation_flow` / `battle_deployment_flow` 建模开机流程（A→确认，Down→移动选项），再用**黑场当相位标记**走到战斗开场对白第 1 页，打字机跑完后停手。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_record.py` | **新增** | ⭐ **回放 + 录制器**：闭环开机 → 载入胜利键脚本 → 探针 Lua 帧回调逐帧截图 → 收据（ROM sha / 脚本 sha / 帧数 / 录制窗口）。`--capture all\|step`，帧预算分块执行。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_drive.py` | **新增** | **交互/脚本化手动驱动器**：REPL + JSON 计划（press/wait/hold/shot/save/load/dump/**boot**），用来在真机上逐屏看重制侧的流程。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_verify.py` | **新增** | **两次跑逐字节一致**校验（帧级 sha256 + ROM/脚本 sha 比对），收据 JSON。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_settlement_table.py` | **新增** | ⭐ **逐屏对照表**：重制侧每一屏 × 原版真值每一图 ⇒ 原版 sha / 重制侧 sha / 差 px / 差 bbox。差 px 用**逐像素**口径（共享的 `v4_settlement_compare.py` 把差分字节**三个一组**数，既少算又可能越界崩溃）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_brightness.py` | **新增** | 帧亮度/暗像素统计（用来自动判「黑场」与「对话页」）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_diag.py` | **新增** | 诊断：探针 stderr 落盘 + 帧预算分块计时（定位「慢/卡」）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\w1_capture.lua` | **新增** | 帧精确录制脚本（V4 的 `capture_victory_frames.lua` 同契约），多一个 `MGBA_W1_CAPTURE_FROM` 录制窗口开关。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\W1-remake-settlement-frames.md` | **新增** | 本文件。 |
| `D:\Github\gba-naruto\build\s49-battle-balance\w1\**` | 临时产物 | 开机探针帧 / 多次录制 / 校验收据 / 对照表（**7 GB 以上的 PNG**，见 §8）。 |

**没有**改重制线任何文件、逆向线任何文件、其它流的仪器
（`tools/s49_victory_capture/*`、`tools/s49_package/*`、`tools/mgba_probe/*` 一律**只读调用**）。

---

## 2. ⭐ 重制侧开机流程（读重制线源码 + 真机逐屏实测得到）

U2 留下的卡点（「部署画面是交互式的，离线控制器完全没建模」）**已经定位到具体源码**：

| 段 | 重制侧的模型（源码） | 屏 | 按键 |
|---|---|---|---|
| 1 | `battle_preparation_flow`（`battle_preparation_flow.h`）的 `root` 相位，4 个选项 `队伍·装备 / 查看地图 / 开始任务 / 储存`，`move(+1)` 循环 | 战前简报 + 绿框菜单 | **`Down` `Down`**（把光标从 `队伍·装备` 移到 `开始任务`） |
| 2 | `root` 相位 `confirm()` → `start_confirmation`（「开始任务吗？」是/否，默认是） | 确认框 | **`A`** |
| 3 | `ready` → 部署画面（`battle_deployment_flow`：`unit_confirmation` → `start_confirmation`） | 部署画面（9 个单位） | **`A` × 9** |
| 4 | 部署画面 `complete` → 「开始」标题 → 确认 | 「开始」标题 | **`A`** |
| 5 | `battle_black_field` 事件 1（部署 → 战斗的淡出） | **黑场** | 无输入 |
| 6 | 战斗开场对白（`script_blocked` / `wait_for_input`，**打字机**效果） | 对白页 | **`A` × 3**（3 页） |
| 7 | `battle_black_field` 事件 2（对白结束 → 回合 1 页） | 黑场 | 无输入 |
| 8 | 回合横幅（`turn_banner`，「回合 1 / 玩家 / 敌行动」） | 横幅 | **`A`** |

⇒ **实测的开机前缀**：`wait 120` → `Down` `Down` → `A`×12 → （黑场）→ 对白第 1 页。
`w1_boot.py` 把这段做成**闭环**：按 A 直到**看见黑场**（黑场是唯一的相位标记：
暗像素 38 095/38 400 = 99.2 %，其它屏最多 6 541 = 17 %），再等黑场结束，
最后等画面**连续 30 帧不变**（打字机跑完）才停手。

⭐ **对齐点**：胜利键脚本的第 1..3 步是 **3 次 `script_blocked` 确认**（hold=120）、
第 4 步是**回合横幅确认**（hold=4）⇒ 开机必须停在**对白第 1 页**，脚本才会接上。
实测：对白第 1 页 → 脚本 A,A,A → 第 3 页 → 回合横幅 → 脚本第 4 步 A → 战斗指令菜单。

---

## 3. ⭐ 重制侧 ROM 的两处回归（同一驱动 / 同一按键计划，只换 ROM）

| ROM | sha256（前 16） | 构建时间 | 第 1 回合页面 | 结论 |
|---|---|---|---|---|
| `build/s49-w1/rom-before.gba` | `804dd79384a96a2c` | 02:54 | **开机流程都不同**（没有部署画面） | 不可用 |
| `build/s49-package-u4/rom/butano-sequel.gba` | `2165061414d6009a` | 11:46/11:50 | ✅ **每个键都推进**（13 屏哈希互不相同） | ✅ **本流的录制对象** |
| 发布 ROM `butano-sequel\butano-sequel.gba` | `af0352d0dd4da7eb1` | **13:07** | ⛔ **A / ← → ↑ ↓ / L / R 全部无效**；画面 2 400 帧不变；按 **START** 直接变黑并永远黑 | ⛔ 回归 |
| `build/w3-probe/w3.gba` | `b6c2a05fa50e2861` | **13:38** | ⚠️ 第 1 回合能推进，但**在指令菜单处失步**（见 §4） | ⚠️ 回归 |

⇒ 回归都出现在**并行流改 `battle_runtime_scene.cpp`（W3 独占，未提交 1 191 行）/
`battle_scene_controller.h`（未提交 178 行）**的窗口里。
**归属：重制线**；本流**零改动**。

---

## 4. ⭐ 真正的卡点：开环键脚本在 ROM 上打不完这场仗

### 4.1 现象（在 `21650614…` 这版**能推进**的 ROM 上）

逐帧看录制的每一屏（`fullA/frames`，114 999 帧）：

| 帧区间 | 屏 |
|---|---|
| 240 – 3 800 | 战斗（对白 → 回合横幅 → 指令菜单 → 移动 → 攻击） |
| 3 800 – 4 900 | 攻击/移动动画（每帧都不同） |
| 4 901 – 5 470 | 战斗（指令菜单 / 术·忍具·行动确认 / 目标选择） |
| 5 471 – 5 498 | **战前准备场景**（`队伍·装备`）—— 战斗场景在这一帧被**中止**，场景退回战役/准备场景 |
| 5 499 – 5 506 | 黑场 |
| 5 507 – 6 100 | 准备场景（`队伍·装备` / `EQUIP PPE·TOOL·SLOT` / `UNEQUIP COMPLETE` / `UPGRADE RECIPE·MATERIAL·BAG`） |
| 6 101 – 6 332 | **战前简报**（`保护木叶丸不被蜜蜂攻击！`） |
| 6 333 – 9 086 | 又回到战斗的指令菜单 |
| 9 087 – … | 又回到准备场景 → 再进战斗 ⇒ **循环** |

⇒ **战斗永远不结束**，游戏在「指令菜单 ⇄ 战斗中段训练相位 ⇄ 战前简报」之间循环。

### 4.2 为什么

U2 的键脚本是**离线**用重制侧自己的 `battle_scene_controller` 算出来的：
每个键 = 一次 controller 调用。**但离线控制器的相位序列与 ROM 的相位序列不是一回事**：
离线控制器从「场景加载完」开始，ROM 还要经过「回合横幅 → 敌行动 → 我方单位选择 →
指令菜单 → …」，键的落点错位一格，之后就再也回不来
（ROM 的输入分派里 `presentation_frame` / `map_movement.busy()` 分支会**吞掉**按键）。

⇒ **要打完这场仗，必须改成闭环驱动（读 ROM 的相位/光标 → 决策 → 按键），
或者重算一条与 ROM 相位对齐的键脚本。** 本流没有做到（见 §8）。

### 4.3 ⭐ 顺带纠正 V4 的一个结论

V4（wave 9）在重制 ROM 上录到的「结算链」四屏
（「AVAILABLE TOOL」「NO AVAILABLE TOOL」「EQUIP COMPLETE」「隊員一覧表」）
**不是结算链**，而是**战前准备场景（`battle_preparation_scene.cpp`）的装备屏**。
证据（本流 11.5 万帧录制里的上下文）：

* 这些屏**只出现在战斗场景被中止、场景退回战役/准备场景之后**：
  战斗的指令菜单（`忍術 / 忍具 / 行動確認`）到 5 470 帧为止，
  **5 471 帧**直接变成 `队伍·装备`（准备场景的 `equipment_root`），
  **中间没有 `outcome` / `result` / `level_up` 任何一屏**；
* 6 101 帧出现**战前简报**（`保护木叶丸不被蜜蜂攻击！`），
  6 333 帧又回到战斗的指令菜单 ⇒ 游戏在
  「战斗 → 中止 → 准备场景 → 再进战斗」之间循环。

⇒ V4 §5「重制侧的结算链实测录到 training 段」这条应改读成
「重制侧**战前准备场景的忍具装备屏**被误当成了结算链」；
**重制侧的真结算链（`outcome` / `result` / `level_up`）至今没有运行帧。**

### 4.4 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **W1-1** | 重制侧的「部署画面」需要离线控制器建模才能走通 | 读 `battle_preparation_flow.h` / `battle_deployment_flow.h` 的相位机 + 真机逐屏实测 | 部署画面 = `A`×9 + 起始确认 `A`；准备菜单 = `Down Down` + `A` + `A` ⇒ **不需要改控制器，只要建模按键** | **已证伪**（不需要建模控制器） |
| **W1-2** | 重制侧开机后停在某个需要很多次 A 的画面 | 闭环 boot：按 A 直到出现黑场 | **13 次 A** 出现黑场（2 次准备 + 9 次部署 + 1 次起始 + 1 次落在黑场里） | **已确认** |
| **W1-3** | 黑场可以作为「已进入战斗」的相位标记 | 逐帧亮度统计 | 黑场暗像素 38 095/38 400（99.2 %），其它屏最多 6 541（17 %）⇒ 可判 | **已确认** |
| **W1-4** | 胜利键脚本从战斗**开场对白**开始录 ⇒ 开机必须停在**对白第 1 页** | 读 `u2_route_gen.cpp`：脚本第 1..3 步是 `script_blocked` 确认（hold=120），第 4 步是 `turn_banner` 确认（hold=4） | 对白恰好 3 页 + 1 横幅 ⇒ 对齐点 = 对白第 1 页 | **已确认** |
| **W1-5** | U2 的「按键被开机流程吃掉」是**开机前缀**的问题，不是键脚本的问题 | 用闭环 boot 重新对齐后再回放同一份 `routeA.json`（sha `197b164f…`） | 战斗**正常推进**（战斗画面、指令菜单、忍术菜单都在变）⇒ 开机前缀这一层已经解决 | **已确认** |
| **W1-6** | 共享的 `probe.py` 客户端会让长录制卡住 | 把同一个 `frames` 命令拆块 vs 单块；对比 CPU 与推进帧数 | 单块 55 000 帧：CPU 5 %、6 分钟只走 5 841 帧；拆块：**2 400 fps** | **已确认**（客户端每行一个读线程会乱序吃 sentinel） |
| **W1-7** | 探针的 `save` 命令会 arm 断点 ⇒ 之后走慢速调试路径 | 去掉 `save` 后重测 | 去掉 `save` 仍然慢 ⇒ **不是** `save` | **已证伪** |
| **W1-8** | 战斗场景比对话场景慢 ⇒ 探针慢 | 同一帧号（65 573）在两个场景下对比 | 对话场景 2 200 fps；战斗场景 **≈ 70 fps**（重制侧战斗场景本身重） | **已确认** |
| **W1-9** | 键脚本的 `settle` 太大（2 500 帧的 presentation）是浪费 | 把 settle 统一缩到 0.5 倍重跑 | 第 6 431 帧就黑屏卡死 ⇒ 但**那次跑的是坏 ROM**（§3），结论被污染，**未在好 ROM 上重测** | **未验**（作废，待重测） |
| **W1-10** | 战斗卡死是**驱动/脚本**的问题，不是 ROM 的问题 | 同一计划换 ROM 跑（只换 ROM 这一个变量） | `21650614…` 每键推进；`af0352d0…` 第 1 回合全无效；`b6c2a05f…` 在指令菜单失步 ⇒ **有两处 ROM 回归** | **已确认** |
| **W1-11** | 键脚本的帧预算算少了，录制在脚本结束前就停 | 对照脚本 settle 总和（111 635）与 `budget_for()` 的结果 | `budget_for()` 把纯等待 token 按 98 帧算 ⇒ 预算 55 578（**少 61 821**）；修后 **117 399** | **已确认**（已修） |
| **W1-12** | 结算链在 ROM 上可达 ⇒ 「勝利」屏与结算屏能录出来 | 完整回放 300 步键脚本（11.7 万帧） | 战斗**从未打完**：战斗场景在 5 471 帧被**中止**（指令菜单 → 准备场景，中间没有 `outcome`/`result`/`level_up` 任何一屏），游戏在「战斗 ⇄ 战前准备场景 ⇄ 战前简报」之间循环 | **已证伪**（开环键脚本打不完这场仗） |
| **W1-13** | V4 录到的「重制侧结算链四屏」其实是结算链 | 看这些屏在录制里的上下文（前后帧） | 同款屏出现在**战斗场景被中止之后**（前面是战斗的指令菜单，后面是战前简报再进战斗）⇒ 是**战前准备场景**的装备屏 | **已确认**（V4 的读法要改） |
| **W1-14** | 两次独立跑逐字节一致 | `w1_verify.py` 帧级 sha256 | 114 999 帧 ×2，`differing_count = 0`，`identical: true` | **已确认** |

---

## 5. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 |
|---|---|---|
| **A1** | `python tools/mgba_probe/build.py`（`$env:KONOHA_PROBE_OUT=build/mgba-probe-w1`） | 私有探针重建成功；共享的 `build/mgba-probe/mgba-probe.exe` **未动** |
| **A2** | `w1_drive.py --plan plan-explore{1..8}.json` | 逐屏实测：准备 `root` → 部署（9 个单位）→「开始」→ 黑场 → 对白 3 页 → 回合横幅 → 指令菜单 |
| **A3** | `w1_boot.py --out build/s49-battle-balance/w1/boot1` | **13 次 A** 见黑场（luma 0.0）；稳定后停在**对白第 1 页**（小樱「真的呀！谢谢你，外婆很累了」） |
| **A4** | `w1_diag.py --chunk 500 --frames 12000` | 分块 500 帧：每块 0.20–0.28 s ⇒ **2 400 fps**；单块长命令 ⇒ 慢 20 倍 ⇒ 定位到共享客户端 |
| **A5** | `w1_record.py --state <savestate> --frames 12000` | 5.4 s / 12 000 帧；stderr 报 `Savestate is for a different version of the game` ⇒ **ROM 被并行流重建过** |
| **A6** | `w1_drive.py --rom <4 个不同 ROM> --plan plan-explore9.json` | 13 屏哈希：02:54 版开机就不同；`21650614…` 每键推进；`af0352d0…` 全同；`b6c2a05f…` 在指令菜单处失步 |
| **A7** | `w1_record.py --rom 21650614… --boot-auto --capture step`（40 步截断脚本） | 41 帧**几乎全不同** ⇒ 战斗在正常推进 |
| **A8** | `w1_record.py --rom 21650614… --boot-auto --capture all --capture-from 1` | **frames_run = 117 399**，**frames_captured = 114 999**（帧 1..114 999） |
| **A9** | `w1_verify.py --a fullA --b fullB` | **identical: true**（见 §6） |
| **A10** | `w1_settlement_table.py --truth build/s49-victory-capture/w4/settlement-truth --remake fullA/frames --min-run 30` | 见 §7 |
| **A11** | `Get-CimInstance Win32_Process -Filter "Name='mgba-probe.exe'"` | 孤儿 `mgba-probe.exe` **0** 个（收尾复查） |

### 5.1 两个工具缺陷（本流已修，记录给其它流）

| 缺陷 | 现象 | 修法 |
|---|---|---|
| `tools/s49_victory_capture/probe.py` **每行一个读线程** | 长 `frames` 命令后客户端乱序吃掉 sentinel ⇒ 后续等一条永远不会来的输出 ⇒ 表现为「探针卡住、CPU 只有 5 %」 | 本流自带 `w1_probe.py`（**单**读线程 + 队列）。**建议共享工具也这样改** |
| 本流 `w1_record.py` 的 `budget_for()` 把「纯等待」token（`:2500:0`）按 98 帧算 | 帧预算少算 **61 821 帧** ⇒ 录制**在脚本结束前就停**，最后几个键步骤从没触发 | 已改成按 `settle + hold + 4` 算；修后预算 55 578 → **117 399** |

---

## 6. 两次独立跑（逐字节一致）

`build/s49-battle-balance/w1/verify.json` / `verify-full.json`：

| 项 | 值 |
|---|---|
| ROM | `build/s49-package-u4/rom/butano-sequel.gba`，sha256 `2165061414d6009a08566eb1998d70851fd4eb8596d4127a4597fcc28a33f242`（两次相同） |
| 键脚本 | `build/s49-battle-balance/u2/routeA.json`，sha256 `197b164f26cc64af28f6974250152ac3edf6f014caa1e12f4be4bf4280223790`（两次相同） |
| 录制 | `fullA` / `fullB`：闭环开机 → 300 步胜利键脚本 → 逐帧 PNG（帧 1..114 999） |
| 帧数 | A = B = **114 999**，`only_in_a = []`，`only_in_b = []` |
| 逐帧 sha256 不同 | **0** |
| 结论 | ⭐ **`identical: true`**（`build/s49-battle-balance/w1/verify-full.json`；另有一对 110 000 帧的录制同样 `identical: true`，见 `verify.json`） |

---

## 7. 结算链逐屏运行帧对照表

见 §7.1（表由 `w1_settlement_table.py` 生成，收据在
`build/s49-battle-balance/w1/settlement-table.json`）。

### 7.1 ⛔ 重制侧「勝利」屏与结算链（`outcome` / `result` / `level_up`）

**没有这一段** —— 重制 ROM 上的战斗**没有结束**（§4），
`outcome` / `result` / `level_up` 三屏**从未出现**。
⇒ **原版真值 `01-victory.png` / `02-settlement-exp-power-turns.png` /
`03..06-levelup-*.png` 在重制侧没有对应运行帧，对照表这三行不存在。**

### 7.2 重制侧**录到的**结算链相关屏（战前准备场景的装备屏）

（下面这张表是本流真正测到的「重制侧运行帧 × 原版真值」的逐屏对照；
它对照的是**重制侧的忍具装备屏**与**原版的忍具一览 / 升级屏**，
因为原版把这几屏放在结算链里、重制侧把它们放在**战斗内部**的 `training` 相位。）

<!-- TABLE-7-2 -->

⚠️ **这张表怎么读**：`best original` 是**机械最优匹配**（差 px 最小的原版真值）。
重制侧这些屏全是绿框面板，所以它们的最优匹配**都落在同一张原版图上**
（`06-levelup-sakura.png`，因为它的像素分布最接近绿框面板），
**这不是语义对应**。真正的语义对应是：

| 重制侧录到的屏（实测） | 原版真值里语义相同的那张 | 关系 |
|---|---|---|
| `队伍·装备`（角色 N / 队伍 N/3 / EQUIP 1/7 / 装备忍具·卸下忍具·强化忍具·返回） | `07-ninja-tool-list.png`（忍具一览） | **位置不同**：原版在结算链末段，重制侧在**战前准备场景**（战斗场景中止后退回战役场景） |
| `EQUIP PPE / TOOL / SLOT / OWNED / USED / UNEQUIP BACK` | `07-ninja-tool-list.png` | 同上 |
| `EQUIP COMPLETE` / `UNEQUIP COMPLETE` | `07-ninja-tool-list.png` | 同上 |
| `UPGRADE / RECIPE / TOOL / MATERIAL / BAG / OWNED` | `03..06-levelup-*.png`（逐人升级屏） | **语义相近但版式不同**：原版是「一个人一页」，重制侧是「一张配方表」 |
| `BATTLE COMPLETE / MISSION CLEARED`（`outcome`） | `01-victory.png`（勝利） | ⛔ **重制侧从未出现**（战斗场景被中止） |
| 结算屏（经验/战力/回合数） | `02-settlement-exp-power-turns.png` | ⛔ **重制侧从未出现** |
| 逐人升级屏 | `03..06-levelup-*.png` | ⛔ **重制侧从未出现** |

⇒ **逐屏对照表里原版真值的 9 张里，有 5 张（勝利/结算/4 张升级屏）在重制侧没有对应运行帧**，
这不是「差得远」，是**根本没有这一屏**。

#### 7.2.1 重制侧录到的每一屏（按停留时长排序，前 20）—— 机械对照表

| remake frames | remake sha256（head） | best original（机械最优） | original sha256（head） | diff px | diff bbox |
|---|---|---|---|---:|---|
| 11657-11900 (14748) | `c3f9b12f64358746` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12782 | [8, 5, 231, 152] |
| 79791-80098 (13488) | `32448aae41fd1cdd` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12166 | [4, 9, 231, 152] |
| 12517-12580 (12544) | `c0066bca13e2b195` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12782 | [8, 5, 231, 152] |
| 33259-33492 (12496) | `1cf8123410e9b834` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12806 | [8, 5, 231, 152] |
| 28425-31156 (5464) | `92d584764beeaf60` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11850 | [4, 9, 231, 152] |
| 80099-80342 (5169) | `0a6ce29c6a9b2f69` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11629 | [4, 9, 231, 152] |
| 11901-12272 (5132) | `945132e90838acbf` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11548 | [4, 9, 231, 152] |
| 34057-36798 (4138) | `b3e2e7a14fea1c79` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11590 | [4, 9, 231, 152] |
| 12581-12824 (3788) | `29b2d1e19e712f2d` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11659 | [4, 9, 231, 152] |
| 6333-9086 (3262) | `b7694658e7256c49` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11541 | [4, 9, 231, 152] |
| 5507-5844 (1290) | `7e2c15ccdd107c1c` | 03-levelup-naruto.png | `a876f32dbe100a65` | 13743 | [8, 9, 231, 152] |
| 58941-59004 (796) | `59d79d5a71eadbf7` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12802 | [8, 5, 231, 152] |
| 32643-32940 (660) | `976442c6509cf6fb` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11850 | [4, 9, 231, 152] |
| 31157-31474 (636) | `c352e43c638ea1bf` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11541 | [4, 9, 231, 152] |
| 32941-33258 (636) | `31ca027c3ad4fea0` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11541 | [4, 9, 231, 152] |
| 55401-55464 (552) | `f51b40d6b46b5025` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12802 | [8, 5, 231, 152] |
| 84255-84498 (552) | `73022e62652813e5` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11629 | [4, 9, 231, 152] |
| 28169-28424 (512) | `17eba545dc2bceeb` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12784 | [8, 5, 231, 152] |
| 31709-31962 (508) | `8031ca8eabd314c6` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 11541 | [4, 9, 231, 152] |
| 5845-6100 (490) | `f15c97a78a1ed9c6` | 06-levelup-sakura.png | `a0db87e9fd8ec358` | 12808 | [8, 5, 231, 152] |

（完整 56 屏在 `build/s49-battle-balance/w1/settlement-table.json`；
差 px 用**逐像素**口径，38 400 px 为整屏。）

---

## 8. 卡在哪 / 遗留风险

* ⛔ **主卡点（在本流范围内无法自解）**：重制 ROM 上的战斗要靠**闭环驱动**才打得完。
  开环键脚本在指令菜单处失步 ⇒ 游戏在「指令菜单 ⇄ 战斗中段训练相位 ⇄ 战前简报」之间循环
  ⇒ `outcome` / `result` / `level_up` 三屏不可达 ⇒ 「勝利」屏与结算链运行帧**未达成**。
  ⇒ **下一步（建议下一流）**：给重制侧做一个**闭环战斗驱动器**——
  读 ROM 的 `battle_scene_phase` / 光标（需要 `battle_scene_controller` 的内存地址，
  逆向线只读 ⇒ 要么在重制线加一个 telemetry 导出，要么在 ROM 侧做一次差分定位），
  再按相位决策按键。
* ⛔ **发布 ROM `af0352d0…`（13:07）与 W3 的 `b6c2a05f…`（13:38）两版都有回归**
  （§3）⇒ 本流的录制只能用 `2165061414d6009a…`（11:46 构建）。
  **归属：重制线（W3 独占 `battle_runtime_scene.cpp`）**，本流**零改动**。
* ⚠️ **ROM 在录制期间被并行流重建过**（`73b74587…` → `21650614…` → `9ff98640…` →
  `af0352d0…`；W3 的 `b6c2a05f…`）⇒ **任何录制收据都必须带 ROM sha256**。
* ⚠️ **重制侧战斗场景在 mGBA 上只有 ≈ 70 fps**（对话场景 2 200 fps）⇒
  一遍 11.7 万帧的脚本要 ≈ 28 分钟；**两遍必须并行跑**（本流就是这么做的）。
* ⚠️ **`tools/s49_victory_capture/probe.py` 的读线程模型有竞态**（长命令会卡死）。
  本流**没有改**它（它是共享工具），而是自带 `w1_probe.py`。
  ⇒ **建议其它流也换用 `w1_probe.py`**，或给 `probe.py` 加一条「单读线程」补丁。
* ⚠️ **V4 的「重制侧结算链已录到」需要改读**（§4.3）：那四屏是**战斗中段的
  `training` 相位**，不是结算链；**重制侧真结算链至今没有运行帧**。
* ⚠️ **磁盘**：`build/s49-battle-balance/w1/` 下有 4 次完整录制
  （`fullA` / `fullB` 各 114 999 帧，`finalA` / `finalB` 各 110 000 帧）
  ⇒ **合计 487 370 个文件 / 2.5 GB**，需要清理（留给父代理）。

---

## 9. 确认

* **新文件一律 LF、无 BOM**（见 §10 的扫描结果）。
* **未提交 git**（本流文件在工作区里是未跟踪状态：`?? tools/s49_battle_balance/`、
  `?? notes/s49-fidelity/`）。
* **未改重制线任何文件**（`D:\Shell\gba-naruto-butano` 只读使用）。
* **未改逆向线任何文件**（`D:\Shell\gba-naruto-reverse` 只读）。
* **未改其它流的仪器**（`tools/s49_victory_capture/*`、`tools/mgba_probe/*`、`tools/s49_package/*` 只读调用）。
* **没有伪造任何帧**：所有 PNG 都来自探针内 Lua 帧回调的逐帧截图；
  对照表里的每一行都能在 `build/s49-battle-balance/w1/fullA/frames/` 里找到原图。
* **孤儿进程检查**：收尾时 `mgba-probe.exe` 残留 **0** 个。

---

## 10. LF / BOM 扫描

| 文件 | bom | crlf_pairs |
|---|---|---:|
| `tools/s49_battle_balance/w1_probe.py` | False | 0 |
| `tools/s49_battle_balance/w1_boot.py` | False | 0 |
| `tools/s49_battle_balance/w1_record.py` | False | 0 |
| `tools/s49_battle_balance/w1_drive.py` | False | 0 |
| `tools/s49_battle_balance/w1_verify.py` | False | 0 |
| `tools/s49_battle_balance/w1_settlement_table.py` | False | 0 |
| `tools/s49_battle_balance/w1_brightness.py` | False | 0 |
| `tools/s49_battle_balance/w1_diag.py` | False | 0 |
| `tools/s49_battle_balance/w1_capture.lua` | False | 0 |
| `notes/s49-fidelity/W1-remake-settlement-frames.md` | False | 0 |
