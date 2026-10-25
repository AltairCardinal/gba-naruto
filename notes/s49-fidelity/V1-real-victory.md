# V1 —— 真实打完仗 + 结算链运行帧真实版（wave 16）

> 工具：`tools/s49_battle_balance/v1_battle.py`（**闭环战斗驱动器**：照抄原版 `w4_play.py`
> 的目标选择策略 + U2 的攻击格规则）、`v1_truth.py`（把重制侧的地图/招式表解析成
> `build/v1/battle-truth.json`）、`v1_compare.py`（**逐屏对照表**）、
> `v1_diag_*.py`（5 个诊断器）
> 产物：`build/v1/{run-a,run-a2,run-passive,run-passive2,notools*}/` + `build/v1/compare-*.json`
> 2026-10-24 · 流 V1（wave 16）。**所有数字都是本机实测。**
> 重制线 **零改动**；逆向线 **只读**；**未提交 git**。

---

## 0. 一句话结论

**没有真打完仗** —— 但卡点已经从「驱动器不会选目标」搬到了**一个新的产品缺陷 D4**：
**重制侧一旦玩家的攻击「射程内有活着的敌人」，战斗场景就废了**（忍具会把 ROM **彻底冻住**，
普通招式会让场景**不再接受任何输入**）⇒ **玩家的攻击永远打不中** ⇒ 蜂永远打不死 ⇒
护送木叶丸必然在第 5 回合被护送失败（`outcome=2`）⇒ **`outcome=1` 在当前 ROM 上不可达**。

* 驾驶侧（我的活）**已经做完**：闭环驱动器现在能走完整条回合链
  （对白 → 回合横幅 → 选人 → **移动指令** → 移动 → **攻击指令** → 招式 → **目标** → 预览 →
  确认 → 朝向 → 防御 → 敌方回合 → **战斗判定**），
  目标选择用**原版 `w4_play.py` 的判据**（一击致命优先 → 伤害 → 移动量 → 槽位），
  攻击格用 **U2 的 `find_attack_cell`**（可达格中离目标最近的那一格），
  另外带上 U2 的 R3（防御选「否」）与 R4（够不到就**追最近的蜂**）。
* ⛔ **产品缺陷 D4 拦住最后一步**：这不是驾驶器的活（驾驶器的目标选择已被原版规则实现并
  被 ROM 自己的错误码验证），而是**重制线战斗场景的演出层**的缺陷
  ⇒ 修复在 **V2 / 父代理**那边（我按规矩**没动重制线任何文件**）。
* 任务 B 的**逐屏对照表工具**已交付并验证（`v1_compare.py`，原版 sha / 重制侧 sha /
  差 px / 差 bbox 四项齐全），但**「真实战斗打出来的结算链」拿不到**（没有胜利）；
  能给的只有**真实战斗产生的败北屏**（`outcome=2`）对照数据。

---

## 1. 改动文件清单

### 1.1 本仓库（`D:\Github\gba-naruto`）—— 本流独占

| 文件（绝对路径） | 性质 | 说明 |
|---|---|---|
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_battle.py` | **新增** | ⭐ **闭环战斗驱动器**：把原版 `w4_play.py` 的目标判据 + U2 的攻击格/追蜂/防御规则实现成实时驱动器；读 ROM 自己的遥测决定一切；收据里带**逐决策日志**（阶段轨迹、招式表、目标、错误码）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_truth.py` | **新增** | 把重制侧的 `generated_battle_map_content.h` / `generated_battle_action_content.h`（**只读**）解析成 `build/v1/battle-truth.json`：地图 14 的 285 格地形类别 + 87 个主动招式 + 94 个忍具（射程/威力/段数/命中率/目标策略）+ U2 实测的单位数值表。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_compare.py` | **新增** | ⭐ **逐屏对照表**：把重制侧结算链的运行帧与原版真值（`build/s49-victory-capture/w4/settlement-truth/`）逐屏对齐，输出原版 sha / 重制侧 sha / 差 px / 差 bbox。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag.py` | **新增** | 开机后的逐帧阶段转储（用来查清回合链的真实相位顺序）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_roster.py` | **新增** | 遥测里的完整单位表（实测：鸣人/佐助/小樱/护送木叶丸/5 只蜂的坐标、血量、查克拉、控制权）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_action.py` | **新增** | 招式确认的逐帧观察（**抓到了 D4 的第一个症状**：场景帧计数停住）。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_freeze.py` | **新增** | ⭐ **D4 的定位器**：逐个招式条目 × 逐个落点地测「确认后场景还动不动」。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_punch.py` | **新增** | 普通招式（忍者组合拳）在射程内/外的对照。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_hover.py` | **新增** | 「悬停」与「确认」哪个是触发点。 |
| `D:\Github\gba-naruto\tools\s49_battle_balance\v1_diag_stall.py` | **新增** | 卡住后长时间观察（演出是否会自己结束）。 |
| `D:\Github\gba-naruto\notes\s49-fidelity\V1-real-victory.md` | **新增** | 本文件。 |
| `build\v1\**` | 产物 | ROM 副本（`rom-pinned.gba` sha `fb9d2dbd…`）、真值快照、两次独立跑的收据、逐屏对照表。 |

### 1.2 没有改的

* **重制线 `D:\Shell\Github\gba-naruto-butano\butano-sequel` 零改动**（只读地看了
  `battle_scene_controller.h` / `battle_player_action_flow.h` / `battle_action_system.h` /
  `battle_scene_presentation.h` / `battle_combat_presentation.h` /
  `battle_runtime_scene.cpp` / `battle_command_browser.h` / 两个 `generated_*.h`）；
* `tools\s49_package\`（V3 独占）零改动；
* 逆向线 `D:\Shell\gba-naruto-reverse` 未访问；
* 共享的 `build/mgba-probe/mgba-probe.exe` 未动（用的是私有的 `build/mgba-probe-v1/`）。

---

## 2. ⭐ D4：玩家的攻击一旦「射程内有活敌人」，战斗场景就废了

### 2.1 现象 A（**ROM 彻底冻住**）：确认忍具

`v1_diag_freeze.py` 的实测（忍者 = 鸣人，忍具 1 = 十字手里剑，射程 3；蜂在 (6,6)，
鸣人起点 (11,6)）：

| 落点 | 离蜂的曼哈顿距离 | 确认忍具 1 之后 | 场景帧 |
|---|---:|---|---|
| 不移动 (11,6) | 5 | ✅ 正常（相位 6 → 8） | 566 → 612 |
| (10,6) | 4 | ✅ 正常 | 489 → 535 |
| (12,6) | 6 | ✅ 正常 | 489 → 535 |
| (13,6) | 7 | ✅ 正常 | 500 → 546 |
| (11,3) / (11,4) | 8 / 7 | ✅ 正常 | 509 → 555 / 500 → 546 |
| (10,5) / (9,5) | 5 / 4 | ✅ 正常 | 500 → 546 / 509 → 555 |
| **(9,6)** | **3（= 射程）** | ⛔ **冻住** | **499 → 500** |
| **(8,6)** | **2（= 射程内）** | ⛔ **冻住** | **508 → 509** |

⇒ **判据就是「射程内有没有活着的敌人」**（不是落点、不是方向、不是步数）：
**离蜂 4 格以上没事，3 格以内（= 十字手里剑的射程 3）ROM 停机**。
忍具 11（另一个十字手里剑）同样；忍具 37（炸弹，空地目标）**正常** ⇒ 只有**伤害型忍具**触发。

* 冻住时**屏幕上没有 Butano 错误屏**（就是战斗画面），探针 stderr 也没有错误 ⇒
  是**死循环/卡死**，不是 `BN_ERROR`；
* 场景帧计数（`battle_runtime_scene_telemetry::scene_frame`，每个战斗帧 +1）停住 ⇒
  战斗场景的主循环不再返回。

### 2.2 现象 B（**输入死亡**）：确认普通招式

`v1_diag_punch.py` 的实测（忍者组合拳 = active 5，射程 1）：

| 场景 | 结果 |
|---|---|
| 蜂在射程外（(8,6) 的鸣人对 (6,6) 的蜂，距离 2） | ✅ 相位 6 → **8（目标选择）**，场景帧继续走 |
| 蜂在射程内（(8,6) 的鸣人对 (8,7) 的蜂，距离 1） | ⛔ 相位**停在 6**，`last_control_error=0`、`last_player_error=0`（**ROM 根本没处理这次输入**）；此后**招式表再也听不见按键**（连按 Down 动作光标都不动） |

⇒ 与现象 A 同一族：**把「射程内有活敌人」的招式选中（甚至确认）之后，
战斗场景就不再接受输入**。

### 2.3 ⭐ 代码层面的落点（只读地读出来的）

* 战斗场景的**全部输入**都在这一个分支里：
  `battle_runtime_scene.cpp:8672` → `else if(presentation.combat().map_controls_enabled())`
  ⇒ **`presentation.combat()` 一旦 active，整场输入全被吞掉**
  （`battle_combat_presentation.h:870`：`map_controls_enabled() { return ! _active; }`）；
* 战斗演出的结束条件在 `battle_scene_presentation.h:362-395`
  （`advance()` 里 `if(_combat.busy()) _combat.advance(); if(!_combat.busy()) _active = false;`）
  ⇒ **只要玩家这次攻击的战斗演出不结束，场景就永远不收输入**；
* 玩家伤害招式的战斗演出从 `battle_combat_presentation.h:627 begin()` 起
  （`battle_active_action_presentations` / `battle_ninja_tool_presentations`，
  即 **active 05 的尘土、active 16 的火遁、忍具 1/11 的十字手里剑**这些**特制演出内容**），
  而**敌方**的攻击（active 86）没有特制演出 ⇒ **敌人的攻击一切正常**
  （实测：蜂每回合把护送木叶丸从 40 打到 28 → 16 → 4 → 0）。
* ⇒ **嫌疑集中在「玩家伤害招式的特制战斗演出」**：要么 `begin()` 之后的推进不收敛
  （输入死亡），要么里面死循环（ROM 冻住）。**这是重制线的活，本流没改。**

### 2.4 ⭐ D4 的后果（真实战斗的实测数据）

`build/v1/run-passive/`（**真实战斗**，驱动器故意不出手，只走位）：

```
battle_decided = true, outcome = 2（护送失败）, round = 5, frames = 24 832, keys = 314
护送木叶丸：40 → 28 → 16 → 4 → 0（第 5 回合阵亡）
5 只蜂：25/25 → 25/25 → 25/25 → 25/25（**一只都没死**）
```

⇒ **玩家的攻击一次都没打中** ⇒ 蜂打不死 ⇒ 护送必然被护送失败。
⇒ **`outcome=1`（胜利）在当前 ROM 上不可达** ⇒ 结算链的「真实战斗版」也就拿不到。

> ⛔ 旁证：wave 15 的 W1 驱动卡在「目标选择」（716 618 帧、249 次尝试）时**还没走到 D4**——
> 它确认的是列表里第一个条目（active 2 = 影分身术，空地目标），不会触发 D4，
> 但它的候选格与该招式的合法目标不匹配 ⇒ 无限试到回合上限。
> **本流补上原版判据后，驱动器能稳定走到「攻击确认」这一步（V8），真正拦住的是 D4。**

---

## 3. 驾驶侧（我的活）：原版的目标选择策略怎么落到实时驱动器上

### 3.1 原版 `w4_play.py::act()` 的判据（照抄）

| 判据 | 原版（`w4_play.py`） | 本流（`v1_battle.py::make_plan`） |
|---|---|---|
| 射程/直线 | `in_line(cell, enemy, range)`：同行或同列、距离 ≤ 射程 | 重制侧**只查曼哈顿距离**（`battle_action_system.h::_preview`：`distance > maximum_distance()` ⇒ `target_out_of_range`），**实测确认**（§3.3） |
| 目标合法性 | 敌人格 | 重制侧：格子上必须有**活着的敌方单位**（`_validate_target`：`target->side != source.side`），实测错误码 `invalid_target`(7)/`occupied_target_tile`(8)/`target_out_of_range`(9) 三种都见过 ✓ |
| 移动范围 | 曼哈顿半径 3，可走格 147 | **曼哈顿半径 3**；可走格模型取**地形类别 0（plain，144 格）**（比重制侧自己的规则严：重制侧只把 15=墙挡住 ⇒ 平原子集 ⇒ 选中的格子 ROM 一定接受） |
| 选谁打 | `(一击致命优先, 伤害, 移动量, 敌人槽位)` | **同一套**：`score = (0 if 一击致命 else 1, -min(伤害, 敌人HP), 离护送距离, 移动量, 敌人槽位)` |
| 攻击格 | 站在离敌人**直线射程内**的那一格 | **U2 的 `find_attack_cell`**：可达格里**离目标最近**的那一格（步数相同时取步数少的） |
| 够不到时 | 追最近的敌人 | **U2 的 R4**：追最近的蜂（不去「守护送」） |
| 防御决定 | 选「否」（承受伤害） | **U2 的 R3**：Down + A（重制侧所有防御条目都报 `unsupported_category`，只能选否） |
| 招式选择 | 按**有效伤害**排（`w4_play.py` 的 `ATTACKS` 表） | 读**招式目录**（威力 × 段数 × 攻防系数，原版公式 `raw=power*attack/10`、`factor=100-5*isqrt(def)`） |

> ⚠️ **驱动器的一个硬性安全约束**：因为 D4，**招式光标绝不能踏上忍具条目**
> （悬停就死输入，确认就冻 ROM）。驱动器用**招式表顺序**（真值表里的角色招式列表）
> 算出「第一个忍具条目的下标」，**走位绝不越过它** ⇒ 鸣人的招式表只走 index 0…2
> （变身术 / 影分身术 / 忍者组合拳），永远碰不到十字手里剑。
> 实测（V8）：进攻模式的招式条目日志只有 index 1、2 两个**主动招式** ✓。

### 3.2 重制侧战斗规则的实测（不是查来的，是打出来的）

`build/v1/run-passive/battle.json` 的遥测快照（`v1_roster.py` 同样能打出来）：

| 槽位 | 角色 | 阵营 | HP | 攻/防/敏 | 移动 | 查克拉 | 控制 | 位置 |
|---:|---|---|---:|---|---:|---:|---|---|
| 0 | 鸣人 (1) | 玩家 | 138 | 18/17/12 | 3 | 5 | 玩家 | (11,6) |
| 1 | 佐助 (2) | 玩家 | 104 | 15/11/15 | 3 | 4 | 玩家 | (10,14) |
| 2 | 小樱 (3) | 玩家 | 110 | 11/11/14 | 3 | 3 | 玩家 | (8,14) |
| 3 | **护送木叶丸 (30)** | 玩家 | **40** | 8/8/8 | 2 | 2 | **AI** | (10,7) |
| 4–8 | **蜂 (55) × 5** | 敌方 | **25** | 14/6/24 | 3 | 0 | AI | (3,4) (4,8) (3,11) (6,6) (5,13) |

* 鸣人的招式表（ROM 自己的 `action_count/selected_action_id`）：
  `[0] active 2（影分身术，空地，射程 3）`、`[1] active 7（变身术，空地，射程 2）`、
  `[2] active 5（忍者组合拳，**对敌**，射程 1，威力 10×1，98 %）`、
  `[3] 忍具 1（**十字手里剑**，对敌，射程 3，威力 6×**3**，90 %）`、
  `[4] 忍具 11（十字手里剑，对敌，射程 3）`、`[5] 忍具 37（烟幕，空地，射程 2）`
  ⇒ 与 U2 的实测表**逐项相同** ✓；
* 回合链的真实相位顺序（`v1_diag.py` 实测）：
  `script_blocked → turn_banner → unit_selection → **command_selection(移动)** →
  move_selection → **command_selection(攻击)** → action_selection → target_selection
  → target_preview → target_confirmation → end_confirmation → facing_selection →
  defense_decision → enemy_turn → …`
  ⇒ ⚠️ **同一个 command_selection 相位要选不同的指令**：第一次要「移動」、
  第二次要「忍術」、收尾要「終了」—— 驱动器必须**知道自己在哪一个指令表里**
  （`v1_battle.py` 的 `self.expect`），W1 是一律按 A。

### 3.3 目标合法性：ROM 自己的三个错误码（实测）

| 情形 | ROM 的 `selected_action_error` | 含义 |
|---|---:|---|
| 光标在**自己脚下**（占用格） | 7 | `invalid_target` |
| 目标格有**敌人**但招式是空地目标 | 8 | `occupied_target_tile` |
| 目标**超出招式射程** | 9 | `target_out_of_range` |

⇒ 目标选择的三条规则都是**从 ROM 的回执里读出来的**，不是猜的 ✓。

---

## 4. 跑了哪些验证（命令 + 关键数字）

| # | 命令 | 关键数字 |
|---|---|---|
| **V1** | `python tools/s49_battle_balance/v1_truth.py --out build/v1/battle-truth.json` | 地图 14 = **15×19**、plain **144**、wall **120**；主动招式 **87**、忍具 **94**；招式表与 U2 的 dump **逐项相同** |
| **V2** | `python tools/s49_battle_balance/v1_diag.py` | 回合链相位顺序（§3.2）；`unit_count=12`、实际单位 **9** |
| **V3** | `python tools/s49_battle_balance/v1_roster.py` | 完整单位表（§3.2）：护送 40 HP、蜂 25 HP × 5 |
| **V4** | `python tools/s49_battle_balance/v1_diag_freeze.py`（6 个招式条目 × {不移动, 移动到 (8,6)}，再扫 10 个落点） | ⭐ **D4 现象 A**：忍具 1 在离蜂 **≤ 3** 格时确认 ⇒ **ROM 冻住**（场景帧 499→500 / 508→509）；离蜂 ≥ 4 格 ⇒ 正常；忍具 37（空地目标）⇒ 正常 |
| **V5** | `python tools/s49_battle_balance/v1_diag_punch.py` | ⭐ **D4 现象 B**：普通招式射程外 ⇒ 相位 6→8 正常；射程内 ⇒ 相位不动 + 输入死亡 |
| **V6** | `python tools/s49_battle_balance/v1_diag_hover.py` | 驱动器走位到「射程内」时的相位/光标轨迹（用于确认卡点位置） |
| **V7** | `python tools/s49_battle_balance/v1_diag_stall.py` | 卡住后长时间观察：场景帧**继续走**（不是冻住），但**按键全部无效** ⇒ 是「输入死亡」不是「演出很长」 |
| **V8** | `python tools/s49_battle_balance/v1_battle.py --rom build/v1/rom-pinned.gba --out build/v1/run-a --boot --max-turns 400` | 闭环驱动器（进攻模式）：跑到**第一次真实攻击确认**就撞上 D4 ⇒ 收据里记 **`scene-input-dead`**（frame **2332**，action_index 卡在 **2** = 忍者组合拳）；共 2 332 帧 / 76 键。**招式光标从未踏上忍具条目**（实测 entries 只有 index 1、2 两个主动招式） |
| **V9** | 同上 `--out build/v1/run-passive --passive` | ⭐ **真实战斗判定**：`battle_decided=true`、**`outcome=2`**（护送失败）、**round 5**、判定发生在第 **8 182** 帧、整场 **24 832 帧**、**314 键**；护送 40→28→16→4→0；**5 只蜂全程 25/25** |
| **V10** | 同上再跑一遍（`run-a2` / `run-passive2`） | ⭐ **两次独立跑逐字节一致**（去掉输出目录名后）：进攻模式 sha256 `e2ad60298863b84fb57d049305db2108ef50906fd546b584487b593a7957c1cf`、被动模式 sha256 `3500dbe832fe220e8819b3eca6ce2c3f4ca374a9547d9d00fde26a49374d0d8f` |
| **V11** | `python tools/s49_battle_balance/v1_compare.py --remake build/v1/run-passive/shots --out build/v1/compare-real-defeat.json` | ⭐ **真实帧**（真实战斗产生的败北屏）vs 原版 `01-victory.png`：**差 37 486 px**，bbox `[0,0,240,160]` |
| **V12** | `python tools/s49_battle_balance/v1_compare.py --remake build/w1/chain-d/shots --out build/v1/compare-w1-poke.json` | **poke 版基线**（W1 的链）：胜利屏 **37 462**、结算屏 **35 859**、升级屏 1 **0**、升级屏 2–6 **5 870 / 5 946 / 5 229 / 5 639 / 841**、忍具一览 **14 795**、战后对白 **26 819**、任务菜单 **37 694** ⇒ 与 wave 15 W3 的数字**逐项相同** ✓（工具是对的） |

---

## 5. 逐屏对照表（真实战斗版 vs 原版真值）

### 5.1 ⭐ 能给的：**真实战斗**打出来的帧

| 重制侧运行帧 | 原版真值 | 原版 sha256 | 重制侧 sha256 | 差 px | 差 bbox |
|---|---|---|---|---:|---|
| `run-passive/shots/shot-001-outcome-p0.png`（**真实战斗**的败北屏，`outcome=2`） | `01-victory.png` | `d60a1d35e45736dbad3a9d9e7f4fb633d55854dd5b7650c1162702793c3128ea` | `3ad80094283ab35013ba0f891e192ad0a5879a5d0e9e7d68b51bed730b61d17c` | **37 486** | `[0,0,240,160]` |

> 说明：这一屏是**真实战斗**的产物（`outcome=2` 由产品代码判定），
> 但它对应的是**败北**，不是原版的胜利屏 ⇒ 整屏差是预期的（重制侧的结局屏目前基本全黑，
> 属 W3/V2 的 B-1…B-9 接线点）。

### 5.2 ⛔ 拿不到的：**胜利**后的结算链（真实战斗版）

| 阶段 | 原版真值文件 | 真实战斗版 | 状态 |
|---|---|---|---|
| outcome（胜利屏） | `01-victory.png` | — | ⛔ 没有胜利（D4） |
| result（结算屏） | `02-settlement-exp-power-turns.png` | — | ⛔ 同上 |
| level_up × 6 | `03/04/05/06-levelup-*.png` | — | ⛔ 同上 |
| training × 6 | `07-ninja-tool-list.png` | — | ⛔ 同上 |
| post_battle_dialogue × 7 | `08-postbattle-dialogue-1.png` | — | ⛔ 同上 |
| task_menu | `09-task-menu-map.png` | — | ⛔ 同上 |

**poke 版（Z1/W1）的同表数字**见 §4 V12（工具已就绪，D4 修好后直接换 `--remake` 目录即可出真实版表）。

---

## 6. 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **V1-1** | 闭环驱动器过不去是「目标选择策略缺失」 | 读原版 `w4_play.py::act` 的判据 + U2 的 `find_attack_cell`，实装成实时策略 | **不成立（作为根因）**：策略补齐后驱动器能走到**目标选择**，但**攻击确认被产品挡住** | **已证伪（根因）** |
| **V1-2** | 重制侧的回合链是 `选人 → 移动 → 指令 → 招式 → 目标` | `v1_diag.py` 逐帧转储相位 | **不成立**：真实顺序是 `选人 → **指令(移动)** → 移动 → **指令(攻击)** → 招式 → 目标`（`open_command_before_move` 为真） | **已证伪（已修）** |
| **V1-3** | 重制侧目标的合法性 = 敌方单位 + 射程内 | 打三种非法目标，读 ROM 自己的 `selected_action_error` | **成立**：占用格 → 8、超射程 → 9、空地目标打敌人 → 8 | **已确认** |
| **V1-4** | 重制侧的距离判定是曼哈顿 | `battle_action_system.h::_preview` 读码 + 实测（距离 2 时 `target_out_of_range`） | **成立** | **已确认** |
| **V1-5** | 重制侧招式表 = U2 的实测表 | 运行时读 `action_count/selected_action_id/selected_action_target_kind` 与 U2 的 dump 对比 | **成立**：鸣人的 6 个条目逐项相同 | **已确认** |
| **V1-6** | ⭐ **D4**：确认「射程内有活敌人」的招式 ⇒ 场景废掉 | 逐条目 × 逐落点测「确认后场景帧还动不动」 | **成立**：忍具 1 在离蜂 ≤ 3 格 ⇒ **ROM 冻住**（场景帧停）；普通招式射程内 ⇒ **输入死亡**；射程外 ⇒ 正常 | **已确认** |
| **V1-7** | D4 的触发点是「落点」而不是「射程」 | 同上，换方向/换步数（(11,3) (11,4) (13,6) (9,5) (10,5) 全部正常） | **不成立**：正常与否只跟**离蜂的距离**相关 | **已证伪** |
| **V1-8** | D4 只影响忍具 | 同上，逐条目测 | **不成立**：active 5（忍者组合拳）射程内也会死输入 | **已证伪** |
| **V1-9** | D4 是「演出很长、慢慢会结束」 | 卡住后连看 3 000 帧 | **不成立**：场景帧继续走（不是冻住），但按键**永远**无效 ⇒ 演出不结束 | **已证伪** |
| **V1-10** | D4 的代码落点在战斗演出层 | 读 `battle_runtime_scene.cpp:8672`、`battle_scene_presentation.h:362`、`battle_combat_presentation.h:627/870` | **成立**：输入只在 `combat().map_controls_enabled()` 时被处理；演出不结束 ⇒ 输入全死 | **已确认** |
| **V1-11** | ⭐ 玩家的攻击在重制侧**从来没有**打中过 | 真实战斗跑完 5 回合（`run-passive`），看 5 只蜂的 HP | **成立**：全程 25/25；护送 40→0 ⇒ `outcome=2` | **已确认** |
| **V1-12** | ⇒ `outcome=1` 在当前 ROM 上不可达 | 由 V1-11 推：蜂打不死 ⇒ 护送必然被护送失败 | **成立**（推理链闭合；**这是 D4 的直接后果**） | **已确认（推理）** |
| **V1-13** | 两次独立跑逐字节一致 | `run-a` vs `run-a2`、`run-passive` vs `run-passive2`，去掉输出目录名后比 sha256 | **成立**：两种模式都完全一致 | **已确认** |
| **V1-14** | 逐屏对照工具本身是对的 | 用它跑 W1 的 poke 版链，与 wave 15 W3 的数字对 | **成立**：37 462 / 35 859 / 0 / … 逐项相同 | **已确认** |
| **V1-15** | W1 驱动器「目标选择卡死」的直接原因 | 读 W1 的 `choose_target`：它确认的是列表里**第一个**条目（active 2 = 影分身术，**空地**目标），候选格是「敌人格 + 围绕行动单位的方环」，而确认后只等 **18 帧**就判失败 | **可判定**：它的**候选格集合与它选的招式的合法目标不匹配**（空地招式不能打敌人格），加上 18 帧的等待不足以覆盖演出 ⇒ 试到回合上限（249 次 / 716 618 帧）。**D4 是更深的一层**：即使目标摆对了，攻击确认也会被 D4 挡住 | **已确认（机制）** |

---

## 7. 卡在哪 / 剩余风险

1. ⛔ **卡点 = D4（产品缺陷，在重制线）**：玩家伤害招式的战斗演出不结束
   （忍具还会把 ROM 冻住）⇒ 玩家的攻击打不中 ⇒ `outcome=1` 不可达 ⇒
   任务 A 的判据（真实 `outcome=1`）与任务 B 的「真实结算链」都被它挡住。
   **修复归属：V2 / 父代理（重制线）。** 本流按规矩**没改重制线**。
   * 可疑文件（只读定位）：`game/include/konoha/battle_combat_presentation.h`
     （`begin()` / `_skip_empty_runtime_steps()` / `advance()`）、
     `game/include/konoha/battle_scene_presentation.h:362-395`、
     `game/src/battle_runtime_scene.cpp:8672`，
     以及特制演出内容 `generated_battle_action_05_dust_effect_content.h` /
     `generated_battle_action_16_fire_effect_content.h` /
     `generated_battle_ninja_tool_bomb_projectile_content.h`。
   * 判据（修好后怎么验）：用 `v1_diag_freeze.py` 重测 ⇒
     **离蜂 ≤ 3 格确认忍具 1 后场景帧必须继续走**，且 `v1_battle.py` 的进攻模式
     必须出现 `target-accepted` 决策、蜂的 HP 必须下降。
2. ⚠️ **ROM 会变**：本流钉的是 `build/v1/rom-pinned.gba` sha `fb9d2dbd…`（= wave 15 W1 的 ROM）。
   V2 重建后 ROM 的 sha 会变 ⇒ **重跑本流要重新钉 ROM 并重测**（`--rom` 参数已留好）。
3. ⚠️ **地图/招式真值是「生成头文件」的快照**（`v1_truth.py` 解析，只读）：
   若重制侧改了 `generated_battle_map_content.h` / `generated_battle_action_content.h`，
   `build/v1/battle-truth.json` 的 sha 会变（工具会自动重建），
   **本流表格里的「地图 144 plain / 招式 87+94」需要复核**。
4. ⚠️ **驱动器的可走格模型比 ROM 严**（只取地形类别 0；ROM 只挡 15=墙）⇒
   选中的落点 ROM 一定接受，但**偶尔会错过 ROM 允许的落点**（比如河面 class 1）⇒
   偶尔会「明明够得到却没去」。这是**保守**的选择，不是 bug。
5. ⚠️ **本流没有改重制线**，所以**没有单测棘轮/残差数据**可报；
   本流对判定台残差**零影响**（只加仪器，不动产品代码）。

---

## 8. 确认

* **新文件一律 LF、无 BOM**（`v1_battle.py` / `v1_truth.py` / `v1_compare.py` /
  `v1_diag*.py` / `v1_roster.py` / 本文件）；
* **未提交 git**（两个仓都没有 `git add/commit`）；
* **未改重制线任何文件**（只读）；
* **未改 `tools\s49_package\`**（V3 独占）；
* 逆向线**只读**（只用了 `tools/s49_orig_map/battle-14-map-truth.json` 这个
  **本仓**的产物，没有访问逆向线目录）。
